"""Ollama integration — real reachability + configured-model presence checks.

Per spec §4/§85: if the configured model isn't available, we report that explicitly with
the exact configured name. We never silently substitute a different model that happens to
be installed.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config.settings import Settings


@dataclass
class OllamaHealth:
    reachable: bool
    version: str | None
    configured_model: str
    model_available: bool
    available_models: list[str]
    error: str | None = None


async def check_ollama_health(settings: Settings) -> OllamaHealth:
    base_url = settings.ollama_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            version_resp = await client.get(f"{base_url}/api/version")
            version_resp.raise_for_status()
            version = version_resp.json().get("version")
        except (httpx.HTTPError, ValueError) as exc:
            return OllamaHealth(
                reachable=False,
                version=None,
                configured_model=settings.ollama_model,
                model_available=False,
                available_models=[],
                error=f"Ollama unreachable at {base_url}: {exc}",
            )

        try:
            tags_resp = await client.get(f"{base_url}/api/tags")
            tags_resp.raise_for_status()
            models = [m.get("name", "") for m in tags_resp.json().get("models", [])]
        except (httpx.HTTPError, ValueError) as exc:
            return OllamaHealth(
                reachable=True,
                version=version,
                configured_model=settings.ollama_model,
                model_available=False,
                available_models=[],
                error=f"Ollama reachable but /api/tags failed: {exc}",
            )

    model_available = _model_name_matches(settings.ollama_model, models)
    error = None
    if not model_available:
        error = (
            f"Configured model '{settings.ollama_model}' is not pulled in Ollama. "
            f"Run: ollama pull {settings.ollama_model}"
        )

    return OllamaHealth(
        reachable=True,
        version=version,
        configured_model=settings.ollama_model,
        model_available=model_available,
        available_models=models,
        error=error,
    )


def _model_name_matches(configured: str, available: list[str]) -> bool:
    """Ollama tags include a `:tag` suffix (e.g. `qwen3.5:9b`) and sometimes a registry
    digest suffix. Match on exact name first, then on the name without an explicit
    `:latest` default, so we don't silently accept an unrelated model."""
    if configured in available:
        return True
    normalized = configured if ":" in configured else f"{configured}:latest"
    return normalized in available
