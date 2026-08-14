from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.encounter import EncounterStatus, EncounterType


class EncounterCreate(BaseModel):
    encounter_type: EncounterType
    start_datetime: datetime | None = None  # defaults to now in the service
    chief_complaint: str | None = Field(default=None, max_length=500)
    clinician_note: str | None = None


class EncounterUpdate(BaseModel):
    status: EncounterStatus | None = None
    end_datetime: datetime | None = None
    chief_complaint: str | None = Field(default=None, max_length=500)
    clinician_note: str | None = None


class EncounterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    encounter_number: str
    encounter_type: EncounterType
    start_datetime: datetime
    end_datetime: datetime | None
    status: EncounterStatus
    chief_complaint: str | None
    clinician_note: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime
