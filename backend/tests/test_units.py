import pytest

from app.ai.llm import _ThinkFilter, parse_json_response
from app.clinical.citations import coverage, validate
from app.ingestion.chunking import chunk_pages
from app.ingestion.labs import extract
from app.models import Patient
from app.research.deidentify import deidentify


def test_lab_parser_table_inline_and_no_invented_ranges():
    text = "\n".join(
        [
            "HbA1c | 8.4 | % | 4.0-5.6 | H",
            "Creatinine (mg/dL) | 1.62 | 0.6-1.2",
            "eGFR: 41 mL/min/1.73m2 (>60)",
            "TSH 2.1 mIU/L",
            "The patient said glucose was fine in the past.",
        ]
    )
    obs = {o.code: o for o in extract([{"page": 3, "text": text}])}
    assert obs["hba1c"].flag == "high" and obs["hba1c"].unit == "%"
    assert obs["creatinine"].unit == "mg/dL" and obs["creatinine"].flag == "high"
    assert obs["egfr"].flag == "low" and obs["egfr"].ref_low == 60
    assert obs["tsh"].flag is None  # no range in document → no flag
    assert "glucose" not in obs  # prose mention is not a measurement
    assert obs["hba1c"].page == 3


def test_chunker_respects_size_and_sections():
    text = "## Section A\n" + ("word " * 900) + "\n\n## Section B\nShort tail paragraph about something."
    chunks = chunk_pages([{"page": 1, "text": text}], target_tokens=300, overlap_tokens=40)
    assert len(chunks) >= 3
    assert chunks[0].section == "Section A"
    assert chunks[-1].section == "Section B"
    assert all(c.tokens <= 420 for c in chunks)


def test_citation_validation():
    cleaned, used, invalid = validate("Value high [P1]. Also [P1, K9]. And [R].", {"P1", "R"})
    assert cleaned == "Value high [P1]. Also [P1]. And [R]."
    assert used == ["P1", "R"] and invalid == ["K9"]
    assert coverage("This sentence has a citation here [P1]. This one has none at all sadly.") == 0.5


def test_deidentify_removes_patient_identifiers_but_keeps_eponyms():
    p = Patient(first_name="James", last_name="Carter", mrn="DEMO-1001", phone="555-0101")
    out = deidentify("James Carter (MRN DEMO-1001, 555-0101, born 1963-03-14) has a Marcus Gunn pupil", p)
    assert "Carter" not in out.text and "DEMO-1001" not in out.text and "555" not in out.text and "1963" not in out.text
    assert "Marcus Gunn pupil" in out.text
    assert out.removed >= 3


def test_think_filter_strips_reasoning_across_chunks():
    f = _ThinkFilter()
    out = "".join(f.feed(p) for p in ["Hel", "lo <thi", "nk>secret plan</th", "ink> world"]) + f.flush()
    assert out == "Hello  world"


def test_parse_json_response_tolerates_fences():
    assert parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_response('Sure! {"a": 2} hope that helps') == {"a": 2}
    with pytest.raises(ValueError):
        parse_json_response("no json")
