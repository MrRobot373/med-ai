"""Deterministic "What Changed?" engine — spec §35: "Implement an actual backend
change engine. Do not just prompt: Compare these records." Everything here is plain
DB comparison; no LLM involved. An LLM (Phase 08+) may narrate this structured output,
never re-derive it.

Scoped to what has a real point-in-time model today: conditions, medications,
allergies, and lab observations. Vitals/symptoms/procedures aren't modeled by any
phase before this one, so they're simply absent from the output rather than
fabricated — a documented, deliberate simplification of spec §35's full entity list.

Observation changes are reported as "increased"/"decreased"/"unchanged" — deliberately
NOT "worsened"/"improved". Whether a rising value is good or bad is test-specific
clinical judgment (rising creatinine is concerning; rising hemoglobin after treating
anemia is not) that this deterministic engine has no basis to assert; that
interpretation belongs to a clinician, or later, an LLM reasoning over the full chart.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session as DbSession

from app.models.condition import Condition, ConditionStatus
from app.models.medication import Medication
from app.models.observation import Observation
from app.schemas.changes import (
    AllergyChange,
    ChangesSummary,
    ConditionChange,
    MedicationDoseChange,
    MedicationStartStop,
    ObservationChange,
)
from app.services.clinical import list_allergies, list_conditions, list_medications
from app.services.observations import convert_value, list_observations


def build_changes_summary(db: DbSession, patient_id: str, since: date) -> ChangesSummary:
    conditions = list_conditions(db, patient_id)
    conditions_new = [
        _to_condition_change(c) for c in conditions if (c.onset_date or c.created_at.date()) >= since
    ]
    conditions_resolved = [
        _to_condition_change(c)
        for c in conditions
        if c.status == ConditionStatus.RESOLVED and c.resolved_date and c.resolved_date >= since
    ]

    medications = list_medications(db, patient_id)
    started_after = [m for m in medications if (m.start_date or m.created_at.date()) >= since]
    stopped_after = [m for m in medications if m.stop_date and m.stop_date >= since]
    dose_changed, started_remaining, stopped_remaining = _pair_dose_changes(started_after, stopped_after)

    allergies_new = [
        AllergyChange(id=a.id, substance=a.substance, recorded_at=a.created_at)
        for a in list_allergies(db, patient_id)
        if a.created_at.date() >= since
    ]

    observations_changed, observations_new_tests = _observation_changes(list_observations(db, patient_id), since)

    return ChangesSummary(
        patient_id=patient_id,
        since=since,
        conditions_new=conditions_new,
        conditions_resolved=conditions_resolved,
        medications_started=[_to_start_stop(m) for m in started_remaining],
        medications_stopped=[_to_start_stop(m) for m in stopped_remaining],
        medications_dose_changed=dose_changed,
        allergies_new=allergies_new,
        observations_changed=observations_changed,
        observations_new_tests=observations_new_tests,
    )


def _to_condition_change(c: Condition) -> ConditionChange:
    return ConditionChange(id=c.id, display=c.display, onset_date=c.onset_date, resolved_date=c.resolved_date)


def _to_start_stop(m: Medication) -> MedicationStartStop:
    return MedicationStartStop(
        id=m.id, medication_name=m.medication_name, dose=m.dose, start_date=m.start_date, stop_date=m.stop_date
    )


def _pair_dose_changes(
    started_after: list[Medication], stopped_after: list[Medication]
) -> tuple[list[MedicationDoseChange], list[Medication], list[Medication]]:
    """A dose change isn't its own concept in the append-only medication model
    (spec §36 "preserve history") — it's represented as stopping one row and starting
    a new one for the same drug. Pair those up here so they surface as one
    "dose changed" entry instead of a misleading separate stop+start."""
    dose_changed: list[MedicationDoseChange] = []
    started_remaining = list(started_after)
    stopped_remaining = list(stopped_after)

    for stopped in list(stopped_remaining):
        match = next(
            (s for s in started_remaining if s.id != stopped.id and _same_drug(s.medication_name, stopped.medication_name)),
            None,
        )
        if match is None:
            continue
        dose_changed.append(
            MedicationDoseChange(
                previous_medication_name=stopped.medication_name,
                current_medication_name=match.medication_name,
                previous_dose=stopped.dose,
                current_dose=match.dose,
                stopped_id=stopped.id,
                started_id=match.id,
            )
        )
        started_remaining.remove(match)
        stopped_remaining.remove(stopped)

    return dose_changed, started_remaining, stopped_remaining


def _same_drug(a: str, b: str) -> bool:
    a_norm, b_norm = a.strip().lower(), b.strip().lower()
    return a_norm == b_norm or a_norm.split()[0] == b_norm.split()[0]


def _observation_changes(observations: list[Observation], since: date) -> tuple[list[ObservationChange], list[str]]:
    groups: dict[str, list[Observation]] = defaultdict(list)
    for observation in observations:
        groups[observation.normalized_name].append(observation)

    changed: list[ObservationChange] = []
    new_tests: list[str] = []
    for normalized_name, items in groups.items():
        ordered = sorted(items, key=lambda o: (o.measured_at or date.min, o.created_at))
        before = [o for o in ordered if (o.measured_at or date.min) < since]
        after = [o for o in ordered if (o.measured_at or date.min) >= since]
        if not after:
            continue

        latest_after = after[-1]
        if not before:
            new_tests.append(latest_after.observation_name)
            continue

        latest_before = before[-1]
        if latest_before.value_numeric is None or latest_after.value_numeric is None:
            continue

        before_value, before_unit = latest_before.value_numeric, latest_before.unit
        after_value, after_unit = latest_after.value_numeric, latest_after.unit
        if before_unit != after_unit:
            if not (before_unit and after_unit):
                continue
            converted = convert_value(normalized_name, before_value, before_unit, after_unit)
            if converted is None:
                continue  # no trusted conversion — don't compare across units (spec §33)
            before_value, before_unit = converted, after_unit

        if after_value == before_value:
            direction = "unchanged"
        else:
            direction = "increased" if after_value > before_value else "decreased"

        changed.append(
            ObservationChange(
                normalized_name=normalized_name,
                display_name=latest_after.observation_name,
                previous_value=before_value,
                previous_unit=before_unit,
                previous_date=latest_before.measured_at,
                current_value=after_value,
                current_unit=after_unit,
                current_date=latest_after.measured_at,
                direction=direction,
            )
        )
    return changed, new_tests
