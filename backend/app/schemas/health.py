"""Response models for /api/health*. Every field reflects a live check performed at
request time — nothing here is a hardcoded/default "Ready" value (spec §84/§85/§103)."""

from __future__ import annotations

from pydantic import BaseModel


class DatabaseStatus(BaseModel):
    reachable: bool
    error: str | None = None


class OllamaStatus(BaseModel):
    reachable: bool
    version: str | None
    configured_model: str
    model_available: bool
    error: str | None = None


class QdrantStatus(BaseModel):
    reachable: bool
    collections: list[str]
    error: str | None = None


class ModelComponentStatus(BaseModel):
    configured_model: str
    device: str
    status: str
    package_installed: bool
    error: str | None = None


class ModelsStatus(BaseModel):
    llm: OllamaStatus
    embedding: ModelComponentStatus
    reranker: ModelComponentStatus
    ocr: ModelComponentStatus


class OverallHealth(BaseModel):
    status: str  # "ok" | "degraded"
    backend: bool = True
    database: DatabaseStatus
    ollama: OllamaStatus
    qdrant: QdrantStatus
