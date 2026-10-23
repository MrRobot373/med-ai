import json

import pytest

from app import db as app_db
from app.rag import lexical
from tests.conftest import create_patient, lab_pdf, upload


def _events(resp_text: str) -> list[tuple[str, dict]]:
    out = []
    for block in resp_text.strip().split("\n\n"):
        lines = block.splitlines()
        ev = next(line[7:] for line in lines if line.startswith("event: "))
        data = json.loads(next(line[6:] for line in lines if line.startswith("data: ")))
        out.append((ev, data))
    return out


def _two_patients(client):
    a = create_patient(client, mrn="A-1", first="Alice", last="Alpha")
    b = create_patient(client, mrn="B-1", first="Bob", last="Bravo")
    upload(client, a["id"], lab_pdf("Alice Alpha", "A-1", [("Creatinine", "1.1", "mg/dL", "0.6-1.2")]))
    upload(
        client,
        b["id"],
        lab_pdf("Bob Bravo", "B-1", [("Creatinine", "3.9", "mg/dL", "0.6-1.2"), ("Ferritin", "4", "ng/mL", "15-150")]),
    )
    return a, b


def test_patient_isolation_in_retrieval(clinician):
    a, b = _two_patients(clinician)
    for query in ("creatinine ferritin Bob Bravo B-1", "kidney function results"):
        res = clinician.post(
            "/api/knowledge/search", json={"query": query, "patient_id": a["id"], "include_knowledge": False}
        ).json()
        assert res["passages"], "patient's own document should be retrievable"
        for p in res["passages"]:
            assert "Bravo" not in p["excerpt"] and "3.9" not in p["excerpt"]


def test_unscoped_patient_search_is_refused():
    db = app_db.SessionLocal()
    with pytest.raises(ValueError):
        lexical.search(db, "creatinine", "patient", 10)


def test_chat_stream_with_citation_validation(clinician, ai):
    a, _ = _two_patients(clinician)
    conv = clinician.post("/api/conversations", json={"patient_id": a["id"]}).json()
    r = clinician.post(f"/api/conversations/{conv['id']}/messages", json={"content": "What is the creatinine?"})
    events = _events(r.text)
    kinds = [e for e, _ in events]
    assert kinds[0] == "user_message" and kinds[-1] == "done" and "token" in kinds and "sources" in kinds
    done = events[-1][1]
    assert "[P99]" not in done["content"]  # fabricated label removed
    assert "P99" in done["trace"]["generation"]["invalid_citations_removed"]
    assert any(c["label"] == "P1" and c["cited"] for c in done["citations"])
    # the model only ever saw this patient's material
    prompt = ai["calls"][-1][-1].content
    assert "Bravo" not in prompt and "Alice Alpha" in prompt
    full = clinician.get(f"/api/conversations/{conv['id']}").json()
    assert [m["role"] for m in full["messages"]] == ["user", "assistant"]
    assert full["title"].startswith("What is the creatinine")


def test_knowledge_chat_abstains_without_calling_llm(clinician, ai):
    conv = clinician.post("/api/conversations", json={}).json()
    r = clinician.post(f"/api/conversations/{conv['id']}/messages", json={"content": "What is the dose of drug zyx?"})
    done = _events(r.text)[-1][1]
    assert done["status"] == "abstained"
    assert "Insufficient evidence" in done["content"]
    assert "calls" not in ai


def test_llm_outage_emits_error_event(clinician, ai):
    a, _ = _two_patients(clinician)
    ai["fail"] = True
    conv = clinician.post("/api/conversations", json={"patient_id": a["id"]}).json()
    r = clinician.post(f"/api/conversations/{conv['id']}/messages", json={"content": "Summarise"})
    ev, data = _events(r.text)[-1]
    assert ev == "error" and "fake outage" in data["message"]


def test_feedback_and_conversation_privacy(client, ai):
    from tests.conftest import login, make_user

    make_user("one@test.local", "clinician")
    make_user("two@test.local", "clinician")
    login(client, "one@test.local", "Password@123")
    conv = client.post("/api/conversations", json={}).json()
    login(client, "two@test.local", "Password@123")
    assert client.get(f"/api/conversations/{conv['id']}").status_code == 404


def test_research_disabled_by_default(clinician):
    r = clinician.post("/api/research/search", json={"question": "latest evidence on SGLT2 inhibitors"})
    assert r.status_code == 403
