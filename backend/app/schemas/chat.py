from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.citation import CitationSourceType
from app.models.conversation import ConversationScope
from app.models.message import MessageRole


class ConversationCreate(BaseModel):
    scope: ConversationScope
    patient_id: str | None = None
    encounter_id: str | None = None
    selected_report_id: str | None = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    patient_id: str | None
    encounter_id: str | None
    selected_report_id: str | None
    scope: ConversationScope
    title: str | None
    created_at: datetime
    updated_at: datetime


class CitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    source_type: CitationSourceType
    chunk_id: str | None
    report_id: str | None
    source_title: str
    page: int | None
    section: str | None
    source_excerpt: str
    relevance_score: float | None


class GroundingClaimOut(BaseModel):
    claim: str
    cited_labels: list[str] = []
    status: str


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: MessageRole
    content: str
    model: str | None
    generation_error: str | None
    created_at: datetime
    citations: list[CitationOut] = []
    # Parsed from Message.structured_payload — the only "acceptable provenance" per
    # spec §125 (never chain-of-thought). None for user/system messages and for
    # assistant messages predating this field.
    evidence_quality: str | None = None
    grounding: list[GroundingClaimOut] | None = None


class ChatSendRequest(BaseModel):
    text: str
