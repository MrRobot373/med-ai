"""`ResearchSynthesis`'s tolerant list-field coercion — found live (Phase 11): with
the larger combined-evidence prompt, qwen3.5:9b intermittently returned a plain string
for a `list[str]` field, which should still validate rather than fail structured
generation outright."""

from __future__ import annotations

from app.research.paper_assistant import ResearchSynthesis


def test_accepts_a_normal_list_unchanged():
    result = ResearchSynthesis.model_validate(
        {"limitations": ["small sample size", "short follow-up"], "conflicting_evidence": [], "exclusion_criteria": []}
    )
    assert result.limitations == ["small sample size", "short follow-up"]


def test_coerces_a_bare_string_into_a_single_item_list():
    result = ResearchSynthesis.model_validate(
        {
            "limitations": "The evidence base is limited by heterogeneous study designs.",
            "conflicting_evidence": "Some trials favor SLT; others show no significant difference.",
            "exclusion_criteria": "Patients with prior incisional surgery were excluded.",
        }
    )
    assert result.limitations == ["The evidence base is limited by heterogeneous study designs."]
    assert result.conflicting_evidence == ["Some trials favor SLT; others show no significant difference."]
    assert result.exclusion_criteria == ["Patients with prior incisional surgery were excluded."]


def test_coerces_a_blank_string_into_an_empty_list():
    result = ResearchSynthesis.model_validate({"limitations": "", "conflicting_evidence": "   ", "exclusion_criteria": []})
    assert result.limitations == []
    assert result.conflicting_evidence == []


def test_defaults_are_empty_when_fields_are_omitted():
    result = ResearchSynthesis.model_validate({})
    assert result.limitations == []
    assert result.conflicting_evidence == []
    assert result.exclusion_criteria == []
    assert result.evidence_summary == ""
