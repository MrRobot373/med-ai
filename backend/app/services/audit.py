from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record(
    db: Session,
    user: User | None,
    action: str,
    summary: str,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    patient_id: str | None = None,
    details: dict | None = None,
    ip: str | None = None,
    outcome: str = "success",
    commit: bool = True,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            user_email=user.email if user else None,
            action=action,
            summary=summary[:500],
            entity_type=entity_type,
            entity_id=entity_id,
            patient_id=patient_id,
            details=details or {},
            ip=ip,
            outcome=outcome,
        )
    )
    if commit:
        db.commit()
