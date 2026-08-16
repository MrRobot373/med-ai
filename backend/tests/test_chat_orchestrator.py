"""Chat orchestration — spec §43/§48. Retrieval and grounding-validation LLM calls
are mocked (fast, deterministic); everything else (classification, scope-based
context assembly, abstention, citation/grounding wiring) is real.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest

from app.chat import orchestrator
from app.chat.context_builder import LabeledEvidence
from app.chat.grounding_validator import GroundingClaim, GroundingResult
from app.config.settings import get_settings
from app.db.session import SessionLocal
from app.models.chunk import ChunkCollection
from app.models.conversation import Conversation, ConversationScope
from app.models.encounter import Encounter, EncounterType
from app.models.patient import Patient, Sex
from app.models.report import ExtractionStatus, IngestionStatus, PatientMatchStatus, Report
from app.models.vision_analysis import VisionAnalysis, VisionAnalysisStatus
from app.rag.deduplicator import RetrievedPassage
from app.vision.analyzer import VisionObservation


def _make_patient(db) -> Patient:
    patient = Patient(
        id=str(uuid.uuid4()),
        mrn=f"TEST-{uuid.uuid4().hex[:8]}",
        first_name="Margaret",
        last_name="Wallace",
        date_of_birth=date(1953, 4, 12),
        sex=Sex.FEMALE,
        synthetic=True,
    )
    db.add(patient)
    db.commit()
    return patient


def _fake_passage(collection: str, source_id: str, label_hint: str) -> RetrievedPassage:
    return RetrievedPassage(
        text=f"Evidence text for {label_hint}",
        score=1.5,
        source_title=f"{label_hint} Source",
        source_id=source_id,
        collection=collection,
        page=1,
        section=None,
        chunk_ids=[str(uuid.uuid4())],
    )


def test_general_conversation_skips_retrieval_entirely(monkeypatch: pytest.MonkeyPatch):
    called = False

    def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr("app.chat.orchestrator.retrieve", fail_if_called)
    settings = get_settings()
    db = SessionLocal()
    try:
        conversation = Conversation(id=str(uuid.uuid4()), user_id="u1", scope=ConversationScope.GENERAL)
        prepared = orchestrator.prepare_turn(db, settings, conversation, "hi", [])
        assert prepared.task_classification == "general_conversation"
        assert prepared.abstain is False
        assert called is False
        # System + user message only — no evidence section was constructed.
        assert len(prepared.messages) == 2
        assert prepared.messages[-1].content == "hi"
    finally:
        db.close()


def test_current_patient_scope_pulls_patient_knowledge_and_vision_evidence(monkeypatch: pytest.MonkeyPatch):
    def fake_retrieve(db, query, settings, collection=None, patient_id=None, max_per_source=3):
        if collection == ChunkCollection.PATIENT_DOCUMENTS:
            return [_fake_passage("patient_documents", "report-1", "Patient")]
        if collection == ChunkCollection.PATIENT_VISION:
            return [_fake_passage("patient_vision", "report-2", "Vision")]
        return [_fake_passage("medical_knowledge", "knowledge-1", "Guideline")]

    monkeypatch.setattr("app.chat.orchestrator.retrieve", fake_retrieve)
    settings = get_settings()
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        conversation = Conversation(
            id=str(uuid.uuid4()), user_id="u1", scope=ConversationScope.CURRENT_PATIENT, patient_id=patient.id
        )
        prepared = orchestrator.prepare_turn(db, settings, conversation, "What medications is she on?", [])

        assert prepared.abstain is False
        assert [e.label for e in prepared.labeled_evidence] == ["P1", "L1", "V1"]
        user_turn = prepared.messages[-1].content
        assert "CURRENT PATIENT FACTS" in user_turn
        assert "Margaret Wallace" in user_turn
        assert "RETRIEVED LOCAL CLINICAL EVIDENCE" in user_turn
        assert "[P1]" in user_turn
        assert "[L1]" in user_turn
        assert "[V1]" in user_turn
    finally:
        db.query(Patient).filter(Patient.id == patient.id).delete()
        db.commit()
        db.close()


def test_selected_report_scope_only_searches_patient_documents(monkeypatch: pytest.MonkeyPatch):
    calls = []

    def fake_retrieve(db, query, settings, collection=None, patient_id=None, max_per_source=3):
        calls.append(collection.value)
        return [_fake_passage("patient_documents", "report-1", "Patient")] if patient_id else []

    monkeypatch.setattr("app.chat.orchestrator.retrieve", fake_retrieve)
    settings = get_settings()
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        report = Report(
            id=str(uuid.uuid4()),
            patient_id=patient.id,
            title="OCT Report",
            source_filename="oct.pdf",
            stored_filename=f"{uuid.uuid4().hex}.pdf",
            file_hash=uuid.uuid4().hex,
            mime_type="application/pdf",
            file_size_bytes=1,
            ingestion_status=IngestionStatus.COMPLETED,
            extraction_status=ExtractionStatus.SUCCESS,
            patient_match_status=PatientMatchStatus.MATCHED,
            extracted_content='[{"page": 1, "text": "Central subfield thickness 340 microns."}]',
        )
        db.add(report)
        db.commit()

        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id="u1",
            scope=ConversationScope.SELECTED_REPORT,
            patient_id=patient.id,
            selected_report_id=report.id,
        )
        prepared = orchestrator.prepare_turn(db, settings, conversation, "Summarize this report", [])

        assert "medical_knowledge" not in calls  # SELECTED_REPORT deliberately doesn't broaden to the whole KB
        assert "patient_vision" not in calls  # nor to the patient's whole image corpus — see same rationale
        user_turn = prepared.messages[-1].content
        assert "SELECTED REPORT FACTS" in user_turn
        assert "Central subfield thickness" in user_turn
    finally:
        db.query(Report).filter(Report.patient_id == patient.id).delete()
        db.query(Patient).filter(Patient.id == patient.id).delete()
        db.commit()
        db.close()


def test_selected_report_scope_includes_its_own_vision_analysis_in_report_facts(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.chat.orchestrator.retrieve", lambda *a, **k: [])
    settings = get_settings()
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        report = Report(
            id=str(uuid.uuid4()),
            patient_id=patient.id,
            title="Fundus.png",
            source_filename="fundus.png",
            stored_filename=f"{uuid.uuid4().hex}.png",
            file_hash=uuid.uuid4().hex,
            mime_type="image/png",
            file_size_bytes=1,
            ingestion_status=IngestionStatus.COMPLETED,
            extraction_status=ExtractionStatus.NOT_APPLICABLE,
            patient_match_status=PatientMatchStatus.MATCHED,
        )
        db.add(report)
        db.commit()
        observation = VisionObservation(
            image_type="fundus photograph", observations=["disc margins well-defined"]
        )
        db.add(
            VisionAnalysis(
                report_id=report.id, status=VisionAnalysisStatus.SUCCESS, payload=observation.model_dump_json()
            )
        )
        db.commit()

        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id="u1",
            scope=ConversationScope.SELECTED_REPORT,
            patient_id=patient.id,
            selected_report_id=report.id,
        )
        prepared = orchestrator.prepare_turn(db, settings, conversation, "What does this image show?", [])

        user_turn = prepared.messages[-1].content
        assert "Vision analysis" in user_turn
        assert "disc margins well-defined" in user_turn
    finally:
        db.query(VisionAnalysis).filter(VisionAnalysis.report_id == report.id).delete()
        db.query(Report).filter(Report.patient_id == patient.id).delete()
        db.query(Patient).filter(Patient.id == patient.id).delete()
        db.commit()
        db.close()


def test_encounter_scope_includes_encounter_facts(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.chat.orchestrator.retrieve", lambda *a, **k: [])
    settings = get_settings()
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        encounter = Encounter(
            id=str(uuid.uuid4()),
            patient_id=patient.id,
            encounter_number=f"ENC-{uuid.uuid4().hex[:6]}",
            encounter_type=EncounterType.OUTPATIENT,
            start_datetime=datetime(2026, 8, 1, tzinfo=UTC),
            chief_complaint="Glare while driving at night",
        )
        db.add(encounter)
        db.commit()

        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id="u1",
            scope=ConversationScope.CURRENT_ENCOUNTER,
            patient_id=patient.id,
            encounter_id=encounter.id,
        )
        prepared = orchestrator.prepare_turn(db, settings, conversation, "What was the chief complaint?", [])
        user_turn = prepared.messages[-1].content
        assert "CURRENT ENCOUNTER FACTS" in user_turn
        assert "Glare while driving at night" in user_turn
    finally:
        db.query(Encounter).filter(Encounter.patient_id == patient.id).delete()
        db.query(Patient).filter(Patient.id == patient.id).delete()
        db.commit()
        db.close()


def test_abstains_when_nothing_at_all_is_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.chat.orchestrator.retrieve", lambda *a, **k: [])
    settings = get_settings()
    db = SessionLocal()
    try:
        conversation = Conversation(id=str(uuid.uuid4()), user_id="u1", scope=ConversationScope.LOCAL_KNOWLEDGE_ONLY)
        prepared = orchestrator.prepare_turn(db, settings, conversation, "What is the treatment for X?", [])
        assert prepared.abstain is True
        assert prepared.messages == []
    finally:
        db.close()


def test_does_not_abstain_when_structured_facts_exist_even_without_retrieval_hits(monkeypatch: pytest.MonkeyPatch):
    # A patient exists (real structured facts available) even though free-text
    # retrieval found nothing — should NOT abstain, since e.g. "what conditions does
    # this patient have?" is fully answerable from structured facts alone.
    monkeypatch.setattr("app.chat.orchestrator.retrieve", lambda *a, **k: [])
    settings = get_settings()
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        conversation = Conversation(
            id=str(uuid.uuid4()), user_id="u1", scope=ConversationScope.CURRENT_PATIENT, patient_id=patient.id
        )
        prepared = orchestrator.prepare_turn(db, settings, conversation, "What conditions does she have?", [])
        assert prepared.abstain is False
    finally:
        db.query(Patient).filter(Patient.id == patient.id).delete()
        db.commit()
        db.close()


@pytest.mark.asyncio
async def test_finalize_turn_strips_invalid_citations_and_scores_quality(monkeypatch: pytest.MonkeyPatch):
    settings = get_settings()
    labeled = [LabeledEvidence(label="P1", passage=_fake_passage("patient_documents", "report-1", "Patient"))]

    async def fake_grounding(answer_text, evidence, settings):
        return GroundingResult(claims=[GroundingClaim(claim="x", cited_labels=["P1"], status="supported")])

    monkeypatch.setattr("app.chat.orchestrator.validate_grounding", fake_grounding)

    result = await orchestrator.finalize_turn("Latanoprost is prescribed [P1] and had surgery in 2020 [P9].", labeled, settings)

    assert "[P9]" not in result.answer_text
    assert "[P1]" in result.answer_text
    assert len(result.citations) == 1
    assert result.grounding is not None
    assert result.grounding.claims[0].status == "supported"


@pytest.mark.asyncio
async def test_finalize_turn_skips_grounding_when_nothing_was_cited(monkeypatch: pytest.MonkeyPatch):
    settings = get_settings()
    called = False

    async def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr("app.chat.orchestrator.validate_grounding", fail_if_called)
    result = await orchestrator.finalize_turn("A generic answer with no citations at all.", [], settings)
    assert called is False
    assert result.grounding is None
