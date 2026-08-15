from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class ConditionChange(BaseModel):
    id: str
    display: str
    onset_date: date | None = None
    resolved_date: date | None = None


class MedicationStartStop(BaseModel):
    id: str
    medication_name: str
    dose: str | None = None
    start_date: date | None = None
    stop_date: date | None = None


class MedicationDoseChange(BaseModel):
    # Named separately, not one shared `medication_name` — the drug's strength is
    # sometimes folded into its name rather than the `dose` field ("Timolol 0.25%" ->
    # "Timolol 0.5%"), so the name itself can be exactly where a change is visible.
    previous_medication_name: str
    current_medication_name: str
    previous_dose: str | None
    current_dose: str | None
    stopped_id: str
    started_id: str


class AllergyChange(BaseModel):
    id: str
    substance: str
    recorded_at: datetime


class ObservationChange(BaseModel):
    normalized_name: str
    display_name: str
    previous_value: float | None
    previous_unit: str | None
    previous_date: date | None
    current_value: float | None
    current_unit: str | None
    current_date: date | None
    # "increased" | "decreased" | "unchanged" — deliberately NOT "worsened"/"improved":
    # whether a rising value is good or bad is test-specific clinical judgment this
    # deterministic engine has no basis to assert. See services/change_engine.py.
    direction: str


class ChangesSummary(BaseModel):
    patient_id: str
    since: date
    conditions_new: list[ConditionChange]
    conditions_resolved: list[ConditionChange]
    medications_started: list[MedicationStartStop]
    medications_stopped: list[MedicationStartStop]
    medications_dose_changed: list[MedicationDoseChange]
    allergies_new: list[AllergyChange]
    observations_changed: list[ObservationChange]
    observations_new_tests: list[str]
