from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import VerificationStatus


class MedicationCreate(BaseModel):
    encounter_id: str | None = None
    medication_name: str = Field(min_length=1, max_length=255)
    dose: str | None = Field(default=None, max_length=50)
    dose_unit: str | None = Field(default=None, max_length=20)
    route: str | None = Field(default=None, max_length=50)
    frequency: str | None = Field(default=None, max_length=100)
    start_date: date | None = None
    source: str | None = Field(default=None, max_length=255)
    verification_status: VerificationStatus = VerificationStatus.CONFIRMED


class MedicationStop(BaseModel):
    stop_date: date | None = None  # defaults to today in the service


class MedicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    encounter_id: str | None
    medication_name: str
    normalized_name: str | None
    dose: str | None
    dose_unit: str | None
    route: str | None
    frequency: str | None
    start_date: date | None
    stop_date: date | None
    active: bool
    source: str | None
    verification_status: VerificationStatus
    created_at: datetime
    updated_at: datetime
