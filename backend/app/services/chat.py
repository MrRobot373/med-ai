"""Evidence-grounded chat. One turn:

  question → retrieval (patient + knowledge) →
  abstain if nothing relevant → prompt with labelled evidence → stream tokens →
  validate citations → persist answer + provenance trace.

Yields event dicts; the API layer frames them as Server-Sent Events.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import registry
from app.ai.llm import ChatMessage
from app.clinical import citations
from app.clinical.context import patient_record_text
from app.clinical.prompts import CHAT_SYSTEM, INSUFFICIENT, evidence_block
from app.core.errors import ServiceUnavailable
from app.core.logging import get_logger
from app.db import utcnow
from app.models import Conversation, Message, Patient, User
from app.rag.retrieve import retrieve
from app.services import audit, runtime_config

logger = get_logger(__name__)


def _title_from(question: str) -> str:
    t = " ".join(question.split())
    return (t[:60] + "…") if len(t) > 60 else t


def _history(conv: Conversation, turns: int, exclude_id: str) -> list[ChatMessage]:
    msgs = [m for m in conv.messages if m.id != exclude_id and m.status in ("complete", "abstained")]
    msgs = msgs[-turns * 2 :] if turns else []
    return [ChatMessage(m.role, m.content) for m in msgs]


async def answer(db: Session, user: User, conv: Conversation, question: str) -> AsyncIterator[dict]:
    cfg = runtime_config.load(db)
    started = time.perf_counter()
    patient = db.get(Patient, conv.patient_id) if conv.patient_id else None

    user_msg = Message(conversation_id=conv.id, role="user", content=question)
    db.add(user_msg)
    if conv.title == "New conversation":
        conv.title = _title_from(question)
    db.commit()
    db.refresh(conv)
    yield {"event": "user_message", "data": {"id": user_msg.id, "content": question, "title": conv.title}}

    # 1. Retrieval
    yield {"event": "status", "data": {"stage": "retrieving", "label": "Searching records and knowledge"}}
    try:
        result = await retrieve(
            db,
            cfg,
            question,
            patient_id=patient.id if patient else None,
            include_knowledge=conv.scope != "patient" or cfg.retrieval.include_knowledge_in_patient_chat,
        )
    except ServiceUnavailable as exc:
        yield _error(db, conv, exc.message, started)
        return
    passages = result.passages
    trace = result.trace

    sources = [p.public() for p in passages]
    if patient:
        sources.insert(
            0,
            {
                "label": "R",
                "scope": "record",
                "document_title": f"Structured record — {patient.full_name}",
                "excerpt": "Conditions, allergies, medications, latest results and recent encounters from the chart.",
            },
        )
    yield {"event": "sources", "data": {"sources": sources, "trace": trace}}

    # 2. Abstain when nothing relevant was found (never fall back to ungrounded answering)
    if not passages and not patient:
        content = f"{INSUFFICIENT}\n\nNo passages in the knowledge library matched this question."
        yield {"event": "token", "data": {"text": content}}
        msg = _save(db, conv, content, "abstained", sources, trace, None, started, [])
        yield {"event": "done", "data": _message_out(msg)}
        return

    # 3. Prompt
    system = CHAT_SYSTEM.format(product=cfg.branding.product_name, insufficient=INSUFFICIENT)
    blocks = []
    if patient:
        blocks.append("PATIENT RECORD [R]\n" + patient_record_text(db, patient))
    if passages:
        blocks.append("EVIDENCE\n" + evidence_block(passages))
    if not passages:
        blocks.append("EVIDENCE\n(no matching passages were found in documents or the knowledge library)")
    context = "\n\n=====\n\n".join(blocks)
    messages = [ChatMessage("system", system)]
    messages += _history(conv, cfg.retrieval.history_turns, user_msg.id)
    messages.append(ChatMessage("user", f"{context}\n\n=====\n\nQUESTION: {question}"))

    # 5. Generate
    yield {"event": "status", "data": {"stage": "generating", "label": "Writing answer"}}
    llm = registry.llm(cfg)
    parts: list[str] = []
    gen_started = time.perf_counter()
    first_token_ms = None
    try:
        async for piece in llm.stream(messages):
            if first_token_ms is None:
                first_token_ms = int((time.perf_counter() - gen_started) * 1000)
            parts.append(piece)
            yield {"event": "token", "data": {"text": piece}}
    except ServiceUnavailable as exc:
        yield _error(db, conv, exc.message, started, partial="".join(parts))
        return

    raw = "".join(parts).strip()
    allowed = {s["label"] for s in sources}
    cleaned, used, invalid = citations.validate(raw, allowed)
    trace["generation"] = {
        "model": llm.model,
        "first_token_ms": first_token_ms,
        "generation_ms": int((time.perf_counter() - gen_started) * 1000),
        "citations_used": used,
        "invalid_citations_removed": invalid,
        "citation_coverage": citations.coverage(cleaned),
    }
    status = "abstained" if INSUFFICIENT.lower()[:60] in cleaned.lower() else "complete"
    for s in sources:
        s["cited"] = s["label"] in used
    msg = _save(db, conv, cleaned, status, sources, trace, llm.model, started, used)
    audit.record(
        db,
        user,
        "ai.chat",
        f"Asked: {_title_from(question)}",
        entity_type="conversation",
        entity_id=conv.id,
        patient_id=conv.patient_id,
        details={"sources": len(sources), "cited": used},
    )
    yield {"event": "done", "data": _message_out(msg)}


def _save(db, conv, content, status, sources, trace, model, started, used) -> Message:
    msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=content,
        status=status,
        citations=sources,
        trace=trace,
        model=model,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
    db.add(msg)
    conv.updated_at = utcnow()
    db.commit()
    return msg


def _error(db: Session, conv: Conversation, message: str, started: float, partial: str = "") -> dict:
    msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=partial,
        status="error",
        trace={"error": message},
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
    db.add(msg)
    db.commit()
    return {"event": "error", "data": {"message": message, "id": msg.id}}


def _message_out(m: Message) -> dict:
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "status": m.status,
        "citations": m.citations,
        "trace": m.trace,
        "model": m.model,
        "latency_ms": m.latency_ms,
        "feedback": m.feedback,
        "created_at": m.created_at.isoformat(),
    }


def message_out(m: Message) -> dict:
    return _message_out(m)


def conversations_for(db: Session, user: User, patient_id: str | None = None) -> list[Conversation]:
    q = select(Conversation).where(Conversation.user_id == user.id)
    if patient_id:
        q = q.where(Conversation.patient_id == patient_id)
    return list(db.scalars(q.order_by(Conversation.pinned.desc(), Conversation.updated_at.desc())))
