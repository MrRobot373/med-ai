"""Shared structured-JSON generation helper — spec §123's validate/repair-retry/
never-fabricate discipline. One controlled retry on invalid JSON; returns `None`
(never a fabricated result) if both attempts fail to parse against the given Pydantic
schema. Used by grounding validation (Phase 08), vision analysis (Phase 09), and the
clinical modules (Phase 10) — the same judgment call made in one place instead of
three slightly-different copies.
"""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.config.settings import Settings
from app.llm.generation import ChatMessage, GenerationError, generate_complete
from app.logging import get_logger

logger = get_logger(__name__)

_REPAIR_NUDGE = "That was not valid JSON matching the required shape. Return ONLY the JSON object, nothing else."

_SchemaT = TypeVar("_SchemaT", bound=BaseModel)


async def generate_structured(
    messages: list[ChatMessage],
    schema: type[_SchemaT],
    settings: Settings,
    *,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    num_ctx: int | None = None,
) -> _SchemaT | None:
    raw = ""
    for attempt in range(2):  # one controlled repair/retry, per spec §123
        try:
            raw = await generate_complete(
                messages,
                settings,
                json_format=True,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                num_ctx=num_ctx,
            )
            return schema.model_validate(json.loads(raw))
        except (GenerationError, ValueError, ValidationError):
            # Logging a preview (not exc_info alone) is what makes this diagnosable —
            # a bare exception tells you parsing failed, not *what* the model actually
            # sent back (truncated JSON vs. extra prose vs. empty string each point at
            # a different fix: num_ctx, max_output_tokens, or the prompt itself).
            logger.warning(
                "Structured generation attempt %s failed to parse; raw preview: %r",
                attempt + 1,
                raw[:500],
                exc_info=True,
            )
            if attempt == 0:
                messages.append(ChatMessage(role="user", content=_REPAIR_NUDGE))
    return None
