"""A doctor's reusable prescribing shortcuts, and the letters (certificates, referrals…) the clinic issues."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin, UTCDateTime, utcnow
from app.models._ids import new_id


class RxTemplate(TimestampMixin, Base):
    """A saved set of medicines (and diagnosis / advice) a doctor applies to a new prescription."""

    __tablename__ = "rx_templates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    diagnosis: Mapped[str | None] = mapped_column(String(500))
    advice: Mapped[str | None] = mapped_column(Text)
    items: Mapped[list] = mapped_column(JSON, default=list)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)  # visible to every clinician in the clinic
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class DrugFavourite(Base):
    """One medicine with the dose the doctor usually writes for it."""

    __tablename__ = "drug_favourites"
    __table_args__ = (UniqueConstraint("user_id", "drug", name="uq_favourite_user_drug"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    drug: Mapped[str] = mapped_column(String(200))
    dose: Mapped[str | None] = mapped_column(String(60))
    frequency: Mapped[str | None] = mapped_column(String(20))
    duration_days: Mapped[int | None] = mapped_column(Integer)
    route: Mapped[str | None] = mapped_column(String(40))
    instructions: Mapped[str | None] = mapped_column(String(300))


class Letter(TimestampMixin, Base):
    __tablename__ = "letters"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(
        String(24), index=True
    )  # medical_certificate | fitness | referral | visit_summary
    number: Mapped[str | None] = mapped_column(String(32), unique=True)  # given when issued, e.g. MC-2026-0007
    status: Mapped[str] = mapped_column(String(12), default="draft")  # draft | final | void
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    encounter_id: Mapped[str | None] = mapped_column(ForeignKey("encounters.id", ondelete="SET NULL"))
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    author_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    fields: Mapped[dict] = mapped_column(JSON, default=dict)
    body: Mapped[str] = mapped_column(Text, default="")
    finalized_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    void_reason: Mapped[str | None] = mapped_column(String(300))


class Counter(Base):
    """Gap-free sequence numbers per document type and year."""

    __tablename__ = "counters"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)


class ApiToken(Base):
    """A key another system (billing, pharmacy) uses to read what it is allowed to. Only a hash is stored."""

    __tablename__ = "api_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(12), index=True)  # first characters, to recognise it in a list
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_used_ip: Mapped[str | None] = mapped_column(String(64))
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Webhook(TimestampMixin, Base):
    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(String(500))
    secret_enc: Mapped[str] = mapped_column(Text)  # encrypted under APP_SECRET_KEY
    events: Mapped[list] = mapped_column(JSON, default=list)
    payload: Mapped[str] = mapped_column(String(10), default="minimal")  # minimal | full
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    last_status: Mapped[str | None] = mapped_column(String(200))
    last_delivery_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class WebhookDelivery(Base):
    """One message to send to one webhook (an outbox row, written in the same transaction as the event)."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    webhook_id: Mapped[str] = mapped_column(ForeignKey("webhooks.id", ondelete="CASCADE"), index=True)
    event: Mapped[str] = mapped_column(String(40))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)  # pending | delivered | failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    response_code: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class ContentSignoff(Base):
    """A named professional's approval of one area of clinical content, bound to the exact content (by hash) they reviewed."""

    __tablename__ = "content_signoffs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    area: Mapped[str] = mapped_column(String(24), index=True)  # formulary | calculators | knowledge
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(16))  # clinical_lead | pharmacist
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(200))  # kept as written at the time of signing
    registration_no: Mapped[str] = mapped_column(String(80))
    registration_council: Mapped[str | None] = mapped_column(String(120))
    statement: Mapped[str] = mapped_column(Text)
    tests_passed: Mapped[int] = mapped_column(Integer, default=0)
    tests_total: Mapped[int] = mapped_column(Integer, default=0)
    signed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_reason: Mapped[str | None] = mapped_column(String(300))
