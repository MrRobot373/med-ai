"""Retrieval pipeline orchestration — spec §43 Stages 5-6, §44, §46, §47. Composes
`dense_retriever` + `sparse_retriever` + `fusion` + `reranker` + `deduplicator` into
one `retrieve()` call.

Chat orchestration (query classification/rewriting, context construction, citation
and grounding validation — spec §43 Stages 1-4 and §48-50) is Phase 08's job and calls
into this module; this module has no knowledge of the LLM or conversation state.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session as DbSession

from app.config.settings import Settings
from app.models.chunk import Chunk, ChunkCollection
from app.rag import dense_retriever, reranker, sparse_retriever
from app.rag.deduplicator import RetrievedPassage, deduplicate_and_expand
from app.rag.fusion import reciprocal_rank_fusion


@dataclass
class RetrievalStats:
    """Real, observed per-stage candidate counts — spec §80's "technical drawer"
    (Retrieval Provenance: "Dense candidates: 30 / BM25 candidates: 30 / Fused
    candidates: 19 / Reranked: 8"). Callers that don't need provenance simply don't
    pass an instance to `retrieve()`; passing one across several calls (e.g. one per
    collection queried in a single chat turn) and reading its fields afterward gives an
    honest turn-level rollup — never a fabricated number, always a real stage size."""

    dense_candidates: int = 0
    bm25_candidates: int = 0
    fused_candidates: int = 0
    reranked: int = 0
    deduplicated: int = 0


def retrieve(
    db: DbSession,
    query: str,
    settings: Settings,
    collection: ChunkCollection = ChunkCollection.PATIENT_DOCUMENTS,
    patient_id: str | None = None,
    max_per_source: int = 3,
    stats: RetrievalStats | None = None,
) -> list[RetrievedPassage]:
    """Patient isolation (spec §16) is enforced inside `dense_search`/`sparse_search`
    themselves (both raise if `patient_documents` is queried without a `patient_id`)
    — this function inherits that guarantee rather than re-checking it, so there's
    exactly one place patient filtering can be forgotten, not several."""
    dense_hits = dense_retriever.dense_search(query, collection, settings, patient_id=patient_id)
    sparse_hits = sparse_retriever.sparse_search(
        db, query, collection, patient_id=patient_id, top_k=settings.rag_sparse_top_k
    )

    fused = reciprocal_rank_fusion(dense_hits, sparse_hits, k=settings.rag_rrf_k, top_k=settings.rag_fusion_top_k)
    if stats is not None:
        stats.dense_candidates += len(dense_hits)
        stats.bm25_candidates += len(sparse_hits)
        stats.fused_candidates += len(fused)
    if not fused:
        return []

    texts_by_id = _fetch_chunk_texts(db, [hit.chunk_id for hit in fused])
    candidates = [(hit.chunk_id, texts_by_id[hit.chunk_id]) for hit in fused if hit.chunk_id in texts_by_id]
    reranked = reranker.rerank(query, candidates, settings, top_k=settings.rag_rerank_top_k)
    if stats is not None:
        stats.reranked += len(reranked)

    deduped = deduplicate_and_expand(db, reranked, max_per_source=max_per_source)
    if stats is not None:
        stats.deduplicated += len(deduped)
    return deduped


def _fetch_chunk_texts(db: DbSession, chunk_ids: list[str]) -> dict[str, str]:
    if not chunk_ids:
        return {}
    rows = db.query(Chunk.id, Chunk.text).filter(Chunk.id.in_(chunk_ids)).all()
    return {row.id: row.text for row in rows}
