"""`citations` table — spec §15 Citations, §51 Citation System.

Maps an assistant message's inline `[P1]`/`[L1]`/`[V1]`/`[W1]`-style labels back to the
exact retrieved passage that supports them — never fabricated (spec §2 "never
fabricate citations... never fabricate page numbers"). `source_excerpt` is copied at
generation time rather than only referencing `chunk_id`, so a citation stays fully
readable even if the underlying chunk is later deleted/reindexed.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CitationSourceType(str, Enum):
    PATIENT_REPORT = "patient_report"
    KNOWLEDGE_DOCUMENT = "knowledge_document"
    PATIENT_VISION = "patient_vision"  # image-derived evidence (Phase 09), label "V#"
    EXTERNAL = "external"  # Phase 11 (web research) — unused until then


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )

    label: Mapped[str] = mapped_column(String(10), nullable=False)  # "P1", "L1", "W1", ...
    source_type: Mapped[CitationSourceType] = mapped_column(
        SAEnum(CitationSourceType, native_enum=False), nullable=False
    )
    chunk_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True
    )
    report_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True
    )

    source_title: Mapped[str] = mapped_column(String(255), nullable=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    # The fused/reranked relevance score at generation time — "relevance/reranking
    # information" per spec's field list. Not a clinical confidence measure (spec §54
    # explicitly prohibits displaying model probability as clinical confidence); this
    # is retrieval-quality metadata only, shown in the evidence panel as such.
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<Citation {self.label} {self.source_title}>"
