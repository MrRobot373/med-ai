"""Ollama vision analysis — spec §58/§59/§60. Single-image structured extraction and
two-image comparison, both built on the shared `app/llm/generation.py` client (same
model, same concurrency semaphore as chat — spec §58 "use Qwen3.5 vision capability
rather than loading a second large VLM").

Same validate/repair-retry/never-fabricate discipline as
`app/chat/grounding_validator.py` (spec §123): one controlled retry on invalid JSON,
`None` returned (never a fabricated result) if both attempts fail to parse.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ValidationError

from app.config.settings import Settings
from app.ingestion.image import normalize_image_b64
from app.llm.generation import ChatMessage, GenerationError, generate_complete
from app.logging import get_logger
from app.vision.prompts import (
    VISION_ANALYSIS_SYSTEM_PROMPT,
    VISION_COMPARISON_SYSTEM_PROMPT,
)

logger = get_logger(__name__)


class VisionObservation(BaseModel):
    """Spec §60's exact schema."""

    image_type: str = ""
    visible_text: list[str] = []
    observations: list[str] = []
    measurements_visible: list[str] = []
    clinical_entities: list[str] = []
    quality_limitations: list[str] = []
    uncertainties: list[str] = []


class VisionComparison(BaseModel):
    """Spec §61's comparison fields — `clinical_evidence` is filled in by the caller
    from a real RAG lookup against `differences`, not by the model itself (spec §61
    "where useful, retrieve relevant local knowledge based on extracted differences")."""

    previous_findings: list[str] = []
    current_findings: list[str] = []
    observable_changes: list[str] = []
    differences: list[str] = []
    limitations: list[str] = []


_REPAIR_NUDGE = "That was not valid JSON matching the required shape. Return ONLY the JSON object, nothing else."


async def analyze_image(image_bytes: bytes, settings: Settings) -> VisionObservation | None:
    """Returns `None` (never a fabricated result) if the model's output can't be
    parsed as valid structured JSON after one retry, or if Ollama itself is
    unreachable — the caller records that as a failed analysis, not a successful one
    with fake content."""
    image_b64 = normalize_image_b64(image_bytes, settings.vision_max_image_dimension)
    messages = [
        ChatMessage(role="system", content=VISION_ANALYSIS_SYSTEM_PROMPT),
        ChatMessage(role="user", content="Analyze this image.", images=[image_b64]),
    ]
    return await _run_structured(messages, VisionObservation, settings)


async def compare_images(previous_bytes: bytes, current_bytes: bytes, settings: Settings) -> VisionComparison | None:
    """`previous_bytes` and `current_bytes` are sent as two images on one user
    message, in that order — the prompt tells the model which is which by position
    (spec §61's "previous image / current image")."""
    previous_b64 = normalize_image_b64(previous_bytes, settings.vision_max_image_dimension)
    current_b64 = normalize_image_b64(current_bytes, settings.vision_max_image_dimension)
    messages = [
        ChatMessage(role="system", content=VISION_COMPARISON_SYSTEM_PROMPT),
        ChatMessage(
            role="user",
            content="The first image is the PREVIOUS image; the second is the CURRENT image. Compare them.",
            images=[previous_b64, current_b64],
        ),
    ]
    return await _run_structured(messages, VisionComparison, settings)


async def _run_structured(
    messages: list[ChatMessage], schema: type[BaseModel], settings: Settings
) -> BaseModel | None:
    for attempt in range(2):  # one controlled repair/retry, per spec §123
        try:
            raw = await generate_complete(
                messages,
                settings,
                json_format=True,
                temperature=settings.vision_temperature,
                max_output_tokens=settings.vision_max_output_tokens,
            )
            return schema.model_validate(json.loads(raw))
        except (GenerationError, ValueError, ValidationError):
            logger.warning("Vision analysis attempt %s failed to parse", attempt + 1, exc_info=True)
            if attempt == 0:
                messages.append(ChatMessage(role="user", content=_REPAIR_NUDGE))
    return None
