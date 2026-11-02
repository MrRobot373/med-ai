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
    upload_max_pdf_pages: int = Field(default=300, alias="UPLOAD_MAX_PDF_PAGES")
    upload_max_image_pixels: int = Field(default=100_000_000, alias="UPLOAD_MAX_IMAGE_PIXELS")
    login_rate_limit_attempts: int = Field(default=8, alias="LOGIN_RATE_LIMIT_ATTEMPTS")
    login_rate_limit_window_seconds: int = Field(default=600, alias="LOGIN_RATE_LIMIT_WINDOW_SECONDS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    timezone: str = Field(default="Asia/Kolkata", alias="APP_TIMEZONE")  # clinic-local dates on printed documents

    # Protection of data at rest and of uploads.
    data_encryption_key: str | None = Field(default=None, alias="DATA_ENCRYPTION_KEY")
    encryption_at_rest_attested: bool = Field(default=False, alias="ENCRYPTION_AT_REST_ATTESTED")
    backup_encryption_key: str | None = Field(default=None, alias="BACKUP_ENCRYPTION_KEY")
    backup_dir_override: Path | None = Field(default=None, alias="BACKUP_DIR")
    allow_insecure_http: bool = Field(default=False, alias="ALLOW_INSECURE_HTTP")
    clamav_host: str | None = Field(default=None, alias="CLAMAV_HOST")
    clamav_port: int = Field(default=3310, alias="CLAMAV_PORT")
    clamav_fail_closed: bool = Field(default=True, alias="CLAMAV_FAIL_CLOSED")

    # First-run administrator. Created only when the users table is empty.
    bootstrap_admin_email: str = Field(default="admin@lifecaremedico.in", alias="BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_password: str = Field(default="Admin@2026", alias="BOOTSTRAP_ADMIN_PASSWORD")
    bootstrap_admin_name: str = Field(default="Vikram Shah", alias="BOOTSTRAP_ADMIN_NAME")

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
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def production_problems(self) -> list[str]:
        """Settings that must not reach a production server. Empty outside production."""
        if not self.is_production:
            return []
        problems = []
        if self.secret_key in ("", "change-me-in-production") or len(self.secret_key) < 32:
            problems.append("APP_SECRET_KEY must be set to a random value of at least 32 characters.")
        return problems

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'gms.db').as_posix()}"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def backup_dir(self) -> Path:
        return self.backup_dir_override or (self.data_dir / "backups")

    @property
    def vector_dir(self) -> Path:
        return self.data_dir / "vectors"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
