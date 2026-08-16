"""`clinical_module_runs` table — spec §63 Structured Clinical Modules (+ Phase 11's
Research Paper Assistant, spec §70, added to the same table rather than a parallel one
— it's the same "real dedicated workflow, own schema, explicit draft" shape).

One table, one row per generation, covering all seven modules (`module_type`
discriminates the shape of `payload`) rather than seven near-identical tables — each
module still has its own real Pydantic schema/prompt/workflow (spec §63's actual
requirement: "do not implement every capability as send-prompt-to-chat-endpoint"),
this is just where the results land. Every row is an explicit, timestamped **draft**
— spec §63's SOAP note instruction ("generate a clinician-review draft; do not
automatically save as finalized clinical record") applies to all of them: nothing here
ever writes to Condition/Medication/Encounter or any other authoritative table.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClinicalModuleType(str, Enum):
    SUMMARY = "summary"
    SOAP = "soap"
    ENTITY_EXTRACTION = "entity_extraction"
    DIFFERENTIAL_SUPPORT = "differential_support"
    GUIDELINE_QA = "guideline_qa"
    REPORT_COMPARISON = "report_comparison"
    RESEARCH = "research"  # Phase 11 — Research Paper Assistant, spec §70


class ClinicalModuleRun(Base):
    __tablename__ = "clinical_module_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    module_type: Mapped[ClinicalModuleType] = mapped_column(SAEnum(ClinicalModuleType, native_enum=False), nullable=False)

    # Nullable: guideline_qa is patient-independent (spec §63 "use strict evidence-
    # grounded local RAG" — general knowledge-base Q&A, not tied to any one chart).
    patient_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=True, index=True
    )
    encounter_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("encounters.id", ondelete="SET NULL"), nullable=True
    )

    # JSON — the module-specific request parameters (summary_type, question text,
    # previous/current report ids...), kept alongside the result for provenance.
    input_params: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON — the module-specific structured result. Shape depends on module_type;
    # each module's own Pydantic schema is the source of truth for what's in here.
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)

    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generation_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<ClinicalModuleRun {self.module_type.value} patient_id={self.patient_id}>"
