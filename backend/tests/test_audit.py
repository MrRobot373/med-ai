"""Audit trail (spec §82, Phase 13): the service write path (best-effort, never
raises) and the admin-only review API, plus a spot-check that the real write endpoints
this build wires up (login, patient/encounter/report/knowledge writes) actually
produce a row — not just that the plumbing compiles.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.audit.service import list_audit_logs, record
from app.auth.security import hash_password
from app.db.session import SessionLocal
from app.models.audit_log import AuditAction, AuditLog, AuditOutcome
from app.models.user import User, UserRole
from tests.sample_documents import make_pdf_bytes

PASSWORD = "correct-horse-battery-7"


def _login_as(client: TestClient, email: str, role: UserRole) -> User:
    db = SessionLocal()
    try:
        user = User(email=email, display_name=email.split("@")[0], password_hash=hash_password(PASSWORD), role=role, active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
    finally:
        db.close()
    resp = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200
    return user


# --- Service ------------------------------------------------------------------------


def test_record_writes_a_row_with_resolved_email_from_user_id():
    db = SessionLocal()
    try:
        user = User(email="svc.audit1@example.com", display_name="svc", password_hash=hash_password(PASSWORD), role=UserRole.DOCTOR)
        db.add(user)
        db.commit()
        db.refresh(user)

        record(db, AuditAction.PATIENT_CREATED, user_id=user.id, object_type="patient", object_id="p1")

        rows = list_audit_logs(db, action=AuditAction.PATIENT_CREATED, user_id=user.id)
        assert len(rows) == 1
        assert rows[0].user_email == "svc.audit1@example.com"
        assert rows[0].outcome == AuditOutcome.SUCCESS
        assert rows[0].object_id == "p1"
    finally:
        db.query(AuditLog).filter(AuditLog.user_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
        db.close()


def test_record_survives_a_bad_detail_value_without_raising(monkeypatch: pytest.MonkeyPatch):
    """`detail` must be JSON-serializable — a caller mistake here must degrade to a
    dropped log entry, never break the real action being described."""
    db = SessionLocal()
    try:
        # An object with no JSON representation forces json.dumps() to raise inside record().
        class Unserializable:
            pass

        record(db, AuditAction.LOGIN, user_email="x@example.com", detail={"bad": Unserializable()})
        # No exception propagated — that's the whole point of the test.
    finally:
        db.close()


def test_list_audit_logs_filters_by_action_and_outcome():
    db = SessionLocal()
    try:
        record(db, AuditAction.LOGIN, user_email="filter1@example.com", outcome=AuditOutcome.FAILURE)
        record(db, AuditAction.LOGIN, user_email="filter1@example.com", outcome=AuditOutcome.SUCCESS)
        record(db, AuditAction.LOGOUT, user_email="filter1@example.com", outcome=AuditOutcome.SUCCESS)

        failures = list_audit_logs(db, action=AuditAction.LOGIN, outcome=AuditOutcome.FAILURE)
        assert all(r.action == AuditAction.LOGIN and r.outcome == AuditOutcome.FAILURE for r in failures)
        assert any(r.user_email == "filter1@example.com" for r in failures)
    finally:
        db.query(AuditLog).filter(AuditLog.user_email == "filter1@example.com").delete()
        db.commit()
        db.close()


# --- API ------------------------------------------------------------------------------


def test_audit_endpoint_requires_admin_role(client: TestClient):
    _login_as(client, "doctor.audit1@example.com", UserRole.DOCTOR)
    assert client.get("/api/audit").status_code == 403


def test_login_success_and_failure_are_both_logged(client: TestClient):
    user = _login_as(client, "admin.audit1@example.com", UserRole.ADMIN)
    client.post("/api/auth/login", json={"email": user.email, "password": "wrong-password"})

    resp = client.get("/api/audit", params={"action": "login", "user_id": user.id})
    assert resp.status_code == 200
    rows = resp.json()
    assert any(r["outcome"] == "success" for r in rows)

    failed = client.get("/api/audit", params={"action": "login", "outcome": "failure"}).json()
    assert any(r["user_email"] == user.email for r in failed)
    # Never resolves to a real user_id for a failed attempt against a real account —
    # the row exists purely from the attempted email (spec §82's minimal-PHI rule).


def test_logout_is_logged(client: TestClient):
    user = _login_as(client, "admin.audit2@example.com", UserRole.ADMIN)
    client.post("/api/auth/logout")
    # Logging back in as the same admin to read the audit log (the previous session
    # was just revoked).
    client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})

    rows = client.get("/api/audit", params={"action": "logout", "user_id": user.id}).json()
    assert len(rows) == 1
    assert rows[0]["outcome"] == "success"


def test_patient_and_encounter_writes_are_logged(client: TestClient):
    user = _login_as(client, "admin.audit3@example.com", UserRole.ADMIN)
    patient = client.post(
        "/api/patients",
        json={"first_name": "Audit", "last_name": "Test", "date_of_birth": "1970-01-01", "sex": "male"},
    ).json()
    client.patch(f"/api/patients/{patient['id']}", json={"notes": "updated"})
    client.post(f"/api/patients/{patient['id']}/archive")
    client.post(
        f"/api/patients/{patient['id']}/encounters",
        json={"encounter_type": "outpatient", "chief_complaint": "Routine visit"},
    )

    rows = client.get("/api/audit", params={"object_type": "patient", "object_id": patient["id"], "user_id": user.id}).json()
    actions = {r["action"] for r in rows}
    assert {"patient_created", "patient_modified"} <= actions
    # Two PATIENT_MODIFIED rows (update + archive), distinguished in `detail`.
    modified = [r for r in rows if r["action"] == "patient_modified"]
    assert {m["detail"]["action"] for m in modified} == {"updated", "archived"}

    encounter_rows = client.get("/api/audit", params={"action": "encounter_created", "user_id": user.id}).json()
    assert any(r["detail"]["patient_id"] == patient["id"] for r in encounter_rows)


def test_report_upload_and_archive_are_logged(client: TestClient):
    user = _login_as(client, "admin.audit4@example.com", UserRole.ADMIN)
    patient = client.post(
        "/api/patients", json={"first_name": "Rep", "last_name": "Ort", "date_of_birth": "1970-01-01", "sex": "male"}
    ).json()

    pdf_bytes = make_pdf_bytes(["Some real report text long enough to skip OCR fallback."])
    upload = client.post(
        f"/api/patients/{patient['id']}/reports", files={"file": ("report.pdf", pdf_bytes, "application/pdf")}
    )
    assert upload.status_code == 201, upload.text
    report_id = upload.json()["id"]
    client.post(f"/api/reports/{report_id}/archive")

    rows = client.get("/api/audit", params={"object_type": "report", "object_id": report_id, "user_id": user.id}).json()
    assert {r["action"] for r in rows} == {"report_uploaded", "report_archived"}


def test_knowledge_upload_and_activate_are_logged(client: TestClient):
    user = _login_as(client, "admin.audit5@example.com", UserRole.ADMIN)
    document = client.post(
        "/api/knowledge/documents", json={"title": "Audit KB Doc", "authority_tier": "a"}
    ).json()

    v1 = client.post(
        f"/api/knowledge/documents/{document['id']}/versions",
        files={"file": ("v1.pdf", make_pdf_bytes(["Guideline text v1, long enough to skip OCR fallback."]), "application/pdf")},
    ).json()
    v2 = client.post(
        f"/api/knowledge/documents/{document['id']}/versions",
        files={"file": ("v2.pdf", make_pdf_bytes(["Guideline text v2, a distinct revision, also long enough."]), "application/pdf")},
    ).json()
    client.post(f"/api/knowledge/documents/{document['id']}/activate-version", json={"version_id": v1["id"]})

    rows = client.get("/api/audit", params={"action": "knowledge_document_uploaded", "user_id": user.id}).json()
    uploaded_ids = {r["object_id"] for r in rows}
    assert {v1["id"], v2["id"]} <= uploaded_ids

    changed = client.get("/api/audit", params={"action": "knowledge_version_changed", "user_id": user.id}).json()
    assert any(r["object_id"] == v1["id"] for r in changed)
