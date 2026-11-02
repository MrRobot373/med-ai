"""Certificates, fitness letters, referral letters and plain-language visit summaries.

A letter starts as an editable draft with text filled from the patient's record. Issuing it gives it the
next number in a gap-free yearly sequence and freezes it; a wrong letter is voided with a reason, never edited.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clinical.context import age
from app.db import utcnow
from app.models import Allergy, Condition, Counter, Encounter, Letter, Medication, Patient, Prescription
from app.services import printing, runtime_config

KINDS = {
    "medical_certificate": ("Medical certificate", "MC"),
    "fitness": ("Fitness certificate", "FC"),
    "referral": ("Referral letter", "RL"),
    "visit_summary": ("Visit summary", "VS"),
}
FIELD_KEYS = {
    "medical_certificate": ("diagnosis", "from_date", "to_date", "days", "show_diagnosis"),
    "fitness": ("purpose", "examined_on"),
    "referral": (
        "to_name",
        "to_speciality",
        "to_hospital",
        "urgency",
        "reason",
        "problems",
        "medicines",
        "allergies",
        "investigations",
    ),
    "visit_summary": ("diagnosis", "advice", "follow_up", "items", "complaint"),
}


def _d(s) -> date | None:
    if not s:
        return None
    return s if isinstance(s, date) else date.fromisoformat(str(s)[:10])


def _fmt(d: date | None) -> str:
    return printing.fmt_date(d) if d else ""


def next_number(db: Session, kind: str, year: int) -> str:
    prefix = KINDS[kind][1]
    key = f"{prefix}-{year}"
    row = db.get(Counter, key)
    if row is None:
        row = Counter(key=key, value=0)
        db.add(row)
    row.value += 1
    db.flush()
    return f"{key}-{row.value:04d}"


def _latest_encounter(db: Session, patient_id: str, encounter_id: str | None) -> Encounter | None:
    if encounter_id:
        return db.get(Encounter, encounter_id)
    return db.scalars(
        select(Encounter).where(Encounter.patient_id == patient_id).order_by(Encounter.started_at.desc())
    ).first()


def defaults(db: Session, kind: str, patient: Patient, enc: Encounter | None) -> tuple[dict, str]:
    """Starting fields and body text for a new draft."""
    today = printing.local_date()
    name = patient.full_name
    who = f"{name}" + (f", {age(patient.date_of_birth)} years" if patient.date_of_birth else "")
    dx = "; ".join(d.get("name", "") for d in (enc.diagnoses if enc else []) or []) or ""
    if kind == "medical_certificate":
        days = 3
        fields = {
            "diagnosis": dx,
            "from_date": today.isoformat(),
            "to_date": (today + timedelta(days=days - 1)).isoformat(),
            "days": days,
            "show_diagnosis": False,
        }
        return fields, _certificate_body(patient, today, today + timedelta(days=days - 1))
    if kind == "fitness":
        fields = {"purpose": "resume work", "examined_on": today.isoformat()}
        return fields, _fitness_body(patient, today, "resume work")
    if kind == "referral":
        problems = [
            c.name
            for c in db.scalars(
                select(Condition).where(Condition.patient_id == patient.id, Condition.status == "active")
            )
        ]
        meds = [
            " ".join(x for x in (m.name, m.dose, m.frequency) if x)
            for m in db.scalars(
                select(Medication).where(Medication.patient_id == patient.id, Medication.status == "active")
            )
        ]
        allergies = [
            f"{a.substance}" + (f" ({a.reaction})" if a.reaction else "")
            for a in db.scalars(select(Allergy).where(Allergy.patient_id == patient.id, Allergy.status == "active"))
        ]
        fields = {
            "to_name": "",
            "to_speciality": "",
            "to_hospital": "",
            "urgency": "routine",
            "reason": enc.reason if enc and enc.reason else "",
            "problems": "\n".join(problems),
            "medicines": "\n".join(meds),
            "allergies": "\n".join(allergies),
            "investigations": "",
        }
        body = f"Thank you for seeing {who}, whom I am referring for your opinion and further management." + (
            f" Working diagnosis: {dx}." if dx else ""
        )
        return fields, body
    if kind == "visit_summary":
        rx = None
        if enc:
            rx = db.scalars(
                select(Prescription)
                .where(Prescription.encounter_id == enc.id, Prescription.status == "final")
                .order_by(Prescription.created_at.desc())
            ).first()
        items = [
            {
                "drug": i.drug,
                "generic": i.generic,
                "dose": i.dose,
                "frequency": i.frequency,
                "duration_days": i.duration_days,
            }
            for i in (rx.items if rx else [])
        ]
        fields = {
            "diagnosis": (rx.diagnosis if rx and rx.diagnosis else dx),
            "advice": (rx.advice if rx else "") or "",
            "follow_up": rx.follow_up_date.isoformat() if rx and rx.follow_up_date else "",
            "items": items,
            "complaint": enc.reason if enc and enc.reason else "",
        }
        when = _fmt(printing.local_date(enc.started_at)) if enc and enc.started_at else _fmt(today)
        body = f"Thank you for visiting us on {when}. This is a summary of your visit for you to keep."
        return fields, body
    raise HTTPException(422, "Unknown letter type")


def _who(patient: Patient) -> str:
    return patient.full_name + (f", {age(patient.date_of_birth)} years" if patient.date_of_birth else "")


def _certificate_body(patient: Patient, start: date, end: date) -> str:
    days = (end - start).days + 1
    unit = "day" if days == 1 else "days"
    return (
        f"This is to certify that {_who(patient)} was examined by me on {_fmt(start)} and is advised rest "
        f"for {days} {unit}, from {_fmt(start)} to {_fmt(end)}."
    )


def _fitness_body(patient: Patient, examined: date, purpose: str) -> str:
    return (
        f"This is to certify that {_who(patient)} was examined by me on {_fmt(examined)}. "
        f"On examination, the patient is found to be medically fit to {purpose}."
    )


def create(db: Session, kind: str, patient: Patient, author, encounter_id: str | None, branch_id: str | None) -> Letter:
    if kind not in KINDS:
        raise HTTPException(422, "Unknown letter type")
    enc = _latest_encounter(db, patient.id, encounter_id)
    fields, body = defaults(db, kind, patient, enc)
    letter = Letter(
        kind=kind,
        patient_id=patient.id,
        encounter_id=enc.id if enc else None,
        author_id=author.id,
        branch_id=branch_id,
        fields=fields,
        body=body,
    )
    db.add(letter)
    db.commit()
    return letter


def update(db: Session, letter: Letter, fields: dict | None, body: str | None) -> Letter:
    if letter.status != "draft":
        raise HTTPException(409, "An issued letter cannot be changed. Void it and write a new one.")
    allowed = FIELD_KEYS[letter.kind]
    if fields is not None:
        merged = dict(letter.fields or {})
        merged.update({k: v for k, v in fields.items() if k in allowed})
        patient = db.get(Patient, letter.patient_id)
        # The standard wording follows the fields unless the doctor is writing their own text in this save.
        if letter.kind == "medical_certificate":
            a, b = _d(merged.get("from_date")), _d(merged.get("to_date"))
            if a and b:
                if b < a:
                    raise HTTPException(422, "The end date is before the start date.")
                merged["days"] = (b - a).days + 1
                if body is None:
                    letter.body = _certificate_body(patient, a, b)
        elif letter.kind == "fitness" and body is None and merged.get("purpose"):
            letter.body = _fitness_body(
                patient, _d(merged.get("examined_on")) or printing.local_date(), merged["purpose"]
            )
        letter.fields = merged
    if body is not None:
        letter.body = body[:6000]
    db.commit()
    return letter


def issue(db: Session, letter: Letter) -> Letter:
    if letter.status != "draft":
        raise HTTPException(409, "This letter has already been issued.")
    if not letter.body.strip():
        raise HTTPException(422, "The letter has no text.")
    f = letter.fields or {}
    if letter.kind == "referral" and not (f.get("to_name") or f.get("to_speciality") or f.get("to_hospital")):
        raise HTTPException(422, "Say who the patient is being referred to.")
    if letter.kind == "fitness" and not f.get("purpose"):
        raise HTTPException(422, "Say what the patient is certified fit for.")
    letter.number = next_number(db, letter.kind, printing.local_date().year)
    letter.status = "final"
    letter.finalized_at = utcnow()
    db.commit()
    return letter


def void(db: Session, letter: Letter, reason: str) -> Letter:
    if letter.status != "final":
        raise HTTPException(409, "Only an issued letter can be voided. Delete a draft instead.")
    letter.status, letter.void_reason = "void", reason[:300]
    db.commit()
    return letter


def out(letter: Letter) -> dict:
    return {
        "id": letter.id,
        "kind": letter.kind,
        "title": KINDS[letter.kind][0],
        "number": letter.number,
        "status": letter.status,
        "patient_id": letter.patient_id,
        "encounter_id": letter.encounter_id,
        "branch_id": letter.branch_id,
        "fields": letter.fields or {},
        "body": letter.body,
        "created_at": letter.created_at,
        "finalized_at": letter.finalized_at,
        "void_reason": letter.void_reason,
    }


def _lines(text: str | None) -> list[str]:
    return [x.strip() for x in (text or "").splitlines() if x.strip()]


def letter_view(db: Session, letter: Letter, cfg=None) -> dict:
    cfg = cfg or runtime_config.load(db).print
    p = db.get(Patient, letter.patient_id)
    f = letter.fields or {}
    when = printing.local_date(letter.finalized_at or letter.created_at)
    view = {
        "id": letter.id,
        "title": KINDS[letter.kind][0],
        "number": letter.number,
        "date": printing.fmt_date(when),
        "patient": {"name": p.full_name, "mrn": p.mrn, "age": age(p.date_of_birth), "sex": printing.SEX.get(p.sex, "")},
        "paragraphs": [letter.body],
        "sections": [],
        "after": [],
        "verify_code": printing.verify_code(letter.id, cfg, "letter") if letter.status == "final" else None,
    }
    if letter.kind == "medical_certificate" and f.get("show_diagnosis") and f.get("diagnosis"):
        view["after"].append(f"Diagnosis: {f['diagnosis']}")
    if letter.kind == "referral":
        view["to"] = [
            "To,",
            ", ".join(x for x in (f.get("to_name"), f.get("to_speciality")) if x),
            f.get("to_hospital") or "",
        ]
        if f.get("urgency") == "urgent":
            view["paragraphs"].insert(0, "URGENT — please see at the earliest.")
        view["sections"] = [
            {"heading": "Reason for referral", "lines": _lines(f.get("reason"))},
            {"heading": "Problems", "lines": _lines(f.get("problems"))},
            {"heading": "Current medicines", "lines": _lines(f.get("medicines"))},
            {"heading": "Allergies", "lines": _lines(f.get("allergies"))},
            {"heading": "Investigations done", "lines": _lines(f.get("investigations"))},
        ]
    if letter.kind == "visit_summary":
        view["sections"] = [
            {"heading": "Why you came", "lines": _lines(f.get("complaint"))},
            {"heading": "What we found", "lines": _lines(f.get("diagnosis"))},
            {"heading": "Advice", "lines": _lines(f.get("advice"))},
        ]
        view["items"] = f.get("items") or []
        if f.get("follow_up"):
            view["after"].append(
                f"Please come back on {printing.fmt_date(_d(f['follow_up']), long=True)}. Come earlier if you feel worse."
            )
    return view
