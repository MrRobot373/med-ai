"""SOAP note generation — spec §63's exact schema. A clinician-review draft, never
automatically saved as a finalized clinical record (enforced by callers: nothing in
this package writes to Encounter/Condition/any authoritative table)."""

from __future__ import annotations

from pydantic import BaseModel

from app.config.settings import Settings
from app.llm.generation import ChatMessage
from app.llm.structured import generate_structured
from app.modules.prompts import SOAP_SYSTEM_PROMPT, build_soap_user_prompt


class SOAPNote(BaseModel):
    subjective: dict[str, str] = {}
    objective: dict[str, str] = {}
    assessment: list[str] = []
    plan: list[str] = []
    missing_information: list[str] = []
    source_trace: list[str] = []


async def generate_soap(context: str, settings: Settings) -> SOAPNote | None:
    messages = [
        ChatMessage(role="system", content=SOAP_SYSTEM_PROMPT),
        ChatMessage(role="user", content=build_soap_user_prompt(context)),
    ]
    return await generate_structured(
        messages,
        SOAPNote,
        settings,
        temperature=settings.clinical_module_temperature,
        max_output_tokens=settings.clinical_module_max_output_tokens,
    )
