"""Guideline Q&A — spec §63: "use strict evidence-grounded local RAG. If no relevant
guideline exists, state that explicitly." A dedicated single-turn workflow (not routed
through the chat endpoint, per spec §63's own instruction), reusing chat's citation
validation and evidence-quality scoring rather than reimplementing that judgment.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.chat.citation_validator import validate_citations
from app.chat.context_builder import LabeledEvidence, build_evidence_block
from app.chat.evidence_quality import EvidenceQuality, score_evidence_quality
from app.config.settings import Settings
from app.llm.generation import ChatMessage, generate_complete
from app.modules.prompts import GUIDELINE_QA_SYSTEM_PROMPT, build_guideline_qa_user_prompt

NO_GUIDELINE_TEXT = "No relevant guideline was found in the local knowledge base for this question."


@dataclass
class GuidelineQAResult:
    answer_text: str
    citations: list[LabeledEvidence]
    evidence_quality: EvidenceQuality
    no_guideline_found: bool


async def answer_guideline_question(
    question: str, labeled_evidence: list[LabeledEvidence], settings: Settings
) -> GuidelineQAResult:
    if not labeled_evidence:
        return GuidelineQAResult(
            answer_text=NO_GUIDELINE_TEXT, citations=[], evidence_quality=EvidenceQuality.INSUFFICIENT, no_guideline_found=True
        )

    messages = [
        ChatMessage(role="system", content=GUIDELINE_QA_SYSTEM_PROMPT),
        ChatMessage(role="user", content=build_guideline_qa_user_prompt(question, build_evidence_block(labeled_evidence))),
    ]
    raw = await generate_complete(
        messages,
        settings,
        temperature=settings.clinical_module_temperature,
        max_output_tokens=settings.clinical_module_max_output_tokens,
    )

    cleaned_text, used_labels = validate_citations(raw, labeled_evidence)
    quality = score_evidence_quality(labeled_evidence, used_labels)
    used_set = set(used_labels)
    citations = [item for item in labeled_evidence if item.label in used_set]
    return GuidelineQAResult(
        answer_text=cleaned_text, citations=citations, evidence_quality=quality, no_guideline_found=not used_labels
    )
