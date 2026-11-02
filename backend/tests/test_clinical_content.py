"""The clinical test-bank, and sign-off of clinical content by named professionals."""

import copy

import pytest

from app import db as app_db
from app.clinical import content, testbank
from app.formulary.catalog import load
from app.models import User
from tests.conftest import login, make_user

PW = "Password@123"


def test_every_clinical_case_passes():
    r = testbank.run_all()
    assert r["total"] >= 25 and r["ok"], [(c["id"], c["problems"]) for c in r["cases"] if not c["ok"]]


def test_the_test_bank_can_actually_fail():
    """A test-bank that cannot fail proves nothing, so check each way a case can be broken."""
    fm = load("IN")
    base = next(c for c in testbank.load_cases() if c["id"] == "allergy-sulfa-cotrimoxazole")

    missing = copy.deepcopy(base)
    missing["facts"]["allergies"] = []  # no allergy recorded → the rule rightly stays silent → the case must fail
    assert not testbank.run_case(fm, missing)["ok"]

    too_strict = copy.deepcopy(base)
    too_strict["expect"] = [{"item": 0, "code": "dose_daily_high", "severity": "critical"}]
    assert "not reported" in testbank.run_case(fm, too_strict)["problems"][0]

    forbidden = copy.deepcopy(base)
    forbidden["expect"], forbidden["forbid"] = [], [{"item": 0, "code": "allergy"}]
    assert "must NOT" in testbank.run_case(fm, forbidden)["problems"][0]

    noisy = copy.deepcopy(base)
    noisy["expect"], noisy["clean"] = [], True  # claims the prescription is routine, yet the allergy rule fires
    assert "routine prescription raised alerts" in testbank.run_case(fm, noisy)["problems"][0]

    weak = copy.deepcopy(base)
    weak["facts"] = {"allergies": ["Penicillin"]}
    weak["items"] = [{"drug": "Taxim-O 200", "dose": "1 tab", "frequency": "BD", "duration_days": 5}]
    weak["expect"] = [{"item": 0, "code": "cross_allergy", "severity": "critical"}]  # the rule gives only a warning
    assert "only 'warning'" in testbank.run_case(fm, weak)["problems"][0]


def test_every_case_explains_itself_and_ids_are_unique():
    cases = testbank.load_cases()
    assert len({c["id"] for c in cases}) == len(cases)
    assert all(c["why"] and c["title"] for c in cases)
    covered = {e["code"] for c in cases for e in c.get("expect", [])}
    assert {
        "allergy",
        "renal",
        "pregnancy",
        "duplicate",
        "interaction",
        "weekly_only",
        "paediatric_dose",
        "elderly",
        "condition",
        "hepatic",
    } <= covered


def test_content_hash_is_stable_and_follows_the_content(tmp_path, monkeypatch):
    area = content.AREAS["calculators"]
    assert content.content_hash(area) == content.content_hash(area)
    f = tmp_path / "rules.txt"
    f.write_text("v1")
    custom = content.Area("x", "X", "", ("clinical_lead",), (f,))
    a = content.content_hash(custom)
    f.write_text("v2")
    assert content.content_hash(custom) != a


def _doctor(email, reg="KMC-1", name="Doctor"):
    make_user(email, "clinician")
    db = app_db.SessionLocal()
    u = db.query(User).filter_by(email=email).one()
    u.registration_no, u.registration_council, u.full_name = reg, "Karnataka Medical Council", name
    db.commit()
    db.close()


def _viewer_pharmacist(email, reg="KPC-9"):
    make_user(email, "viewer")
    db = app_db.SessionLocal()
    u = db.query(User).filter_by(email=email).one()
    u.registration_no, u.full_name = reg, "Pharma Cist"
    db.commit()
    db.close()


def test_signing_needs_a_password_a_registration_number_and_the_right_role(clinician):
    base = "/api/clinical-content/formulary/sign"
    assert clinician.post(base, json={"role": "clinical_lead", "password": "wrong"}).status_code == 403
    assert (
        clinician.post(base, json={"role": "clinical_lead", "password": PW}).status_code == 422
    )  # no registration number yet
    _doctor("lead@test.local", name="Anita Rao")
    login(clinician, "lead@test.local", PW)
    assert clinician.post(base, json={"role": "nurse", "password": PW}).status_code == 422
    assert (
        clinician.post(
            "/api/clinical-content/calculators/sign", json={"role": "pharmacist", "password": PW}
        ).status_code
        == 422
    )  # not a role for this area
    r = clinician.post(base, json={"role": "clinical_lead", "password": PW})
    assert r.status_code == 200
    s = r.json()
    assert s["status"] == "partial" and [m["role"] for m in s["missing"]] == ["pharmacist"]
    assert (
        s["signoffs"][0]["registration_no"] == "KMC-1"
        and s["signoffs"][0]["tests"].split("/")[0] == s["signoffs"][0]["tests"].split("/")[1]
    )


def test_two_different_people_must_sign_the_rules(admin):
    _doctor("lead@test.local", "KMC-1", "Anita Rao")
    _viewer_pharmacist("pharm@test.local")
    base = "/api/clinical-content/formulary/sign"
    login(admin, "lead@test.local", PW)
    assert admin.post(base, json={"role": "clinical_lead", "password": PW}).status_code == 200
    assert (
        admin.post(base, json={"role": "clinical_lead", "password": PW}).status_code == 409
    )  # already signed for that role
    assert (
        admin.post(base, json={"role": "pharmacist", "password": PW}).status_code == 409
    )  # the same person cannot sign both
    login(admin, "pharm@test.local", PW)
    done = admin.post(base, json={"role": "pharmacist", "password": PW}).json()
    assert done["status"] == "signed"
    assert {s["role"] for s in done["signoffs"] if s["current"]} == {"clinical_lead", "pharmacist"}
    overview = admin.get("/api/clinical-content").json()
    assert overview["overall"] == "incomplete" and overview["areas"][0]["status"] == "signed"


def test_a_signature_lapses_when_the_content_changes(admin, monkeypatch):
    _doctor("lead@test.local", "KMC-1", "Anita Rao")
    login(admin, "lead@test.local", PW)
    assert (
        admin.post("/api/clinical-content/calculators/sign", json={"role": "clinical_lead", "password": PW}).json()[
            "status"
        ]
        == "signed"
    )
    # the reviewed content changes (as it would in a new product version)
    real = content.content_hash
    monkeypatch.setattr(content, "content_hash", lambda area: "f" * 64 if area.key == "calculators" else real(area))
    s = admin.get("/api/clinical-content").json()["areas"]
    calc = next(a for a in s if a["key"] == "calculators")
    assert calc["status"] == "changed" and calc["signoffs"][0]["current"] is False
    assert (
        admin.post("/api/clinical-content/calculators/sign", json={"role": "clinical_lead", "password": PW}).json()[
            "status"
        ]
        == "signed"
    )  # re-review


def test_rules_cannot_be_signed_while_a_clinical_test_fails(admin, monkeypatch):
    _doctor("lead@test.local", "KMC-1", "Anita Rao")
    login(admin, "lead@test.local", PW)
    broken = testbank.run_all()
    broken["ok"], broken["failed"] = False, 2
    monkeypatch.setattr(testbank, "run_all", lambda *a, **k: broken)
    r = admin.post("/api/clinical-content/formulary/sign", json={"role": "clinical_lead", "password": PW})
    assert r.status_code == 422 and "failing" in r.json()["detail"]


def test_an_administrator_can_revoke_a_signature_with_a_reason(admin):
    _doctor("lead@test.local", "KMC-1", "Anita Rao")
    login(admin, "lead@test.local", PW)
    sid = admin.post("/api/clinical-content/calculators/sign", json={"role": "clinical_lead", "password": PW}).json()[
        "signoffs"
    ][0]["id"]
    assert (
        admin.post(
            f"/api/clinical-content/signoffs/{sid}/revoke", json={"reason": "Reviewer left the clinic"}
        ).status_code
        == 403
    )  # a clinician cannot
    login(admin)
    assert admin.post(f"/api/clinical-content/signoffs/{sid}/revoke", json={"reason": "x"}).status_code == 422
    r = admin.post(f"/api/clinical-content/signoffs/{sid}/revoke", json={"reason": "Reviewer left the clinic"}).json()
    assert r["status"] == "unsigned" and r["signoffs"][0]["revoked"] is True


def test_security_checklist_reports_the_review_state(admin):
    items = {i["id"]: i for i in admin.get("/api/system/security").json()["items"]}
    assert items["clinical_content"]["ok"] is False


def test_front_desk_cannot_read_clinical_content_status(admin):
    make_user("desk@test.local", "front_desk")
    login(admin, "desk@test.local", PW)
    assert admin.get("/api/clinical-content").status_code == 403


def test_selftest_endpoint_records_its_result(admin):
    r = admin.post("/api/clinical-content/selftest").json()
    assert r["ok"] and admin.get("/api/clinical-content").json()["selftest"]["passed"] == r["total"]


@pytest.mark.parametrize("key", list(content.AREAS))
def test_every_content_area_has_content_to_hash(key):
    assert any(content._files(p) for p in content.AREAS[key].paths), f"{key} has nothing to review"
