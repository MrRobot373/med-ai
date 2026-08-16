"""Clinical modules service layer (spec §63). Deterministic numeric-diff logic
(report_comparison) gets the most thorough direct testing since it's pure business
logic with no LLM involved — spec's own acceptance criterion "numeric values are
calculated deterministically." LLM-calling paths use real DB rows with the module-
level generation functions mocked, mirroring test_chat_orchestrator.py's approach.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest

from app.config.settings import get_settings
from app.db.session import SessionLocal
from app.models.chunk import ChunkCollection
from app.models.clinical_module_run import ClinicalModuleType
from app.models.encounter import Encounter, EncounterType
from app.models.observation import ExtractionMethod, Observation
from app.models.patient import Patient, Sex
from app.models.report import ExtractionStatus, IngestionStatus, PatientMatchStatus, Report
from app.modules.differential import DifferentialCandidate, DifferentialSupport
from app.modules.entity_extraction import EntityExtractionResult, ExtractedEntity
from app.modules.report_comparison import ReportComparisonNarrative
from app.modules.soap import SOAPNote
from app.modules.summarizer import SummaryResult, SummaryType
from app.rag.deduplicator import RetrievedPassage
from app.services import clinical_modules as module_service


def _make_patient(db) -> Patient:
    patient = Patient(
        id=str(uuid.uuid4()),
        mrn=f"TEST-{uuid.uuid4().hex[:8]}",
        first_name="Iris",
        last_name="Whitfield",
        date_of_birth=date(1962, 11, 20),
        sex=Sex.FEMALE,
        synthetic=True,
    )
    db.add(patient)
    db.commit()
    return patient


def _make_report(db, patient: Patient, title: str) -> Report:
    report = Report(
        id=str(uuid.uuid4()),
        patient_id=patient.id,
        title=title,
        source_filename=f"{title}.pdf",
        stored_filename=f"{uuid.uuid4().hex}.pdf",
        file_hash=uuid.uuid4().hex,
        mime_type="application/pdf",
        file_size_bytes=1,
        ingestion_status=IngestionStatus.COMPLETED,
        extraction_status=ExtractionStatus.SUCCESS,
        patient_match_status=PatientMatchStatus.MATCHED,
        extracted_content=f'[{{"page": 1, "text": "{title} findings."}}]',
    )
    db.add(report)
    db.commit()
    return report


def _make_observation(db, patient, report, normalized_name, name, value, unit) -> Observation:
    obs = Observation(
        patient_id=patient.id,
        report_id=report.id,
        observation_name=name,
        normalized_name=normalized_name,
        value_numeric=value,
        unit=unit,
        extraction_method=ExtractionMethod.TABLE,
    )
    db.add(obs)
    db.commit()
    return obs


def _cleanup(db, patient: Patient) -> None:
    db.query(Observation).filter(Observation.patient_id == patient.id).delete()
    db.query(module_service.ClinicalModuleRun).filter(module_service.ClinicalModuleRun.patient_id == patient.id).delete()
    db.query(Encounter).filter(Encounter.patient_id == patient.id).delete()
    db.query(Report).filter(Report.patient_id == patient.id).delete()
    db.query(Patient).filter(Patient.id == patient.id).delete()
    db.commit()


# --- Deterministic numeric diff (report_comparison) --------------------------------------


def test_numeric_diff_detects_increase():
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        r1 = _make_report(db, patient, "Baseline")
        r2 = _make_report(db, patient, "Followup")
        _make_observation(db, patient, r1, "iop_od", "IOP OD", 18.0, "mmHg")
        _make_observation(db, patient, r2, "iop_od", "IOP OD", 24.0, "mmHg")

        changes = module_service._compute_numeric_changes(db, r1.id, r2.id)
        assert len(changes) == 1
        assert changes[0].direction == "increased"
        assert changes[0].previous_value == 18.0
        assert changes[0].current_value == 24.0
        assert changes[0].delta == pytest.approx(6.0)
        assert changes[0].percent_change == pytest.approx(33.33, rel=0.01)
    finally:
        _cleanup(db, patient)
        db.close()


def test_numeric_diff_detects_unchanged():
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        r1 = _make_report(db, patient, "Baseline")
        r2 = _make_report(db, patient, "Followup")
        _make_observation(db, patient, r1, "glucose", "Glucose", 95.0, "mg/dL")
        _make_observation(db, patient, r2, "glucose", "Glucose", 95.0, "mg/dL")

        changes = module_service._compute_numeric_changes(db, r1.id, r2.id)
        assert changes[0].direction == "unchanged"
        assert changes[0].delta == 0.0
    finally:
        _cleanup(db, patient)
        db.close()


def test_numeric_diff_converts_trusted_units_before_comparing():
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        r1 = _make_report(db, patient, "Baseline")
        r2 = _make_report(db, patient, "Followup")
        # 100 mg/dL glucose == 5.5509 mmol/L — a rising mmol/L reading should still
        # compare correctly against a prior mg/dL reading via the trusted conversion.
        _make_observation(db, patient, r1, "glucose", "Glucose", 100.0, "mg/dL")
        _make_observation(db, patient, r2, "glucose", "Glucose", 7.0, "mmol/L")  # ~126 mg/dL — a real rise

        changes = module_service._compute_numeric_changes(db, r1.id, r2.id)
        assert len(changes) == 1
        assert changes[0].direction == "increased"
    finally:
        _cleanup(db, patient)
        db.close()


def test_numeric_diff_skips_untrusted_unit_conversion():
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        r1 = _make_report(db, patient, "Baseline")
        r2 = _make_report(db, patient, "Followup")
        # No trusted conversion table entry exists for this made-up test/unit pair —
        # must never be compared, per spec's "convert only when a trusted conversion
        # is defined" rule (same one the lab trend engine follows).
        _make_observation(db, patient, r1, "made_up_test", "Made Up Test", 10.0, "widgets")
        _make_observation(db, patient, r2, "made_up_test", "Made Up Test", 20.0, "gadgets")

        changes = module_service._compute_numeric_changes(db, r1.id, r2.id)
        assert changes == []
    finally:
        _cleanup(db, patient)
        db.close()


def test_numeric_diff_flags_new_and_resolved_observations():
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        r1 = _make_report(db, patient, "Baseline")
        r2 = _make_report(db, patient, "Followup")
        _make_observation(db, patient, r1, "hba1c", "HbA1c", 6.1, "%")  # present only on r1
        _make_observation(db, patient, r2, "ldl", "LDL", 130.0, "mg/dL")  # present only on r2

        changes = module_service._compute_numeric_changes(db, r1.id, r2.id)
        by_name = {c.name: c for c in changes}
        assert by_name["HbA1c"].direction == "resolved"
        assert by_name["LDL"].direction == "new"
    finally:
        _cleanup(db, patient)
        db.close()


# --- Service orchestration (LLM calls mocked) ---------------------------------------------


@pytest.mark.asyncio
async def test_run_summary_persists_a_run_with_encounter_context(monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_summary(summary_type, context, settings):
        assert "Iris Whitfield" in context
        return SummaryResult(summary="Stable glaucoma follow-up.", key_points=["IOP controlled"], source_trace=["Encounter"])

    monkeypatch.setattr("app.services.clinical_modules.summarizer_module.generate_summary", fake_generate_summary)
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        encounter = Encounter(
            id=str(uuid.uuid4()),
            patient_id=patient.id,
            encounter_number=f"ENC-{uuid.uuid4().hex[:6]}",
            encounter_type=EncounterType.OUTPATIENT,
            start_datetime=datetime(2026, 8, 1, tzinfo=UTC),
            chief_complaint="Routine follow-up",
        )
        db.add(encounter)
        db.commit()

        run = await module_service.run_summary(db, get_settings(), patient, SummaryType.ENCOUNTER, encounter, None)

        assert run.module_type == ClinicalModuleType.SUMMARY
        assert run.generation_error is None
        assert "Stable glaucoma" in run.payload
    finally:
        _cleanup(db, patient)
        db.close()


@pytest.mark.asyncio
async def test_run_soap_uses_encounter_and_report_context(monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_soap(context, settings):
        assert "Encounter" in context
        return SOAPNote(subjective={"cc": "blurry vision"}, assessment=["POAG, stable"], plan=["continue latanoprost"])

    monkeypatch.setattr("app.services.clinical_modules.soap_module.generate_soap", fake_generate_soap)
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        encounter = Encounter(
            id=str(uuid.uuid4()),
            patient_id=patient.id,
            encounter_number=f"ENC-{uuid.uuid4().hex[:6]}",
            encounter_type=EncounterType.OUTPATIENT,
            start_datetime=datetime(2026, 8, 1, tzinfo=UTC),
        )
        db.add(encounter)
        db.commit()

        run = await module_service.run_soap(db, get_settings(), patient, encounter, None)
        assert run.generation_error is None
        assert "POAG" in run.payload
    finally:
        _cleanup(db, patient)
        db.close()


@pytest.mark.asyncio
async def test_run_entity_extraction_requires_report_or_encounter():
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        with pytest.raises(module_service.ClinicalModuleValidationError):
            await module_service.run_entity_extraction(db, get_settings(), patient, None, None, None)
    finally:
        _cleanup(db, patient)
        db.close()


@pytest.mark.asyncio
async def test_run_entity_extraction_from_a_report(monkeypatch: pytest.MonkeyPatch):
    async def fake_extract(source_title, text, settings):
        return EntityExtractionResult(entities=[ExtractedEntity(text="Latanoprost", category="medication")])

    monkeypatch.setattr("app.services.clinical_modules.entity_module.extract_entities", fake_extract)
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        report = _make_report(db, patient, "Consult note")
        run = await module_service.run_entity_extraction(db, get_settings(), patient, report, None, None)
        assert run.generation_error is None
        assert "Latanoprost" in run.payload
    finally:
        _cleanup(db, patient)
        db.close()


@pytest.mark.asyncio
async def test_run_differential_strips_invalid_evidence_ids(monkeypatch: pytest.MonkeyPatch):
    def fake_retrieve(db, query, settings, collection=None, patient_id=None, max_per_source=3):
        if collection == ChunkCollection.PATIENT_DOCUMENTS:
            return [
                RetrievedPassage(
                    text="Field loss noted.", score=1.0, source_title="Visual Field", source_id="report-1",
                    collection="patient_documents", page=1, section=None, chunk_ids=["c1"],
                )
            ]
        return []

    async def fake_generate_differential(patient_facts, labeled, settings):
        return DifferentialSupport(
            patient_summary="Patient with visual field loss.",
            differential=[
                DifferentialCandidate(condition="Glaucoma progression", supporting_findings=["field loss"], evidence_ids=["P1", "L9"])
            ],
            evidence_quality="Grounded in one retrieved patient document.",
        )

    monkeypatch.setattr("app.services.clinical_modules.retrieve", fake_retrieve)
    monkeypatch.setattr("app.services.clinical_modules.differential_module.generate_differential", fake_generate_differential)
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        run = await module_service.run_differential(db, get_settings(), patient, None, None)
        assert run.generation_error is None
        import json

        payload = json.loads(run.payload)
        # P1 was really offered (patient_documents hit); L9 was never offered — spec
        # §52 "never trust the model's own citation numbering," same rule as chat.
        assert payload["differential"][0]["evidence_ids"] == ["P1"]
    finally:
        _cleanup(db, patient)
        db.close()


@pytest.mark.asyncio
async def test_run_guideline_qa_abstains_honestly_when_nothing_is_retrieved(monkeypatch: pytest.MonkeyPatch):
    called = False

    async def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr("app.services.clinical_modules.retrieve", lambda *a, **k: [])
    monkeypatch.setattr("app.modules.guideline_qa.generate_complete", fail_if_called)
    db = SessionLocal()
    try:
        run = await module_service.run_guideline_qa(db, get_settings(), "What is the treatment for X?", None)
        assert called is False
        import json

        payload = json.loads(run.payload)
        assert payload["no_guideline_found"] is True
        assert "No relevant guideline" in payload["answer"]
        assert run.patient_id is None
    finally:
        db.query(module_service.ClinicalModuleRun).filter(module_service.ClinicalModuleRun.id == run.id).delete()
        db.commit()
        db.close()


@pytest.mark.asyncio
async def test_run_guideline_qa_answers_with_real_evidence(monkeypatch: pytest.MonkeyPatch):
    def fake_retrieve(db, query, settings, collection=None, patient_id=None, max_per_source=3):
        return [
            RetrievedPassage(
                text="Target IOP should be individualized.", score=1.0, source_title="ICO Guidelines",
                source_id="knowledge:ico", collection="medical_knowledge", page=12, section="POAG", chunk_ids=["c1"],
            )
        ]

    async def fake_generate_complete(messages, settings, json_format=False, temperature=None, max_output_tokens=None):
        return "Target IOP is individualized per patient [L1]."

    monkeypatch.setattr("app.services.clinical_modules.retrieve", fake_retrieve)
    monkeypatch.setattr("app.modules.guideline_qa.generate_complete", fake_generate_complete)
    db = SessionLocal()
    try:
        run = await module_service.run_guideline_qa(db, get_settings(), "What is the target IOP?", None)
        import json

        payload = json.loads(run.payload)
        assert payload["no_guideline_found"] is False
        assert "[L1]" in payload["answer"]
        assert payload["citations"][0]["source_title"] == "ICO Guidelines"
    finally:
        db.query(module_service.ClinicalModuleRun).filter(module_service.ClinicalModuleRun.id == run.id).delete()
        db.commit()
        db.close()


@pytest.mark.asyncio
async def test_run_report_comparison_combines_deterministic_and_narrative_results(monkeypatch: pytest.MonkeyPatch):
    async def fake_narrative(previous_text, current_text, numeric_changes_summary, settings):
        assert "IOP" in numeric_changes_summary
        return ReportComparisonNarrative(narrative_differences=["Optic disc cupping progressed"], limitations=[])

    monkeypatch.setattr("app.services.clinical_modules.comparison_module.generate_comparison_narrative", fake_narrative)
    monkeypatch.setattr("app.services.clinical_modules.retrieve", lambda *a, **k: [])
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        r1 = _make_report(db, patient, "Baseline")
        r2 = _make_report(db, patient, "Followup")
        _make_observation(db, patient, r1, "iop_od", "IOP OD", 16.0, "mmHg")
        _make_observation(db, patient, r2, "iop_od", "IOP OD", 21.0, "mmHg")

        run = await module_service.run_report_comparison(db, get_settings(), patient, r1, r2, None)
        import json

        payload = json.loads(run.payload)
        assert payload["numeric_changes"][0]["direction"] == "increased"
        assert payload["narrative_differences"] == ["Optic disc cupping progressed"]
    finally:
        _cleanup(db, patient)
        db.close()
