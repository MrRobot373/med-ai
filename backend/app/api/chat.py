"""Clinical AI chat endpoints (spec §104 Clinical AI, §39 Clinical Chat).

The streaming endpoint uses real server-sent events (spec §119 "no fake streaming") —
`StreamingResponse` over `text/event-stream`, not a fully-buffered response chunked
client-side. Conversations are private to the user who created them (no cross-user
visibility here — that's an audit-log concern for Phase 13, not a chat-history one).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.api.common import get_patient_or_404
from app.api.deps import DbDep, SettingsDep
from app.auth.dependencies import CurrentUser, WriteUser
from app.models.conversation import Conversation
from app.models.message import MessageRole
from app.schemas.chat import (
    ChatSendRequest,
    CitationOut,
    ConversationCreate,
    ConversationOut,
    GroundingClaimOut,
    MessageOut,
)
from app.services import chat as chat_service

router = APIRouter(prefix="/api", tags=["chat"])


def _structured_fields(raw_payload: str | None) -> tuple[str | None, list[GroundingClaimOut] | None]:
    """Pulls evidence_quality/grounding back out of Message.structured_payload for the
    API response — see the field docstrings in schemas/chat.py."""
    if not raw_payload:
        return None, None
    payload = json.loads(raw_payload)
    evidence_quality = payload.get("evidence_quality")
    grounding_raw = payload.get("grounding")
    grounding = [GroundingClaimOut.model_validate(c) for c in grounding_raw] if grounding_raw else None
    return evidence_quality, grounding


def _get_own_conversation_or_404(db: DbDep, conversation_id: str, user_id: str) -> Conversation:
    conversation = chat_service.get_conversation(db, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        # Same message either way — never confirm a conversation ID exists for
        # someone else's account (same anti-enumeration pattern as auth's login error).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(db: DbDep, current_user: CurrentUser, patient_id: str | None = None) -> list[ConversationOut]:
    conversations = chat_service.list_conversations(db, current_user.id, patient_id=patient_id)
    return [ConversationOut.model_validate(c) for c in conversations]


@router.post("/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(payload: ConversationCreate, db: DbDep, current_user: WriteUser) -> ConversationOut:
    if payload.patient_id:
        get_patient_or_404(db, payload.patient_id)
    try:
        conversation = chat_service.create_conversation(
            db,
            current_user.id,
            payload.scope,
            patient_id=payload.patient_id,
            encounter_id=payload.encounter_id,
            selected_report_id=payload.selected_report_id,
        )
    except chat_service.UnsupportedScopeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return ConversationOut.model_validate(conversation)


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(conversation_id: str, db: DbDep, current_user: CurrentUser) -> ConversationOut:
    conversation = _get_own_conversation_or_404(db, conversation_id, current_user.id)
    return ConversationOut.model_validate(conversation)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(conversation_id: str, db: DbDep, current_user: CurrentUser) -> list[MessageOut]:
    conversation = _get_own_conversation_or_404(db, conversation_id, current_user.id)
    messages = chat_service.list_messages(db, conversation.id)
    result = []
    for message in messages:
        citations = chat_service.list_citations(db, message.id) if message.role == MessageRole.ASSISTANT else []
        evidence_quality, grounding = _structured_fields(message.structured_payload)
        result.append(
            MessageOut(
                id=message.id,
                conversation_id=message.conversation_id,
                role=message.role,
                content=message.content,
                model=message.model,
                generation_error=message.generation_error,
                created_at=message.created_at,
                citations=[CitationOut.model_validate(c) for c in citations],
                evidence_quality=evidence_quality,
                grounding=grounding,
            )
        )
    return result


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    payload: ChatSendRequest,
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    current_user: WriteUser,
) -> StreamingResponse:
    conversation = _get_own_conversation_or_404(db, conversation_id, current_user.id)

    async def event_stream():
        async for event in chat_service.run_turn(db, settings, conversation, payload.text):
            if await request.is_disconnected():
                break  # spec §120 cancellation — stop once the client is gone
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
