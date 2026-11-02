"""Duplicate warning, merging two charts, automatic MRNs and importing patients from a spreadsheet."""

import io

from app import db as app_db
from app.models import Chunk, Document
from app.services import dedupe
from tests.conftest import create_patient, lab_pdf, login, make_user, upload


def _reg(c, **kw):
    body = {
        "first_name": "Rohit",
        "last_name": "Verma",
        "sex": "male",
        "date_of_birth": "1957-05-10",
        "phone": "+91 98765 43210",
        **kw,
    }
    return c.post("/api/patients", json=body)


def test_matching_scores_and_reasons():
    a = {
        "first_name": "Rohit",
        "last_name": "Verma",
        "date_of_birth": "1957-05-10",
        "phone": "98765 43210",
        "email": None,
    }
    same = {**a, "phone": "+91-98765-43210"}
    swapped = {**a, "first_name": "Verma", "last_name": "Rohit"}
    other_dob = {**a, "date_of_birth": "1990-01-01"}
    family = {
        "first_name": "Sunita",
        "last_name": "Verma",
        "date_of_birth": None,
        "phone": "98765 43210",
        "email": None,
    }
    assert dedupe.compare(a, same)[0] >= dedupe.STRONG
    assert dedupe.compare(a, swapped)[0] >= dedupe.STRONG
    assert dedupe.compare(a, other_dob)[0] < dedupe.STRONG
    assert dedupe.compare(a, family)[0] < dedupe.POSSIBLE  # a shared family phone is not a duplicate


def test_registration_is_stopped_for_a_clear_duplicate_but_can_be_overridden(admin):
    first = _reg(admin, mrn="D-1")
    assert first.status_code == 201
    again = _reg(admin, mrn="D-2", phone="9876543210")
    assert again.status_code == 409 and again.json()["code"] == "possible_duplicate"
    assert again.json()["matches"][0]["mrn"] == "D-1" and "same date of birth" in again.json()["matches"][0]["reasons"]
    assert _reg(admin, mrn="D-2", phone="9876543210", allow_duplicate=True).status_code == 201
    # the same name alone (no date of birth, no phone) is only a warning on the check endpoint, never a block
    assert admin.post("/api/patients", json={"first_name": "Rohit", "last_name": "Verma"}).status_code == 201
    chk = admin.post("/api/patients/duplicates/check", json={"first_name": "Rohit", "last_name": "Verma"}).json()
    d1 = next(m for m in chk if m["mrn"] == "D-1")
    assert d1["reasons"] == ["same name"] and d1["strong"] is False


def test_mrn_is_generated_when_left_blank(admin):
    admin.put("/api/settings/branding", json={"organization": "Life Care Medico"})
    a = admin.post("/api/patients", json={"first_name": "Asha", "last_name": "Nair"}).json()
    b = admin.post("/api/patients", json={"first_name": "Bina", "last_name": "Shah"}).json()
    assert a["mrn"].startswith("LCM-") and b["mrn"] != a["mrn"]
    # a hand-typed number that the sequence would reach later is skipped, not collided with
    assert admin.get("/api/patients/next-mrn").json()["prefix"] == "LCM"


def test_merge_moves_everything_and_hides_the_duplicate(admin):
    keep = create_patient(admin, mrn="M-1", first="Rohit", last="Verma", date_of_birth="1957-05-10", sex="male")["id"]
    dupe = _reg(admin, mrn="M-2", allow_duplicate=True).json()["id"]
    for pid in (keep, dupe):
        admin.post(f"/api/patients/{pid}/conditions", json={"name": "Type 2 diabetes mellitus"})
    admin.post(f"/api/patients/{dupe}/allergies", json={"substance": "Sulfa drugs"})
    admin.post(f"/api/patients/{dupe}/medications", json={"name": "Metformin 500", "dose": "1 tab", "frequency": "BD"})
    admin.post("/api/appointments", json={"patient_id": dupe, "reason": "Follow-up"})
    admin.post(f"/api/patients/{dupe}/consultations", json={})
    up = upload(admin, dupe, lab_pdf("Rohit Verma", "M-2", [("HbA1c", "7.1", "%", "4.0-5.6")]))
    assert up.status_code == 201

    assert (
        admin.post("/api/patients/merge", json={"keep_id": keep, "merge_id": dupe, "confirm_mrn": "wrong"}).status_code
        == 422
    )
    assert (
        admin.post("/api/patients/merge", json={"keep_id": keep, "merge_id": keep, "confirm_mrn": "M-1"}).status_code
        == 422
    )
    r = admin.post("/api/patients/merge", json={"keep_id": keep, "merge_id": dupe, "confirm_mrn": "M-2"})
    assert r.status_code == 200, r.text
    assert r.json()["duplicates_removed"] == 1  # the diabetes entry that both charts had

    names = [c["name"] for c in admin.get(f"/api/patients/{keep}/conditions").json()]
    assert names == ["Type 2 diabetes mellitus"]
    assert [a["substance"] for a in admin.get(f"/api/patients/{keep}/allergies").json()] == ["Sulfa drugs"]
    assert admin.get(f"/api/patients/{keep}/medications").json()[0]["name"] == "Metformin 500"
    assert admin.get(f"/api/patients/{dupe}/conditions").json() == []
    assert len(admin.get(f"/api/patients/{keep}/documents").json()) == 1
    assert admin.get("/api/patients").json()[0]["mrn"] == "M-1" and len(admin.get("/api/patients").json()) == 1
    db = app_db.SessionLocal()
    assert (
        db.query(Chunk).filter(Chunk.patient_id == dupe).count() == 0
        and db.query(Chunk).filter(Chunk.patient_id == keep).count() > 0
    )
    assert db.query(Document).filter(Document.patient_id == keep).count() == 1
    db.close()
    # semantic search over the merged chart still finds the report that was uploaded to the duplicate
    import asyncio

    from app.ai import registry
    from app.rag import vector_store
    from app.services import runtime_config

    async def hits(patient_id):
        cfg = runtime_config.load(app_db.SessionLocal())
        vec = await registry.embedder(cfg).embed_query("HbA1c 7.1")
        return await registry.vector_store(cfg).search("patient", vec, 5, patient_id=patient_id)

    assert asyncio.run(hits(keep)) and not asyncio.run(hits(dupe))
    vector_store.reset_clients()
    assert (
        admin.post("/api/patients/merge", json={"keep_id": keep, "merge_id": dupe, "confirm_mrn": "M-2"}).status_code
        == 409
    )
    logged = admin.get("/api/audit", params={"action": "patient.merge"}).json()
    rows = logged["items"] if isinstance(logged, dict) else logged
    merged = [r for r in rows if r["action"] == "patient.merge"]
    assert len(merged) == 1 and "M-2" in merged[0]["summary"]
    assert any(r["action"] == "patient.merged_away" for r in rows)  # the merged-away chart's own history says so too
    assert admin.get("/api/audit/verify").json()["ok"] is True  # merging never rewrites the audit trail


def test_scan_finds_duplicate_pairs(admin):
    create_patient(admin, mrn="S-1", first="Asha", last="Nair", date_of_birth="1990-02-01")
    _reg(admin, mrn="S-2", first_name="Asha", last_name="Nair", date_of_birth="1990-02-01", allow_duplicate=True)
    create_patient(admin, mrn="S-3", first="Someone", last="Else", date_of_birth="1970-01-01")
    pairs = admin.get("/api/patients/duplicates").json()
    assert len(pairs) == 1 and {pairs[0]["a"]["mrn"], pairs[0]["b"]["mrn"]} == {"S-1", "S-2"}


CSV = (
    "UHID,Patient Name,Gender,DOB,Mobile,Email\n"
    "H-100,Dr. Meera Pillai,F,12/03/1985,98450 11111,meera@example.com\n"
    ",Suresh Kumar,M,1971-07-04,98450 22222,\n"
    "H-100,Duplicate Mrn,M,01/01/1980,,\n"
    "H-102,,F,01/01/1980,,\n"
    "H-103,Ravi Rao,M,31/02/1980,,\n"
    "H-104,Bad Email,M,01/01/1980,,not-an-email\n"
)


def _import(c, data=CSV, name="patients.csv", **form):
    return c.post(
        "/api/patients/import",
        files={"file": (name, data.encode() if isinstance(data, str) else data, "text/csv")},
        data=form,
    )


def test_import_preview_reports_every_problem_without_saving(admin):
    create_patient(admin, mrn="H-100", first="Existing", last="Person")
    r = _import(admin).json()
    assert r["mapping"]["mrn"] == 0 and r["mapping"]["full_name"] == 1 and r["mapping"]["date_of_birth"] == 3
    s = r["summary"]
    assert s == {"new": 1, "exists": 2, "error": 3} and r["committed"] is False
    errors = [x["errors"][0] for x in r["rows"] if x["status"] == "error"]
    assert (
        any("Name is missing" in e for e in errors)
        and any("not recognised" in e for e in errors)
        and any("Email" in e for e in errors)
    )
    assert len(admin.get("/api/patients?status=all").json()) == 1  # nothing was saved


def test_import_commit_creates_patients_with_generated_mrns_and_audit(admin):
    r = _import(
        admin, "Name,DOB,Phone\nAsha Nair,01/02/1990,9845011111\nBina Shah,05/06/1975,9845022222\n", commit="true"
    ).json()
    assert r["committed"] and r["created"] == 2
    got = {p["full_name"]: p for p in admin.get("/api/patients").json()}
    assert got["Asha Nair"]["date_of_birth"] == "1990-02-01" and got["Asha Nair"]["mrn"] != got["Bina Shah"]["mrn"]
    assert "imported" in got["Asha Nair"]["tags"]
    # importing the same file again creates nothing new: both are now strong duplicates of themselves
    again = _import(admin, "Name,DOB,Phone\nAsha Nair,01/02/1990,9845011111\n").json()
    assert again["summary"] == {"possible_duplicate": 1}
    forced = _import(
        admin, "Name,DOB,Phone\nAsha Nair,01/02/1990,9845011111\n", commit="true", include_possible="true"
    ).json()
    assert forced["created"] == 1


def test_import_needs_a_name_column_and_rejects_bad_files(admin):
    r = _import(admin, "Phone,City\n9845011111,Pune\n").json()
    assert r["needs_mapping"] is True and r["summary"] is None
    assert _import(admin, "x", name="notes.pdf").status_code == 422
    assert _import(admin, "Name\n", name="empty.csv").status_code == 422
    mapped = _import(admin, "Phone,Person\n9845011111,Asha Nair\n", mapping='{"full_name": 1, "phone": 0}').json()
    assert mapped["summary"] == {"new": 1}


def test_import_excel_file(admin):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Patient Name", "Sex", "Date of birth"])
    ws.append(["Kavya Menon", "Female", "14/08/1999"])
    buf = io.BytesIO()
    wb.save(buf)
    r = admin.post(
        "/api/patients/import",
        files={"file": ("p.xlsx", buf.getvalue(), "application/octet-stream")},
        data={"commit": "true"},
    ).json()
    assert r["created"] == 1 and admin.get("/api/patients").json()[0]["sex"] == "female"


def test_viewer_cannot_import_or_merge(admin):
    a = create_patient(admin, mrn="V-1")["id"]
    b = create_patient(admin, mrn="V-2", first="Other")["id"]
    make_user("view@test.local", "viewer")
    login(admin, "view@test.local", "Password@123")
    assert _import(admin).status_code == 403
    assert (
        admin.post("/api/patients/merge", json={"keep_id": a, "merge_id": b, "confirm_mrn": "V-2"}).status_code == 403
    )
    assert admin.get("/api/patients/duplicates").status_code == 403
