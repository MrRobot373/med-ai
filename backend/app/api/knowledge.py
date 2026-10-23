from __future__ import annotations

from datetime import date

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from sqlalchemy import func, or_, select

from app.api.deps import DB, AdminUser, AIUser, CurrentUser
from app.api.documents import doc_out
from app.models import Document
from app.rag.retrieve import retrieve
from app.schemas.common import RetrievalTestIn
from app.services import audit, documents, runtime_config
from app.services.knowledge_domains import DOMAINS

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("")
def list_knowledge(db: DB, _: CurrentUser, q: str | None = None, domain: str | None = None, status: str | None = None):
    stmt = select(Document).where(Document.scope == "knowledge")
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(Document.title.ilike(like), Document.filename.ilike(like), Document.source_org.ilike(like))
        )
    if domain:
        stmt = stmt.where(Document.domain == domain)
    if status == "active":
        stmt = stmt.where(Document.is_active.is_(True))
    elif status == "inactive":
        stmt = stmt.where(Document.is_active.is_(False))
    elif status:
        stmt = stmt.where(Document.status == status)
    return [doc_out(d) for d in db.scalars(stmt.order_by(Document.updated_at.desc()))]


@router.get("/domains")
def domains(db: DB, _: CurrentUser):
    counts = dict(
        db.execute(
            select(Document.domain, func.count()).where(Document.scope == "knowledge").group_by(Document.domain)
        ).all()
    )
    known = {d["id"] for d in DOMAINS}
    out = [{**d, "count": counts.get(d["id"], 0)} for d in DOMAINS]
    for custom, n in counts.items():
        if custom and custom not in known:
            out.append({"id": custom, "name": custom.replace("_", " ").title(), "group": "Custom", "count": n})
    return out


@router.get("/stats")
def stats(db: DB, _: CurrentUser):
    rows = db.execute(
        select(Document.status, func.count(), func.sum(Document.chunk_count))
        .where(Document.scope == "knowledge")
        .group_by(Document.status)
    ).all()
    return {
        "by_status": {s: c for s, c, _ in rows},
        "chunks": sum((n or 0) for _, _, n in rows),
        "documents": sum(c for _, c, _ in rows),
    }


@router.post("", status_code=201)
async def upload(
    db: DB,
    admin: AdminUser,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    domain: str | None = Form(None),
    kind: str | None = Form(None),
    source_org: str | None = Form(None),
    version: str | None = Form(None),
    document_date: date | None = Form(None),
):
    data = await file.read()
    doc = documents.create(
        db,
        admin,
        data=data,
        filename=file.filename or "upload",
        declared_mime=file.content_type,
        scope="knowledge",
        title=title,
        kind=kind or "guideline",
        domain=domain or None,
        source_org=source_org,
        version=version,
        document_date=document_date,
    )
    background.add_task(documents.process, doc.id)
    return doc_out(doc)


@router.post("/search")
async def retrieval_playground(body: RetrievalTestIn, db: DB, user: AIUser):
    """Runs the real retrieval pipeline without generation — for tuning and debugging."""
    cfg = runtime_config.load(db)
    res = await retrieve(
        db, cfg, body.query, patient_id=body.patient_id, include_knowledge=body.include_knowledge, domains=body.domains
    )
    audit.record(db, user, "retrieval.test", f"Retrieval test: {body.query[:80]}", patient_id=body.patient_id)
    return {"passages": [p.public(1200) for p in res.passages], "trace": res.trace}


@router.post("/{doc_id}/activate")
def set_active(doc_id: str, active: bool, db: DB, admin: AdminUser):
    d = db.get(Document, doc_id)
    if d is None or d.scope != "knowledge":
        raise HTTPException(404, "Document not found")
    d.is_active = active
    db.commit()
    audit.record(
        db,
        admin,
        "knowledge.activate" if active else "knowledge.deactivate",
        f"{'Activated' if active else 'Deactivated'} '{d.title}'",
        entity_type="document",
        entity_id=d.id,
    )
    return doc_out(d)
