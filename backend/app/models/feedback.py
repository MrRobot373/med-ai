"""`feedback` table — spec §81: every AI-generated answer surface should allow
Helpful/Not Helpful/Incorrect/Missing Evidence/Outdated Evidence/Wrong Patient Context,
stored for evaluation. `target_type`/`target_id` is a small polymorphic reference
(rather than a `message_id`-only FK) so the same table covers both real "AI answer"
surfaces this build has: Clinical AI chat messages (private per-conversation) and
Clinical Module runs (SOAP/summary/differential/... plus Phase 11's Research Paper
Assistant — all `ClinicalModuleRun` rows, chart-visible to any clinician per Phase 10's
own convention). One row per (target, user): a clinician revising their reaction to the
same answer overwrites it rather than accumulating duplicate rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FeedbackTarget(str, Enum):
    MESSAGE = "message"
    CLINICAL_MODULE_RUN = "clinical_module_run"


class FeedbackRating(str, Enum):
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"
    INCORRECT = "incorrect"
    MISSING_EVIDENCE = "missing_evidence"
    OUTDATED_EVIDENCE = "outdated_evidence"
    WRONG_PATIENT_CONTEXT = "wrong_patient_context"


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (UniqueConstraint("target_type", "target_id", "user_id", name="uq_feedback_target_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    target_type: Mapped[FeedbackTarget] = mapped_column(SAEnum(FeedbackTarget, native_enum=False), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[FeedbackRating] = mapped_column(SAEnum(FeedbackRating, native_enum=False), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<Feedback {self.target_type.value}:{self.target_id} rating={self.rating.value}>"
