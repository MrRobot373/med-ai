from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import hash_token
from app.db import get_db
from app.models import User, UserSession
from app.services import runtime_config

DB = Annotated[Session, Depends(get_db)]


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


# Calls that must work while a person still has to change their password or enrol an authenticator.
_ALLOWED_WHILE_PENDING = ("/api/auth/", "/api/branding")


def mfa_required_for(user: User, db: Session) -> bool:
    """True when this person's role must use a second factor (enforced in production)."""
    if not get_settings().is_production:
        return False
    return user.role in runtime_config.load(db).security.mfa_required_roles


def current_user(request: Request, db: DB) -> User:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(401, "Not signed in")
    session = db.query(UserSession).filter(UserSession.token_hash == hash_token(token)).one_or_none()
    now = datetime.now(UTC)
    if session is None or _aware(session.expires_at) < now:
        raise HTTPException(401, "Session expired — please sign in again")
    cfg = runtime_config.load(db).security
    if now - _aware(session.created_at) > timedelta(hours=cfg.session_absolute_hours):
        db.delete(session)
        db.commit()
        raise HTTPException(401, "Your session has reached its maximum length — please sign in again")
    user = session.user
    if not user.is_active:
        raise HTTPException(401, "Account is deactivated")
    # Sliding expiry, written at most once a minute.
    if (now - _aware(session.last_seen_at)).total_seconds() > 60:
        session.last_seen_at = now
        session.expires_at = now + timedelta(minutes=cfg.session_timeout_minutes)
        db.commit()
    request.state.user = user
    request.state.session_id = session.id
    if not request.url.path.startswith(_ALLOWED_WHILE_PENDING):
        if user.must_change_password:
            raise AppError(
                "You must choose a new password before continuing.", status_code=403, code="password_change_required"
            )
        if mfa_required_for(user, db) and not user.mfa_enabled:
            raise AppError(
                "Your role requires two-step verification. Set it up to continue.",
                status_code=403,
                code="mfa_enrolment_required",
            )
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_roles(*roles: str):
    def dep(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(403, "You don't have permission to do this")
        return user

    return dep


AdminUser = Annotated[User, Depends(require_roles("admin"))]
# Clinical writes (notes, prescriptions, results, problems…)
WriteUser = Annotated[User, Depends(require_roles("admin", "clinician"))]
# Reading clinical content — everyone except the front desk
ClinicalUser = Annotated[User, Depends(require_roles("admin", "clinician", "viewer"))]
# Registration, report uploads and the day list — clinical staff and the front desk
StaffUser = Annotated[User, Depends(require_roles("admin", "clinician", "front_desk"))]


def ai_user(user: CurrentUser, db: DB) -> User:
    if user.role == "front_desk":
        raise HTTPException(403, "AI features are available to clinical staff only")
    if user.role == "viewer" and not runtime_config.load(db).security.allow_viewer_ai:
        raise HTTPException(403, "AI features are disabled for viewer accounts")
    return user


AIUser = Annotated[User, Depends(ai_user)]


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
