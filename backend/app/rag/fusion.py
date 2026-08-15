"""Reciprocal Rank Fusion — spec §44. The initial default fusion strategy the spec
names explicitly; kept as a standalone, swappable module (not inlined into
`pipeline.py`) since spec §44 also says to "keep fusion strategy configurable."
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class _RankedHit(Protocol):
    chunk_id: str
    score: float


@dataclass
class FusedHit:
    chunk_id: str
    score: float
    dense_rank: int | None
    sparse_rank: int | None


def reciprocal_rank_fusion(
    dense_hits: list[_RankedHit],
    sparse_hits: list[_RankedHit],
    k: int = 60,
    top_k: int | None = None,
) -> list[FusedHit]:
    """Standard RRF: score(chunk) = sum(1 / (k + rank)) across every ranked list the
    chunk appears in. `k` (default 60, the constant from the original RRF paper) damps
    the influence of any single list's exact rank — a chunk ranked #1 by one retriever
    and completely absent from the other still surfaces if the other retriever simply
    didn't have lexical/semantic signal for it, rather than being penalized to zero."""
    scores: dict[str, float] = {}
    dense_ranks: dict[str, int] = {}
    sparse_ranks: dict[str, int] = {}

    for rank, hit in enumerate(dense_hits, start=1):
        scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
        dense_ranks[hit.chunk_id] = rank
    for rank, hit in enumerate(sparse_hits, start=1):
        scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
        sparse_ranks[hit.chunk_id] = rank

    fused = [
        FusedHit(chunk_id=cid, score=score, dense_rank=dense_ranks.get(cid), sparse_rank=sparse_ranks.get(cid))
        for cid, score in scores.items()
    ]
    fused.sort(key=lambda hit: hit.score, reverse=True)
    return fused[:top_k] if top_k else fused
