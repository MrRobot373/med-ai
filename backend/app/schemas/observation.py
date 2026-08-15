from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import VerificationStatus
from app.models.observation import ExtractionMethod


class ObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    encounter_id: str | None
    report_id: str | None
    observation_name: str
    normalized_name: str
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    reference_low: float | None
    reference_high: float | None
    abnormal_flag: bool | None
    measured_at: date | None
    source_page: int | None
    extraction_method: ExtractionMethod
    source_excerpt: str | None
    clinician_verified: bool
    verification_status: VerificationStatus
    created_at: datetime


class TrendPoint(BaseModel):
    observation_id: str
    measured_at: date | None
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    abnormal_flag: bool | None
    report_id: str | None
    source_page: int | None


class ObservationTrend(BaseModel):
    normalized_name: str
    display_name: str
    unit: str | None
    points: list[TrendPoint]
    # True when at least one reading for this test used a different, non-convertible
    # unit and was therefore excluded from `points` rather than compared unsafely —
    # spec §33 "otherwise do not compare numerically... flag the incompatible units."
    unit_conflict: bool
    excluded_units: list[str]
