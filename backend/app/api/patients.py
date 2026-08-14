"""Patient system endpoints (spec §104): patients, encounters, conditions, allergies,
medications, and the derived timeline.

Read access (GET) is open to any authenticated role (admin/doctor/viewer). Every write
(create/update/archive) requires admin or doctor — spec §18 "Viewer: read-only demo
access, cannot modify patient information."
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DbDep
from app.auth.dependencies import CurrentUser, require_role
from app.models.allergy import Allergy
from app.models.condition import Condition
from app.models.encounter import Encounter
from app.models.medication import Medication
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.schemas.allergy import AllergyCreate, AllergyOut, AllergyUpdate
from app.schemas.condition import ConditionCreate, ConditionOut, ConditionUpdate
from app.schemas.encounter import EncounterCreate, EncounterOut, EncounterUpdate
from app.schemas.medication import MedicationCreate, MedicationOut, MedicationStop
from app.schemas.patient import PatientCreate, PatientListItem, PatientOut, PatientUpdate
from app.schemas.timeline import TimelineEvent
from app.services import clinical
from app.services import encounters as encounter_service
from app.services import patients as patient_service
from app.services import timeline as timeline_service

router = APIRouter(prefix="/api", tags=["patients"])

# A distinct Annotated alias (not a reused CurrentUser + a default value, which would
# silently NOT apply the role check — Annotated's Depends is fixed at declaration time).
WriteUser = Annotated[User, Depends(require_role(UserRole.ADMIN, UserRole.DOCTOR))]


def _get_patient_or_404(db: DbDep, patient_id: str) -> Patient:
    patient = patient_service.get_patient(db, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


def _get_encounter_or_404(db: DbDep, encounter_id: str) -> Encounter:
    encounter = encounter_service.get_encounter(db, encounter_id)
    if encounter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encounter not found")
    return encounter


def _get_condition_or_404(db: DbDep, condition_id: str) -> Condition:
    condition = clinical.get_condition(db, condition_id)
    if condition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Condition not found")
    return condition


def _get_allergy_or_404(db: DbDep, allergy_id: str) -> Allergy:
    allergy = clinical.get_allergy(db, allergy_id)
    if allergy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allergy not found")
    return allergy


def _get_medication_or_404(db: DbDep, medication_id: str) -> Medication:
    medication = clinical.get_medication(db, medication_id)
    if medication is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")
    return medication


# --- Patients --------------------------------------------------------------------


@router.get("/patients", response_model=list[PatientListItem])
def list_patients(
    db: DbDep,
    _current_user: CurrentUser,
    q: str | None = None,
    include_archived: bool = False,
) -> list[PatientListItem]:
    return patient_service.search_patients(db, query=q, include_archived=include_archived)


@router.post("/patients", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(payload: PatientCreate, db: DbDep, _current_user: WriteUser) -> PatientOut:
    patient = patient_service.create_patient(db, payload)
    return PatientOut.model_validate(patient)


@router.get("/patients/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: str, db: DbDep, _current_user: CurrentUser) -> PatientOut:
    return PatientOut.model_validate(_get_patient_or_404(db, patient_id))


@router.patch("/patients/{patient_id}", response_model=PatientOut)
def update_patient(patient_id: str, payload: PatientUpdate, db: DbDep, _current_user: WriteUser) -> PatientOut:
    patient = _get_patient_or_404(db, patient_id)
    return PatientOut.model_validate(patient_service.update_patient(db, patient, payload))


@router.post("/patients/{patient_id}/archive", response_model=PatientOut)
def archive_patient(patient_id: str, db: DbDep, _current_user: WriteUser) -> PatientOut:
    patient = _get_patient_or_404(db, patient_id)
    return PatientOut.model_validate(patient_service.archive_patient(db, patient))


@router.post("/patients/{patient_id}/unarchive", response_model=PatientOut)
def unarchive_patient(patient_id: str, db: DbDep, _current_user: WriteUser) -> PatientOut:
    patient = _get_patient_or_404(db, patient_id)
    return PatientOut.model_validate(patient_service.unarchive_patient(db, patient))


# --- Timeline ----------------------------------------------------------------------


@router.get("/patients/{patient_id}/timeline", response_model=list[TimelineEvent])
def get_patient_timeline(patient_id: str, db: DbDep, _current_user: CurrentUser) -> list[TimelineEvent]:
    _get_patient_or_404(db, patient_id)
    return timeline_service.build_timeline(db, patient_id)


# --- Encounters ----------------------------------------------------------------------


@router.get("/patients/{patient_id}/encounters", response_model=list[EncounterOut])
def list_patient_encounters(patient_id: str, db: DbDep, _current_user: CurrentUser) -> list[EncounterOut]:
    _get_patient_or_404(db, patient_id)
    return [EncounterOut.model_validate(e) for e in encounter_service.list_encounters(db, patient_id)]


@router.post("/patients/{patient_id}/encounters", response_model=EncounterOut, status_code=status.HTTP_201_CREATED)
def create_patient_encounter(
    patient_id: str, payload: EncounterCreate, db: DbDep, current_user: WriteUser
) -> EncounterOut:
    patient = _get_patient_or_404(db, patient_id)
    encounter = encounter_service.create_encounter(db, patient, payload, created_by=current_user.id)
    return EncounterOut.model_validate(encounter)


@router.get("/encounters/{encounter_id}", response_model=EncounterOut)
def get_encounter(encounter_id: str, db: DbDep, _current_user: CurrentUser) -> EncounterOut:
    return EncounterOut.model_validate(_get_encounter_or_404(db, encounter_id))


@router.patch("/encounters/{encounter_id}", response_model=EncounterOut)
def update_encounter(encounter_id: str, payload: EncounterUpdate, db: DbDep, _current_user: WriteUser) -> EncounterOut:
    encounter = _get_encounter_or_404(db, encounter_id)
    return EncounterOut.model_validate(encounter_service.update_encounter(db, encounter, payload))


# --- Conditions ----------------------------------------------------------------------


@router.get("/patients/{patient_id}/conditions", response_model=list[ConditionOut])
def list_patient_conditions(patient_id: str, db: DbDep, _current_user: CurrentUser) -> list[ConditionOut]:
    _get_patient_or_404(db, patient_id)
    return [ConditionOut.model_validate(c) for c in clinical.list_conditions(db, patient_id)]


@router.post("/patients/{patient_id}/conditions", response_model=ConditionOut, status_code=status.HTTP_201_CREATED)
def create_patient_condition(
    patient_id: str, payload: ConditionCreate, db: DbDep, _current_user: WriteUser
) -> ConditionOut:
    _get_patient_or_404(db, patient_id)
    return ConditionOut.model_validate(clinical.create_condition(db, patient_id, payload))


@router.patch("/conditions/{condition_id}", response_model=ConditionOut)
def update_condition(condition_id: str, payload: ConditionUpdate, db: DbDep, _current_user: WriteUser) -> ConditionOut:
    condition = _get_condition_or_404(db, condition_id)
    return ConditionOut.model_validate(clinical.update_condition(db, condition, payload))


# --- Allergies ----------------------------------------------------------------------


@router.get("/patients/{patient_id}/allergies", response_model=list[AllergyOut])
def list_patient_allergies(patient_id: str, db: DbDep, _current_user: CurrentUser) -> list[AllergyOut]:
    _get_patient_or_404(db, patient_id)
    return [AllergyOut.model_validate(a) for a in clinical.list_allergies(db, patient_id)]


@router.post("/patients/{patient_id}/allergies", response_model=AllergyOut, status_code=status.HTTP_201_CREATED)
def create_patient_allergy(patient_id: str, payload: AllergyCreate, db: DbDep, _current_user: WriteUser) -> AllergyOut:
    _get_patient_or_404(db, patient_id)
    return AllergyOut.model_validate(clinical.create_allergy(db, patient_id, payload))


@router.patch("/allergies/{allergy_id}", response_model=AllergyOut)
def update_allergy(allergy_id: str, payload: AllergyUpdate, db: DbDep, _current_user: WriteUser) -> AllergyOut:
    allergy = _get_allergy_or_404(db, allergy_id)
    return AllergyOut.model_validate(clinical.update_allergy(db, allergy, payload))


# --- Medications ----------------------------------------------------------------------


@router.get("/patients/{patient_id}/medications", response_model=list[MedicationOut])
def list_patient_medications(patient_id: str, db: DbDep, _current_user: CurrentUser) -> list[MedicationOut]:
    _get_patient_or_404(db, patient_id)
    return [MedicationOut.model_validate(m) for m in clinical.list_medications(db, patient_id)]


@router.post("/patients/{patient_id}/medications", response_model=MedicationOut, status_code=status.HTTP_201_CREATED)
def create_patient_medication(
    patient_id: str, payload: MedicationCreate, db: DbDep, _current_user: WriteUser
) -> MedicationOut:
    _get_patient_or_404(db, patient_id)
    return MedicationOut.model_validate(clinical.create_medication(db, patient_id, payload))


@router.post("/medications/{medication_id}/stop", response_model=MedicationOut)
def stop_medication(medication_id: str, payload: MedicationStop, db: DbDep, _current_user: WriteUser) -> MedicationOut:
    medication = _get_medication_or_404(db, medication_id)
    return MedicationOut.model_validate(clinical.stop_medication(db, medication, payload))
