from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class TimelineEventType(str, Enum):
    ENCOUNTER = "encounter"
    CONDITION_RECORDED = "condition_recorded"
    CONDITION_RESOLVED = "condition_resolved"
    MEDICATION_STARTED = "medication_started"
    MEDICATION_STOPPED = "medication_stopped"
    ALLERGY_RECORDED = "allergy_recorded"


class TimelineEvent(BaseModel):
    """A single chronological entry (spec §26). Built entirely from structured
    encounters/conditions/medications/allergies data that exists today — report and
    lab events join the same timeline once Phase 05/06 land, without changing this
    shape."""

    event_type: TimelineEventType
    event_date: datetime
    title: str
    description: str | None = None
    encounter_id: str | None = None
    source_id: str
