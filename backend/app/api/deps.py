from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_token
from app.db import get_db
from app.models import User, UserSession
from app.services import runtime_config

DB = Annotated[Session, Depends(get_db)]


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def current_user(request: Request, db: DB) -> User:
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token:
        raise HTTPException(401, "Not signed in")
    session = db.query(UserSession).filter(UserSession.token_hash == hash_token(token)).one_or_none()
    now = datetime.now(UTC)
    if session is None or _aware(session.expires_at) < now:
        raise HTTPException(401, "Session expired — please sign in again")
    user = session.user
    if not user.is_active:
        raise HTTPException(401, "Account is deactivated")
    # Sliding expiry, written at most once a minute.
    if (now - _aware(session.last_seen_at)).total_seconds() > 60:
        timeout = runtime_config.load(db).security.session_timeout_minutes
        session.last_seen_at = now
        session.expires_at = now + timedelta(minutes=timeout)
        db.commit()
    request.state.user = user
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_roles(*roles: str):
    def dep(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(403, "You don't have permission to do this")
        return user

    return dep


AdminUser = Annotated[User, Depends(require_roles("admin"))]
WriteUser = Annotated[User, Depends(require_roles("admin", "clinician"))]


def ai_user(user: CurrentUser, db: DB) -> User:
    if user.role == "viewer" and not runtime_config.load(db).security.allow_viewer_ai:
        raise HTTPException(403, "AI features are disabled for viewer accounts")
    return user


AIUser = Annotated[User, Depends(ai_user)]


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
