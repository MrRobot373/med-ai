from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select

from app.api.deps import DB, AdminUser
from app.models import AuditLog, Message

router = APIRouter(prefix="/api/audit", tags=["audit"])


def _query(q, action, user_email, patient_id, outcome, since, until):
    stmt = select(AuditLog)
    if q:
        stmt = stmt.where(or_(AuditLog.summary.ilike(f"%{q}%"), AuditLog.user_email.ilike(f"%{q}%")))
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    if user_email:
        stmt = stmt.where(AuditLog.user_email == user_email)
    if patient_id:
        stmt = stmt.where(AuditLog.patient_id == patient_id)
    if outcome:
        stmt = stmt.where(AuditLog.outcome == outcome)
    if since:
        stmt = stmt.where(AuditLog.at >= since)
    if until:
        stmt = stmt.where(AuditLog.at <= until)
    return stmt


@router.get("")
def list_audit(
    db: DB,
    _: AdminUser,
    q: str | None = None,
    action: str | None = None,
    user_email: str | None = None,
    patient_id: str | None = None,
    outcome: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    page: int = 1,
    page_size: int = 50,
):
    stmt = _query(q, action, user_email, patient_id, outcome, since, until)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(AuditLog.at.desc()).offset((page - 1) * page_size).limit(min(page_size, 200))).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id,
                "at": r.at,
                "user_email": r.user_email,
                "action": r.action,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "patient_id": r.patient_id,
                "summary": r.summary,
                "details": r.details,
                "ip": r.ip,
                "outcome": r.outcome,
            }
            for r in rows
        ],
    }


@router.get("/facets")
def facets(db: DB, _: AdminUser):
    actions = [a for (a,) in db.execute(select(AuditLog.action).distinct().order_by(AuditLog.action))]
    users = [u for (u,) in db.execute(select(AuditLog.user_email).where(AuditLog.user_email.is_not(None)).distinct())]
    return {"actions": actions, "users": sorted(users)}


@router.get("/export.csv")
def export_csv(
    db: DB,
    _: AdminUser,
    q: str | None = None,
    action: str | None = None,
    user_email: str | None = None,
    patient_id: str | None = None,
    outcome: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
):
    stmt = _query(q, action, user_email, patient_id, outcome, since, until).order_by(AuditLog.at.desc()).limit(50000)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["time", "user", "action", "summary", "entity_type", "entity_id", "patient_id", "outcome", "ip"])
    for r in db.scalars(stmt):
        w.writerow(
            [
                r.at.isoformat(),
                r.user_email or "",
                r.action,
                r.summary,
                r.entity_type or "",
                r.entity_id or "",
                r.patient_id or "",
                r.outcome,
                r.ip or "",
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit-log.csv"'},
    )


@router.get("/feedback")
def feedback(db: DB, _: AdminUser):
    rows = db.scalars(
        select(Message).where(Message.feedback.is_not(None)).order_by(Message.created_at.desc()).limit(200)
    ).all()
    up = sum(1 for m in rows if m.feedback == "up")
    return {
        "summary": {"up": up, "down": len(rows) - up},
        "items": [
            {
                "id": m.id,
                "rating": m.feedback,
                "note": m.feedback_note,
                "content": m.content[:400],
                "model": m.model,
                "conversation_id": m.conversation_id,
                "at": m.created_at,
            }
            for m in rows
        ],
    }
