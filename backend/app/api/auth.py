from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import func, select

from app.api.deps import DB, AdminUser, CurrentUser, client_ip, mfa_required_for
from app.core import passwords, totp
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    decrypt_secret,
    encrypt_secret,
    hash_password,
    hash_token,
    new_session_token,
    verify_password,
)
from app.models import User, UserSession
from app.schemas.common import (
    LoginIn,
    MfaDisableIn,
    MfaEnableIn,
    MfaVerifyIn,
    PasswordIn,
    ProfileIn,
    ResetPasswordIn,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.services import audit, runtime_config
from app.services import branches as branches_service
from app.services.rate_limit import login_limiter

router = APIRouter(prefix="/api", tags=["auth"])

PREFERENCE_KEYS = {
    "theme",
    "accent",
    "density",
    "radius",
    "font_scale",
    "sidebar_collapsed",
    "reduce_motion",
    "chat_show_trace",
    "default_landing",
    "font_family",
    "contrast",
    "branch_id",
}

MFA_TOKEN_MINUTES = 5
_TOO_MANY = "Too many sign-in attempts. Please wait a few minutes and try again."


# ---- helpers ----------------------------------------------------------------
def user_out(user: User, db) -> UserOut:
    out = UserOut.model_validate(user)
    out.mfa_required = mfa_required_for(user, db)
    out.has_signature = bool(user.signature_data_url)
    options = branches_service.accessible(db, user)
    out.branches = [{"id": b.id, "name": b.name, "code": b.code} for b in options]
    out.branch_id = branches_service.active(db, user).id
    return out


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _sign(payload: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    mac = hmac.new(get_settings().secret_key.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{mac}"


def _unsign(token: str) -> dict | None:
    try:
        body, mac = token.rsplit(".", 1)
        good = hmac.new(get_settings().secret_key.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, good):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        return payload if payload.get("exp", 0) > _now().timestamp() else None
    except Exception:
        return None


def _open_session(user: User, request: Request, response: Response, db) -> None:
    s = get_settings()
    token = new_session_token()
    timeout = runtime_config.load(db).security.session_timeout_minutes
    now = _now()
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=now + timedelta(minutes=timeout),
            user_agent=(request.headers.get("user-agent") or "")[:300],
            ip=client_ip(request),
        )
    )
    user.last_login_at = now
    user.failed_attempts = 0
    user.locked_until = None
    db.commit()
    response.set_cookie(
        s.session_cookie_name,
        token,
        httponly=True,
        samesite="lax",
        secure=s.cookie_secure,
        max_age=timeout * 60,
        path="/",
    )
    audit.record(db, user, "auth.login", "Signed in", ip=client_ip(request))


def _fail(user: User, db, request: Request, why: str) -> None:
    """Counts a failed second-step or password attempt and locks the account after too many."""
    cfg = runtime_config.load(db).security
    user.failed_attempts = (user.failed_attempts or 0) + 1
    locked = user.failed_attempts >= cfg.max_failed_attempts
    if locked:
        user.locked_until = _now() + timedelta(minutes=cfg.lockout_minutes)
        user.failed_attempts = 0
    db.commit()
    audit.record(
        db,
        user,
        "auth.locked" if locked else "auth.login_failed",
        f"{why}; account locked for {cfg.lockout_minutes} minutes" if locked else why,
        ip=client_ip(request),
        outcome="failure",
    )


def _revoke_sessions(user: User, db, *, keep: str | None = None) -> int:
    n = 0
    for sess in list(user.sessions):
        if keep and sess.id == keep:
            continue
        db.delete(sess)
        n += 1
    return n


# ---- sign-in ----------------------------------------------------------------
@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response, db: DB):
    s = get_settings()
    email = body.email.strip().lower()
    key = f"{email}|{client_ip(request)}"
    if not login_limiter.hit(key, s.login_rate_limit_attempts, s.login_rate_limit_window_seconds):
        raise HTTPException(429, _TOO_MANY)
    user = db.scalars(select(User).where(func.lower(User.email) == email)).first()
    if user is not None and user.locked_until and _aware(user.locked_until) > _now():
        audit.record(
            db, user, "auth.login_blocked", "Sign-in attempt while locked", ip=client_ip(request), outcome="failure"
        )
        raise HTTPException(429, _TOO_MANY)
    if user is None or not verify_password(body.password, user.password_hash):
        if user is None:
            audit.record(
                db, None, "auth.login_failed", f"Failed sign-in for {email}", ip=client_ip(request), outcome="failure"
            )
        else:
            _fail(user, db, request, f"Failed sign-in for {email}")
        raise HTTPException(401, "Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(403, "This account has been deactivated. Contact your administrator.")
    login_limiter.reset(key)
    if user.mfa_enabled:
        token = _sign(
            {
                "uid": user.id,
                "exp": (_now() + timedelta(minutes=MFA_TOKEN_MINUTES)).timestamp(),
                "n": secrets.token_hex(4),
            }
        )
        return {"mfa_required": True, "mfa_token": token}
    _open_session(user, request, response, db)
    return user_out(user, db)


@router.post("/auth/mfa/verify")
def mfa_verify(body: MfaVerifyIn, request: Request, response: Response, db: DB):
    payload = _unsign(body.mfa_token)
    user = db.get(User, payload["uid"]) if payload else None
    if user is None or not user.mfa_enabled or not user.is_active:
        raise HTTPException(401, "This sign-in has expired. Start again.")
    s = get_settings()
    if not login_limiter.hit(
        f"mfa|{user.id}|{client_ip(request)}", s.login_rate_limit_attempts, s.login_rate_limit_window_seconds
    ):
        raise HTTPException(429, _TOO_MANY)
    if user.locked_until and _aware(user.locked_until) > _now():
        raise HTTPException(429, _TOO_MANY)
    code = body.code.strip()
    secret = decrypt_secret(user.mfa_secret or "", s.secret_key)
    step = totp.verify(secret, code, last_step=user.mfa_last_step) if secret else None
    if step is not None:
        user.mfa_last_step = step
    else:
        digest = totp.hash_recovery(code)
        recovery = list(user.mfa_recovery or [])
        if digest in recovery:
            recovery.remove(digest)
            user.mfa_recovery = recovery
            audit.record(
                db,
                user,
                "auth.mfa_recovery_used",
                f"Recovery code used ({len(recovery)} left)",
                ip=client_ip(request),
                commit=False,
            )
        else:
            _fail(user, db, request, "Wrong two-step verification code")
            raise HTTPException(401, "That code is not correct.")
    _open_session(user, request, response, db)
    return user_out(user, db)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: DB):
    s = get_settings()
    token = request.cookies.get(s.session_cookie_name)
    if token:
        sess = db.scalars(select(UserSession).where(UserSession.token_hash == hash_token(token))).first()
        if sess:
            user = sess.user
            db.delete(sess)
            db.commit()
            audit.record(db, user, "auth.logout", "Signed out", ip=client_ip(request))
    response.delete_cookie(s.session_cookie_name, path="/")


@router.get("/auth/me", response_model=UserOut)
def me(user: CurrentUser, db: DB):
    return user_out(user, db)


@router.patch("/auth/me", response_model=UserOut)
def update_me(body: ProfileIn, user: CurrentUser, db: DB):
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    db.commit()
    return user_out(user, db)


@router.put("/auth/me/preferences", response_model=UserOut)
def update_preferences(body: dict, user: CurrentUser, db: DB):
    prefs = dict(user.preferences or {})
    for k, v in body.items():
        if k in PREFERENCE_KEYS:
            prefs[k] = v
    user.preferences = prefs
    db.commit()
    return user_out(user, db)


@router.post("/auth/me/password", status_code=204)
def change_password(body: PasswordIn, user: CurrentUser, db: DB, request: Request):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect.")
    cfg = runtime_config.load(db).security
    if body.new_password == body.current_password:
        raise AppError("Choose a password you have not used just now.", status_code=422, code="weak_password")
    passwords.check(body.new_password, min_length=cfg.min_password_length, email=user.email, name=user.full_name)
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    user.password_changed_at = _now()
    revoked = _revoke_sessions(user, db, keep=getattr(request.state, "session_id", None))
    db.commit()
    audit.record(
        db,
        user,
        "auth.password_change",
        f"Changed own password; {revoked} other session(s) signed out",
        ip=client_ip(request),
    )


@router.get("/auth/me/signature")
def my_signature(user: CurrentUser):
    return {"data_url": user.signature_data_url}


@router.put("/auth/me/signature", status_code=204)
def set_signature(body: dict, request: Request, user: CurrentUser, db: DB):
    url = body.get("data_url")
    if url is not None and (
        not isinstance(url, str) or not url.startswith("data:image/png;base64,") or len(url) > 400_000
    ):
        raise AppError("Use a PNG image under 300 KB.", status_code=422)
    user.signature_data_url = url or None
    db.commit()
    audit.record(
        db,
        user,
        "user.signature",
        "Updated own signature image" if url else "Removed own signature image",
        ip=client_ip(request),
    )


# ---- sessions ---------------------------------------------------------------
@router.get("/auth/sessions")
def my_sessions(request: Request, user: CurrentUser, db: DB):
    current = getattr(request.state, "session_id", None)
    rows = db.scalars(
        select(UserSession).where(UserSession.user_id == user.id).order_by(UserSession.last_seen_at.desc())
    )
    return [
        {
            "id": s.id,
            "created_at": s.created_at,
            "last_seen_at": s.last_seen_at,
            "user_agent": s.user_agent,
            "ip": s.ip,
            "current": s.id == current,
        }
        for s in rows
    ]


@router.delete("/auth/sessions/{session_id}", status_code=204)
def revoke_session(session_id: str, request: Request, user: CurrentUser, db: DB):
    sess = db.get(UserSession, session_id)
    if sess is None or sess.user_id != user.id:
        raise HTTPException(404, "Session not found")
    db.delete(sess)
    db.commit()
    audit.record(db, user, "auth.session_revoked", "Signed out a device", ip=client_ip(request))


@router.post("/auth/sessions/revoke-others")
def revoke_other_sessions(request: Request, user: CurrentUser, db: DB):
    n = _revoke_sessions(user, db, keep=getattr(request.state, "session_id", None))
    db.commit()
    audit.record(db, user, "auth.session_revoked", f"Signed out {n} other device(s)", ip=client_ip(request))
    return {"revoked": n}


# ---- two-step verification --------------------------------------------------
@router.post("/auth/mfa/setup")
def mfa_setup(request: Request, user: CurrentUser, db: DB):
    if user.mfa_enabled:
        raise HTTPException(409, "Two-step verification is already on. Turn it off first to set it up again.")
    s = get_settings()
    secret = totp.new_secret()
    user.mfa_secret = encrypt_secret(secret, s.secret_key)
    db.commit()
    issuer = runtime_config.load(db).branding.product_name
    return {"secret": secret, "otpauth_uri": totp.provisioning_uri(secret, user.email, issuer)}


@router.post("/auth/mfa/enable")
def mfa_enable(body: MfaEnableIn, request: Request, user: CurrentUser, db: DB):
    s = get_settings()
    secret = decrypt_secret(user.mfa_secret or "", s.secret_key) if user.mfa_secret else None
    if not secret:
        raise HTTPException(400, "Start the setup first.")
    step = totp.verify(secret, body.code)
    if step is None:
        raise HTTPException(400, "That code is not correct. Check the time on your phone and try again.")
    codes = totp.new_recovery_codes()
    user.mfa_enabled = True
    user.mfa_last_step = step
    user.mfa_recovery = [totp.hash_recovery(c) for c in codes]
    revoked = _revoke_sessions(user, db, keep=getattr(request.state, "session_id", None))
    db.commit()
    audit.record(
        db,
        user,
        "auth.mfa_enabled",
        f"Turned on two-step verification; {revoked} other session(s) signed out",
        ip=client_ip(request),
    )
    return {"recovery_codes": codes}


@router.post("/auth/mfa/disable", status_code=204)
def mfa_disable(body: MfaDisableIn, request: Request, user: CurrentUser, db: DB):
    if mfa_required_for(user, db):
        raise HTTPException(403, "Your role requires two-step verification, so it cannot be turned off.")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(400, "Password is incorrect.")
    s = get_settings()
    secret = decrypt_secret(user.mfa_secret or "", s.secret_key) if user.mfa_secret else None
    ok = bool(secret and totp.verify(secret, body.code, last_step=user.mfa_last_step) is not None)
    if not ok and totp.hash_recovery(body.code) not in (user.mfa_recovery or []):
        raise HTTPException(400, "That code is not correct.")
    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_recovery = []
    user.mfa_last_step = None
    db.commit()
    audit.record(db, user, "auth.mfa_disabled", "Turned off two-step verification", ip=client_ip(request))


# ---- User administration ----------------------------------------------------
@router.get("/users", response_model=list[UserOut])
def list_users(_: AdminUser, db: DB):
    return [user_out(u, db) for u in db.scalars(select(User).order_by(User.full_name))]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, admin: AdminUser, db: DB):
    email = body.email.strip().lower()
    if db.scalars(select(User).where(func.lower(User.email) == email)).first():
        raise HTTPException(409, "A user with this email already exists.")
    from app.services import licensing

    licensing.assert_can_add_user(db, body.role)
    cfg = runtime_config.load(db).security
    passwords.check(body.password, min_length=cfg.min_password_length, email=email, name=body.full_name)
    user = User(
        email=email,
        full_name=body.full_name,
        title=body.title,
        specialty=body.specialty,
        role=body.role,
        password_hash=hash_password(body.password),
        must_change_password=True,  # the administrator knows this password; the person chooses their own
        password_changed_at=_now(),
    )
    db.add(user)
    db.flush()
    branches_service.ensure_membership(db, user)
    db.commit()
    audit.record(db, admin, "user.create", f"Created user {email} ({body.role})", entity_type="user", entity_id=user.id)
    return user_out(user, db)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: str, body: UserUpdate, admin: AdminUser, db: DB):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    changes = body.model_dump(exclude_unset=True)
    branch_ids = changes.pop("branch_ids", None)
    if user.id == admin.id and (changes.get("role", "admin") != "admin" or changes.get("is_active") is False):
        raise HTTPException(400, "You can't remove your own administrator access.")
    from app.services import licensing

    new_role = changes.get("role", user.role)
    reactivating = changes.get("is_active") is True and not user.is_active
    if reactivating or new_role != user.role:
        licensing.assert_can_add_user(db, new_role, excluding=user.id)
    for k, v in changes.items():
        setattr(user, k, v)
    if branch_ids is not None:
        branches_service.assign(db, user, branch_ids)
        changes["branch_ids"] = branch_ids
    if changes.get("is_active") is False:
        _revoke_sessions(user, db)
    db.commit()
    audit.record(
        db, admin, "user.update", f"Updated user {user.email}", entity_type="user", entity_id=user.id, details=changes
    )
    return user_out(user, db)


@router.post("/users/{user_id}/reset-password", status_code=204)
def reset_password(user_id: str, body: ResetPasswordIn, admin: AdminUser, db: DB):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    cfg = runtime_config.load(db).security
    passwords.check(body.new_password, min_length=cfg.min_password_length, email=user.email, name=user.full_name)
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = True
    user.password_changed_at = _now()
    user.failed_attempts = 0
    user.locked_until = None
    _revoke_sessions(user, db)
    db.commit()
    audit.record(
        db, admin, "user.password_reset", f"Reset password for {user.email}", entity_type="user", entity_id=user.id
    )


@router.post("/users/{user_id}/unlock", status_code=204)
def unlock_user(user_id: str, admin: AdminUser, db: DB):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    user.failed_attempts = 0
    user.locked_until = None
    db.commit()
    login_limiter.reset_prefix(f"{user.email.lower()}|")
    audit.record(db, admin, "user.unlock", f"Unlocked {user.email}", entity_type="user", entity_id=user.id)


@router.post("/users/{user_id}/mfa/reset", status_code=204)
def reset_user_mfa(user_id: str, admin: AdminUser, db: DB):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_recovery = []
    user.mfa_last_step = None
    _revoke_sessions(user, db)
    db.commit()
    audit.record(
        db,
        admin,
        "user.mfa_reset",
        f"Reset two-step verification for {user.email}",
        entity_type="user",
        entity_id=user.id,
    )


@router.get("/branding")
def branding(db: DB):
    """Public: the sign-in page needs the product name, logo and default theme."""
    b = runtime_config.load(db).branding
    return b.model_dump()
