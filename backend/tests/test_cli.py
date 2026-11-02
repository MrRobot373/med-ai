from __future__ import annotations

from sqlalchemy import select

from app import cli
from app import db as app_db
from app.core.config import get_settings
from app.core.security import decrypt_secret, encrypt_secret
from app.models import AppSetting, User
from tests.conftest import create_patient, make_user


def test_audit_verify_command(admin, capsys):
    create_patient(admin)
    assert cli.main(["audit-verify"]) == 0
    assert "verified" in capsys.readouterr().out


def test_rotate_secret_reencrypts_settings_and_mfa(admin, capsys):
    old = get_settings().secret_key
    new = "n" * 40
    db = app_db.SessionLocal()
    try:
        row = db.get(AppSetting, "runtime")
        data = dict(row.value)
        data["llm"] = {**data["llm"], "api_key": encrypt_secret("sk-live-123", old)}
        row.value = data
        make_user("mfa@test.local", "clinician")
        u = db.scalars(select(User).where(User.email == "mfa@test.local")).one()
        u.mfa_secret = encrypt_secret("JBSWY3DPEHPK3PXP", old)
        db.commit()
    finally:
        db.close()
    assert cli.main(["rotate-secret", "wrong-old-secret", new]) == 1  # refuses, changes nothing
    assert cli.main(["rotate-secret", old, new]) == 0
    db = app_db.SessionLocal()
    try:
        assert decrypt_secret(db.get(AppSetting, "runtime").value["llm"]["api_key"], new) == "sk-live-123"
        u = db.scalars(select(User).where(User.email == "mfa@test.local")).one()
        assert decrypt_secret(u.mfa_secret, new) == "JBSWY3DPEHPK3PXP"
    finally:
        db.close()


def test_create_admin_enforces_password_policy(client):
    assert cli.main(["create-admin", "ops@test.local", "Ops Admin", "--password", "short"]) == 1
    assert cli.main(["create-admin", "ops@test.local", "Ops Admin", "--password", "Blue-Heron-Walks-0914"]) == 0
    db = app_db.SessionLocal()
    try:
        u = db.scalars(select(User).where(User.email == "ops@test.local")).one()
        assert u.role == "admin" and u.must_change_password
    finally:
        db.close()


def test_unlock_and_reset_mfa(client):
    make_user("d@test.local", "clinician")
    db = app_db.SessionLocal()
    try:
        u = db.scalars(select(User).where(User.email == "d@test.local")).one()
        u.failed_attempts, u.mfa_enabled, u.mfa_secret = 4, True, "x"
        db.commit()
    finally:
        db.close()
    assert cli.main(["unlock", "d@test.local"]) == 0
    assert cli.main(["reset-mfa", "d@test.local"]) == 0
    db = app_db.SessionLocal()
    try:
        u = db.scalars(select(User).where(User.email == "d@test.local")).one()
        assert u.failed_attempts == 0 and not u.mfa_enabled and u.mfa_secret is None
    finally:
        db.close()
    assert cli.main(["unlock", "nobody@test.local"]) == 1
