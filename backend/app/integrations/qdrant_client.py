"""Qdrant integration — real reachability check, including real per-collection point
counts (spec §84 — no hardcoded "Ready" placeholder) once Phase 07's collections
(`medical_knowledge`, `patient_documents`) exist. `patient_vision` (Phase 09) and
`web_cache` (Phase 11) join the same way once those phases create them.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config.settings import Settings


@dataclass
class QdrantHealth:
    reachable: bool
    collections: list[str]
    points_by_collection: dict[str, int]
    error: str | None = None


async def check_qdrant_health(settings: Settings) -> QdrantHealth:
    base_url = settings.qdrant_url.rstrip("/")
    headers = {"api-key": settings.qdrant_api_key} if settings.qdrant_api_key else {}
    async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
        try:
            resp = await client.get(f"{base_url}/collections")
            resp.raise_for_status()
            payload = resp.json()
            names = [c.get("name", "") for c in payload.get("result", {}).get("collections", [])]

            points_by_collection: dict[str, int] = {}
            for name in names:
                try:
                    detail = await client.get(f"{base_url}/collections/{name}")
                    detail.raise_for_status()
                    points_by_collection[name] = detail.json().get("result", {}).get("points_count", 0)
                except (httpx.HTTPError, ValueError):
                    pass  # a per-collection detail failure shouldn't sink the whole health check

            return QdrantHealth(reachable=True, collections=names, points_by_collection=points_by_collection)
        except (httpx.HTTPError, ValueError) as exc:
            return QdrantHealth(
                reachable=False,
                collections=[],
                points_by_collection={},
                error=f"Qdrant unreachable at {base_url}: {exc}",
            )
