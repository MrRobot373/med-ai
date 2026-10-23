"""Structured patient-record context. Facts come straight from the database, so the
model sees exactly what is documented — including explicit statements about what is
NOT documented (we never let absence read as a negative finding)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Allergy, Condition, Encounter, Medication, Observation, Patient


def age(dob: date | None) -> int | None:
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def latest_observations(db: Session, patient_id: str, limit_codes: int = 25) -> list[Observation]:
    rows = db.scalars(
        select(Observation).where(Observation.patient_id == patient_id).order_by(Observation.observed_at.desc())
    ).all()
    seen: dict[str, Observation] = {}
    for o in rows:
        if o.code not in seen:
            seen[o.code] = o
        if len(seen) >= limit_codes:
            break
    return list(seen.values())


def _fmt_obs(o: Observation) -> str:
    value = o.value_text if o.value_num is None else f"{o.value_num:g}"
    ref = f", ref {o.ref_text}" if o.ref_text else ""
    flag = f", {o.flag.upper()}" if o.flag and o.flag != "normal" else ""
    return f"{o.name}: {value} {o.unit or ''}".strip() + f" ({o.observed_at.date().isoformat()}{ref}{flag})"


def patient_record_text(db: Session, patient: Patient, *, max_encounters: int = 5) -> str:
    conditions = db.scalars(select(Condition).where(Condition.patient_id == patient.id)).all()
    allergies = db.scalars(select(Allergy).where(Allergy.patient_id == patient.id, Allergy.status == "active")).all()
    meds = db.scalars(select(Medication).where(Medication.patient_id == patient.id)).all()
    encounters = db.scalars(
        select(Encounter)
        .where(Encounter.patient_id == patient.id)
        .order_by(Encounter.started_at.desc())
        .limit(max_encounters)
    ).all()
    obs = latest_observations(db, patient.id)

    a = age(patient.date_of_birth)
    lines = [
        f"Patient: {patient.full_name} | MRN {patient.mrn} | {a if a is not None else 'age unknown'} y | sex {patient.sex}",
    ]
    active = [c for c in conditions if c.status in ("active", "suspected")]
    past = [c for c in conditions if c.status not in ("active", "suspected")]
    lines.append(
        "Active problems: "
        + (
            "; ".join(
                f"{c.name}{' (' + c.code + ')' if c.code else ''}{' [suspected]' if c.status == 'suspected' else ''}"
                for c in active
            )
            or "none documented"
        )
    )
    if past:
        lines.append("Past/resolved problems: " + "; ".join(c.name for c in past))
    lines.append(
        "Allergies: "
        + (
            "; ".join(f"{al.substance}{' — ' + al.reaction if al.reaction else ''} ({al.severity})" for al in allergies)
            or "none documented (absence is NOT confirmation of no allergies)"
        )
    )
    active_meds = [m for m in meds if m.status == "active"]
    lines.append(
        "Active medications: "
        + (
            "; ".join(" ".join(filter(None, [m.name, m.dose, m.route, m.frequency])) for m in active_meds)
            or "none documented"
        )
    )
    stopped = [m for m in meds if m.status != "active"]
    if stopped:
        lines.append("Stopped/held medications: " + "; ".join(f"{m.name} ({m.status})" for m in stopped))
    lines.append("Latest results: " + ("; ".join(_fmt_obs(o) for o in obs) or "none recorded"))
    if encounters:
        lines.append("Recent encounters:")
        for e in encounters:
            note = (e.notes or "").replace("\n", " ")
            vitals = ", ".join(f"{k} {v}" for k, v in (e.vitals or {}).items() if v not in (None, ""))
            lines.append(
                f"- {e.started_at.date().isoformat()} {e.type} ({e.status}): {e.reason or 'no reason recorded'}"
                + (f" | vitals: {vitals}" if vitals else "")
                + (f" | note: {note[:600]}" if note else "")
            )
    return "\n".join(lines)
