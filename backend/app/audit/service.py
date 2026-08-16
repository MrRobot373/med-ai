"""Audit trail write path (spec §82). `record()` is best-effort and MUST NOT raise —
an audit-logging bug must never take down the real action it's describing, the same
"never break the primary flow" discipline `ingestion/pipeline.py` already applies to
per-stage failures. Called from the API layer, right after the action it describes has
actually succeeded or failed — never speculatively before.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.logging import get_logger
from app.models.audit_log import AuditAction, AuditLog, AuditOutcome
from app.models.user import User

logger = get_logger(__name__)


def record(
    db: DbSession,
    action: AuditAction,
    *,
    user: User | None = None,
    user_id: str | None = None,
    user_email: str | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    outcome: AuditOutcome = AuditOutcome.SUCCESS,
    detail: dict[str, Any] | None = None,
) -> None:
    """Three ways to identify the actor, in priority order: a loaded `User` (the
    common case — every write endpoint already has one via `CurrentUser`/`WriteUser`),
    a bare `user_id` (resolved to an email via one lookup, so the record stays
    readable), or an explicit `user_email` alone (the one case with no real user at
    all — a failed login attempt against an email that may not belong to any account)."""
    resolved_user_id = user.id if user is not None else user_id
    resolved_email = user.email if user is not None else user_email
    if resolved_email is None and resolved_user_id:
        found = db.get(User, resolved_user_id)
        resolved_email = found.email if found else None

    try:
        db.add(
            AuditLog(
                user_id=resolved_user_id,
                user_email=resolved_email,
                action=action,
                outcome=outcome,
                object_type=object_type,
                object_id=object_id,
                detail=json.dumps(detail) if detail is not None else None,
            )
        )
        db.commit()
    except Exception:
        logger.exception("Failed to write audit log for action=%s", action.value)
        db.rollback()


def list_audit_logs(
    db: DbSession,
    *,
    action: AuditAction | None = None,
    outcome: AuditOutcome | None = None,
    user_id: str | None = None,
    object_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if outcome is not None:
        stmt = stmt.where(AuditLog.outcome == outcome)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if object_type is not None:
        stmt = stmt.where(AuditLog.object_type == object_type)
    stmt = stmt.limit(max(1, min(limit, 500))).offset(max(0, offset))
    return list(db.scalars(stmt))
