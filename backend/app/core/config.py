"""Bootstrap configuration read from the environment / `.env`.

Only infrastructure-level values live here (where the database is, the secret key,
where files are stored). Everything an operator is expected to tune while the app is
running — AI providers, models, retrieval parameters, branding —
lives in the runtime configuration (`app.services.runtime_config`), which is stored
in the database and edited from Settings. The `DEFAULT_*` values below only seed that
runtime configuration on first start.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    secret_key: str = Field(default="change-me-in-production", alias="APP_SECRET_KEY")
    data_dir: Path = Field(default=PROJECT_ROOT / "data", alias="DATA_DIR")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173", alias="CORS_ORIGINS")
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")
    session_cookie_name: str = Field(default="gms_session", alias="SESSION_COOKIE_NAME")
    upload_max_mb: int = Field(default=40, alias="UPLOAD_MAX_MB")
    login_rate_limit_attempts: int = Field(default=8, alias="LOGIN_RATE_LIMIT_ATTEMPTS")
    login_rate_limit_window_seconds: int = Field(default=600, alias="LOGIN_RATE_LIMIT_WINDOW_SECONDS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # First-run administrator. Created only when the users table is empty.
    bootstrap_admin_email: str = Field(default="admin@gms.local", alias="BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_password: str = Field(default="Admin@12345", alias="BOOTSTRAP_ADMIN_PASSWORD")

    # Seed values for the runtime configuration (first start only; edit later in Settings).
    default_llm_provider: str = Field(default="ollama", alias="DEFAULT_LLM_PROVIDER")
    default_llm_base_url: str = Field(default="http://localhost:11434", alias="DEFAULT_LLM_BASE_URL")
    default_llm_model: str = Field(default="qwen3.5:9b", alias="DEFAULT_LLM_MODEL")
    default_embedding_provider: str = Field(default="ollama", alias="DEFAULT_EMBEDDING_PROVIDER")
    default_embedding_base_url: str = Field(default="http://localhost:11434", alias="DEFAULT_EMBEDDING_BASE_URL")
    default_embedding_model: str = Field(default="qwen3-embedding:0.6b", alias="DEFAULT_EMBEDDING_MODEL")
    default_vector_store_url: str = Field(default="", alias="DEFAULT_VECTOR_STORE_URL")

    @field_validator("data_dir")
    @classmethod
    def _anchor_data_dir(cls, v: Path) -> Path:
        # Relative paths in .env are relative to the project root, not to whichever
        # directory a command happens to be run from.
        return v if v.is_absolute() or str(v) == ":memory:" else (PROJECT_ROOT / v).resolve()

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'gms.db').as_posix()}"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def vector_dir(self) -> Path:
        return self.data_dir / "vectors"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
