"""FDA/openFDA — spec §65. Drug label search (api.fda.gov), no API key required.
Regulatory information — spec §67's Tier A ("regulatory information")."""

from __future__ import annotations

from datetime import date

import httpx

from app.config.settings import Settings
from app.logging import get_logger
from app.models.web_cache import AuthorityTier, WebSource
from app.research.providers.base import WebResult, clean_search_terms

logger = get_logger(__name__)

_BASE = "https://api.fda.gov/drug/label.json"
_TEXT_FIELDS = ("indications_and_usage", "warnings_and_cautions", "boxed_warning")


def _parse_effective_time(value: str | None) -> date | None:
    if not value or len(value) != 8 or not value.isdigit():
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


def _excerpt(result: dict) -> str:
    parts = []
    for field in _TEXT_FIELDS:
        values = result.get(field)
        if values:
            parts.append(values[0])
    return " ".join(parts)[:2000]


async def search(query: str, settings: Settings, max_results: int) -> list[WebResult]:
    # openFDA's search syntax is field:term, not free text — searching across the
    # clinically relevant label sections covers most research questions well without
    # requiring the caller to know openFDA's field names. A raw clinician question
    # quoted as a literal phrase either never matches or is rejected outright as
    # invalid syntax (found live: a "?" and unbalanced "(...)" inside the quoted
    # phrase 400'd) — cleaned, unquoted keywords let openFDA's own analyzer match
    # any of them instead of requiring an exact-phrase hit.
    terms = clean_search_terms(query)
    search_expr = f"(indications_and_usage:{terms} OR warnings_and_cautions:{terms} OR openfda.generic_name:{terms})"
    try:
        async with httpx.AsyncClient(timeout=settings.research_http_timeout_seconds) as client:
            resp = await client.get(_BASE, params={"search": search_expr, "limit": max_results})
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        logger.warning("openFDA search failed", exc_info=True)
        return []

    results = []
    for result in data.get("results", []):
        openfda = result.get("openfda", {})
        brand = (openfda.get("brand_name") or [None])[0]
        generic = (openfda.get("generic_name") or [None])[0]
        title = brand or generic or "FDA drug label"
        set_id = result.get("set_id")
        url = f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}" if set_id else "https://www.fda.gov"
        text = _excerpt(result)
        if not text.strip():
            continue
        results.append(
            WebResult(
                title=title,
                url=url,
                text=text,
                source=WebSource.FDA,
                authority_tier=AuthorityTier.A,
                published_at=_parse_effective_time(result.get("effective_time")),
                study_type=None,
            )
        )
    return results
