"""Auth endpoints — spec §104: POST /api/auth/login, POST /api/auth/logout, GET /api/auth/me.

Session token travels only as an HttpOnly cookie — never in the response body, a URL
parameter, or a header the frontend JS could read (spec §17 "no tokens in URL
parameters"). The frontend learns who's logged in solely via GET /api/auth/me.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import DbDep, SettingsDep
from app.audit.service import record as record_audit
from app.auth.dependencies import CurrentUser
from app.auth.rate_limit import login_rate_limiter
from app.auth.service import (
    authenticate_user,
    create_session,
    get_user_by_session_token,
    revoke_session,
)
from app.logging import get_logger
from app.models.audit_log import AuditAction, AuditOutcome
from app.schemas.auth import LoginRequest, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = get_logger(__name__)


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, request: Request, response: Response, db: DbDep, settings: SettingsDep) -> UserOut:
    client_ip = request.client.host if request.client else "unknown"
    rate_limit_key = f"{client_ip}:{payload.email.lower()}"

    if login_rate_limiter.is_blocked(rate_limit_key, settings):
        # Never logged with the password; email is logged so a real lockout is
        # diagnosable without exposing what the attempted password was (spec §94).
        logger.warning("Login rate limit exceeded for %s", rate_limit_key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait a few minutes and try again.",
        )

    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        login_rate_limiter.record_attempt(rate_limit_key)
        # Logged with the attempted email (not a real user_id — the email may not
        # belong to any account) so an admin reviewing the audit log can still spot a
        # brute-force pattern, without the login response itself revealing anything
        # more than spec §17/§92's identical error message already does.
        record_audit(
            db, AuditAction.LOGIN, user_email=payload.email.strip().lower(), outcome=AuditOutcome.FAILURE
        )
        # Deliberately identical message whether the email doesn't exist, the account
        # is inactive, or the password is wrong — distinguishing them lets an attacker
        # enumerate valid accounts (spec §17/§92).
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    login_rate_limiter.reset(rate_limit_key)
    issued = create_session(db, user, settings, user_agent=request.headers.get("user-agent"))
    record_audit(db, AuditAction.LOGIN, user=user, outcome=AuditOutcome.SUCCESS)

    response.set_cookie(
        key=settings.session_cookie_name,
        value=issued.raw_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_timeout_minutes * 60,
        path="/",
    )

    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DbDep, settings: SettingsDep) -> None:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token:
        # Resolved before revoking (a revoked session no longer resolves to a user) —
        # best-effort only: an already-expired/invalid token still 204s (logout is
        # never an error), it just has no identifiable user left to log.
        user = get_user_by_session_token(db, raw_token)
        revoke_session(db, raw_token)
        if user is not None:
            record_audit(db, AuditAction.LOGOUT, user=user, outcome=AuditOutcome.SUCCESS)
    response.delete_cookie(key=settings.session_cookie_name, path="/")


@router.get("/me", response_model=UserOut)
def me(current_user: CurrentUser) -> UserOut:
    return UserOut.model_validate(current_user)
