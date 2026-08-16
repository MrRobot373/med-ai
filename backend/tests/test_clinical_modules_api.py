"""Clinical modules API — RBAC, validation, and history endpoints (spec §104, §63).
Generation itself is mocked (real Ollama calls verified live, matching every prior
phase's established pattern)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.modules.differential import DifferentialSupport
from app.modules.entity_extraction import EntityExtractionResult, ExtractedEntity
from app.modules.soap import SOAPNote
from app.modules.summarizer import SummaryResult

PASSWORD = "correct-horse-battery-4"


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
    payload = {"first_name": "Grace", "last_name": "Bello", "date_of_birth": "1975-02-14", "sex": "female"}
    payload.update(overrides)
    resp = client.post("/api/patients", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_encounter(client: TestClient, patient_id: str) -> dict:
    resp = client.post(f"/api/patients/{patient_id}/encounters", json={"encounter_type": "outpatient", "chief_complaint": "Blurry vision"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_summary_requires_write_role(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake(summary_type, context, settings):
        return SummaryResult(summary="ok")

    monkeypatch.setattr("app.services.clinical_modules.summarizer_module.generate_summary", fake)
    _login_as(client, "doctor.cm1@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)

    _login_as(client, "viewer.cm1@example.com", UserRole.VIEWER)
    resp = client.post(f"/api/patients/{patient['id']}/clinical/summary", json={"summary_type": "concise"})
    assert resp.status_code == 403


def test_summary_end_to_end_and_history(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake(summary_type, context, settings):
        return SummaryResult(summary="Stable follow-up.", key_points=["stable"], source_trace=["patient facts"])

    monkeypatch.setattr("app.services.clinical_modules.summarizer_module.generate_summary", fake)
    _login_as(client, "doctor.cm2@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)

    resp = client.post(f"/api/patients/{patient['id']}/clinical/summary", json={"summary_type": "concise"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["module_type"] == "summary"
    assert body["payload"]["summary"] == "Stable follow-up."
    assert body["patient_id"] == patient["id"]

    history = client.get(f"/api/patients/{patient['id']}/clinical/runs").json()
    assert len(history) == 1
    assert history[0]["id"] == body["id"]

    filtered = client.get(f"/api/patients/{patient['id']}/clinical/runs?module_type=soap").json()
    assert filtered == []


def test_soap_requires_a_real_encounter_belonging_to_the_patient(client: TestClient):
    _login_as(client, "doctor.cm3@example.com", UserRole.DOCTOR)
    patient_a = _create_patient(client, first_name="PatientA")
    patient_b = _create_patient(client, first_name="PatientB")
    encounter_b = _create_encounter(client, patient_b["id"])

    resp = client.post(f"/api/patients/{patient_a['id']}/clinical/soap", json={"encounter_id": encounter_b["id"]})
    assert resp.status_code == 404


def test_soap_end_to_end(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake(context, settings):
        return SOAPNote(subjective={"cc": "blurry vision"}, assessment=["POAG"], plan=["continue latanoprost"])

    monkeypatch.setattr("app.services.clinical_modules.soap_module.generate_soap", fake)
    _login_as(client, "doctor.cm4@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    encounter = _create_encounter(client, patient["id"])

    resp = client.post(f"/api/patients/{patient['id']}/clinical/soap", json={"encounter_id": encounter["id"]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["payload"]["assessment"] == ["POAG"]


def test_entity_extraction_rejects_missing_report_and_encounter(client: TestClient):
    _login_as(client, "doctor.cm5@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)

    resp = client.post(f"/api/patients/{patient['id']}/clinical/entities", json={})
    assert resp.status_code == 422


def test_entity_extraction_end_to_end(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake(source_title, text, settings):
        return EntityExtractionResult(entities=[ExtractedEntity(text="Latanoprost", category="medication")])

    monkeypatch.setattr("app.services.clinical_modules.entity_module.extract_entities", fake)
    _login_as(client, "doctor.cm6@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    encounter = _create_encounter(client, patient["id"])

    resp = client.post(f"/api/patients/{patient['id']}/clinical/entities", json={"encounter_id": encounter["id"]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["payload"]["entities"][0]["text"] == "Latanoprost"


def test_differential_end_to_end(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.clinical_modules.retrieve", lambda *a, **k: [])

    async def fake(patient_facts, labeled, settings):
        return DifferentialSupport(patient_summary="Case summary.", evidence_quality="Insufficient retrieved evidence.")

    monkeypatch.setattr("app.services.clinical_modules.differential_module.generate_differential", fake)
    _login_as(client, "doctor.cm7@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)

    resp = client.post(f"/api/patients/{patient['id']}/clinical/differential", json={})
    assert resp.status_code == 200, resp.text
    assert resp.json()["payload"]["patient_summary"] == "Case summary."


def test_guideline_qa_is_not_patient_scoped_and_lists_globally(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.clinical_modules.retrieve", lambda *a, **k: [])
    _login_as(client, "doctor.cm8@example.com", UserRole.DOCTOR)

    resp = client.post("/api/clinical/guideline-qa", json={"question": "What is the treatment for glaucoma?"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["patient_id"] is None
    assert body["payload"]["no_guideline_found"] is True

    history = client.get("/api/clinical/runs?module_type=guideline_qa").json()
    assert any(r["id"] == body["id"] for r in history)

    fetched = client.get(f"/api/clinical/runs/{body['id']}").json()
    assert fetched["id"] == body["id"]


def test_report_comparison_requires_both_reports_to_belong_to_the_url_patient(client: TestClient):
    _login_as(client, "doctor.cm9@example.com", UserRole.DOCTOR)
    patient_a = _create_patient(client, first_name="PatientA")
    patient_b = _create_patient(client, first_name="PatientB")
    report_a = client.post(f"/api/patients/{patient_a['id']}/reports", files={"file": ("a.pdf", b"%PDF-1.4 fake", "application/pdf")}).json()
    report_b = client.post(f"/api/patients/{patient_b['id']}/reports", files={"file": ("b.pdf", b"%PDF-1.4 fake", "application/pdf")}).json()

    resp = client.post(
        f"/api/patients/{patient_a['id']}/clinical/report-comparison",
        json={"previous_report_id": report_a["id"], "current_report_id": report_b["id"]},
    )
    assert resp.status_code == 404
