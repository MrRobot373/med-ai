"""Administration of API keys and webhooks, the read-only partner API they unlock, and CSV exports for billing staff."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, AdminUser, WriteUser
from app.db import utcnow
from app.models import ApiToken, Encounter, Patient, Prescription, Webhook, WebhookDelivery
from app.services import audit, integration, printing

admin = APIRouter(prefix="/api/integrations", tags=["integrations"])
partner = APIRouter(prefix="/api/integration/v1", tags=["partner API"])
exports = APIRouter(prefix="/api/exports", tags=["exports"])


# ------------------------------------------------------------------------------------------- admin: tokens
class TokenIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    scopes: list[str]
    expires_in_days: int | None = Field(None, ge=1, le=3650)


def _token_out(t: ApiToken) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "prefix": t.prefix,
        "scopes": t.scopes,
        "created_at": t.created_at,
        "expires_at": t.expires_at,
        "last_used_at": t.last_used_at,
        "last_used_ip": t.last_used_ip,
        "revoked": t.revoked_at is not None,
    }


@admin.get("/catalog")
def catalog(_: AdminUser):
    return {"scopes": integration.SCOPES, "events": {k: v for k, v in integration.EVENTS.items() if k != "ping"}}


@admin.get("/tokens")
def list_tokens(db: DB, _: AdminUser):
    return [_token_out(t) for t in db.scalars(select(ApiToken).order_by(ApiToken.created_at.desc()))]


@admin.post("/tokens", status_code=201)
def create_token(body: TokenIn, db: DB, user: AdminUser):
    row, plain = integration.create_token(db, body.name, body.scopes, user, body.expires_in_days)
    audit.record(
        db,
        user,
        "integration.token_create",
        f"Created API key '{row.name}'",
        entity_type="api_token",
        entity_id=row.id,
        details={"scopes": row.scopes},
    )
    return {**_token_out(row), "token": plain}  # shown once; only a hash is kept


@admin.delete("/tokens/{token_id}", status_code=204)
def revoke_token(token_id: str, db: DB, user: AdminUser):
    t = db.get(ApiToken, token_id)
    if t is None:
        raise HTTPException(404, "Key not found")
    t.revoked_at = utcnow()
    db.commit()
    audit.record(
        db, user, "integration.token_revoke", f"Revoked API key '{t.name}'", entity_type="api_token", entity_id=t.id
    )


# ------------------------------------------------------------------------------------------- admin: webhooks
class WebhookIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    url: str = Field(max_length=500)
    events: list[str]
    payload: str = Field("minimal", pattern="^(minimal|full)$")
    active: bool = True


class WebhookUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    url: str | None = Field(None, max_length=500)
    events: list[str] | None = None
    payload: str | None = Field(None, pattern="^(minimal|full)$")
    active: bool | None = None


def _hook_out(db, h: Webhook) -> dict:
    counts = {
        s: n
        for s, n in db.execute(
            select(WebhookDelivery.status, __import__("sqlalchemy").func.count())
            .where(WebhookDelivery.webhook_id == h.id)
            .group_by(WebhookDelivery.status)
        )
    }
    return {
        "id": h.id,
        "name": h.name,
        "url": h.url,
        "events": h.events,
        "payload": h.payload,
        "active": h.active,
        "last_status": h.last_status,
        "last_delivery_at": h.last_delivery_at,
        "pending": counts.get("pending", 0),
        "failed": counts.get("failed", 0),
        "delivered": counts.get("delivered", 0),
    }


def _check_events(events: list[str]) -> None:
    bad = [e for e in events if e not in integration.EVENTS or e == "ping"]
    if bad or not events:
        raise HTTPException(422, "Choose at least one event." if not events else f"Unknown event: {', '.join(bad)}")


@admin.get("/webhooks")
def list_webhooks(db: DB, _: AdminUser):
    return [_hook_out(db, h) for h in db.scalars(select(Webhook).order_by(Webhook.created_at))]


@admin.post("/webhooks", status_code=201)
def create_webhook(body: WebhookIn, db: DB, user: AdminUser):
    _check_events(body.events)
    integration.check_url(body.url)
    secret = integration.new_secret()
    h = Webhook(
        name=body.name.strip(),
        url=body.url.strip(),
        events=sorted(set(body.events)),
        payload=body.payload,
        active=body.active,
        secret_enc=integration.encrypt_hook_secret(secret),
        created_by=user.id,
    )
    db.add(h)
    db.commit()
    audit.record(
        db,
        user,
        "integration.webhook_create",
        f"Added webhook '{h.name}'",
        entity_type="webhook",
        entity_id=h.id,
        details={"url": h.url, "events": h.events},
    )
    return {**_hook_out(db, h), "secret": secret}  # shown once


@admin.patch("/webhooks/{hook_id}")
def update_webhook(hook_id: str, body: WebhookUpdate, db: DB, user: AdminUser):
    h = db.get(Webhook, hook_id)
    if h is None:
        raise HTTPException(404, "Webhook not found")
    ch = body.model_dump(exclude_unset=True)
    if "events" in ch:
        _check_events(ch["events"])
        ch["events"] = sorted(set(ch["events"]))
    if "url" in ch:
        integration.check_url(ch["url"])
    for k, v in ch.items():
        setattr(h, k, v)
    db.commit()
    audit.record(
        db,
        user,
        "integration.webhook_update",
        f"Updated webhook '{h.name}'",
        entity_type="webhook",
        entity_id=h.id,
        details=ch,
    )
    return _hook_out(db, h)


@admin.post("/webhooks/{hook_id}/rotate-secret")
def rotate_secret(hook_id: str, db: DB, user: AdminUser):
    h = db.get(Webhook, hook_id)
    if h is None:
        raise HTTPException(404, "Webhook not found")
    secret = integration.new_secret()
    h.secret_enc = integration.encrypt_hook_secret(secret)
    db.commit()
    audit.record(
        db,
        user,
        "integration.webhook_rotate",
        f"Rotated the signing secret of '{h.name}'",
        entity_type="webhook",
        entity_id=h.id,
    )
    return {"secret": secret}


@admin.delete("/webhooks/{hook_id}", status_code=204)
def delete_webhook(hook_id: str, db: DB, user: AdminUser):
    h = db.get(Webhook, hook_id)
    if h is None:
        raise HTTPException(404, "Webhook not found")
    db.delete(h)
    db.commit()
    audit.record(
        db, user, "integration.webhook_delete", f"Deleted webhook '{h.name}'", entity_type="webhook", entity_id=hook_id
    )


@admin.post("/webhooks/{hook_id}/test")
def test_webhook(hook_id: str, db: DB, _: AdminUser):
    h = db.get(Webhook, hook_id)
    if h is None:
        raise HTTPException(404, "Webhook not found")
    d = integration.queue_ping(db, h)
    integration.deliver_due(db, limit=1)
    db.refresh(d)
    return {"status": d.status, "attempts": d.attempts, "response_code": d.response_code, "error": d.error}


@admin.get("/webhooks/{hook_id}/deliveries")
def deliveries(hook_id: str, db: DB, _: AdminUser, limit: int = Query(30, le=200)):
    rows = db.scalars(
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == hook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": d.id,
            "event": d.event,
            "status": d.status,
            "attempts": d.attempts,
            "response_code": d.response_code,
            "error": d.error,
            "created_at": d.created_at,
            "delivered_at": d.delivered_at,
            "next_attempt_at": d.next_attempt_at if d.status == "pending" else None,
        }
        for d in rows
    ]


@admin.post("/deliveries/{delivery_id}/retry")
def retry_delivery(delivery_id: str, db: DB, _: AdminUser):
    d = db.get(WebhookDelivery, delivery_id)
    if d is None:
        raise HTTPException(404, "Delivery not found")
    d.status, d.next_attempt_at, d.attempts = "pending", utcnow(), 0
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------------------------------- partner API
def _since(since: datetime | None) -> datetime:
    return since or (utcnow() - timedelta(days=30))


@partner.get("/prescriptions")
def partner_prescriptions(
    request: Request,
    db: DB,
    since: datetime | None = None,
    limit: int = Query(100, ge=1, le=500),
    after: str | None = None,
):
    integration.authenticate(db, request, "prescriptions:read")
    stmt = (
        select(Prescription)
        .where(Prescription.status == "final", Prescription.finalized_at >= _since(since))
        .order_by(Prescription.finalized_at, Prescription.id)
    )
    rows = db.scalars(stmt).all()
    if after:
        ids = [r.id for r in rows]
        rows = rows[ids.index(after) + 1 :] if after in ids else rows
    page = rows[:limit]
    return {
        "items": [integration.prescription_api(db, r) for r in page],
        "next": page[-1].id if len(rows) > limit else None,
    }


@partner.get("/prescriptions/{rx_id}")
def partner_prescription(rx_id: str, request: Request, db: DB):
    integration.authenticate(db, request, "prescriptions:read")
    rx = db.get(Prescription, rx_id)
    if rx is None or rx.status == "draft":
        raise HTTPException(404, "Prescription not found")
    return integration.prescription_api(db, rx)


class DispenseIn(BaseModel):
    dispensed_by: str = Field(min_length=2, max_length=200, description="Pharmacy name or pharmacist")
    note: str | None = Field(None, max_length=300)


@partner.post("/prescriptions/{rx_id}/dispensed")
def partner_dispensed(rx_id: str, body: DispenseIn, request: Request, db: DB):
    token = integration.authenticate(db, request, "prescriptions:dispense")
    rx = db.get(Prescription, rx_id)
    if rx is None or rx.status != "final":
        raise HTTPException(404, "Prescription not found")
    if rx.dispensed_at:
        raise HTTPException(409, f"Already marked as dispensed by {rx.dispensed_by}.")
    rx.dispensed_at, rx.dispensed_by, rx.dispense_note = utcnow(), body.dispensed_by.strip(), body.note
    integration.emit(
        db,
        "prescription.dispensed",
        rx.id,
        patient_id=rx.patient_id,
        builder=lambda: integration.prescription_api(db, rx),
    )
    db.commit()
    audit.record(
        db,
        None,
        "prescription.dispensed",
        f"Marked dispensed by {body.dispensed_by} (key '{token.name}')",
        entity_type="prescription",
        entity_id=rx.id,
        patient_id=rx.patient_id,
    )
    return integration.prescription_api(db, rx)


@partner.get("/visits")
def partner_visits(request: Request, db: DB, since: datetime | None = None, limit: int = Query(100, ge=1, le=500)):
    integration.authenticate(db, request, "visits:read")
    rows = db.scalars(
        select(Encounter)
        .where(Encounter.status == "completed", Encounter.ended_at >= _since(since))
        .order_by(Encounter.ended_at)
        .limit(limit)
    ).all()
    return {"items": [integration.visit_api(db, e) for e in rows]}


@partner.get("/patients/{mrn}")
def partner_patient(mrn: str, request: Request, db: DB):
    integration.authenticate(db, request, "patients:read")
    p = db.scalars(select(Patient).where(Patient.mrn == mrn)).first()
    if p is None:
        raise HTTPException(404, "Patient not found")
    return integration.patient_brief(p)


# ------------------------------------------------------------------------------------------- CSV exports for staff
def _csv(rows: list[list], header: list[str], name: str) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    # a leading BOM makes Excel open UTF-8 (₹, Devanagari names) correctly
    return Response(
        "﻿" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


def _guard(cell):
    """Spreadsheet formula injection: a value starting with = + - @ would run as a formula when opened."""
    s = "" if cell is None else str(cell)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s


@exports.get("/visits.csv")
def export_visits(db: DB, user: WriteUser, start: date, end: date):
    if (end - start).days > 366:
        raise HTTPException(422, "Choose a period of at most one year.")
    lo = datetime.combine(start, datetime.min.time()).replace(
        tzinfo=printing.ZoneInfo(printing.get_settings().timezone)
    )
    hi = datetime.combine(end + timedelta(days=1), datetime.min.time()).replace(tzinfo=lo.tzinfo)
    rows = []
    for e in db.scalars(
        select(Encounter)
        .where(Encounter.status == "completed", Encounter.ended_at >= lo, Encounter.ended_at < hi)
        .order_by(Encounter.ended_at)
    ):
        v = integration.visit_api(db, e)
        svc = "; ".join(
            s.get("name") or s.get("number") or s["type"] for s in v["services"] if s["type"] != "consultation"
        )
        rows.append(
            [
                _guard(c)
                for c in (
                    v["date"],
                    v["patient"]["mrn"],
                    v["patient"]["name"],
                    v["doctor"],
                    (v["branch"] or {}).get("name"),
                    "; ".join(v["diagnoses"]),
                    svc,
                )
            ]
        )
    audit.record(
        db, user, "export.visits", f"Exported {len(rows)} visits ({start} to {end})", details={"rows": len(rows)}
    )
    return _csv(
        rows,
        ["Date", "MRN", "Patient", "Doctor", "Branch", "Diagnoses", "Investigations / letters"],
        f"visits-{start}-{end}.csv",
    )


@exports.get("/prescriptions.csv")
def export_prescriptions(db: DB, user: WriteUser, start: date, end: date):
    if (end - start).days > 366:
        raise HTTPException(422, "Choose a period of at most one year.")
    tz = printing.ZoneInfo(printing.get_settings().timezone)
    lo = datetime.combine(start, datetime.min.time()).replace(tzinfo=tz)
    hi = datetime.combine(end + timedelta(days=1), datetime.min.time()).replace(tzinfo=tz)
    rows = []
    for rx in db.scalars(
        select(Prescription)
        .where(Prescription.status == "final", Prescription.finalized_at >= lo, Prescription.finalized_at < hi)
        .order_by(Prescription.finalized_at)
    ):
        v = integration.prescription_api(db, rx)
        for i in v["items"]:
            rows.append(
                [
                    _guard(c)
                    for c in (
                        v["issued_at"][:10],
                        v["patient"]["mrn"],
                        v["patient"]["name"],
                        (v["doctor"] or {}).get("name"),
                        v["diagnosis"],
                        i["drug"],
                        i["generic"],
                        i["dose"],
                        i["frequency"],
                        i["duration_days"],
                        "yes" if v["dispensed"] else "",
                    )
                ]
            )
    audit.record(
        db,
        user,
        "export.prescriptions",
        f"Exported {len(rows)} prescription lines ({start} to {end})",
        details={"rows": len(rows)},
    )
    return _csv(
        rows,
        [
            "Date",
            "MRN",
            "Patient",
            "Doctor",
            "Diagnosis",
            "Medicine",
            "Generic",
            "Dose",
            "Frequency",
            "Days",
            "Dispensed",
        ],
        f"prescriptions-{start}-{end}.csv",
    )
