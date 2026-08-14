"""`encounters` table — spec §15 Encounters."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EncounterType(str, Enum):
    OUTPATIENT = "outpatient"
    INPATIENT = "inpatient"
    TELEHEALTH = "telehealth"
    PROCEDURE = "procedure"
    OTHER = "other"


class EncounterStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Encounter(Base):
    __tablename__ = "encounters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    encounter_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    encounter_type: Mapped[EncounterType] = mapped_column(SAEnum(EncounterType, native_enum=False), nullable=False)

    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[EncounterStatus] = mapped_column(
        SAEnum(EncounterStatus, native_enum=False), nullable=False, default=EncounterStatus.PLANNED
    )

    chief_complaint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    clinician_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<Encounter {self.encounter_number} status={self.status.value}>"
