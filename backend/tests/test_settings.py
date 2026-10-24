import json

from sqlalchemy import select

from app import db as app_db
from app.models import AppSetting


def test_secret_is_encrypted_at_rest_and_masked(admin):
    r = admin.put(
        "/api/settings/llm",
        json={
            "provider": "openai",
            "base_url": "https://api.example.com/v1",
            "api_key": "sk-supersecret-123456",
            "model": "gpt-x",
        },
    )
    assert r.status_code == 200
    llm = r.json()["llm"]
    assert "api_key" not in llm
    assert llm["has_api_key"] is True
    assert llm["api_key_preview"].endswith("3456")
    raw = json.dumps(app_db.SessionLocal().scalars(select(AppSetting)).first().value)
    assert "sk-supersecret-123456" not in raw


def test_omitted_secret_is_kept_and_empty_string_clears(admin):
    admin.put("/api/settings/llm", json={"api_key": "sk-keepme-000000"})
    r = admin.put("/api/settings/llm", json={"model": "other-model"})
    assert r.json()["llm"]["has_api_key"] is True
    r = admin.put("/api/settings/llm", json={"api_key": ""})
    assert r.json()["llm"]["has_api_key"] is False


def test_validation_errors_are_reported(admin):
    r = admin.put("/api/settings/llm", json={"temperature": 9})
    assert r.status_code == 422
    assert admin.put("/api/settings/nonsense", json={}).status_code == 400


def test_retrieval_profiles(admin):
    r = admin.put("/api/settings/retrieval", json={"profile": "thorough"})
    ret = r.json()["retrieval"]
    assert ret["final_top_k"] == 12 and ret["dense_top_k"] == 80
    r = admin.put("/api/settings/retrieval", json={"final_top_k": 5})
    assert r.json()["retrieval"]["profile"] == "custom"


def test_changing_embedding_model_requires_reindex(admin):
    from tests.conftest import create_patient, lab_pdf, upload

    p = create_patient(admin)
    upload(admin, p["id"], lab_pdf("Alice Tester", "T-100", [("HbA1c", "7.0", "%", "4.0-5.6")]))
    view = admin.get("/api/settings").json()
    assert view["index_status"]["reindex_required"] is False
    view = admin.put("/api/settings/embeddings", json={"model": "another-embedder"}).json()
    assert view["index_status"]["reindex_required"] is True
    r = admin.post("/api/settings/reindex")
    assert r.status_code == 200


def test_connection_test_reports_failure_not_crash(admin):
    r = admin.post("/api/settings/test/vector_store", json={"overrides": {}})
    assert r.status_code == 200 and r.json()["ok"] is True
    r = admin.post(
        "/api/settings/models", json={"section": "llm", "provider": "ollama", "base_url": "http://127.0.0.1:1"}
    )
    assert r.json()["ok"] is False


def test_settings_saved_by_another_process_are_picked_up(admin, monkeypatch):
    from app.db import SessionLocal
    from app.models import AppSetting
    from app.services import runtime_config

    monkeypatch.setattr(runtime_config, "_RECHECK_SECONDS", 0)
    db = SessionLocal()
    try:
        runtime_config.load(db)
        row = db.get(AppSetting, "runtime")
        row.value = {**row.value, "llm": {**row.value["llm"], "model": "set-elsewhere"}}  # as a CLI command would
        db.commit()
        assert runtime_config.load(db).llm.model == "set-elsewhere"
        assert admin.get("/api/settings").json()["llm"]["model"] == "set-elsewhere"
    finally:
        db.close()
