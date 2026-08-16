"""Audit log review (spec §82; spec §18 lists "Review audits" only under Admin's
permissions, same rationale as Knowledge Administration in Phase 12)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbDep
from app.audit.service import list_audit_logs
from app.auth.dependencies import AdminUser
from app.models.audit_log import AuditAction, AuditOutcome
from app.schemas.audit import AuditLogOut

router = APIRouter(prefix="/api", tags=["audit"])


@router.get("/audit", response_model=list[AuditLogOut])
def list_audit(
    db: DbDep,
    _admin: AdminUser,
    action: AuditAction | None = None,
    outcome: AuditOutcome | None = None,
    user_id: str | None = None,
    object_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLogOut]:
    logs = list_audit_logs(
        db, action=action, outcome=outcome, user_id=user_id, object_type=object_type, limit=limit, offset=offset
    )
    return [AuditLogOut.model_validate(row) for row in logs]
