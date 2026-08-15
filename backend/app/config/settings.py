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
    # Qwen3-Embedding defaults to a 32,768-token max sequence length (it supports very
    # long context) — sentence-transformers sizes its attention computation off that
    # max, not the actual input length, so leaving it uncapped makes embedding even a
    # short ~500-token chunk dramatically (60x+, measured) slower than necessary on
    # CPU. Our chunks target 400-700 tokens (spec §55); 2048 leaves comfortable margin
    # for the real tokenizer producing more tokens than chunking.py's approximation.
    embedding_max_seq_length: int = Field(default=2048, alias="EMBEDDING_MAX_SEQ_LENGTH")
    reranker_model: str = Field(default="Qwen/Qwen3-Reranker-0.6B", alias="RERANKER_MODEL")
    reranker_device: str = Field(default="cpu", alias="RERANKER_DEVICE")

    # --- RAG retrieval defaults ---
    rag_profile: RagProfile = Field(default=RagProfile.FAST_DEMO, alias="RAG_PROFILE")
    rag_dense_top_k: int = Field(default=30, alias="RAG_DENSE_TOP_K")
    rag_sparse_top_k: int = Field(default=30, alias="RAG_SPARSE_TOP_K")
    # Post-fusion candidate count kept for reranking — spec §46 "retain approximately
    # 15-20 candidates" before the reranker runs.
    rag_fusion_top_k: int = Field(default=20, alias="RAG_FUSION_TOP_K")
    # Final passages kept after reranking — spec §46 "keep approximately 6-8".
    rag_rerank_top_k: int = Field(default=8, alias="RAG_RERANK_TOP_K")
    rag_default_context_tokens: int = Field(default=8192, alias="RAG_DEFAULT_CONTEXT_TOKENS")
    # RRF's rank-damping constant (spec §44) — 60 is the standard default from the
    # original Reciprocal Rank Fusion paper, not a value this deployment has tuned.
    rag_rrf_k: int = Field(default=60, alias="RAG_RRF_K")
    # Chunking (Phase 07, spec §55): "approximately 400-700 tokens" / "60-100 token
    # overlap" — token count is an approximation (see ingestion/chunking.py), not a
    # real tokenizer's count, so these sit mid-range rather than at either edge.
    rag_chunk_target_tokens: int = Field(default=550, alias="RAG_CHUNK_TARGET_TOKENS")
    rag_chunk_overlap_tokens: int = Field(default=80, alias="RAG_CHUNK_OVERLAP_TOKENS")
    # Deduplication (spec §47): cosine-similarity threshold above which two adjacent
    # chunks from the same source are considered overlapping enough to merge.
    rag_dedup_similarity_threshold: float = Field(default=0.92, alias="RAG_DEDUP_SIMILARITY_THRESHOLD")

    # --- Clinical chat / generation (Phase 08, spec §50) ---
    # "Low, deterministic temperature... suggested default 0.1-0.2" — a clinical
    # answer generator prioritizes reproducibility over creative variation.
    chat_temperature: float = Field(default=0.15, alias="CHAT_TEMPERATURE")
    chat_max_output_tokens: int = Field(default=1024, alias="CHAT_MAX_OUTPUT_TOKENS")
    # Spec §121: "do not launch multiple simultaneous heavy Qwen generations for the
    # same user unintentionally" — a single shared slot is enough for a one-machine
    # demo without adding a real task queue (spec §135 "avoid unnecessary infrastructure").
    chat_max_concurrent_generations: int = Field(default=1, alias="CHAT_MAX_CONCURRENT_GENERATIONS")
    # How many prior turns (user+assistant pairs) are replayed into the prompt so the
    # model can resolve conversational references ("what about the second one?") itself
    # — a deliberately simpler alternative to a separate query-rewriting LLM call (spec
    # §43 Stage 3); see rag-design notes in docs/architecture.md's Phase 08 section.
    chat_history_turns: int = Field(default=4, alias="CHAT_HISTORY_TURNS")

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
