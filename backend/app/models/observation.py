"""`observations` table — spec §15/§Observations schema, §33 Laboratory Trend Engine.

Reference ranges/abnormal flags are only ever populated from what the *source document
itself* states (a "Reference Range"/"Target" table column, or an explicit qualitative
annotation like "(elevated)" next to the value) — never a hardcoded "normal" threshold.
Real reference intervals vary by lab, sex, age, and method; baking in a single default
would be exactly the kind of invented clinical fact spec §2 prohibits. See
`app/ingestion/labs.py` for the extraction logic this schema supports.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import VerificationStatus


class ExtractionMethod(str, Enum):
    TABLE = "table"
    INLINE = "inline"
    MANUAL = "manual"


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    encounter_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("encounters.id", ondelete="SET NULL"), nullable=True
    )
    report_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True, index=True
    )

    observation_code: Mapped[str | None] = mapped_column(String(20), nullable=True)  # LOINC, not populated yet
    observation_name: Mapped[str] = mapped_column(String(255), nullable=False)  # as it appeared in the document
    normalized_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # registry canonical key

    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Populated ONLY when the source document itself provides a range — see module
    # docstring. NULL means "unknown", never "assumed normal."
    reference_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    # NULL = not determinable (no range/annotation available) — distinct from False.
    abnormal_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    measured_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        SAEnum(ExtractionMethod, native_enum=False), nullable=False, default=ExtractionMethod.MANUAL
    )
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    clinician_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, native_enum=False), nullable=False, default=VerificationStatus.PROVISIONAL
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<Observation {self.observation_name}={self.value_numeric or self.value_text}>"
