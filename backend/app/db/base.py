"""SQLAlchemy 2.x declarative base.

All ORM models (across every phase — users/sessions now, patients/encounters/reports/etc.
from Phase 04 onward) inherit from `Base` so Alembic autogenerate can discover them via a
single metadata object. Foreign-key enforcement is turned on for SQLite explicitly, since
SQLite ignores FK constraints unless PRAGMA foreign_keys=ON is set per-connection.
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    """SQLite requires this pragma on every connection; other backends ignore it safely."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    except Exception:  # noqa: BLE001, S110 - intentionally broad: non-SQLite DBAPI
        # connections don't support this pragma and must not crash app startup over it.
        pass
    finally:
        cursor.close()
