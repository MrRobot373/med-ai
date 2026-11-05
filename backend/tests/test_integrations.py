"""Partner API keys, webhooks (signed, queued, retried) and CSV exports."""

import hashlib
import hmac
import json
from datetime import date, timedelta

import httpx
import pytest

from app import db as app_db
from app.models import Webhook, WebhookDelivery
from app.services import integration
from tests.conftest import create_patient, login, make_user

ITEMS = [{"drug": "Pan 40", "dose": "1 tab", "frequency": "OD", "duration_days": 14}]


def _finalized_rx(c, mrn="IN-1"):
    pid = create_patient(c, mrn=mrn, first="Rohit", last="Verma", date_of_birth="1957-05-10", sex="male")["id"]
    enc = c.post(f"/api/patients/{pid}/consultations", json={}).json()
    rx = c.post(f"/api/consultations/{enc['id']}/prescription").json()
    c.put(f"/api/prescriptions/{rx['id']}", json={"diagnosis": "Acute gastritis", "items": ITEMS})
    assert c.post(f"/api/prescriptions/{rx['id']}/finalize", json={}).status_code == 200
    return pid, enc["id"], rx["id"]


def _token(c, scopes, **kw):
    r = c.post("/api/integrations/tokens", json={"name": "Pharmacy partner", "scopes": scopes, **kw})
    assert r.status_code == 201, r.text
    return r.json()["token"]


def _bearer(t):
    return {"Authorization": f"Bearer {t}"}


def test_keys_are_scoped_hashed_and_revocable(admin):
    _, _, rx_id = _finalized_rx(admin)
    made = admin.post("/api/integrations/tokens", json={"name": "Pharmacy", "scopes": ["prescriptions:read"]}).json()
    token = made["token"]
    assert (
        token.startswith("gms_") and "token" not in admin.get("/api/integrations/tokens").json()[0]
    )  # shown once only
    db = app_db.SessionLocal()
    try:
        from app.models import ApiToken

        row = db.get(ApiToken, made["id"])
        assert token not in (row.token_hash, row.prefix) and len(row.token_hash) == 64
    finally:
        db.close()
    admin.cookies.clear()  # partners do not sign in as a person
    h = _bearer(token)
    ok = admin.get(f"/api/integration/v1/prescriptions/{rx_id}", headers=h)
    assert ok.status_code == 200 and ok.json()["items"][0]["drug"] == "Pan 40" and ok.json()["patient"]["mrn"] == "IN-1"
    assert admin.get("/api/integration/v1/visits", headers=h).status_code == 403  # a scope it was not given
    assert (
        admin.post(
            f"/api/integration/v1/prescriptions/{rx_id}/dispensed", json={"dispensed_by": "Apollo"}, headers=h
        ).status_code
        == 403
    )
    assert admin.get("/api/integration/v1/prescriptions").status_code == 401
    assert admin.get("/api/integration/v1/prescriptions", headers=_bearer("gms_wrong")).status_code == 401
    login(admin)
    assert admin.delete(f"/api/integrations/tokens/{made['id']}").status_code == 204
    admin.cookies.clear()
    assert admin.get(f"/api/integration/v1/prescriptions/{rx_id}", headers=h).status_code == 401


def test_expired_keys_stop_working(admin):
    token = _token(admin, ["patients:read"], expires_in_days=1)
    db = app_db.SessionLocal()
    try:
        from app.db import utcnow
        from app.models import ApiToken

        for t in db.query(ApiToken):
            t.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()
    create_patient(admin, mrn="EX-1")
    admin.cookies.clear()
    assert admin.get("/api/integration/v1/patients/EX-1", headers=_bearer(token)).status_code == 401


def test_a_session_cookie_cannot_use_the_partner_api_and_keys_cannot_use_the_app(admin):
    _, _, rx_id = _finalized_rx(admin)
    assert admin.get(f"/api/integration/v1/prescriptions/{rx_id}").status_code == 401  # cookie alone is not a key
    token = _token(admin, ["prescriptions:read", "patients:read", "visits:read", "prescriptions:dispense"])
    admin.cookies.clear()
    assert admin.get("/api/patients", headers=_bearer(token)).status_code == 401  # the app's own API needs a person


def test_pharmacy_can_mark_dispensed_once_and_drafts_are_invisible(admin):
    pid, enc_id, rx_id = _finalized_rx(admin)
    token = _token(admin, ["prescriptions:read", "prescriptions:dispense"])
    pid2 = create_patient(admin, mrn="IN-2", first="Asha", last="Nair")["id"]
    enc2 = admin.post(f"/api/patients/{pid2}/consultations", json={}).json()
    rx2 = admin.post(f"/api/consultations/{enc2['id']}/prescription").json()
    assert rx2["status"] == "draft"
    admin.cookies.clear()
    h = _bearer(token)
    assert admin.get(f"/api/integration/v1/prescriptions/{rx2['id']}", headers=h).status_code == 404  # draft
    r = admin.post(
        f"/api/integration/v1/prescriptions/{rx_id}/dispensed",
        json={"dispensed_by": "Apollo Pharmacy", "note": "Paid cash"},
        headers=h,
    )
    assert r.status_code == 200 and r.json()["dispensed"]["by"] == "Apollo Pharmacy"
    assert (
        admin.post(
            f"/api/integration/v1/prescriptions/{rx_id}/dispensed", json={"dispensed_by": "Other"}, headers=h
        ).status_code
        == 409
    )
    listing = admin.get("/api/integration/v1/prescriptions", headers=h).json()
    assert [i["id"] for i in listing["items"]] == [rx_id] and listing["items"][0]["dispensed"][
        "by"
    ] == "Apollo Pharmacy"
    login(admin)
    audit = admin.get("/api/audit", params={"action": "prescription.dispensed"}).json()
    assert any("Apollo" in a["summary"] for a in (audit["items"] if isinstance(audit, dict) else audit))


def test_visits_feed_for_billing(admin):
    pid, enc_id, _ = _finalized_rx(admin)
    admin.post(f"/api/consultations/{enc_id}/orders", json={"tests": [{"test_name": "HbA1c", "category": "lab"}]})
    admin.post(f"/api/consultations/{enc_id}/complete", json={})
    letter = admin.post(f"/api/patients/{pid}/letters", json={"kind": "fitness", "encounter_id": enc_id}).json()
    admin.post(f"/api/letters/{letter['id']}/issue")
    token = _token(admin, ["visits:read"])
    admin.cookies.clear()
    v = admin.get("/api/integration/v1/visits", headers=_bearer(token)).json()["items"]
    assert len(v) == 1
    kinds = [s["type"] for s in v[0]["services"]]
    assert "consultation" in kinds and "prescription" in kinds and "letter" in kinds
    assert v[0]["patient"]["mrn"] == "IN-1" and v[0]["diagnoses"] is not None


class _Receiver:
    """Stands in for a partner's server and records what it was sent."""

    def __init__(self, statuses):
        self.statuses, self.calls = list(statuses), []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        return httpx.Response(self.statuses.pop(0) if self.statuses else 200)


def _hook(c, **kw):
    r = c.post(
        "/api/integrations/webhooks",
        json={"name": "Billing", "url": "http://10.1.2.3:9000/hook", "events": ["prescription.finalized"], **kw},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _pump(receiver, **kw):
    db = app_db.SessionLocal()
    try:
        client = httpx.Client(transport=httpx.MockTransport(receiver))
        return integration.deliver_due(db, client=client, **kw)
    finally:
        db.close()


def test_webhook_message_is_signed_minimal_by_default_and_queued_with_the_event(admin, monkeypatch):
    monkeypatch.setattr(integration, "check_url", lambda url: None)
    hook = _hook(admin)
    secret = hook["secret"]
    _, _, rx_id = _finalized_rx(admin)
    db = app_db.SessionLocal()
    queued = db.query(WebhookDelivery).all()
    db.close()
    assert len(queued) == 1 and queued[0].status == "pending"
    rec = _Receiver([200])
    assert _pump(rec) == 1
    req = rec.calls[0]
    body = req.content.decode()
    data = json.loads(body)
    assert data["event"] == "prescription.finalized" and data["id"] == rx_id and data["patient_mrn"] == "IN-1"
    assert "data" not in data and "Pan 40" not in body  # minimal: no clinical content in the message
    ts = req.headers["X-GMS-Timestamp"]
    expected = hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
    assert (
        req.headers["X-GMS-Signature"] == f"t={ts},v1={expected}"
        and req.headers["X-GMS-Event"] == "prescription.finalized"
    )
    db = app_db.SessionLocal()
    assert db.query(WebhookDelivery).one().status == "delivered"
    db.close()


def test_full_payload_webhooks_carry_the_details(admin, monkeypatch):
    monkeypatch.setattr(integration, "check_url", lambda url: None)
    _hook(admin, payload="full")
    _finalized_rx(admin)
    rec = _Receiver([200])
    _pump(rec)
    assert json.loads(rec.calls[0].content)["data"]["items"][0]["drug"] == "Pan 40"


def test_failed_deliveries_are_retried_later_then_given_up_on(admin, monkeypatch):
    monkeypatch.setattr(integration, "check_url", lambda url: None)
    _hook(admin)
    _finalized_rx(admin)
    rec = _Receiver([500, 200])
    assert _pump(rec) == 1
    db = app_db.SessionLocal()
    d = db.query(WebhookDelivery).one()
    assert d.status == "pending" and d.attempts == 1 and d.response_code == 500 and d.next_attempt_at > app_db.utcnow()
    assert _pump(rec) == 0  # not due yet: no hammering a struggling server
    d.next_attempt_at = app_db.utcnow() - timedelta(seconds=1)
    db.commit()
    db.close()
    assert _pump(rec) == 1
    db = app_db.SessionLocal()
    assert db.query(WebhookDelivery).one().status == "delivered"
    d = db.query(WebhookDelivery).one()
    d.status, d.attempts, d.next_attempt_at = "pending", len(integration.RETRY_DELAYS), app_db.utcnow()
    db.commit()
    db.close()
    always_down = _Receiver([500] * 5)
    _pump(always_down)
    db = app_db.SessionLocal()
    assert db.query(WebhookDelivery).one().status == "failed"
    db.close()


def test_events_are_only_sent_to_webhooks_that_asked_for_them(admin, monkeypatch):
    monkeypatch.setattr(integration, "check_url", lambda url: None)
    _hook(admin, events=["letter.issued"])
    _finalized_rx(admin)
    db = app_db.SessionLocal()
    assert db.query(WebhookDelivery).count() == 0
    db.close()
    inactive = _hook(admin, events=["prescription.finalized"], active=False)
    assert inactive["active"] is False


def test_the_test_button_sends_a_ping_and_reports_the_result(admin, monkeypatch):
    monkeypatch.setattr(integration, "check_url", lambda url: None)
    hook = _hook(admin)
    seen = []

    def handler(req):
        seen.append(req.headers["X-GMS-Event"])
        return httpx.Response(204)

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kw: (
            httpx.Client.__wrapped__(transport=httpx.MockTransport(handler)) if False else _RealClient(handler)
        ),
    )
    r = admin.post(f"/api/integrations/webhooks/{hook['id']}/test")
    assert r.status_code == 200 and r.json()["status"] == "delivered" and seen == ["ping"]


_real_client = httpx.Client


def _RealClient(handler):
    return _real_client(transport=httpx.MockTransport(handler))


def test_dangerous_webhook_addresses_are_refused(admin):
    for url in (
        "http://127.0.0.1:8000/x",
        "http://169.254.169.254/latest/meta-data",
        "ftp://example.com/x",
        "file:///etc/passwd",
        "http://localhost/x",
    ):
        r = admin.post("/api/integrations/webhooks", json={"name": "Bad", "url": url, "events": ["ping"]})
        assert r.status_code == 422, url
    bad_event = admin.post(
        "/api/integrations/webhooks", json={"name": "Bad", "url": "http://10.1.2.3/x", "events": ["nonsense"]}
    )
    assert bad_event.status_code == 422


def test_secrets_are_stored_encrypted_and_can_be_rotated(admin, monkeypatch):
    monkeypatch.setattr(integration, "check_url", lambda url: None)
    hook = _hook(admin)
    db = app_db.SessionLocal()
    row = db.get(Webhook, hook["id"])
    assert hook["secret"] not in row.secret_enc
    db.close()
    assert "secret" not in admin.get("/api/integrations/webhooks").json()[0]
    new = admin.post(f"/api/integrations/webhooks/{hook['id']}/rotate-secret").json()["secret"]
    assert new != hook["secret"]


def test_only_administrators_manage_integrations(clinician):
    for method, url in (
        ("get", "/api/integrations/tokens"),
        ("get", "/api/integrations/webhooks"),
        ("get", "/api/integrations/catalog"),
    ):
        assert getattr(clinician, method)(url).status_code == 403
    assert (
        clinician.post("/api/integrations/tokens", json={"name": "x", "scopes": ["patients:read"]}).status_code == 403
    )


def test_csv_export_for_billing_staff(admin):
    pid, enc_id, _ = _finalized_rx(admin)
    admin.patch(f"/api/patients/{pid}", json={"first_name": '=HYPERLINK("http://evil")'})
    admin.post(f"/api/consultations/{enc_id}/complete", json={})
    today = date.today()
    r = admin.get(
        "/api/exports/visits.csv",
        params={"start": str(today - timedelta(days=1)), "end": str(today + timedelta(days=1))},
    )
    assert r.status_code == 200 and r.text.startswith("﻿") and "IN-1" in r.text
    assert "'=HYPERLINK" in r.text and ",=HYPERLINK" not in r.text  # spreadsheet formulas are defused
    p = admin.get(
        "/api/exports/prescriptions.csv",
        params={"start": str(today - timedelta(days=1)), "end": str(today + timedelta(days=1))},
    )
    assert "Pan 40" in p.text
    assert admin.get("/api/exports/visits.csv", params={"start": "2020-01-01", "end": "2026-01-01"}).status_code == 422


def test_viewer_cannot_export(admin):
    make_user("view@test.local", "viewer")
    login(admin, "view@test.local", "Password@123")
    assert admin.get("/api/exports/visits.csv", params={"start": "2026-01-01", "end": "2026-01-31"}).status_code == 403


@pytest.mark.parametrize(
    "path", ["/api/integration/v1/prescriptions", "/api/integration/v1/visits", "/api/integration/v1/patients/X"]
)
def test_partner_endpoints_require_a_key(client, path):
    assert client.get(path).status_code == 401


def test_fhir_bundle_for_a_pharmacy(admin):
    _, _, rx_id = _finalized_rx(admin)
    token = _token(admin, ["prescriptions:read", "metrics:read"])
    admin.cookies.clear()
    r = admin.get(f"/api/integration/v1/prescriptions/{rx_id}/fhir", headers=_bearer(token))
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/fhir+json")
    b = r.json()
    kinds = [e["resource"]["resourceType"] for e in b["entry"]]
    assert b["resourceType"] == "Bundle" and kinds == ["Patient", "Practitioner", "MedicationRequest"]
    mr = b["entry"][2]["resource"]
    assert mr["medicationCodeableConcept"]["text"] == "Pan 40" and mr["intent"] == "order" and mr["status"] == "active"
    assert mr["dosageInstruction"][0]["timing"]["repeat"] == {
        "frequency": 1,
        "period": 1,
        "periodUnit": "d",
        "boundsDuration": {"value": 14, "unit": "day", "system": "http://unitsofmeasure.org", "code": "d"},
    }
    assert (
        mr["subject"]["reference"] == b["entry"][0]["fullUrl"]
        and b["entry"][0]["resource"]["identifier"][0]["value"] == "IN-1"
    )


def test_metrics_need_their_own_scope_and_hold_no_patient_data(admin):
    _finalized_rx(admin)
    ok, no = _token(admin, ["metrics:read"]), _token(admin, ["patients:read"])
    admin.cookies.clear()
    assert admin.get("/api/integration/v1/metrics", headers=_bearer(no)).status_code == 403
    r = admin.get("/api/integration/v1/metrics", headers=_bearer(ok))
    assert r.status_code == 200 and "gms_up 1" in r.text and "gms_patients 1" in r.text
    assert "Rohit" not in r.text and "IN-1" not in r.text
