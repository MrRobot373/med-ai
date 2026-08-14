"""Authentication service — the only place that touches `users`/`sessions` directly.

Deliberately framework-agnostic (no FastAPI imports): API-layer concerns (cookies,
HTTP status codes) live in app/auth/dependencies.py and app/api/auth.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.auth.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.config.settings import Settings
from app.models.session import Session as SessionModel
from app.models.user import User


@dataclass
class IssuedSession:
    raw_token: str
    expires_at: datetime


def authenticate_user(db: DbSession, email: str, password: str) -> User | None:
    """Returns the user only if the email exists, the account is active, AND the
    password matches. Callers must use one generic error message regardless of which
    of those failed — distinguishing them in the response lets an attacker enumerate
    valid emails."""
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not user.active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_session(db: DbSession, user: User, settings: Settings, user_agent: str | None) -> IssuedSession:
    raw_token = generate_session_token()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.session_timeout_minutes)

    db.add(
        SessionModel(
            user_id=user.id,
            token_hash=hash_session_token(raw_token),
            expires_at=expires_at,
            user_agent=(user_agent or "")[:255] or None,
        )
    )
    user.last_login_at = datetime.now(UTC)
    db.commit()

    return IssuedSession(raw_token=raw_token, expires_at=expires_at)


def get_user_by_session_token(db: DbSession, raw_token: str) -> User | None:
    """Validates the session server-side against `expires_at`/`revoked_at` — the
    cookie's own Max-Age is a client-side convenience only, never trusted alone."""
    token_hash = hash_session_token(raw_token)
    session = db.scalar(select(SessionModel).where(SessionModel.token_hash == token_hash))
    if session is None:
        return None
    if session.revoked_at is not None:
        return None
    if _as_aware_utc(session.expires_at) < datetime.now(UTC):
        return None

    user = db.get(User, session.user_id)
    if user is None or not user.active:
        return None
    return user


def revoke_session(db: DbSession, raw_token: str) -> bool:
    token_hash = hash_session_token(raw_token)
    session = db.scalar(select(SessionModel).where(SessionModel.token_hash == token_hash))
    if session is None or session.revoked_at is not None:
        return False
    session.revoked_at = datetime.now(UTC)
    db.commit()
    return True


def _as_aware_utc(value: datetime) -> datetime:
    """SQLite loses tzinfo on round-trip even for TIMESTAMP(timezone=True) columns —
    values read back are naive but were always written as UTC, so reattach tzinfo
    rather than comparing a naive and an aware datetime (which raises TypeError)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


__all__ = [
    "IssuedSession",
    "authenticate_user",
    "create_session",
    "get_user_by_session_token",
    "hash_password",
    "revoke_session",
]
