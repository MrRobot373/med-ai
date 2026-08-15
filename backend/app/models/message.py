"""`messages` table — spec §15 Messages.

`structured_payload` stores only the "acceptable provenance" spec §125 explicitly
names — task classification, the retrieval query used, which evidence was selected,
supported/unsupported grounding classification — never hidden chain-of-thought
reasoning, which is neither requested from the model nor stored here.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(SAEnum(MessageRole, native_enum=False), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # JSON: {"task_classification": "...", "retrieval_query": "...", "evidence_quality":
    # "...", "grounding": [{"claim": "...", "status": "supported"}, ...]}. NULL for user
    # messages (nothing to attach) or an assistant message that abstained pre-generation.
    structured_payload: Mapped[str | None] = mapped_column(Text, nullable=True)

    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # JSON: {"temperature": 0.15, "profile": "fast_demo", ...} — never hardcoded
    # elsewhere, always exactly what was actually used for this specific generation.
    generation_settings: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set only when generation failed outright (spec §119 "show a meaningful error if
    # generation fails") — distinct from an honest abstention, which is a normal
    # assistant message whose content IS the "insufficient evidence" statement.
    generation_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<Message {self.id} role={self.role.value}>"
