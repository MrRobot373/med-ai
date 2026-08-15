"""Context construction — spec §48: clearly separated sections, retrieved documents
are DATA, not instructions. The actual prompt-injection boundary is stated explicitly
in `prompts.CLINICAL_CHAT_SYSTEM_PROMPT`; this module's job is just to keep every
section visually and structurally distinct so that boundary is unambiguous.

Citation labels (spec §51: "[P1] Patient Report", "[L1] Local Guideline") are assigned
here, once, from the same ordered list the model is shown — so a citation the model
emits can always be matched back to a real passage later (spec §52 citation
validation), never re-derived from the model's own (untrusted) numbering.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.rag.deduplicator import RetrievedPassage


@dataclass
class LabeledEvidence:
    label: str  # "P1", "L1", ...
    passage: RetrievedPassage


def label_evidence(
    patient_passages: list[RetrievedPassage], knowledge_passages: list[RetrievedPassage]
) -> list[LabeledEvidence]:
    labeled = [LabeledEvidence(label=f"P{i}", passage=p) for i, p in enumerate(patient_passages, start=1)]
    labeled.extend(LabeledEvidence(label=f"L{i}", passage=p) for i, p in enumerate(knowledge_passages, start=1))
    return labeled


def build_evidence_block(labeled: list[LabeledEvidence]) -> str:
    if not labeled:
        return "(No relevant evidence was retrieved for this question.)"
    blocks = []
    for item in labeled:
        passage = item.passage
        header = f"[{item.label}] {passage.source_title}"
        if passage.page:
            header += f", page {passage.page}"
        if passage.section:
            header += f" — {passage.section}"
        blocks.append(f'{header}\n"{passage.text.strip()}"')
    return "\n\n".join(blocks)


def build_user_turn(
    user_question: str,
    evidence_block: str,
    patient_facts: str | None = None,
    encounter_facts: str | None = None,
    report_facts: str | None = None,
) -> str:
    sections = []
    if patient_facts:
        sections.append(f"CURRENT PATIENT FACTS\n{patient_facts}")
    if encounter_facts:
        sections.append(f"CURRENT ENCOUNTER FACTS\n{encounter_facts}")
    if report_facts:
        sections.append(f"SELECTED REPORT FACTS\n{report_facts}")
    sections.append(f"RETRIEVED LOCAL CLINICAL EVIDENCE\n{evidence_block}")
    sections.append(f"USER QUESTION\n{user_question}")
    return "\n\n---\n\n".join(sections)
