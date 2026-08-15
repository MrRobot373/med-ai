"""Deterministic task classification — spec §43 Stage 2: "Use deterministic routing
where obvious. Use LLM structured classification only when necessary."

Scoped to what Phase 08 actually needs to decide: whether this message is a
substantive clinical question that needs retrieval at all, or small talk that doesn't
(so we don't run a full RAG pipeline — and burn a slow CPU embedding call — on
"thanks"). The deeper task categories spec §43 lists (report comparison, SOAP note,
coding request, vision request, ...) route to modules that don't exist until Phase
09-11; a classifier deciding among them today would have nowhere real to send most of
its own output. This one grows as those phases land, not before (spec §135).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_GREETING_PATTERN = re.compile(
    r"^\s*(hi|hello|hey|thanks|thank you|ok|okay|good morning|good afternoon|good evening|bye|goodbye)[.!?\s]*$",
    re.IGNORECASE,
)


@dataclass
class QueryClassification:
    task: str  # "general_conversation" | "clinical_question"
    needs_retrieval: bool


def classify_query(text: str) -> QueryClassification:
    stripped = text.strip()
    if not stripped or _GREETING_PATTERN.match(stripped):
        return QueryClassification(task="general_conversation", needs_retrieval=False)
    return QueryClassification(task="clinical_question", needs_retrieval=True)
