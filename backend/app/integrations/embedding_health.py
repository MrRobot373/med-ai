"""Embedding-model health/status (spec §5).

Phase 01 deliberately does NOT eagerly load the embedding model on every health check —
`Qwen3-Embedding-0.6B` is a ~600 MB download and loading it per-request would make the
health endpoint slow and would trigger surprise network usage. Instead we report whether
the `sentence-transformers` package is installed and the configured model name/device;
actual lazy loading (with programmatic dimension detection, never hardcoded) is wired up
in Phase 07 when the RAG pipeline starts using it for real. This is real status, not a
placeholder pretending to be "Ready" — an honest "not loaded yet" is exactly what spec
§103 ("no silent fallback" / no fake status) calls for.
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
    status: str  # "not_loaded" | "package_missing"
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
    return EmbeddingHealth(
        package_installed=True,
        configured_model=settings.embedding_model,
        device=settings.embedding_device,
        status="not_loaded",
        error=None,
    )
