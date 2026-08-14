from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.report import ExtractionStatus, IngestionStatus, PatientMatchStatus, ReportType


class ReportPage(BaseModel):
    page: int
    text: str
    method: str  # "text" | "ocr" | "metadata" | "none"


class ReportListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    encounter_id: str | None
    title: str
    report_type: ReportType
    report_date: date | None
    source_filename: str
    mime_type: str
    file_size_bytes: int
    ingestion_status: IngestionStatus
    extraction_status: ExtractionStatus
    patient_match_status: PatientMatchStatus
    source_patient_name: str | None
    source_mrn: str | None
    page_count: int | None
    ocr_used: bool
    archived: bool
    created_at: datetime


class ReportDetail(ReportListItem):
    extraction_error: str | None
    pages: list[ReportPage]


class ReportStatus(BaseModel):
    id: str
    ingestion_status: IngestionStatus
    extraction_status: ExtractionStatus
    stage: str | None
    error: str | None
