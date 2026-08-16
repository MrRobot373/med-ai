from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator

from app.models.clinical_module_run import ClinicalModuleType
from app.modules.summarizer import SummaryType


class ClinicalModuleRunOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    module_type: ClinicalModuleType
    patient_id: str | None
    encounter_id: str | None
    input_params: dict[str, Any]
    payload: dict[str, Any] | None
    model: str | None
    generation_error: str | None
    created_at: datetime

    @field_validator("input_params", "payload", mode="before")
    @classmethod
    def _parse_json(cls, value: Any) -> Any:
        if isinstance(value, str):
            return json.loads(value)
        return value


class SummaryRequest(BaseModel):
    summary_type: SummaryType
    encounter_id: str | None = None


class SOAPRequest(BaseModel):
    encounter_id: str


class EntityExtractionRequest(BaseModel):
    report_id: str | None = None
    encounter_id: str | None = None


class DifferentialRequest(BaseModel):
    encounter_id: str | None = None


class GuidelineQARequest(BaseModel):
    question: str


class ReportComparisonRequest(BaseModel):
    previous_report_id: str
    current_report_id: str
