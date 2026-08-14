"""Central application configuration.

Every tunable referenced throughout the Master Build Prompt (model names, RAG K-values,
context profiles, service URLs, feature flags) is declared here as a Pydantic Settings
field so it can be overridden via `.env` / real environment variables without touching
code. Nothing about model choice or retrieval behavior should ever be hardcoded elsewhere
in the app — services should import `get_settings()` and read from it.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchored to the repo root regardless of the process's current working directory —
# backend commands are run from `backend/` (alembic, uvicorn, pytest) while
# `scripts/*.py` are run from the repo root, and both must resolve the same `.env` and
# the same default SQLite file rather than silently creating divergent databases.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "data" / "sqlite" / "gms.db"
DEFAULT_UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"


class RagProfile(str, Enum):
    """Named operational profiles from spec §12. Controls context budget and retrieval
    candidate counts as a group, tuned for the 8 GB VRAM target machine."""

    FAST_DEMO = "fast_demo"
    CLINICAL_QUALITY = "clinical_quality"
    LONG_DOCUMENT = "long_document"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    app_env: str = Field(default="demo", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_secret_key: str = Field(default="dev-only-insecure-key", alias="APP_SECRET_KEY")
    frontend_origin: str = Field(default="http://localhost:5173", alias="FRONTEND_ORIGIN")

    # --- Database ---
    database_url: str = Field(
        default=f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}", alias="DATABASE_URL"
    )

    # --- Qdrant ---
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, alias="QDRANT_API_KEY")

    # --- Ollama (main LLM/VLM) ---
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen3.5:9b", alias="OLLAMA_MODEL")
    ollama_request_timeout_seconds: int = Field(default=120, alias="OLLAMA_REQUEST_TIMEOUT_SECONDS")

    # --- Embedding / Reranker ---
    embedding_model: str = Field(default="Qwen/Qwen3-Embedding-0.6B", alias="EMBEDDING_MODEL")
    embedding_device: str = Field(default="cpu", alias="EMBEDDING_DEVICE")
    embedding_batch_size: int = Field(default=16, alias="EMBEDDING_BATCH_SIZE")
    reranker_model: str = Field(default="Qwen/Qwen3-Reranker-0.6B", alias="RERANKER_MODEL")
    reranker_device: str = Field(default="cpu", alias="RERANKER_DEVICE")

    # --- RAG retrieval defaults ---
    rag_profile: RagProfile = Field(default=RagProfile.FAST_DEMO, alias="RAG_PROFILE")
    rag_dense_top_k: int = Field(default=30, alias="RAG_DENSE_TOP_K")
    rag_sparse_top_k: int = Field(default=30, alias="RAG_SPARSE_TOP_K")
    rag_fusion_top_k: int = Field(default=20, alias="RAG_FUSION_TOP_K")
    rag_rerank_top_k: int = Field(default=8, alias="RAG_RERANK_TOP_K")
    rag_default_context_tokens: int = Field(default=8192, alias="RAG_DEFAULT_CONTEXT_TOKENS")

    # --- Research Mode (off by default — privacy-first per §64) ---
    enable_research: bool = Field(default=False, alias="ENABLE_RESEARCH")
    searxng_url: str = Field(default="http://localhost:8080", alias="SEARXNG_URL")

    # --- Voice module (feature-flagged per §91) ---
    enable_voice: bool = Field(default=False, alias="ENABLE_VOICE")

    # --- Uploads / sessions ---
    upload_max_mb: int = Field(default=25, alias="UPLOAD_MAX_MB")
    upload_dir: str = Field(default=str(DEFAULT_UPLOAD_DIR), alias="UPLOAD_DIR")
    session_timeout_minutes: int = Field(default=60, alias="SESSION_TIMEOUT_MINUTES")

    # --- Ingestion (Phase 05) ---
    # OCR is auto-detected (package installed or not) — this only lets an operator
    # force it off even when installed, e.g. to keep a low-resource demo machine fast.
    enable_ocr: bool = Field(default=True, alias="ENABLE_OCR")
    ocr_min_chars_per_page: int = Field(default=40, alias="OCR_MIN_CHARS_PER_PAGE")

    # --- Auth (Phase 03) ---
    session_cookie_name: str = Field(default="gms_session", alias="SESSION_COOKIE_NAME")
    # False by default (plain HTTP on localhost during the demo). Set true explicitly
    # once the deployment is behind HTTPS — never inferred/guessed, per spec §103.
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")
    login_rate_limit_attempts: int = Field(default=5, alias="LOGIN_RATE_LIMIT_ATTEMPTS")
    login_rate_limit_window_seconds: int = Field(default=900, alias="LOGIN_RATE_LIMIT_WINDOW_SECONDS")

    # --- Logging ---
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    debug_mode: bool = Field(default=False, alias="DEBUG_MODE")


@lru_cache
def get_settings() -> Settings:
    """Settings are cached for process lifetime. Tests override via dependency
    injection / monkeypatching env vars before first access, not by mutating this."""
    return Settings()
