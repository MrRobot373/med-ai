"""Web Research API — RBAC, status honesty, and validation (spec §104, §64-72).
Real generation/network calls are mocked (verified live, matching every other phase's
established pattern)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.research.paper_assistant import ResearchSynthesis

PASSWORD = "correct-horse-battery-5"


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
def _mock_retrieval(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.research.retrieve", lambda *a, **k: [])


def test_status_reports_disabled_by_default(client: TestClient):
    _login_as(client, "doctor.research1@example.com", UserRole.DOCTOR)
    resp = client.get("/api/research/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["sources_available"] == []


def test_status_reports_enabled_and_available_sources_when_turned_on(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from app.config.settings import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_research", True)
    # SearXNG's own reachability is checked live, separately from ENABLE_RESEARCH —
    # forced False here so this test doesn't depend on optional infra actually running.
    monkeypatch.setattr("app.services.research.searxng_reachable", lambda s: False)

    _login_as(client, "doctor.research2@example.com", UserRole.DOCTOR)
    resp = client.get("/api/research/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert body["searxng_reachable"] is False
    assert set(body["sources_available"]) == {"pubmed", "fda", "clinicaltrials"}


def test_query_requires_write_role(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_synthesis(*args, **kwargs):
        return ResearchSynthesis(evidence_summary="Answer.")

    monkeypatch.setattr("app.services.research.generate_research_synthesis", fake_synthesis)
    _login_as(client, "viewer.research3@example.com", UserRole.VIEWER)
    resp = client.post("/api/research/query", json={"question": "What is the treatment for glaucoma?"})
    assert resp.status_code == 403


def test_query_local_only_end_to_end(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_synthesis(question, patient_block, local_block, external_block, settings):
        assert "Research Mode not enabled" in external_block
        return ResearchSynthesis(evidence_summary="Local synthesis only.", consensus="No consensus without more evidence.")

    monkeypatch.setattr("app.services.research.generate_research_synthesis", fake_synthesis)
    _login_as(client, "doctor.research4@example.com", UserRole.DOCTOR)

    resp = client.post("/api/research/query", json={"question": "What is the treatment for glaucoma?"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["module_type"] == "research"
    assert body["payload"]["evidence_summary"] == "Local synthesis only."
    assert body["payload"]["research_mode_used"] is False


def test_query_rejects_external_sources_when_research_mode_disabled(client: TestClient):
    _login_as(client, "doctor.research5@example.com", UserRole.DOCTOR)
    resp = client.post("/api/research/query", json={"question": "latest evidence for drug X", "sources": ["pubmed"]})
    assert resp.status_code == 422


def test_query_with_unknown_patient_id_404s(client: TestClient):
    _login_as(client, "doctor.research6@example.com", UserRole.DOCTOR)
    resp = client.post("/api/research/query", json={"question": "anything", "patient_id": "does-not-exist"})
    assert resp.status_code == 404


def test_runs_history_lists_completed_queries(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_synthesis(*args, **kwargs):
        return ResearchSynthesis(evidence_summary="An answer.")

    monkeypatch.setattr("app.services.research.generate_research_synthesis", fake_synthesis)
    _login_as(client, "doctor.research7@example.com", UserRole.DOCTOR)

    created = client.post("/api/research/query", json={"question": "What is the treatment for glaucoma?"}).json()
    history = client.get("/api/research/runs").json()
    assert any(r["id"] == created["id"] for r in history)


def test_query_with_external_sources_logs_research_mode_and_external_search_audit_events(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from app.config.settings import get_settings
    from app.models.web_cache import AuthorityTier, WebSource
    from app.research.providers.base import WebResult

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_research", True)

    async def pubmed_provider(query, settings, max_results):
        return [WebResult(title="A", url="https://pubmed.ncbi.nlm.nih.gov/1/", text="glaucoma evidence", source=WebSource.PUBMED, authority_tier=AuthorityTier.C)]

    monkeypatch.setattr("app.services.research._PROVIDERS", {WebSource.PUBMED: pubmed_provider})

    async def fake_synthesis(question, patient_block, local_block, external_block, settings):
        return ResearchSynthesis(evidence_summary="Evidence from PubMed [W1].", consensus="")

    monkeypatch.setattr("app.services.research.generate_research_synthesis", fake_synthesis)

    user = _login_as(client, "doctor.research9@example.com", UserRole.DOCTOR)
    resp = client.post(
        "/api/research/query", json={"question": "What is the treatment for glaucoma?", "sources": ["pubmed"]}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["payload"]["research_mode_used"] is True

    _login_as(client, "admin.research9@example.com", UserRole.ADMIN)
    enabled_rows = client.get("/api/audit", params={"action": "research_mode_enabled", "user_id": user.id}).json()
    assert len(enabled_rows) == 1
    assert enabled_rows[0]["detail"]["sources"] == ["pubmed"]

    executed_rows = client.get("/api/audit", params={"action": "external_search_executed", "user_id": user.id}).json()
    assert len(executed_rows) == 1
    assert executed_rows[0]["detail"]["web_source_counts"] == {"PUBMED": 1}


def test_viewer_can_read_status_and_history(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_synthesis(*args, **kwargs):
        return ResearchSynthesis(evidence_summary="An answer.")

    monkeypatch.setattr("app.services.research.generate_research_synthesis", fake_synthesis)
    _login_as(client, "doctor.research8@example.com", UserRole.DOCTOR)
    client.post("/api/research/query", json={"question": "What is the treatment for glaucoma?"})

    _login_as(client, "viewer.research8@example.com", UserRole.VIEWER)
    assert client.get("/api/research/status").status_code == 200
    assert client.get("/api/research/runs").status_code == 200
