"""Vision AI API endpoints — spec §104, §58-61. Real upload -> ingestion -> vision
analysis flow through the actual HTTP API, with `analyze_image`/`compare_images`
mocked per-test (real Ollama vision calls are verified live, not in unit tests,
matching Phase 08's established pattern)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.vision.analyzer import VisionComparison, VisionObservation
from tests.sample_documents import make_png_bytes

PASSWORD = "correct-horse-battery-3"
PNG_BYTES = make_png_bytes(["Fundus photo — left eye"])

_OBSERVATION = VisionObservation(
    image_type="fundus photograph",
    observations=["optic disc margins appear well-defined"],
    clinical_entities=["optic disc"],
    quality_limitations=["mild glare in the superior field"],
)


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
    payload = {"first_name": "Amara", "last_name": "Diallo", "date_of_birth": "1972-06-01", "sex": "female"}
    payload.update(overrides)
    resp = client.post("/api/patients", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _upload_image(client: TestClient, patient_id: str, filename: str = "fundus.png") -> dict:
    # Every test image shares identical bytes for simplicity — allow_duplicate skips
    # the (real, correctly-working) same-patient duplicate-file rejection that would
    # otherwise 409 on the second upload within a test.
    resp = client.post(
        f"/api/patients/{patient_id}/reports",
        files={"file": (filename, PNG_BYTES, "image/png")},
        params={"allow_duplicate": "true"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _mock_successful_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_analyze(*args, **kwargs):
        return _OBSERVATION

    monkeypatch.setattr("app.services.vision.analyze_image", fake_analyze)


def test_vision_analysis_404_for_a_report_analysis_was_never_run_against(client: TestClient):
    # A non-image report's mime type isn't in ingestion's auto-analyze set (only
    # image/DICOM reports trigger vision analysis automatically) and nothing here
    # explicitly calls POST .../vision/analyze — so no VisionAnalysis row exists at
    # all, distinct from the NOT_APPLICABLE row an explicit call would create.
    _login_as(client, "doctor.vision1@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    resp = client.post(
        f"/api/patients/{patient['id']}/reports",
        files={"file": ("note.docx", b"PK\x03\x04fake docx bytes", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert resp.status_code == 201, resp.text
    report = resp.json()

    get_resp = client.get(f"/api/reports/{report['id']}/vision")
    assert get_resp.status_code == 404


def test_image_upload_automatically_runs_vision_analysis(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    _mock_successful_analysis(monkeypatch)
    _login_as(client, "doctor.vision1b@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    report = _upload_image(client, patient["id"])

    # No explicit POST /analyze call — ingestion (ingestion/pipeline.py) triggers it
    # automatically for image/DICOM reports, same as OCR/lab extraction.
    resp = client.get(f"/api/reports/{report['id']}/vision")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    assert resp.json()["image_type"] == "fundus photograph"


def test_analyze_endpoint_returns_structured_result_and_persists_it(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    _mock_successful_analysis(monkeypatch)
    _login_as(client, "doctor.vision2@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    report = _upload_image(client, patient["id"])

    resp = client.post(f"/api/reports/{report['id']}/vision/analyze")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    assert body["image_type"] == "fundus photograph"
    assert body["observations"] == ["optic disc margins appear well-defined"]
    assert body["quality_limitations"] == ["mild glare in the superior field"]

    # And it's now persisted — a plain GET reflects the same result.
    get_resp = client.get(f"/api/reports/{report['id']}/vision")
    assert get_resp.status_code == 200
    assert get_resp.json()["image_type"] == "fundus photograph"


def test_analyze_endpoint_reports_not_applicable_for_a_non_image_report(client: TestClient):
    _login_as(client, "doctor.vision3@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    resp = client.post(
        f"/api/patients/{patient['id']}/reports",
        files={"file": ("note.docx", b"PK\x03\x04fake docx bytes", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert resp.status_code == 201, resp.text
    report = resp.json()

    analyze_resp = client.post(f"/api/reports/{report['id']}/vision/analyze")
    assert analyze_resp.status_code == 200
    assert analyze_resp.json()["status"] == "not_applicable"


def test_viewer_can_read_but_not_trigger_vision_analysis(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    _mock_successful_analysis(monkeypatch)
    _login_as(client, "doctor.vision4@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    report = _upload_image(client, patient["id"])
    client.post(f"/api/reports/{report['id']}/vision/analyze")

    _login_as(client, "viewer.vision4@example.com", UserRole.VIEWER)
    assert client.get(f"/api/reports/{report['id']}/vision").status_code == 200
    assert client.post(f"/api/reports/{report['id']}/vision/analyze").status_code == 403


def test_compare_endpoint_returns_findings_and_evidence(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_compare(*args, **kwargs):
        return VisionComparison(
            previous_findings=["baseline cupping"],
            current_findings=["increased cupping"],
            observable_changes=["cup-to-disc ratio increased"],
            differences=["cup-to-disc ratio increased from 0.4 to 0.6"],
            limitations=[],
        )

    monkeypatch.setattr("app.services.vision.compare_images", fake_compare)
    monkeypatch.setattr("app.services.vision.retrieve", lambda *a, **k: [])

    _login_as(client, "doctor.vision5@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    previous_report = _upload_image(client, patient["id"], "previous.png")
    current_report = _upload_image(client, patient["id"], "current.png")

    resp = client.post(
        f"/api/patients/{patient['id']}/vision/compare",
        json={"previous_report_id": previous_report["id"], "current_report_id": current_report["id"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["differences"] == ["cup-to-disc ratio increased from 0.4 to 0.6"]
    assert body["previous_report_id"] == previous_report["id"]
    assert body["current_report_id"] == current_report["id"]


def test_compare_endpoint_rejects_a_report_belonging_to_a_different_patient(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    _login_as(client, "doctor.vision6@example.com", UserRole.DOCTOR)
    patient_a = _create_patient(client, first_name="PatientA")
    patient_b = _create_patient(client, first_name="PatientB")
    report_a = _upload_image(client, patient_a["id"])
    report_b = _upload_image(client, patient_b["id"])

    resp = client.post(
        f"/api/patients/{patient_a['id']}/vision/compare",
        json={"previous_report_id": report_a["id"], "current_report_id": report_b["id"]},
    )
    assert resp.status_code == 422


def test_compare_endpoint_requires_write_role(client: TestClient):
    _login_as(client, "doctor.vision7@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    report_a = _upload_image(client, patient["id"], "a.png")
    report_b = _upload_image(client, patient["id"], "b.png")

    _login_as(client, "viewer.vision7@example.com", UserRole.VIEWER)
    resp = client.post(
        f"/api/patients/{patient['id']}/vision/compare",
        json={"previous_report_id": report_a["id"], "current_report_id": report_b["id"]},
    )
    assert resp.status_code == 403
