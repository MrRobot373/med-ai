"""Vision analysis service — persistence, image-to-RAG indexing, and comparison
(spec §58-61). Real DB rows and real file bytes on disk; `analyze_image`/
`compare_images`/`index_document`/`retrieve` are mocked (the slow/nondeterministic
parts), matching Phase 07/08's established mocking philosophy.
"""

from __future__ import annotations

import json
import uuid
from datetime import date

import pytest

from app.config.settings import get_settings
from app.db.session import SessionLocal
from app.ingestion.storage import reports_dir, write_file
from app.models.chunk import ChunkCollection
from app.models.patient import Patient, Sex
from app.models.report import ExtractionStatus, IngestionStatus, PatientMatchStatus, Report
from app.models.vision_analysis import VisionAnalysis, VisionAnalysisStatus
from app.services import vision as vision_service
from app.vision.analyzer import VisionComparison, VisionObservation
from tests.sample_documents import make_png_bytes

PNG_BYTES = make_png_bytes(["Fundus photo — right eye"])


def _make_patient(db) -> Patient:
    patient = Patient(
        id=str(uuid.uuid4()),
        mrn=f"TEST-{uuid.uuid4().hex[:8]}",
        first_name="Nadia",
        last_name="Okafor",
        date_of_birth=date(1969, 2, 3),
        sex=Sex.FEMALE,
        synthetic=True,
    )
    db.add(patient)
    db.commit()
    return patient


def _make_report(db, patient: Patient, mime_type: str, content: bytes, title: str = "Fundus.png") -> Report:
    settings = get_settings()
    stored_filename = f"{uuid.uuid4().hex}.bin"
    write_file(reports_dir(settings, patient.id) / stored_filename, content)
    report = Report(
        id=str(uuid.uuid4()),
        patient_id=patient.id,
        title=title,
        source_filename=title,
        stored_filename=stored_filename,
        file_hash=uuid.uuid4().hex,
        mime_type=mime_type,
        file_size_bytes=len(content),
        ingestion_status=IngestionStatus.COMPLETED,
        extraction_status=ExtractionStatus.NOT_APPLICABLE,
        patient_match_status=PatientMatchStatus.MATCHED,
    )
    db.add(report)
    db.commit()
    return report


def _cleanup(db, patient: Patient) -> None:
    db.query(VisionAnalysis).filter(
        VisionAnalysis.report_id.in_(db.query(Report.id).filter(Report.patient_id == patient.id))
    ).delete(synchronize_session=False)
    db.query(Report).filter(Report.patient_id == patient.id).delete()
    db.query(Patient).filter(Patient.id == patient.id).delete()
    db.commit()


# --- _image_bytes_for -----------------------------------------------------------------


def test_image_bytes_for_returns_raw_bytes_for_a_real_image():
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        report = _make_report(db, patient, "image/png", PNG_BYTES)
        result = vision_service._image_bytes_for(get_settings(), report)
        assert result == PNG_BYTES
    finally:
        _cleanup(db, patient)
        db.close()


def test_image_bytes_for_raises_for_non_image_mime_type():
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        report = _make_report(db, patient, "application/pdf", b"%PDF-1.4 fake", title="report.pdf")
        with pytest.raises(vision_service.NotAnalyzableError):
            vision_service._image_bytes_for(get_settings(), report)
    finally:
        _cleanup(db, patient)
        db.close()


def test_image_bytes_for_raises_for_undecodable_dicom():
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        report = _make_report(db, patient, "application/dicom", b"not a real dicom file", title="scan.dcm")
        with pytest.raises(vision_service.NotAnalyzableError):
            vision_service._image_bytes_for(get_settings(), report)
    finally:
        _cleanup(db, patient)
        db.close()


# --- run_analysis -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_analysis_stores_not_applicable_for_a_non_image_report(monkeypatch: pytest.MonkeyPatch):
    indexed = []
    monkeypatch.setattr("app.services.vision.index_document", lambda *a, **k: indexed.append(1))
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        report = _make_report(db, patient, "application/pdf", b"%PDF-1.4 fake", title="report.pdf")
        row = await vision_service.run_analysis(db, get_settings(), report)
        assert row.status == VisionAnalysisStatus.NOT_APPLICABLE
        assert row.payload is None
        assert indexed == []
    finally:
        _cleanup(db, patient)
        db.close()


@pytest.mark.asyncio
async def test_run_analysis_stores_failed_when_model_returns_none(monkeypatch: pytest.MonkeyPatch):
    async def fake_analyze(*args, **kwargs):
        return None

    monkeypatch.setattr("app.services.vision.analyze_image", fake_analyze)
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        report = _make_report(db, patient, "image/png", PNG_BYTES)
        row = await vision_service.run_analysis(db, get_settings(), report)
        assert row.status == VisionAnalysisStatus.FAILED
        assert row.analysis_error
    finally:
        _cleanup(db, patient)
        db.close()


@pytest.mark.asyncio
async def test_run_analysis_success_indexes_into_patient_vision(monkeypatch: pytest.MonkeyPatch):
    observation = VisionObservation(
        image_type="fundus photograph",
        observations=["optic disc appears normal"],
        clinical_entities=["optic disc"],
    )

    async def fake_analyze(*args, **kwargs):
        return observation

    captured = {}

    def fake_index_document(db, settings, pages, **kwargs):
        captured["pages"] = pages
        captured["kwargs"] = kwargs
        return []

    monkeypatch.setattr("app.services.vision.analyze_image", fake_analyze)
    monkeypatch.setattr("app.services.vision.index_document", fake_index_document)
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        report = _make_report(db, patient, "image/png", PNG_BYTES)
        row = await vision_service.run_analysis(db, get_settings(), report)

        assert row.status == VisionAnalysisStatus.SUCCESS
        assert json.loads(row.payload)["observations"] == ["optic disc appears normal"]
        assert captured["kwargs"]["collection"] == ChunkCollection.PATIENT_VISION
        assert captured["kwargs"]["patient_id"] == patient.id
        assert captured["kwargs"]["report_id"] == report.id
        assert "optic disc appears normal" in captured["pages"][0]["text"]
    finally:
        _cleanup(db, patient)
        db.close()


@pytest.mark.asyncio
async def test_run_analysis_skips_indexing_for_a_mismatched_report(monkeypatch: pytest.MonkeyPatch):
    observation = VisionObservation(image_type="photo", observations=["a finding"])

    async def fake_analyze(*args, **kwargs):
        return observation

    indexed = []
    monkeypatch.setattr("app.services.vision.analyze_image", fake_analyze)
    monkeypatch.setattr("app.services.vision.index_document", lambda *a, **k: indexed.append(1))
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        report = _make_report(db, patient, "image/png", PNG_BYTES)
        report.patient_match_status = PatientMatchStatus.MISMATCH
        db.commit()

        row = await vision_service.run_analysis(db, get_settings(), report)

        # The analysis result itself is still recorded honestly — only indexing
        # (which would make it searchable) is withheld while identity is unresolved.
        assert row.status == VisionAnalysisStatus.SUCCESS
        assert indexed == []
    finally:
        _cleanup(db, patient)
        db.close()


def test_reindex_if_present_reindexes_without_recalling_the_model(monkeypatch: pytest.MonkeyPatch):
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("analyze_image should not be called by reindex_if_present")

    indexed = []
    monkeypatch.setattr("app.services.vision.analyze_image", fail_if_called)
    monkeypatch.setattr("app.services.vision.index_document", lambda *a, **k: indexed.append(1))
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        report = _make_report(db, patient, "image/png", PNG_BYTES)
        observation = VisionObservation(image_type="photo", observations=["a finding"])
        db.add(
            VisionAnalysis(
                report_id=report.id, status=VisionAnalysisStatus.SUCCESS, payload=observation.model_dump_json()
            )
        )
        db.commit()

        vision_service.reindex_if_present(db, get_settings(), report)
        assert indexed == [1]
    finally:
        _cleanup(db, patient)
        db.close()


def test_reindex_if_present_does_nothing_when_no_successful_analysis_exists():
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        report = _make_report(db, patient, "image/png", PNG_BYTES)
        vision_service.reindex_if_present(db, get_settings(), report)  # no row at all — should not raise
    finally:
        _cleanup(db, patient)
        db.close()


# --- compare_reports --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compare_reports_rejects_different_patients():
    db = SessionLocal()
    patient_a = patient_b = None
    try:
        patient_a = _make_patient(db)
        patient_b = _make_patient(db)
        report_a = _make_report(db, patient_a, "image/png", PNG_BYTES)
        report_b = _make_report(db, patient_b, "image/png", PNG_BYTES)

        with pytest.raises(vision_service.ReportsNotComparableError):
            await vision_service.compare_reports(db, get_settings(), report_a, report_b)
    finally:
        if patient_a:
            _cleanup(db, patient_a)
        if patient_b:
            _cleanup(db, patient_b)
        db.close()


@pytest.mark.asyncio
async def test_compare_reports_returns_result_and_retrieved_evidence(monkeypatch: pytest.MonkeyPatch):
    from app.rag.deduplicator import RetrievedPassage

    comparison = VisionComparison(
        previous_findings=["baseline"], current_findings=["progression"], differences=["larger cup-to-disc ratio"]
    )

    async def fake_compare(*args, **kwargs):
        return comparison

    def fake_retrieve(db, query, settings, collection=None, patient_id=None, max_per_source=3):
        assert "larger cup-to-disc ratio" in query
        return [
            RetrievedPassage(
                text="Guideline text about cup-to-disc ratio progression.",
                score=1.0,
                source_title="ICO Guidelines",
                source_id="knowledge:ico",
                collection="medical_knowledge",
                page=5,
                section="Glaucoma",
                chunk_ids=["c1"],
            )
        ]

    monkeypatch.setattr("app.services.vision.compare_images", fake_compare)
    monkeypatch.setattr("app.services.vision.retrieve", fake_retrieve)
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        previous_report = _make_report(db, patient, "image/png", PNG_BYTES, title="Previous.png")
        current_report = _make_report(db, patient, "image/png", PNG_BYTES, title="Current.png")

        result, evidence = await vision_service.compare_reports(db, get_settings(), previous_report, current_report)

        assert result.differences == ["larger cup-to-disc ratio"]
        assert len(evidence) == 1
        assert evidence[0].source_title == "ICO Guidelines"
    finally:
        _cleanup(db, patient)
        db.close()


@pytest.mark.asyncio
async def test_compare_reports_raises_when_model_returns_none(monkeypatch: pytest.MonkeyPatch):
    async def fake_compare(*args, **kwargs):
        return None

    monkeypatch.setattr("app.services.vision.compare_images", fake_compare)
    db = SessionLocal()
    try:
        patient = _make_patient(db)
        previous_report = _make_report(db, patient, "image/png", PNG_BYTES, title="Previous.png")
        current_report = _make_report(db, patient, "image/png", PNG_BYTES, title="Current.png")

        with pytest.raises(vision_service.ReportsNotComparableError):
            await vision_service.compare_reports(db, get_settings(), previous_report, current_report)
    finally:
        _cleanup(db, patient)
        db.close()
