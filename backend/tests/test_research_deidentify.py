"""External query de-identification — spec §66, MANDATORY: "Implement tests proving
identifiers are stripped." This is the one gate every outbound Research Mode query
passes through; these tests exist specifically because the spec requires them, not
just as general coverage.
"""

from __future__ import annotations

import uuid
from datetime import date

from app.models.patient import Patient, Sex
from app.research.deidentify import deidentify_query


def _make_patient(**overrides) -> Patient:
    defaults = {
        "id": str(uuid.uuid4()),
        "mrn": "DEMO-10044",
        "first_name": "John",
        "last_name": "Smith",
        "preferred_name": None,
        "date_of_birth": date(1958, 3, 12),
        "sex": Sex.MALE,
        "phone": "555-201-3344",
        "email": "john.smith@example.com",
        "synthetic": True,
    }
    defaults.update(overrides)
    return Patient(**defaults)


def test_strips_patients_full_name():
    patient = _make_patient()
    result = deidentify_query("John Smith MRN 10044 creatinine 1.8 CKD, what medication adjustments are needed?", patient)
    assert "John" not in result.sanitized_text
    assert "Smith" not in result.sanitized_text
    assert "creatinine 1.8 CKD" in result.sanitized_text  # clinical content is preserved
    assert result.removed_count > 0
    assert "patient_identity" in result.removed_categories


def test_strips_patients_mrn():
    patient = _make_patient()
    result = deidentify_query("Reviewing DEMO-10044 for renal dosing guidance", patient)
    assert "DEMO-10044" not in result.sanitized_text


def test_strips_patients_phone_and_email():
    patient = _make_patient()
    result = deidentify_query("Contact 555-201-3344 or john.smith@example.com about glaucoma follow-up", patient)
    assert "555-201-3344" not in result.sanitized_text
    assert "john.smith@example.com" not in result.sanitized_text


def test_spec_example_produces_a_clean_generic_query():
    """The exact example from spec §66: DO NOT send 'John Smith MRN 10044 creatinine
    1.8 CKD...' — every direct identifier must be gone."""
    patient = _make_patient()
    result = deidentify_query("John Smith MRN 10044 creatinine 1.8 CKD medication options", patient)
    assert "John" not in result.sanitized_text
    assert "Smith" not in result.sanitized_text
    assert "10044" not in result.sanitized_text
    assert "creatinine" in result.sanitized_text
    assert "CKD" in result.sanitized_text


def test_strips_generic_email_even_without_patient_context():
    result = deidentify_query("Please reply to clinician@hospital.org with current guidance", None)
    assert "clinician@hospital.org" not in result.sanitized_text
    assert "email" in result.removed_categories


def test_strips_generic_phone_even_without_patient_context():
    result = deidentify_query("Call (555) 867-5309 for follow-up on treatment options", None)
    assert "555" not in result.sanitized_text or "867-5309" not in result.sanitized_text
    assert "phone" in result.removed_categories


def test_strips_generic_mrn_pattern_even_without_patient_context():
    result = deidentify_query("MRN: ABC-99182 renal dosing question", None)
    assert "ABC-99182" not in result.sanitized_text
    assert "mrn" in result.removed_categories


def test_strips_street_address():
    result = deidentify_query("Patient lives at 742 Evergreen Terrace, referred for glaucoma workup", None)
    assert "742 Evergreen Terrace" not in result.sanitized_text
    assert "address" in result.removed_categories


def test_never_strips_clinical_terms_that_are_not_the_patients_name():
    """False-positive guard: a condition/drug name that happens to look like a proper
    noun must survive when it isn't the current patient's own identifier."""
    patient = _make_patient(first_name="Robert", last_name="Klein")
    result = deidentify_query("What is the current guideline for Marcus Gunn pupil evaluation?", patient)
    assert "Marcus Gunn pupil" in result.sanitized_text


def test_a_clean_query_with_no_identifiers_passes_through_unchanged():
    result = deidentify_query("current guideline chronic kidney disease medication renal impairment", None)
    assert result.sanitized_text == "current guideline chronic kidney disease medication renal impairment"
    assert result.removed_count == 0
    assert result.removed_categories == []


def test_no_patient_context_means_only_generic_patterns_are_checked():
    result = deidentify_query("Discuss options for Elena Novak's diabetic retinopathy", None)
    # No patient object given — this app never attempts general name redaction (see
    # module docstring), so an arbitrary name string is NOT stripped without context.
    assert "Elena Novak" in result.sanitized_text


def test_preferred_name_is_also_stripped_when_set():
    patient = _make_patient(preferred_name="Johnny")
    result = deidentify_query("Johnny is asking about his glaucoma treatment plan", patient)
    assert "Johnny" not in result.sanitized_text
