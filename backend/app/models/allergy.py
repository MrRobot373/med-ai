"""`allergies` table — spec §15 Allergies. Never silently inferred as absent (spec §2)
— the UI must distinguish "documented no known allergies" from "not yet asked".
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import VerificationStatus


class AllergySeverity(str, Enum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    UNKNOWN = "unknown"


class AllergyStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    RESOLVED = "resolved"


class Allergy(Base):
    __tablename__ = "allergies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )

    substance: Mapped[str] = mapped_column(String(255), nullable=False)
    reaction: Mapped[str | None] = mapped_column(String(500), nullable=True)
    severity: Mapped[AllergySeverity] = mapped_column(
        SAEnum(AllergySeverity, native_enum=False), nullable=False, default=AllergySeverity.UNKNOWN
    )
    status: Mapped[AllergyStatus] = mapped_column(
        SAEnum(AllergyStatus, native_enum=False), nullable=False, default=AllergyStatus.ACTIVE
    )
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, native_enum=False), nullable=False, default=VerificationStatus.CONFIRMED
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<Allergy {self.substance} severity={self.severity.value}>"
