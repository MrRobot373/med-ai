"""Reranker health/status (spec §6). Same "honest loaded-state, no fake Ready"
approach as `embedding_health.py` — see that module's docstring for the rationale.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass

from app.config.settings import Settings


@dataclass
class RerankerHealth:
    package_installed: bool
    configured_model: str
    device: str
    status: str  # "ready" | "not_loaded" | "package_missing"
    error: str | None = None


def check_reranker_health(settings: Settings) -> RerankerHealth:
    installed = importlib.util.find_spec("transformers") is not None
    if not installed:
        return RerankerHealth(
            package_installed=False,
            configured_model=settings.reranker_model,
            device=settings.reranker_device,
            status="package_missing",
            error="transformers is not installed. Install the 'rag' extra "
            "(pip install -r requirements.txt) to enable local reranking.",
        )

    from app.rag.reranker import is_loaded

    return RerankerHealth(
        package_installed=True,
        configured_model=settings.reranker_model,
        device=settings.reranker_device,
        status="ready" if is_loaded() else "not_loaded",
    )
