"""Structured patient/encounter/report context assembly — spec §43 Stage 4: "Retrieve
relevant structured information from SQLite first. Do NOT embed every structured
database row unnecessarily." Plain, deterministic DB reads formatted as facts text —
never a retrieval/embedding operation. An empty list renders as an honest "None
documented" line (spec §2: never let silence be mistaken for "confirmed absent"),
matching the same wording the Overview tab already uses for allergies.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session as DbSession

from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.report import Report
from app.models.vision_analysis import VisionAnalysisStatus
from app.services.clinical import list_allergies, list_conditions, list_medications
from app.services.vision import get_analysis


def _age(dob: date) -> int:
    today = datetime.now(UTC).date()
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return years


def build_patient_facts(db: DbSession, patient: Patient) -> str:
    lines = [
        f"Patient: {patient.first_name} {patient.last_name} (MRN {patient.mrn})",
        f"Age: {_age(patient.date_of_birth)}  Sex: {patient.sex.value}",
    ]

    conditions = list_conditions(db, patient.id, active_only=True)
    lines.append(
        "Active conditions: "
        + (", ".join(c.display for c in conditions) if conditions else "None documented")
    )

    allergies = list_allergies(db, patient.id)
    if allergies:
        lines.append("Allergies: " + "; ".join(f"{a.substance} ({a.severity.value})" for a in allergies))
    else:
        lines.append("Allergies: None documented — this means not yet recorded, not confirmed absent")

    medications = list_medications(db, patient.id, active_only=True)
    if medications:
        med_lines = []
        for medication in medications:
            parts = [medication.medication_name]
            if medication.dose:
                parts.append(medication.dose)
            if medication.frequency:
                parts.append(medication.frequency)
            med_lines.append(" ".join(parts))
        lines.append("Current medications: " + "; ".join(med_lines))
    else:
        lines.append("Current medications: None documented")

    return "\n".join(lines)


def build_encounter_facts(encounter: Encounter) -> str:
    lines = [
        f"Encounter: {encounter.encounter_number} ({encounter.encounter_type.value}, status: {encounter.status.value})",
        f"Date: {encounter.start_datetime.date().isoformat()}",
    ]
    lines.append(f"Chief complaint: {encounter.chief_complaint}" if encounter.chief_complaint else "Chief complaint: Not documented")
    if encounter.clinician_note:
        lines.append(f"Clinician note: {encounter.clinician_note}")
    return "\n".join(lines)


def build_report_facts(db: DbSession, report: Report) -> str:
    lines = [f"Report: {report.title} ({report.report_type.value.replace('_', ' ')})"]
    lines.append(f"Date: {report.report_date.isoformat()}" if report.report_date else "Date: Not detected")

    if report.extracted_content:
        pages = json.loads(report.extracted_content)
        for page in pages:
            text = (page.get("text") or "").strip()
            if text:
                lines.append(f"[Page {page.get('page')}]\n{text}")
    else:
        lines.append("(No extracted text is available for this report.)")

    # A selected image/DICOM report's vision analysis (Phase 09) is directly on-topic
    # here — surfaced as a fact about the report itself, the same way OCR/parsed text
    # is, rather than only via a separate retrieval hit.
    vision = get_analysis(db, report.id)
    if vision and vision.status == VisionAnalysisStatus.SUCCESS and vision.payload:
        payload = json.loads(vision.payload)
        vision_lines = [f"Image type: {payload['image_type']}"] if payload.get("image_type") else []
        for key, label in (
            ("observations", "Observations"),
            ("measurements_visible", "Measurements visible"),
            ("clinical_entities", "Clinical entities"),
            ("quality_limitations", "Image quality limitations"),
            ("uncertainties", "Uncertainties"),
        ):
            values = payload.get(key)
            if values:
                vision_lines.append(f"{label}: " + "; ".join(values))
        if vision_lines:
            lines.append("Vision analysis:\n" + "\n".join(vision_lines))

    return "\n".join(lines)
