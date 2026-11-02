"""A doctor's reusable prescribing shortcuts, and the letters (certificates, referrals…) the clinic issues."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin, UTCDateTime
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
