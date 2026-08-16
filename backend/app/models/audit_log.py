"""`audit_logs` table — spec §82 Audit Trail. Records meaningful, security/compliance-
relevant events (never every read request) so an admin can reconstruct who did what,
when. Written best-effort via `app.audit.service.record()`: a logging failure must
never break the action being logged — same "never raise past its own boundary"
discipline as `ingestion/pipeline.py`'s stage isolation.

`user_id` is nullable + SET NULL (same convention as `KnowledgeDocument.created_by`) so
deactivating/removing an account never blocks on its audit history; `user_email` is a
write-time snapshot so the record stays human-readable even after that FK goes NULL —
an audit trail that becomes anonymous the moment an account disappears defeats its own
purpose. It also covers failed-login rows, where there may be no real `user_id` at all
(the attempted email might not belong to any account).

`detail` is free-form JSON but deliberately minimal — spec §82: "Avoid putting
unnecessary full PHI or passwords/tokens into logs." Callers pass small structured
metadata only (counts, scope names, source lists) — never raw clinical free text such
as a chat question or a report's extracted content.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditAction(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    PATIENT_CREATED = "patient_created"
    PATIENT_MODIFIED = "patient_modified"
    ENCOUNTER_CREATED = "encounter_created"
    REPORT_UPLOADED = "report_uploaded"
    REPORT_ARCHIVED = "report_archived"
    KNOWLEDGE_DOCUMENT_UPLOADED = "knowledge_document_uploaded"
    KNOWLEDGE_VERSION_CHANGED = "knowledge_version_changed"
    CLINICAL_AI_QUERY = "clinical_ai_query"
    RESEARCH_MODE_ENABLED = "research_mode_enabled"
    EXTERNAL_SEARCH_EXECUTED = "external_search_executed"
    # Defined for spec §82's completeness but never emitted in this build: no Export
    # feature exists anywhere in the 16-phase roadmap (spec §83 "Export" was never
    # scheduled into a phase — see docs/architecture.md's Phase 13 notes) and the
    # Settings nav item stays an explicit NotYetBuilt placeholder for the same reason
    # — no "settings changed" action can honestly be logged for a feature that doesn't
    # exist. Nothing here would need to change shape to start emitting either once a
    # real feature exists behind it.
    AI_EXPORT_CREATED = "ai_export_created"
    SETTINGS_CHANGED = "settings_changed"


class AuditOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    action: Mapped[AuditAction] = mapped_column(SAEnum(AuditAction, native_enum=False), nullable=False, index=True)
    outcome: Mapped[AuditOutcome] = mapped_column(
        SAEnum(AuditOutcome, native_enum=False), nullable=False, default=AuditOutcome.SUCCESS
    )

    object_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # JSON — small structured metadata only (see module docstring).
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<AuditLog {self.action.value} user={self.user_email!r} outcome={self.outcome.value}>"
