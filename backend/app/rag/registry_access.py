"""Small bridge so API code can re-point vectors without importing the provider registry everywhere."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai import registry
from app.core.logging import get_logger
from app.services import runtime_config

logger = get_logger("vectors")


async def reassign_patient_vectors(db: Session, old_id: str, new_id: str) -> None:
    try:
        await registry.vector_store(runtime_config.load(db)).reassign_patient(old_id, new_id)
    except Exception:
        # The database is already merged. Search results for the old chart's documents would be missing until a re-index.
        logger.warning(
            "Could not re-point vectors from %s to %s; re-index the library to repair", old_id, new_id, exc_info=True
        )
