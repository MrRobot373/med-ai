"""Engine/session factory + FastAPI dependency.

A single module-level engine is created from `Settings.database_url`. SQLite needs
`check_same_thread=False` because FastAPI may service a request on a different thread
than the one that created the connection pool entry; sessions themselves are still
scoped per-request via the `get_db` dependency, so this does not introduce cross-request
sharing.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings

_settings = get_settings()

_connect_args = {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}

engine = create_engine(_settings.database_url, connect_args=_connect_args, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_reachable() -> tuple[bool, str | None]:
    """Real connectivity check for the health endpoint — opens a connection and runs a
    trivial query rather than assuming SQLite is always available."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # noqa: BLE001 - health check must never raise
        return False, str(exc)
