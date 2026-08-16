"""Deterministic web-result ranking — spec §67: "Do not allow a random webpage to
outrank a directly relevant guideline solely because lexical similarity is slightly
higher. Any authority boost must remain modest/configurable and must not override
obvious relevance." No LLM and no cross-encoder reranker involved (see
docs/architecture.md's Phase 11 section for why — the same CPU reranker latency
already documented for local RAG would make Research Mode impractically slow):
relevance is a plain deterministic word-overlap score (0-1), authority tier adds a
modest, explicitly bounded bonus on top — a big relevance gap always wins; only close
ties are broken in the more authoritative source's favor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.web_cache import AuthorityTier
from app.research.providers.base import WebResult

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

# Deliberately small relative to the 0-1 relevance range — "modest," per spec §67 —
# and a plain module-level constant rather than a settings field: tuning source
# authority ordering is a code change (it defines what "authoritative" means for this
# deployment), not an operational knob a demo would flip at runtime.
_TIER_BOOST: dict[AuthorityTier, float] = {
    AuthorityTier.A: 0.15,
    AuthorityTier.B: 0.12,
    AuthorityTier.C: 0.09,
    AuthorityTier.D: 0.06,
    AuthorityTier.E: 0.03,
    AuthorityTier.F: 0.0,
}
# Applied on top of the tier boost when the caller prefers reviews/guidelines (spec
# §69's "Guidelines & Reviews First" evidence-preference control).
_REVIEW_BOOST = 0.08


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_PATTERN.findall(text.lower()))


def relevance_score(query: str, result: WebResult) -> float:
    query_terms = _tokenize(query)
    if not query_terms:
        return 0.0
    document_terms = _tokenize(f"{result.title} {result.text}")
    overlap = len(query_terms & document_terms)
    return overlap / len(query_terms)


@dataclass
class RankedResult:
    result: WebResult
    relevance: float
    rank_score: float


def rank_results(query: str, results: list[WebResult], prefer_reviews: bool = True) -> list[RankedResult]:
    ranked = []
    for result in results:
        relevance = relevance_score(query, result)
        score = relevance + _TIER_BOOST[result.authority_tier]
        if prefer_reviews and result.study_type == "systematic_review":
            score += _REVIEW_BOOST
        ranked.append(RankedResult(result=result, relevance=relevance, rank_score=score))
    ranked.sort(key=lambda r: r.rank_score, reverse=True)
    return ranked
