from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser, WriteUser
from app.models import Chunk, Document, Patient
from app.schemas.common import ChunkOut, DocumentOut, DocumentUpdate
from app.services import audit, documents

router = APIRouter(prefix="/api", tags=["documents"])


def doc_out(d: Document) -> dict:
    return DocumentOut.model_validate(d).model_dump()


def _get(db, doc_id: str) -> Document:
    d = db.get(Document, doc_id)
    if d is None:
        raise HTTPException(404, "Document not found")
    return d


@router.get("/patients/{patient_id}/documents")
def list_patient_documents(patient_id: str, db: DB, _: CurrentUser):
    return [
        doc_out(d)
        for d in db.scalars(
            select(Document)
            .where(Document.patient_id == patient_id)
            .order_by(func.coalesce(Document.document_date, Document.created_at).desc())
        )
    ]


@router.post("/patients/{patient_id}/documents", status_code=201)
async def upload_patient_document(
    patient_id: str,
    db: DB,
    user: WriteUser,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    kind: str | None = Form(None),
    document_date: date | None = Form(None),
    encounter_id: str | None = Form(None),
):
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(404, "Patient not found")
    data = await file.read()
    doc = documents.create(
        db,
        user,
        data=data,
        filename=file.filename or "upload",
        declared_mime=file.content_type,
        scope="patient",
        patient=patient,
        title=title,
        kind=kind or None,
        document_date=document_date,
        encounter_id=encounter_id,
    )
    background.add_task(documents.process, doc.id)
    return doc_out(doc)


@router.get("/documents/{doc_id}")
def read_document(doc_id: str, db: DB, _: CurrentUser):
    return doc_out(_get(db, doc_id))


@router.get("/documents/{doc_id}/file")
def document_file(doc_id: str, db: DB, user: CurrentUser, download: bool = False):
    d = _get(db, doc_id)
    path = Path(d.storage_path)
    if not path.exists():
        raise HTTPException(410, "The stored file is missing.")
    audit.record(
        db,
        user,
        "document.view",
        f"Viewed file '{d.title}'",
        entity_type="document",
        entity_id=d.id,
        patient_id=d.patient_id,
    )
    return FileResponse(
        path,
        media_type=d.mime_type,
        filename=d.filename,
        content_disposition_type="attachment" if download else "inline",
    )


@router.get("/documents/{doc_id}/chunks", response_model=list[ChunkOut])
def document_chunks(doc_id: str, db: DB, _: CurrentUser):
    _get(db, doc_id)
    return db.scalars(select(Chunk).where(Chunk.document_id == doc_id).order_by(Chunk.ordinal)).all()


@router.patch("/documents/{doc_id}")
def update_document(doc_id: str, body: DocumentUpdate, db: DB, user: WriteUser, background: BackgroundTasks):
    d = _get(db, doc_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("kind") and changes["kind"] not in documents.KINDS:
        raise HTTPException(400, "Unknown document type")
    reprocess_needed = False
    if changes.get("identity_status") == "confirmed":
        # Clinician confirms the document belongs to this patient: release quarantine.
        changes["identity_status"] = "match"
        d.identity_detail = f"Identity confirmed manually by {user.full_name}"
        d.extraction = {**(d.extraction or {}), "identity_confirmed": True, "quarantined": False}
        changes["is_active"] = True
        d.status = "processing"
        reprocess_needed = True
    for k, v in changes.items():
        setattr(d, k, v)
    db.commit()
    if reprocess_needed:
        background.add_task(documents.process, d.id)
    audit.record(
        db,
        user,
        "document.update",
        f"Updated '{d.title}'",
        entity_type="document",
        entity_id=d.id,
        patient_id=d.patient_id,
        details=changes,
    )
    return doc_out(d)


@router.post("/documents/{doc_id}/reprocess")
def reprocess(doc_id: str, db: DB, user: WriteUser, background: BackgroundTasks):
    d = _get(db, doc_id)
    d.status, d.error = "processing", None
    db.commit()
    background.add_task(documents.process, d.id)
    audit.record(
        db,
        user,
        "document.reprocess",
        f"Re-processing '{d.title}'",
        entity_type="document",
        entity_id=d.id,
        patient_id=d.patient_id,
    )
    return doc_out(d)


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: str, db: DB, user: WriteUser):
    d = _get(db, doc_id)
    if d.scope == "knowledge" and user.role != "admin":
        raise HTTPException(403, "Only administrators can delete library documents")
    await documents.remove(db, user, d)


@router.get("/document-kinds")
def kinds(_: CurrentUser):
    return list(documents.KINDS)
