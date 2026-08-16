"""Deterministic web-result ranking — spec §67: relevance-first, authority tier a
modest boost that breaks ties without overriding an obvious relevance gap."""

from __future__ import annotations

from app.models.web_cache import AuthorityTier, WebSource
from app.research.providers.base import WebResult
from app.research.ranking import rank_results, relevance_score


def _result(title: str, text: str, tier: AuthorityTier, study_type: str | None = None) -> WebResult:
    return WebResult(title=title, url="https://example.test", text=text, source=WebSource.PUBMED, authority_tier=tier, study_type=study_type)


def test_relevance_score_counts_query_term_overlap():
    result = _result("Glaucoma treatment guideline", "Discusses IOP-lowering therapy options.", AuthorityTier.D)
    score = relevance_score("glaucoma treatment options", result)
    assert 0 < score <= 1.0


def test_relevance_score_is_zero_for_no_overlap():
    result = _result("Diabetic retinopathy screening", "Unrelated content about a different condition.", AuthorityTier.D)
    score = relevance_score("cardiac arrhythmia management", result)
    assert score == 0.0


def test_a_clearly_more_relevant_general_webpage_still_outranks_a_barely_relevant_guideline():
    """Spec §67: authority boost must NOT override obvious relevance."""
    barely_relevant_guideline = _result("General eye care guideline", "Brief mention of glaucoma among many topics.", AuthorityTier.A)
    highly_relevant_general = _result("Glaucoma treatment glaucoma therapy glaucoma IOP", "glaucoma glaucoma glaucoma treatment IOP therapy", AuthorityTier.F)

    ranked = rank_results("glaucoma treatment IOP therapy", [barely_relevant_guideline, highly_relevant_general])
    assert ranked[0].result.title == "Glaucoma treatment glaucoma therapy glaucoma IOP"


def test_close_relevance_ties_favor_the_more_authoritative_source():
    guideline = _result("Glaucoma IOP treatment", "glaucoma IOP treatment guidance", AuthorityTier.A)
    general_web = _result("Glaucoma IOP treatment", "glaucoma IOP treatment guidance", AuthorityTier.F)

    ranked = rank_results("glaucoma IOP treatment", [general_web, guideline])
    assert ranked[0].result.authority_tier == AuthorityTier.A


def test_prefer_reviews_boosts_systematic_reviews_when_enabled():
    review = _result("Glaucoma management review", "glaucoma management systematic review", AuthorityTier.B, study_type="systematic_review")
    rct = _result("Glaucoma management trial", "glaucoma management systematic review", AuthorityTier.B, study_type="rct")

    ranked_preferring = rank_results("glaucoma management systematic review", [rct, review], prefer_reviews=True)
    assert ranked_preferring[0].result.study_type == "systematic_review"


def test_prefer_reviews_off_does_not_apply_the_extra_boost():
    review = _result("A", "glaucoma treatment", AuthorityTier.B, study_type="systematic_review")
    rct = _result("A", "glaucoma treatment", AuthorityTier.B, study_type="rct")

    ranked = rank_results("glaucoma treatment", [review, rct], prefer_reviews=False)
    # Identical text/tier and no review boost applied — scores tie, order preserved.
    assert ranked[0].rank_score == ranked[1].rank_score


def test_rank_results_sorts_descending_by_score():
    low = _result("Barely relevant", "unrelated", AuthorityTier.F)
    high = _result("glaucoma glaucoma glaucoma", "glaucoma", AuthorityTier.A)
    ranked = rank_results("glaucoma", [low, high])
    assert [r.result.title for r in ranked] == ["glaucoma glaucoma glaucoma", "Barely relevant"]
