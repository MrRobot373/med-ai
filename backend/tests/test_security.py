"""Two-step verification, lockout, password policy, sessions, headers, CSRF, audit chain, encryption, scanning."""

from __future__ import annotations

import socket
import struct
import threading

import pytest
from sqlalchemy import select

from app import db as app_db
from app.core import fileenc, passwords, totp
from app.core.config import get_settings
from app.models import AuditLog, User
from app.services import audit
from tests.conftest import create_patient, login, make_user

STRONG = "Blue-Heron-Walks-0914"


# ---- TOTP ------------------------------------------------------------------------------------------
def test_totp_matches_rfc6238_vectors():
    # RFC 6238 appendix B, SHA-1, secret "12345678901234567890", 6-digit truncation of the 8-digit values.
    import base64

    secret = base64.b32encode(b"12345678901234567890").decode().rstrip("=")
    assert totp.code_at(secret, 59 // 30) == "287082"
    assert totp.code_at(secret, 1111111109 // 30) == "081804"
    assert totp.code_at(secret, 2000000000 // 30) == "279037"


def test_totp_window_and_replay():
    s = totp.new_secret()
    now = 1_700_000_000
    step = now // 30
    code = totp.code_at(s, step)
    assert totp.verify(s, code, now=now) == step
    assert totp.verify(s, totp.code_at(s, step - 1), now=now) == step - 1  # one step of clock drift
    assert totp.verify(s, totp.code_at(s, step - 3), now=now) is None
    assert totp.verify(s, code, last_step=step, now=now) is None  # the same code cannot be used twice
    assert totp.verify(s, "12ab56", now=now) is None


# ---- password policy -------------------------------------------------------------------------------
def test_password_policy():
    assert not passwords.validate(STRONG, email="a@b.c")
    for weak in ("short1!", "Password@123", "aaaaaaaaaaaaaaaa", "abcdefghijklmnop", "Clinic@2026"):
        assert passwords.validate(weak), weak
    assert passwords.validate("rahul.menon-2026-xx", email="rahul.menon@lifecaremedico.in")  # contains own name


def test_weak_password_is_refused_when_creating_and_changing(admin):
    r = admin.post(
        "/api/users", json={"email": "n@test.local", "full_name": "New", "role": "viewer", "password": "Password@123"}
    )
    assert r.status_code == 422 and r.json()["code"] == "weak_password"
    r = admin.post("/api/auth/me/password", json={"current_password": "Admin@12345", "new_password": "short"})
    assert r.status_code == 422


def test_admin_created_users_must_change_password(admin, client):
    r = admin.post(
        "/api/users", json={"email": "n@test.local", "full_name": "New", "role": "clinician", "password": STRONG}
    )
    assert r.status_code == 201 and r.json()["must_change_password"] is True
    client.cookies.clear()
    assert client.post("/api/auth/login", json={"email": "n@test.local", "password": STRONG}).status_code == 200
    blocked = client.get("/api/patients")
    assert blocked.status_code == 403 and blocked.json()["code"] == "password_change_required"
    assert client.get("/api/auth/me").status_code == 200  # the account page still works
    new_pw = "Quiet-Orchard-Lamp-7731"
    assert (
        client.post("/api/auth/me/password", json={"current_password": STRONG, "new_password": new_pw}).status_code
        == 204
    )
    assert client.get("/api/patients").status_code == 200


# ---- lockout ---------------------------------------------------------------------------------------
def test_account_locks_after_repeated_failures_and_admin_can_unlock(client):
    make_user("doc@test.local", "clinician")
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "doc@test.local", "password": "wrong"}).status_code == 401
    locked = client.post("/api/auth/login", json={"email": "doc@test.local", "password": "Password@123"})
    assert locked.status_code == 429  # correct password, still locked
    login(client)  # admin
    uid = next(u["id"] for u in client.get("/api/users").json() if u["email"] == "doc@test.local")
    assert client.post(f"/api/users/{uid}/unlock").status_code == 204
    client.cookies.clear()
    from app.services import rate_limit

    rate_limit.login_limiter._hits.clear()
    assert (
        client.post("/api/auth/login", json={"email": "doc@test.local", "password": "Password@123"}).status_code == 200
    )


# ---- MFA flow --------------------------------------------------------------------------------------
def _enrol(c) -> tuple[str, list[str]]:
    setup = c.post("/api/auth/mfa/setup").json()
    secret = setup["secret"]
    assert setup["otpauth_uri"].startswith("otpauth://totp/")
    r = c.post("/api/auth/mfa/enable", json={"code": totp.code_at(secret, totp.current_step())})
    assert r.status_code == 200, r.text
    return secret, r.json()["recovery_codes"]


def test_mfa_login_flow_with_totp_and_recovery_code(client):
    make_user("doc@test.local", "clinician")
    login(client, "doc@test.local", "Password@123")
    secret, recovery = _enrol(client)
    assert len(recovery) == 10
    client.post("/api/auth/logout")

    r = client.post("/api/auth/login", json={"email": "doc@test.local", "password": "Password@123"})
    assert r.status_code == 200 and r.json()["mfa_required"] is True
    assert client.get("/api/auth/me").status_code == 401  # no session until the second step
    token = r.json()["mfa_token"]

    assert client.post("/api/auth/mfa/verify", json={"mfa_token": token, "code": "000000"}).status_code == 401
    step = totp.current_step()
    good = totp.code_at(secret, step + 1)  # a later step than the one used to enrol
    r = client.post("/api/auth/mfa/verify", json={"mfa_token": token, "code": good})
    assert r.status_code == 200 and r.json()["mfa_enabled"] is True
    assert client.get("/api/auth/me").status_code == 200
    client.post("/api/auth/logout")
    # the same code is not accepted twice
    token2 = client.post("/api/auth/login", json={"email": "doc@test.local", "password": "Password@123"}).json()[
        "mfa_token"
    ]
    assert client.post("/api/auth/mfa/verify", json={"mfa_token": token2, "code": good}).status_code == 401
    # a recovery code works once
    assert client.post("/api/auth/mfa/verify", json={"mfa_token": token2, "code": recovery[0]}).status_code == 200
    client.post("/api/auth/logout")
    token3 = client.post("/api/auth/login", json={"email": "doc@test.local", "password": "Password@123"}).json()[
        "mfa_token"
    ]
    assert client.post("/api/auth/mfa/verify", json={"mfa_token": token3, "code": recovery[0]}).status_code == 401


def test_mfa_token_cannot_be_forged_or_expired(client):
    make_user("doc@test.local", "clinician")
    login(client, "doc@test.local", "Password@123")
    _enrol(client)
    client.post("/api/auth/logout")
    token = client.post("/api/auth/login", json={"email": "doc@test.local", "password": "Password@123"}).json()[
        "mfa_token"
    ]
    body, mac = token.rsplit(".", 1)
    assert (
        client.post("/api/auth/mfa/verify", json={"mfa_token": body + ".00" + mac[2:], "code": "123456"}).status_code
        == 401
    )


def test_admin_can_reset_mfa_and_production_requires_it_for_admins(client, admin, monkeypatch):
    make_user("doc@test.local", "clinician")
    # production enforcement: an admin without a second factor is held at enrolment
    monkeypatch.setattr(get_settings(), "app_env", "production")
    r = admin.get("/api/patients")
    assert r.status_code == 403 and r.json()["code"] == "mfa_enrolment_required"
    assert admin.get("/api/auth/me").json()["mfa_required"] is True
    _enrol(admin)
    assert admin.get("/api/patients").status_code == 200
    r = admin.post("/api/auth/mfa/disable", json={"password": "Admin@12345", "code": "123456"})
    assert r.status_code == 403  # required for this role
    uid = next(u["id"] for u in admin.get("/api/users").json() if u["email"] == "doc@test.local")
    assert admin.post(f"/api/users/{uid}/mfa/reset").status_code == 204


# ---- sessions --------------------------------------------------------------------------------------
def test_sessions_list_revoke_and_password_change_signs_out_others(client):
    from fastapi.testclient import TestClient

    from app.main import create_app

    make_user("doc@test.local", "clinician")
    login(client, "doc@test.local", "Password@123")
    with TestClient(create_app(skip_migrations=True)) as other:
        login(other, "doc@test.local", "Password@123")
        sessions = client.get("/api/auth/sessions").json()
        assert len(sessions) == 2 and sum(s["current"] for s in sessions) == 1
        victim = next(s for s in sessions if not s["current"])
        assert client.delete(f"/api/auth/sessions/{victim['id']}").status_code == 204
        assert other.get("/api/auth/me").status_code == 401
        login(other, "doc@test.local", "Password@123")
        r = client.post("/api/auth/me/password", json={"current_password": "Password@123", "new_password": STRONG})
        assert r.status_code == 204
        assert other.get("/api/auth/me").status_code == 401  # signed out by the change
        assert client.get("/api/auth/me").status_code == 200


# ---- headers and CSRF ------------------------------------------------------------------------------
def test_security_headers_and_no_store(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "same-origin"
    assert r.headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in r.headers  # only over HTTPS


def test_hsts_when_cookies_are_secure(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "cookie_secure", True)
    assert "max-age" in client.get("/api/health").headers["strict-transport-security"]


def test_cross_site_state_change_is_blocked(admin):
    evil = {"Origin": "https://evil.example"}
    r = admin.post("/api/patients", json={"mrn": "X1", "first_name": "A", "last_name": "B"}, headers=evil)
    assert r.status_code == 403 and r.json()["code"] == "csrf"
    assert (
        admin.post(
            "/api/patients",
            json={"mrn": "X1", "first_name": "A", "last_name": "B"},
            headers={"Sec-Fetch-Site": "cross-site"},
        ).status_code
        == 403
    )
    same = {"Origin": "http://testserver"}
    assert (
        admin.post("/api/patients", json={"mrn": "X1", "first_name": "A", "last_name": "B"}, headers=same).status_code
        == 201
    )
    assert admin.get("/api/patients", headers=evil).status_code == 200  # reads are not state changes


# ---- production start guard ------------------------------------------------------------------------
def test_production_refuses_default_secret(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "app_env", "production")
    assert any("APP_SECRET_KEY" in p for p in s.production_problems())
    monkeypatch.setattr(s, "secret_key", "x" * 40)
    assert s.production_problems() == []


# ---- audit chain -----------------------------------------------------------------------------------
def test_audit_chain_detects_edit_and_deletion(admin):
    for i in range(3):
        create_patient(admin, mrn=f"A-{i}", first="Ann", last=f"Case{i}")
    db = app_db.SessionLocal()
    try:
        assert audit.verify_chain(db).ok
        assert admin.get("/api/audit/verify").json()["ok"] is True
        rows = db.scalars(select(AuditLog).order_by(AuditLog.id)).all()
        assert len(rows) >= 3 and all(r.entry_hash for r in rows)
        rows[1].summary = "tampered"
        db.commit()
        r = audit.verify_chain(db)
        assert not r.ok and r.first_bad_id == rows[1].id
    finally:
        db.close()
    assert admin.get("/api/audit/verify").json()["ok"] is False


def test_audit_chain_detects_removed_row(admin):
    for i in range(3):
        create_patient(admin, mrn=f"B-{i}", first="Bob", last=f"Case{i}")
    db = app_db.SessionLocal()
    try:
        rows = db.scalars(select(AuditLog).order_by(AuditLog.id)).all()
        db.delete(rows[1])
        db.commit()
        assert not audit.verify_chain(db).ok
    finally:
        db.close()


# ---- encryption at rest ----------------------------------------------------------------------------
def test_file_encryption_roundtrip_tamper_and_truncation():
    key = fileenc.derive_key("a passphrase for tests")
    data = b"patient report " * 200_000  # > 1 chunk
    blob = fileenc.encrypt_bytes(data, key)
    assert blob != data and fileenc.is_encrypted(blob[:8]) and len(blob) > len(data)
    assert fileenc.decrypt_bytes(blob, key) == data
    with pytest.raises(fileenc.DecryptionError):
        fileenc.decrypt_bytes(blob, fileenc.derive_key("another"))
    flipped = bytearray(blob)
    flipped[100] ^= 1
    with pytest.raises(fileenc.DecryptionError):
        fileenc.decrypt_bytes(bytes(flipped), key)
    with pytest.raises(fileenc.DecryptionError):
        fileenc.decrypt_bytes(blob[: len(blob) // 2], key)  # truncation is detected
    assert fileenc.decrypt_bytes(fileenc.encrypt_bytes(b"", key), key) == b""


def test_uploads_are_encrypted_on_disk_and_still_readable(clinician, monkeypatch):
    from pathlib import Path

    from app.models import Document
    from tests.conftest import lab_pdf, upload

    monkeypatch.setattr(get_settings(), "data_encryption_key", fileenc.new_key())
    p = create_patient(clinician, mrn="E-1", first="Eve", last="Crypt")
    r = upload(clinician, p["id"], lab_pdf("Eve Crypt", "E-1", [("HbA1c", "7.0", "%", "4.0-5.6")]))
    assert r.status_code == 201
    db = app_db.SessionLocal()
    try:
        doc = db.scalars(select(Document)).first()
        raw = Path(doc.storage_path).read_bytes()
    finally:
        db.close()
    assert fileenc.is_encrypted(raw[:8]) and b"%PDF" not in raw[:64]
    served = clinician.get(f"/api/documents/{r.json()['id']}/file")
    assert served.status_code == 200 and served.content.startswith(b"%PDF")
    assert clinician.get(f"/api/documents/{r.json()['id']}/preview?width=300").status_code == 200


# ---- malware scanning ------------------------------------------------------------------------------
def _fake_clamd(reply: bytes):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)

    def run():
        conn, _ = srv.accept()
        buf = b""
        while not buf.startswith(b"zINSTREAM\0"):
            buf += conn.recv(4096)
        buf = buf[len(b"zINSTREAM\0") :]
        while True:
            while len(buf) < 4:
                buf += conn.recv(4096)
            (n,) = struct.unpack("!I", buf[:4])
            buf = buf[4:]
            if n == 0:
                break
            while len(buf) < n:
                buf += conn.recv(4096)
            buf = buf[n:]
        conn.sendall(reply + b"\0")
        conn.close()
        srv.close()

    threading.Thread(target=run, daemon=True).start()
    return srv.getsockname()[1]


def test_infected_upload_is_blocked(clinician, monkeypatch):
    from tests.conftest import lab_pdf, upload

    port = _fake_clamd(b"stream: Eicar-Test-Signature FOUND")
    s = get_settings()
    monkeypatch.setattr(s, "clamav_host", "127.0.0.1")
    monkeypatch.setattr(s, "clamav_port", port)
    p = create_patient(clinician)
    r = upload(clinician, p["id"], lab_pdf("Alice Tester", "T-100", [("HbA1c", "7.0", "%", "4.0-5.6")]))
    assert r.status_code == 422 and "Eicar" in r.text


def test_clean_upload_passes_and_unreachable_scanner_fails_closed(clinician, monkeypatch):
    from tests.conftest import lab_pdf, upload

    s = get_settings()
    monkeypatch.setattr(s, "clamav_host", "127.0.0.1")
    monkeypatch.setattr(s, "clamav_port", _fake_clamd(b"stream: OK"))
    p = create_patient(clinician)
    pdf = lab_pdf("Alice Tester", "T-100", [("HbA1c", "7.0", "%", "4.0-5.6")])
    assert upload(clinician, p["id"], pdf).status_code == 201
    monkeypatch.setattr(s, "clamav_port", 1)  # nothing listens here
    assert (
        upload(clinician, p["id"], lab_pdf("Alice Tester", "T-100", [("HbA1c", "7.1", "%", "4.0-5.6")])).status_code
        == 503
    )
    monkeypatch.setattr(s, "clamav_fail_closed", False)
    assert (
        upload(clinician, p["id"], lab_pdf("Alice Tester", "T-100", [("HbA1c", "7.2", "%", "4.0-5.6")])).status_code
        == 201
    )


def test_user_model_defaults():
    db = app_db.SessionLocal()
    try:
        make_user("u@test.local", "viewer")
        u = db.scalars(select(User).where(User.email == "u@test.local")).one()
        assert u.mfa_enabled is False and u.failed_attempts == 0 and u.must_change_password is False
    finally:
        db.close()


def test_security_posture_endpoint(admin, clinician_client=None):
    r = admin.get("/api/system/security")
    assert r.status_code == 200
    ids = {i["id"]: i for i in r.json()["items"]}
    assert {"https", "secret", "mfa", "uploads", "disk", "scan", "audit", "lockout"} <= set(ids)
    assert ids["audit"]["ok"] is True and ids["secret"]["ok"] is True


def test_security_posture_is_admin_only(clinician):
    assert clinician.get("/api/system/security").status_code == 403
