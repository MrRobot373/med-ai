"""`chunks` table — the SQLite-side twin of every Qdrant point (spec §55 chunk
metadata). Qdrant stores the vector + a copy of the filterable metadata for retrieval;
this table is the canonical text store: it's what `sparse_retriever.py` builds its
BM25 index from, and what turns a Qdrant hit's point ID back into human-readable,
citable content. A chunk's `id` here IS its Qdrant point ID — one row, one point, no
separate mapping table to keep in sync.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChunkCollection(str, Enum):
    """Mirrors the Qdrant collection it's indexed into — spec §14. `web_cache`
    (Phase 11) joins once that phase populates it; the column is a plain string so
    adding values later needs no migration."""

    MEDICAL_KNOWLEDGE = "medical_knowledge"
    PATIENT_DOCUMENTS = "patient_documents"
    # Normalized text/observations produced from images (spec §14): report images,
    # scanned documents, vision analysis output, OCR output — see app/vision/.
    PATIENT_VISION = "patient_vision"


# Collections that carry per-patient content and therefore require a mandatory
# patient_id filter on every query (spec §16) — everything except the shared,
# unscoped medical_knowledge base.
PATIENT_SCOPED_COLLECTIONS = frozenset({ChunkCollection.PATIENT_DOCUMENTS, ChunkCollection.PATIENT_VISION})


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    collection: Mapped[ChunkCollection] = mapped_column(SAEnum(ChunkCollection, native_enum=False), nullable=False)

    # Patient isolation (spec §14/§16): every patient_documents chunk carries a
    # patient_id, enforced as a mandatory retrieval filter — never optional, never
    # inferred. NULL here means "not patient-scoped" (medical_knowledge only).
    patient_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=True, index=True
    )
    report_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("reports.id", ondelete="CASCADE"), nullable=True, index=True
    )

    source_title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<Chunk {self.source_title} #{self.chunk_index} collection={self.collection.value}>"
