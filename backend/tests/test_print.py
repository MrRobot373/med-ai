"""Branches, doctor registration details, the letterhead and the server-made prescription PDF."""

from app import db as app_db
from app.ingestion import pdf as pdf_io
from app.models import User
from tests.conftest import create_patient, login, make_user


def _text(data: bytes) -> str:
    return "\n".join(p["text"] for p in pdf_io.extract_pages(data))


def _final_rx(c, name="Rohit", surname="Verma", drug="Pan 40"):
    pid = create_patient(c, mrn="PR-1", first=name, last=surname, date_of_birth="1957-05-10", sex="male")["id"]
    enc = c.post(f"/api/patients/{pid}/consultations", json={}).json()
    rx = c.post(f"/api/consultations/{enc['id']}/prescription").json()
    c.put(
        f"/api/prescriptions/{rx['id']}",
        json={
            "diagnosis": "Acute gastritis",
            "items": [{"drug": drug, "dose": "1 tab", "frequency": "OD", "duration_days": 14}],
        },
    )
    assert c.post(f"/api/prescriptions/{rx['id']}/finalize", json={}).status_code == 200
    return pid, rx["id"]


def test_default_branch_exists_and_admin_can_add_another(admin):
    rows = admin.get("/api/branches").json()
    assert len(rows) == 1 and rows[0]["is_default"]
    r = admin.post("/api/branches", json={"code": "NORTH", "name": "North clinic", "address": "12 Ring Road"})
    assert r.status_code == 201
    assert {b["code"] for b in admin.get("/api/branches").json()} == {rows[0]["code"], "NORTH"}
    assert admin.post("/api/branches", json={"code": "NORTH", "name": "Again"}).status_code in (409, 422)


def test_prescription_pdf_has_letterhead_doctor_and_medicines(clinician):
    db = app_db.SessionLocal()
    doc = db.query(User).filter_by(email="doc@test.local").one()
    doc.registration_no, doc.registration_council, doc.qualifications = (
        "MH-45821",
        "Maharashtra Medical Council",
        "MBBS, MD",
    )
    db.commit()
    db.close()
    pid, rx_id = _final_rx(clinician)
    r = clinician.get(f"/api/prescriptions/{rx_id}/pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:5] == b"%PDF-"
    text = _text(r.content)
    for expected in ("Rohit Verma", "PR-1", "Pan 40", "Acute gastritis", "MH-45821"):
        assert expected in text, expected
    png = pdf_io.render_png(r.content, 1, width=600)[0]
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_print_settings_change_the_pdf(admin):
    admin.put("/api/settings/print", json={"title": "Sunrise Family Clinic", "footer_text": "Open 9 to 9 daily"})
    # a clinician (not the admin) writes the prescription; the admin owns the print settings
    make_user("doc2@test.local", "clinician")
    login(admin, "doc2@test.local", "Password@123")
    _, rx_id = _final_rx(admin)
    text = _text(admin.get(f"/api/prescriptions/{rx_id}/pdf").content)
    assert "Sunrise Family Clinic" in text and "Open 9 to 9 daily" in text


def test_print_preview_returns_png_without_saving(admin):
    r = admin.post("/api/settings/print/preview", json={"overrides": {"title": "Preview Only Clinic", "paper": "A5"}})
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG"
    assert admin.get("/api/settings").json()["print"]["title"] != "Preview Only Clinic"
    bad = admin.post("/api/settings/print/preview", json={"overrides": {"paper": "Legal-XXL"}})
    assert bad.status_code == 422


def test_public_verification_confirms_real_and_rejects_forged(clinician):
    from app.services import printing

    _, rx_id = _final_rx(clinician)
    sig = printing.verify_sig(rx_id)
    clinician.cookies.clear()  # an outsider scanning the QR code is not signed in
    ok = clinician.get(f"/api/verify/rx/{rx_id}", params={"s": sig})
    assert ok.status_code == 200 and ok.json()["valid"] is True
    assert "Rohit" not in ok.text and "PR-1" not in ok.text  # nothing about the patient is revealed
    assert clinician.get(f"/api/verify/rx/{rx_id}", params={"s": "0" * len(sig)}).status_code == 404


def test_appointments_are_scoped_to_the_branch(admin):
    north = admin.post("/api/branches", json={"code": "NORTH", "name": "North clinic"}).json()
    a, b = create_patient(admin, mrn="B-1")["id"], create_patient(admin, mrn="B-2", first="Bina")["id"]
    assert admin.post("/api/appointments", json={"patient_id": a, "reason": "Main desk"}).status_code == 201
    r = admin.post("/api/appointments", json={"patient_id": b, "reason": "North desk", "branch_id": north["id"]})
    assert r.status_code == 201
    # one patient cannot be on two lists on the same day, even at different branches
    dup = admin.post("/api/appointments", json={"patient_id": a, "branch_id": north["id"]})
    assert dup.status_code == 409
    main_id = next(b["id"] for b in admin.get("/api/branches").json() if b["is_default"])
    reasons = lambda **p: sorted(a["reason"] for a in admin.get("/api/appointments", params=p).json())  # noqa: E731
    assert reasons(branch_id=main_id) == ["Main desk"]
    assert reasons(branch_id=north["id"]) == ["North desk"]
    assert reasons(branch_id="all") == ["Main desk", "North desk"]


def test_registration_number_is_required_in_production(clinician, monkeypatch):
    from app.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(type(s), "is_production", property(lambda self: True))
    pid = create_patient(clinician, mrn="PR-2")["id"]
    enc = clinician.post(f"/api/patients/{pid}/consultations", json={}).json()
    rx = clinician.post(f"/api/consultations/{enc['id']}/prescription").json()
    clinician.put(
        f"/api/prescriptions/{rx['id']}", json={"items": [{"drug": "Pan 40", "dose": "1 tab", "frequency": "OD"}]}
    )
    r = clinician.post(f"/api/prescriptions/{rx['id']}/finalize", json={})
    assert r.status_code == 422 and "registration number" in r.json()["detail"]
