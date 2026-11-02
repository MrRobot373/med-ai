"""Prescription templates and favourites, repeat-last, and letters (certificates, referrals, summaries)."""

from app.ingestion import pdf as pdf_io
from app.services import printing
from tests.conftest import create_patient, login, make_user


def _text(data: bytes) -> str:
    return "\n".join(p["text"] for p in pdf_io.extract_pages(data))


ITEMS = [
    {"drug": "Pan 40", "dose": "1 tab", "frequency": "OD", "duration_days": 14, "instructions": "Before breakfast"},
    {"drug": "Dolo 650", "dose": "1 tab", "frequency": "TDS", "duration_days": 3},
]


def _issued_rx(c, pid, items=ITEMS, diagnosis="Acute gastritis"):
    enc = c.post(f"/api/patients/{pid}/consultations", json={}).json()
    rx = c.post(f"/api/consultations/{enc['id']}/prescription").json()
    c.put(f"/api/prescriptions/{rx['id']}", json={"diagnosis": diagnosis, "advice": "Avoid spicy food", "items": items})
    assert c.post(f"/api/prescriptions/{rx['id']}/finalize", json={}).status_code == 200
    return enc, rx


def test_template_lifecycle_and_sharing_rules(clinician):
    r = clinician.post("/api/rx/templates", json={"name": "Gastritis", "diagnosis": "Acute gastritis", "items": ITEMS})
    assert r.status_code == 201 and r.json()["mine"] and len(r.json()["items"]) == 2
    tid = r.json()["id"]
    assert clinician.post("/api/rx/templates", json={"name": "X", "items": ITEMS, "is_shared": True}).status_code == 403
    assert clinician.get("/api/rx/templates").json()[0]["id"] == tid
    clinician.post(f"/api/rx/templates/{tid}/used")
    assert clinician.get("/api/rx/templates").json()[0]["use_count"] == 1
    assert clinician.post("/api/rx/templates", json={"name": "Empty", "items": []}).status_code == 422
    assert clinician.delete(f"/api/rx/templates/{tid}").status_code == 204
    assert clinician.get("/api/rx/templates").json() == []


def test_shared_template_is_visible_to_others_but_only_owner_or_admin_can_change(admin):
    t = admin.post("/api/rx/templates", json={"name": "Clinic standard", "items": ITEMS, "is_shared": True}).json()
    make_user("doc@test.local", "clinician")
    login(admin, "doc@test.local", "Password@123")
    seen = admin.get("/api/rx/templates").json()
    assert [x["id"] for x in seen] == [t["id"]] and seen[0]["mine"] is False
    assert admin.delete(f"/api/rx/templates/{t['id']}").status_code == 403
    assert (
        admin.put(
            f"/api/rx/templates/{t['id']}", json={"name": "Hijack", "items": ITEMS, "is_shared": True}
        ).status_code
        == 403
    )


def test_template_from_prescription_favourites_frequent_and_repeat_last(clinician):
    pid = create_patient(clinician, mrn="L-1", first="Rohit", last="Verma", date_of_birth="1957-05-10", sex="male")[
        "id"
    ]
    assert clinician.get(f"/api/rx/patients/{pid}/last").json()["items"] == []
    _, rx = _issued_rx(clinician, pid)
    saved = clinician.post(
        "/api/rx/templates/from-prescription", json={"prescription_id": rx["id"], "name": "My gastritis"}
    ).json()
    assert saved["diagnosis"] == "Acute gastritis" and [i["drug"] for i in saved["items"]] == ["Pan 40", "Dolo 650"]

    last = clinician.get(f"/api/rx/patients/{pid}/last").json()
    assert last["prescription_id"] == rx["id"] and last["items"][0]["instructions"] == "Before breakfast"

    fav = clinician.post("/api/rx/favourites", json={"drug": "Telma 40", "dose": "1 tab", "frequency": "OD"}).json()
    clinician.post(
        "/api/rx/favourites", json={"drug": "Telma 40", "dose": "1 tab", "frequency": "BD"}
    )  # same drug: updated
    favs = clinician.get("/api/rx/favourites").json()
    assert len(favs) == 1 and favs[0]["frequency"] == "BD"
    assert clinician.delete(f"/api/rx/favourites/{fav['id']}").status_code == 204

    top = clinician.get("/api/rx/frequent").json()
    assert {t["drug"] for t in top} == {"Pan 40", "Dolo 650"} and top[0]["times"] == 1


def test_medical_certificate_numbering_pdf_and_immutability(clinician):
    pid = create_patient(clinician, mrn="L-2", first="Asha", last="Nair", date_of_birth="1990-02-01", sex="female")[
        "id"
    ]
    a = clinician.post(f"/api/patients/{pid}/letters", json={"kind": "medical_certificate"}).json()
    assert a["status"] == "draft" and a["number"] is None and a["fields"]["days"] == 3
    edited = clinician.patch(
        f"/api/letters/{a['id']}", json={"fields": {"from_date": "2026-11-02", "to_date": "2026-11-06"}}
    ).json()
    assert edited["fields"]["days"] == 5
    assert (
        clinician.patch(
            f"/api/letters/{a['id']}", json={"fields": {"from_date": "2026-11-09", "to_date": "2026-11-06"}}
        ).status_code
        == 422
    )

    issued = clinician.post(f"/api/letters/{a['id']}/issue").json()
    assert issued["status"] == "final" and issued["number"].startswith("MC-") and issued["number"].endswith("-0001")
    assert clinician.patch(f"/api/letters/{a['id']}", json={"body": "changed"}).status_code == 409
    assert clinician.delete(f"/api/letters/{a['id']}").status_code == 409

    b = clinician.post(f"/api/patients/{pid}/letters", json={"kind": "medical_certificate"}).json()
    assert clinician.post(f"/api/letters/{b['id']}/issue").json()["number"].endswith("-0002")  # no gaps, no repeats

    r = clinician.get(f"/api/letters/{a['id']}/pdf")
    text = _text(r.content)
    assert r.headers["content-type"] == "application/pdf"
    for expected in ("MEDICAL CERTIFICATE", issued["number"], "Asha Nair", "L-2", "advised rest for 5 days"):
        assert expected in text, expected

    assert clinician.post(f"/api/letters/{a['id']}/void", json={"reason": "x"}).status_code == 422
    voided = clinician.post(f"/api/letters/{a['id']}/void", json={"reason": "Wrong dates"}).json()
    assert voided["status"] == "void"
    assert clinician.post(f"/api/letters/{a['id']}/issue").status_code == 409


def test_referral_is_prefilled_from_the_record_and_needs_a_recipient(clinician):
    pid = create_patient(clinician, mrn="L-3", first="Rohit", last="Verma", date_of_birth="1957-05-10", sex="male")[
        "id"
    ]
    clinician.post(f"/api/patients/{pid}/conditions", json={"name": "Type 2 diabetes mellitus"})
    clinician.post(f"/api/patients/{pid}/allergies", json={"substance": "Sulfa drugs", "reaction": "rash"})
    clinician.post(
        f"/api/patients/{pid}/medications", json={"name": "Metformin 500", "dose": "1 tab", "frequency": "BD"}
    )
    r = clinician.post(f"/api/patients/{pid}/letters", json={"kind": "referral"}).json()
    f = r["fields"]
    assert (
        "Type 2 diabetes" in f["problems"]
        and "Sulfa drugs (rash)" in f["allergies"]
        and "Metformin 500" in f["medicines"]
    )
    assert clinician.post(f"/api/letters/{r['id']}/issue").status_code == 422
    clinician.patch(
        f"/api/letters/{r['id']}",
        json={
            "fields": {
                "to_name": "Dr. Kapoor",
                "to_speciality": "Nephrology",
                "reason": "Rising creatinine",
                "urgency": "urgent",
            }
        },
    )
    issued = clinician.post(f"/api/letters/{r['id']}/issue").json()
    text = _text(clinician.get(f"/api/letters/{issued['id']}/pdf").content)
    for expected in (
        "REFERRAL LETTER",
        "Dr. Kapoor",
        "Nephrology",
        "Rising creatinine",
        "Metformin 500",
        "Sulfa drugs",
        "URGENT",
    ):
        assert expected in text, expected


def test_visit_summary_is_the_patient_copy(clinician):
    pid = create_patient(clinician, mrn="L-4", first="Meena", last="Iyer", date_of_birth="1980-01-01", sex="female")[
        "id"
    ]
    enc, _ = _issued_rx(clinician, pid)
    s = clinician.post(f"/api/patients/{pid}/letters", json={"kind": "visit_summary", "encounter_id": enc["id"]}).json()
    assert [i["drug"] for i in s["fields"]["items"]] == ["Pan 40", "Dolo 650"] and s["fields"][
        "diagnosis"
    ] == "Acute gastritis"
    issued = clinician.post(f"/api/letters/{s['id']}/issue").json()
    text = _text(clinician.get(f"/api/letters/{issued['id']}/pdf").content)
    assert "VISIT SUMMARY" in text and "Pan 40" in text and "Three times a day" in text and "Avoid spicy food" in text


def test_letters_can_be_verified_publicly_and_forgeries_fail(clinician):
    pid = create_patient(clinician, mrn="L-5")["id"]
    a = clinician.post(f"/api/patients/{pid}/letters", json={"kind": "fitness"}).json()
    clinician.patch(f"/api/letters/{a['id']}", json={"fields": {"purpose": "join school"}})
    issued = clinician.post(f"/api/letters/{a['id']}/issue").json()
    sig = printing.verify_sig(a["id"], "letter")
    clinician.cookies.clear()
    ok = clinician.get(f"/api/verify/letter/{a['id']}", params={"s": sig})
    assert ok.status_code == 200 and ok.json()["number"] == issued["number"] and "Tester" not in ok.text
    assert clinician.get(f"/api/verify/letter/{a['id']}", params={"s": "0" * 16}).status_code == 404
    # a prescription signature must not validate a letter
    assert clinician.get(f"/api/verify/letter/{a['id']}", params={"s": printing.verify_sig(a["id"])}).status_code == 404


def test_viewer_can_read_but_not_write_and_front_desk_sees_nothing(admin):
    pid = create_patient(admin, mrn="L-6")["id"]
    letter = admin.post(f"/api/patients/{pid}/letters", json={"kind": "fitness"}).json()
    make_user("view@test.local", "viewer")
    make_user("desk@test.local", "front_desk")
    login(admin, "view@test.local", "Password@123")
    assert admin.get(f"/api/letters/{letter['id']}").status_code == 200
    assert admin.post(f"/api/patients/{pid}/letters", json={"kind": "fitness"}).status_code == 403
    login(admin, "desk@test.local", "Password@123")
    assert admin.get(f"/api/letters/{letter['id']}").status_code == 403
    assert admin.get("/api/rx/templates").status_code == 403
