"""Medication-list extraction — spec §36 (feeds reconciliation). Pure unit tests
against `app/ingestion/medications.py` directly. End-to-end reconciliation against a
patient's actual current medication list is covered by `test_reconciliation.py`.
"""

from __future__ import annotations

from app.ingestion.medications import extract_medications


def _pages(text: str, page: int = 1) -> list[dict]:
    return [{"page": page, "text": text, "method": "text"}]


def test_free_text_medication_lines_under_a_section_heading():
    text = (
        "Patient Name: Robert Klein\n"
        "MRN: DEMO-1002\n\n"
        "Current Medications:\n"
        "Latanoprost 0.005% eye drops, one drop each eye nightly\n"
        "Timolol 0.5% eye drops, one drop each eye twice daily\n"
        "Aspirin 81mg oral once daily\n\n"
        "Assessment: IOP well controlled."
    )
    meds = extract_medications(_pages(text))
    by_name = {m.medication_name: m for m in meds}

    assert set(by_name) == {"Latanoprost", "Timolol", "Aspirin"}
    assert by_name["Latanoprost"].dose == "0.005%"  # regression: trailing `\b` fails after `%`
    assert by_name["Latanoprost"].route == "eye drops"
    assert by_name["Latanoprost"].frequency == "nightly"
    assert by_name["Timolol"].dose == "0.5%"
    assert by_name["Aspirin"].dose == "81mg"
    assert by_name["Aspirin"].frequency == "once daily"
    for med in meds:
        assert med.source_page == 1
        assert med.source_excerpt


def test_tabular_medication_section():
    text = "Discharge Medications:\nMedication | Dose | Frequency\nMetformin | 500mg | twice daily\nLisinopril | 10mg | once daily"
    meds = extract_medications(_pages(text))
    by_name = {m.medication_name: m for m in meds}

    assert set(by_name) == {"Metformin", "Lisinopril"}
    assert by_name["Metformin"].dose == "500mg"
    assert by_name["Metformin"].frequency == "twice daily"


def test_no_medication_section_yields_nothing():
    text = "Patient Name: Robert Klein\nChief Complaint: Routine follow-up\nAssessment: stable."
    assert extract_medications(_pages(text)) == []


def test_a_line_without_a_recognizable_dose_is_not_treated_as_a_medication():
    text = "Current Medications:\nSee attached pharmacy printout for full list."
    assert extract_medications(_pages(text)) == []
