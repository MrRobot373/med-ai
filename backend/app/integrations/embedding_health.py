"""Embedding-model health/status (spec §5).

This deliberately does NOT eagerly load the embedding model just to answer a health
check — `Qwen3-Embedding-0.6B` is a ~600 MB download and loading it per-request would
make the health endpoint slow and trigger surprise network usage. Instead it reports
whether the model is *already* loaded (`app.rag.embeddings.is_loaded()` — true once
anything has actually indexed or queried) with its real, programmatically-detected
dimension, or an honest "not loaded yet" otherwise — never a hardcoded "Ready"
placeholder (spec §103 "no silent fallback").
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass

from app.config.settings import Settings


@dataclass
class EmbeddingHealth:
    package_installed: bool
    configured_model: str
    device: str
    status: str  # "ready" | "not_loaded" | "package_missing"
    dimension: int | None = None
    error: str | None = None


def check_embedding_health(settings: Settings) -> EmbeddingHealth:
    installed = importlib.util.find_spec("sentence_transformers") is not None
    if not installed:
        return EmbeddingHealth(
            package_installed=False,
            configured_model=settings.embedding_model,
            device=settings.embedding_device,
            status="package_missing",
            error="sentence-transformers is not installed. Install the 'rag' extra "
            "(pip install -r requirements.txt) to enable local embedding.",
        )

    from app.rag.embeddings import get_embedding_dimension, is_loaded

    if not is_loaded():
        return EmbeddingHealth(
            package_installed=True,
            configured_model=settings.embedding_model,
            device=settings.embedding_device,
            status="not_loaded",
        )
    return EmbeddingHealth(
        package_installed=True,
        configured_model=settings.embedding_model,
        device=settings.embedding_device,
        status="ready",
        dimension=get_embedding_dimension(settings),
    )
