"""Encounter service (spec §27 Current Encounter Workflow)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.models.encounter import Encounter, EncounterStatus
from app.models.patient import Patient
from app.schemas.encounter import EncounterCreate, EncounterUpdate


def _next_encounter_number(db: DbSession, patient: Patient) -> str:
    count = db.scalar(select(func.count()).select_from(Encounter).where(Encounter.patient_id == patient.id)) or 0
    return f"{patient.mrn}-ENC{count + 1:03d}"


def create_encounter(db: DbSession, patient: Patient, payload: EncounterCreate, created_by: str | None) -> Encounter:
    encounter = Encounter(
        patient_id=patient.id,
        encounter_number=_next_encounter_number(db, patient),
        encounter_type=payload.encounter_type,
        start_datetime=payload.start_datetime or datetime.now(UTC),
        status=EncounterStatus.ACTIVE,
        chief_complaint=payload.chief_complaint,
        clinician_note=payload.clinician_note,
        created_by=created_by,
    )
    db.add(encounter)
    db.commit()
    db.refresh(encounter)
    return encounter


def get_encounter(db: DbSession, encounter_id: str) -> Encounter | None:
    return db.get(Encounter, encounter_id)


def list_encounters(db: DbSession, patient_id: str) -> list[Encounter]:
    stmt = (
        select(Encounter)
        .where(Encounter.patient_id == patient_id)
        .order_by(Encounter.start_datetime.desc())
    )
    return list(db.scalars(stmt))


def update_encounter(db: DbSession, encounter: Encounter, payload: EncounterUpdate) -> Encounter:
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(encounter, field, value)
    db.commit()
    db.refresh(encounter)
    return encounter
