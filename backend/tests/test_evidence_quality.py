from __future__ import annotations

from app.chat.context_builder import LabeledEvidence
from app.chat.evidence_quality import EvidenceQuality, score_evidence_quality
from app.rag.deduplicator import RetrievedPassage


def _passage(**overrides) -> RetrievedPassage:
    defaults = {
        "text": "some evidence text",
        "score": 1.0,
        "source_title": "Report",
        "source_id": "report-1",
        "collection": "patient_documents",
        "page": 1,
        "section": None,
        "chunk_ids": ["c1"],
    }
    defaults.update(overrides)
    return RetrievedPassage(**defaults)


def test_no_evidence_at_all_is_insufficient():
    assert score_evidence_quality([], []) == EvidenceQuality.INSUFFICIENT


def test_evidence_offered_but_none_cited_is_insufficient():
    # The model was given evidence but didn't actually use it in its answer — an
    # uncited passage doesn't count as support for anything.
    labeled = [LabeledEvidence(label="P1", passage=_passage())]
    assert score_evidence_quality(labeled, []) == EvidenceQuality.INSUFFICIENT


def test_two_independent_positive_sources_with_good_coverage_is_strong():
    labeled = [
        LabeledEvidence(label="P1", passage=_passage(source_id="report-1", score=2.0)),
        LabeledEvidence(label="L1", passage=_passage(source_id="knowledge-1", score=1.5)),
    ]
    assert score_evidence_quality(labeled, ["P1", "L1"]) == EvidenceQuality.STRONG


def test_single_positive_source_is_moderate():
    labeled = [LabeledEvidence(label="P1", passage=_passage(score=1.0))]
    assert score_evidence_quality(labeled, ["P1"]) == EvidenceQuality.MODERATE


def test_negative_reranker_score_is_limited_not_moderate():
    # Qwen3-Reranker logits: negative means the reranker itself judged this passage
    # not actually relevant (spec §54 — a transparent factor, not a fabricated number).
    labeled = [LabeledEvidence(label="P1", passage=_passage(score=-3.0))]
    assert score_evidence_quality(labeled, ["P1"]) == EvidenceQuality.LIMITED


def test_two_sources_but_low_coverage_is_not_strong():
    labeled = [
        LabeledEvidence(label="P1", passage=_passage(source_id="report-1", score=1.0)),
        LabeledEvidence(label="L1", passage=_passage(source_id="knowledge-1", score=1.0)),
        LabeledEvidence(label="L2", passage=_passage(source_id="knowledge-2", score=1.0)),
        LabeledEvidence(label="L3", passage=_passage(source_id="knowledge-3", score=1.0)),
    ]
    # Only 1 of 4 offered passages actually cited — below the 0.5 coverage bar for STRONG.
    assert score_evidence_quality(labeled, ["P1"]) == EvidenceQuality.MODERATE
