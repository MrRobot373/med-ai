"""Report comparison (text reports) — spec §63/Phase 10 "report comparison" +
acceptance criteria "numeric values are calculated deterministically." Numeric diffs
are computed entirely outside this module (`services/clinical_modules.py`, from real
`Observation` rows via `services/observations.py`'s trusted unit conversions) — this
module only narrates non-numeric textual differences, and is explicitly told not to
recompute or restate the numbers as its own calculation.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.config.settings import Settings
from app.llm.generation import ChatMessage
from app.llm.structured import generate_structured
from app.modules.prompts import REPORT_COMPARISON_SYSTEM_PROMPT, build_report_comparison_user_prompt


class ReportComparisonNarrative(BaseModel):
    narrative_differences: list[str] = []
    limitations: list[str] = []


async def generate_comparison_narrative(
    previous_text: str, current_text: str, numeric_changes_summary: str, settings: Settings
) -> ReportComparisonNarrative | None:
    messages = [
        ChatMessage(role="system", content=REPORT_COMPARISON_SYSTEM_PROMPT),
        ChatMessage(
            role="user",
            content=build_report_comparison_user_prompt(previous_text, current_text, numeric_changes_summary),
        ),
    ]
    return await generate_structured(
        messages,
        ReportComparisonNarrative,
        settings,
        temperature=settings.clinical_module_temperature,
        max_output_tokens=settings.clinical_module_max_output_tokens,
    )
