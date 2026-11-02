from datetime import date

from tests.conftest import create_patient


def _obs(c, pid, name, code, v, unit=""):
    c.post(f"/api/patients/{pid}/observations", json={"name": name, "code": code, "value_num": v, "unit": unit})


def test_scores_only_appear_when_applicable(clinician):
    p = create_patient(clinician, date_of_birth="1990-01-01")
    assert clinician.get(f"/api/patients/{p['id']}/scores").json() == []


def test_ckd_cha2ds2vasc_and_drug_checks(clinician):
    dob = date(date.today().year - 72, 1, 1).isoformat()
    pid = create_patient(clinician, date_of_birth=dob)["id"]  # female
    for name in ("Atrial fibrillation", "Heart failure with reduced ejection fraction", "Essential hypertension"):
        clinician.post(f"/api/patients/{pid}/conditions", json={"name": name})
    clinician.post(
        f"/api/patients/{pid}/medications", json={"name": "Apixaban", "dose": "5 mg", "frequency": "twice daily"}
    )
    clinician.post(f"/api/patients/{pid}/encounters", json={"reason": "Clinic", "vitals": {"weight_kg": 58}})
    _obs(clinician, pid, "eGFR", "egfr", 41)
    _obs(clinician, pid, "UACR", "uacr", 120)
    _obs(clinician, pid, "Creatinine", "creatinine", 1.5, "mg/dL")
    items = {s["id"]: s for s in clinician.get(f"/api/patients/{pid}/scores").json()}
    assert items["ckd_kdigo"]["value"] == "G3b A2" and items["ckd_kdigo"]["category"] == "Very high risk"
    # age 65-74 (1) + female (1) + HF (1) + HTN (1)
    assert items["cha2ds2vasc"]["value"] == "4" and items["cha2ds2vasc"]["category"] == "Anticoagulation recommended"
    assert items["apixaban_dose"]["value"] == "2 of 3" and items["apixaban_dose"]["level"] == 3
    assert "glycaemic" not in items  # no diabetes documented


def test_missing_inputs_are_reported_not_assumed(clinician):
    pid = create_patient(clinician)["id"]  # no DOB
    clinician.post(f"/api/patients/{pid}/conditions", json={"name": "Paroxysmal atrial fibrillation"})
    s = next(x for x in clinician.get(f"/api/patients/{pid}/scores").json() if x["id"] == "cha2ds2vasc")
    assert "Age (date of birth)" in s["missing"]


def test_keyword_matching_is_whole_word(clinician):
    pid = create_patient(clinician, date_of_birth="1990-01-01", sex="male")["id"]
    for name in ("Atrial fibrillation", "Essential hypertension"):
        clinician.post(f"/api/patients/{pid}/conditions", json={"name": name})
    s = next(x for x in clinician.get(f"/api/patients/{pid}/scores").json() if x["id"] == "cha2ds2vasc")
    assert s["value"] == "1"  # hypertension only — "essential" is not a TIA
