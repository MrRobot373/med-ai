from tests.conftest import create_patient, lab_pdf, upload


def test_lab_report_ingestion_extracts_flagged_observations(clinician):
    p = create_patient(clinician)
    r = upload(
        clinician,
        p["id"],
        lab_pdf("Alice Tester", "T-100", [("HbA1c", "8.4", "%", "4.0-5.6"), ("Potassium", "4.2", "mmol/L", "3.5-5.1")]),
    )
    assert r.status_code == 201
    doc = clinician.get(f"/api/documents/{r.json()['id']}").json()
    assert doc["status"] == "ready", doc["error"]
    assert doc["identity_status"] == "match"
    assert doc["kind"] == "lab_report"
    assert doc["document_date"] == "2026-09-01"
    obs = {o["code"]: o for o in clinician.get(f"/api/patients/{p['id']}/observations").json()}
    assert obs["hba1c"]["flag"] == "high" and obs["hba1c"]["source_page"] == 1
    assert obs["potassium"]["flag"] == "normal"
    assert doc["chunk_count"] >= 1


def test_wrong_patient_document_is_quarantined(clinician):
    p = create_patient(clinician)
    r = upload(clinician, p["id"], lab_pdf("Zed Other", "OTHER-999", [("Hemoglobin", "9.0", "g/dL", "12-15")]))
    doc = clinician.get(f"/api/documents/{r.json()['id']}").json()
    assert doc["identity_status"] == "mismatch"
    assert doc["is_active"] is False
    assert clinician.get(f"/api/patients/{p['id']}/observations").json() == []
    inbox = clinician.get("/api/inbox").json()
    assert any(i["type"] == "identity" for i in inbox)
    # retrieval never sees quarantined content
    res = clinician.post(
        "/api/knowledge/search", json={"query": "hemoglobin", "patient_id": p["id"], "include_knowledge": False}
    ).json()
    assert res["passages"] == []
    # clinician confirms → released and re-processed
    clinician.patch(f"/api/documents/{doc['id']}", json={"identity_status": "confirmed"})
    doc = clinician.get(f"/api/documents/{doc['id']}").json()
    assert doc["is_active"] is True and doc["identity_status"] == "match"
    assert len(clinician.get(f"/api/patients/{p['id']}/observations").json()) == 1


def test_duplicate_and_invalid_uploads(clinician):
    p = create_patient(clinician)
    data = lab_pdf("Alice Tester", "T-100", [("HbA1c", "7.0", "%", "4.0-5.6")])
    assert upload(clinician, p["id"], data).status_code == 201
    dup = upload(clinician, p["id"], data)
    assert dup.status_code == 409 and dup.json()["code"] == "duplicate"
    assert upload(clinician, p["id"], b"MZ\x90 not a pdf", filename="evil.pdf").status_code == 415
    assert upload(clinician, p["id"], b"data", filename="script.exe").status_code == 415
    assert upload(clinician, p["id"], b"", filename="empty.pdf").status_code == 400


def test_text_and_json_knowledge_upload(admin):
    r = admin.post(
        "/api/knowledge",
        files={"file": ("pack.json", b'[{"disease": "Gout", "management": ["allopurinol"]}]', "application/json")},
        data={"domain": "rheumatology"},
    )
    assert r.status_code == 201
    doc = admin.get(f"/api/documents/{r.json()['id']}").json()
    assert doc["status"] == "ready" and doc["domain"] == "rheumatology"
    chunks = admin.get(f"/api/documents/{doc['id']}/chunks").json()
    assert "## Gout" in chunks[0]["text"]
    domains = {d["id"]: d["count"] for d in admin.get("/api/knowledge/domains").json()}
    assert domains["rheumatology"] == 1


def test_failed_ingestion_is_reported(clinician, ai, monkeypatch):
    from app.ai import registry

    class Down:
        async def embed_documents(self, texts):
            from app.core.errors import ServiceUnavailable

            raise ServiceUnavailable("Embedding service unreachable (test)")

    monkeypatch.setattr(registry, "embedder", lambda cfg: Down())
    p = create_patient(clinician)
    r = upload(clinician, p["id"], lab_pdf("Alice Tester", "T-100", [("HbA1c", "7.0", "%", "4.0-5.6")]))
    doc = clinician.get(f"/api/documents/{r.json()['id']}").json()
    assert doc["status"] == "failed" and "unreachable" in doc["error"]
