"""ClinicalTrials.gov — spec §65. Public API v2, no API key required. Registered
trials — spec §67's Tier C ("peer-reviewed clinical studies") for completed trials
with results; treated the same tier here since a trial's registration itself doesn't
carry peer-review status either way, and this app never fabricates that distinction.
"""

from __future__ import annotations

from datetime import date

import httpx

from app.config.settings import Settings
from app.logging import get_logger
from app.models.web_cache import AuthorityTier, WebSource
from app.research.providers.base import WebResult

logger = get_logger(__name__)

_BASE = "https://clinicaltrials.gov/api/v2/studies"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        parts = [int(p) for p in value.split("-")]
        while len(parts) < 3:
            parts.append(1)
        return date(*parts[:3])
    except (ValueError, TypeError):
        return None


async def search(query: str, settings: Settings, max_results: int) -> list[WebResult]:
    try:
        async with httpx.AsyncClient(timeout=settings.research_http_timeout_seconds) as client:
            resp = await client.get(
                _BASE,
                params={
                    "query.term": query,
                    "pageSize": max_results,
                    "fields": "NCTId,BriefTitle,OverallStatus,StudyType,StartDate,BriefSummary",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        logger.warning("ClinicalTrials.gov search failed", exc_info=True)
        return []

    results = []
    for study in data.get("studies", []):
        protocol = study.get("protocolSection", {})
        identification = protocol.get("identificationModule", {})
        nct_id = identification.get("nctId")
        if not nct_id:
            continue
        title = identification.get("briefTitle", "").strip() or nct_id
        summary = protocol.get("descriptionModule", {}).get("briefSummary", "").strip()
        status = protocol.get("statusModule", {})
        study_type_raw = protocol.get("designModule", {}).get("studyType", "")
        study_type = "rct" if study_type_raw.upper() == "INTERVENTIONAL" else "observational"
        results.append(
            WebResult(
                title=title,
                url=f"https://clinicaltrials.gov/study/{nct_id}",
                text=summary or title,
                source=WebSource.CLINICALTRIALS,
                authority_tier=AuthorityTier.C,
                published_at=_parse_date(status.get("startDateStruct", {}).get("date")),
                study_type=study_type,
            )
        )
    return results
