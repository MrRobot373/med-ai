from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.allergy import AllergySeverity, AllergyStatus
from app.models.enums import VerificationStatus


class AllergyCreate(BaseModel):
    substance: str = Field(min_length=1, max_length=255)
    reaction: str | None = Field(default=None, max_length=500)
    severity: AllergySeverity = AllergySeverity.UNKNOWN
    status: AllergyStatus = AllergyStatus.ACTIVE
    source: str | None = Field(default=None, max_length=255)
    verification_status: VerificationStatus = VerificationStatus.CONFIRMED


class AllergyUpdate(BaseModel):
    status: AllergyStatus | None = None
    severity: AllergySeverity | None = None
    verification_status: VerificationStatus | None = None


class AllergyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    substance: str
    reaction: str | None
    severity: AllergySeverity
    status: AllergyStatus
    source: str | None
    verification_status: VerificationStatus
    created_at: datetime
    updated_at: datetime
