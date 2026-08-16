"""Grounding validation — spec §53 ("classify major statements as supported/
partially supported/unsupported") folded together with spec §52's "ensure the cited
passage reasonably contains/supports the associated claim" into one structured LLM
pass — see `prompts.py`'s docstring for why these are the same underlying judgment.

Validate/repair-retry/never-fabricate (spec §123) lives in `app.llm.structured` —
shared with vision analysis and the clinical modules rather than three separate copies.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.chat.context_builder import LabeledEvidence
from app.chat.prompts import GROUNDING_VALIDATION_SYSTEM_PROMPT, build_grounding_user_prompt
from app.config.settings import Settings
from app.llm.generation import ChatMessage
from app.llm.structured import generate_structured


class GroundingClaim(BaseModel):
    claim: str
    cited_labels: list[str] = []
    status: str  # "supported" | "partially_supported" | "unsupported"


class GroundingResult(BaseModel):
    claims: list[GroundingClaim] = []


def _evidence_block(labeled_evidence: list[LabeledEvidence]) -> str:
    if not labeled_evidence:
        return "(no evidence was provided)"
    return "\n\n".join(
        f'[{item.label}] {item.passage.source_title}\n"{item.passage.text.strip()}"' for item in labeled_evidence
    )


async def validate_grounding(
    answer_text: str, labeled_evidence: list[LabeledEvidence], settings: Settings
) -> GroundingResult | None:
    if not answer_text.strip():
        return GroundingResult(claims=[])

    messages = [
        ChatMessage(role="system", content=GROUNDING_VALIDATION_SYSTEM_PROMPT),
        ChatMessage(role="user", content=build_grounding_user_prompt(answer_text, _evidence_block(labeled_evidence))),
    ]
    return await generate_structured(messages, GroundingResult, settings)
