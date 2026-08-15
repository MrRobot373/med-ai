"""Medication reconciliation API — spec §36, end-to-end: seeded current medications
vs. a report's detected medication list.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.db.session import SessionLocal
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


def _create_patient(client: TestClient, **overrides) -> dict:
    payload = {"first_name": "Robert", "last_name": "Klein", "date_of_birth": "1958-09-03", "sex": "male"}
    payload.update(overrides)
    resp = client.post("/api/patients", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _add_medication(client: TestClient, patient_id: str, **overrides) -> dict:
    payload = {"medication_name": "Aspirin", "dose": "81mg", "frequency": "once daily"}
    payload.update(overrides)
    resp = client.post(f"/api/patients/{patient_id}/medications", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_reconciliation_classifies_new_unchanged_review_and_not_in_document(client: TestClient):
    _login_as(client, "doctor.rec1@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, mrn="DEMO-TEST-REC1")

    # Current system list: one that will match unchanged (same dose text on both
    # sides), one that will mismatch on dose, one the document simply won't mention.
    _add_medication(client, patient["id"], medication_name="Aspirin", dose="81mg")
    _add_medication(client, patient["id"], medication_name="Metformin", dose="500mg", frequency="twice daily")
    _add_medication(client, patient["id"], medication_name="Artificial tears", dose="1 drop", frequency="as needed")

    pdf_bytes = make_pdf_bytes(
        [
            "Patient Name: Robert Klein",
            "MRN: DEMO-TEST-REC1",
            "Date: 14 August 2026",
            "",
            "Current Medications:",
            "Aspirin 81mg oral once daily",
            "Metformin 1000mg oral twice daily",
            "Lisinopril 10mg oral once daily",
        ]
    )
    resp = client.post(
        f"/api/patients/{patient['id']}/reports", files={"file": ("consult.pdf", pdf_bytes, "application/pdf")}
    )
    assert resp.status_code == 201, resp.text
    report_id = resp.json()["id"]

    recon = client.get(f"/api/reports/{report_id}/medication-reconciliation")
    assert recon.status_code == 200
    items = recon.json()["items"]
    by_status: dict[str, list[dict]] = {}
    for item in items:
        by_status.setdefault(item["status"], []).append(item)

    newly_detected_names = {i["document_medication_name"] for i in by_status.get("newly_detected", [])}
    assert newly_detected_names == {"Lisinopril"}

    not_in_document_names = {i["current_medication_name"] for i in by_status.get("not_in_document", [])}
    assert not_in_document_names == {"Artificial tears"}

    unchanged_names = {i["current_medication_name"] for i in by_status.get("matched_unchanged", [])}
    assert unchanged_names == {"Aspirin"}  # "81mg" on both sides

    review_names = {i["current_medication_name"] for i in by_status.get("matched_review", [])}
    assert review_names == {"Metformin"}  # dose text differs ("500mg" vs "1000mg")


def test_viewer_can_read_reconciliation(client: TestClient):
    _login_as(client, "doctor.rec2@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, mrn="DEMO-TEST-REC2")
    pdf_bytes = make_pdf_bytes(
        ["Patient Name: Robert Klein", "MRN: DEMO-TEST-REC2", "Current Medications:", "Aspirin 81mg oral once daily"]
    )
    resp = client.post(
        f"/api/patients/{patient['id']}/reports", files={"file": ("consult.pdf", pdf_bytes, "application/pdf")}
    )
    report_id = resp.json()["id"]

    _login_as(client, "viewer.rec2@example.com", UserRole.VIEWER)
    recon = client.get(f"/api/reports/{report_id}/medication-reconciliation")
    assert recon.status_code == 200
