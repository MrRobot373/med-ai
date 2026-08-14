"""Patient CRUD/search service (spec §23/§24).

Patient isolation (spec §16) starts here: every query in this module is always scoped
by an explicit `Patient.id` — there is no "search across all patients' clinical data"
code path anywhere in this file for callers to accidentally reuse incorrectly once RAG
retrieval (Phase 07) needs the same guarantee.
"""

from __future__ import annotations

import secrets

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as DbSession

from app.models.condition import Condition, ConditionStatus
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientListItem, PatientUpdate

MAX_CONDITION_CHIPS = 5


def generate_mrn(db: DbSession) -> str:
    """Demo-friendly MRN generator — not a real hospital MRN registry integration.
    Retries on the (astronomically unlikely) collision rather than trusting entropy
    alone, since `mrn` is a unique column."""
    for _ in range(10):
        candidate = f"MRN-{secrets.token_hex(4).upper()}"
        if db.scalar(select(Patient.id).where(Patient.mrn == candidate)) is None:
            return candidate
    raise RuntimeError("Could not generate a unique MRN after 10 attempts")


def create_patient(db: DbSession, payload: PatientCreate) -> Patient:
    mrn = payload.mrn or generate_mrn(db)
    patient = Patient(
        mrn=mrn,
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        preferred_name=payload.preferred_name,
        date_of_birth=payload.date_of_birth,
        sex=payload.sex,
        phone=payload.phone,
        email=payload.email,
        notes=payload.notes,
        synthetic=False,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def get_patient(db: DbSession, patient_id: str) -> Patient | None:
    return db.get(Patient, patient_id)


def update_patient(db: DbSession, patient: Patient, payload: PatientUpdate) -> Patient:
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(patient, field, value)
    db.commit()
    db.refresh(patient)
    return patient


def archive_patient(db: DbSession, patient: Patient) -> Patient:
    patient.archived = True
    db.commit()
    db.refresh(patient)
    return patient


def unarchive_patient(db: DbSession, patient: Patient) -> Patient:
    patient.archived = False
    db.commit()
    db.refresh(patient)
    return patient


def search_patients(db: DbSession, query: str | None, include_archived: bool) -> list[PatientListItem]:
    stmt = select(Patient)
    if not include_archived:
        stmt = stmt.where(Patient.archived.is_(False))
    if query:
        like = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                Patient.first_name.ilike(like),
                Patient.last_name.ilike(like),
                Patient.preferred_name.ilike(like),
                Patient.mrn.ilike(like),
            )
        )
    stmt = stmt.order_by(Patient.last_name, Patient.first_name)
    patients = list(db.scalars(stmt))
    if not patients:
        return []

    patient_ids = [p.id for p in patients]

    last_encounter_rows = db.execute(
        select(Encounter.patient_id, func.max(Encounter.start_datetime))
        .where(Encounter.patient_id.in_(patient_ids))
        .group_by(Encounter.patient_id)
    ).all()
    last_encounter_by_patient = dict(last_encounter_rows)

    condition_rows = db.execute(
        select(Condition.patient_id, Condition.display)
        .where(Condition.patient_id.in_(patient_ids), Condition.status == ConditionStatus.ACTIVE)
        .order_by(Condition.onset_date.desc().nulls_last())
    ).all()
    conditions_by_patient: dict[str, list[str]] = {}
    for pid, display in condition_rows:
        bucket = conditions_by_patient.setdefault(pid, [])
        if len(bucket) < MAX_CONDITION_CHIPS:
            bucket.append(display)

    return [
        PatientListItem(
            id=p.id,
            mrn=p.mrn,
            first_name=p.first_name,
            last_name=p.last_name,
            preferred_name=p.preferred_name,
            sex=p.sex,
            date_of_birth=p.date_of_birth,
            synthetic=p.synthetic,
            archived=p.archived,
            last_encounter_at=last_encounter_by_patient.get(p.id),
            active_condition_names=conditions_by_patient.get(p.id, []),
        )
        for p in patients
    ]
