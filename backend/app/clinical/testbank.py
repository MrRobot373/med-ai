"""A reviewable bank of clinical test cases for the prescription safety rules.

Each case in testbank.json states a patient, a prescription, what the rules MUST report, what they must NOT report,
and — in plain words — why. A pharmacist or clinical lead can read the file without any programming, add cases,
and sign off the rules only while every case passes (see clinical/content.py). Run it any time with:

    python -m app.cli clinical-selftest
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.formulary.catalog import Formulary, load
from app.formulary.engine import ItemInput, check
from app.formulary.facts import CurrentMed, Fact, PatientFacts, allergy_groups

PATH = Path(__file__).with_name("testbank.json")
SEVERITY = {"info": 1, "warning": 2, "critical": 3}


def load_cases() -> list[dict]:
    return json.loads(PATH.read_text(encoding="utf-8"))["cases"]


def bank_hash() -> str:
    return hashlib.sha256(PATH.read_bytes()).hexdigest()


def _facts(fm: Formulary, spec: dict) -> PatientFacts:
    f = PatientFacts(patient_id="selftest", name="Test patient", age=spec.get("age", 45), sex=spec.get("sex", "male"))
    if "weight_kg" in spec:
        f.weight = Fact(spec["weight_kg"], "test case")
    if "egfr" in spec:
        f.egfr = Fact(spec["egfr"], "test case")
    if spec.get("hepatic"):
        f.hepatic = Fact(True, "test case")
    f.pregnant = bool(spec.get("pregnant"))
    f.conditions = list(spec.get("conditions", []))
    f.allergies = [
        {"substance": s, "reaction": "test", "severity": "severe", "groups": allergy_groups(fm, s)}
        for s in spec.get("allergies", [])
    ]
    for name in spec.get("current_meds", []):
        r = fm.resolve(name)
        tags = sorted({t for g in r.generics for t in g.tags})
        f.current_meds.append(CurrentMed("test", name, r.generic_ids, tags, None, None))
    return f


def run_case(fm: Formulary, case: dict) -> dict:
    items = [
        ItemInput(
            drug=i["drug"], dose=i.get("dose"), frequency=i.get("frequency"), duration_days=i.get("duration_days")
        )
        for i in case["items"]
    ]
    result = check(fm, _facts(fm, case["facts"]), items)
    got = [{(f["code"], f["severity"]) for f in it["findings"]} for it in result["items"]]
    problems: list[str] = []
    for e in case.get("expect", []):
        have = {s for c, s in got[e["item"]] if c == e["code"]}
        if not have:
            problems.append(f"Expected '{e['code']}' on {case['items'][e['item']]['drug']} but it was not reported.")
        elif e.get("severity") and max(SEVERITY[s] for s in have) < SEVERITY[e["severity"]]:
            problems.append(
                f"'{e['code']}' on {case['items'][e['item']]['drug']} was only '{max(have, key=SEVERITY.get)}'; expected at least '{e['severity']}'."
            )
    for fb in case.get("forbid", []):
        if any(c == fb["code"] for c, _ in got[fb["item"]]):
            problems.append(f"'{fb['code']}' must NOT be reported on {case['items'][fb['item']]['drug']}, but it was.")
    if case.get("clean"):
        extra = [(i, c, s) for i, g in enumerate(got) for c, s in g if s in ("warning", "critical")]
        if extra:
            problems.append(
                "A routine prescription raised alerts: "
                + ", ".join(f"{case['items'][i]['drug']} → {c} ({s})" for i, c, s in extra)
            )
    return {
        "id": case["id"],
        "title": case["title"],
        "why": case.get("why", ""),
        "ok": not problems,
        "problems": problems,
        "reported": [sorted(g) for g in got],
    }


def run_all(region: str = "IN") -> dict:
    fm = load(region)
    cases = [run_case(fm, c) for c in load_cases()]
    passed = sum(1 for c in cases if c["ok"])
    return {
        "region": region,
        "total": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "ok": passed == len(cases),
        "bank_hash": bank_hash(),
        "cases": cases,
    }
