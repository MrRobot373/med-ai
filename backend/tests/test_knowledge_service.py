"""Knowledge Administration service (Phase 12) — versioning, activation, and archive
semantics. `index_document`/`delete_indexed_source` are mocked (see conftest.py) the
same way every other module's indexing calls are; real embedding/Qdrant behavior is
already covered by test_rag_pipeline.py."""

from __future__ import annotations

import pytest

from app.config.settings import get_settings
from app.db.session import SessionLocal
from app.models.web_cache import AuthorityTier
from app.services import knowledge as knowledge_service
from tests.sample_documents import make_pdf_bytes

SETTINGS = get_settings()


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _pdf_bytes(text: str = "Guideline content about glaucoma management.") -> bytes:
    return make_pdf_bytes([text])


def test_create_and_list_documents_excludes_archived_by_default(db):
    doc = knowledge_service.create_document(db, "ICO Guidelines", "ICO", "Glaucoma", AuthorityTier.A, "glaucoma,surgical", None)
    assert doc.id
    assert doc.archived is False

    listed = knowledge_service.list_documents(db)
    assert any(d.id == doc.id for d in listed)

    knowledge_service.archive_document(db, SETTINGS, doc)
    assert not any(d.id == doc.id for d in knowledge_service.list_documents(db))
    assert any(d.id == doc.id for d in knowledge_service.list_documents(db, include_archived=True))


def test_update_document_only_changes_supplied_fields(db):
    doc = knowledge_service.create_document(db, "Original Title", "Original Source", None, AuthorityTier.D, None, None)
    updated = knowledge_service.update_document(db, doc, title="New Title")
    assert updated.title == "New Title"
    assert updated.source == "Original Source"  # untouched


def test_upload_version_increments_version_number(db):
    doc = knowledge_service.create_document(db, "Doc", None, None, AuthorityTier.D, None, None)
    v1 = knowledge_service.upload_version(db, SETTINGS, doc, "guideline.pdf", _pdf_bytes("This is the first edition of the guideline with enough text to skip OCR."), None, None, None)
    v2 = knowledge_service.upload_version(db, SETTINGS, doc, "guideline_v2.pdf", _pdf_bytes("This is the second edition of the guideline with enough text to skip OCR."), None, None, None)
    assert v1.version_number == 1
    assert v2.version_number == 2
    assert v1.ingestion_status.value == "queued"


def test_upload_version_rejects_disallowed_extension(db):
    doc = knowledge_service.create_document(db, "Doc", None, None, AuthorityTier.D, None, None)
    with pytest.raises(knowledge_service.UploadValidationError):
        knowledge_service.upload_version(db, SETTINGS, doc, "scan.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20, None, None, None)


def test_upload_version_rejects_duplicate_content_within_same_document(db):
    doc = knowledge_service.create_document(db, "Doc", None, None, AuthorityTier.D, None, None)
    content = _pdf_bytes("This is identical content repeated for the duplicate-detection test case here.")
    knowledge_service.upload_version(db, SETTINGS, doc, "a.pdf", content, None, None, None)
    with pytest.raises(knowledge_service.DuplicateVersionError):
        knowledge_service.upload_version(db, SETTINGS, doc, "a_again.pdf", content, None, None, None)


def test_activate_version_marks_active_and_deactivates_sibling(db):
    doc = knowledge_service.create_document(db, "Doc", None, None, AuthorityTier.D, None, None)
    v1 = knowledge_service.upload_version(db, SETTINGS, doc, "v1.pdf", _pdf_bytes("This is edition one of the guideline document with enough text to skip OCR."), None, None, None)
    v2 = knowledge_service.upload_version(db, SETTINGS, doc, "v2.pdf", _pdf_bytes("This is edition two of the guideline document with enough text to skip OCR."), None, None, None)

    knowledge_service.activate_version(db, SETTINGS, v1)
    db.refresh(v1)
    assert v1.is_active is True
    assert v1.ingestion_status.value == "completed"

    knowledge_service.activate_version(db, SETTINGS, v2)
    db.refresh(v1)
    db.refresh(v2)
    assert v2.is_active is True
    assert v1.is_active is False  # deactivated the moment v2 became active
    assert v1.chunk_count == 0


def test_activate_version_is_idempotent(db):
    doc = knowledge_service.create_document(db, "Doc", None, None, AuthorityTier.D, None, None)
    v1 = knowledge_service.upload_version(db, SETTINGS, doc, "v1.pdf", _pdf_bytes("This is the only edition of the guideline document with enough text to skip OCR."), None, None, None)
    knowledge_service.activate_version(db, SETTINGS, v1)
    knowledge_service.activate_version(db, SETTINGS, v1)  # calling again must not error or duplicate anything
    db.refresh(v1)
    assert v1.is_active is True


def test_archive_document_deindexes_the_active_version(db):
    doc = knowledge_service.create_document(db, "Doc", None, None, AuthorityTier.D, None, None)
    v1 = knowledge_service.upload_version(db, SETTINGS, doc, "v1.pdf", _pdf_bytes("This document has plenty of body text content so OCR is never triggered."), None, None, None)
    knowledge_service.activate_version(db, SETTINGS, v1)

    archived = knowledge_service.archive_document(db, SETTINGS, doc)
    db.refresh(v1)
    assert archived.archived is True
    assert v1.is_active is False
    assert v1.chunk_count == 0


def test_run_activation_task_marks_failed_on_a_genuinely_broken_file(db):
    doc = knowledge_service.create_document(db, "Doc", None, None, AuthorityTier.D, None, None)
    # Passes the extension/magic-byte check but isn't a real parseable PDF — pymupdf
    # raises past the header sniff, exercising the failure path end to end.
    version = knowledge_service.upload_version(db, SETTINGS, doc, "broken.pdf", b"%PDF-1.4 not a real pdf structure", None, None, None)

    knowledge_service.run_activation_task(version.id, SETTINGS)

    db.refresh(version)
    assert version.ingestion_status.value == "failed"
    assert version.ingestion_error
    assert version.is_active is False
