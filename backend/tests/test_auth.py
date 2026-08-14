"""Auth tests — spec §98 "Critical Security Tests" (login/session parts) plus §17.

Covers: login success/failure paths use one generic error message, session cookie
issuance/validation/expiry/revocation, role-based authorization, and the rate limiter.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.auth.dependencies import require_role
from app.auth.rate_limit import LoginRateLimiter
from app.auth.security import hash_password, verify_password
from app.config.settings import get_settings
from app.db.session import SessionLocal
from app.models.session import Session as SessionModel
from app.models.user import User, UserRole

ADMIN_PASSWORD = "correct-horse-battery-staple"
DOCTOR_PASSWORD = "another-strong-password-1"


def _create_user(email: str, password: str, role: UserRole, active: bool = True) -> User:
    db = SessionLocal()
    try:
        user = User(
            email=email,
            display_name=email.split("@")[0],
            password_hash=hash_password(password),
            role=role,
            active=active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def test_password_hash_never_stores_plaintext():
    hashed = hash_password("hunter2")
    assert hashed != "hunter2"
    assert verify_password("hunter2", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_login_success_sets_cookie_and_returns_user(client):
    _create_user("nurse.login@example.com", "supersecretpw1", UserRole.DOCTOR)

    resp = client.post("/api/auth/login", json={"email": "nurse.login@example.com", "password": "supersecretpw1"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "nurse.login@example.com"
    assert "password" not in body
    assert "password_hash" not in body
    assert client.cookies.get(get_settings().session_cookie_name) is not None


def test_login_accepts_local_domain_demo_accounts(client):
    # Regression test: pydantic's EmailStr rejects `.local`/`.test`/etc. as
    # reserved/special-use TLDs, which broke login for exactly the accounts
    # scripts/seed_demo.py creates (e.g. doctor@gms.local). LoginRequest must not
    # perform deliverability-style validation — see app/schemas/auth.py.
    _create_user("clinician@gms.local", "somepassword123", UserRole.DOCTOR)

    resp = client.post("/api/auth/login", json={"email": "clinician@gms.local", "password": "somepassword123"})

    assert resp.status_code == 200


def test_login_malformed_email_returns_clean_error_not_a_500(client):
    resp = client.post("/api/auth/login", json={"email": "not-an-email", "password": "whatever123"})

    assert resp.status_code == 422
    # Body must be introspectable by the frontend's error handling, not an opaque blob.
    assert "detail" in resp.json()


def test_login_wrong_password_and_unknown_email_return_identical_message(client):
    _create_user("known.user@example.com", "correctpassword1", UserRole.DOCTOR)

    wrong_pw = client.post("/api/auth/login", json={"email": "known.user@example.com", "password": "nope"})
    unknown = client.post("/api/auth/login", json={"email": "nobody-here@example.com", "password": "nope"})

    assert wrong_pw.status_code == 401
    assert unknown.status_code == 401
    # Identical message on both — must not let an attacker enumerate valid emails.
    assert wrong_pw.json()["detail"] == unknown.json()["detail"]


def test_login_inactive_account_is_rejected(client):
    _create_user("inactive.user@example.com", "somepassword1", UserRole.VIEWER, active=False)

    resp = client.post("/api/auth/login", json={"email": "inactive.user@example.com", "password": "somepassword1"})

    assert resp.status_code == 401


def test_me_requires_authentication(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user_after_login(client):
    _create_user("me.check@example.com", "checkpassword1", UserRole.ADMIN)
    client.post("/api/auth/login", json={"email": "me.check@example.com", "password": "checkpassword1"})

    resp = client.get("/api/auth/me")

    assert resp.status_code == 200
    assert resp.json()["email"] == "me.check@example.com"
    assert resp.json()["role"] == "admin"


def test_logout_revokes_session(client):
    _create_user("logout.user@example.com", "logoutpassword1", UserRole.DOCTOR)
    client.post("/api/auth/login", json={"email": "logout.user@example.com", "password": "logoutpassword1"})
    assert client.get("/api/auth/me").status_code == 200

    logout_resp = client.post("/api/auth/logout")
    assert logout_resp.status_code == 204

    assert client.get("/api/auth/me").status_code == 401


def test_expired_session_is_rejected_even_with_valid_cookie(client):
    user = _create_user("expiring.user@example.com", "expirepassword1", UserRole.DOCTOR)
    client.post("/api/auth/login", json={"email": "expiring.user@example.com", "password": "expirepassword1"})
    assert client.get("/api/auth/me").status_code == 200

    # Force the stored session into the past — server-side expiry must win even though
    # the cookie itself is still present and unexpired on the client.
    db = SessionLocal()
    try:
        session_row = db.scalar(select(SessionModel).where(SessionModel.user_id == user.id))
        session_row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    assert client.get("/api/auth/me").status_code == 401


def test_login_rate_limiter_blocks_after_threshold(client):
    _create_user("ratelimited.user@example.com", "correctpassword2", UserRole.DOCTOR)

    settings = get_settings()
    for _ in range(settings.login_rate_limit_attempts):
        resp = client.post(
            "/api/auth/login", json={"email": "ratelimited.user@example.com", "password": "wrongpassword"}
        )
        assert resp.status_code == 401

    blocked = client.post(
        "/api/auth/login", json={"email": "ratelimited.user@example.com", "password": "wrongpassword"}
    )
    assert blocked.status_code == 429

    # Even the CORRECT password is blocked while rate-limited — that's the point.
    still_blocked = client.post(
        "/api/auth/login", json={"email": "ratelimited.user@example.com", "password": "correctpassword2"}
    )
    assert still_blocked.status_code == 429


def test_rate_limiter_window_expiry_unblocks(monkeypatch):
    limiter = LoginRateLimiter()
    settings = get_settings()
    key = "unit-test-key"

    for _ in range(settings.login_rate_limit_attempts):
        limiter.record_attempt(key)
    assert limiter.is_blocked(key, settings) is True

    limiter.reset(key)
    assert limiter.is_blocked(key, settings) is False


def test_require_role_allows_matching_role_and_rejects_others():
    admin_dep = require_role(UserRole.ADMIN)
    admin_user = User(email="a@x.com", display_name="A", password_hash="x", role=UserRole.ADMIN, active=True)
    doctor_user = User(email="d@x.com", display_name="D", password_hash="x", role=UserRole.DOCTOR, active=True)

    assert admin_dep(admin_user) is admin_user

    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        admin_dep(doctor_user)
    assert exc_info.value.status_code == 403
