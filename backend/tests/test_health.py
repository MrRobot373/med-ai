"""Health endpoints must reflect real, live-checked status — never a hardcoded "Ready".

These tests intentionally do NOT require Qdrant/Ollama to be running: they assert the
endpoint always returns a well-formed, honest response (including a "degraded" status
when a dependency is down), matching spec §84/§85/§103.
"""

from __future__ import annotations

from app.db.session import check_database_reachable
from app.integrations.ollama_client import _model_name_matches


def test_database_is_reachable_after_schema_creation():
    reachable, error = check_database_reachable()
    assert reachable is True
    assert error is None


def test_overall_health_endpoint_shape(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()

    assert body["status"] in ("ok", "degraded")
    assert isinstance(body["database"]["reachable"], bool)
    assert isinstance(body["ollama"]["reachable"], bool)
    assert body["ollama"]["configured_model"]  # never empty/absent
    assert isinstance(body["qdrant"]["reachable"], bool)

    # This test's own SQLite DB is always reachable regardless of Docker/Ollama state.
    assert body["database"]["reachable"] is True


def test_ollama_health_endpoint_never_fabricates_model_availability(client):
    resp = client.get("/api/health/ollama")
    assert resp.status_code == 200
    body = resp.json()
    if not body["reachable"]:
        # Honest failure: no model can be "available" if the service itself is down.
        assert body["model_available"] is False
        assert body["error"]


def test_qdrant_health_endpoint_shape(client):
    resp = client.get("/api/health/qdrant")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["reachable"], bool)
    assert isinstance(body["collections"], list)


def test_models_health_reports_honest_not_loaded_status(client):
    resp = client.get("/api/health/models")
    assert resp.status_code == 200
    body = resp.json()
    # Neither embedding nor reranker should ever claim "ready"/"loaded" in Phase 01 —
    # they are lazily loaded starting in Phase 07, so the only truthful values here are:
    assert body["embedding"]["status"] in ("not_loaded", "package_missing")
    assert body["reranker"]["status"] in ("not_loaded", "package_missing")


def test_model_name_matching_exact():
    assert _model_name_matches("qwen3.5:9b", ["qwen3.5:9b", "gemma4:e4b"]) is True


def test_model_name_matching_default_tag():
    assert _model_name_matches("qwen3.5", ["qwen3.5:latest"]) is True


def test_model_name_matching_rejects_unrelated_model():
    # Critical per spec §4: never silently treat an unrelated installed model as a match.
    assert _model_name_matches("qwen3.5:9b", ["gemma4:e4b", "ornith:9b"]) is False
