from app.services.tools import _reconcile
from tests.conftest import create_patient, lab_pdf, upload


def test_summary_is_stored_as_draft_and_reviewable(clinician, ai):
    p = create_patient(clinician)
    run = clinician.post("/api/tools/summary/run", json={"patient_id": p["id"]}).json()
    assert run["status"] == "draft" and run["output"]["one_liner"] == "Summary"
    r = clinician.post(f"/api/ai-runs/{run['id']}/review", json={"decision": "accepted"}).json()
    assert r["status"] == "accepted" and r["reviewed_at"]
    ov = clinician.get(f"/api/patients/{p['id']}/overview").json()
    assert ov["summary"]["id"] == run["id"]


def test_tool_error_is_recorded_not_raised(clinician, ai):
    p = create_patient(clinician)
    ai["fail"] = True
    run = clinician.post("/api/tools/summary/run", json={"patient_id": p["id"]}).json()
    assert run["status"] == "error" and "fake outage" in run["error"]


def test_unparseable_model_output_is_an_error(clinician, ai):
    p = create_patient(clinician)
    ai["reply"] = "definitely not json"
    run = clinician.post("/api/tools/summary/run", json={"patient_id": p["id"]}).json()
    assert run["status"] == "error"


def test_report_comparison_computes_lab_deltas(clinician, ai):
    p = create_patient(clinician)
    d1 = upload(
        clinician, p["id"], lab_pdf("Alice Tester", "T-100", [("Creatinine", "1.2", "mg/dL", "0.6-1.2")], "2026-01-01")
    ).json()
    d2 = upload(
        clinician, p["id"], lab_pdf("Alice Tester", "T-100", [("Creatinine", "1.6", "mg/dL", "0.6-1.2")], "2026-06-01")
    ).json()
    ai["json"] = {"overview": "Kidney function worse"}
    run = clinician.post(
        "/api/tools/comparison/run",
        json={"patient_id": p["id"], "prior_document_id": d1["id"], "current_document_id": d2["id"]},
    ).json()
    delta = run["output"]["lab_changes"][0]
    assert delta["name"] == "Creatinine" and delta["direction"] == "up" and delta["delta"] == 0.4


def test_guideline_qa_abstains_with_empty_library(clinician, ai):
    run = clinician.post("/api/tools/guideline_qa/run", json={"question": "What is the target HbA1c?"}).json()
    assert run["output"]["abstained"] is True
    assert "calls" not in ai


def test_medication_reconciliation_logic():
    class M:
        def __init__(self, name, dose, freq):
            self.name, self.dose, self.frequency, self.route = name, dose, freq, "oral"

    chart = [M("Metformin", "1000 mg", "twice daily"), M("Lisinopril", "20 mg", "daily")]
    doc = [
        {"name": "Metformin", "dose": "500 mg", "frequency": "twice daily"},
        {"name": "Empagliflozin", "dose": "10 mg"},
    ]
    out = _reconcile(chart, doc)
    assert [d["name"] for d in out["discrepancies"]] == ["Metformin"]
    assert [d["name"] for d in out["only_in_document"]] == ["Empagliflozin"]
    assert [d["name"] for d in out["only_in_chart"]] == ["Lisinopril"]
