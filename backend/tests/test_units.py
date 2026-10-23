import pytest

from app.ai.llm import _ThinkFilter, parse_json_response
from app.clinical.citations import coverage, validate
from app.ingestion.chunking import chunk_pages
from app.ingestion.labs import extract


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


def test_think_filter_strips_reasoning_across_chunks():
    f = _ThinkFilter()
    out = "".join(f.feed(p) for p in ["Hel", "lo <thi", "nk>secret plan</th", "ink> world"]) + f.flush()
    assert out == "Hello  world"


def test_parse_json_response_tolerates_fences():
    assert parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_response('Sure! {"a": 2} hope that helps') == {"a": 2}
    with pytest.raises(ValueError):
        parse_json_response("no json")


def test_pdf_column_table_keeps_decimal_values():
    """Lab PDFs lay results out in columns; decimals must survive text extraction."""
    import pymupdf

    from app.ingestion import labs, parsers

    doc = pymupdf.open()
    page = doc.new_page()
    y = 100
    for row in (
        ("Haemoglobin", "12.9", "g/dL", "13.0 - 17.0", "L"),
        ("Serum Creatinine", "1.36", "mg/dL", "0.70 - 1.30", "H"),
    ):
        for x, cell in zip((50, 220, 300, 380, 480), row, strict=True):
            page.insert_text((x, y), cell, fontsize=10)
        y += 16
    pages = parsers.parse(doc.tobytes(), "application/pdf").pages
    got = {o.code: (o.value_num, o.unit, o.ref_low, o.ref_high, o.flag) for o in labs.extract(pages)}
    assert got["hemoglobin"] == (12.9, "g/dL", 13.0, 17.0, "low")
    assert got["creatinine"] == (1.36, "mg/dL", 0.7, 1.3, "high")


def test_identity_flags_namesake_in_table_layout():
    from app.ingestion import identity
    from app.models import Patient

    p = Patient(mrn="LCM-10232", first_name="Harish Chandra", last_name="Gupta")
    other = "LABORATORY REPORT\nPatient Name | : Mr. Hemant Gupta | Lab No. | : AP/2610/44871\nPatient ID | : AP-778812"
    assert identity.check(p, other).status == "mismatch"
    own = "Patient Name | : Mr. Harish Chandra Gupta | Lab No. | : SV/1\nPatient ID | : SV-99812"
    assert identity.check(p, own).status == "match"
