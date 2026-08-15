"""Grounding validation — spec §53 ("classify major statements as supported/
partially supported/unsupported") folded together with spec §52's "ensure the cited
passage reasonably contains/supports the associated claim" into one structured LLM
pass — see `prompts.py`'s docstring for why these are the same underlying judgment.

Uses Pydantic to validate the model's JSON output (spec §123): validate, attempt one
controlled repair/retry, and if it's still invalid, return `None` rather than
fabricating a passing result — a failed safety check must never be silently presented
as a passed one (spec §103).
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ValidationError

from app.chat.context_builder import LabeledEvidence
from app.chat.generation import ChatMessage, GenerationError, generate_complete
from app.chat.prompts import GROUNDING_VALIDATION_SYSTEM_PROMPT, build_grounding_user_prompt
from app.config.settings import Settings
from app.logging import get_logger

logger = get_logger(__name__)


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

    for attempt in range(2):  # one controlled repair/retry, per spec §123
        try:
            raw = await generate_complete(messages, settings, json_format=True)
            return GroundingResult.model_validate(json.loads(raw))
        except (GenerationError, ValueError, ValidationError):
            logger.warning("Grounding validation attempt %s failed", attempt + 1, exc_info=True)
            if attempt == 0:
                messages.append(
                    ChatMessage(
                        role="user",
                        content="That was not valid JSON matching the required shape. "
                        "Return ONLY the JSON object, nothing else.",
                    )
                )
    return None
