"""Clinical modules persistence + orchestration (spec §63). `app/api/clinical_modules.py`
calls into this; `app/modules/*` has the actual LLM-calling logic and knows nothing
about SQLAlchemy or HTTP. Every run is recorded as an explicit draft
(`ClinicalModuleRun`) — visible to any authenticated clinician viewing that patient's
chart (unlike Phase 08's private chat conversations), since a generated SOAP/summary/
differential draft is chart-adjacent clinical work product, not one user's personal
conversation history.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.chat.context_builder import label_evidence
from app.chat.patient_context import build_encounter_facts, build_patient_facts, build_report_facts
from app.config.settings import Settings
from app.llm.generation import GenerationError
from app.models.chunk import ChunkCollection
from app.models.clinical_module_run import ClinicalModuleRun, ClinicalModuleType
from app.models.encounter import Encounter
from app.models.observation import Observation
from app.models.patient import Patient
from app.models.report import Report
from app.modules import differential as differential_module
from app.modules import entity_extraction as entity_module
from app.modules import guideline_qa as guideline_module
from app.modules import report_comparison as comparison_module
from app.modules import soap as soap_module
from app.modules import summarizer as summarizer_module
from app.modules.summarizer import SummaryType
from app.rag.pipeline import retrieve
from app.services.observations import convert_value

_NOT_PARSED_ERROR = "Model did not return valid structured output after retry"


class ClinicalModuleValidationError(Exception):
    """Bad input for a module call (e.g. neither report_id nor encounter_id given) —
    distinct from a generation failure, which still records a run row."""


def list_runs(
    db: DbSession, patient_id: str | None = None, module_type: ClinicalModuleType | None = None
) -> list[ClinicalModuleRun]:
    stmt = select(ClinicalModuleRun).order_by(ClinicalModuleRun.created_at.desc())
    if patient_id:
        stmt = stmt.where(ClinicalModuleRun.patient_id == patient_id)
    if module_type:
        stmt = stmt.where(ClinicalModuleRun.module_type == module_type)
    return list(db.scalars(stmt))


def get_run(db: DbSession, run_id: str) -> ClinicalModuleRun | None:
    return db.get(ClinicalModuleRun, run_id)


def record_run(
    db: DbSession,
    module_type: ClinicalModuleType,
    patient_id: str | None,
    encounter_id: str | None,
    input_params: dict,
    payload: dict | None,
    model: str | None,
    error: str | None,
    created_by: str | None,
) -> ClinicalModuleRun:
    run = ClinicalModuleRun(
        module_type=module_type,
        patient_id=patient_id,
        encounter_id=encounter_id,
        input_params=json.dumps(input_params),
        payload=json.dumps(payload) if payload is not None else None,
        model=model,
        generation_error=error,
        created_by=created_by,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


# --- Note summarization -----------------------------------------------------------------


async def run_summary(
    db: DbSession,
    settings: Settings,
    patient: Patient,
    summary_type: SummaryType,
    encounter: Encounter | None,
    created_by: str | None,
) -> ClinicalModuleRun:
    parts = [build_patient_facts(db, patient)]
    if encounter:
        parts.append(build_encounter_facts(encounter))
        reports = db.scalars(
            select(Report).where(Report.encounter_id == encounter.id, Report.archived.is_(False))
        ).all()
        parts.extend(build_report_facts(db, r) for r in reports)
    else:
        # No specific encounter given — summarize the patient's overall recent state
        # rather than requiring one (spec's "concise" summary reads as patient-level).
        recent = db.scalars(
            select(Encounter).where(Encounter.patient_id == patient.id).order_by(Encounter.start_datetime.desc()).limit(3)
        ).all()
        parts.extend(build_encounter_facts(e) for e in recent)
    context = "\n\n---\n\n".join(parts)

    input_params = {"summary_type": summary_type.value}
    encounter_id = encounter.id if encounter else None
    try:
        result = await summarizer_module.generate_summary(summary_type, context, settings)
    except GenerationError as exc:
        return record_run(db, ClinicalModuleType.SUMMARY, patient.id, encounter_id, input_params, None, settings.ollama_model, str(exc), created_by)
    if result is None:
        return record_run(db, ClinicalModuleType.SUMMARY, patient.id, encounter_id, input_params, None, settings.ollama_model, _NOT_PARSED_ERROR, created_by)
    return record_run(
        db, ClinicalModuleType.SUMMARY, patient.id, encounter_id, input_params, result.model_dump(mode="json"), settings.ollama_model, None, created_by
    )


# --- SOAP note ---------------------------------------------------------------------------


async def run_soap(db: DbSession, settings: Settings, patient: Patient, encounter: Encounter, created_by: str | None) -> ClinicalModuleRun:
    parts = [build_patient_facts(db, patient), build_encounter_facts(encounter)]
    reports = db.scalars(select(Report).where(Report.encounter_id == encounter.id, Report.archived.is_(False))).all()
    parts.extend(build_report_facts(db, r) for r in reports)
    context = "\n\n---\n\n".join(parts)

    try:
        result = await soap_module.generate_soap(context, settings)
    except GenerationError as exc:
        return record_run(db, ClinicalModuleType.SOAP, patient.id, encounter.id, {}, None, settings.ollama_model, str(exc), created_by)
    if result is None:
        return record_run(db, ClinicalModuleType.SOAP, patient.id, encounter.id, {}, None, settings.ollama_model, _NOT_PARSED_ERROR, created_by)
    return record_run(db, ClinicalModuleType.SOAP, patient.id, encounter.id, {}, result.model_dump(mode="json"), settings.ollama_model, None, created_by)


# --- Entity extraction -------------------------------------------------------------------


async def run_entity_extraction(
    db: DbSession,
    settings: Settings,
    patient: Patient,
    report: Report | None,
    encounter: Encounter | None,
    created_by: str | None,
) -> ClinicalModuleRun:
    if not report and not encounter:
        raise ClinicalModuleValidationError("Either report_id or encounter_id is required")

    if report:
        source_title = report.title
        text = build_report_facts(db, report)
        input_params = {"report_id": report.id}
        encounter_id = report.encounter_id
    else:
        source_title = f"Encounter {encounter.encounter_number}"
        reports = db.scalars(select(Report).where(Report.encounter_id == encounter.id, Report.archived.is_(False))).all()
        text = "\n\n---\n\n".join([build_encounter_facts(encounter), *[build_report_facts(db, r) for r in reports]])
        input_params = {"encounter_id": encounter.id}
        encounter_id = encounter.id

    try:
        result = await entity_module.extract_entities(source_title, text, settings)
    except GenerationError as exc:
        return record_run(db, ClinicalModuleType.ENTITY_EXTRACTION, patient.id, encounter_id, input_params, None, settings.ollama_model, str(exc), created_by)
    if result is None:
        return record_run(db, ClinicalModuleType.ENTITY_EXTRACTION, patient.id, encounter_id, input_params, None, settings.ollama_model, _NOT_PARSED_ERROR, created_by)
    return record_run(
        db, ClinicalModuleType.ENTITY_EXTRACTION, patient.id, encounter_id, input_params, result.model_dump(mode="json"), settings.ollama_model, None, created_by
    )


# --- Differential support ------------------------------------------------------------------


async def run_differential(
    db: DbSession, settings: Settings, patient: Patient, encounter: Encounter | None, created_by: str | None
) -> ClinicalModuleRun:
    facts = [build_patient_facts(db, patient)]
    if encounter:
        facts.append(build_encounter_facts(encounter))
    patient_facts = "\n\n---\n\n".join(facts)

    query = encounter.chief_complaint if encounter and encounter.chief_complaint else patient_facts[:500]
    patient_passages = retrieve(db, query, settings, collection=ChunkCollection.PATIENT_DOCUMENTS, patient_id=patient.id)
    knowledge_passages = retrieve(db, query, settings, collection=ChunkCollection.MEDICAL_KNOWLEDGE)
    vision_passages = retrieve(db, query, settings, collection=ChunkCollection.PATIENT_VISION, patient_id=patient.id)
    labeled = label_evidence(patient_passages, knowledge_passages, vision_passages)

    input_params = {}
    encounter_id = encounter.id if encounter else None
    try:
        result = await differential_module.generate_differential(patient_facts, labeled, settings)
    except GenerationError as exc:
        return record_run(db, ClinicalModuleType.DIFFERENTIAL_SUPPORT, patient.id, encounter_id, input_params, None, settings.ollama_model, str(exc), created_by)
    if result is None:
        return record_run(db, ClinicalModuleType.DIFFERENTIAL_SUPPORT, patient.id, encounter_id, input_params, None, settings.ollama_model, _NOT_PARSED_ERROR, created_by)

    # Never trust the model's own evidence_ids — validate against real offered
    # evidence exactly like chat's citation_validator (spec §52).
    valid_labels = {item.label for item in labeled}
    payload = result.model_dump(mode="json")
    for candidate in payload["differential"]:
        candidate["evidence_ids"] = [e for e in candidate["evidence_ids"] if e in valid_labels]
    return record_run(
        db, ClinicalModuleType.DIFFERENTIAL_SUPPORT, patient.id, encounter_id, input_params, payload, settings.ollama_model, None, created_by
    )


# --- Guideline Q&A (patient-independent) --------------------------------------------------


async def run_guideline_qa(db: DbSession, settings: Settings, question: str, created_by: str | None) -> ClinicalModuleRun:
    knowledge_passages = retrieve(db, question, settings, collection=ChunkCollection.MEDICAL_KNOWLEDGE)
    labeled = label_evidence([], knowledge_passages)
    input_params = {"question": question}

    try:
        result = await guideline_module.answer_guideline_question(question, labeled, settings)
    except GenerationError as exc:
        return record_run(db, ClinicalModuleType.GUIDELINE_QA, None, None, input_params, None, settings.ollama_model, str(exc), created_by)

    payload = {
        "answer": result.answer_text,
        "no_guideline_found": result.no_guideline_found,
        "evidence_quality": result.evidence_quality.value,
        "citations": [
            {
                "label": item.label,
                "source_title": item.passage.source_title,
                "page": item.passage.page,
                "section": item.passage.section,
                "excerpt": item.passage.text[:600],
            }
            for item in result.citations
        ],
    }
    return record_run(db, ClinicalModuleType.GUIDELINE_QA, None, None, input_params, payload, settings.ollama_model, None, created_by)


# --- Report comparison (text reports) -------------------------------------------------------


@dataclass
class NumericChange:
    name: str
    previous_value: float | None
    current_value: float | None
    unit: str | None
    delta: float | None
    percent_change: float | None
    direction: str  # "increased" | "decreased" | "unchanged" | "new" | "resolved"


def _compute_numeric_changes(db: DbSession, previous_report_id: str, current_report_id: str) -> list[NumericChange]:
    """100% deterministic — no LLM involved (spec's acceptance criterion "numeric
    values are calculated deterministically"), same trusted-unit-conversion rules as
    the lab trend engine and change engine (`services/observations.convert_value`)."""
    previous = db.scalars(
        select(Observation).where(Observation.report_id == previous_report_id, Observation.value_numeric.is_not(None))
    ).all()
    current = db.scalars(
        select(Observation).where(Observation.report_id == current_report_id, Observation.value_numeric.is_not(None))
    ).all()
    prev_by_name = {o.normalized_name: o for o in previous}
    curr_by_name = {o.normalized_name: o for o in current}

    changes: list[NumericChange] = []
    for name in sorted(set(prev_by_name) | set(curr_by_name)):
        prev, curr = prev_by_name.get(name), curr_by_name.get(name)
        if prev and not curr:
            changes.append(NumericChange(prev.observation_name, prev.value_numeric, None, prev.unit, None, None, "resolved"))
            continue
        if curr and not prev:
            changes.append(NumericChange(curr.observation_name, None, curr.value_numeric, curr.unit, None, None, "new"))
            continue

        prev_val = prev.value_numeric
        if prev.unit != curr.unit and prev.unit and curr.unit:
            converted = convert_value(name, prev_val, prev.unit, curr.unit)
            if converted is None:
                continue  # no trusted conversion — never compare across incompatible units
            prev_val = converted

        delta = curr.value_numeric - prev_val
        percent_change = (delta / prev_val * 100) if prev_val else None
        direction = "increased" if delta > 0 else "decreased" if delta < 0 else "unchanged"
        changes.append(NumericChange(curr.observation_name, prev_val, curr.value_numeric, curr.unit, delta, percent_change, direction))
    return changes


def _numeric_changes_summary(changes: list[NumericChange]) -> str:
    if not changes:
        return "(no matching numeric observations were found on both reports)"
    lines = []
    for c in changes:
        unit = f" {c.unit}" if c.unit else ""
        if c.direction == "new":
            lines.append(f"{c.name}: new — {c.current_value}{unit}")
        elif c.direction == "resolved":
            lines.append(f"{c.name}: no longer present (was {c.previous_value}{unit})")
        else:
            pct = f", {c.percent_change:+.0f}%" if c.percent_change is not None else ""
            lines.append(f"{c.name}: {c.previous_value}{unit} -> {c.current_value}{unit} ({c.direction}{pct})")
    return "\n".join(lines)


async def run_report_comparison(
    db: DbSession, settings: Settings, patient: Patient, previous_report: Report, current_report: Report, created_by: str | None
) -> ClinicalModuleRun:
    numeric_changes = _compute_numeric_changes(db, previous_report.id, current_report.id)
    numeric_summary = _numeric_changes_summary(numeric_changes)
    previous_text = build_report_facts(db, previous_report)
    current_text = build_report_facts(db, current_report)

    input_params = {"previous_report_id": previous_report.id, "current_report_id": current_report.id}
    try:
        narrative = await comparison_module.generate_comparison_narrative(previous_text, current_text, numeric_summary, settings)
    except GenerationError as exc:
        return record_run(db, ClinicalModuleType.REPORT_COMPARISON, patient.id, None, input_params, None, settings.ollama_model, str(exc), created_by)
    if narrative is None:
        return record_run(db, ClinicalModuleType.REPORT_COMPARISON, patient.id, None, input_params, None, settings.ollama_model, _NOT_PARSED_ERROR, created_by)

    evidence: list[dict] = []
    if narrative.narrative_differences:
        query = " ".join(narrative.narrative_differences)
        passages = retrieve(db, query, settings, collection=ChunkCollection.MEDICAL_KNOWLEDGE, max_per_source=2)
        evidence = [
            {"source_title": p.source_title, "page": p.page, "section": p.section, "excerpt": p.text[:600]} for p in passages
        ]

    payload = {
        "previous_report_id": previous_report.id,
        "current_report_id": current_report.id,
        "numeric_changes": [
            {
                "name": c.name,
                "previous_value": c.previous_value,
                "current_value": c.current_value,
                "unit": c.unit,
                "delta": c.delta,
                "percent_change": c.percent_change,
                "direction": c.direction,
            }
            for c in numeric_changes
        ],
        "narrative_differences": narrative.narrative_differences,
        "limitations": narrative.limitations,
        "clinical_evidence": evidence,
    }
    return record_run(db, ClinicalModuleType.REPORT_COMPARISON, patient.id, None, input_params, payload, settings.ollama_model, None, created_by)
