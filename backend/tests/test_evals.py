"""The evaluation harness itself, and a regression guard on lab-extraction accuracy."""

import asyncio
import json

import pytest

from app.core.config import PROJECT_ROOT
from app.evals import runner
from app.ingestion import labs

HAVE_FILES = (PROJECT_ROOT / "patient-files").exists()


@pytest.mark.skipif(not HAVE_FILES, reason="sample patient files are not present")
def test_lab_extraction_meets_its_targets_on_real_reports():
    r = runner.extraction()
    assert r["status"] == "ok" and r["reports"] >= 20
    assert r["recall"] >= 0.95 and r["precision"] >= 0.9, r["misses"]


def test_extraction_suite_says_so_when_there_is_nothing_to_measure(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "PATIENT_FILES", tmp_path)
    r = runner.extraction()
    assert r["status"] == "skipped" and "patient files" in r["reason"]


def test_matching_uses_the_parsers_own_codes_not_display_names():
    assert runner._code_of("Total Leucocyte Count") == "wbc"
    assert runner._code_of("Random blood glucose") == "glucose"
    assert runner._code_of("A test nobody has heard of") is None


@pytest.mark.parametrize(
    "line,code,value",
    [
        ("Random blood glucose | 246 | H | mg/dL | 70 - 140", "glucose", 246.0),
        ("Absolute eosinophil count | 640 | H | cells/µL | 40 - 440", "aec", 640.0),
        ("Total IgE | 486 | H | IU/mL | < 100", "ige", 486.0),
        ("D-dimer | 0.42 | µg/mL FEU | < 0.50", "d_dimer", 0.42),
    ],
)
def test_newly_recognised_analytes(line, code, value):
    got = labs.extract([{"page": 1, "text": line}])
    assert [(o.code, o.value_num) for o in got] == [(code, value)]


def test_family_history_is_not_mistaken_for_a_result():
    assert labs.extract([{"page": 1, "text": "Family history of diabetes | 2 | relatives"}]) == []


def test_a_suite_that_cannot_run_reports_why_instead_of_failing_the_rest(monkeypatch):
    monkeypatch.setattr(runner, "extraction", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    report = asyncio.run(runner.run(["extraction"]))
    assert (
        report["suites"][0]["status"] == "error" and "boom" in report["suites"][0]["reason"] and report["ok"] is False
    )


def test_report_names_the_models_and_is_saved(tmp_path):
    report = asyncio.run(runner.run(["retrieval"]))  # an empty reference library: skipped, not an error
    assert report["suites"][0]["status"] == "skipped"
    assert set(report["models"]) == {"language", "embedding", "reranker", "clinical"}
    assert runner.latest()["at"] == report["at"]


def test_question_sets_are_well_formed():
    qa = json.loads((runner.DATA / "qa.json").read_text())
    assert len(qa["retrieval"]) >= 8 and len(qa["out_of_scope"]) >= 4
    assert all(c["q"].endswith("?") and c["expect"] for c in qa["retrieval"])
    for c in qa["retrieval"]:  # every expected source exists in the shipped reference library
        assert any(c["expect"] in p.name for p in (PROJECT_ROOT / "knowledge-packs").rglob("*") if p.is_file()), c


def test_the_ground_truth_covers_every_generated_lab_report():
    truth = json.loads((runner.DATA / "lab_truth.json").read_text())
    assert len(truth) >= 20 and sum(len(v) for v in truth.values()) >= 120
