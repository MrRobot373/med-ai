from datetime import date, timedelta

from tests.conftest import create_patient, lab_pdf, login, make_user, upload


def _rohit(client):
    p = create_patient(client, mrn="R-1", first="Rohit", last="Verma", date_of_birth="1957-05-10", sex="male")
    pid = p["id"]
    client.post(f"/api/patients/{pid}/conditions", json={"name": "Type 2 diabetes mellitus"})
    client.post(f"/api/patients/{pid}/conditions", json={"name": "Benign prostatic hyperplasia"})
    client.post(f"/api/patients/{pid}/allergies", json={"substance": "Sulfa drugs", "reaction": "rash"})
    client.post(f"/api/patients/{pid}/medications", json={"name": "Ecosprin 75", "dose": "1 tab", "frequency": "OD"})
    client.post(f"/api/patients/{pid}/medications", json={"name": "Telma 40", "dose": "1 tab", "frequency": "OD"})
    client.post(
        f"/api/patients/{pid}/observations",
        json={
            "name": "Creatinine",
            "code": "creatinine",
            "value_num": 1.6,
            "unit": "mg/dL",
            "observed_at": "2026-09-01T00:00:00Z",
        },
    )
    return pid


def test_front_desk_can_register_upload_and_list_but_not_read_clinical(client):
    make_user("desk@test.local", "front_desk")
    login(client, "desk@test.local", "Password@123")
    p = create_patient(client, mrn="FD-1")
    pid = p["id"]
    assert client.post("/api/appointments", json={"patient_id": pid, "reason": "Follow-up"}).status_code == 201
    today = client.get("/api/today").json()
    assert today["appointments"][0]["patient"]["name"] == "Alice Tester" and "clinical" not in today["appointments"][0]
    r = upload(client, pid, lab_pdf("Alice Tester", "FD-1", [("HbA1c", "7.1", "%", "4.0-5.6")]))
    assert r.status_code == 201 and r.json()["extraction"] == {}
    for path in (
        f"/api/patients/{pid}/overview",
        f"/api/patients/{pid}/observations",
        f"/api/patients/{pid}/medications",
        f"/api/patients/{pid}/prescriptions",
        f"/api/documents/{r.json()['id']}/chunks",
        "/api/inbox",
        "/api/dashboard",
    ):
        assert client.get(path).status_code == 403, path
    assert client.post(f"/api/patients/{pid}/previsit/brief").status_code == 403
    assert client.post(f"/api/patients/{pid}/consultations", json={}).status_code == 403


def test_live_prescription_check_uses_patient_facts(clinician):
    pid = _rohit(clinician)
    r = clinician.post(
        "/api/prescriptions/check",
        json={
            "patient_id": pid,
            "items": [
                {"drug": "Meftal-Spas", "dose": "1 tab", "frequency": "TDS"},
                {"drug": "Septran DS", "dose": "1 tab", "frequency": "BD"},
            ],
        },
    ).json()
    assert r["patient"]["egfr"]["source"].startswith("calculated")
    meftal = {f["title"] for f in r["items"][0]["findings"]}
    assert any("Benign prostatic" in t for t in meftal)
    assert any("Ecosprin" in t for t in meftal)
    assert r["items"][1]["status"] == "critical"


def test_consultation_prescription_and_follow_up_flow(clinician, ai):
    pid = _rohit(clinician)
    appt = clinician.post(
        "/api/appointments", json={"patient_id": pid, "time": "10:15", "reason": "Stomach pain"}
    ).json()
    enc = clinician.post(f"/api/patients/{pid}/consultations", json={"appointment_id": appt["id"]}).json()
    assert enc["reason"] == "Stomach pain"
    # idempotent: starting again returns the same consultation
    assert (
        clinician.post(f"/api/patients/{pid}/consultations", json={"appointment_id": appt["id"]}).json()["id"]
        == enc["id"]
    )
    clinician.patch(
        f"/api/consultations/{enc['id']}",
        json={
            "history": "Epigastric burning 2 days",
            "diagnoses": [{"name": "Acute gastritis", "add_to_problems": True}],
        },
    )

    ai["json"] = {
        "verdict": "partly_consistent",
        "summary": "Consider biliary colic",
        "supporting": ["burning"],
        "against": [],
        "consider": [{"diagnosis": "Biliary colic", "why": "diabetic", "how_to_check": "USG"}],
        "red_flags": [],
        "suggested_tests": [],
        "history_links": [],
    }
    dc = clinician.post(f"/api/consultations/{enc['id']}/diagnosis-check").json()
    assert dc["status"] == "draft" and dc["output"]["verdict"] == "partly_consistent"

    rx = clinician.post(f"/api/consultations/{enc['id']}/prescription").json()
    assert rx["diagnosis"] == "Acute gastritis"
    items = [
        {"drug": "Pan 40", "dose": "1 tab", "frequency": "OD", "duration_days": 14},
        {"drug": "Septran DS", "dose": "1 tab", "frequency": "BD", "duration_days": 5},
    ]
    follow = (date.today() + timedelta(days=14)).isoformat()
    saved = clinician.put(
        f"/api/prescriptions/{rx['id']}",
        json={"diagnosis": "Acute gastritis", "follow_up_date": follow, "items": items},
    ).json()
    assert saved["check"]["status"] == "critical" and saved["items"][1]["checks"]

    ai["json"] = {
        "overall": "unsafe",
        "summary": "Sulfa allergy",
        "items": [
            {"index": 1, "verdict": "avoid", "dose_assessment": "adequate", "comment": "allergy"},
            {"index": 9, "verdict": "x"},
        ],
        "diagnosis_fit": "",
        "missing": [],
        "monitoring": [],
        "counselling": [],
    }
    review = clinician.post(f"/api/prescriptions/{rx['id']}/review").json()
    assert review["output"]["overall"] == "unsafe" and [i["index"] for i in review["output"]["items"]] == [1]

    # Completing with an unfinished prescription is refused
    assert clinician.post(f"/api/consultations/{enc['id']}/complete", json={}).status_code == 409
    r = clinician.post(f"/api/prescriptions/{rx['id']}/finalize", json={})
    assert r.status_code == 422 and "Septran DS" in r.json()["detail"]
    item_id = saved["items"][1]["id"]
    r = clinician.post(
        f"/api/prescriptions/{rx['id']}/finalize", json={"overrides": {item_id: "Tolerated before; rash was mild"}}
    )
    assert r.status_code == 200 and r.json()["status"] == "final"
    assert clinician.put(f"/api/prescriptions/{rx['id']}", json={"items": []}).status_code == 409

    meds = clinician.get(f"/api/patients/{pid}/medications").json()
    assert {m["name"] for m in meds if m["source"] == "prescription"} == {"Pan 40", "Septran DS"}
    assert clinician.post(f"/api/consultations/{enc['id']}/complete", json={}).status_code == 200
    problems = [c["name"] for c in clinician.get(f"/api/patients/{pid}/conditions").json()]
    assert "Acute gastritis" in problems
    upcoming = clinician.get("/api/appointments", params={"day": follow}).json()
    assert upcoming and upcoming[0]["reason"] == "Follow-up"
    assert clinician.get("/api/appointments").json()[0]["status"] == "seen"
    # The prescription is part of the record the AI sees next time
    from app import db as app_db
    from app.clinical.context import patient_record_text
    from app.models import Patient

    s = app_db.SessionLocal()
    assert "Previous prescriptions:" in patient_record_text(s, s.get(Patient, pid))
    s.close()


def test_finalize_replaces_same_medicine_on_chart(clinician):
    pid = _rohit(clinician)
    enc = clinician.post(f"/api/patients/{pid}/consultations", json={"reason": "BP review"}).json()
    rx = clinician.post(f"/api/consultations/{enc['id']}/prescription").json()
    clinician.put(
        f"/api/prescriptions/{rx['id']}", json={"items": [{"drug": "Telma 80", "dose": "1 tab", "frequency": "OD"}]}
    )
    assert clinician.post(f"/api/prescriptions/{rx['id']}/finalize", json={}).status_code == 200
    meds = {m["name"]: m["status"] for m in clinician.get(f"/api/patients/{pid}/medications").json()}
    assert meds["Telma 40"] == "stopped" and meds["Telma 80"] == "active"


def test_order_auto_matches_uploaded_report_and_surfaces_in_inbox(clinician, ai):
    p = create_patient(clinician, mrn="O-1")
    pid = p["id"]
    o = clinician.post(
        f"/api/patients/{pid}/orders", json={"test_name": "USG abdomen", "reason": "Epigastric pain"}
    ).json()
    assert o["category"] == "radiology" and o["status"] == "ordered"
    other = clinician.post(f"/api/patients/{pid}/orders", json={"test_name": "CBC"}).json()
    import pymupdf

    d = pymupdf.open()
    page = d.new_page()
    page.insert_text((50, 60), "Ultrasonography of whole abdomen")
    page.insert_text((50, 80), "Patient name: Alice Tester   MRN: O-1")
    page.insert_text((50, 100), "Impression: Gall bladder calculus. No pancreatic lesion.")
    data = d.tobytes()
    r = upload(clinician, pid, data, filename="usg.pdf", title="USG whole abdomen")
    assert r.status_code == 201
    orders = {x["id"]: x for x in clinician.get(f"/api/patients/{pid}/orders").json()}
    assert orders[o["id"]]["status"] == "result_received"
    assert orders[other["id"]]["status"] == "ordered"
    assert any(i["type"] == "result" and i["ref_id"] == o["id"] for i in clinician.get("/api/inbox").json())
    ai["json"] = {
        "answers_question": "Gallstone explains pain",
        "key_findings": ["Calculus"],
        "abnormal": [],
        "next_steps": [],
        "urgency": "soon",
        "patient_explanation": "x",
    }
    rev = clinician.post(f"/api/orders/{o['id']}/ai-review").json()
    assert rev["output"]["urgency"] == "soon"
    assert (
        clinician.post(f"/api/orders/{o['id']}/reviewed", json={"note": "Surgical referral"}).json()["status"]
        == "reviewed"
    )
    # A report uploaded against a specific order is linked directly
    r2 = upload(
        clinician,
        pid,
        lab_pdf("Alice Tester", "O-1", [("Hemoglobin", "12.1", "g/dL", "12-16")]),
        filename="cbc.pdf",
        order_id=other["id"],
    )
    assert r2.status_code == 201
    assert (
        clinician.get(f"/api/patients/{pid}/orders", params={"status": "result_received"}).json()[0]["id"]
        == other["id"]
    )


def test_previsit_facts_and_brief(clinician, ai):
    pid = _rohit(clinician)
    pv = clinician.get(f"/api/patients/{pid}/previsit").json()
    assert pv["facts"]["last_visit"] is None and pv["brief"] is None
    ai["json"] = {
        "headline": "69M diabetic",
        "since_last_visit": ["x"],
        "ask_about": [{"question": "Weight?", "why": "gain"}, "Fever settled?"],
        "watch_outs": [],
        "consider_today": [],
    }
    b = clinician.post(f"/api/patients/{pid}/previsit/brief").json()
    assert b["output"]["ask_about"][1] == {"question": "Fever settled?", "why": ""}
    assert clinician.get(f"/api/patients/{pid}/previsit").json()["brief"]["id"] == b["id"]
    ai["fail"] = True
    err = clinician.post(f"/api/patients/{pid}/previsit/brief").json()
    assert err["status"] == "error" and "fake outage" in err["error"]


def test_formulary_endpoints(clinician, monkeypatch):
    assert "Dolo 650" in [x["label"] for x in clinician.get("/api/formulary/search", params={"q": "dolo"}).json()]
    meta = clinician.get("/api/formulary/meta").json()
    assert meta["region"] == "IN" and "1-0-1" in meta["frequencies"]
    g = clinician.get("/api/formulary/generics/paracetamol").json()
    assert g["rules"]["max_daily"] == 4000 and any(p["brand"] == "Dolo" for p in g["products"])
    from app.formulary import images

    async def fake_fetch(gid, query, client=None):
        return {"status": "none"}

    monkeypatch.setattr(images, "fetch", fake_fetch)
    assert clinician.get("/api/formulary/generics/paracetamol/image-info").json()["image"] is None
    clinician.put("/api/settings/formulary", json={"fetch_images": False})  # clinician is not admin
    assert clinician.get("/api/formulary/generics/paracetamol/image").status_code == 404
