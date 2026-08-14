"""`reports` table — spec §15 Reports / §29 Report Upload Pipeline.

Files are stored under `data/uploads/reports/<patient_id>/<stored_filename>` — outside
any directly-served web root (spec §92) — and are only ever reachable through the
auth-gated `GET /api/reports/{id}/file` endpoint, never a static mount. `stored_filename`
is a random, non-guessable name; `source_filename` (the original, clinician-facing name)
is kept separate so a hostile filename never touches the filesystem path.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReportType(str, Enum):
    LAB_REPORT = "lab_report"
    IMAGING_REPORT = "imaging_report"
    CONSULTATION_NOTE = "consultation_note"
    DISCHARGE_SUMMARY = "discharge_summary"
    REFERRAL_LETTER = "referral_letter"
    OTHER = "other"


class IngestionStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


class PatientMatchStatus(str, Enum):
    MATCHED = "matched"
    MISMATCH = "mismatch"
    UNCONFIRMED = "unconfirmed"
    NOT_CHECKED = "not_checked"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    encounter_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("encounters.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    report_type: Mapped[ReportType] = mapped_column(
        SAEnum(ReportType, native_enum=False), nullable=False, default=ReportType.OTHER
    )
    report_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # sha256 hex
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    ingestion_status: Mapped[IngestionStatus] = mapped_column(
        SAEnum(IngestionStatus, native_enum=False), nullable=False, default=IngestionStatus.QUEUED
    )
    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        SAEnum(ExtractionStatus, native_enum=False), nullable=False, default=ExtractionStatus.PENDING
    )
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Detected from document content — never assumed. NULL means "not detected", which
    # is distinct from patient_match_status=UNCONFIRMED (detected but not confident).
    source_patient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_mrn: Mapped[str | None] = mapped_column(String(64), nullable=True)
    patient_match_status: Mapped[PatientMatchStatus] = mapped_column(
        SAEnum(PatientMatchStatus, native_enum=False), nullable=False, default=PatientMatchStatus.NOT_CHECKED
    )
    identity_reviewed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    identity_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # JSON-encoded list of {"page": int, "text": str, "method": "text"|"ocr"} — kept
    # page-tagged from day one so Phase 06/07 citations can point at an exact page
    # instead of an undifferentiated text blob.
    extracted_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ocr_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    uploaded_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<Report {self.title} status={self.ingestion_status.value}>"
