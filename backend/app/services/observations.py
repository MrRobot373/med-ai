"""Structured lab/observation persistence + trend grouping — spec §33 "Laboratory
Trend Engine".

`build_trends` deliberately does NOT depend on the LLM for longitudinal numerical
comparison (spec's own explicit instruction) — grouping, unit conversion, and ordering
are all plain deterministic code. An LLM (Phase 08+) only ever narrates structured data
this module already computed, never re-derives it.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.ingestion.labs import ExtractedObservation
from app.models.observation import ExtractionMethod, Observation
from app.models.report import Report
from app.schemas.observation import ObservationTrend, TrendPoint

# A small, deliberately conservative set of well-established, purely physical unit
# conversions (no clinical judgment involved) — spec §33 "convert only when a trusted
# conversion is defined." Keyed by test -> {canonical_unit: {other_unit: factor}},
# where value_in_canonical = value_in_other_unit * factor. Any test/unit pair not
# listed here is never converted — its readings are excluded from the trend series and
# reported via `excluded_units` instead of being compared unsafely.
_TRUSTED_CONVERSIONS: dict[str, dict[str, dict[str, float]]] = {
    "glucose": {"mg/dL": {"mmol/L": 18.0182}},
    "creatinine": {"mg/dL": {"umol/L": 1 / 88.4, "µmol/L": 1 / 88.4}},
    "total_cholesterol": {"mg/dL": {"mmol/L": 38.67}},
    "ldl_cholesterol": {"mg/dL": {"mmol/L": 38.67}},
    "hdl_cholesterol": {"mg/dL": {"mmol/L": 38.67}},
}


def save_extracted_observations(
    db: DbSession, report: Report, extracted: list[ExtractedObservation]
) -> list[Observation]:
    """Replaces any observations previously saved for this report — idempotent, so a
    future re-extraction feature (or a duplicate pipeline run) never accumulates
    duplicate rows, matching spec §31's "do not create duplicate [] unnecessarily."
    """
    db.query(Observation).filter(Observation.report_id == report.id).delete()

    saved: list[Observation] = []
    for item in extracted:
        observation = Observation(
            patient_id=report.patient_id,
            encounter_id=report.encounter_id,
            report_id=report.id,
            observation_name=item.observation_name,
            normalized_name=item.normalized_name,
            value_numeric=item.value_numeric,
            value_text=item.value_text,
            unit=item.unit,
            reference_low=item.reference_low,
            reference_high=item.reference_high,
            abnormal_flag=item.abnormal_flag,
            measured_at=report.report_date,
            source_page=item.source_page,
            extraction_method=ExtractionMethod(item.extraction_method),
            source_excerpt=item.source_excerpt,
        )
        db.add(observation)
        saved.append(observation)
    db.commit()
    for observation in saved:
        db.refresh(observation)
    return saved


def list_observations(db: DbSession, patient_id: str) -> list[Observation]:
    stmt = (
        select(Observation)
        .where(Observation.patient_id == patient_id)
        .order_by(Observation.measured_at.desc().nulls_last(), Observation.created_at.desc())
    )
    return list(db.scalars(stmt))


def build_trends(observations: list[Observation]) -> list[ObservationTrend]:
    groups: dict[str, list[Observation]] = defaultdict(list)
    for observation in observations:
        groups[observation.normalized_name].append(observation)

    trends: list[ObservationTrend] = []
    for normalized_name, items in groups.items():
        ordered = sorted(items, key=lambda o: (o.measured_at or date.min, o.created_at))

        unit_counts = Counter(o.unit for o in ordered if o.unit)
        primary_unit = unit_counts.most_common(1)[0][0] if unit_counts else None

        points: list[TrendPoint] = []
        excluded_units: set[str] = set()
        for observation in ordered:
            value = observation.value_numeric
            unit = observation.unit
            if value is not None and unit and primary_unit and unit != primary_unit:
                converted = convert_value(normalized_name, value, unit, primary_unit)
                if converted is None:
                    excluded_units.add(unit)
                    continue
                value, unit = converted, primary_unit
            points.append(
                TrendPoint(
                    observation_id=observation.id,
                    measured_at=observation.measured_at,
                    value_numeric=value,
                    value_text=observation.value_text,
                    unit=unit,
                    abnormal_flag=observation.abnormal_flag,
                    report_id=observation.report_id,
                    source_page=observation.source_page,
                )
            )

        trends.append(
            ObservationTrend(
                normalized_name=normalized_name,
                display_name=ordered[-1].observation_name,
                unit=primary_unit,
                points=points,
                unit_conflict=bool(excluded_units),
                excluded_units=sorted(excluded_units),
            )
        )

    trends.sort(key=lambda t: t.display_name)
    return trends


def convert_value(test_key: str, value: float, from_unit: str, to_unit: str) -> float | None:
    """Public so `change_engine.py` can safely compare two readings recorded in
    different units using the same trusted-conversion rules as the trend view — never
    its own separate (and potentially inconsistent) copy of unit math."""
    if from_unit == to_unit:
        return value
    base_test = test_key.split(":")[0]  # strip a wide-format qualifier suffix, e.g. "iop:od"
    table = _TRUSTED_CONVERSIONS.get(base_test)
    if not table:
        return None
    if to_unit in table and from_unit in table[to_unit]:
        return value * table[to_unit][from_unit]
    if from_unit in table and to_unit in table[from_unit]:
        return value / table[from_unit][to_unit]
    return None
