"""Chat orchestration — spec §43 Stages 2/4-6 + §48. Composes query classification,
structured patient context, RAG retrieval (via `app.rag.pipeline`), and context
construction into a ready-to-generate prompt. No DB writes and no HTTP/SSE framing
here — `app/services/chat.py` owns persistence, `app/api/chat.py` owns the streaming
response; this module is the part that's actually worth unit testing in isolation.

Split into `prepare_turn()` (classification + retrieval + context assembly — no LLM
call) and `finalize_turn()` (citation + grounding validation — runs only after
streaming completes) because spec §119 frames it that way: "preserve citations/
provenance when final answer completes" implies citation/grounding validation is a
post-stream step, not something that can happen before the clinician has already seen
the streamed tokens.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session as DbSession

from app.chat.citation_validator import validate_citations
from app.chat.context_builder import (
    LabeledEvidence,
    build_evidence_block,
    build_user_turn,
    label_evidence,
)
from app.chat.evidence_quality import EvidenceQuality, score_evidence_quality
from app.chat.generation import ChatMessage
from app.chat.grounding_validator import GroundingResult, validate_grounding
from app.chat.patient_context import build_encounter_facts, build_patient_facts, build_report_facts
from app.chat.prompts import CLINICAL_CHAT_SYSTEM_PROMPT
from app.chat.query_classifier import classify_query
from app.config.settings import Settings
from app.models.chunk import ChunkCollection
from app.models.conversation import Conversation, ConversationScope
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.report import Report
from app.rag.pipeline import retrieve

ABSTENTION_TEXT = (
    "Insufficient evidence is available in the selected patient record and knowledge "
    "sources to answer this reliably."
)

_PATIENT_SCOPED = (ConversationScope.CURRENT_PATIENT, ConversationScope.CURRENT_ENCOUNTER, ConversationScope.SELECTED_REPORT)


@dataclass
class PreparedTurn:
    task_classification: str
    labeled_evidence: list[LabeledEvidence]
    messages: list[ChatMessage]  # ready to hand to generate_stream()/generate_complete()
    abstain: bool


def prepare_turn(
    db: DbSession, settings: Settings, conversation: Conversation, user_text: str, history: list[ChatMessage]
) -> PreparedTurn:
    classification = classify_query(user_text)
    if not classification.needs_retrieval:
        messages = [ChatMessage("system", CLINICAL_CHAT_SYSTEM_PROMPT), *history, ChatMessage("user", user_text)]
        return PreparedTurn(task_classification=classification.task, labeled_evidence=[], messages=messages, abstain=False)

    patient_facts = encounter_facts = report_facts = None

    if conversation.scope in _PATIENT_SCOPED and conversation.patient_id:
        patient = db.get(Patient, conversation.patient_id)
        if patient:
            patient_facts = build_patient_facts(db, patient)
    if conversation.scope == ConversationScope.CURRENT_ENCOUNTER and conversation.encounter_id:
        encounter = db.get(Encounter, conversation.encounter_id)
        if encounter:
            encounter_facts = build_encounter_facts(encounter)
    if conversation.scope == ConversationScope.SELECTED_REPORT and conversation.selected_report_id:
        report = db.get(Report, conversation.selected_report_id)
        if report:
            report_facts = build_report_facts(report)

    patient_passages = []
    if conversation.scope in _PATIENT_SCOPED and conversation.patient_id:
        patient_passages = retrieve(
            db, user_text, settings, collection=ChunkCollection.PATIENT_DOCUMENTS, patient_id=conversation.patient_id
        )

    knowledge_passages = []
    if conversation.scope != ConversationScope.SELECTED_REPORT:
        # Even patient-scoped questions often want guideline grounding alongside
        # patient evidence (spec §42's own suggested question: "Find guideline
        # evidence relevant to this case") — SELECTED_REPORT is the one scope that's
        # deliberately narrow, since the point of picking a specific report is to
        # discuss *that* document, not the whole knowledge base.
        knowledge_passages = retrieve(db, user_text, settings, collection=ChunkCollection.MEDICAL_KNOWLEDGE)

    labeled = label_evidence(patient_passages, knowledge_passages)

    # Abstain only when there's truly nothing to answer from — not just when
    # free-text retrieval came up empty. Structured facts (e.g. "what medications is
    # this patient on?") can fully answer many questions with no retrieval hit at all.
    if not labeled and not patient_facts and not encounter_facts and not report_facts:
        return PreparedTurn(task_classification=classification.task, labeled_evidence=[], messages=[], abstain=True)

    evidence_block = build_evidence_block(labeled)
    user_turn = build_user_turn(user_text, evidence_block, patient_facts, encounter_facts, report_facts)
    messages = [ChatMessage("system", CLINICAL_CHAT_SYSTEM_PROMPT), *history, ChatMessage("user", user_turn)]

    return PreparedTurn(task_classification=classification.task, labeled_evidence=labeled, messages=messages, abstain=False)


@dataclass
class TurnResult:
    answer_text: str
    citations: list[LabeledEvidence]
    evidence_quality: EvidenceQuality
    grounding: GroundingResult | None


async def finalize_turn(raw_answer_text: str, labeled_evidence: list[LabeledEvidence], settings: Settings) -> TurnResult:
    cleaned_text, used_labels = validate_citations(raw_answer_text, labeled_evidence)
    quality = score_evidence_quality(labeled_evidence, used_labels)

    grounding = None
    if used_labels:
        grounding = await validate_grounding(cleaned_text, labeled_evidence, settings)

    used_set = set(used_labels)
    citations = [item for item in labeled_evidence if item.label in used_set]
    return TurnResult(answer_text=cleaned_text, citations=citations, evidence_quality=quality, grounding=grounding)
