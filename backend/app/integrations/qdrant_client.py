"""Qdrant integration — real reachability check.

Phase 01 only verifies the service is up and lists existing collections; collection
creation (`medical_knowledge`, `patient_documents`, `patient_vision`, `web_cache` per
spec §14) happens in Phase 07 when the RAG pipeline is built.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config.settings import Settings


@dataclass
class QdrantHealth:
    reachable: bool
    collections: list[str]
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
            return QdrantHealth(reachable=True, collections=names)
        except (httpx.HTTPError, ValueError) as exc:
            return QdrantHealth(
                reachable=False,
                collections=[],
                error=f"Qdrant unreachable at {base_url}: {exc}",
            )
