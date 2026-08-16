"""`vision_analyses` table — spec §58-60 Vision AI. One row per report that has (or
attempted) vision analysis; re-running analysis updates this row rather than
accumulating history, matching `index_document`'s "idempotent per source" pattern
used everywhere else in ingestion.

`payload` holds spec §60's exact structured schema (image_type/visible_text/
observations/measurements_visible/clinical_entities/quality_limitations/uncertainties)
as JSON text — the same "acceptable provenance, never chain-of-thought" shape as
`Message.structured_payload` in Phase 08. `analysis_error` is distinct from a
successful-but-limited analysis (which honestly lists its own `quality_limitations`),
matching `Report.extraction_error`'s precedent.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VisionAnalysisStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    # The report's mime type isn't analyzable (e.g. a DICOM file whose pixel data
    # couldn't be decoded into a preview) — distinct from FAILED, which means analysis
    # was attempted against real image bytes and the model/parse step itself failed.
    NOT_APPLICABLE = "not_applicable"


class VisionAnalysis(Base):
    __tablename__ = "vision_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    status: Mapped[VisionAnalysisStatus] = mapped_column(
        SAEnum(VisionAnalysisStatus, native_enum=False), nullable=False
    )
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON — spec §60 schema
    analysis_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<VisionAnalysis report_id={self.report_id} status={self.status.value}>"
