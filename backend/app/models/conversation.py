"""`conversations` table — spec §15 Conversations, §40 Conversation Scopes.

A conversation's `scope` is fixed at creation, never silently reinterpreted (spec §40:
"do not silently continue a patient-specific conversation with another patient" —
enforced by `patient_id` being part of the conversation's identity, not a mutable
field a later message could redirect).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConversationScope(str, Enum):
    GENERAL = "general"  # spec's "General Clinical AI" — no patient context
    CURRENT_PATIENT = "current_patient"
    CURRENT_ENCOUNTER = "current_encounter"
    SELECTED_REPORT = "selected_report"
    SELECTED_REPORTS_COMPARISON = "selected_reports_comparison"  # Phase 10 (report comparison engine)
    LOCAL_KNOWLEDGE_ONLY = "local_knowledge_only"
    RESEARCH_MODE = "research_mode"  # Phase 11 (web research)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    patient_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=True, index=True
    )
    encounter_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("encounters.id", ondelete="SET NULL"), nullable=True
    )
    selected_report_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True
    )

    scope: Mapped[ConversationScope] = mapped_column(SAEnum(ConversationScope, native_enum=False), nullable=False)
    # NULL until the first exchange completes, then derived from it — never a fabricated
    # placeholder like "Untitled" masquerading as a real summary.
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<Conversation {self.id} scope={self.scope.value}>"
