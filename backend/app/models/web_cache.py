"""`web_cache` table — spec §72 Web Cache. External evidence fetched through Research
Mode is cached locally: "improves reproducibility, speed, demo reliability,
auditability." A repeated (de-identified query, source) pair reuses a fresh cache
entry instead of re-hitting the network (see `services/research.py`).

Deliberately NOT also indexed into a Qdrant `web_cache` vector collection in this
phase — see docs/architecture.md's Phase 11 section for why (the CPU cross-encoder
reranker's already-documented ~6-7 minute latency on `medical_knowledge` makes a
second full embed+rerank pass over live web results impractical; ranking here uses a
fast deterministic lexical+authority-tier score instead, computed at query time, not
stored). The SQLite cache alone already satisfies spec §72's stated goals.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum

from sqlalchemy import Date, DateTime, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WebSource(str, Enum):
    PUBMED = "pubmed"
    FDA = "fda"
    CLINICALTRIALS = "clinicaltrials"
    SEARXNG = "searxng"


class AuthorityTier(str, Enum):
    """Spec §67's example hierarchy. A modest, configurable ranking boost — never a
    hard override of relevance (see `research/ranking.py`)."""

    A = "a"  # official guidelines, regulatory information (FDA labels)
    B = "b"  # systematic reviews, meta-analyses
    C = "c"  # peer-reviewed clinical studies (RCTs, registered trials)
    D = "d"  # authoritative medical references
    E = "e"  # general medical webpages
    F = "f"  # general internet


class WebCacheEntry(Base):
    __tablename__ = "web_cache"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[WebSource] = mapped_column(SAEnum(WebSource, native_enum=False), nullable=False)
    authority_tier: Mapped[AuthorityTier] = mapped_column(SAEnum(AuthorityTier, native_enum=False), nullable=False)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    # sha256 of `text` — content-based dedup, same convention as Report.file_hash.
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # The de-identified query that produced this hit — never the raw clinician
    # question, which may still carry patient context (spec §66).
    query: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    study_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # pubmed/trials: rct/systematic_review/...

    published_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<WebCacheEntry {self.source.value} {self.title[:40]!r}>"
