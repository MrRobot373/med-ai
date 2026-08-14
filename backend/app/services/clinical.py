"""Conditions / allergies / medications service (spec §32/§36).

Medication history is append-only (spec §36 "preserve history rather than overwriting
previous prescriptions"): `stop_medication` never deletes or mutates the original
dose/frequency a clinician entered, it only sets `active=False` + `stop_date`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.allergy import Allergy
from app.models.condition import Condition, ConditionStatus
from app.models.medication import Medication
from app.schemas.allergy import AllergyCreate, AllergyUpdate
from app.schemas.condition import ConditionCreate, ConditionUpdate
from app.schemas.medication import MedicationCreate, MedicationStop

# --- Conditions ---------------------------------------------------------------


def create_condition(db: DbSession, patient_id: str, payload: ConditionCreate) -> Condition:
    condition = Condition(patient_id=patient_id, **payload.model_dump())
    db.add(condition)
    db.commit()
    db.refresh(condition)
    return condition


def list_conditions(db: DbSession, patient_id: str, active_only: bool = False) -> list[Condition]:
    stmt = select(Condition).where(Condition.patient_id == patient_id)
    if active_only:
        stmt = stmt.where(Condition.status == ConditionStatus.ACTIVE)
    stmt = stmt.order_by(Condition.onset_date.desc().nulls_last(), Condition.created_at.desc())
    return list(db.scalars(stmt))


def get_condition(db: DbSession, condition_id: str) -> Condition | None:
    return db.get(Condition, condition_id)


def update_condition(db: DbSession, condition: Condition, payload: ConditionUpdate) -> Condition:
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("status") == ConditionStatus.RESOLVED and "resolved_date" not in updates:
        updates["resolved_date"] = datetime.now(UTC).date()
    for field, value in updates.items():
        setattr(condition, field, value)
    db.commit()
    db.refresh(condition)
    return condition


# --- Allergies -----------------------------------------------------------------


def create_allergy(db: DbSession, patient_id: str, payload: AllergyCreate) -> Allergy:
    allergy = Allergy(patient_id=patient_id, **payload.model_dump())
    db.add(allergy)
    db.commit()
    db.refresh(allergy)
    return allergy


def list_allergies(db: DbSession, patient_id: str) -> list[Allergy]:
    stmt = select(Allergy).where(Allergy.patient_id == patient_id).order_by(Allergy.created_at.desc())
    return list(db.scalars(stmt))


def get_allergy(db: DbSession, allergy_id: str) -> Allergy | None:
    return db.get(Allergy, allergy_id)


def update_allergy(db: DbSession, allergy: Allergy, payload: AllergyUpdate) -> Allergy:
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(allergy, field, value)
    db.commit()
    db.refresh(allergy)
    return allergy


# --- Medications -----------------------------------------------------------------


def create_medication(db: DbSession, patient_id: str, payload: MedicationCreate) -> Medication:
    medication = Medication(patient_id=patient_id, active=True, **payload.model_dump())
    db.add(medication)
    db.commit()
    db.refresh(medication)
    return medication


def list_medications(db: DbSession, patient_id: str, active_only: bool = False) -> list[Medication]:
    stmt = select(Medication).where(Medication.patient_id == patient_id)
    if active_only:
        stmt = stmt.where(Medication.active.is_(True))
    stmt = stmt.order_by(Medication.active.desc(), Medication.start_date.desc().nulls_last())
    return list(db.scalars(stmt))


def get_medication(db: DbSession, medication_id: str) -> Medication | None:
    return db.get(Medication, medication_id)


def stop_medication(db: DbSession, medication: Medication, payload: MedicationStop) -> Medication:
    medication.active = False
    medication.stop_date = payload.stop_date or datetime.now(UTC).date()
    db.commit()
    db.refresh(medication)
    return medication
