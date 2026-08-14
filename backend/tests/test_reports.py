"""Report ingestion tests — spec §133 acceptance criteria for Reports:
PDF upload, OCR path, report status, duplicate detection, patient mismatch, and
extracted values tracing back to a source page.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.db.session import SessionLocal
from app.ingestion.ocr import OcrResult
from app.models.user import User, UserRole
from tests.sample_documents import (
    make_dicom_bytes,
    make_docx_bytes,
    make_pdf_bytes,
    make_scanned_pdf_bytes,
    make_xlsx_bytes,
)

PASSWORD = "correct-horse-battery-2"


def _login_as(client: TestClient, email: str, role: UserRole) -> User:
    db = SessionLocal()
    try:
        user = User(
            email=email,
            display_name=email.split("@")[0],
            password_hash=hash_password(PASSWORD),
            role=role,
            active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    finally:
        db.close()

    resp = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200
    return user


def _create_patient(client: TestClient, **overrides) -> dict:
    payload = {
        "first_name": "Margaret",
        "last_name": "Wallace",
        "date_of_birth": "1953-04-12",
        "sex": "female",
    }
    payload.update(overrides)
    resp = client.post("/api/patients", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _upload(client: TestClient, patient_id: str, filename: str, content: bytes, mime: str, **params) -> dict:
    resp = client.post(
        f"/api/patients/{patient_id}/reports",
        files={"file": (filename, content, mime)},
        params=params,
    )
    return resp


# --- Text extraction across formats --------------------------------------------------


def test_upload_pdf_extracts_text_classifies_and_matches_patient(client):
    _login_as(client, "doctor.reports1@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, mrn="DEMO-TEST-1001")

    pdf_bytes = make_pdf_bytes(
        [
            "Patient Name: Margaret Wallace",
            "MRN: DEMO-TEST-1001",
            "Optical coherence tomography - macular thickness normal.",
        ]
    )
    resp = _upload(client, patient["id"], "oct_report.pdf", pdf_bytes, "application/pdf")
    assert resp.status_code == 201, resp.text
    report_id = resp.json()["id"]

    detail = client.get(f"/api/reports/{report_id}").json()
    assert detail["ingestion_status"] == "completed"
    assert detail["extraction_status"] == "success"
    assert detail["patient_match_status"] == "matched"
    assert detail["source_patient_name"] == "Margaret Wallace"
    assert detail["source_mrn"] == "DEMO-TEST-1001"
    assert detail["report_type"] == "imaging_report"  # "optical coherence tomography" keyword
    # Extracted values trace back to an exact source page (spec §133).
    assert detail["pages"][0]["page"] == 1
    assert "macular thickness" in detail["pages"][0]["text"]
    assert detail["pages"][0]["method"] == "text"


def test_upload_docx_extracts_paragraphs_and_table(client):
    _login_as(client, "doctor.reports2@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)

    docx_bytes = make_docx_bytes(
        paragraphs=["Consultation Note", "Chief Complaint: routine follow-up"],
        table_rows=[["Eye", "IOP"], ["OD", "16"], ["OS", "17"]],
    )
    resp = _upload(
        client,
        patient["id"],
        "note.docx",
        docx_bytes,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert resp.status_code == 201
    detail = client.get(f"/api/reports/{resp.json()['id']}").json()
    assert detail["extraction_status"] == "success"
    text = detail["pages"][0]["text"]
    assert "Chief Complaint" in text
    assert "[Table]" in text
    assert "OD | 16" in text


def test_upload_xlsx_extracts_sheet_rows(client):
    _login_as(client, "doctor.reports3@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)

    xlsx_bytes = make_xlsx_bytes("Labs", [["Test", "Result"], ["HbA1c", 8.1], ["Glucose", 168]])
    resp = _upload(
        client,
        patient["id"],
        "labs.xlsx",
        xlsx_bytes,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    assert resp.status_code == 201
    detail = client.get(f"/api/reports/{resp.json()['id']}").json()
    assert detail["extraction_status"] == "success"
    assert "[Sheet: Labs]" in detail["pages"][0]["text"]
    assert "HbA1c" in detail["pages"][0]["text"]


def test_xlsx_pipe_separated_identity_is_detected(client):
    # Regression test: spreadsheet extraction renders "Label | Value" (pipe-separated
    # cells), not "Label: Value" — found via live testing, not a unit test, so it's
    # worth pinning down explicitly here.
    _login_as(client, "doctor.reports3b@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, first_name="Elena", last_name="Novak", mrn="DEMO-TEST-XLSX")

    xlsx_bytes = make_xlsx_bytes(
        "Metabolic Panel",
        [["Patient Name", "Elena Novak"], ["MRN", "DEMO-TEST-XLSX"], ["HbA1c", 8.1]],
    )
    resp = _upload(
        client,
        patient["id"],
        "labs.xlsx",
        xlsx_bytes,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    detail = client.get(f"/api/reports/{resp.json()['id']}").json()
    assert detail["source_patient_name"] == "Elena Novak"
    assert detail["source_mrn"] == "DEMO-TEST-XLSX"


def test_identity_extraction_stops_at_next_label_on_same_line(client):
    # Regression test: found via live testing against a real OCR'd image upload, where
    # flattened text put multiple fields on one line with no newline between them
    # ("Patient: Elena Novak MRN: DEMO 1003 DOB: ..."). The name pattern used to swallow
    # the next label into its capture ("Elena Novak MRN"), and the MRN pattern used to
    # truncate its own value at the first internal space ("DEMO 1003" -> "DEMO").
    _login_as(client, "doctor.reports3c@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, first_name="Elena", last_name="Novak", mrn="DEMO-TEST-BLEED")

    pdf_bytes = make_pdf_bytes(
        [
            (
                "Patient: Elena Novak MRN: DEMO-TEST-BLEED DOB: 1971-03-14 "
                "Optical coherence tomography - macular thickness normal."
            )
        ]
    )
    resp = _upload(client, patient["id"], "oct_report.pdf", pdf_bytes, "application/pdf")
    detail = client.get(f"/api/reports/{resp.json()['id']}").json()
    assert detail["source_patient_name"] == "Elena Novak"
    assert detail["source_mrn"] == "DEMO-TEST-BLEED"
    assert detail["patient_match_status"] == "matched"
    assert detail["patient_match_status"] == "matched"


def test_upload_dicom_extracts_metadata(client):
    _login_as(client, "doctor.reports4@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)

    dicom_bytes = make_dicom_bytes(modality="OP")
    resp = _upload(client, patient["id"], "scan.dcm", dicom_bytes, "application/dicom")
    assert resp.status_code == 201
    detail = client.get(f"/api/reports/{resp.json()['id']}").json()
    assert detail["extraction_status"] == "success"
    assert "Modality: OP" in detail["pages"][0]["text"]
    assert detail["pages"][0]["method"] == "metadata"


def test_dicom_preview_endpoint_returns_png(client):
    _login_as(client, "doctor.reports5@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    dicom_bytes = make_dicom_bytes()
    resp = _upload(client, patient["id"], "scan.dcm", dicom_bytes, "application/dicom")
    report_id = resp.json()["id"]

    preview = client.get(f"/api/reports/{report_id}/preview")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert preview.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_preview_endpoint_404_for_non_dicom_report(client):
    _login_as(client, "doctor.reports6@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    content = make_pdf_bytes(["This PDF has a normal enough text layer to skip the OCR fallback path."])
    resp = _upload(client, patient["id"], "x.pdf", content, "application/pdf")
    preview = client.get(f"/api/reports/{resp.json()['id']}/preview")
    assert preview.status_code == 404


# --- OCR fallback ----------------------------------------------------------------


def test_scanned_pdf_triggers_ocr_fallback(client, monkeypatch):
    _login_as(client, "doctor.reports7@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, mrn="DEMO-TEST-OCR")

    # Real easyocr model loading is slow/network-dependent on first use — this test
    # verifies the PIPELINE correctly detects sparse text and invokes OCR, not
    # easyocr's actual recognition accuracy (that's a library concern, not ours).
    def fake_run_ocr(_image_bytes):
        return OcrResult(text="Patient Name: Margaret Wallace\nMRN: DEMO-TEST-OCR\nOCR recovered text.", mean_confidence=0.9)

    monkeypatch.setattr("app.ingestion.ocr.run_ocr", fake_run_ocr)

    scanned = make_scanned_pdf_bytes(["Patient Name: Margaret Wallace", "MRN: DEMO-TEST-OCR", "Scanned content."])
    resp = _upload(client, patient["id"], "scanned.pdf", scanned, "application/pdf")
    assert resp.status_code == 201
    detail = client.get(f"/api/reports/{resp.json()['id']}").json()

    assert detail["ocr_used"] is True
    assert detail["extraction_status"] == "success"
    assert detail["pages"][0]["method"] == "ocr"
    assert "OCR recovered text" in detail["pages"][0]["text"]
    assert detail["patient_match_status"] == "matched"  # OCR text fed identity checking too


def test_ocr_failure_degrades_gracefully_without_crashing_ingestion(client, monkeypatch):
    _login_as(client, "doctor.reports8@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)

    def failing_run_ocr(_image_bytes):
        raise RuntimeError("simulated OCR engine crash")

    monkeypatch.setattr("app.ingestion.ocr.run_ocr", failing_run_ocr)

    scanned = make_scanned_pdf_bytes(["Some scanned content with no real text layer."])
    resp = _upload(client, patient["id"], "scanned2.pdf", scanned, "application/pdf")
    assert resp.status_code == 201
    detail = client.get(f"/api/reports/{resp.json()['id']}").json()
    # Ingestion still completes overall — OCR failing on one page doesn't fail the job.
    assert detail["ingestion_status"] == "completed"
    assert detail["ocr_used"] is False


# --- Duplicate detection --------------------------------------------------------------


def test_duplicate_upload_rejected_by_default(client):
    _login_as(client, "doctor.reports9@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    content = make_pdf_bytes(["Duplicate test content used to verify hash-based upload deduplication."])

    first = _upload(client, patient["id"], "a.pdf", content, "application/pdf")
    assert first.status_code == 201

    second = _upload(client, patient["id"], "a.pdf", content, "application/pdf")
    assert second.status_code == 409


def test_duplicate_upload_allowed_with_explicit_flag(client):
    _login_as(client, "doctor.reports10@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    content = make_pdf_bytes(["Duplicate test content used to verify the allow_duplicate override flag."])

    first = _upload(client, patient["id"], "a.pdf", content, "application/pdf")
    assert first.status_code == 201

    second = _upload(client, patient["id"], "a.pdf", content, "application/pdf", allow_duplicate=True)
    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]


# --- Patient identity mismatch ---------------------------------------------------------


def test_patient_mismatch_detected_and_document_not_silently_attached(client):
    _login_as(client, "doctor.reports11@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, first_name="John", last_name="Demo", mrn="DEMO-JOHN-1")

    wrong_patient_pdf = make_pdf_bytes(["Patient Name: Sarah Demo", "MRN: DEMO-SARAH-9", "Unrelated content."])
    resp = _upload(client, patient["id"], "wrong.pdf", wrong_patient_pdf, "application/pdf")
    detail = client.get(f"/api/reports/{resp.json()['id']}").json()

    assert detail["patient_match_status"] == "mismatch"
    assert detail["source_patient_name"] == "Sarah Demo"


def test_confirm_match_overrides_mismatch_and_records_reviewer(client):
    doctor = _login_as(client, "doctor.reports12@example.com", UserRole.DOCTOR)
    patient = _create_patient(client, first_name="John", last_name="Demo", mrn="DEMO-JOHN-2")

    wrong_patient_pdf = make_pdf_bytes(["Patient Name: Sarah Demo", "MRN: DEMO-SARAH-8"])
    resp = _upload(client, patient["id"], "wrong2.pdf", wrong_patient_pdf, "application/pdf")
    report_id = resp.json()["id"]
    assert client.get(f"/api/reports/{report_id}").json()["patient_match_status"] == "mismatch"

    confirmed = client.post(f"/api/reports/{report_id}/confirm-match")
    assert confirmed.status_code == 200
    assert confirmed.json()["patient_match_status"] == "matched"
    assert doctor.id  # sanity — reviewer id is a real user we created above


def test_unconfirmed_when_no_identity_detected(client):
    _login_as(client, "doctor.reports13@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)

    no_identity_pdf = make_pdf_bytes(["Just some clinical text with no header fields."])
    resp = _upload(client, patient["id"], "noident.pdf", no_identity_pdf, "application/pdf")
    detail = client.get(f"/api/reports/{resp.json()['id']}").json()
    assert detail["patient_match_status"] == "unconfirmed"
    assert detail["source_patient_name"] is None


# --- Validation --------------------------------------------------------------------


def test_unsupported_file_extension_rejected(client):
    _login_as(client, "doctor.reports14@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    resp = _upload(client, patient["id"], "malware.exe", b"MZ\x90\x00fake-exe-content", "application/octet-stream")
    assert resp.status_code == 422


def test_content_not_matching_extension_rejected(client):
    _login_as(client, "doctor.reports15@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    # .pdf extension but the content isn't actually a PDF (no %PDF- magic bytes).
    resp = _upload(client, patient["id"], "fake.pdf", b"this is not a real pdf file", "application/pdf")
    assert resp.status_code == 422


def test_empty_file_rejected(client):
    _login_as(client, "doctor.reports16@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    resp = _upload(client, patient["id"], "empty.pdf", b"", "application/pdf")
    assert resp.status_code == 422


# --- Authorization -----------------------------------------------------------------


def test_viewer_cannot_upload_archive_or_confirm_match(client):
    _login_as(client, "doctor.reports17@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    resp = _upload(client, patient["id"], "a.pdf", make_pdf_bytes(["Placeholder report content padded past the OCR fallback threshold."]), "application/pdf")
    report_id = resp.json()["id"]
    client.post("/api/auth/logout")

    _login_as(client, "viewer.reports1@example.com", UserRole.VIEWER)
    upload_resp = _upload(client, patient["id"], "b.pdf", make_pdf_bytes(["Another placeholder report, never processed since the viewer role is rejected first."]), "application/pdf")
    assert upload_resp.status_code == 403
    assert client.post(f"/api/reports/{report_id}/archive").status_code == 403
    assert client.post(f"/api/reports/{report_id}/confirm-match").status_code == 403


def test_viewer_can_list_and_view_reports(client):
    _login_as(client, "doctor.reports18@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    resp = _upload(client, patient["id"], "a.pdf", make_pdf_bytes(["Placeholder report content padded past the OCR fallback threshold."]), "application/pdf")
    report_id = resp.json()["id"]
    client.post("/api/auth/logout")

    _login_as(client, "viewer.reports2@example.com", UserRole.VIEWER)
    assert client.get(f"/api/patients/{patient['id']}/reports").status_code == 200
    assert client.get(f"/api/reports/{report_id}").status_code == 200


# --- Archive / status / file download ----------------------------------------------


def test_archive_excludes_report_from_default_list(client):
    _login_as(client, "doctor.reports19@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    resp = _upload(client, patient["id"], "a.pdf", make_pdf_bytes(["Placeholder report content padded past the OCR fallback threshold."]), "application/pdf")
    report_id = resp.json()["id"]

    client.post(f"/api/reports/{report_id}/archive")

    default_list = client.get(f"/api/patients/{patient['id']}/reports").json()
    assert all(r["id"] != report_id for r in default_list)

    with_archived = client.get(f"/api/patients/{patient['id']}/reports", params={"include_archived": True}).json()
    assert any(r["id"] == report_id for r in with_archived)


def test_report_status_endpoint(client):
    _login_as(client, "doctor.reports20@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    resp = _upload(client, patient["id"], "a.pdf", make_pdf_bytes(["Placeholder report content padded past the OCR fallback threshold."]), "application/pdf")
    report_id = resp.json()["id"]

    status_resp = client.get(f"/api/reports/{report_id}/status")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["ingestion_status"] == "completed"
    assert body["extraction_status"] == "success"


def test_download_report_file_returns_original_bytes(client):
    _login_as(client, "doctor.reports21@example.com", UserRole.DOCTOR)
    patient = _create_patient(client)
    original = make_pdf_bytes(["Exact byte match test content, padded to skip the OCR fallback path too."])
    resp = _upload(client, patient["id"], "a.pdf", original, "application/pdf")
    report_id = resp.json()["id"]

    file_resp = client.get(f"/api/reports/{report_id}/file")
    assert file_resp.status_code == 200
    assert file_resp.content == original
    assert file_resp.headers["content-type"] == "application/pdf"


def test_unknown_report_returns_404_across_endpoints(client):
    _login_as(client, "doctor.reports22@example.com", UserRole.DOCTOR)
    assert client.get("/api/reports/does-not-exist").status_code == 404
    assert client.get("/api/reports/does-not-exist/status").status_code == 404
    assert client.get("/api/reports/does-not-exist/file").status_code == 404
