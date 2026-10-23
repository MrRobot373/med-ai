"""Builds provider clients from the current runtime configuration. Everything that
needs a model goes through here, so swapping a provider in Settings takes effect on
the very next request — no restart. Tests replace these factories with fakes."""

from __future__ import annotations

from app.ai.embeddings import Embedder
from app.ai.llm import LLMClient, vision_llm_config
from app.ai.reranker import Reranker
from app.rag.vector_store import VectorStore
from app.services.runtime_config import RuntimeConfig


def llm(cfg: RuntimeConfig) -> LLMClient:
    return LLMClient(cfg.llm)


def vision_llm(cfg: RuntimeConfig) -> LLMClient:
    return LLMClient(vision_llm_config(cfg.llm, cfg.vision))


def clinical_llm(cfg: RuntimeConfig) -> LLMClient:
    """The specialist medical model (e.g. MedGemma) used for medication and diagnosis review."""
    c = cfg.clinical
    if c.use_main_llm:
        return LLMClient(cfg.llm)
    return LLMClient(
        cfg.llm.model_copy(
            update={
                "provider": c.provider, "base_url": c.base_url, "api_key": c.api_key, "model": c.model,
                "temperature": c.temperature, "max_output_tokens": c.max_output_tokens,
                "context_window": c.context_window, "timeout_seconds": c.timeout_seconds,
            }
        )
    )


def embedder(cfg: RuntimeConfig) -> Embedder:
    return Embedder(cfg.embeddings)


def reranker(cfg: RuntimeConfig) -> Reranker:
    return Reranker(cfg.reranker, cfg.llm)


def vector_store(cfg: RuntimeConfig) -> VectorStore:
    return VectorStore(cfg.vector_store)
