"""Medication reconciliation — spec §36 "Create a dedicated screen."

Read-only comparison between a patient's current active medication list and what one
specific report's text mentions. Never writes to the `medications` table itself — a
clinician acts on what this surfaces, the system never auto-applies a change.

Name matching is deliberately fuzzy (case-insensitive substring), since the same drug
is often recorded with its concentration folded into the name in one place
("Latanoprost 0.005%") and split out separately in another. Dose comparison is
deliberately conservative: free-text extraction and the structured medication record
frequently encode "dose" as different concepts entirely (administration volume, e.g.
"1 drop", vs. strength, e.g. "0.005%") — a raw string difference is surfaced as
"needs review", never as a confident "increased"/"decreased" claim, since that would
require comparable units on both sides that extraction can't guarantee (spec §37:
"Potential inconsistency — clinician review required" rather than an overclaimed fact).
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session as DbSession

from app.ingestion.medications import ExtractedMedication, extract_medications
from app.models.medication import Medication
from app.models.report import Report
from app.schemas.reconciliation import (
    ReconciliationItem,
    ReconciliationResult,
    ReconciliationStatus,
)
from app.services.clinical import list_medications


def reconcile_report(db: DbSession, report: Report) -> ReconciliationResult:
    pages = json.loads(report.extracted_content) if report.extracted_content else []
    detected = extract_medications(pages)
    current = list_medications(db, report.patient_id, active_only=True)

    matched_current_ids: set[str] = set()
    items: list[ReconciliationItem] = [_detected_item(med, current, matched_current_ids) for med in detected]
    items.extend(
        ReconciliationItem(
            status=ReconciliationStatus.NOT_IN_DOCUMENT,
            current_medication_id=medication.id,
            current_medication_name=medication.medication_name,
            current_dose=medication.dose,
            current_frequency=medication.frequency,
        )
        for medication in current
        if medication.id not in matched_current_ids
    )

    return ReconciliationResult(report_id=report.id, report_title=report.title, items=items)


def _detected_item(
    med: ExtractedMedication, current: list[Medication], matched_current_ids: set[str]
) -> ReconciliationItem:
    match = _find_match(med.medication_name, current, matched_current_ids)
    if match is None:
        return ReconciliationItem(
            status=ReconciliationStatus.NEWLY_DETECTED,
            document_medication_name=med.medication_name,
            document_dose=med.dose,
            document_route=med.route,
            document_frequency=med.frequency,
            source_page=med.source_page,
            source_excerpt=med.source_excerpt,
        )

    matched_current_ids.add(match.id)
    doses_differ = (
        med.dose is not None and match.dose is not None and med.dose.strip().lower() != match.dose.strip().lower()
    )
    return ReconciliationItem(
        status=ReconciliationStatus.REVIEW if doses_differ else ReconciliationStatus.UNCHANGED,
        current_medication_id=match.id,
        current_medication_name=match.medication_name,
        current_dose=match.dose,
        current_frequency=match.frequency,
        document_medication_name=med.medication_name,
        document_dose=med.dose,
        document_route=med.route,
        document_frequency=med.frequency,
        source_page=med.source_page,
        source_excerpt=med.source_excerpt,
    )


def _find_match(name: str, current: list[Medication], already_matched: set[str]) -> Medication | None:
    normalized = name.strip().lower()
    for medication in current:
        if medication.id in already_matched:
            continue
        candidate = medication.medication_name.strip().lower()
        if normalized == candidate or normalized in candidate or candidate in normalized:
            return medication
    return None
