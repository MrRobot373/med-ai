"""Knowledge Administration endpoints (spec §104 Knowledge, Phase 12). Every route is
`AdminUser`-gated — spec §18 lists "Manage knowledge base" only under Admin's
permissions, unlike patient-facing routes where Doctor also has write access.

Version upload/reindex/activate all return immediately and run the actual
extract-chunk-embed-index work in a `BackgroundTask` (spec §122's persistent-job-row
pattern, same as report ingestion) — the frontend polls the version's
`ingestion_status` rather than blocking the request on a potentially slow CPU
embedding pass.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import DbDep, SettingsDep
from app.audit.service import record as record_audit
from app.auth.dependencies import AdminUser
from app.models.audit_log import AuditAction
from app.models.knowledge_document import KnowledgeDocument, KnowledgeDocumentVersion
from app.models.report import IngestionStatus
from app.schemas.knowledge import (
    KnowledgeDocumentCreate,
    KnowledgeDocumentDetail,
    KnowledgeDocumentOut,
    KnowledgeDocumentUpdate,
    KnowledgeVersionOut,
)
from app.services import knowledge as knowledge_service

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class ActivateVersionRequest(BaseModel):
    version_id: str


def _get_document_or_404(db: DbDep, document_id: str) -> KnowledgeDocument:
    document = knowledge_service.get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found")
    return document


def _get_version_or_404(db: DbDep, document_id: str, version_id: str) -> KnowledgeDocumentVersion:
    version = knowledge_service.get_version(db, version_id)
    if version is None or version.document_id != document_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found")
    return version


def _to_detail(db: DbDep, document: KnowledgeDocument) -> KnowledgeDocumentDetail:
    versions = knowledge_service.list_versions(db, document.id)
    return KnowledgeDocumentDetail(
        **KnowledgeDocumentOut.model_validate(document).model_dump(),
        versions=[KnowledgeVersionOut.model_validate(v) for v in versions],
    )


@router.get("/documents", response_model=list[KnowledgeDocumentOut])
def list_documents(
    db: DbDep, _admin: AdminUser, include_archived: bool = False, search: str | None = None
) -> list[KnowledgeDocumentOut]:
    documents = knowledge_service.list_documents(db, include_archived=include_archived, search=search)
    return [KnowledgeDocumentOut.model_validate(d) for d in documents]


@router.post("/documents", response_model=KnowledgeDocumentOut, status_code=status.HTTP_201_CREATED)
def create_document(payload: KnowledgeDocumentCreate, db: DbDep, admin: AdminUser) -> KnowledgeDocumentOut:
    document = knowledge_service.create_document(
        db, payload.title, payload.source, payload.specialty, payload.authority_tier, payload.tags, admin.id
    )
    return KnowledgeDocumentOut.model_validate(document)


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentDetail)
def get_document(document_id: str, db: DbDep, _admin: AdminUser) -> KnowledgeDocumentDetail:
    document = _get_document_or_404(db, document_id)
    return _to_detail(db, document)


@router.patch("/documents/{document_id}", response_model=KnowledgeDocumentOut)
def update_document(document_id: str, payload: KnowledgeDocumentUpdate, db: DbDep, _admin: AdminUser) -> KnowledgeDocumentOut:
    document = _get_document_or_404(db, document_id)
    updated = knowledge_service.update_document(
        db,
        document,
        title=payload.title,
        source=payload.source,
        specialty=payload.specialty,
        authority_tier=payload.authority_tier,
        tags=payload.tags,
    )
    return KnowledgeDocumentOut.model_validate(updated)


@router.post("/documents/{document_id}/archive", response_model=KnowledgeDocumentOut)
def archive_document(document_id: str, db: DbDep, settings: SettingsDep, _admin: AdminUser) -> KnowledgeDocumentOut:
    document = _get_document_or_404(db, document_id)
    updated = knowledge_service.archive_document(db, settings, document)
    return KnowledgeDocumentOut.model_validate(updated)


@router.post(
    "/documents/{document_id}/versions", response_model=KnowledgeVersionOut, status_code=status.HTTP_201_CREATED
)
async def upload_version(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: DbDep,
    settings: SettingsDep,
    admin: AdminUser,
    file: Annotated[UploadFile, File()],
    effective_date: str | None = None,
    review_date: str | None = None,
) -> KnowledgeVersionOut:
    document = _get_document_or_404(db, document_id)
    content = await file.read()

    def _parse_date(raw: str | None):
        if not raw:
            return None
        try:
            return date_cls.fromisoformat(raw)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Invalid date '{raw}' — expected YYYY-MM-DD") from exc

    try:
        version = knowledge_service.upload_version(
            db,
            settings,
            document,
            file.filename or "upload",
            content,
            _parse_date(effective_date),
            _parse_date(review_date),
            created_by=admin.id,
        )
    except knowledge_service.UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except knowledge_service.DuplicateVersionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    record_audit(
        db, AuditAction.KNOWLEDGE_DOCUMENT_UPLOADED, user=admin, object_type="knowledge_document_version",
        object_id=version.id, detail={"document_id": document_id},
    )

    # Upload -> activate is the default flow (spec: "upload, ... active documents") —
    # a freshly uploaded version becomes the retrievable one once ingestion succeeds,
    # without a separate manual activation step for the common case. Rolling back to
    # an older version still goes through the explicit activate-version endpoint.
    background_tasks.add_task(knowledge_service.run_activation_task, version.id, settings)
    return KnowledgeVersionOut.model_validate(version)


@router.post("/documents/{document_id}/reindex", response_model=KnowledgeVersionOut)
def reindex_document(document_id: str, background_tasks: BackgroundTasks, db: DbDep, settings: SettingsDep, _admin: AdminUser) -> KnowledgeVersionOut:
    """Re-runs extraction/chunking/embedding/indexing for the document's current
    version (whichever is active, or the most recent upload if none is) — useful
    after a chunking/embedding setting change, or to recover a version stuck FAILED,
    without requiring the admin to re-upload the same file."""
    document = _get_document_or_404(db, document_id)
    versions = knowledge_service.list_versions(db, document.id)
    target = next((v for v in versions if v.is_active), versions[0] if versions else None)
    if target is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="This document has no uploaded versions to reindex")

    target.ingestion_status = IngestionStatus.QUEUED
    db.commit()
    background_tasks.add_task(knowledge_service.run_activation_task, target.id, settings)
    return KnowledgeVersionOut.model_validate(target)


@router.post("/documents/{document_id}/activate-version", response_model=KnowledgeVersionOut)
def activate_version(
    document_id: str, payload: ActivateVersionRequest, background_tasks: BackgroundTasks, db: DbDep, settings: SettingsDep, admin: AdminUser
) -> KnowledgeVersionOut:
    document = _get_document_or_404(db, document_id)
    version = _get_version_or_404(db, document.id, payload.version_id)

    version.ingestion_status = IngestionStatus.QUEUED
    db.commit()
    record_audit(
        db, AuditAction.KNOWLEDGE_VERSION_CHANGED, user=admin, object_type="knowledge_document_version",
        object_id=version.id, detail={"document_id": document_id, "version_number": version.version_number},
    )
    background_tasks.add_task(knowledge_service.run_activation_task, version.id, settings)
    return KnowledgeVersionOut.model_validate(version)


@router.get("/documents/{document_id}/versions/{version_id}/file")
def download_version_file(document_id: str, version_id: str, db: DbDep, settings: SettingsDep, _admin: AdminUser) -> FileResponse:
    document = _get_document_or_404(db, document_id)
    version = _get_version_or_404(db, document.id, version_id)
    path = knowledge_service.file_path_for(settings, version)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found")
    return FileResponse(path, media_type=version.mime_type, filename=version.source_filename)
