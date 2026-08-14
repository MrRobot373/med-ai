"""Patient system tests — spec §133 acceptance criteria for Patient/Report(-adjacent).

Covers: patient CRUD/search/archive, encounters, conditions/allergies/medications
(including append-only medication history), the derived timeline, role-based write
authorization (viewer is read-only), and basic cross-patient data isolation.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole

PASSWORD = "correct-horse-battery-1"


def _login_as(client: TestClient, email: str, role: UserRole) -> User:
    db = SessionLocal()
    try:
        user = User(
            email=email,
            display_name=email.split("@")[0],
            password_hash=hash_password(PASSWORD),
            role=role,
            active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    finally:
        db.close()

    resp = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200
    return user


def _create_patient(client: TestClient, **overrides) -> dict:
    payload = {
        "first_name": "John",
        "last_name": "Demo",
        "date_of_birth": "1969-03-15",
        "sex": "male",
    }
    payload.update(overrides)
    resp = client.post("/api/patients", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- Patient CRUD / search -----------------------------------------------------------


def test_create_and_get_patient(client):
    _login_as(client, "doctor.patients1@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, first_name="Sarah", last_name="Chen")

    assert patient["mrn"].startswith("MRN-")
    assert patient["age"] > 0

    resp = client.get(f"/api/patients/{patient['id']}")
    assert resp.status_code == 200
    assert resp.json()["last_name"] == "Chen"


def test_get_unknown_patient_returns_404(client):
    _login_as(client, "doctor.patients2@example.com", UserRole.DOCTOR)
    resp = client.get("/api/patients/does-not-exist")
    assert resp.status_code == 404


def test_search_patients_by_name_and_mrn(client):
    _login_as(client, "doctor.patients3@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, first_name="Unique-Zara", last_name="Vasquez")

    by_name = client.get("/api/patients", params={"q": "Unique-Zara"})
    assert any(p["id"] == patient["id"] for p in by_name.json())

    by_mrn = client.get("/api/patients", params={"q": patient["mrn"]})
    assert any(p["id"] == patient["id"] for p in by_mrn.json())

    no_match = client.get("/api/patients", params={"q": "Nobody-Named-This-xyz"})
    assert no_match.json() == []


def test_archived_patients_excluded_by_default_and_included_when_requested(client):
    _login_as(client, "doctor.patients4@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, first_name="ArchiveMe-Unique", last_name="Test")

    client.post(f"/api/patients/{patient['id']}/archive")

    default_list = client.get("/api/patients", params={"q": "ArchiveMe-Unique"})
    assert default_list.json() == []

    with_archived = client.get("/api/patients", params={"q": "ArchiveMe-Unique", "include_archived": True})
    assert any(p["id"] == patient["id"] and p["archived"] for p in with_archived.json())


def test_update_patient_partial_fields_only(client):
    _login_as(client, "doctor.patients5@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, first_name="Before", last_name="Update")

    resp = client.patch(f"/api/patients/{patient['id']}", json={"phone": "555-0100"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["phone"] == "555-0100"
    assert body["first_name"] == "Before"  # untouched


def test_viewer_cannot_create_or_modify_patients(client):
    _login_as(client, "viewer.patients1@example.com", UserRole.VIEWER)

    create_resp = client.post(
        "/api/patients", json={"first_name": "X", "last_name": "Y", "date_of_birth": "1990-01-01", "sex": "male"}
    )
    assert create_resp.status_code == 403


def test_viewer_can_read_patients(client):
    _login_as(client, "doctor.patients6@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, first_name="Readable-Unique", last_name="Patient")
    client.post("/api/auth/logout")

    _login_as(client, "viewer.patients2@example.com", UserRole.VIEWER)
    resp = client.get(f"/api/patients/{patient['id']}")
    assert resp.status_code == 200


def test_unauthenticated_requests_are_rejected(client):
    resp = client.get("/api/patients")
    assert resp.status_code == 401


# --- Encounters ------------------------------------------------------------------


def test_create_encounter_and_sequential_numbering(client):
    _login_as(client, "doctor.enc1@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)

    first = client.post(
        f"/api/patients/{patient['id']}/encounters",
        json={"encounter_type": "outpatient", "chief_complaint": "blurry vision"},
    )
    second = client.post(f"/api/patients/{patient['id']}/encounters", json={"encounter_type": "telehealth"})

    assert first.status_code == 201
    assert first.json()["status"] == "active"
    assert first.json()["created_by"] is not None
    assert second.json()["encounter_number"] != first.json()["encounter_number"]

    listed = client.get(f"/api/patients/{patient['id']}/encounters")
    assert len(listed.json()) == 2


def test_update_encounter_status(client):
    _login_as(client, "doctor.enc2@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    encounter = client.post(f"/api/patients/{patient['id']}/encounters", json={"encounter_type": "outpatient"}).json()

    resp = client.patch(f"/api/encounters/{encounter['id']}", json={"status": "completed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


# --- Conditions / Allergies / Medications -----------------------------------------


def test_condition_lifecycle_resolve_sets_resolved_date(client):
    _login_as(client, "doctor.cond1@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)

    created = client.post(f"/api/patients/{patient['id']}/conditions", json={"display": "Cataract, right eye"})
    assert created.status_code == 201
    assert created.json()["status"] == "active"

    resolved = client.patch(f"/api/conditions/{created.json()['id']}", json={"status": "resolved"})
    assert resolved.status_code == 200
    assert resolved.json()["resolved_date"] is not None


def test_allergy_create_and_list(client):
    _login_as(client, "doctor.allergy1@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)

    resp = client.post(
        f"/api/patients/{patient['id']}/allergies",
        json={"substance": "Penicillin", "severity": "severe", "reaction": "anaphylaxis"},
    )
    assert resp.status_code == 201

    listed = client.get(f"/api/patients/{patient['id']}/allergies")
    assert len(listed.json()) == 1
    assert listed.json()[0]["substance"] == "Penicillin"


def test_medication_history_is_preserved_not_overwritten_on_stop(client):
    _login_as(client, "doctor.med1@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)

    created = client.post(
        f"/api/patients/{patient['id']}/medications",
        json={"medication_name": "Latanoprost", "dose": "0.005%", "frequency": "nightly"},
    )
    med_id = created.json()["id"]
    assert created.json()["active"] is True

    stopped = client.post(f"/api/medications/{med_id}/stop", json={})
    assert stopped.status_code == 200
    assert stopped.json()["active"] is False
    assert stopped.json()["stop_date"] is not None
    # Original prescribing details are untouched, not deleted (spec §36).
    assert stopped.json()["medication_name"] == "Latanoprost"
    assert stopped.json()["dose"] == "0.005%"


# --- Timeline ----------------------------------------------------------------------


def test_timeline_includes_events_from_all_sources_sorted_descending(client):
    _login_as(client, "doctor.timeline1@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)

    client.post(f"/api/patients/{patient['id']}/encounters", json={"encounter_type": "outpatient"})
    client.post(f"/api/patients/{patient['id']}/conditions", json={"display": "Glaucoma"})
    client.post(f"/api/patients/{patient['id']}/allergies", json={"substance": "Sulfa drugs"})
    client.post(
        f"/api/patients/{patient['id']}/medications", json={"medication_name": "Timolol", "frequency": "BID"}
    )

    resp = client.get(f"/api/patients/{patient['id']}/timeline")
    assert resp.status_code == 200
    events = resp.json()
    event_types = {e["event_type"] for e in events}
    assert {"encounter", "condition_recorded", "allergy_recorded", "medication_started"} <= event_types

    dates = [e["event_date"] for e in events]
    assert dates == sorted(dates, reverse=True)


# --- Cross-patient isolation (spec §16 principle, at the structured-data layer) -----


def test_conditions_are_scoped_to_their_own_patient(client):
    _login_as(client, "doctor.isolation1@example.com", UserRole.DOCTOR)
    patient_a = _create_patient(client, first_name="Isolation-A", last_name="Patient")
    patient_b = _create_patient(client, first_name="Isolation-B", last_name="Patient")

    client.post(f"/api/patients/{patient_a['id']}/conditions", json={"display": "Condition-Only-On-A"})

    b_conditions = client.get(f"/api/patients/{patient_b['id']}/conditions").json()
    assert all(c["display"] != "Condition-Only-On-A" for c in b_conditions)

    a_conditions = client.get(f"/api/patients/{patient_a['id']}/conditions").json()
    assert any(c["display"] == "Condition-Only-On-A" for c in a_conditions)
