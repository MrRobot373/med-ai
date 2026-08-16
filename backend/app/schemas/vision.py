from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.vision_analysis import VisionAnalysisStatus


class VisionAnalysisOut(BaseModel):
    report_id: str
    status: VisionAnalysisStatus
    model: str | None
    analysis_error: str | None
    created_at: datetime
    updated_at: datetime
    # Spec §60's schema, flattened onto the response rather than nested under
    # `payload` — None for every field when status isn't SUCCESS.
    image_type: str | None = None
    visible_text: list[str] = []
    observations: list[str] = []
    measurements_visible: list[str] = []
    clinical_entities: list[str] = []
    quality_limitations: list[str] = []
    uncertainties: list[str] = []


class VisionCompareRequest(BaseModel):
    previous_report_id: str
    current_report_id: str


class ComparisonEvidenceOut(BaseModel):
    source_title: str
    page: int | None
    section: str | None
    excerpt: str


class VisionCompareResponse(BaseModel):
    previous_report_id: str
    current_report_id: str
    previous_findings: list[str]
    current_findings: list[str]
    observable_changes: list[str]
    differences: list[str]
    limitations: list[str]
    clinical_evidence: list[ComparisonEvidenceOut]
