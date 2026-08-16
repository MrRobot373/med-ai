"""Knowledge Administration service (Phase 12, spec's Knowledge Administration
section): upload, metadata, versions, active documents, reindex, archive, ingestion
monitoring — the admin-facing counterpart to `scripts/ingest_knowledge.py`'s one-shot
seeding script, now with real per-document/version tracking instead of a bare Qdrant
upsert.

Versioning model: exactly one `KnowledgeDocumentVersion` per document is ever
`is_active` at a time. `activate_version()` is the single place that changes what's
retrievable — it (re)indexes the target version's chunks (idempotent: `index_document`
deletes any existing chunks for that file_hash first) and deindexes+deactivates
whichever version was previously active, so uploading a new version, rolling back to
an older one, and recovering a FAILED version through the same "activate" call all
share one code path rather than three slightly different ones.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.config.settings import Settings
from app.db.session import SessionLocal
from app.ingestion import docx as docx_parser
from app.ingestion import ocr, pdf, validators, xlsx
from app.ingestion.storage import (
    delete_file,
    generate_stored_filename,
    knowledge_dir,
    sha256_hex,
    write_file,
)
from app.logging import get_logger
from app.models.chunk import ChunkCollection
from app.models.knowledge_document import KnowledgeDocument, KnowledgeDocumentVersion
from app.models.report import IngestionStatus
from app.models.web_cache import AuthorityTier
from app.rag.indexing import delete_indexed_source, index_document

logger = get_logger(__name__)

# Reference documents only — not the broader set Reports accepts (images/DICOM don't
# apply to a curated knowledge base of guidelines/protocols/references).
_ALLOWED_EXTENSIONS = frozenset({".pdf", ".docx", ".xlsx"})


class UploadValidationError(Exception):
    pass


class DuplicateVersionError(Exception):
    def __init__(self, existing: KnowledgeDocumentVersion):
        self.existing = existing
        super().__init__("An identical file has already been uploaded as a version of this document")


# --- Documents -----------------------------------------------------------------


def create_document(
    db: DbSession,
    title: str,
    source: str | None,
    specialty: str | None,
    authority_tier: AuthorityTier,
    tags: str | None,
    created_by: str | None,
) -> KnowledgeDocument:
    document = KnowledgeDocument(
        title=title, source=source, specialty=specialty, authority_tier=authority_tier, tags=tags, created_by=created_by
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def get_document(db: DbSession, document_id: str) -> KnowledgeDocument | None:
    return db.get(KnowledgeDocument, document_id)


def list_documents(db: DbSession, include_archived: bool = False, search: str | None = None) -> list[KnowledgeDocument]:
    stmt = select(KnowledgeDocument)
    if not include_archived:
        stmt = stmt.where(KnowledgeDocument.archived.is_(False))
    if search:
        stmt = stmt.where(KnowledgeDocument.title.ilike(f"%{search}%"))
    stmt = stmt.order_by(KnowledgeDocument.title)
    return list(db.scalars(stmt))


def update_document(
    db: DbSession,
    document: KnowledgeDocument,
    title: str | None = None,
    source: str | None = None,
    specialty: str | None = None,
    authority_tier: AuthorityTier | None = None,
    tags: str | None = None,
) -> KnowledgeDocument:
    if title is not None:
        document.title = title
    if source is not None:
        document.source = source
    if specialty is not None:
        document.specialty = specialty
    if authority_tier is not None:
        document.authority_tier = authority_tier
    if tags is not None:
        document.tags = tags
    db.commit()
    db.refresh(document)
    return document


def archive_document(db: DbSession, settings: Settings, document: KnowledgeDocument) -> KnowledgeDocument:
    """Deindexes whichever version is currently active and marks the document
    archived — mirrors `Report.archived`'s soft-delete-only convention (spec's data
    model lists "archive," never "delete," as the terminal admin action). The file(s)
    and version history stay on disk/in SQLite for audit purposes; only retrievability
    is revoked."""
    for version in list_versions(db, document.id):
        if version.is_active:
            try:
                delete_indexed_source(db, settings, ChunkCollection.MEDICAL_KNOWLEDGE, file_hash=version.file_hash)
            except Exception:
                logger.warning("Failed to deindex archived document_id=%s", document.id, exc_info=True)
            version.is_active = False
            version.chunk_count = 0
    document.archived = True
    db.commit()
    db.refresh(document)
    return document


# --- Versions --------------------------------------------------------------------


def list_versions(db: DbSession, document_id: str) -> list[KnowledgeDocumentVersion]:
    stmt = (
        select(KnowledgeDocumentVersion)
        .where(KnowledgeDocumentVersion.document_id == document_id)
        .order_by(KnowledgeDocumentVersion.version_number.desc())
    )
    return list(db.scalars(stmt))


def get_version(db: DbSession, version_id: str) -> KnowledgeDocumentVersion | None:
    return db.get(KnowledgeDocumentVersion, version_id)


def upload_version(
    db: DbSession,
    settings: Settings,
    document: KnowledgeDocument,
    filename: str,
    content: bytes,
    effective_date: date | None,
    review_date: date | None,
    created_by: str | None,
) -> KnowledgeDocumentVersion:
    result = validators.validate_upload(
        filename, content[: validators.MAGIC_SNIFF_BYTES], len(content), settings.upload_max_mb
    )
    if not result.ok:
        raise UploadValidationError(result.error)
    if result.extension not in _ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            f"Knowledge documents only accept PDF/DOCX/XLSX files (got '{result.extension}')"
        )

    file_hash = sha256_hex(content)
    existing = db.scalar(
        select(KnowledgeDocumentVersion).where(
            KnowledgeDocumentVersion.document_id == document.id,
            KnowledgeDocumentVersion.file_hash == file_hash,
        )
    )
    if existing:
        raise DuplicateVersionError(existing)

    display_name = validators.sanitize_display_filename(filename)
    stored_filename = generate_stored_filename(result.extension)
    write_file(knowledge_dir(settings) / stored_filename, content)

    next_number = (
        db.scalar(
            select(func.max(KnowledgeDocumentVersion.version_number)).where(
                KnowledgeDocumentVersion.document_id == document.id
            )
        )
        or 0
    ) + 1

    version = KnowledgeDocumentVersion(
        document_id=document.id,
        version_number=next_number,
        source_filename=display_name,
        stored_filename=stored_filename,
        file_hash=file_hash,
        mime_type=result.mime_type,
        file_size_bytes=len(content),
        effective_date=effective_date,
        review_date=review_date,
        ingestion_status=IngestionStatus.QUEUED,
        created_by=created_by,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def file_path_for(settings: Settings, version: KnowledgeDocumentVersion):
    return knowledge_dir(settings) / version.stored_filename


def delete_version_file(settings: Settings, version: KnowledgeDocumentVersion) -> None:
    delete_file(file_path_for(settings, version))


# --- Ingestion / activation --------------------------------------------------------


def _extract_pages(content: bytes, mime_type: str, settings: Settings) -> list[dict]:
    """Deliberately simpler than `ingestion/pipeline.py`'s report extraction — no
    identity checking, lab extraction, or vision analysis apply to a reference
    document. OCR fallback is kept (scanned guideline PDFs are common)."""
    if mime_type == "application/pdf":
        result = pdf.extract_pdf_text(content)
        ocr_health = ocr.check_ocr_health(settings)
        pages: list[dict] = []
        for page_content in result.pages:
            text = page_content.text
            if len(text) < settings.ocr_min_chars_per_page and ocr_health.status in ("ready", "not_loaded"):
                try:
                    rendered = pdf.render_page_png(content, page_content.page)
                    ocr_result = ocr.run_ocr(rendered)
                    if len(ocr_result.text) > len(text):
                        text = ocr_result.text
                except Exception:
                    logger.warning("OCR failed for knowledge document page %s", page_content.page, exc_info=True)
            pages.append({"page": page_content.page, "text": text})
        return pages

    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        text = docx_parser.extract_docx_text(content)
        return [{"page": 1, "text": text}]

    if mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        sheets = xlsx.extract_xlsx_text(content)
        return [{"page": i + 1, "text": f"[Sheet: {s.sheet_name}]\n{s.text}"} for i, s in enumerate(sheets)]

    return [{"page": 1, "text": ""}]


def activate_version(db: DbSession, settings: Settings, version: KnowledgeDocumentVersion) -> KnowledgeDocumentVersion:
    """The one place that changes what's retrievable for a document. (Re)indexes
    `version` — idempotent, so calling this on an already-active or already-indexed
    version is a safe no-op in effect — then deindexes+deactivates every sibling
    version of the same document, so at most one version is ever searchable at once
    ("active documents", spec's own term)."""
    document = db.get(KnowledgeDocument, version.document_id)
    if document is None:
        raise ValueError(f"Document {version.document_id} not found")

    content = file_path_for(settings, version).read_bytes()
    pages = _extract_pages(content, version.mime_type, settings)
    rows = index_document(
        db,
        settings,
        pages,
        collection=ChunkCollection.MEDICAL_KNOWLEDGE,
        source_title=document.title,
        source_filename=version.source_filename,
        file_hash=version.file_hash,
    )
    version.chunk_count = len(rows)
    version.ingestion_status = IngestionStatus.COMPLETED
    version.ingestion_error = None

    siblings = db.scalars(
        select(KnowledgeDocumentVersion).where(
            KnowledgeDocumentVersion.document_id == version.document_id,
            KnowledgeDocumentVersion.id != version.id,
            KnowledgeDocumentVersion.is_active.is_(True),
        )
    ).all()
    for sibling in siblings:
        try:
            delete_indexed_source(db, settings, ChunkCollection.MEDICAL_KNOWLEDGE, file_hash=sibling.file_hash)
        except Exception:
            logger.warning("Failed to deindex sibling version_id=%s", sibling.id, exc_info=True)
        sibling.is_active = False
        sibling.chunk_count = 0

    version.is_active = True
    db.commit()
    db.refresh(version)
    return version


def run_activation_task(document_version_id: str, settings: Settings) -> None:
    """The `BackgroundTasks` callable for both a fresh upload and an explicit
    reindex/activate-version request — opens its own db session (the request's is
    closed by the time a background task runs), and captures any failure into the
    version row rather than leaving it stuck at PROCESSING forever (spec §122)."""
    db = SessionLocal()
    try:
        version = db.get(KnowledgeDocumentVersion, document_version_id)
        if version is None:
            logger.error("Activation requested for missing document_version_id=%s", document_version_id)
            return
        version.ingestion_status = IngestionStatus.PROCESSING
        version.ingestion_error = None
        db.commit()
        activate_version(db, settings, version)
    except Exception as exc:
        logger.exception("Activation failed for document_version_id=%s", document_version_id)
        db.rollback()
        version = db.get(KnowledgeDocumentVersion, document_version_id)
        if version:
            version.ingestion_status = IngestionStatus.FAILED
            version.ingestion_error = str(exc)[:2000]
            db.commit()
    finally:
        db.close()
