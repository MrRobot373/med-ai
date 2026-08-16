"""Shared helper for evaluation scripts that need to run a real chat turn end-to-end
(retrieval -> real Ollama generation -> citation/grounding validation) — the exact
same `app.chat.orchestrator` pipeline live chat uses, per spec §140 rule 9 ("never mock
a core final-demo workflow merely to satisfy a test"). Never persists a Conversation/
Message row — the evaluation suite reads and scores real pipeline output, it doesn't
need its own conversation history in the database.

Imported by citation_eval.py, groundedness_eval.py, and hallucination_eval.py (each
inserts this file's directory onto `sys.path` first, matching the sys.path convention
every `evaluation/*.py` / `scripts/*.py` file in this repo already uses for `backend/`).
"""

from __future__ import annotations

import uuid

from app.chat.orchestrator import PreparedTurn, TurnResult, finalize_turn, prepare_turn
from app.config.settings import Settings
from app.llm.generation import GenerationError, generate_complete
from app.models.conversation import Conversation, ConversationScope


async def run_real_turn(
    db, settings: Settings, user_text: str, scope: ConversationScope, patient_id: str | None = None
) -> tuple[PreparedTurn, str | None, TurnResult | None]:
    """Returns `(prepared, answer_text, result)`. `answer_text` is `None` when
    `prepared.abstain` is True (nothing to generate) or starts with
    `"GENERATION_ERROR: "` if Ollama itself failed; `result` is `None` in either case."""
    conversation = Conversation(id=str(uuid.uuid4()), user_id="eval", scope=scope, patient_id=patient_id)
    prepared = prepare_turn(db, settings, conversation, user_text, history=[])

    if prepared.abstain:
        return prepared, None, None

    try:
        answer_text = await generate_complete(prepared.messages, settings)
    except GenerationError as exc:
        return prepared, f"GENERATION_ERROR: {exc}", None

    result = await finalize_turn(answer_text, prepared.labeled_evidence, settings)
    return prepared, answer_text, result
