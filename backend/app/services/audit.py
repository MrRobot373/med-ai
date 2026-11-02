"""The audit trail: who did what, to which patient, when — and tamper-evident.

Every entry stores the SHA-256 of its own content chained to the previous entry's hash. Editing,
deleting or inserting a past row breaks the chain from that point on, which `verify_chain` (and
`python -m app.cli audit-verify`) reports. The chain proves *integrity*; for protection against
someone with full database access who rewrites the whole chain, export and keep the latest hash
(`audit-verify` prints it) somewhere the database administrator cannot change.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import AuditLog, User

_lock = threading.Lock()
GENESIS = "0" * 64


def _stamp(at: datetime) -> str:
    return at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")


def entry_hash(prev: str, row: AuditLog) -> str:
    body = json.dumps(
        [
            prev,
            _stamp(row.at),
            row.user_id,
            row.user_email,
            row.action,
            row.entity_type,
            row.entity_id,
            row.patient_id,
            row.summary,
            row.details or {},
            row.ip,
            row.outcome,
        ],
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(body.encode()).hexdigest()


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
    row = AuditLog(
        at=utcnow(),
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
    with _lock:
        last = db.scalar(
            select(AuditLog.entry_hash).where(AuditLog.entry_hash.is_not(None)).order_by(AuditLog.id.desc())
        )
        row.prev_hash = last or GENESIS
        row.entry_hash = entry_hash(row.prev_hash, row)
        db.add(row)
        if commit:
            db.commit()
        else:
            db.flush()


@dataclass
class ChainReport:
    ok: bool
    checked: int
    unchained: int
    first_bad_id: int | None
    last_hash: str | None
    message: str


def verify_chain(db: Session) -> ChainReport:
    """Recomputes every hash in order. Rows written before the chain existed (no hash) are counted
    separately; once the chain starts, every later row must be chained and intact."""
    prev: str | None = None
    checked = unchained = 0
    last_hash = None
    for row in db.scalars(select(AuditLog).order_by(AuditLog.id)):
        if row.entry_hash is None:
            if prev is not None:
                return ChainReport(
                    False, checked, unchained, row.id, last_hash, f"Entry {row.id} has no hash inside the chain."
                )
            unchained += 1
            continue
        expected_prev = prev if prev is not None else row.prev_hash
        if prev is not None and row.prev_hash != prev:
            return ChainReport(
                False,
                checked,
                unchained,
                row.id,
                last_hash,
                f"Entry {row.id} does not follow the previous entry (a row was removed or inserted).",
            )
        if entry_hash(expected_prev or GENESIS, row) != row.entry_hash:
            return ChainReport(
                False, checked, unchained, row.id, last_hash, f"Entry {row.id} was changed after it was written."
            )
        prev = row.entry_hash
        last_hash = row.entry_hash
        checked += 1
    return ChainReport(True, checked, unchained, None, last_hash, f"{checked} entries verified.")
