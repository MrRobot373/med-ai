"""Research Paper Assistant — spec §70's structured synthesis over combined patient/
local/external evidence."""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.config.settings import Settings
from app.llm.generation import ChatMessage
from app.llm.structured import generate_structured
from app.research.prompts import RESEARCH_PAPER_ASSISTANT_SYSTEM_PROMPT, build_research_user_prompt


def _coerce_str_list(value: object) -> object:
    """Tolerates the model collapsing a list field into a single string — found live
    (Phase 11): with the much larger combined patient+local+external evidence prompt,
    qwen3.5:9b intermittently returned e.g. `"limitations": "The evidence base is
    limited by..."` instead of `["The evidence base is limited by..."]`, failing
    Pydantic validation on both `generate_structured` attempts even though the JSON
    itself was well-formed. Rather than gambling the whole call on prompt wording
    alone fixing a probabilistic model habit, normalize the shape here: a non-empty
    string becomes a single-item list, an empty/blank string becomes `[]`, anything
    already a list passes through untouched for normal validation."""
    if isinstance(value, str):
        return [value] if value.strip() else []
    return value


class ResearchSynthesis(BaseModel):
    evidence_summary: str = ""
    consensus: str = ""
    conflicting_evidence: list[str] = []
    patient_applicability: str = ""
    exclusion_criteria: list[str] = []
    limitations: list[str] = []

    _coerce_conflicting_evidence = field_validator("conflicting_evidence", mode="before")(_coerce_str_list)
    _coerce_exclusion_criteria = field_validator("exclusion_criteria", mode="before")(_coerce_str_list)
    _coerce_limitations = field_validator("limitations", mode="before")(_coerce_str_list)


async def generate_research_synthesis(
    question: str,
    patient_evidence_block: str,
    local_evidence_block: str,
    external_evidence_block: str,
    settings: Settings,
) -> ResearchSynthesis | None:
    messages = [
        ChatMessage(role="system", content=RESEARCH_PAPER_ASSISTANT_SYSTEM_PROMPT),
        ChatMessage(
            role="user",
            content=build_research_user_prompt(question, patient_evidence_block, local_evidence_block, external_evidence_block),
        ),
    ]
    return await generate_structured(
        messages,
        ResearchSynthesis,
        settings,
        temperature=settings.research_temperature,
        max_output_tokens=settings.research_max_output_tokens,
        num_ctx=settings.research_num_ctx,
    )
