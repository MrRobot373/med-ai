"""Signed offline licences: tamper-proof, bound to one installation, and never a reason to block clinical work."""

import base64
import importlib.util
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app import db as app_db
from app.core.config import get_settings
from app.services import licensing
from tests.conftest import create_patient, make_user

_spec = importlib.util.spec_from_file_location(
    "licence_tool", Path(__file__).resolve().parents[2] / "tools" / "licence.py"
)
tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tool)


@pytest.fixture
def vendor(monkeypatch):
    """A throwaway vendor key; the product is told to trust its public half."""
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    monkeypatch.setenv("LICENCE_PUBLIC_KEY", pub.decode().replace("\n", "\\n"))
    return key


def make_licence(key, install_id, *, clinicians=1, staff=1, branches=1, expires=None, grace=30):
    payload = {
        "v": 1,
        "licence_id": "LIC-T-1",
        "customer": "Test Clinic",
        "install_id": install_id,
        "issued_at": date.today().isoformat(),
        "expires_at": expires,
        "grace_days": grace,
        "limits": {"clinicians": clinicians, "staff": staff, "branches": branches},
    }
    return {"payload": payload, "signature": base64.b64encode(key.sign(tool.canonical(payload))).decode()}


def _iid():
    db = app_db.SessionLocal()
    try:
        return licensing.install_id(db)
    finally:
        db.close()


def test_the_vendor_tool_and_the_product_agree_on_the_signed_bytes(vendor):
    doc = make_licence(vendor, _iid())
    assert licensing.canonical(doc["payload"]) == tool.canonical(doc["payload"])
    assert licensing.verify(doc, _iid())["customer"] == "Test Clinic"


def test_a_licence_must_be_signed_by_the_vendor_and_made_for_this_installation(admin, vendor):
    good = make_licence(vendor, _iid())
    assert admin.post("/api/system/licence", json=good).status_code == 200
    tampered = json.loads(json.dumps(good))
    tampered["payload"]["limits"]["clinicians"] = 500
    assert admin.post("/api/system/licence", json=tampered).status_code == 422
    forged = make_licence(Ed25519PrivateKey.generate(), _iid())
    assert admin.post("/api/system/licence", json=forged).status_code == 422
    elsewhere = make_licence(vendor, "ANOTHER-INSTALL")
    r = admin.post("/api/system/licence", json=elsewhere)
    assert r.status_code == 422 and "different installation" in r.json()["detail"]
    assert admin.post("/api/system/licence", json={"nonsense": 1}).status_code == 422


def test_without_a_vendor_key_licences_are_refused_with_a_clear_message(admin, monkeypatch):
    monkeypatch.setenv("LICENCE_PUBLIC_KEY", "")
    monkeypatch.setattr(licensing, "ASSETS", Path("/nonexistent"))
    r = admin.post("/api/system/licence", json={"payload": {}, "signature": ""})
    assert r.status_code == 422 and "no vendor key" in r.json()["detail"]


def test_seat_limits_apply_per_role_and_admins_are_free(admin, vendor):
    admin.post("/api/system/licence", json=make_licence(vendor, _iid(), clinicians=1, staff=1))
    ok = admin.post(
        "/api/users",
        json={"email": "d1@t.local", "full_name": "Doc One", "role": "clinician", "password": "Blue-Heron-Walks-0914"},
    )
    assert ok.status_code == 201
    over = admin.post(
        "/api/users",
        json={"email": "d2@t.local", "full_name": "Doc Two", "role": "clinician", "password": "Blue-Heron-Walks-0914"},
    )
    assert (
        over.status_code == 402 and over.json()["code"] == "licence_limit" and "1 clinicians" in over.json()["detail"]
    )
    assert (
        admin.post(
            "/api/users",
            json={
                "email": "f1@t.local",
                "full_name": "Desk One",
                "role": "front_desk",
                "password": "Blue-Heron-Walks-0914",
            },
        ).status_code
        == 201
    )
    assert (
        admin.post(
            "/api/users",
            json={
                "email": "v1@t.local",
                "full_name": "View One",
                "role": "viewer",
                "password": "Blue-Heron-Walks-0914",
            },
        ).status_code
        == 402
    )
    assert (
        admin.post(
            "/api/users",
            json={
                "email": "a2@t.local",
                "full_name": "Admin Two",
                "role": "admin",
                "password": "Blue-Heron-Walks-0914",
            },
        ).status_code
        == 201
    )


def test_reactivating_or_changing_role_also_needs_a_seat(admin, vendor):
    admin.post("/api/system/licence", json=make_licence(vendor, _iid(), clinicians=1, staff=5))
    uid = admin.post(
        "/api/users",
        json={"email": "d1@t.local", "full_name": "Doc One", "role": "clinician", "password": "Blue-Heron-Walks-0914"},
    ).json()["id"]
    desk = admin.post(
        "/api/users",
        json={
            "email": "f1@t.local",
            "full_name": "Desk One",
            "role": "front_desk",
            "password": "Blue-Heron-Walks-0914",
        },
    ).json()["id"]
    assert admin.patch(f"/api/users/{desk}", json={"role": "clinician"}).status_code == 402
    admin.patch(f"/api/users/{uid}", json={"is_active": False})
    assert (
        admin.patch(f"/api/users/{desk}", json={"role": "clinician"}).status_code == 200
    )  # seat freed by deactivation
    assert admin.patch(f"/api/users/{uid}", json={"is_active": True}).status_code == 402


def test_branch_limit(admin, vendor):
    admin.post("/api/system/licence", json=make_licence(vendor, _iid(), branches=1))
    r = admin.post("/api/branches", json={"code": "NORTH", "name": "North"})
    assert r.status_code == 402 and "1 branches" in r.json()["detail"]


def test_expiry_warns_then_stops_new_seats_but_never_clinical_work(admin, vendor):
    soon = (date.today() + timedelta(days=10)).isoformat()
    admin.post("/api/system/licence", json=make_licence(vendor, _iid(), clinicians=5, expires=soon))
    s = admin.get("/api/system/licence").json()
    assert s["mode"] == "licensed" and s["days_left"] == 10 and "expires in 10" in s["message"]

    lapsed = (date.today() - timedelta(days=5)).isoformat()
    admin.post("/api/system/licence", json=make_licence(vendor, _iid(), clinicians=5, expires=lapsed, grace=30))
    s = admin.get("/api/system/licence").json()
    assert s["mode"] == "grace" and s["can_add"] is True

    long_ago = (date.today() - timedelta(days=90)).isoformat()
    admin.post("/api/system/licence", json=make_licence(vendor, _iid(), clinicians=5, expires=long_ago, grace=30))
    s = admin.get("/api/system/licence").json()
    assert s["mode"] == "expired" and s["can_add"] is False
    blocked = admin.post(
        "/api/users",
        json={"email": "d1@t.local", "full_name": "Doc One", "role": "clinician", "password": "Blue-Heron-Walks-0914"},
    )
    assert blocked.status_code == 402 and blocked.json()["code"] == "licence_required"
    # clinical work is untouched
    p = create_patient(admin, mrn="LIC-1")
    assert admin.get(f"/api/patients/{p['id']}").status_code == 200
    assert admin.post(f"/api/patients/{p['id']}/conditions", json={"name": "Asthma"}).status_code == 201


def test_evaluation_limits_apply_only_in_production(admin, monkeypatch):
    from app.core.errors import AppError

    for i in range(4):
        make_user(f"d{i}@t.local", "clinician")
    db = app_db.SessionLocal()
    try:
        assert licensing.state(db)["enforced"] is False  # development / test: unrestricted
        licensing.assert_can_add_user(db, "clinician")
        monkeypatch.setattr(type(get_settings()), "is_production", property(lambda self: True))
        s = licensing.state(db)
        assert s["mode"] == "evaluation" and s["enforced"] is True and s["limits"]["clinicians"] == 2
        with pytest.raises(AppError) as e:
            licensing.assert_can_add_user(db, "clinician")
        assert e.value.status_code == 402
        licensing.assert_can_add_user(db, "admin")  # administrators never use a seat
    finally:
        db.close()


def test_usage_report_has_counts_only(admin):
    create_patient(admin, mrn="U-1", first="Private", last="Person")
    r = admin.get("/api/system/usage-report")
    assert r.status_code == 200 and r.json()["usage"]["patients"] == 1 and r.json()["usage"]["admins"] == 1
    assert "Private" not in r.text and "U-1" not in r.text


def test_only_administrators_see_licence_details(clinician):
    assert clinician.get("/api/system/licence").status_code == 403
    assert clinician.post("/api/system/licence", json={}).status_code == 403
    assert clinician.get("/api/system/usage-report").status_code == 403


def test_the_vendor_tool_round_trip(tmp_path, monkeypatch):
    out = tmp_path / "keys"

    class A:
        pass

    a = A()
    a.out, a.force = str(out), False
    assert tool.keygen(a) == 0 and tool.keygen(a) == 1  # refuses to overwrite a signing key
    lic = tmp_path / "lic.json"
    b = A()
    b.key, b.customer, b.install_id = str(out / "licence_private.pem"), "Round Trip Clinic", "ABCD1234ABCD1234"
    b.clinicians, b.staff, b.branches, b.expires, b.grace_days, b.licence_id, b.out = (
        3,
        2,
        1,
        "2030-01-01",
        30,
        None,
        str(lic),
    )
    assert tool.issue(b) == 0
    monkeypatch.setenv("LICENCE_PUBLIC_KEY", (out / "licence_public.pem").read_text().replace("\n", "\\n"))
    p = licensing.verify(json.loads(lic.read_text()), "ABCD1234ABCD1234")
    assert p["customer"] == "Round Trip Clinic" and p["limits"] == {"clinicians": 3, "staff": 2, "branches": 1}
