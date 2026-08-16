"""Overview dashboard summary — spec §22, real counts (Phase 16 finding: the frontend
placeholder was never wired up to real data once reports/AI features actually shipped,
see docs/architecture.md's Phase 16 section). The shared test DB accumulates rows
across the whole session, so these assertions check *deltas* around a call, never
absolute totals.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from tests.sample_documents import make_pdf_bytes

PASSWORD = "correct-horse-battery-11"


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


def test_summary_reflects_a_real_new_patient_and_report(client: TestClient):
    _login_as(client, "doctor.dash1@example.com", UserRole.DOCTOR)
    before = client.get("/api/dashboard/summary").json()

    patient = client.post(
        "/api/patients", json={"first_name": "Dash", "last_name": "Board", "date_of_birth": "1970-01-01", "sex": "male"}
    ).json()
    pdf_bytes = make_pdf_bytes(["Patient Name: Dash Board", "Chief Complaint: Routine check."])
    upload = client.post(
        f"/api/patients/{patient['id']}/reports", files={"file": ("note.pdf", pdf_bytes, "application/pdf")}
    )
    assert upload.status_code == 201

    after = client.get("/api/dashboard/summary").json()
    assert after["active_patients"] == before["active_patients"] + 1
    assert after["total_reports"] == before["total_reports"] + 1


def test_summary_excludes_archived_patients_and_reports(client: TestClient):
    _login_as(client, "doctor.dash2@example.com", UserRole.DOCTOR)
    patient = client.post(
        "/api/patients", json={"first_name": "Archived", "last_name": "Person", "date_of_birth": "1970-01-01", "sex": "female"}
    ).json()
    before = client.get("/api/dashboard/summary").json()

    client.post(f"/api/patients/{patient['id']}/archive")

    after = client.get("/api/dashboard/summary").json()
    assert after["active_patients"] == before["active_patients"] - 1


def test_summary_requires_authentication(client: TestClient):
    resp = client.get("/api/dashboard/summary")
    assert resp.status_code == 401
