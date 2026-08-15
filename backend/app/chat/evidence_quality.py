"""Evidence quality — spec §54: a categorical label from transparent factors, never
`AI Confidence: 93%` "unless there is a scientifically calibrated model specifically
supporting that measure" (there isn't one here — a reranker relevance score is a
retrieval-ranking signal, not a calibrated probability of correctness, so it feeds a
category, never a displayed percentage).

Qwen3-Reranker's scores are raw logits (unbounded, positive = relevant, negative =
not — confirmed empirically: 0.06 for a genuinely relevant pair, -5.8 for an
irrelevant one during Phase 07 live testing), so "average score > 0 for the cited
evidence" is a principled threshold reflecting the reranker's own decision boundary,
not an arbitrary cutoff.
"""

from __future__ import annotations

from enum import Enum

from app.chat.context_builder import LabeledEvidence


class EvidenceQuality(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


def score_evidence_quality(labeled_evidence: list[LabeledEvidence], cited_labels: list[str]) -> EvidenceQuality:
    if not labeled_evidence or not cited_labels:
        return EvidenceQuality.INSUFFICIENT

    cited_set = set(cited_labels)
    cited_passages = [item.passage for item in labeled_evidence if item.label in cited_set]
    if not cited_passages:
        return EvidenceQuality.INSUFFICIENT

    distinct_sources = len({p.source_id for p in cited_passages})
    avg_score = sum(p.score for p in cited_passages) / len(cited_passages)
    coverage = len(cited_set) / len(labeled_evidence)

    if distinct_sources >= 2 and avg_score > 0 and coverage >= 0.5:
        return EvidenceQuality.STRONG
    if avg_score > 0:
        return EvidenceQuality.MODERATE
    return EvidenceQuality.LIMITED
