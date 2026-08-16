"""`knowledge_documents` / `knowledge_document_versions` tables — spec's Knowledge
Administration data model (Phase 12): upload, metadata, versions, active documents,
reindex, archive, ingestion monitoring.

Every point in the `medical_knowledge` Qdrant collection traces back to exactly one
*version* of exactly one admin-managed document. "Active" is a per-version flag
(`is_active`), not a document-level FK to its active version — that keeps
activating/rolling-back a version a single-row flip instead of two tables that must be
kept in lockstep, and sidesteps a circular FK between the two tables entirely.
Indexing itself is keyed off `file_hash` (a version's file content), reusing exactly
`app.rag.indexing.index_document`/`delete_indexed_source`'s existing file_hash-based
identity — the same mechanism `scripts/ingest_knowledge.py` already relies on — so no
change to `Chunk` or the indexing pipeline was needed for versioning to work.

Reuses `app.models.report.IngestionStatus` (QUEUED/PROCESSING/COMPLETED/FAILED) instead
of a near-duplicate enum, and `app.models.web_cache.AuthorityTier` (spec §67's A-F
scale) instead of a second authority-tier concept for admin-curated documents.

No hard delete — mirrors `Report.archived`'s soft-delete-only convention (spec's own
data model lists "archive," not "delete," as the terminal admin action).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.report import IngestionStatus
from app.models.web_cache import AuthorityTier


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # Publisher/issuing body, admin-entered free text (e.g. "ICO", "AAO PPP") — not a
    # controlled vocabulary; spec's own bullet list just says "source."
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    specialty: Mapped[str | None] = mapped_column(String(120), nullable=True)
    authority_tier: Mapped[AuthorityTier] = mapped_column(
        SAEnum(AuthorityTier, native_enum=False), nullable=False, default=AuthorityTier.D
    )
    # Comma-separated, admin-entered — same lightweight convention as free-text
    # metadata elsewhere in this codebase rather than a separate tags table for a
    # single-operator admin screen (spec §135 "avoid unnecessary infrastructure").
    tags: Mapped[str | None] = mapped_column(String(500), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<KnowledgeDocument {self.title!r} tier={self.authority_tier.value}>"


class KnowledgeDocumentVersion(Base):
    __tablename__ = "knowledge_document_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # sha256 hex
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    review_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Exactly one version per document should be True at a time — enforced at the
    # service layer (activate_version deactivates siblings in the same transaction),
    # not a DB constraint, since SQLite has no native partial-unique-index support
    # this project already relies on elsewhere.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ingestion_status: Mapped[IngestionStatus] = mapped_column(
        SAEnum(IngestionStatus, native_enum=False), nullable=False, default=IngestionStatus.QUEUED
    )
    ingestion_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<KnowledgeDocumentVersion doc={self.document_id} v{self.version_number} status={self.ingestion_status.value}>"
