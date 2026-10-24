"""Runtime configuration — everything an administrator tunes from Settings.

Stored as one JSON document in `app_settings` (key `runtime`). Secrets (API keys) are
encrypted at rest with a key derived from APP_SECRET_KEY and are never returned to the
browser in clear text: the API exposes `has_api_key` + a masked preview instead.

Each section is a pydantic model so the UI, the API and the providers all share one
validated schema. Unknown/old keys are ignored, missing keys take defaults, so the
document can evolve without migrations.
"""

from __future__ import annotations

import threading
import time
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decrypt_secret, encrypt_secret, mask_secret
from app.models import AppSetting

LLMProvider = Literal["ollama", "openai"]
EmbeddingProvider = Literal["ollama", "openai", "local"]
RerankerProvider = Literal["none", "local", "remote", "llm"]


class LLMConfig(BaseModel):
    provider: LLMProvider = "ollama"
    base_url: str = "http://localhost:11434"
    api_key: str | None = None
    model: str = "qwen3.5:9b"
    temperature: float = Field(0.15, ge=0, le=2)
    max_output_tokens: int = Field(1536, ge=64, le=32768)
    context_window: int = Field(8192, ge=1024, le=1_048_576)
    timeout_seconds: int = Field(300, ge=5, le=3600)
    # Hybrid-reasoning models (qwen3.x, deepseek-r1…) spend tokens on hidden "thinking"
    # before any visible output. Off by default: faster and nothing is hidden.
    reasoning: bool = False
    max_concurrency: int = Field(1, ge=1, le=32)
    extra_headers: dict[str, str] = Field(default_factory=dict)


class VisionConfig(BaseModel):
    # When true the main LLM handles images too (it must be multimodal).
    use_main_llm: bool = True
    provider: LLMProvider = "ollama"
    base_url: str = "http://localhost:11434"
    api_key: str | None = None
    model: str = "qwen3.5:9b"
    max_image_dimension: int = Field(1600, ge=256, le=4096)
    temperature: float = Field(0.1, ge=0, le=2)


class ClinicalModelConfig(BaseModel):
    """Specialist medical model for dose review, diagnosis second look and pre-visit
    briefs (default: Google MedGemma 27B via Ollama). Chat keeps the main LLM."""

    use_main_llm: bool = False
    provider: LLMProvider = "ollama"
    base_url: str = "http://localhost:11434"
    api_key: str | None = None
    model: str = "medgemma:27b"
    temperature: float = Field(0.1, ge=0, le=2)
    max_output_tokens: int = Field(2048, ge=64, le=32768)
    context_window: int = Field(8192, ge=1024, le=1_048_576)
    timeout_seconds: int = Field(600, ge=5, le=3600)


class FormularyConfig(BaseModel):
    region: Literal["IN"] = "IN"
    # Look up a reference picture for a medicine by its generic name (Wikimedia).
    # Only the drug name is ever sent — never patient data.
    fetch_images: bool = True


class EmbeddingConfig(BaseModel):
    provider: EmbeddingProvider = "ollama"
    base_url: str = "http://localhost:11434"
    api_key: str | None = None
    model: str = "qwen3-embedding:0.6b"
    device: str = "cpu"
    batch_size: int = Field(16, ge=1, le=512)
    # Optional instruction prefix applied to queries only (instruction-tuned embedders).
    query_instruction: str = ""


class RerankerConfig(BaseModel):
    provider: RerankerProvider = "none"
    base_url: str = ""
    api_key: str | None = None
    model: str = ""
    device: str = "cpu"


class RetrievalConfig(BaseModel):
    profile: Literal["fast", "balanced", "thorough", "custom"] = "fast"
    dense_top_k: int = Field(30, ge=1, le=200)
    lexical_top_k: int = Field(30, ge=0, le=200)
    fusion_top_k: int = Field(20, ge=1, le=200)
    final_top_k: int = Field(8, ge=1, le=40)
    rrf_k: int = Field(60, ge=1, le=1000)
    dense_weight: float = Field(1.0, ge=0, le=5)
    lexical_weight: float = Field(1.0, ge=0, le=5)
    # Passages whose reranker score falls below this are dropped (reranker only).
    min_rerank_score: float = Field(0.0, ge=-100, le=100)
    chunk_size_tokens: int = Field(550, ge=100, le=4000)
    chunk_overlap_tokens: int = Field(80, ge=0, le=1000)
    context_budget_tokens: int = Field(6000, ge=500, le=500_000)
    history_turns: int = Field(4, ge=0, le=20)
    include_knowledge_in_patient_chat: bool = True


RETRIEVAL_PROFILES: dict[str, dict] = {
    "fast": {
        "dense_top_k": 25,
        "lexical_top_k": 25,
        "fusion_top_k": 16,
        "final_top_k": 6,
        "context_budget_tokens": 5000,
    },
    "balanced": {
        "dense_top_k": 40,
        "lexical_top_k": 40,
        "fusion_top_k": 24,
        "final_top_k": 8,
        "context_budget_tokens": 8000,
    },
    "thorough": {
        "dense_top_k": 80,
        "lexical_top_k": 80,
        "fusion_top_k": 40,
        "final_top_k": 12,
        "context_budget_tokens": 14000,
    },
}


class VectorStoreConfig(BaseModel):
    # "embedded" keeps vectors in a local folder (no extra service to run);
    # "server" talks to a Qdrant server (Docker / cloud).
    mode: Literal["embedded", "server"] = "embedded"
    url: str = "http://localhost:6333"
    api_key: str | None = None
    collection_prefix: str = "gms"


class BrandingConfig(BaseModel):
    product_name: str = "GMS Clinical AI"
    tagline: str = "Clinical intelligence, grounded in evidence"
    organization: str = "GMS Health"
    logo_data_url: str | None = None
    default_accent: str = "#246BFD"
    default_theme: Literal["light", "dark", "system"] = "light"
    disclaimer: str = "Clinical decision support — AI output must be reviewed by the treating clinician."
    login_message: str = "Private, on-premise clinical intelligence."


class SecurityConfig(BaseModel):
    session_timeout_minutes: int = Field(480, ge=5, le=60 * 24 * 30)
    allow_viewer_ai: bool = True


class RuntimeConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    clinical: ClinicalModelConfig = Field(default_factory=ClinicalModelConfig)
    formulary: FormularyConfig = Field(default_factory=FormularyConfig)
    embeddings: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    branding: BrandingConfig = Field(default_factory=BrandingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    # Fingerprint of the embedding setup the vector index was built with. When the
    # current embedding config no longer matches, the UI asks for a re-index.
    index_signature: str | None = None
    index_dimension: int | None = None


SECTIONS = (
    "llm",
    "vision",
    "clinical",
    "formulary",
    "embeddings",
    "reranker",
    "retrieval",
    "vector_store",
    "branding",
    "security",
)
# (section, field) pairs holding secrets.
SECRET_FIELDS: tuple[tuple[str, str], ...] = (
    ("llm", "api_key"),
    ("vision", "api_key"),
    ("clinical", "api_key"),
    ("embeddings", "api_key"),
    ("reranker", "api_key"),
    ("vector_store", "api_key"),
)

_KEY = "runtime"
_cache: RuntimeConfig | None = None
_cache_stamp = None
_checked = 0.0
_lock = threading.Lock()
# Settings saved by another process (a CLI command, a second worker) are picked up within this time.
_RECHECK_SECONDS = 3.0


def _defaults() -> RuntimeConfig:
    s = get_settings()
    cfg = RuntimeConfig()
    cfg.llm.provider = s.default_llm_provider  # type: ignore[assignment]
    cfg.llm.base_url = s.default_llm_base_url
    cfg.llm.model = s.default_llm_model
    cfg.vision.base_url = s.default_llm_base_url
    cfg.vision.model = s.default_llm_model
    cfg.embeddings.provider = s.default_embedding_provider  # type: ignore[assignment]
    cfg.embeddings.base_url = s.default_embedding_base_url
    cfg.embeddings.model = s.default_embedding_model
    if s.default_vector_store_url:
        cfg.vector_store.mode = "server"
        cfg.vector_store.url = s.default_vector_store_url
    return cfg


def _decrypt_in_place(data: dict) -> dict:
    key = get_settings().secret_key
    for section, field in SECRET_FIELDS:
        sec = data.get(section) or {}
        token = sec.get(field)
        if token:
            sec[field] = decrypt_secret(token, key)
    return data


def _encrypt_copy(cfg: RuntimeConfig) -> dict:
    key = get_settings().secret_key
    data = cfg.model_dump(mode="json")
    for section, field in SECRET_FIELDS:
        value = data[section].get(field)
        data[section][field] = encrypt_secret(value, key) if value else None
    return data


def load(db: Session) -> RuntimeConfig:
    global _cache, _cache_stamp, _checked
    if _cache is not None and time.monotonic() - _checked < _RECHECK_SECONDS:
        return _cache
    with _lock:
        stamp = db.scalar(select(AppSetting.updated_at).where(AppSetting.key == _KEY))
        _checked = time.monotonic()
        if _cache is not None and stamp is not None and stamp == _cache_stamp:
            return _cache
        row = db.get(AppSetting, _KEY)
        if row is None:
            cfg = _defaults()
            row = AppSetting(key=_KEY, value=_encrypt_copy(cfg))
            db.add(row)
            db.commit()
        else:
            db.refresh(row)
            cfg = RuntimeConfig.model_validate(_decrypt_in_place(dict(row.value)))
        _cache, _cache_stamp = cfg, row.updated_at
        return cfg


def save(db: Session, cfg: RuntimeConfig, user_id: str | None = None) -> RuntimeConfig:
    global _cache, _cache_stamp, _checked
    with _lock:
        row = db.get(AppSetting, _KEY)
        data = _encrypt_copy(cfg)
        if row is None:
            row = AppSetting(key=_KEY, value=data, updated_by=user_id)
            db.add(row)
        else:
            row.value = data
            row.updated_by = user_id
        db.commit()
        _cache, _cache_stamp, _checked = cfg.model_copy(deep=True), row.updated_at, time.monotonic()
    return _cache


def invalidate_cache() -> None:
    global _cache, _cache_stamp
    _cache, _cache_stamp = None, None


def apply_section_update(cfg: RuntimeConfig, section: str, patch: dict) -> RuntimeConfig:
    """Merge a partial section update. For secret fields: omitted / null keeps the
    stored value, empty string clears it, anything else replaces it."""
    if section not in SECTIONS:
        raise ValueError(f"Unknown settings section '{section}'")
    current = getattr(cfg, section).model_dump()
    secret_names = {f for s, f in SECRET_FIELDS if s == section}
    for name, value in patch.items():
        if name not in current:
            continue
        if name in secret_names:
            if value is None:
                continue
            current[name] = value or None
        else:
            current[name] = value
    if section == "retrieval" and patch.get("profile") in RETRIEVAL_PROFILES:
        # Choosing a named profile applies its numbers; editing a number switches to custom.
        current.update(RETRIEVAL_PROFILES[patch["profile"]])
    elif section == "retrieval" and any(
        k in patch for k in ("dense_top_k", "lexical_top_k", "fusion_top_k", "final_top_k")
    ):
        current["profile"] = "custom"
    new_section = type(getattr(cfg, section)).model_validate(current)
    updated = cfg.model_copy(deep=True)
    setattr(updated, section, new_section)
    return updated


def public_view(cfg: RuntimeConfig) -> dict:
    """Configuration as the admin UI sees it: secrets replaced by presence + mask."""
    data = cfg.model_dump(mode="json")
    for section, field in SECRET_FIELDS:
        value = data[section].pop(field, None)
        data[section][f"has_{field}"] = bool(value)
        data[section][f"{field}_preview"] = mask_secret(value)
    data["index_status"] = index_status(cfg)
    return data


def embedding_signature(cfg: RuntimeConfig) -> str:
    e = cfg.embeddings
    return f"{e.provider}|{e.base_url.rstrip('/') if e.provider != 'local' else ''}|{e.model}"


def index_status(cfg: RuntimeConfig) -> dict:
    current = embedding_signature(cfg)
    return {
        "current_signature": current,
        "indexed_signature": cfg.index_signature,
        "dimension": cfg.index_dimension,
        "reindex_required": cfg.index_signature is not None and cfg.index_signature != current,
    }
