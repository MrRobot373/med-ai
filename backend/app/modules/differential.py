"""Differential Support — spec §63's exact schema. A clinician-support tool, never
"autonomous diagnosis" (spec's own naming instruction — called Differential Support,
not Differential Diagnosis, throughout). Citations are validated against real offered
evidence exactly like chat's citation_validator, reusing the same building blocks.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.chat.context_builder import LabeledEvidence, build_evidence_block
from app.config.settings import Settings
from app.llm.generation import ChatMessage
from app.llm.structured import generate_structured
from app.modules.prompts import DIFFERENTIAL_SUPPORT_SYSTEM_PROMPT, build_differential_user_prompt


class DifferentialCandidate(BaseModel):
    condition: str
    supporting_findings: list[str] = []
    findings_against: list[str] = []
    missing_information: list[str] = []
    evidence_ids: list[str] = []


class DifferentialSupport(BaseModel):
    patient_summary: str = ""
    differential: list[DifferentialCandidate] = []
    red_flags: list[str] = []
    recommended_clarifications: list[str] = []
    evidence_quality: str = ""


async def generate_differential(
    patient_facts: str, labeled_evidence: list[LabeledEvidence], settings: Settings
) -> DifferentialSupport | None:
    evidence_block = build_evidence_block(labeled_evidence)
    messages = [
        ChatMessage(role="system", content=DIFFERENTIAL_SUPPORT_SYSTEM_PROMPT),
        ChatMessage(role="user", content=build_differential_user_prompt(patient_facts, evidence_block)),
    ]
    return await generate_structured(
        messages,
        DifferentialSupport,
        settings,
        temperature=settings.clinical_module_temperature,
        max_output_tokens=settings.clinical_module_max_output_tokens,
    )
