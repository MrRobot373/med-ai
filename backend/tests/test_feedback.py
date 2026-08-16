"""Feedback (spec §81, Phase 13): submit/upsert, visibility rules per target type, and
the admin-only review list.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.db.session import SessionLocal
from app.models.clinical_module_run import ClinicalModuleRun, ClinicalModuleType
from app.models.user import User, UserRole

PASSWORD = "correct-horse-battery-8"


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


@pytest.fixture(autouse=True)
def _mock_generation(monkeypatch: pytest.MonkeyPatch):
    async def fake_stream(messages, settings, temperature=None):
        for token in ["An ", "answer."]:
            yield token

    monkeypatch.setattr("app.services.chat.generate_stream", fake_stream)
    monkeypatch.setattr("app.chat.orchestrator.retrieve", lambda *a, **k: [])

    async def fake_grounding(answer_text, evidence, settings):
        return None

    monkeypatch.setattr("app.chat.orchestrator.validate_grounding", fake_grounding)


def _send_message(client: TestClient) -> str:
    """Returns the assistant message id from a fresh general-scope conversation."""
    conversation = client.post("/api/conversations", json={"scope": "general"}).json()
    client.post(f"/api/conversations/{conversation['id']}/messages", json={"text": "hi"})
    messages = client.get(f"/api/conversations/{conversation['id']}/messages").json()
    return next(m["id"] for m in messages if m["role"] == "assistant")


def _make_module_run() -> str:
    db = SessionLocal()
    try:
        run = ClinicalModuleRun(id=str(uuid.uuid4()), module_type=ClinicalModuleType.SUMMARY, payload='{"x": 1}')
        db.add(run)
        db.commit()
        return run.id
    finally:
        db.close()


def test_submit_and_refetch_own_feedback_on_a_message(client: TestClient):
    _login_as(client, "doctor.fb1@example.com", UserRole.DOCTOR)
    message_id = _send_message(client)

    resp = client.post("/api/feedback", json={"target_type": "message", "target_id": message_id, "rating": "helpful"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["rating"] == "helpful"

    mine = client.get("/api/feedback/mine", params={"target_type": "message", "target_id": message_id})
    assert mine.status_code == 200
    assert mine.json()["rating"] == "helpful"


def test_resubmitting_feedback_upserts_rather_than_duplicates(client: TestClient):
    _login_as(client, "doctor.fb2@example.com", UserRole.DOCTOR)
    message_id = _send_message(client)

    first = client.post(
        "/api/feedback", json={"target_type": "message", "target_id": message_id, "rating": "helpful"}
    ).json()
    second = client.post(
        "/api/feedback",
        json={"target_type": "message", "target_id": message_id, "rating": "incorrect", "comment": "wrong drug name"},
    ).json()

    assert first["id"] == second["id"]
    assert second["rating"] == "incorrect"
    assert second["comment"] == "wrong drug name"


def test_cannot_give_feedback_on_another_users_private_message(client: TestClient):
    _login_as(client, "doctor.fb3a@example.com", UserRole.DOCTOR)
    message_id = _send_message(client)

    _login_as(client, "doctor.fb3b@example.com", UserRole.DOCTOR)
    resp = client.post("/api/feedback", json={"target_type": "message", "target_id": message_id, "rating": "helpful"})
    assert resp.status_code == 404


def test_unknown_message_target_404s(client: TestClient):
    _login_as(client, "doctor.fb4@example.com", UserRole.DOCTOR)
    resp = client.post("/api/feedback", json={"target_type": "message", "target_id": "does-not-exist", "rating": "helpful"})
    assert resp.status_code == 404


def test_clinical_module_run_target_is_chart_visible_not_owner_restricted(client: TestClient):
    """ClinicalModuleRun drafts are chart-visible to any clinician (Phase 10's own
    convention) — unlike private chat messages, any authenticated doctor can react."""
    run_id = _make_module_run()
    _login_as(client, "doctor.fb5a@example.com", UserRole.DOCTOR)
    assert client.post("/api/feedback", json={"target_type": "clinical_module_run", "target_id": run_id, "rating": "helpful"}).status_code == 201

    _login_as(client, "doctor.fb5b@example.com", UserRole.DOCTOR)
    resp = client.post(
        "/api/feedback", json={"target_type": "clinical_module_run", "target_id": run_id, "rating": "outdated_evidence"}
    )
    assert resp.status_code == 201  # a second clinician's own, separate feedback row


def test_viewer_can_submit_feedback_but_not_review_all(client: TestClient):
    run_id = _make_module_run()
    _login_as(client, "viewer.fb6@example.com", UserRole.VIEWER)
    assert client.post("/api/feedback", json={"target_type": "clinical_module_run", "target_id": run_id, "rating": "helpful"}).status_code == 201
    assert client.get("/api/feedback").status_code == 403


def test_admin_can_list_all_feedback_filtered_by_rating(client: TestClient):
    run_id = _make_module_run()
    _login_as(client, "doctor.fb7@example.com", UserRole.DOCTOR)
    client.post("/api/feedback", json={"target_type": "clinical_module_run", "target_id": run_id, "rating": "missing_evidence"})

    _login_as(client, "admin.fb7@example.com", UserRole.ADMIN)
    resp = client.get("/api/feedback", params={"rating": "missing_evidence"})
    assert resp.status_code == 200
    assert any(r["target_id"] == run_id for r in resp.json())
