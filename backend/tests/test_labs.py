"""Lab/observation extraction — spec §33. Pure unit tests against `app/ingestion/labs.py`
directly (no DB/HTTP), since extraction is a plain function of already-extracted page
text. End-to-end persistence (extraction -> Observation rows -> API) is covered by
`test_observations.py`.
"""

from __future__ import annotations

from app.ingestion.labs import extract_observations


def _pages(text: str, page: int = 1) -> list[dict]:
    return [{"page": page, "text": text, "method": "text"}]


def test_long_format_table_extracts_values_units_and_reference_ranges():
    # The exact shape our own XLSX/PDF table extractors produce, including the
    # 2-column identity preamble ("Patient Name | Elena Novak") appearing on the same
    # contiguous pipe-run as the real data table with no blank-line separator — the
    # regression this module's header-detection has to handle correctly.
    text = (
        "Patient Name | Elena Novak |  | \n"
        "MRN | DEMO-1003 |  | \n"
        "Test | Result | Unit | Reference Range\n"
        "HbA1c | 8.1 | % | 4.0-5.6\n"
        "Fasting Glucose | 168 | mg/dL | 70-99\n"
        "LDL Cholesterol | 132 | mg/dL | <100\n"
        "Creatinine | 0.9 | mg/dL | 0.6-1.3"
    )
    observations = extract_observations(_pages(text))
    by_name = {o.normalized_name: o for o in observations}

    assert set(by_name) == {"hba1c", "glucose", "ldl_cholesterol", "creatinine"}
    assert by_name["hba1c"].value_numeric == 8.1
    assert by_name["hba1c"].unit == "%"
    assert by_name["hba1c"].reference_low == 4.0
    assert by_name["hba1c"].reference_high == 5.6
    assert by_name["hba1c"].abnormal_flag is True  # 8.1 > 5.6

    assert by_name["creatinine"].abnormal_flag is False  # 0.9 within 0.6-1.3

    # One-sided range ("<100") -> reference_low stays None, not fabricated as 0.
    assert by_name["ldl_cholesterol"].reference_low is None
    assert by_name["ldl_cholesterol"].reference_high == 100.0
    assert by_name["ldl_cholesterol"].abnormal_flag is True  # 132 > 100

    for observation in observations:
        assert observation.extraction_method == "table"
        assert observation.source_page == 1


def test_wide_format_table_extracts_one_series_per_qualifier():
    text = "[Table]\nEye | IOP (mmHg) | Target\nOD | 16 | <18\nOS | 22 | <18"
    observations = extract_observations(_pages(text))
    by_name = {o.normalized_name: o for o in observations}

    assert set(by_name) == {"iop:od", "iop:os"}
    assert by_name["iop:od"].observation_name == "IOP (OD)"
    assert by_name["iop:od"].value_numeric == 16.0
    assert by_name["iop:od"].unit == "mmHg"
    assert by_name["iop:od"].abnormal_flag is False  # 16 <= 18

    assert by_name["iop:os"].value_numeric == 22.0
    assert by_name["iop:os"].abnormal_flag is True  # 22 > 18


def test_inline_extraction_uses_qualitative_annotation_when_no_range_present():
    text = "Central subfield thickness: 340 microns (elevated)"
    observations = extract_observations(_pages(text))

    assert len(observations) == 1
    observation = observations[0]
    assert observation.normalized_name == "central_subfield_thickness"
    assert observation.value_numeric == 340.0
    assert observation.unit == "microns"
    assert observation.reference_low is None
    assert observation.reference_high is None
    # No numeric range was ever stated — abnormal_flag comes ONLY from the document's
    # own "(elevated)" annotation, never a fabricated threshold.
    assert observation.abnormal_flag is True
    assert observation.extraction_method == "inline"


def test_no_reference_range_leaves_abnormal_flag_unknown_not_false():
    text = "Sodium: 140 mmol/L"
    observations = extract_observations(_pages(text))

    assert len(observations) == 1
    assert observations[0].value_numeric == 140.0
    assert observations[0].abnormal_flag is None  # unknown, never assumed "normal"


def test_table_found_test_is_not_also_extracted_inline_on_same_page():
    # "Intraocular pressure at this visit:" mentions IOP by name right before the
    # table that actually has the values — should not create a spurious extra
    # bare "iop" observation alongside the two per-eye table entries.
    text = (
        "Intraocular pressure at this visit:\n\n"
        "[Table]\nEye | IOP (mmHg) | Target\nOD | 16 | <18\nOS | 17 | <18"
    )
    observations = extract_observations(_pages(text))
    assert {o.normalized_name for o in observations} == {"iop:od", "iop:os"}


def test_identity_only_block_produces_no_observations():
    text = "Patient Name | Elena Novak |  | \nMRN | DEMO-1003 |  | \nCollection Date | 2026-08-10 |  | "
    assert extract_observations(_pages(text)) == []


def test_unrelated_prose_does_not_false_positive():
    text = "Patient Name: Robert Klein\nChief Complaint: Routine glaucoma follow-up\nNo new symptoms reported."
    assert extract_observations(_pages(text)) == []
