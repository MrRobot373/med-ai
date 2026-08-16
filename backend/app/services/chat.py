"""Chat conversation service — DB persistence + turn orchestration glue.
`app/api/chat.py` calls into this; `app/chat/orchestrator.py` has the actual
retrieval/context-assembly logic and knows nothing about SQLAlchemy or HTTP.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.chat.orchestrator import ABSTENTION_TEXT, finalize_turn, prepare_turn
from app.config.settings import Settings
from app.llm.generation import ChatMessage, GenerationError, generate_stream
from app.logging import get_logger
from app.models.citation import Citation, CitationSourceType
from app.models.conversation import Conversation, ConversationScope
from app.models.message import Message, MessageRole
from app.rag.dense_retriever import RetrievalError

logger = get_logger(__name__)

# Report comparison (Phase 10) and web research (Phase 11) don't exist yet — reject
# these scopes explicitly at creation time rather than silently mishandling them.
_UNIMPLEMENTED_SCOPES = {ConversationScope.SELECTED_REPORTS_COMPARISON, ConversationScope.RESEARCH_MODE}

_SOURCE_TYPE_BY_COLLECTION = {
    "patient_documents": CitationSourceType.PATIENT_REPORT,
    "patient_vision": CitationSourceType.PATIENT_VISION,
}


class UnsupportedScopeError(Exception):
    pass


def create_conversation(
    db: DbSession,
    user_id: str,
    scope: ConversationScope,
    patient_id: str | None = None,
    encounter_id: str | None = None,
    selected_report_id: str | None = None,
) -> Conversation:
    if scope in _UNIMPLEMENTED_SCOPES:
        raise UnsupportedScopeError(f"Scope '{scope.value}' is not implemented yet")
    conversation = Conversation(
        user_id=user_id,
        scope=scope,
        patient_id=patient_id,
        encounter_id=encounter_id,
        selected_report_id=selected_report_id,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def list_conversations(db: DbSession, user_id: str, patient_id: str | None = None) -> list[Conversation]:
    stmt = select(Conversation).where(Conversation.user_id == user_id)
    stmt = stmt.where(Conversation.patient_id == patient_id) if patient_id else stmt
    stmt = stmt.order_by(Conversation.updated_at.desc())
    return list(db.scalars(stmt))


def get_conversation(db: DbSession, conversation_id: str) -> Conversation | None:
    return db.get(Conversation, conversation_id)


def list_messages(db: DbSession, conversation_id: str) -> list[Message]:
    stmt = select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    return list(db.scalars(stmt))


def list_citations(db: DbSession, message_id: str) -> list[Citation]:
    stmt = select(Citation).where(Citation.message_id == message_id).order_by(Citation.label)
    return list(db.scalars(stmt))


def _recent_history(db: DbSession, conversation_id: str, max_turns: int) -> list[ChatMessage]:
    if max_turns <= 0:
        return []
    messages = list_messages(db, conversation_id)
    recent = messages[-(max_turns * 2) :]
    return [ChatMessage(role=m.role.value, content=m.content) for m in recent if m.role != MessageRole.SYSTEM]


def _derive_title(text: str) -> str:
    stripped = " ".join(text.strip().split())
    return stripped[:80] + ("…" if len(stripped) > 80 else "")


def _citation_payload(citation: Citation) -> dict[str, Any]:
    return {
        "label": citation.label,
        "source_type": citation.source_type.value,
        "source_title": citation.source_title,
        "page": citation.page,
        "section": citation.section,
        "source_excerpt": citation.source_excerpt,
        "relevance_score": citation.relevance_score,
    }


async def run_turn(
    db: DbSession, settings: Settings, conversation: Conversation, user_text: str
) -> AsyncIterator[dict[str, Any]]:
    """Yields plain-dict, SSE-ready events — `{"type": "token", ...}`,
    `{"type": "final", ...}`, `{"type": "error", ...}`. HTTP/SSE framing is the API
    layer's job, not this function's."""
    history = _recent_history(db, conversation.id, settings.chat_history_turns)

    db.add(Message(conversation_id=conversation.id, role=MessageRole.USER, content=user_text))
    if conversation.title is None:
        conversation.title = _derive_title(user_text)
    conversation.updated_at = datetime.now(UTC)
    db.commit()

    try:
        prepared = prepare_turn(db, settings, conversation, user_text, history)
    except RetrievalError as exc:
        # Same graceful-degradation shape as a GenerationError below (spec §99: Qdrant
        # unavailable must fail like this, not crash the SSE stream mid-response) — an
        # honest "couldn't retrieve" error, never silently reinterpreted as "no
        # evidence exists" (which would look like a normal abstention).
        db.add(
            Message(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content="",
                generation_error=str(exc),
                model=settings.ollama_model,
            )
        )
        db.commit()
        yield {"type": "error", "message": "Retrieval is temporarily unavailable. Please try again shortly."}
        return

    if prepared.abstain:
        assistant_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=ABSTENTION_TEXT,
            model=settings.ollama_model,
            structured_payload=json.dumps(
                {
                    "task_classification": prepared.task_classification,
                    "evidence_quality": "insufficient",
                    "provenance": prepared.provenance,
                }
            ),
        )
        db.add(assistant_message)
        db.commit()
        yield {"type": "token", "content": ABSTENTION_TEXT}
        yield {
            "type": "final",
            "message_id": assistant_message.id,
            "citations": [],
            "evidence_quality": "insufficient",
            "grounding": None,
        }
        return

    accumulated = ""
    try:
        async for delta in generate_stream(prepared.messages, settings):
            accumulated += delta
            yield {"type": "token", "content": delta}
    except GenerationError as exc:
        db.add(
            Message(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content="",
                generation_error=str(exc),
                model=settings.ollama_model,
            )
        )
        db.commit()
        yield {"type": "error", "message": str(exc)}
        return

    result = await finalize_turn(accumulated, prepared.labeled_evidence, settings)

    assistant_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=result.answer_text,
        model=settings.ollama_model,
        generation_settings=json.dumps({"temperature": settings.chat_temperature, "profile": settings.rag_profile.value}),
        structured_payload=json.dumps(
            {
                "task_classification": prepared.task_classification,
                "evidence_quality": result.evidence_quality.value,
                "grounding": [c.model_dump() for c in result.grounding.claims] if result.grounding else None,
                "provenance": prepared.provenance,
            }
        ),
    )
    db.add(assistant_message)
    db.flush()  # populate assistant_message.id before Citation rows reference it

    citation_rows: list[Citation] = []
    for item in result.citations:
        passage = item.passage
        source_type = _SOURCE_TYPE_BY_COLLECTION.get(passage.collection, CitationSourceType.KNOWLEDGE_DOCUMENT)
        # Both patient_documents and patient_vision chunks carry a report_id
        # (patient_vision's is the image report the analysis was run against) — only
        # medical_knowledge chunks have no report to link back to.
        has_report = passage.collection in _SOURCE_TYPE_BY_COLLECTION
        citation = Citation(
            message_id=assistant_message.id,
            label=item.label,
            source_type=source_type,
            chunk_id=passage.chunk_ids[0] if passage.chunk_ids else None,
            report_id=passage.source_id if has_report else None,
            source_title=passage.source_title,
            page=passage.page,
            section=passage.section,
            source_excerpt=passage.text[:1000],
            relevance_score=passage.score,
        )
        db.add(citation)
        citation_rows.append(citation)

    db.commit()

    yield {
        "type": "final",
        "message_id": assistant_message.id,
        "citations": [_citation_payload(c) for c in citation_rows],
        "evidence_quality": result.evidence_quality.value,
        "grounding": [c.model_dump() for c in result.grounding.claims] if result.grounding else None,
    }
