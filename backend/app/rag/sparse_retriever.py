"""Sparse/BM25 (lexical) retrieval — spec §43 Stage 6. Critical for drug names, ICD
codes, exact phrases, and numeric terminology that dense embedding similarity can
blur past (spec's own list). Computed in-process over the SQLite chunk corpus at
query time rather than stored as a Qdrant sparse vector — see the `rag` extra's
comment in pyproject.toml for why; at this deployment's scale that's simpler than the
IDF-fitting infrastructure a persistent sparse index needs, and it never goes stale.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.chunk import PATIENT_SCOPED_COLLECTIONS, Chunk, ChunkCollection

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


@dataclass
class SparseHit:
    chunk_id: str
    score: float


def sparse_search(
    db: DbSession,
    query: str,
    collection: ChunkCollection,
    patient_id: str | None = None,
    top_k: int = 30,
) -> list[SparseHit]:
    """Patient filtering is mandatory for patient-scoped collections, matching
    `dense_retriever.dense_search` — same rule, same reason (spec §16)."""
    if collection in PATIENT_SCOPED_COLLECTIONS and not patient_id:
        raise ValueError(f"patient_id is required when searching the {collection.value} collection")

    stmt = select(Chunk.id, Chunk.text).where(Chunk.collection == collection)
    if patient_id:
        stmt = stmt.where(Chunk.patient_id == patient_id)
    rows = db.execute(stmt).all()
    if not rows:
        return []

    chunk_ids = [row.id for row in rows]
    corpus = [_tokenize(row.text) for row in rows]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_tokenize(query))

    ranked = sorted(zip(chunk_ids, scores, strict=True), key=lambda pair: pair[1], reverse=True)
    # A zero BM25 score means no query term matched at all — excluded rather than
    # padding the candidate list with irrelevant filler just to hit top_k.
    return [SparseHit(chunk_id=cid, score=float(score)) for cid, score in ranked[:top_k] if score > 0]
