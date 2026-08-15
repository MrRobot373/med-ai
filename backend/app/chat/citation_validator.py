"""Citation validation — spec §52: "Do not simply trust the LLM's citation
numbering." Parses `[P1]`/`[L1]`-style markers the model emitted, keeps only the ones
that reference a real, actually-shown-to-the-model piece of evidence, and strips the
rest from the visible answer text.
"""

from __future__ import annotations

import re

from app.chat.context_builder import LabeledEvidence

_CITATION_PATTERN = re.compile(r"\[([PLW]\d+)\]")


def extract_cited_labels(answer_text: str) -> list[str]:
    return _CITATION_PATTERN.findall(answer_text)


def validate_citations(answer_text: str, labeled_evidence: list[LabeledEvidence]) -> tuple[str, list[str]]:
    """Returns `(cleaned_answer_text, valid_labels_actually_used)`. An invalid label
    (referencing evidence that was never given to the model — spec: "never invent a
    citation") is removed from the visible text outright rather than left dangling."""
    valid_labels = {item.label for item in labeled_evidence}
    cited = extract_cited_labels(answer_text)
    invalid = {label for label in cited if label not in valid_labels}

    cleaned_text = answer_text
    for label in invalid:
        cleaned_text = cleaned_text.replace(f"[{label}]", "")

    used_labels = [label for label in cited if label in valid_labels]
    return cleaned_text, list(dict.fromkeys(used_labels))  # de-duplicated, first-seen order
