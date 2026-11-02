"""Licences: signed offline files that set how many people and branches an installation may have.

How it works
  * The vendor holds an Ed25519 private key (never shipped). The matching public key is built into the
    product (`app/assets/licence_public.pem`, or the LICENCE_PUBLIC_KEY setting).
  * A licence is a small JSON file: the terms plus a signature. It is bound to this installation's
    `install_id`, so one licence cannot be reused on a second server.
  * Nothing is checked online. Nothing here ever blocks reading or writing clinical records: a lapsed
    licence only stops *new* seats and branches from being added, and shows a warning to the administrator.
  * Without a licence the install is in evaluation. Evaluation limits apply only in production (APP_ENV=production),
    so development and test environments stay unrestricted.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db import utcnow
from app.models import AIRun, AppSetting, Branch, Document, Patient, User

ASSETS = Path(__file__).resolve().parents[1] / "assets"
EVALUATION = {"clinicians": 2, "staff": 2, "branches": 1}
SEAT_CLASS = {"clinician": "clinicians", "front_desk": "staff", "viewer": "staff"}  # administrators do not use a seat


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def public_key() -> Ed25519PublicKey | None:
    raw = os.environ.get("LICENCE_PUBLIC_KEY", "").strip()
    pem = raw.replace("\\n", "\n").encode() if raw.startswith("-----") else None
    if pem is None and not raw:
        f = ASSETS / "licence_public.pem"
        pem = f.read_bytes() if f.exists() else None
    try:
        if pem:
            key = serialization.load_pem_public_key(pem)
        elif raw:
            key = Ed25519PublicKey.from_public_bytes(base64.b64decode(raw))
        else:
            return None
    except Exception:
        return None
    return key if isinstance(key, Ed25519PublicKey) else None


def install_id(db: Session) -> str:
    row = db.get(AppSetting, "install_id")
    if row is None:
        row = AppSetting(key="install_id", value={"id": uuid.uuid4().hex[:16].upper()})
        db.add(row)
        db.commit()
    return row.value["id"]


def verify(doc: dict, expected_install: str | None = None) -> dict:
    """Returns the payload if the signature and install binding are right, otherwise raises AppError."""
    key = public_key()
    if key is None:
        raise AppError(
            "This build has no vendor key, so licences cannot be checked. Contact your supplier.", status_code=422
        )
    try:
        payload, sig = doc["payload"], base64.b64decode(doc["signature"])
        key.verify(sig, canonical(payload))
    except (KeyError, TypeError, ValueError, InvalidSignature) as exc:
        raise AppError("This licence file is not valid: the signature does not match.", status_code=422) from exc
    if expected_install and payload.get("install_id") not in (expected_install, "*"):
        raise AppError(
            f"This licence was issued for a different installation ({payload.get('install_id')}). "
            f"This server is {expected_install}.",
            status_code=422,
        )
    limits = payload.get("limits") or {}
    if not all(isinstance(limits.get(k), int) and limits[k] >= 0 for k in EVALUATION):
        raise AppError("This licence file is incomplete.", status_code=422)
    return payload


def stored(db: Session) -> dict | None:
    row = db.get(AppSetting, "licence")
    return row.value if row and row.value else None


def save(db: Session, doc: dict, user: User | None) -> dict:
    payload = verify(doc, install_id(db))
    db.merge(AppSetting(key="licence", value=doc, updated_at=utcnow(), updated_by=user.id if user else None))
    db.commit()
    return payload


def remove(db: Session) -> None:
    row = db.get(AppSetting, "licence")
    if row:
        db.delete(row)
        db.commit()


def usage(db: Session) -> dict:
    users = {
        r: n for r, n in db.execute(select(User.role, func.count()).where(User.is_active.is_(True)).group_by(User.role))
    }
    uploads = get_settings().uploads_dir
    size = sum(f.stat().st_size for f in uploads.rglob("*") if f.is_file()) if uploads.exists() else 0
    since = utcnow() - timedelta(days=30)
    return {
        "users": users,
        "clinicians": users.get("clinician", 0),
        "staff": users.get("front_desk", 0) + users.get("viewer", 0),
        "admins": users.get("admin", 0),
        "branches": db.scalar(select(func.count()).select_from(Branch).where(Branch.is_active.is_(True))) or 0,
        "patients": db.scalar(select(func.count()).select_from(Patient).where(Patient.status == "active")) or 0,
        "documents": db.scalar(select(func.count()).select_from(Document)) or 0,
        "storage_bytes": size,
        "ai_runs_30d": db.scalar(select(func.count()).select_from(AIRun).where(AIRun.created_at >= since)) or 0,
    }


def state(db: Session) -> dict:
    """What the administrator sees: the terms, how much is used, and whether new seats may be added."""
    st = get_settings()
    use = usage(db)
    iid = install_id(db)
    doc = stored(db)
    base = {"install_id": iid, "usage": use, "vendor_key": public_key() is not None}
    if not doc:
        enforced = st.is_production
        return {
            **base,
            "mode": "evaluation",
            "customer": None,
            "limits": EVALUATION,
            "enforced": enforced,
            "can_add": True,
            "expires_at": None,
            "days_left": None,
            "message": "Evaluation. Install a licence to add more people and branches.",
        }
    try:
        p = verify(doc, iid)
    except AppError as exc:
        return {
            **base,
            "mode": "invalid",
            "customer": None,
            "limits": EVALUATION,
            "enforced": True,
            "can_add": False,
            "expires_at": None,
            "days_left": None,
            "message": exc.message,
        }
    exp = date.fromisoformat(p["expires_at"]) if p.get("expires_at") else None
    today = date.today()
    grace = int(p.get("grace_days", 30))
    mode, days_left, can_add, msg = "licensed", None, True, f"Licensed to {p.get('customer')}."
    if exp:
        days_left = (exp - today).days
        if days_left < 0 and -days_left <= grace:
            mode, can_add = "grace", True
            msg = f"The licence expired {-days_left} day(s) ago. Renew within {grace + days_left} day(s) to keep adding people and branches."
        elif days_left < 0:
            mode, can_add = "expired", False
            msg = "The licence has expired. Everyone can keep working; new people and branches cannot be added until it is renewed."
        elif days_left <= 30:
            msg = f"The licence expires in {days_left} day(s)."
    return {
        **base,
        "mode": mode,
        "customer": p.get("customer"),
        "licence_id": p.get("licence_id"),
        "limits": p["limits"],
        "enforced": True,
        "can_add": can_add,
        "expires_at": p.get("expires_at"),
        "days_left": days_left,
        "message": msg,
    }


def _enforce(db: Session, key: str, current: int, label: str) -> None:
    s = state(db)
    if not s["enforced"]:
        return
    if not s["can_add"]:
        raise AppError(s["message"], status_code=402, code="licence_required")
    if current + 1 > s["limits"][key]:
        raise AppError(
            f"Your licence allows {s['limits'][key]} {label}. Remove one or ask your supplier for a larger licence.",
            status_code=402,
            code="licence_limit",
        )


def assert_can_add_user(db: Session, role: str, *, excluding: str | None = None) -> None:
    """Called before a person is created, re-activated or moved into a role that uses a seat."""
    cls = SEAT_CLASS.get(role)
    if cls is None:
        return
    stmt = (
        select(func.count())
        .select_from(User)
        .where(User.is_active.is_(True), User.role.in_([r for r, c in SEAT_CLASS.items() if c == cls]))
    )
    if excluding:
        stmt = stmt.where(User.id != excluding)
    _enforce(db, cls, db.scalar(stmt) or 0, "clinicians" if cls == "clinicians" else "front-desk and viewer accounts")


def assert_can_add_branch(db: Session) -> None:
    n = db.scalar(select(func.count()).select_from(Branch).where(Branch.is_active.is_(True))) or 0
    _enforce(db, "branches", n, "branches")


def usage_report(db: Session) -> dict:
    """A small file the clinic can send to the vendor for renewals and billing — counts only, no patient data."""
    s = state(db)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "install_id": s["install_id"],
        "customer": s["customer"],
        "licence_id": s.get("licence_id"),
        "mode": s["mode"],
        "usage": s["usage"],
        "limits": s["limits"],
    }
