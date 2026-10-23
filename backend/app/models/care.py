"""Point-of-care records: the day's expected patients, prescriptions (with their
safety-check results) and investigation orders that are matched to reports later."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin, UTCDateTime, utcnow
from app.models._ids import new_id


class Appointment(TimestampMixin, Base):
    """Deliberately minimal: who is expected on which day. No slots, no billing."""

    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    clinician_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    day: Mapped[date] = mapped_column(Date, index=True)
    time: Mapped[str | None] = mapped_column(String(5))  # "HH:MM", optional
    reason: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(16), default="expected")  # expected | arrived | seen | cancelled
    encounter_id: Mapped[str | None] = mapped_column(ForeignKey("encounters.id", ondelete="SET NULL"))
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class Prescription(TimestampMixin, Base):
    __tablename__ = "prescriptions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    encounter_id: Mapped[str | None] = mapped_column(ForeignKey("encounters.id", ondelete="SET NULL"), index=True)
    clinician_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft | final | cancelled
    diagnosis: Mapped[str | None] = mapped_column(String(500))
    advice: Mapped[str | None] = mapped_column(Text)
    follow_up_date: Mapped[date | None] = mapped_column(Date)
    finalized_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # Patient facts the checks were run against (age, weight, eGFR…) — kept for the record.
    context: Mapped[dict] = mapped_column(JSON, default=dict)

    items: Mapped[list[PrescriptionItem]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan", order_by="PrescriptionItem.position"
    )


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    prescription_id: Mapped[str] = mapped_column(ForeignKey("prescriptions.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    drug: Mapped[str] = mapped_column(String(200))  # as written, e.g. "Dolo 650"
    generic: Mapped[str | None] = mapped_column(String(200))  # resolved, e.g. "paracetamol"
    strength_mg: Mapped[float | None] = mapped_column(Float)
    dose: Mapped[str] = mapped_column(String(60), default="1 tab")
    route: Mapped[str | None] = mapped_column(String(40))
    frequency: Mapped[str] = mapped_column(String(20), default="BD")
    duration_days: Mapped[int | None] = mapped_column(Integer)
    instructions: Mapped[str | None] = mapped_column(String(300))
    checks: Mapped[list] = mapped_column(JSON, default=list)
    override_reason: Mapped[str | None] = mapped_column(String(500))

    prescription: Mapped[Prescription] = relationship(back_populates="items")


class Order(TimestampMixin, Base):
    """An investigation the doctor asked for. When the report comes back and is
    uploaded, it is matched to the open order and surfaced for review."""

    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    encounter_id: Mapped[str | None] = mapped_column(ForeignKey("encounters.id", ondelete="SET NULL"))
    clinician_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    category: Mapped[str] = mapped_column(String(20), default="lab")  # lab | radiology | cardiology | other
    test_name: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str | None] = mapped_column(String(500))
    urgency: Mapped[str] = mapped_column(String(10), default="routine")
    status: Mapped[str] = mapped_column(
        String(20), default="ordered", index=True
    )  # ordered | result_received | reviewed | cancelled
    ordered_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    result_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    result_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    review_note: Mapped[str | None] = mapped_column(Text)
