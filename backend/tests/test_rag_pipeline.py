"""RAG retrieval pipeline — spec §43/§44/§46/§47, and critically spec §14/§16:
"There must be automated tests proving that patient A's chunks can never appear in
patient B's context."

Embedding/reranking are mocked (fast, deterministic) — real model inference is a
separate, slow, live-verified concern (see docs/architecture.md's Phase 07 section);
these tests exist to prove the *orchestration* is correct: patient filtering is
actually applied, chunks route to the right collection, fusion/dedup behave — not to
benchmark the model. Real Qdrant (already running for this project) IS used, since
that's the actual patient-isolation enforcement point (the Qdrant filter), not
something safe to fake away in the one test that matters most.

Mocked vectors are 1024-dimensional to match the real configured embedding model's
dimension (Qwen3-Embedding-0.6B) — so these tests interoperate safely with whatever
collections already exist in the shared dev Qdrant instance instead of risking a
dimension mismatch. Every chunk (and the synthetic Patient/Report rows `Chunk.patient_id`
/`report_id` foreign-key to) this file creates is deleted in a `finally` block.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date

import pytest

from app.config.settings import get_settings
from app.db.session import SessionLocal
from app.models.chunk import Chunk, ChunkCollection
from app.models.patient import Patient, Sex
from app.models.report import ExtractionStatus, IngestionStatus, PatientMatchStatus, Report
from app.rag import dense_retriever, indexing
from app.rag.pipeline import retrieve

_FAKE_DIM = 1024


def _fake_vector(text: str) -> list[float]:
    """Deterministic pseudo-random unit-ish vector derived from the text's hash — same
    text always gets the same vector (so dense search behaves consistently across a
    test), different texts get different vectors, without loading any real model."""
    seed = int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**32)
    values = []
    state = seed
    for _ in range(_FAKE_DIM):
        state = (state * 1103515245 + 12345) % (2**31)
        values.append((state / (2**31)) - 0.5)
    return values


@pytest.fixture(autouse=True)
def _mock_embeddings(monkeypatch: pytest.MonkeyPatch):
    from app.rag.embeddings import EmbeddingResult

    def fake_embed_documents(texts, settings):
        return EmbeddingResult(vectors=[_fake_vector(t) for t in texts], dimension=_FAKE_DIM)

    def fake_embed_query(text, settings):
        return _fake_vector(text)

    monkeypatch.setattr("app.rag.indexing.embed_documents", fake_embed_documents)
    monkeypatch.setattr("app.rag.dense_retriever.embed_query", fake_embed_query)


def _make_patient_and_report(db) -> tuple[str, str]:
    """Chunk.patient_id/report_id are real foreign keys (spec §8 "enable appropriate
    ... foreign-key enforcement") — a synthetic UUID with no matching row fails the
    insert, so isolation tests need real (if minimal) Patient/Report rows to hang
    their chunks off, same as the app itself would have."""
    patient = Patient(
        id=str(uuid.uuid4()),
        mrn=f"TEST-{uuid.uuid4().hex[:8]}",
        first_name="Test",
        last_name="Patient",
        date_of_birth=date(1970, 1, 1),
        sex=Sex.UNKNOWN,
        synthetic=True,
    )
    db.add(patient)
    db.commit()

    report = Report(
        id=str(uuid.uuid4()),
        patient_id=patient.id,
        title="Test Report",
        source_filename="test.pdf",
        stored_filename=f"{uuid.uuid4().hex}.pdf",
        file_hash=uuid.uuid4().hex,
        mime_type="application/pdf",
        file_size_bytes=1,
        ingestion_status=IngestionStatus.COMPLETED,
        extraction_status=ExtractionStatus.SUCCESS,
        patient_match_status=PatientMatchStatus.MATCHED,
    )
    db.add(report)
    db.commit()
    return patient.id, report.id


def _cleanup(db, settings, patient_id: str, report_id: str) -> None:
    indexing.delete_indexed_source(db, settings, ChunkCollection.PATIENT_DOCUMENTS, report_id=report_id)
    db.query(Report).filter(Report.id == report_id).delete()
    db.query(Patient).filter(Patient.id == patient_id).delete()
    db.commit()


def _index_fake_report(db, settings, patient_id: str, report_id: str, text: str, title: str) -> None:
    indexing.index_document(
        db,
        settings,
        pages=[{"page": 1, "text": text}],
        collection=ChunkCollection.PATIENT_DOCUMENTS,
        source_title=title,
        patient_id=patient_id,
        report_id=report_id,
    )


def test_patient_a_chunks_never_appear_in_patient_bs_context():
    """The spec §14 test, verbatim: patient A's chunks can never appear in patient
    B's retrieval results, even when the query text is built directly from patient
    A's own real clinical content (the worst case — maximal semantic/lexical
    relevance, deliberately trying to leak across the boundary)."""
    settings = get_settings()
    db = SessionLocal()
    patient_a, report_a = _make_patient_and_report(db)
    patient_b, report_b = _make_patient_and_report(db)

    try:
        _index_fake_report(
            db, settings, patient_a, report_a,
            "Patient A current medications: Latanoprost 0.005% nightly both eyes, Timolol 0.5% twice daily.",
            "Patient A Consult",
        )
        _index_fake_report(
            db, settings, patient_b, report_b,
            "Patient B history: no ocular medications, cataract surgery pending right eye.",
            "Patient B Consult",
        )

        # Query built from patient A's own content, run while scoped to patient B.
        hits = dense_retriever.dense_search(
            "Latanoprost 0.005% nightly both eyes Timolol 0.5% twice daily",
            ChunkCollection.PATIENT_DOCUMENTS,
            settings,
            patient_id=patient_b,
        )
        returned_ids = {hit.chunk_id for hit in hits}

        leaked = db.query(Chunk).filter(Chunk.id.in_(returned_ids), Chunk.patient_id == patient_a).count()
        assert leaked == 0, "Patient A's chunks leaked into a patient-B-scoped query"

        # And the full retrieve() pipeline (fusion/rerank/dedup included) too.
        passages = retrieve(db, "Latanoprost Timolol", settings, patient_id=patient_b)
        for passage in passages:
            for chunk_id in passage.chunk_ids:
                chunk = db.get(Chunk, chunk_id)
                assert chunk.patient_id != patient_a
    finally:
        _cleanup(db, settings, patient_a, report_a)
        _cleanup(db, settings, patient_b, report_b)
        db.close()


def test_patient_documents_search_requires_patient_id():
    settings = get_settings()
    with pytest.raises(ValueError, match="patient_id is required"):
        dense_retriever.dense_search("anything", ChunkCollection.PATIENT_DOCUMENTS, settings, patient_id=None)


def test_indexed_chunks_are_retrievable_for_the_correct_patient():
    settings = get_settings()
    db = SessionLocal()
    patient_id, report_id = _make_patient_and_report(db)
    try:
        _index_fake_report(
            db, settings, patient_id, report_id,
            "Central subfield thickness 340 microns, diabetic macular edema unchanged.",
            "OCT Report",
        )
        hits = dense_retriever.dense_search(
            "diabetic macular edema", ChunkCollection.PATIENT_DOCUMENTS, settings, patient_id=patient_id
        )
        assert len(hits) > 0
    finally:
        _cleanup(db, settings, patient_id, report_id)
        db.close()


def test_reindexing_a_report_does_not_accumulate_duplicate_points():
    settings = get_settings()
    db = SessionLocal()
    patient_id, report_id = _make_patient_and_report(db)
    try:
        _index_fake_report(db, settings, patient_id, report_id, "Some clinical text here.", "Note v1")
        _index_fake_report(db, settings, patient_id, report_id, "Some clinical text here, revised.", "Note v2")

        rows = db.query(Chunk).filter(Chunk.report_id == report_id).all()
        assert len(rows) == 1  # not 2 — the first index's chunk was replaced, not left behind
        assert "revised" in rows[0].text
    finally:
        _cleanup(db, settings, patient_id, report_id)
        db.close()
