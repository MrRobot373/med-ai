from tests.conftest import create_patient


def test_patient_crud_and_duplicate_mrn(clinician):
    p = create_patient(clinician, mrn="M-1", date_of_birth="1970-01-01", tags=["diabetes"])
    assert p["age"] >= 50
    assert clinician.post("/api/patients", json={"mrn": "m-1", "first_name": "X", "last_name": "Y"}).status_code == 409
    r = clinician.patch(f"/api/patients/{p['id']}", json={"phone": "555-1234"})
    assert r.json()["phone"] == "555-1234"
    listed = clinician.get("/api/patients", params={"q": "Alice"}).json()
    assert [x["mrn"] for x in listed] == ["M-1"]
    assert clinician.get("/api/patients/tags").json() == [{"tag": "diabetes", "count": 1}]


def test_sub_resources_and_overview(clinician):
    p = create_patient(clinician)
    pid = p["id"]
    assert (
        clinician.post(f"/api/patients/{pid}/conditions", json={"name": "Hypertension", "code": "I10"}).status_code
        == 201
    )
    med = clinician.post(f"/api/patients/{pid}/medications", json={"name": "Amlodipine", "dose": "5 mg"}).json()
    clinician.post(f"/api/patients/{pid}/encounters", json={"reason": "Check-up", "vitals": {"bp": "130/80"}})
    r = clinician.patch(f"/api/patients/{pid}/medications/{med['id']}", json={"status": "stopped"})
    assert r.json()["status"] == "stopped"
    ov = clinician.get(f"/api/patients/{pid}/overview").json()
    assert ov["conditions"][0]["name"] == "Hypertension"
    # absence of allergies is surfaced as a gap, never as "no allergies"
    assert any(a["type"] == "gap" for a in ov["alerts"])
    timeline = clinician.get(f"/api/patients/{pid}/timeline").json()
    assert {e["kind"] for e in timeline} >= {"encounter", "condition", "medication"}


def test_manual_observation_flags_and_trend(clinician):
    pid = create_patient(clinician)["id"]
    for v, at in ((6.5, "2026-01-01T00:00:00Z"), (7.4, "2026-06-01T00:00:00Z")):
        clinician.post(
            f"/api/patients/{pid}/observations",
            json={
                "name": "HbA1c",
                "code": "hba1c",
                "value_num": v,
                "unit": "%",
                "ref_low": 4.0,
                "ref_high": 5.6,
                "observed_at": at,
            },
        )
    trends = clinician.get(f"/api/patients/{pid}/trends").json()
    s = trends[0]
    assert s["code"] == "hba1c" and s["trend"] == "up" and s["abnormal"] is True
    assert round(s["change"], 2) == 0.9


def test_cross_patient_subresource_access_is_rejected(clinician):
    a = create_patient(clinician, mrn="A-1")
    b = create_patient(clinician, mrn="B-1", first="Bob")
    cond = clinician.post(f"/api/patients/{a['id']}/conditions", json={"name": "Asthma"}).json()
    assert clinician.patch(f"/api/patients/{b['id']}/conditions/{cond['id']}", json={"name": "x"}).status_code == 404
    assert clinician.delete(f"/api/patients/{b['id']}/conditions/{cond['id']}").status_code == 404


def test_export_is_markdown(clinician):
    pid = create_patient(clinician)["id"]
    r = clinician.get(f"/api/patients/{pid}/export")
    assert r.status_code == 200 and r.text.startswith("# Patient summary")


def test_dashboard_attention_and_review_queue(clinician):
    from tests.conftest import lab_pdf, upload

    calm = create_patient(clinician, mrn="C-1", first="Calm")
    busy = create_patient(clinician, mrn="B-1", first="Busy", last="Patient")
    upload(clinician, busy["id"], lab_pdf("Busy Patient", "B-1", [("Potassium", "6.1", "mmol/L", "3.5-5.1")]))
    ranked = clinician.get("/api/dashboard/attention").json()
    assert [r["mrn"] for r in ranked] == ["B-1"]
    assert ranked[0]["marker"]["name"] == "Potassium" and ranked[0]["pending_documents"] == 1
    queue = clinician.get("/api/dashboard/review-queue").json()
    assert queue[0]["patient_mrn"] == "B-1" and queue[0]["review_status"] == "pending"
    assert calm["id"] not in {r["id"] for r in ranked}
