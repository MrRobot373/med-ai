"""Change engine API — spec §35 "an actual backend change engine." Seeds
conditions/medications/allergies/observations directly (this is deterministic DB
comparison, not something that needs to go through report ingestion) and checks the
diff against a `since` date via the real API.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.db.session import SessionLocal
from app.models.allergy import Allergy
from app.models.condition import Condition, ConditionStatus
from app.models.medication import Medication
from app.models.observation import ExtractionMethod, Observation
from app.models.user import User, UserRole

PASSWORD = "correct-horse-battery-8"
SINCE = date(2026, 7, 1)


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


def _seed_scenario(patient_id: str) -> None:
    db = SessionLocal()
    try:
        db.add(Condition(patient_id=patient_id, display="Glaucoma", status=ConditionStatus.ACTIVE, onset_date=date(2020, 1, 1)))
        db.add(
            Condition(
                patient_id=patient_id,
                display="Conjunctivitis",
                status=ConditionStatus.RESOLVED,
                onset_date=date(2026, 7, 10),
                resolved_date=date(2026, 7, 20),
            )
        )
        db.add(
            Medication(
                patient_id=patient_id, medication_name="Timolol 0.25%", dose="1 drop",
                active=False, start_date=date(2025, 1, 1), stop_date=date(2026, 7, 5),
            )
        )
        db.add(
            Medication(
                patient_id=patient_id, medication_name="Timolol 0.5%", dose="1 drop",
                active=True, start_date=date(2026, 7, 5),
            )
        )
        db.add(
            Medication(
                patient_id=patient_id, medication_name="Brimonidine", dose="1 drop",
                active=True, start_date=date(2026, 7, 12),
            )
        )
        db.add(Allergy(patient_id=patient_id, substance="Sulfa drugs", created_at=datetime(2026, 7, 25, tzinfo=UTC)))
        db.add(
            Observation(
                patient_id=patient_id, observation_name="IOP", normalized_name="iop",
                value_numeric=16, unit="mmHg", measured_at=date(2026, 6, 1),
                extraction_method=ExtractionMethod.MANUAL,
            )
        )
        db.add(
            Observation(
                patient_id=patient_id, observation_name="IOP", normalized_name="iop",
                value_numeric=22, unit="mmHg", measured_at=date(2026, 7, 20),
                extraction_method=ExtractionMethod.MANUAL,
            )
        )
        db.commit()
    finally:
        db.close()


def test_changes_since_date_reports_new_resolved_started_stopped_dose_changed(client: TestClient):
    _login_as(client, "doctor.chg1@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, mrn="DEMO-TEST-CHG1")
    _seed_scenario(patient["id"])

    resp = client.get(f"/api/patients/{patient['id']}/changes", params={"since": SINCE.isoformat()})
    assert resp.status_code == 200
    summary = resp.json()

    assert {c["display"] for c in summary["conditions_resolved"]} == {"Conjunctivitis"}
    assert {c["display"] for c in summary["conditions_new"]} == {"Conjunctivitis"}

    assert {m["medication_name"] for m in summary["medications_started"]} == {"Brimonidine"}
    assert summary["medications_stopped"] == []  # Timolol's stop was paired into a dose change, not a bare stop
    dose_changes = summary["medications_dose_changed"]
    assert len(dose_changes) == 1
    assert dose_changes[0]["previous_medication_name"] == "Timolol 0.25%"
    assert dose_changes[0]["current_medication_name"] == "Timolol 0.5%"

    assert {a["substance"] for a in summary["allergies_new"]} == {"Sulfa drugs"}

    obs_changes = summary["observations_changed"]
    assert len(obs_changes) == 1
    assert obs_changes[0]["normalized_name"] == "iop"
    assert obs_changes[0]["direction"] == "increased"
    assert obs_changes[0]["previous_value"] == 16.0
    assert obs_changes[0]["current_value"] == 22.0


def test_changes_requires_since_param(client: TestClient):
    _login_as(client, "doctor.chg2@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, mrn="DEMO-TEST-CHG2")
    resp = client.get(f"/api/patients/{patient['id']}/changes")
    assert resp.status_code == 422  # never silently defaulted to an invented window


def test_viewer_can_read_changes(client: TestClient):
    _login_as(client, "doctor.chg3@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, mrn="DEMO-TEST-CHG3")
    _seed_scenario(patient["id"])

    _login_as(client, "viewer.chg3@example.com", UserRole.VIEWER)
    resp = client.get(f"/api/patients/{patient['id']}/changes", params={"since": SINCE.isoformat()})
    assert resp.status_code == 200
