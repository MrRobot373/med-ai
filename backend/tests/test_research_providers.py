"""Trusted-source providers (spec §65) — httpx mocked so these run fast and
deterministically; real reachability is verified live (see docs/architecture.md's
Phase 11 section), matching every other external-service test in this codebase.
"""

from __future__ import annotations

import httpx
import pytest

from app.config.settings import get_settings
from app.models.web_cache import AuthorityTier, WebSource
from app.research.providers import clinicaltrials, fda, pubmed, searxng
from app.research.providers.base import clean_search_terms


def _json_response(payload: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=payload, request=httpx.Request("GET", "https://example.test"))


def _text_response(text: str, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, text=text, request=httpx.Request("GET", "https://example.test"))


# --- clean_search_terms --------------------------------------------------------------------
# Found live (Phase 11): PubMed/openFDA both choked on a raw natural-language question.


def test_clean_search_terms_strips_punctuation_and_stopwords():
    result = clean_search_terms(
        "What is the recent evidence for selective laser trabeculoplasty (SLT) as first-line treatment for open-angle glaucoma?"
    )
    assert result == "recent evidence selective laser trabeculoplasty SLT first-line treatment open-angle glaucoma"


def test_clean_search_terms_falls_back_to_stripped_original_when_every_word_is_a_stopword():
    assert clean_search_terms("What is it?") == "What is it"


def test_clean_search_terms_keeps_hyphenated_clinical_terms_intact():
    assert "open-angle" in clean_search_terms("evidence for open-angle glaucoma treatment").split()


# --- PubMed ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pubmed_search_parses_title_pubtype_and_abstract(monkeypatch: pytest.MonkeyPatch):
    call_log = []

    async def fake_get(self, url, params=None, **kwargs):
        call_log.append(url)
        if "esearch" in url:
            return _json_response({"esearchresult": {"idlist": ["111"]}})
        if "esummary" in url:
            return _json_response({"result": {"111": {"title": "A Systematic Review of Glaucoma Therapy", "pubtype": ["Systematic Review"], "pubdate": "2026 Jul 14"}}})
        if "efetch" in url:
            xml = (
                '<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>111</PMID>'
                '<Article><Abstract><AbstractText>Real abstract text.</AbstractText></Abstract></Article>'
                "</MedlineCitation></PubmedArticle></PubmedArticleSet>"
            )
            return _text_response(xml)
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    results = await pubmed.search("glaucoma therapy", get_settings(), 5)

    assert len(results) == 1
    assert results[0].title == "A Systematic Review of Glaucoma Therapy"
    assert results[0].text == "Real abstract text."
    assert results[0].study_type == "systematic_review"
    assert results[0].authority_tier == AuthorityTier.B
    assert results[0].published_at.isoformat() == "2026-07-14"
    assert results[0].url == "https://pubmed.ncbi.nlm.nih.gov/111/"


@pytest.mark.asyncio
async def test_pubmed_search_returns_empty_list_on_network_failure(monkeypatch: pytest.MonkeyPatch):
    async def fake_get(self, url, params=None, **kwargs):
        raise httpx.ConnectTimeout("simulated timeout")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    results = await pubmed.search("anything", get_settings(), 5)
    assert results == []


@pytest.mark.asyncio
async def test_pubmed_search_returns_empty_list_when_no_ids_found(monkeypatch: pytest.MonkeyPatch):
    async def fake_get(self, url, params=None, **kwargs):
        return _json_response({"esearchresult": {"idlist": []}})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    results = await pubmed.search("a query with no hits", get_settings(), 5)
    assert results == []


# --- FDA ---------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fda_search_parses_label_and_builds_dailymed_url(monkeypatch: pytest.MonkeyPatch):
    async def fake_get(self, url, params=None, **kwargs):
        return _json_response(
            {
                "results": [
                    {
                        "openfda": {"brand_name": ["Xalatan"], "generic_name": ["LATANOPROST"]},
                        "set_id": "abc-123",
                        "effective_time": "20260115",
                        "indications_and_usage": ["Indicated for reduction of elevated IOP."],
                    }
                ]
            }
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    results = await fda.search("latanoprost", get_settings(), 5)

    assert len(results) == 1
    assert results[0].title == "Xalatan"
    assert results[0].url == "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=abc-123"
    assert results[0].authority_tier == AuthorityTier.A
    assert results[0].published_at.isoformat() == "2026-01-15"
    assert "reduction of elevated IOP" in results[0].text


@pytest.mark.asyncio
async def test_fda_search_returns_empty_list_on_http_error(monkeypatch: pytest.MonkeyPatch):
    async def fake_get(self, url, params=None, **kwargs):
        return httpx.Response(500, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    results = await fda.search("anything", get_settings(), 5)
    assert results == []


# --- ClinicalTrials.gov --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clinicaltrials_search_parses_studies(monkeypatch: pytest.MonkeyPatch):
    async def fake_get(self, url, params=None, **kwargs):
        return _json_response(
            {
                "studies": [
                    {
                        "protocolSection": {
                            "identificationModule": {"nctId": "NCT01234567", "briefTitle": "A Trial of Drug X for Glaucoma"},
                            "statusModule": {"overallStatus": "RECRUITING", "startDateStruct": {"date": "2024-03-01"}},
                            "descriptionModule": {"briefSummary": "Studying Drug X."},
                            "designModule": {"studyType": "INTERVENTIONAL"},
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    results = await clinicaltrials.search("glaucoma", get_settings(), 5)

    assert len(results) == 1
    assert results[0].url == "https://clinicaltrials.gov/study/NCT01234567"
    assert results[0].study_type == "rct"
    assert results[0].authority_tier == AuthorityTier.C
    assert results[0].published_at.isoformat() == "2024-03-01"


@pytest.mark.asyncio
async def test_clinicaltrials_search_returns_empty_list_on_failure(monkeypatch: pytest.MonkeyPatch):
    async def fake_get(self, url, params=None, **kwargs):
        raise httpx.ConnectError("simulated")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    results = await clinicaltrials.search("anything", get_settings(), 5)
    assert results == []


# --- SearXNG (optional) ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_searxng_search_parses_results_when_reachable(monkeypatch: pytest.MonkeyPatch):
    async def fake_get(self, url, params=None, **kwargs):
        return _json_response({"results": [{"title": "General web result", "url": "https://example.org/a", "content": "Some content.", "publishedDate": "2026-01-01T00:00:00"}]})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    results = await searxng.search("glaucoma", get_settings(), 5)

    assert len(results) == 1
    assert results[0].source == WebSource.SEARXNG
    assert results[0].authority_tier == AuthorityTier.F  # always lowest tier — general web


@pytest.mark.asyncio
async def test_searxng_degrades_to_empty_list_when_unreachable(monkeypatch: pytest.MonkeyPatch):
    """Optional infrastructure being absent is never a hard failure (spec §85) —
    confirms the same graceful-degradation contract as every other provider."""

    async def fake_get(self, url, params=None, **kwargs):
        raise httpx.ConnectError("connection refused — searxng not running")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    results = await searxng.search("anything", get_settings(), 5)
    assert results == []
