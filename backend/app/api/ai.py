from __future__ import annotations

import json
import time

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import DB, AIUser, ClinicalUser, WriteUser
from app.core.errors import AppError, ServiceUnavailable
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models import AIRun, Conversation, Message, Patient, User
from app.schemas.common import (
    AIRunOut,
    AskIn,
    ConversationIn,
    ConversationOut,
    ConversationUpdate,
    FeedbackIn,
    ReviewIn,
    ToolRunIn,
)
from app.services import audit, chat, documents, runtime_config, tools, vision

router = APIRouter(prefix="/api", tags=["ai"])
logger = get_logger(__name__)


def _conv(db, user, conv_id: str) -> Conversation:
    c = db.get(Conversation, conv_id)
    if c is None or c.user_id != user.id:
        raise HTTPException(404, "Conversation not found")
    return c


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(db: DB, user: ClinicalUser, patient_id: str | None = None):
    return chat.conversations_for(db, user, patient_id)


@router.post("/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(body: ConversationIn, db: DB, user: AIUser):
    if body.patient_id and db.get(Patient, body.patient_id) is None:
        raise HTTPException(404, "Patient not found")
    c = Conversation(
        user_id=user.id,
        patient_id=body.patient_id,
        scope="patient" if body.patient_id else "knowledge",
        title=body.title or "New conversation",
    )
    db.add(c)
    db.commit()
    return c


@router.get("/conversations/{conv_id}")
def read_conversation(conv_id: str, db: DB, user: ClinicalUser):
    c = _conv(db, user, conv_id)
    patient = db.get(Patient, c.patient_id) if c.patient_id else None
    return {
        **ConversationOut.model_validate(c).model_dump(),
        "patient": {"id": patient.id, "full_name": patient.full_name, "mrn": patient.mrn} if patient else None,
        "messages": [chat.message_out(m) for m in c.messages],
    }


@router.patch("/conversations/{conv_id}", response_model=ConversationOut)
def update_conversation(conv_id: str, body: ConversationUpdate, db: DB, user: ClinicalUser):
    c = _conv(db, user, conv_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    db.commit()
    return c


@router.delete("/conversations/{conv_id}", status_code=204)
def delete_conversation(conv_id: str, db: DB, user: ClinicalUser):
    db.delete(_conv(db, user, conv_id))
    db.commit()


@router.post("/conversations/{conv_id}/messages")
async def ask(conv_id: str, body: AskIn, request: Request, db: DB, user: AIUser):
    _conv(db, user, conv_id)
    user_id = user.id

    async def events():
        # The stream outlives the request-scoped session, so it uses its own.
        sdb = SessionLocal()
        try:
            suser = sdb.get(User, user_id)
            sconv = sdb.get(Conversation, conv_id)
            async for ev in chat.answer(sdb, suser, sconv, body.content.strip()):
                if await request.is_disconnected():
                    break
                yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'], default=str)}\n\n"
        except Exception as exc:  # last-resort: surface, never hang the stream
            logger.exception("Chat stream failed")
            msg = getattr(exc, "message", None) or "Unexpected error while answering."
            yield f"event: error\ndata: {json.dumps({'message': msg})}\n\n"
        finally:
            sdb.close()

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.post("/messages/{message_id}/feedback")
def feedback(message_id: str, body: FeedbackIn, db: DB, user: ClinicalUser):
    m = db.get(Message, message_id)
    if m is None or m.conversation.user_id != user.id:
        raise HTTPException(404, "Message not found")
    m.feedback, m.feedback_note = body.rating, body.note
    db.commit()
    audit.record(
        db,
        user,
        "ai.feedback",
        f"Rated answer {body.rating or 'cleared'}",
        entity_type="message",
        entity_id=m.id,
        patient_id=m.conversation.patient_id,
        details={"note": body.note},
    )
    return {"ok": True}


# ---- Tools ------------------------------------------------------------------
@router.get("/tools")
def tool_catalog(_: ClinicalUser):
    return [{"id": k, **v} for k, v in tools.TOOLS.items()]


@router.post("/tools/{tool}/run", response_model=AIRunOut)
async def run_tool(tool: str, body: ToolRunIn, db: DB, user: AIUser):
    return await tools.run(db, user, tool, body.model_dump(exclude_none=True))


@router.get("/ai-runs", response_model=list[AIRunOut])
def list_runs(
    db: DB,
    _: ClinicalUser,
    patient_id: str | None = None,
    tool: str | None = None,
    status: str | None = None,
    limit: int = 50,
):
    stmt = select(AIRun)
    if patient_id:
        stmt = stmt.where(AIRun.patient_id == patient_id)
    if tool:
        stmt = stmt.where(AIRun.tool == tool)
    if status:
        stmt = stmt.where(AIRun.status == status)
    return db.scalars(stmt.order_by(AIRun.created_at.desc()).limit(min(limit, 200))).all()


@router.get("/ai-runs/{run_id}", response_model=AIRunOut)
def read_run(run_id: str, db: DB, _: ClinicalUser):
    r = db.get(AIRun, run_id)
    if r is None:
        raise HTTPException(404, "Run not found")
    return r


@router.post("/ai-runs/{run_id}/review", response_model=AIRunOut)
def review_run(run_id: str, body: ReviewIn, db: DB, user: WriteUser):
    r = db.get(AIRun, run_id)
    if r is None:
        raise HTTPException(404, "Run not found")
    return tools.review(db, user, r, body.decision)


# ---- Vision -----------------------------------------------------------------
@router.post("/vision/analyze", response_model=AIRunOut)
async def analyze_image(
    db: DB,
    user: AIUser,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    patient_id: str | None = Form(None),
    question: str | None = Form(None),
    attach_to_record: bool = Form(False),
):
    data = await file.read()
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(415, "Upload a PNG, JPG or WEBP image.")
    patient = db.get(Patient, patient_id) if patient_id else None
    if patient_id and patient is None:
        raise HTTPException(404, "Patient not found")
    cfg = runtime_config.load(db)
    started = time.perf_counter()
    run_row = AIRun(
        tool="vision",
        patient_id=patient_id,
        input={"filename": file.filename, "question": question},
        created_by=user.id,
    )
    try:
        output, model = await vision.analyze(cfg, data, question)
        run_row.output, run_row.model, run_row.status = output, model, "draft"
    except ServiceUnavailable as exc:
        run_row.status, run_row.error = "error", exc.message
    except ValueError as exc:
        run_row.status, run_row.error = "error", str(exc)
    run_row.latency_ms = int((time.perf_counter() - started) * 1000)
    if attach_to_record and patient is not None:
        try:
            doc = documents.create(
                db,
                user,
                data=data,
                filename=file.filename or "image.png",
                declared_mime=file.content_type,
                scope="patient",
                patient=patient,
                kind="imaging",
            )
            run_row.input = {**run_row.input, "document_id": doc.id}
            background.add_task(documents.process, doc.id)
        except AppError as exc:
            run_row.input = {**run_row.input, "attach_error": exc.message}
    db.add(run_row)
    db.commit()
    audit.record(
        db,
        user,
        "ai.vision",
        f"Analysed image {file.filename}",
        entity_type="ai_run",
        entity_id=run_row.id,
        patient_id=patient_id,
    )
    return run_row
