"""PubMed/NCBI — spec §65's first-priority trusted provider. NCBI E-utilities, no API
key required (an optional key just raises the rate limit — spec's own "do not commit
real secrets" ethos applies: never required for the integration to work).
"""

from __future__ import annotations

from datetime import date
from xml.etree import ElementTree

import httpx

from app.config.settings import Settings
from app.logging import get_logger
from app.models.web_cache import AuthorityTier, WebSource
from app.research.providers.base import WebResult, clean_search_terms

logger = get_logger(__name__)

_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

_MONTHS = {
    m.lower(): i
    for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1
    )
}


def _classify_pubtype(pubtypes: list[str]) -> tuple[str | None, AuthorityTier]:
    lowered = {t.lower() for t in pubtypes}
    if "systematic review" in lowered or "meta-analysis" in lowered:
        return "systematic_review", AuthorityTier.B
    if "practice guideline" in lowered or "guideline" in lowered:
        return "systematic_review", AuthorityTier.A
    if "randomized controlled trial" in lowered:
        return "rct", AuthorityTier.C
    if "observational study" in lowered or "comparative study" in lowered:
        return "observational", AuthorityTier.C
    return None, AuthorityTier.D


def _parse_pubdate(pubdate: str) -> date | None:
    # esummary's "pubdate" is free-text ("2026 Jul 14", "2026", "2026 Jul") — parsed
    # best-effort; an unparseable format just means no date, never a guessed one.
    parts = pubdate.split()
    if not parts or not parts[0].isdigit():
        return None
    year = int(parts[0])
    month = _MONTHS.get(parts[1][:3].lower(), 1) if len(parts) > 1 else 1
    day = 1
    if len(parts) > 2:
        try:
            day = int(parts[2])
        except ValueError:
            day = 1
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_abstracts(xml_text: str) -> dict[str, str]:
    abstracts: dict[str, str] = {}
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return abstracts
    for article in root.iter("PubmedArticle"):
        pmid_el = article.find(".//PMID")
        if pmid_el is None or not pmid_el.text:
            continue
        segments = [(seg.text or "") for seg in article.findall(".//Abstract/AbstractText")]
        abstracts[pmid_el.text] = " ".join(s.strip() for s in segments if s.strip())
    return abstracts


async def search(query: str, settings: Settings, max_results: int) -> list[WebResult]:
    # esearch implicitly ANDs every space-separated term — a raw clinician question's
    # filler words zero out the result set (found live; see base.py's docstring).
    search_term = clean_search_terms(query)
    key_kw = {"api_key": settings.pubmed_api_key} if settings.pubmed_api_key else {}
    try:
        async with httpx.AsyncClient(timeout=settings.research_http_timeout_seconds) as client:
            esearch_resp = await client.get(
                f"{_BASE}/esearch.fcgi",
                params={"db": "pubmed", "term": search_term, "retmode": "json", "retmax": max_results, "sort": "relevance", **key_kw},
            )
            esearch_resp.raise_for_status()
            ids: list[str] = esearch_resp.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return []
            id_param = ",".join(ids)

            esummary_resp = await client.get(
                f"{_BASE}/esummary.fcgi", params={"db": "pubmed", "id": id_param, "retmode": "json", **key_kw}
            )
            esummary_resp.raise_for_status()
            summaries = esummary_resp.json().get("result", {})

            efetch_resp = await client.get(
                f"{_BASE}/efetch.fcgi", params={"db": "pubmed", "id": id_param, "rettype": "abstract", "retmode": "xml", **key_kw}
            )
            efetch_resp.raise_for_status()
            abstracts = _parse_abstracts(efetch_resp.text)
    except (httpx.HTTPError, ValueError):
        logger.warning("PubMed search failed for query (not logged — may carry clinical context)", exc_info=True)
        return []

    results = []
    for pmid in ids:
        summary = summaries.get(pmid)
        if not isinstance(summary, dict):
            continue
        title = (summary.get("title") or "").strip() or f"PubMed {pmid}"
        study_type, tier = _classify_pubtype(summary.get("pubtype") or [])
        text = abstracts.get(pmid, "").strip() or title
        results.append(
            WebResult(
                title=title,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                text=text,
                source=WebSource.PUBMED,
                authority_tier=tier,
                published_at=_parse_pubdate(summary.get("pubdate") or ""),
                study_type=study_type,
            )
        )
    return results
