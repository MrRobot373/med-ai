"""`medications` table — spec §15 Medications.

History is preserved rather than overwritten (spec §36): stopping a medication sets
`active=False` and `stop_date`, it does not delete the row or mutate the original
dose/frequency values a clinician entered. Dose reconciliation (Phase 06) builds on
this append-only history.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import VerificationStatus


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    encounter_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("encounters.id", ondelete="SET NULL"), nullable=True
    )

    medication_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dose: Mapped[str | None] = mapped_column(String(50), nullable=True)
    dose_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    route: Mapped[str | None] = mapped_column(String(50), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(100), nullable=True)

    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    stop_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, native_enum=False), nullable=False, default=VerificationStatus.CONFIRMED
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<Medication {self.medication_name} active={self.active}>"
