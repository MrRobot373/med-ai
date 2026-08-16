"""SearXNG — spec §65's "optional generic discovery through self-hosted SearXNG."
General web results are Tier E/F (spec §67) — always the lowest-priority source, and
only queried when explicitly enabled (see `services/research.py`). Requires a running
SearXNG instance with JSON output enabled (`search.formats: [html, json]` in its
settings.yml, `docker compose --profile research up searxng`); if unreachable or JSON
isn't enabled, this degrades to an empty result list like every other provider —
optional infrastructure being absent is never a hard failure (spec §85).
"""

from __future__ import annotations

from datetime import date

import httpx

from app.config.settings import Settings
from app.logging import get_logger
from app.models.web_cache import AuthorityTier, WebSource
from app.research.providers.base import WebResult

logger = get_logger(__name__)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


async def search(query: str, settings: Settings, max_results: int) -> list[WebResult]:
    try:
        async with httpx.AsyncClient(timeout=settings.research_http_timeout_seconds) as client:
            resp = await client.get(
                f"{settings.searxng_url.rstrip('/')}/search", params={"q": query, "format": "json"}
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        logger.warning("SearXNG search failed or is unreachable — optional source, degrading to no results", exc_info=True)
        return []

    results = []
    for item in data.get("results", [])[:max_results]:
        url = item.get("url")
        title = (item.get("title") or "").strip()
        content = (item.get("content") or "").strip()
        if not url or not title:
            continue
        results.append(
            WebResult(
                title=title,
                url=url,
                text=content or title,
                source=WebSource.SEARXNG,
                authority_tier=AuthorityTier.F,
                published_at=_parse_date(item.get("publishedDate")),
                study_type=None,
            )
        )
    return results
