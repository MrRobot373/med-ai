"""Clinical entity extraction — spec §63 "structured output." Extracts entities
literally present in provided text; never infers beyond what's written (same
non-fabrication rule as every other module)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from app.config.settings import Settings
from app.llm.generation import ChatMessage
from app.llm.structured import generate_structured
from app.modules.prompts import ENTITY_EXTRACTION_SYSTEM_PROMPT, build_entity_extraction_user_prompt


class EntityCategory(str, Enum):
    CONDITION = "condition"
    MEDICATION = "medication"
    ALLERGY = "allergy"
    PROCEDURE = "procedure"
    LAB_FINDING = "lab_finding"
    SYMPTOM = "symptom"
    OTHER = "other"


class ExtractedEntity(BaseModel):
    text: str
    category: EntityCategory
    context: str = ""


class EntityExtractionResult(BaseModel):
    entities: list[ExtractedEntity] = []


async def extract_entities(source_title: str, text: str, settings: Settings) -> EntityExtractionResult | None:
    messages = [
        ChatMessage(role="system", content=ENTITY_EXTRACTION_SYSTEM_PROMPT),
        ChatMessage(role="user", content=build_entity_extraction_user_prompt(source_title, text)),
    ]
    return await generate_structured(
        messages,
        EntityExtractionResult,
        settings,
        temperature=settings.clinical_module_temperature,
        max_output_tokens=settings.clinical_module_max_output_tokens,
    )
