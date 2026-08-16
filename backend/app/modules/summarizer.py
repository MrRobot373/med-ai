"""Note summarization — spec §63: concise/discharge/encounter/progress-note summaries."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from app.config.settings import Settings
from app.llm.generation import ChatMessage
from app.llm.structured import generate_structured
from app.modules.prompts import SUMMARY_SYSTEM_PROMPT, build_summary_user_prompt


class SummaryType(str, Enum):
    CONCISE = "concise"
    DISCHARGE = "discharge"
    ENCOUNTER = "encounter"
    PROGRESS_NOTE = "progress_note"


_DISPLAY = {
    SummaryType.CONCISE: "concise patient summary",
    SummaryType.DISCHARGE: "discharge summary",
    SummaryType.ENCOUNTER: "encounter summary",
    SummaryType.PROGRESS_NOTE: "progress-note summary",
}


class SummaryResult(BaseModel):
    summary: str = ""
    key_points: list[str] = []
    source_trace: list[str] = []


async def generate_summary(summary_type: SummaryType, context: str, settings: Settings) -> SummaryResult | None:
    system_prompt = SUMMARY_SYSTEM_PROMPT.format(summary_type=_DISPLAY[summary_type])
    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=build_summary_user_prompt(context)),
    ]
    return await generate_structured(
        messages,
        SummaryResult,
        settings,
        temperature=settings.clinical_module_temperature,
        max_output_tokens=settings.clinical_module_max_output_tokens,
    )
