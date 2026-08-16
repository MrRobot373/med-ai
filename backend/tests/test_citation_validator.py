from __future__ import annotations

from dataclasses import dataclass

from app.chat.citation_validator import extract_cited_labels, validate_citations


@dataclass
class _FakePassage:
    pass


@dataclass
class _FakeLabeledEvidence:
    label: str


def test_extract_cited_labels_finds_all_marker_styles():
    text = "The IOP is elevated [P1]. This matches guideline recommendations [L1][L2]."
    assert extract_cited_labels(text) == ["P1", "L1", "L2"]


def test_valid_citations_are_kept_and_reported():
    evidence = [_FakeLabeledEvidence(label="P1"), _FakeLabeledEvidence(label="L1")]
    text = "Latanoprost is prescribed [P1]. This is standard first-line therapy [L1]."
    cleaned, used = validate_citations(text, evidence)
    assert cleaned == text  # nothing removed
    assert used == ["P1", "L1"]


def test_invalid_citation_id_is_stripped_not_trusted():
    # [P9] was never given to the model — spec §52 "do not simply trust the LLM's
    # citation numbering" / "remove invalid citation IDs."
    evidence = [_FakeLabeledEvidence(label="P1")]
    text = "The patient takes Latanoprost [P1] and reportedly had surgery in 2020 [P9]."
    cleaned, used = validate_citations(text, evidence)
    assert "[P9]" not in cleaned
    assert "[P1]" in cleaned
    assert used == ["P1"]


def test_duplicate_citations_reported_once_in_first_seen_order():
    evidence = [_FakeLabeledEvidence(label="P1"), _FakeLabeledEvidence(label="L1")]
    text = "Claim one [L1]. Claim two [P1]. Claim three, same source again [L1]."
    _, used = validate_citations(text, evidence)
    assert used == ["L1", "P1"]


def test_no_citations_at_all():
    cleaned, used = validate_citations("A plain answer with no sources.", [])
    assert used == []
    assert cleaned == "A plain answer with no sources."


def test_vision_derived_v_labels_are_recognized():
    evidence = [_FakeLabeledEvidence(label="V1")]
    text = "The optic disc shows mild pallor on the retinal image [V1]."
    cleaned, used = validate_citations(text, evidence)
    assert cleaned == text
    assert used == ["V1"]
