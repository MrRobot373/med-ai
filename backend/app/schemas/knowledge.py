from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.report import IngestionStatus
from app.models.web_cache import AuthorityTier


class KnowledgeVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    version_number: int
    source_filename: str
    mime_type: str
    file_size_bytes: int
    effective_date: date | None
    review_date: date | None
    is_active: bool
    ingestion_status: IngestionStatus
    ingestion_error: str | None
    chunk_count: int
    created_at: datetime


class KnowledgeDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    source: str | None
    specialty: str | None
    authority_tier: AuthorityTier
    tags: str | None
    archived: bool
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentDetail(KnowledgeDocumentOut):
    versions: list[KnowledgeVersionOut]


class KnowledgeDocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    source: str | None = None
    specialty: str | None = None
    authority_tier: AuthorityTier = AuthorityTier.D
    tags: str | None = None


class KnowledgeDocumentUpdate(BaseModel):
    """PATCH — every field optional, only what's supplied is changed (spec's own
    `PATCH /api/knowledge/documents/{id}` endpoint)."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    source: str | None = None
    specialty: str | None = None
    authority_tier: AuthorityTier | None = None
    tags: str | None = None
