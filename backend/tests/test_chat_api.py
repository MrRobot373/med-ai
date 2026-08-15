"""Chat API — conversation CRUD, RBAC, scope validation, and the streaming endpoint
(with generation mocked — real Ollama streaming is verified live, not in unit tests).
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.db.session import SessionLocal
from app.models.chunk import ChunkCollection
from app.models.user import User, UserRole

PASSWORD = "correct-horse-battery-9"


def _parse_sse_events(raw_text: str) -> list[dict]:
    events = []
    for line in raw_text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


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


@pytest.fixture(autouse=True)
def _mock_generation(monkeypatch: pytest.MonkeyPatch):
    """No real Ollama call in the fast test suite — mirrors the RAG-indexing mock's
    rationale in conftest.py, just scoped to this file since chat generation isn't
    triggered by unrelated flows the way indexing was."""

    async def fake_stream(messages, settings, temperature=None):
        for token in ["This ", "is ", "a ", "test ", "answer."]:
            yield token

    monkeypatch.setattr("app.services.chat.generate_stream", fake_stream)
    monkeypatch.setattr("app.chat.orchestrator.retrieve", lambda *a, **k: [])

    async def fake_grounding(answer_text, evidence, settings):
        return None

    monkeypatch.setattr("app.chat.orchestrator.validate_grounding", fake_grounding)


def test_create_and_list_conversation(client: TestClient):
    _login_as(client, "doctor.chat1@example.com", UserRole.DOCTOR)
    resp = client.post("/api/conversations", json={"scope": "general"})
    assert resp.status_code == 201, resp.text
    conversation = resp.json()
    assert conversation["scope"] == "general"
    assert conversation["title"] is None

    listed = client.get("/api/conversations").json()
    assert any(c["id"] == conversation["id"] for c in listed)


def test_unimplemented_scope_is_rejected(client: TestClient):
    _login_as(client, "doctor.chat2@example.com", UserRole.DOCTOR)
    resp = client.post("/api/conversations", json={"scope": "research_mode"})
    assert resp.status_code == 422
    resp2 = client.post("/api/conversations", json={"scope": "selected_reports_comparison"})
    assert resp2.status_code == 422


def test_viewer_can_read_but_not_create_or_send(client: TestClient):
    _login_as(client, "doctor.chat3@example.com", UserRole.DOCTOR)
    conversation = client.post("/api/conversations", json={"scope": "general"}).json()

    _login_as(client, "viewer.chat3@example.com", UserRole.VIEWER)
    assert client.get("/api/conversations").status_code == 200
    assert client.post("/api/conversations", json={"scope": "general"}).status_code == 403
    assert client.post(f"/api/conversations/{conversation['id']}/messages", json={"text": "hi"}).status_code == 403


def test_conversation_not_visible_to_a_different_user(client: TestClient):
    _login_as(client, "doctor.chat4a@example.com", UserRole.DOCTOR)
    conversation = client.post("/api/conversations", json={"scope": "general"}).json()

    _login_as(client, "doctor.chat4b@example.com", UserRole.DOCTOR)
    resp = client.get(f"/api/conversations/{conversation['id']}")
    assert resp.status_code == 404


def test_send_message_streams_and_persists(client: TestClient):
    _login_as(client, "doctor.chat5@example.com", UserRole.DOCTOR)
    conversation = client.post("/api/conversations", json={"scope": "general"}).json()

    # "hi" matches the greeting classifier (general_conversation, no retrieval needed)
    # so this exercises the real streaming-generation path, not abstention — that's
    # covered separately below.
    resp = client.post(f"/api/conversations/{conversation['id']}/messages", json={"text": "hi"})
    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    token_events = [e for e in events if e["type"] == "token"]
    assert "".join(e["content"] for e in token_events) == "This is a test answer."
    assert events[-1]["type"] == "final"

    messages = client.get(f"/api/conversations/{conversation['id']}/messages").json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "hi"
    assert messages[1]["content"] == "This is a test answer."


def test_abstention_when_scope_has_nothing_to_answer_from(client: TestClient):
    _login_as(client, "doctor.chat6@example.com", UserRole.DOCTOR)
    conversation = client.post("/api/conversations", json={"scope": "local_knowledge_only"}).json()

    resp = client.post(f"/api/conversations/{conversation['id']}/messages", json={"text": "What is the treatment for glaucoma?"})
    assert resp.status_code == 200
    assert "Insufficient evidence" in resp.text

    messages = client.get(f"/api/conversations/{conversation['id']}/messages").json()
    assert messages[1]["content"].startswith("Insufficient evidence")


def test_patient_scoped_conversation_never_leaks_another_patients_evidence(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Chat-layer version of spec §14's isolation guarantee: even if retrieve() is
    (hypothetically, via a bug) asked for the wrong patient, the conversation's own
    patient_id is what's actually passed through — verified here by asserting the
    patient_id retrieve() receives always matches the conversation's, never anything
    else, across every call the turn makes."""
    _login_as(client, "doctor.chat7@example.com", UserRole.DOCTOR)
    patient_a = _create_patient(client, first_name="PatientA", mrn="ISO-A")
    patient_b = _create_patient(client, first_name="PatientB", mrn="ISO-B")

    seen_patient_ids = []

    def spy_retrieve(db, query, settings, collection=None, patient_id=None, max_per_source=3):
        if collection == ChunkCollection.PATIENT_DOCUMENTS:
            seen_patient_ids.append(patient_id)
        return []

    monkeypatch.setattr("app.chat.orchestrator.retrieve", spy_retrieve)

    conversation = client.post(
        "/api/conversations", json={"scope": "current_patient", "patient_id": patient_b["id"]}
    ).json()
    client.post(f"/api/conversations/{conversation['id']}/messages", json={"text": "What medications is this patient on?"})

    assert seen_patient_ids, "patient_documents retrieval was never called"
    assert all(pid == patient_b["id"] for pid in seen_patient_ids)
    assert patient_a["id"] not in seen_patient_ids
