"""`conditions` table — spec §15 Conditions.

`source_report_id` is deliberately absent until Phase 05 introduces the `reports`
table — adding it now as a plain unconstrained column would either be a dangling
reference or require jumping ahead to build report ingestion early. The migration that
adds `reports` will also add this as a proper foreign key.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import VerificationStatus


class ConditionStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    INACTIVE = "inactive"


class Condition(Base):
    __tablename__ = "conditions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    encounter_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("encounters.id", ondelete="SET NULL"), nullable=True
    )

    code: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ICD-10-CM, Phase 15 ICD assistant
    display: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ConditionStatus] = mapped_column(
        SAEnum(ConditionStatus, native_enum=False), nullable=False, default=ConditionStatus.ACTIVE
    )

    onset_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    resolved_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, native_enum=False), nullable=False, default=VerificationStatus.CONFIRMED
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<Condition {self.display} status={self.status.value}>"
