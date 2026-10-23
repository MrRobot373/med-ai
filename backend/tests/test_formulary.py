import httpx
import pytest

from app.formulary import images
from app.formulary.catalog import load
from app.formulary.dosing import parse_dose, parse_frequency
from app.formulary.engine import ItemInput, check
from app.formulary.facts import CurrentMed, Fact, PatientFacts, ckd_epi_2021

FM = load("IN")


def facts(**kw) -> PatientFacts:
    base = dict(patient_id="p", name="Test", age=45, sex="male")
    base.update(kw)
    return PatientFacts(**base)


def findings(result, idx=0):
    return {(f["code"], f["severity"]) for f in result["items"][idx]["findings"]}


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Dolo 650", {"paracetamol": 650}),
        ("Tab. Pan 40", {"pantoprazole": 40}),
        ("Augmentin 625", {"amoxicillin": 500, "clavulanic_acid": 125}),
        ("co-amoxiclav 1000", {"amoxicillin": 875, "clavulanic_acid": 125}),
        ("Glycomet-GP 2", {"glimepiride": 2, "metformin": 500}),
        ("pantoprazole 40 mg", {"pantoprazole": 40}),
        ("Folitrax 7.5", {"methotrexate": 7.5}),
        ("Uprise-D3", {"cholecalciferol": 60000}),
    ],
)
def test_resolves_indian_brands(text, expected):
    r = FM.resolve(text)
    assert r.matched and r.components == expected


def test_brand_without_strength_knows_generic_not_amount():
    r = FM.resolve("Crocin")
    assert r.generic_ids == ["paracetamol"] and not r.strength_known


def test_dose_and_frequency_parsing():
    assert parse_dose("½ tab").quantity == 0.5
    assert parse_dose("1 g").quantity == 1000 and parse_dose("1 g").unit == "mg"
    assert parse_frequency("1-0-1").per_day == 2
    assert parse_frequency("TDS").per_day == 3
    assert parse_frequency("weekly").weekly
    sos = parse_frequency("SOS", "max 4 times a day")
    assert sos.prn and sos.per_day == 4 and not sos.assumed


def test_ckd_epi_2021():
    # Reference values from the 2021 equation
    assert round(ckd_epi_2021(1.0, 50, "male")) == 92
    assert round(ckd_epi_2021(1.0, 50, "female")) == 69


def test_normal_adult_dose_is_clean():
    out = check(FM, facts(), [ItemInput("Dolo 650", "1 tab", "TDS", 3)])
    assert out["status"] == "ok" and out["items"][0]["per_day"] == {"paracetamol": 1950}


def test_daily_maximum_exceeded():
    out = check(FM, facts(), [ItemInput("Dolo 650", "2 tab", "QID")])
    assert ("dose_daily_high", "critical") in findings(out)


def test_low_dose_flagged_as_possible_undertreatment():
    out = check(FM, facts(), [ItemInput("Glycomet 250", "1 tab", "OD")])
    assert ("dose_low", "info") in findings(out)


def test_renal_maximum_for_metformin():
    f = facts(age=72, egfr=Fact(38, "reported eGFR", "2026-09-01"))
    out = check(FM, f, [ItemInput("Glycomet 1000", "1 tab", "BD")])
    codes = findings(out)
    assert ("dose_daily_high", "critical") in codes
    ok = check(FM, f, [ItemInput("Glycomet 500", "1 tab", "BD")])
    assert ("dose_daily_high", "critical") not in findings(ok)
    severe = check(FM, facts(egfr=Fact(25, "reported eGFR")), [ItemInput("Glycomet 500", "1 tab", "BD")])
    assert ("renal", "critical") in findings(severe)


def test_elderly_lower_ceiling_and_beers():
    out = check(FM, facts(age=70), [ItemInput("Nexito 20", "1 tab", "OD")])
    assert ("dose_daily_high", "critical") in findings(out)  # escitalopram >65: max 10 mg
    glib = check(FM, facts(age=78), [ItemInput("Daonil 5", "1 tab", "OD")])
    assert ("elderly", "critical") in findings(glib)


def test_condition_contraindication_and_allergy_groups():
    f = facts(
        conditions=["Peptic ulcer disease"],
        allergies=[{"substance": "Penicillin", "reaction": "hives", "severity": "moderate", "groups": ["penicillin"]}],
    )
    out = check(
        FM,
        f,
        [
            ItemInput("Brufen 400", "1 tab", "TDS"),
            ItemInput("Augmentin 625", "1 tab", "TDS"),
            ItemInput("Taxim-O 200", "1 tab", "BD"),
        ],
    )
    assert ("condition", "critical") in findings(out, 0)
    assert ("allergy", "critical") in findings(out, 1)
    assert ("cross_allergy", "warning") in findings(out, 2)


def test_interactions_with_current_medicines():
    f = facts(current_meds=[CurrentMed("m", "Warf 5", ["warfarin"], ["anticoagulant"], "1 tab", "OD")])
    out = check(FM, f, [ItemInput("Flagyl 400", "1 tab", "TDS", 5), ItemInput("Brufen 400", "1 tab", "TDS")])
    assert ("interaction", "critical") in findings(out, 0)
    assert ("interaction", "critical") in findings(out, 1)


def test_combined_ingredient_total():
    out = check(FM, facts(), [ItemInput("Dolo 650", "1 tab", "QID"), ItemInput("Combiflam", "2 tab", "TDS")])
    assert ("combined_total", "critical") in findings(out, 0)
    assert ("duplicate", "critical") in findings(out, 1)


def test_methotrexate_must_be_weekly():
    out = check(FM, facts(), [ItemInput("Folitrax 7.5", "1 tab", "OD")])
    assert ("weekly_only", "critical") in findings(out)
    ok = check(FM, facts(), [ItemInput("Folitrax 7.5", "1 tab", "weekly")])
    assert ok["status"] in ("ok", "info")


def test_pregnancy_and_potassium_rules():
    f = facts(
        sex="female",
        pregnant=True,
        labs={"potassium": {"name": "Potassium", "value": 5.8, "unit": "mmol/L", "date": "2026-10-01"}},
    )
    out = check(FM, f, [ItemInput("Telma 40", "1 tab", "OD")])
    codes = findings(out)
    assert ("pregnancy", "critical") in codes and ("lab", "critical") in codes


def test_paediatric_weight_based_dose():
    child = facts(age=6, weight=Fact(20, "vitals"))
    out = check(FM, child, [ItemInput("Syp Calpol 250", "10 ml", "QID")])  # 500 mg/dose = 25 mg/kg
    assert ("paediatric_dose", "critical") in findings(out)
    fine = check(FM, child, [ItemInput("Syp Calpol 250", "5 ml", "QID")])  # 250 mg = 12.5 mg/kg
    assert ("paediatric_dose", "critical") not in findings(fine)


def test_unknown_medicine_is_reported_not_guessed():
    out = check(FM, facts(), [ItemInput("Zyxolin 10", "1 tab", "OD")])
    assert out["items"][0]["recognised"] is False and ("unknown_drug", "info") in findings(out)


def test_search_autocomplete():
    labels = [o["label"] for o in FM.search("dolo")]
    assert "Dolo 650" in labels
    assert any(o["generic"] == "paracetamol" for o in FM.search("paraceta"))


async def test_image_fetch_and_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "cache_dir", lambda: tmp_path)
    calls = {"n": 0}

    def handler(request: httpx.Request):
        calls["n"] += 1
        if "api.php" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "query": {
                        "pages": {
                            "1": {
                                "index": 1,
                                "title": "File:Paracetamol tablets.jpg",
                                "imageinfo": [
                                    {
                                        "mime": "image/jpeg",
                                        "thumburl": "https://upload.example/p.jpg",
                                        "descriptionurl": "https://commons.example/p",
                                        "extmetadata": {
                                            "Artist": {"value": "<a>Someone</a>"},
                                            "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                        },
                                    }
                                ],
                            }
                        }
                    }
                },
            )
        return httpx.Response(200, content=b"\xff\xd8jpegbytes")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    meta = await images.fetch("paracetamol", "Paracetamol tablets", client)
    assert meta["status"] == "ok" and meta["author"] == "Someone" and meta["license"] == "CC BY-SA 4.0"
    assert images.file_path(meta).read_bytes().startswith(b"\xff\xd8")
    again = await images.fetch("paracetamol", "Paracetamol tablets", client)
    assert again["file"] == meta["file"] and calls["n"] == 2  # served from cache


async def test_image_fetch_failure_is_graceful(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "cache_dir", lambda: tmp_path)
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(429)))
    meta = await images.fetch("ibuprofen", "Ibuprofen tablets", client)
    assert meta["status"] == "error" and images.file_path(meta) is None
