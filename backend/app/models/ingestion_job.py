"""`ingestion_jobs` table — spec §29/§122.

A persistent log of the ingestion pipeline's progress, separate from `reports.
ingestion_status` (which reflects only the current/latest state). This is what
`start-demo.bat`/a restart-recovery pass would inspect to find jobs stuck mid-run (spec
§122: "on restart, detect incomplete jobs... never mark failed work as completed").
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.report import IngestionStatus

# Pipeline stage names, in order — used for the "stage" column so the UI can show
# progress ("Extracting text…", "Running OCR…") rather than a bare "processing" blob.
PIPELINE_STAGES = (
    "validating",
    "hashing",
    "classifying",
    "extracting_text",
    "running_ocr",
    "checking_identity",
    "extracting_labs",
    "finalizing",
)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[IngestionStatus] = mapped_column(
        SAEnum(IngestionStatus, native_enum=False), nullable=False, default=IngestionStatus.QUEUED
    )
    stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<IngestionJob report={self.report_id} status={self.status.value} stage={self.stage}>"
