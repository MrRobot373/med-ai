from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.condition import ConditionStatus
from app.models.enums import VerificationStatus


class ConditionCreate(BaseModel):
    encounter_id: str | None = None
    code: str | None = Field(default=None, max_length=20)
    display: str = Field(min_length=1, max_length=255)
    status: ConditionStatus = ConditionStatus.ACTIVE
    onset_date: date | None = None
    verification_status: VerificationStatus = VerificationStatus.CONFIRMED
    notes: str | None = None


class ConditionUpdate(BaseModel):
    status: ConditionStatus | None = None
    resolved_date: date | None = None
    verification_status: VerificationStatus | None = None
    notes: str | None = None


class ConditionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    encounter_id: str | None
    code: str | None
    display: str
    status: ConditionStatus
    onset_date: date | None
    resolved_date: date | None
    verification_status: VerificationStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime
