from __future__ import annotations

from pydantic import BaseModel

from app.models.web_cache import WebSource


class ResearchStatusOut(BaseModel):
    enabled: bool
    searxng_reachable: bool
    sources_available: list[WebSource]


class ResearchQueryRequest(BaseModel):
    question: str
    patient_id: str | None = None
    sources: list[WebSource] = []
    date_range: str = "any"  # "any" | "5y" | "1y" — spec §69
    prefer_reviews: bool = True  # spec §69's evidence-preference control
