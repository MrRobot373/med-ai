from datetime import date

from app.seed import _ct_phantom_dicom, _ecg_png
from tests.conftest import create_patient, lab_pdf, upload


def test_dicom_ingestion_identity_and_preview(clinician):
    p = create_patient(clinician, mrn="DEMO-77", first="Robert", last="Klein")
    data = _ct_phantom_dicom("Robert Klein", "DEMO-77", date(2026, 9, 1))
    r = clinician.post(f"/api/patients/{p['id']}/documents", files={"file": ("head.dcm", data, "application/dicom")})
    assert r.status_code == 201, r.text
    doc = clinician.get(f"/api/documents/{r.json()['id']}").json()
    assert doc["status"] == "ready", doc["error"]
    assert doc["kind"] == "imaging" and doc["document_date"] == "2026-09-01"
    assert doc["identity_status"] == "match"  # DICOM PatientID matches the MRN
    text = clinician.get(f"/api/documents/{doc['id']}/chunks").json()[0]["text"]
    assert "Modality: CT" in text
    png = clinician.get(f"/api/documents/{doc['id']}/preview", params={"width": 200})
    assert png.status_code == 200 and png.content.startswith(b"\x89PNG")


def test_pdf_and_image_previews(clinician):
    p = create_patient(clinician)
    pdf = upload(clinician, p["id"], lab_pdf("Alice Tester", "T-100", [("HbA1c", "7.0", "%", "4.0-5.6")])).json()
    r = clinician.get(f"/api/documents/{pdf['id']}/preview", params={"page": 1, "width": 300})
    assert r.status_code == 200 and r.headers["x-page-count"] == "1" and r.content.startswith(b"\x89PNG")
    img = clinician.post(
        f"/api/patients/{p['id']}/documents",
        files={"file": ("ecg.png", _ecg_png("Alice Tester", "T-100", date.today()), "image/png")},
    ).json()
    assert clinician.get(f"/api/documents/{img['id']}/preview", params={"width": 400}).status_code == 200


def test_text_documents_have_no_visual_preview(admin):
    r = admin.post("/api/knowledge", files={"file": ("note.md", b"# Note\nSome guidance text here.", "text/markdown")})
    assert admin.get(f"/api/documents/{r.json()['id']}/preview").status_code == 415


def test_fake_dicom_is_rejected(clinician):
    p = create_patient(clinician)
    r = clinician.post(
        f"/api/patients/{p['id']}/documents", files={"file": ("x.dcm", b"not a dicom file at all", "application/dicom")}
    )
    assert r.status_code == 415
