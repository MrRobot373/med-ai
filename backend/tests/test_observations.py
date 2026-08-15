"""Observations/trends API — spec §33, end-to-end through the real ingestion pipeline
(upload -> extraction -> persisted Observation rows -> API), not just the extraction
unit tests in `test_labs.py`.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from tests.sample_documents import make_xlsx_bytes

PASSWORD = "correct-horse-battery-6"


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
    payload = {"first_name": "Elena", "last_name": "Novak", "date_of_birth": "1971-03-14", "sex": "female"}
    payload.update(overrides)
    resp = client.post("/api/patients", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _upload_xlsx(client: TestClient, patient_id: str, filename: str, rows: list[list]) -> dict:
    content = make_xlsx_bytes(sheet_name="Panel", rows=rows)
    resp = client.post(
        f"/api/patients/{patient_id}/reports",
        files={"file": (filename, content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


_METABOLIC_ROWS = [
    ["Patient Name", "Elena Novak"],
    ["MRN", "DEMO-TEST-OBS"],
    ["Collection Date", "2026-08-10"],
    [],
    ["Test", "Result", "Unit", "Reference Range"],
    ["HbA1c", 8.1, "%", "4.0-5.6"],
    ["Fasting Glucose", 168, "mg/dL", "70-99"],
]


def test_upload_persists_observations_traceable_to_the_report(client: TestClient):
    _login_as(client, "doctor.obs1@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, mrn="DEMO-TEST-OBS")
    report = _upload_xlsx(client, patient["id"], "labs.xlsx", _METABOLIC_ROWS)

    resp = client.get(f"/api/patients/{patient['id']}/observations")
    assert resp.status_code == 200
    observations = resp.json()
    by_name = {o["normalized_name"]: o for o in observations}

    assert by_name["hba1c"]["value_numeric"] == 8.1
    assert by_name["hba1c"]["abnormal_flag"] is True
    assert by_name["hba1c"]["report_id"] == report["id"]
    assert by_name["hba1c"]["measured_at"] == "2026-08-10"
    assert by_name["glucose"]["value_numeric"] == 168.0


def test_trends_group_by_normalized_name_and_are_chart_ready(client: TestClient):
    _login_as(client, "doctor.obs2@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, mrn="DEMO-TEST-OBS2")
    _upload_xlsx(client, patient["id"], "labs.xlsx", _METABOLIC_ROWS)

    resp = client.get(f"/api/patients/{patient['id']}/observations/trends")
    assert resp.status_code == 200
    trends = {t["normalized_name"]: t for t in resp.json()}

    assert trends["hba1c"]["unit"] == "%"
    assert trends["hba1c"]["unit_conflict"] is False
    assert len(trends["hba1c"]["points"]) == 1
    assert trends["hba1c"]["points"][0]["value_numeric"] == 8.1


def test_incompatible_units_are_excluded_from_the_trend_not_silently_compared(client: TestClient):
    # Two reports for the same patient, both mentioning "IOP" (no trusted conversion
    # registered for IOP at all) with a unit typo/variant the second time — the trend
    # must not merge these two into one misleading numeric series.
    _login_as(client, "doctor.obs3@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, mrn="DEMO-TEST-OBS3")
    _upload_xlsx(
        client,
        patient["id"],
        "iop1.xlsx",
        [["Test", "Result", "Unit", "Reference Range"], ["IOP", 16, "mmHg", "<21"]],
    )
    _upload_xlsx(
        client,
        patient["id"],
        "iop2.xlsx",
        [["Test", "Result", "Unit", "Reference Range"], ["IOP", 2.1, "kPa", "<2.8"]],
    )

    resp = client.get(f"/api/patients/{patient['id']}/observations/trends")
    trends = {t["normalized_name"]: t for t in resp.json()}

    assert trends["iop"]["unit_conflict"] is True
    assert "kPa" in trends["iop"]["excluded_units"]
    # The mmHg reading is still shown; the kPa one is excluded rather than compared.
    assert len(trends["iop"]["points"]) == 1
    assert trends["iop"]["points"][0]["unit"] == "mmHg"

    # Nothing is actually hidden from the clinician — the raw list still has both.
    raw = client.get(f"/api/patients/{patient['id']}/observations").json()
    assert {o["unit"] for o in raw if o["normalized_name"] == "iop"} == {"mmHg", "kPa"}


def test_trusted_conversion_merges_glucose_across_units(client: TestClient):
    _login_as(client, "doctor.obs4@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, mrn="DEMO-TEST-OBS4")
    _upload_xlsx(
        client,
        patient["id"],
        "g1.xlsx",
        [["Test", "Result", "Unit", "Reference Range"], ["Glucose", 100, "mg/dL", "70-99"]],
    )
    _upload_xlsx(
        client,
        patient["id"],
        "g2.xlsx",
        [["Test", "Result", "Unit", "Reference Range"], ["Glucose", 6.0, "mmol/L", "3.9-5.5"]],
    )

    resp = client.get(f"/api/patients/{patient['id']}/observations/trends")
    trends = {t["normalized_name"]: t for t in resp.json()}

    assert trends["glucose"]["unit_conflict"] is False
    assert len(trends["glucose"]["points"]) == 2


def test_viewer_can_read_observations(client: TestClient):
    _login_as(client, "doctor.obs5@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, mrn="DEMO-TEST-OBS5")
    _upload_xlsx(client, patient["id"], "labs.xlsx", _METABOLIC_ROWS)

    _login_as(client, "viewer.obs5@example.com", UserRole.VIEWER)
    resp = client.get(f"/api/patients/{patient['id']}/observations")
    assert resp.status_code == 200
    assert len(resp.json()) > 0
