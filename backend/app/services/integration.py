"""Letting other systems (billing, pharmacy, a hospital) work with this one — safely and on the clinic's terms.

* API tokens: a long random key per partner, scoped to what they may read, revocable, only a hash stored.
* Webhooks: when something happens (a prescription is finalised…) the system tells the partner. Messages are
  queued in the same database transaction as the event (an outbox), signed with HMAC-SHA256, and retried with
  increasing delays for about two days. A partner that is down for an hour misses nothing.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clinical.context import age
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import decrypt_secret, encrypt_secret
from app.db import utcnow
from app.models import (
    ApiToken,
    Branch,
    Encounter,
    Letter,
    Order,
    Patient,
    Prescription,
    User,
    Webhook,
    WebhookDelivery,
)
from app.services import printing

logger = get_logger("integration")

SCOPES = {
    "patients:read": "Read basic details of patients (name, MRN, age, sex, phone)",
    "prescriptions:read": "Read issued prescriptions, including the medicines",
    "visits:read": "Read completed visits and the services given (for billing)",
    "prescriptions:dispense": "Tell the clinic a prescription was dispensed",
    "metrics:read": "Read health counters (no patient data) for monitoring",
}
EVENTS = {
    "prescription.finalized": "A doctor issued a prescription",
    "prescription.dispensed": "A pharmacy marked a prescription as dispensed",
    "visit.completed": "A consultation was completed",
    "letter.issued": "A certificate or letter was issued",
    "patient.created": "A patient was registered",
    "ping": "Sent by the Test button",
}
RETRY_DELAYS = [
    60,
    300,
    900,
    3600,
    3 * 3600,
    6 * 3600,
    12 * 3600,
    24 * 3600,
]  # seconds; after the last the message is marked failed


# ------------------------------------------------------------------------------------------------ tokens
def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_token(db: Session, name: str, scopes: list[str], user: User, days: int | None) -> tuple[ApiToken, str]:
    bad = [s for s in scopes if s not in SCOPES]
    if bad or not scopes:
        raise HTTPException(
            422, f"Choose at least one valid scope. Unknown: {', '.join(bad)}" if bad else "Choose at least one scope."
        )
    plain = "gms_" + secrets.token_urlsafe(32)
    row = ApiToken(
        name=name.strip(),
        prefix=plain[:10],
        token_hash=_hash(plain),
        scopes=sorted(set(scopes)),
        created_by=user.id,
        expires_at=utcnow() + timedelta(days=days) if days else None,
    )
    db.add(row)
    db.commit()
    return row, plain


def authenticate(db: Session, request: Request, scope: str) -> ApiToken:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(
            401, "Send the key as 'Authorization: Bearer <key>'.", headers={"WWW-Authenticate": "Bearer"}
        )
    token = header[7:].strip()
    row = db.scalars(select(ApiToken).where(ApiToken.token_hash == _hash(token))).first()
    now = utcnow()
    if row is None or row.revoked_at is not None or (row.expires_at and row.expires_at < now):
        raise HTTPException(
            401, "This key is not valid, has expired or was revoked.", headers={"WWW-Authenticate": "Bearer"}
        )
    if scope not in (row.scopes or []):
        raise HTTPException(403, f"This key does not have the '{scope}' permission.")
    if not row.last_used_at or (now - row.last_used_at).total_seconds() > 60:
        row.last_used_at = now
        row.last_used_ip = request.client.host if request.client else None
        db.commit()
    return row


# ------------------------------------------------------------------------------------------------ what partners see
def patient_brief(p: Patient) -> dict:
    return {
        "mrn": p.mrn,
        "name": p.full_name,
        "age": age(p.date_of_birth),
        "sex": p.sex,
        "date_of_birth": p.date_of_birth.isoformat() if p.date_of_birth else None,
        "phone": p.phone,
    }


def prescription_api(db: Session, rx: Prescription) -> dict:
    p = db.get(Patient, rx.patient_id)
    doc = db.get(User, rx.clinician_id) if rx.clinician_id else None
    br = db.get(Branch, rx.branch_id) if rx.branch_id else None
    return {
        "id": rx.id,
        "status": rx.status,
        "issued_at": (rx.finalized_at or rx.created_at).isoformat(),
        "patient": patient_brief(p),
        "doctor": {"name": doc.full_name, "registration_no": doc.registration_no} if doc else None,
        "branch": {"code": br.code, "name": br.name} if br else None,
        "diagnosis": rx.diagnosis,
        "advice": rx.advice,
        "follow_up_date": rx.follow_up_date.isoformat() if rx.follow_up_date else None,
        "items": [
            {
                "drug": i.drug,
                "generic": i.generic,
                "dose": i.dose,
                "frequency": i.frequency,
                "duration_days": i.duration_days,
                "instructions": i.instructions,
            }
            for i in rx.items
        ],
        "dispensed": {"at": rx.dispensed_at.isoformat(), "by": rx.dispensed_by, "note": rx.dispense_note}
        if rx.dispensed_at
        else None,
    }


def visit_api(db: Session, enc: Encounter) -> dict:
    p = db.get(Patient, enc.patient_id)
    doc = db.get(User, enc.clinician_id) if enc.clinician_id else None
    br = db.get(Branch, enc.branch_id) if enc.branch_id else None
    services = [{"type": "consultation"}]
    for o in db.scalars(select(Order).where(Order.encounter_id == enc.id, Order.status != "cancelled")):
        services.append({"type": "investigation", "name": o.test_name, "category": o.category})
    for rx in db.scalars(
        select(Prescription).where(Prescription.encounter_id == enc.id, Prescription.status == "final")
    ):
        services.append({"type": "prescription", "id": rx.id, "medicines": len(rx.items)})
    for lt in db.scalars(select(Letter).where(Letter.encounter_id == enc.id, Letter.status == "final")):
        services.append({"type": "letter", "kind": lt.kind, "number": lt.number})
    return {
        "id": enc.id,
        "date": printing.local_date(enc.started_at).isoformat(),
        "completed_at": enc.ended_at.isoformat() if enc.ended_at else None,
        "patient": patient_brief(p),
        "doctor": doc.full_name if doc else None,
        "branch": {"code": br.code, "name": br.name} if br else None,
        "reason": enc.reason,
        "diagnoses": [d.get("name") for d in enc.diagnoses or [] if d.get("name")],
        "services": services,
    }


# ------------------------------------------------------------------------------------------------ webhooks
def check_url(url: str) -> None:
    """Partners live on the clinic's network, so private addresses are fine; this app itself and cloud metadata are not."""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise HTTPException(422, "The address must start with http:// or https://")
    try:
        infos = socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise HTTPException(422, f"Cannot find the server {u.hostname}.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast:
            raise HTTPException(
                422, "That address is not allowed (this machine itself, or a link-local / metadata address)."
            )


def new_secret() -> str:
    return "whsec_" + secrets.token_urlsafe(32)


def sign(secret: str, timestamp: int, body: str) -> str:
    return hmac.new(secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()


def emit(db: Session, event: str, resource_id: str, *, patient_id: str | None = None, builder=None) -> int:
    """Queues `event` for every active webhook that wants it. Call before the caller's commit, so the message is
    stored (or not) together with the change that caused it. Returns how many messages were queued."""
    hooks = [h for h in db.scalars(select(Webhook).where(Webhook.active.is_(True))) if event in (h.events or [])]
    if not hooks:
        return 0
    mrn = None
    if patient_id:
        p = db.get(Patient, patient_id)
        mrn = p.mrn if p else None
    full = builder() if builder else None
    for h in hooks:
        data = {"event": event, "id": resource_id, "occurred_at": utcnow().isoformat(), "patient_mrn": mrn}
        if h.payload == "full" and full is not None:
            data["data"] = full
        db.add(
            WebhookDelivery(
                webhook_id=h.id,
                event=event,
                body=json.dumps(data, separators=(",", ":"), default=str),
                next_attempt_at=utcnow(),
            )
        )
    db.flush()
    return len(hooks)


def queue_ping(db: Session, hook: Webhook) -> WebhookDelivery:
    d = WebhookDelivery(
        webhook_id=hook.id,
        event="ping",
        body=json.dumps(
            {"event": "ping", "occurred_at": utcnow().isoformat(), "message": "Test message from GMS Clinical AI"}
        ),
        next_attempt_at=utcnow(),
    )
    db.add(d)
    db.commit()
    return d


def deliver_due(db: Session, limit: int = 20, client: httpx.Client | None = None) -> int:
    """Sends what is due. Returns how many attempts were made. Safe to call often."""
    now = utcnow()
    rows = db.scalars(
        select(WebhookDelivery)
        .where(WebhookDelivery.status == "pending", WebhookDelivery.next_attempt_at <= now)
        .order_by(WebhookDelivery.next_attempt_at)
        .limit(limit)
    ).all()
    if not rows:
        return 0
    own = client is None
    client = client or httpx.Client(timeout=10, follow_redirects=False)
    key = get_settings().secret_key
    try:
        for d in rows:
            hook = db.get(Webhook, d.webhook_id)
            if hook is None or not hook.active:
                d.status, d.error = "failed", "The webhook was removed or switched off."
                continue
            d.attempts += 1
            ts = int(time.time())
            try:
                check_url(hook.url)
                secret = decrypt_secret(hook.secret_enc, key) or ""
                r = client.post(
                    hook.url,
                    content=d.body,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "GMS-Clinical-AI-Webhook/1",
                        "X-GMS-Event": d.event,
                        "X-GMS-Delivery": d.id,
                        "X-GMS-Timestamp": str(ts),
                        "X-GMS-Signature": f"t={ts},v1={sign(secret, ts, d.body)}",
                    },
                )
                d.response_code = r.status_code
                if 200 <= r.status_code < 300:
                    d.status, d.delivered_at, d.error = "delivered", utcnow(), None
                    hook.last_status, hook.last_delivery_at = f"OK ({r.status_code})", utcnow()
                    continue
                d.error = f"The receiver answered {r.status_code}"
            except HTTPException as exc:
                d.error = str(exc.detail)[:300]
            except Exception as exc:
                d.error = f"{exc.__class__.__name__}: {exc}"[:300]
            hook.last_status, hook.last_delivery_at = f"Failed: {d.error}"[:200], utcnow()
            if d.attempts > len(RETRY_DELAYS):
                d.status = "failed"
            else:
                d.next_attempt_at = utcnow() + timedelta(seconds=RETRY_DELAYS[d.attempts - 1])
        db.commit()
    finally:
        if own:
            client.close()
    return len(rows)


def encrypt_hook_secret(secret: str) -> str:
    return encrypt_secret(secret, get_settings().secret_key)


# ------------------------------------------------------------------------------------------------ FHIR (HL7 R4)
def prescription_fhir(db: Session, rx: Prescription) -> dict:
    """The issued prescription as a FHIR R4 *document-style* Bundle: Patient, Practitioner and one MedicationRequest per
    medicine. Built from the structured record so a pharmacy's system can read it without parsing text.
    NOT validated against a national profile (e.g. ABDM): that needs the profile's own validator and a test partner."""
    from app.formulary.dosing import parse_frequency

    p = db.get(Patient, rx.patient_id)
    doc = db.get(User, rx.clinician_id) if rx.clinician_id else None
    issued = (rx.finalized_at or rx.created_at).isoformat()
    pat_id, doc_id = f"patient-{p.id}", f"practitioner-{doc.id}" if doc else None
    entries: list[dict] = [
        {
            "fullUrl": f"urn:uuid:{pat_id}",
            "resource": {
                "resourceType": "Patient",
                "id": pat_id,
                "identifier": [{"system": "urn:gms:mrn", "value": p.mrn}],
                "name": [{"text": p.full_name, "family": p.last_name, "given": [p.first_name]}],
                "gender": p.sex if p.sex in ("male", "female", "other") else "unknown",
                **({"birthDate": p.date_of_birth.isoformat()} if p.date_of_birth else {}),
            },
        },
    ]
    if doc:
        entries.append(
            {
                "fullUrl": f"urn:uuid:{doc_id}",
                "resource": {
                    "resourceType": "Practitioner",
                    "id": doc_id,
                    "name": [{"text": doc.full_name}],
                    "identifier": [
                        {
                            "system": f"urn:gms:registration:{(doc.registration_council or 'unknown').replace(' ', '-').lower()}",
                            "value": doc.registration_no,
                        }
                    ]
                    if doc.registration_no
                    else [],
                },
            }
        )
    for n, i in enumerate(rx.items, start=1):
        f = parse_frequency(i.frequency)
        timing: dict = {}
        if f.per_day and not f.weekly:
            timing = {"repeat": {"frequency": max(1, round(f.per_day)), "period": 1, "periodUnit": "d"}}
        elif f.weekly:
            timing = {"repeat": {"frequency": 1, "period": 1, "periodUnit": "wk"}}
        if i.duration_days and timing:
            timing["repeat"]["boundsDuration"] = {
                "value": i.duration_days,
                "unit": "day",
                "system": "http://unitsofmeasure.org",
                "code": "d",
            }
        dosage = {
            "sequence": n,
            "text": " ".join(
                x
                for x in (
                    i.dose,
                    i.frequency,
                    f"for {i.duration_days} days" if i.duration_days else "",
                    i.instructions or "",
                )
                if x
            ),
            **({"timing": timing} if timing else {}),
            **({"asNeededBoolean": True} if f.prn else {}),
        }
        entries.append(
            {
                "fullUrl": f"urn:uuid:{rx.id}-{n}",
                "resource": {
                    "resourceType": "MedicationRequest",
                    "id": f"{rx.id}-{n}",
                    "status": "completed" if rx.dispensed_at else "active",
                    "intent": "order",
                    "authoredOn": issued,
                    "medicationCodeableConcept": {
                        "text": i.drug,
                        **({"coding": [{"system": "urn:gms:generic", "display": i.generic}]} if i.generic else {}),
                    },
                    "subject": {"reference": f"urn:uuid:{pat_id}"},
                    **({"requester": {"reference": f"urn:uuid:{doc_id}"}} if doc else {}),
                    **({"reasonCode": [{"text": rx.diagnosis}]} if rx.diagnosis else {}),
                    "dosageInstruction": [dosage],
                },
            }
        )
    return {"resourceType": "Bundle", "id": rx.id, "type": "collection", "timestamp": issued, "entry": entries}


# ------------------------------------------------------------------------------------------------ metrics
def metrics_text(db: Session) -> str:
    """Prometheus text format. Counts and queue depths only — never patient data."""
    from sqlalchemy import func

    from app.models import AuditLog, Document, WebhookDelivery
    from app.services import backup, licensing

    use = licensing.usage(db)
    b = backup.status(db)
    age = None
    if b.get("last_ok_at"):
        age = (utcnow() - datetime.fromisoformat(b["last_ok_at"])).total_seconds()
    docs = {s: n for s, n in db.execute(select(Document.status, func.count()).group_by(Document.status))}
    hooks = {s: n for s, n in db.execute(select(WebhookDelivery.status, func.count()).group_by(WebhookDelivery.status))}
    lines = [
        "# HELP gms_up The application is running.",
        "# TYPE gms_up gauge",
        "gms_up 1",
        "# TYPE gms_patients gauge",
        f"gms_patients {use['patients']}",
        "# TYPE gms_users gauge",
        *[f'gms_users{{role="{r}"}} {n}' for r, n in use["users"].items()],
        "# TYPE gms_storage_bytes gauge",
        f"gms_storage_bytes {use['storage_bytes']}",
        "# TYPE gms_documents gauge",
        *[f'gms_documents{{status="{s}"}} {n}' for s, n in docs.items()],
        "# TYPE gms_webhook_deliveries gauge",
        *[f'gms_webhook_deliveries{{status="{s}"}} {n}' for s, n in hooks.items()],
        "# TYPE gms_audit_entries counter",
        f"gms_audit_entries {db.scalar(select(func.count()).select_from(AuditLog)) or 0}",
        "# HELP gms_backup_age_seconds Seconds since the last successful backup (absent if never).",
        "# TYPE gms_backup_age_seconds gauge",
    ]
    if age is not None:
        lines.append(f"gms_backup_age_seconds {int(age)}")
    return "\n".join(lines) + "\n"
