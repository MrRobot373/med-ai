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
    REPORT_UPLOADED = "report_uploaded"
    ABNORMAL_RESULT = "abnormal_result"


class TimelineEvent(BaseModel):
    """A single chronological entry (spec §26): encounters, conditions, medications,
    allergies, completed report uploads, and abnormal lab results (not every normal
    result — that would drown the timeline in noise; the full list is on the Labs
    tab)."""

    event_type: TimelineEventType
    event_date: datetime
    title: str
    description: str | None = None
    encounter_id: str | None = None
    source_id: str
