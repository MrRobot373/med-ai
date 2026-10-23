from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import func, select

from app.api.deps import DB, AdminUser, CurrentUser, client_ip
from app.core.config import get_settings
from app.core.security import hash_password, hash_token, new_session_token, verify_password
from app.models import User, UserSession
from app.schemas.common import LoginIn, PasswordIn, ProfileIn, ResetPasswordIn, UserCreate, UserOut, UserUpdate
from app.services import audit, runtime_config
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
}


@router.post("/auth/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, db: DB):
    s = get_settings()
    email = body.email.strip().lower()
    key = f"{email}|{client_ip(request)}"
    if not login_limiter.hit(key, s.login_rate_limit_attempts, s.login_rate_limit_window_seconds):
        raise HTTPException(429, "Too many sign-in attempts. Please wait a few minutes and try again.")
    user = db.scalars(select(User).where(func.lower(User.email) == email)).first()
    if user is None or not verify_password(body.password, user.password_hash):
        audit.record(
            db, None, "auth.login_failed", f"Failed sign-in for {email}", ip=client_ip(request), outcome="failure"
        )
        raise HTTPException(401, "Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(403, "This account has been deactivated. Contact your administrator.")
    login_limiter.reset(key)
    token = new_session_token()
    timeout = runtime_config.load(db).security.session_timeout_minutes
    now = datetime.now(UTC)
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
    return user


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
def me(user: CurrentUser):
    return user


@router.patch("/auth/me", response_model=UserOut)
def update_me(body: ProfileIn, user: CurrentUser, db: DB):
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    db.commit()
    return user


@router.put("/auth/me/preferences", response_model=UserOut)
def update_preferences(body: dict, user: CurrentUser, db: DB):
    prefs = dict(user.preferences or {})
    for k, v in body.items():
        if k in PREFERENCE_KEYS:
            prefs[k] = v
    user.preferences = prefs
    db.commit()
    return user


@router.post("/auth/me/password", status_code=204)
def change_password(body: PasswordIn, user: CurrentUser, db: DB, request: Request):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect.")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    audit.record(db, user, "auth.password_change", "Changed own password", ip=client_ip(request))


@router.get("/auth/sessions")
def my_sessions(user: CurrentUser, db: DB):
    rows = db.scalars(
        select(UserSession).where(UserSession.user_id == user.id).order_by(UserSession.last_seen_at.desc())
    )
    return [
        {"id": s.id, "created_at": s.created_at, "last_seen_at": s.last_seen_at, "user_agent": s.user_agent, "ip": s.ip}
        for s in rows
    ]


# ---- User administration ----------------------------------------------------
@router.get("/users", response_model=list[UserOut])
def list_users(_: AdminUser, db: DB):
    return db.scalars(select(User).order_by(User.full_name)).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, admin: AdminUser, db: DB):
    email = body.email.strip().lower()
    if db.scalars(select(User).where(func.lower(User.email) == email)).first():
        raise HTTPException(409, "A user with this email already exists.")
    user = User(
        email=email,
        full_name=body.full_name,
        title=body.title,
        specialty=body.specialty,
        role=body.role,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    audit.record(db, admin, "user.create", f"Created user {email} ({body.role})", entity_type="user", entity_id=user.id)
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: str, body: UserUpdate, admin: AdminUser, db: DB):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    changes = body.model_dump(exclude_unset=True)
    if user.id == admin.id and (changes.get("role", "admin") != "admin" or changes.get("is_active") is False):
        raise HTTPException(400, "You can't remove your own administrator access.")
    for k, v in changes.items():
        setattr(user, k, v)
    if changes.get("is_active") is False:
        for s in list(user.sessions):
            db.delete(s)
    db.commit()
    audit.record(
        db, admin, "user.update", f"Updated user {user.email}", entity_type="user", entity_id=user.id, details=changes
    )
    return user


@router.post("/users/{user_id}/reset-password", status_code=204)
def reset_password(user_id: str, body: ResetPasswordIn, admin: AdminUser, db: DB):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    user.password_hash = hash_password(body.new_password)
    for s in list(user.sessions):
        db.delete(s)
    db.commit()
    audit.record(
        db, admin, "user.password_reset", f"Reset password for {user.email}", entity_type="user", entity_id=user.id
    )


@router.get("/branding")
def branding(db: DB):
    """Public: the sign-in page needs the product name, logo and default theme."""
    b = runtime_config.load(db).branding
    return b.model_dump()
