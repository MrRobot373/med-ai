"""Reciprocal Rank Fusion — spec §44. Pure unit tests, no DB/models needed."""

from __future__ import annotations

from dataclasses import dataclass

from app.rag.fusion import reciprocal_rank_fusion


@dataclass
class _Hit:
    chunk_id: str
    score: float


def test_chunk_ranked_first_by_both_retrievers_wins():
    dense = [_Hit("a", 0.9), _Hit("b", 0.8), _Hit("c", 0.7)]
    sparse = [_Hit("a", 5.0), _Hit("c", 3.0), _Hit("b", 1.0)]
    fused = reciprocal_rank_fusion(dense, sparse, k=60)
    assert fused[0].chunk_id == "a"


def test_chunk_missing_from_one_retriever_still_surfaces():
    # "b" only appears in sparse results (e.g. dense embedding missed a drug name a
    # lexical match caught) — RRF must not zero it out just because one list lacks it.
    dense = [_Hit("a", 0.9)]
    sparse = [_Hit("b", 5.0), _Hit("a", 1.0)]
    fused = reciprocal_rank_fusion(dense, sparse, k=60)
    chunk_ids = {hit.chunk_id for hit in fused}
    assert "b" in chunk_ids


def test_fused_score_combines_both_lists_ranks():
    dense = [_Hit("a", 0.9), _Hit("b", 0.5)]
    sparse = [_Hit("a", 5.0), _Hit("b", 1.0)]
    fused = {hit.chunk_id: hit for hit in reciprocal_rank_fusion(dense, sparse, k=60)}
    # a: rank 1 in both -> 1/61 + 1/61; b: rank 2 in both -> 1/62 + 1/62
    assert fused["a"].score > fused["b"].score
    assert fused["a"].dense_rank == 1
    assert fused["a"].sparse_rank == 1


def test_top_k_caps_the_result():
    dense = [_Hit(str(i), 1.0 / i) for i in range(1, 11)]
    fused = reciprocal_rank_fusion(dense, [], k=60, top_k=3)
    assert len(fused) == 3


def test_empty_inputs_produce_empty_output():
    assert reciprocal_rank_fusion([], [], k=60) == []
