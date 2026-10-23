from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError

from app.ai.embeddings import Embedder
from app.ai.llm import LLMClient, list_models, vision_llm_config
from app.ai.reranker import Reranker
from app.api.deps import DB, AdminUser
from app.core.errors import AppError, ServiceUnavailable
from app.db import SessionLocal
from app.rag import indexing
from app.rag.vector_store import VectorStore, reset_clients
from app.services import audit, runtime_config

router = APIRouter(prefix="/api/settings", tags=["settings"])

_reindex_state: dict = {"running": False, "done": 0, "total": 0, "result": None, "error": None, "started_at": None}


@router.get("")
def get_settings_view(db: DB, _: AdminUser):
    data = runtime_config.public_view(runtime_config.load(db))
    data["profiles"] = runtime_config.RETRIEVAL_PROFILES
    return data


@router.put("/{section}")
def update_section(section: str, body: dict, db: DB, admin: AdminUser):
    cfg = runtime_config.load(db)
    try:
        updated = runtime_config.apply_section_update(cfg, section, body)
    except ValidationError as exc:  # must precede ValueError (it is a subclass)
        raise HTTPException(
            422, "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        ) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if section == "vector_store":
        reset_clients()
    runtime_config.save(db, updated, admin.id)
    changed = sorted(k for k in body if not k.endswith("api_key") or body[k] is not None)
    audit.record(
        db,
        admin,
        "settings.update",
        f"Updated {section} settings",
        entity_type="settings",
        entity_id=section,
        details={"fields": changed},
    )
    return runtime_config.public_view(updated)


class TestIn(BaseModel):
    # Unsaved values from the form; secrets omitted fall back to the stored ones.
    overrides: dict = {}


def _with_overrides(db, section: str, overrides: dict):
    cfg = runtime_config.load(db)
    return runtime_config.apply_section_update(cfg, section, overrides) if overrides else cfg


@router.post("/test/{component}")
async def test_component(component: str, body: TestIn, db: DB, admin: AdminUser):
    section = {
        "llm": "llm",
        "vision": "vision",
        "clinical": "clinical",
        "embeddings": "embeddings",
        "reranker": "reranker",
        "vector_store": "vector_store",
    }.get(component)
    if section is None:
        raise HTTPException(404, "Unknown component")
    try:
        cfg = _with_overrides(db, section, body.overrides)
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    started = time.perf_counter()
    try:
        if component == "llm":
            result = await LLMClient(cfg.llm).test()
        elif component == "clinical":
            from app.ai import registry

            result = await registry.clinical_llm(cfg).test()
        elif component == "vision":
            vcfg = vision_llm_config(cfg.llm, cfg.vision)
            models = await list_models(vcfg.provider, vcfg.base_url, vcfg.api_key)
            result = {
                "ok": True,
                "detail": f"Endpoint reachable; {len(models)} models listed",
                "model_listed": vcfg.model in models or any(m.split(":")[0] == vcfg.model for m in models),
            }
        elif component == "embeddings":
            dim = await Embedder(cfg.embeddings).dimension()
            result = {"ok": True, "dimension": dim, "detail": f"{dim}-dimensional vectors"}
            if cfg.index_dimension and cfg.index_dimension != dim:
                result["warning"] = (
                    f"The library is indexed with {cfg.index_dimension}-d vectors; saving this model requires a re-index."
                )
        elif component == "reranker":
            rr = Reranker(cfg.reranker, cfg.llm)
            if not rr.enabled:
                result = {"ok": True, "detail": "Reranking disabled — fusion order is used."}
            else:
                scores = await rr.score(
                    "blood sugar control",
                    ["HbA1c reflects average glucose over three months.", "The knee joint has menisci."],
                )
                result = {
                    "ok": True,
                    "scores": scores,
                    "detail": "Relevant passage ranked first"
                    if scores[0] > scores[1]
                    else "Warning: ranking looks inverted",
                }
        else:
            if section == "vector_store" and body.overrides:
                reset_clients()
            stats = await VectorStore(cfg.vector_store).stats()
            result = {
                "ok": True,
                "detail": f"{stats['knowledge']} knowledge vectors, {stats['patient']} patient vectors",
                "stats": stats,
            }
    except (ServiceUnavailable, AppError) as exc:
        result = {"ok": False, "error": exc.message}
    except Exception as exc:  # report anything — this is a diagnostic endpoint
        result = {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"}
    result["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return result


class ModelsIn(BaseModel):
    section: str = "llm"
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None


@router.post("/models")
async def discover_models(body: ModelsIn, db: DB, _: AdminUser):
    cfg = runtime_config.load(db)
    sec = getattr(cfg, body.section, None)
    if sec is None or not hasattr(sec, "base_url"):
        raise HTTPException(400, "Unknown section")
    provider = body.provider or getattr(sec, "provider", "openai")
    provider = "ollama" if provider == "ollama" else "openai"
    try:
        models = await list_models(
            provider, body.base_url or sec.base_url, body.api_key or getattr(sec, "api_key", None)
        )
    except ServiceUnavailable as exc:
        return {"ok": False, "error": exc.message, "models": []}
    return {"ok": True, "models": models}


@router.post("/reindex")
async def start_reindex(admin: AdminUser, db: DB):
    if _reindex_state["running"]:
        raise HTTPException(409, "A re-index is already running")
    _reindex_state.update(running=True, done=0, total=0, result=None, error=None, started_at=time.time())
    audit.record(db, admin, "settings.reindex", "Started full re-index")

    async def job():
        sdb = SessionLocal()
        try:

            def progress(done, total):
                _reindex_state.update(done=done, total=total)

            _reindex_state["result"] = await indexing.reindex_all(sdb, progress)
        except Exception as exc:
            _reindex_state["error"] = getattr(exc, "message", None) or str(exc)
        finally:
            _reindex_state["running"] = False
            sdb.close()

    asyncio.get_running_loop().create_task(job())
    return _reindex_state


@router.get("/reindex")
def reindex_status(_: AdminUser):
    return _reindex_state
