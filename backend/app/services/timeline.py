"""Builds the patient timeline (spec §26) from structured data that exists today.

Deliberately NOT report/lab-derived yet — those events join once Phase 05/06 add the
`reports`/`observations` tables. The `TimelineEvent` shape already anticipates them
(a generic event_type/date/title/description), so adding those sources later doesn't
require reshaping anything a frontend already consumes.
"""

from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy.orm import Session as DbSession

from app.models.condition import ConditionStatus
from app.schemas.timeline import TimelineEvent, TimelineEventType
from app.services.clinical import list_allergies, list_conditions, list_medications
from app.services.encounters import list_encounters


def _as_datetime(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min)


def build_timeline(db: DbSession, patient_id: str) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []

    for encounter in list_encounters(db, patient_id):
        label = encounter.encounter_type.value.replace("_", " ").title()
        events.append(
            TimelineEvent(
                event_type=TimelineEventType.ENCOUNTER,
                event_date=_as_datetime(encounter.start_datetime),
                title=f"{label} encounter" + (f" — {encounter.chief_complaint}" if encounter.chief_complaint else ""),
                description=encounter.clinician_note,
                encounter_id=encounter.id,
                source_id=encounter.id,
            )
        )

    for condition in list_conditions(db, patient_id):
        events.append(
            TimelineEvent(
                event_type=TimelineEventType.CONDITION_RECORDED,
                event_date=_as_datetime(condition.onset_date or condition.created_at),
                title=f"Condition documented: {condition.display}",
                description=condition.notes,
                encounter_id=condition.encounter_id,
                source_id=condition.id,
            )
        )
        if condition.status == ConditionStatus.RESOLVED and condition.resolved_date:
            events.append(
                TimelineEvent(
                    event_type=TimelineEventType.CONDITION_RESOLVED,
                    event_date=_as_datetime(condition.resolved_date),
                    title=f"Condition resolved: {condition.display}",
                    source_id=condition.id,
                )
            )

    for medication in list_medications(db, patient_id):
        dose_part = f" {medication.dose}{medication.dose_unit or ''}".rstrip() if medication.dose else ""
        events.append(
            TimelineEvent(
                event_type=TimelineEventType.MEDICATION_STARTED,
                event_date=_as_datetime(medication.start_date or medication.created_at),
                title=f"Started {medication.medication_name}{dose_part}",
                encounter_id=medication.encounter_id,
                source_id=medication.id,
            )
        )
        if not medication.active and medication.stop_date:
            events.append(
                TimelineEvent(
                    event_type=TimelineEventType.MEDICATION_STOPPED,
                    event_date=_as_datetime(medication.stop_date),
                    title=f"Stopped {medication.medication_name}",
                    source_id=medication.id,
                )
            )

    for allergy in list_allergies(db, patient_id):
        events.append(
            TimelineEvent(
                event_type=TimelineEventType.ALLERGY_RECORDED,
                event_date=_as_datetime(allergy.created_at),
                title=f"Allergy documented: {allergy.substance}",
                description=allergy.reaction,
                source_id=allergy.id,
            )
        )

    events.sort(key=lambda e: e.event_date, reverse=True)
    return events
