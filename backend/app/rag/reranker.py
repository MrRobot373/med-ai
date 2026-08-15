"""Reranker abstraction — spec §6. Wraps `Qwen3-Reranker-0.6B` via
`sentence-transformers`' `CrossEncoder`. Lazy-loaded singleton, same double-checked-
locking pattern as `embeddings.py`.

A generic interface (spec §6 "create a generic reranker interface"): callers pass a
query and a list of `(chunk_id, text)` candidates and get back re-scored, re-ordered
results — nothing outside this module knows the reranker is specifically a Qwen
model, so swapping it later doesn't touch `pipeline.py`.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from app.config.settings import Settings
from app.logging import get_logger

logger = get_logger(__name__)

_model = None
_loaded_model_name: str | None = None
_model_lock = threading.Lock()


@dataclass
class RerankedHit:
    chunk_id: str
    score: float


def is_loaded() -> bool:
    return _model is not None


def _get_model(settings: Settings):
    global _model, _loaded_model_name
    if _model is None or _loaded_model_name != settings.reranker_model:
        with _model_lock:
            if _model is None or _loaded_model_name != settings.reranker_model:
                from sentence_transformers import CrossEncoder

                logger.info("Loading reranker model %s on %s", settings.reranker_model, settings.reranker_device)
                # Same "sdpa over eager" CPU throughput fix as embeddings.py — see
                # that module's comment; Qwen3-Reranker is the same decoder-based
                # architecture family. `max_length` caps runaway attention cost the
                # same way `embedding_max_seq_length` does for the embedding model.
                try:
                    _model = CrossEncoder(
                        settings.reranker_model,
                        device=settings.reranker_device,
                        trust_remote_code=True,
                        max_length=settings.embedding_max_seq_length,
                        automodel_args={"attn_implementation": "sdpa"},
                    )
                except Exception:
                    logger.warning("sdpa attention unavailable for reranker model; falling back to default", exc_info=True)
                    _model = CrossEncoder(
                        settings.reranker_model, device=settings.reranker_device, trust_remote_code=True
                    )
                _loaded_model_name = settings.reranker_model
    return _model


def rerank(
    query: str, candidates: list[tuple[str, str]], settings: Settings, top_k: int | None = None
) -> list[RerankedHit]:
    """`candidates` is `[(chunk_id, text), ...]` — expected to already be the
    fused, capped candidate set (spec §46 "retain approximately 15-20 candidates"
    before reranking), not hundreds of chunks (spec §6 "do not rerank hundreds of
    chunks unnecessarily"). This function doesn't enforce that cap itself — capping is
    `pipeline.py`'s job, via `settings.rag_fusion_top_k` — but never silently reranks
    an unbounded list either; an empty candidate list is a no-op, not an error."""
    if not candidates:
        return []
    model = _get_model(settings)
    pairs = [(query, text) for _chunk_id, text in candidates]
    scores = model.predict(pairs)
    hits = [
        RerankedHit(chunk_id=chunk_id, score=float(score))
        for (chunk_id, _text), score in zip(candidates, scores, strict=True)
    ]
    hits.sort(key=lambda hit: hit.score, reverse=True)
    return hits[:top_k] if top_k else hits
