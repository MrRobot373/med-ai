from __future__ import annotations

import platform
import time
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import func, select, text

from app.ai import registry
from app.ai.llm import list_models
from app.api.deps import DB, CurrentUser
from app.core.config import get_settings
from app.core.errors import AppError, ServiceUnavailable
from app.models import AIRun, AuditLog, Conversation, Document, Encounter, Message, Observation, Patient, User
from app.services import runtime_config

router = APIRouter(prefix="/api", tags=["system"])
_health_cache: dict = {"at": 0.0, "data": None}
APP_VERSION = "2.0.0"


async def _check(name: str, fn) -> dict:
    started = time.perf_counter()
    try:
        detail = await fn()
        status = detail.pop("status", "online")
        return {
            "component": name,
            "status": status,
            **detail,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    except (ServiceUnavailable, AppError) as exc:
        return {
            "component": name,
            "status": "offline",
            "error": exc.message,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    except Exception as exc:
        return {
            "component": name,
            "status": "offline",
            "error": f"{exc.__class__.__name__}: {exc}",
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }


@router.get("/system/health")
async def health(db: DB, _: CurrentUser, refresh: bool = False):
    if not refresh and _health_cache["data"] and time.time() - _health_cache["at"] < 20:
        return _health_cache["data"]
    cfg = runtime_config.load(db)

    async def database():
        db.execute(text("SELECT 1"))
        return {"detail": "SQLite" if get_settings().resolved_database_url.startswith("sqlite") else "SQL database"}

    async def llm():
        models = await list_models(cfg.llm.provider, cfg.llm.base_url, cfg.llm.api_key)
        found = cfg.llm.model in models or (cfg.llm.provider == "ollama" and f"{cfg.llm.model}:latest" in models)
        if not found and models:
            return {
                "status": "degraded",
                "detail": f"Endpoint reachable, but model '{cfg.llm.model}' is not listed",
                "model": cfg.llm.model,
            }
        return {"detail": f"{cfg.llm.model} via {cfg.llm.provider}", "model": cfg.llm.model}

    async def embeddings():
        dim = await registry.embedder(cfg).dimension()
        st = runtime_config.index_status(cfg)
        if st["reindex_required"]:
            return {
                "status": "degraded",
                "detail": "Embedding model changed — re-index required",
                "model": cfg.embeddings.model,
            }
        return {"detail": f"{cfg.embeddings.model} · {dim}-d", "model": cfg.embeddings.model}

    async def reranker():
        rr = registry.reranker(cfg)
        if not rr.enabled:
            return {"status": "disabled", "detail": "Reranking off — fusion order used"}
        if cfg.reranker.provider == "llm":
            return {"detail": rr.label}
        await rr.score("test", ["test passage"])
        return {"detail": rr.label, "model": cfg.reranker.model}

    async def vectors():
        stats = await registry.vector_store(cfg).stats()
        mode = "embedded" if cfg.vector_store.mode == "embedded" else cfg.vector_store.url
        return {"detail": f"Qdrant ({mode}) · {stats['knowledge'] + stats['patient']} vectors", "stats": stats}

    async def research():
        if not cfg.research.enabled:
            return {"status": "disabled", "detail": "Research Mode off (local-only)"}
        return {"detail": ", ".join(cfg.research.sources)}

    import asyncio

    components = await asyncio.gather(
        _check("database", database),
        _check("llm", llm),
        _check("embeddings", embeddings),
        _check("reranker", reranker),
        _check("vector_store", vectors),
        _check("research", research),
    )
    critical = [c for c in components if c["component"] in ("database", "llm", "embeddings", "vector_store")]
    overall = (
        "online"
        if all(c["status"] == "online" for c in critical)
        else "offline"
        if any(c["status"] == "offline" for c in critical)
        else "degraded"
    )
    data = {"status": overall, "checked_at": datetime.now(UTC), "components": components}
    _health_cache.update(at=time.time(), data=data)
    return data


@router.get("/system/info")
def info(db: DB, _: CurrentUser):
    cfg = runtime_config.load(db)
    return {
        "version": APP_VERSION,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "llm": {"provider": cfg.llm.provider, "model": cfg.llm.model},
        "embeddings": {
            "provider": cfg.embeddings.provider,
            "model": cfg.embeddings.model,
            "dimension": cfg.index_dimension,
        },
        "reranker": {"provider": cfg.reranker.provider, "model": cfg.reranker.model},
        "vector_store": cfg.vector_store.mode,
        "research_enabled": cfg.research.enabled,
        "counts": {
            "patients": db.scalar(select(func.count()).select_from(Patient)),
            "documents": db.scalar(select(func.count()).select_from(Document)),
            "users": db.scalar(select(func.count()).select_from(User)),
        },
    }


@router.get("/dashboard")
def dashboard(db: DB, user: CurrentUser):
    now = datetime.now(UTC)
    week = now - timedelta(days=7)

    def count(stmt):
        return db.scalar(stmt) or 0

    stats = {
        "active_patients": count(select(func.count()).select_from(Patient).where(Patient.status == "active")),
        "new_documents_7d": count(
            select(func.count()).select_from(Document).where(Document.scope == "patient", Document.created_at >= week)
        ),
        "documents_needing_review": count(
            select(func.count())
            .select_from(Document)
            .where(Document.scope == "patient", Document.review_status == "pending", Document.status == "ready")
        ),
        "abnormal_unacknowledged": count(
            select(func.count())
            .select_from(Observation)
            .where(Observation.flag.in_(["high", "low", "abnormal"]), Observation.acknowledged.is_(False))
        ),
        "ai_runs_7d": count(select(func.count()).select_from(AIRun).where(AIRun.created_at >= week)),
        "questions_7d": count(
            select(func.count()).select_from(Message).where(Message.role == "user", Message.created_at >= week)
        ),
        "drafts_pending": count(
            select(func.count())
            .select_from(AIRun)
            .where(AIRun.status == "draft", AIRun.tool.in_(["summary", "soap", "differential"]))
        ),
        "knowledge_documents": count(
            select(func.count()).select_from(Document).where(Document.scope == "knowledge", Document.status == "ready")
        ),
        "encounters_today": count(
            select(func.count())
            .select_from(Encounter)
            .where(Encounter.started_at >= now.replace(hour=0, minute=0, second=0, microsecond=0))
        ),
    }
    recent_patients = []
    seen = set()
    for log in db.scalars(
        select(AuditLog)
        .where(AuditLog.user_id == user.id, AuditLog.action == "patient.view")
        .order_by(AuditLog.at.desc())
        .limit(80)
    ):
        if log.patient_id in seen:
            continue
        p = db.get(Patient, log.patient_id)
        if p:
            seen.add(p.id)
            recent_patients.append({"id": p.id, "full_name": p.full_name, "mrn": p.mrn, "at": log.at})
        if len(recent_patients) >= 6:
            break
    activity = [
        {"at": a.at, "user": a.user_email, "action": a.action, "summary": a.summary, "patient_id": a.patient_id}
        for a in db.scalars(
            select(AuditLog)
            .where(AuditLog.action.not_in(["patient.view", "document.view", "auth.login", "auth.logout"]))
            .order_by(AuditLog.at.desc())
            .limit(10)
        )
    ]
    days = []
    for i in range(13, -1, -1):
        start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        days.append(
            {
                "date": start.date().isoformat(),
                "questions": count(
                    select(func.count())
                    .select_from(Message)
                    .where(Message.role == "user", Message.created_at >= start, Message.created_at < end)
                ),
                "tools": count(
                    select(func.count()).select_from(AIRun).where(AIRun.created_at >= start, AIRun.created_at < end)
                ),
                "documents": count(
                    select(func.count())
                    .select_from(Document)
                    .where(Document.created_at >= start, Document.created_at < end)
                ),
            }
        )
    recent_conversations = [
        {"id": c.id, "title": c.title, "patient_id": c.patient_id, "updated_at": c.updated_at}
        for c in db.scalars(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.updated_at.desc())
            .limit(5)
        )
    ]
    return {
        "stats": stats,
        "recent_patients": recent_patients,
        "activity": activity,
        "usage": days,
        "recent_conversations": recent_conversations,
    }


@router.get("/inbox")
def inbox(db: DB, _: CurrentUser):
    """Clinical work queue: everything that needs a human decision."""
    items = []

    def pname(pid):
        p = db.get(Patient, pid) if pid else None
        return (p.full_name, p.mrn) if p else (None, None)

    for d in db.scalars(select(Document).where(Document.scope == "patient", Document.identity_status == "mismatch")):
        n, m = pname(d.patient_id)
        items.append(
            {
                "id": f"id-{d.id}",
                "type": "identity",
                "priority": "high",
                "title": "Possible wrong-patient document",
                "detail": d.identity_detail,
                "patient_id": d.patient_id,
                "patient_name": n,
                "mrn": m,
                "ref_id": d.id,
                "at": d.created_at,
            }
        )
    for d in db.scalars(select(Document).where(Document.status == "failed")):
        n, m = pname(d.patient_id)
        items.append(
            {
                "id": f"fail-{d.id}",
                "type": "ingestion",
                "priority": "high",
                "title": f"Processing failed: {d.title}",
                "detail": d.error,
                "patient_id": d.patient_id,
                "patient_name": n,
                "mrn": m,
                "ref_id": d.id,
                "at": d.updated_at,
            }
        )
    for o in db.scalars(
        select(Observation)
        .where(Observation.flag.in_(["high", "low", "abnormal"]), Observation.acknowledged.is_(False))
        .order_by(Observation.observed_at.desc())
        .limit(100)
    ):
        n, m = pname(o.patient_id)
        value = f"{o.value_num:g}" if o.value_num is not None else (o.value_text or "")
        items.append(
            {
                "id": f"lab-{o.id}",
                "type": "lab",
                "priority": "medium",
                "title": f"{o.name} {o.flag}: {value} {o.unit or ''}".strip(),
                "detail": f"Reference {o.ref_text}" if o.ref_text else o.source_excerpt,
                "patient_id": o.patient_id,
                "patient_name": n,
                "mrn": m,
                "ref_id": o.id,
                "at": o.observed_at,
            }
        )
    for d in db.scalars(
        select(Document).where(
            Document.scope == "patient",
            Document.status == "ready",
            Document.review_status == "pending",
            Document.identity_status != "mismatch",
        )
    ):
        n, m = pname(d.patient_id)
        items.append(
            {
                "id": f"rev-{d.id}",
                "type": "review",
                "priority": "low",
                "title": f"New document to review: {d.title}",
                "detail": d.kind.replace("_", " "),
                "patient_id": d.patient_id,
                "patient_name": n,
                "mrn": m,
                "ref_id": d.id,
                "at": d.created_at,
            }
        )
    for r in db.scalars(
        select(AIRun)
        .where(
            AIRun.status == "draft",
            AIRun.tool.in_(["summary", "soap", "differential", "comparison", "med_reconciliation"]),
        )
        .order_by(AIRun.created_at.desc())
        .limit(50)
    ):
        n, m = pname(r.patient_id)
        items.append(
            {
                "id": f"draft-{r.id}",
                "type": "draft",
                "priority": "low",
                "title": f"AI draft awaiting review: {r.tool.replace('_', ' ')}",
                "detail": None,
                "patient_id": r.patient_id,
                "patient_name": n,
                "mrn": m,
                "ref_id": r.id,
                "at": r.created_at,
            }
        )
    order = {"high": 0, "medium": 1, "low": 2}

    def ts(v):
        return v if v.tzinfo else v.replace(tzinfo=UTC)

    items.sort(key=lambda i: (order[i["priority"]], -ts(i["at"]).timestamp()))
    return items


@router.get("/dashboard/review-queue")
def review_queue(db: DB, _: CurrentUser, limit: int = 12):
    """Patient documents awaiting clinician review (newest first), for the home viewer.
    Quarantined documents come first so a suspected wrong-patient file is never missed."""
    from app.api.documents import doc_out

    rows = db.execute(
        select(Document, Patient)
        .join(Patient, Patient.id == Document.patient_id)
        .where(
            Document.scope == "patient",
            Document.review_status == "pending",
            Document.status.in_(["ready", "processing"]),
        )
        .order_by(Document.created_at.desc())
        .limit(min(limit, 50))
    ).all()
    out = [{**doc_out(d), "patient_name": p.full_name, "patient_mrn": p.mrn} for d, p in rows]
    out.sort(key=lambda d: d["identity_status"] != "mismatch")
    return out


@router.get("/dashboard/attention")
def attention(db: DB, _: CurrentUser, limit: int = 6):
    """Active patients ranked by what needs a clinician: unacknowledged abnormal results,
    identity mismatches, pending documents and the most concerning applicable score."""
    from app.clinical import scores as scores_mod
    from app.clinical.context import age, latest_observations

    ranked = []
    for p in db.scalars(select(Patient).where(Patient.status == "active")):
        latest = latest_observations(db, p.id, limit_codes=60)
        abnormal = [o for o in latest if o.flag in ("high", "low", "abnormal") and not o.acknowledged]
        mismatches = (
            db.scalar(
                select(func.count())
                .select_from(Document)
                .where(Document.patient_id == p.id, Document.identity_status == "mismatch")
            )
            or 0
        )
        pending = (
            db.scalar(
                select(func.count())
                .select_from(Document)
                .where(Document.patient_id == p.id, Document.review_status == "pending", Document.status == "ready")
            )
            or 0
        )
        scored = scores_mod.compute(db, p)
        top_score = scored[0] if scored else None
        severity = len(abnormal) + 5 * mismatches + pending + (3 * top_score["level"] if top_score else 0)
        if not severity:
            continue

        def deviation(o):
            if o.value_num is None:
                return 0
            span = (o.ref_high or 0) - (o.ref_low or 0) or abs(o.ref_high or o.ref_low or 1)
            ref = (
                o.ref_high
                if o.flag == "high" and o.ref_high is not None
                else o.ref_low
                if o.ref_low is not None
                else o.value_num
            )
            return abs(o.value_num - ref) / (span or 1)

        marker = max(abnormal, key=deviation, default=None)
        ranked.append(
            {
                "id": p.id,
                "full_name": p.full_name,
                "mrn": p.mrn,
                "age": age(p.date_of_birth),
                "sex": p.sex,
                "abnormal": len(abnormal),
                "mismatches": mismatches,
                "pending_documents": pending,
                "severity": severity,
                "marker": {
                    "name": marker.name,
                    "value": marker.value_num,
                    "unit": marker.unit,
                    "ref_low": marker.ref_low,
                    "ref_high": marker.ref_high,
                    "flag": marker.flag,
                    "observed_at": marker.observed_at,
                }
                if marker
                else None,
                "score": {k: top_score[k] for k in ("name", "value", "category", "level", "levels")}
                if top_score
                else None,
            }
        )
    ranked.sort(key=lambda r: r["severity"], reverse=True)
    return ranked[: min(limit, 50)]
