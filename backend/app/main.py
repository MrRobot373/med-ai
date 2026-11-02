from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from app.api import (
    ai,
    audit,
    auth,
    care,
    documents,
    integrations,
    knowledge,
    letters,
    org,
    patient_tools,
    patients,
    rxlib,
    settings,
    system,
    verify,
)
from app.core import passwords
from app.core.config import PROJECT_ROOT, get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db import SessionLocal
from app.middleware import SecurityMiddleware
from app.models import User
from app.services import branches, runtime_config

logger = get_logger(__name__)


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    cfg.set_main_option("sqlalchemy.url", get_settings().resolved_database_url)
    command.upgrade(cfg, "head")


def bootstrap() -> None:
    s = get_settings()
    db = SessionLocal()
    try:
        if not db.scalar(select(func.count()).select_from(User)):
            if s.is_production:
                problems = passwords.validate(
                    s.bootstrap_admin_password, email=s.bootstrap_admin_email, name=s.bootstrap_admin_name
                )
                if problems:
                    raise RuntimeError(
                        "BOOTSTRAP_ADMIN_PASSWORD is not acceptable for a production install: " + " ".join(problems)
                    )
            db.add(
                User(
                    email=s.bootstrap_admin_email.lower(),
                    full_name=s.bootstrap_admin_name,
                    role="admin",
                    password_hash=hash_password(s.bootstrap_admin_password),
                    must_change_password=s.is_production,
                )
            )
            db.commit()
            logger.warning(
                "Created first administrator %s — change the password after signing in.", s.bootstrap_admin_email
            )
        runtime_config.load(db)
        branches.ensure_default(db)
        for u in db.scalars(select(User)):
            branches.ensure_membership(db, u)
        db.commit()
    finally:
        db.close()


async def _recover_documents() -> None:
    """After a crash or power cut, documents left half-processed are processed again (one at a time)."""
    from app.services import documents

    try:
        ids = await asyncio.to_thread(documents.stuck_ids)
        for doc_id in ids:
            logger.info("Resuming processing of document %s", doc_id)
            await documents.process(doc_id)
    except Exception:
        logger.warning("Could not resume interrupted documents", exc_info=True)


async def _webhook_worker() -> None:
    """Sends queued webhook messages (and retries the ones that failed) every few seconds."""
    from app.services import integration

    def tick() -> int:
        db = SessionLocal()
        try:
            return integration.deliver_due(db)
        finally:
            db.close()

    while True:
        await asyncio.sleep(5)
        try:
            await asyncio.to_thread(tick)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Webhook delivery pass failed", exc_info=True)


async def _backup_scheduler() -> None:
    """Takes the daily backup at the clinic's configured time. Checked once a minute."""
    from zoneinfo import ZoneInfo

    from app.services import backup

    tz = ZoneInfo(get_settings().timezone)
    while True:
        await asyncio.sleep(60)
        try:

            def tick() -> None:
                db = SessionLocal()
                try:
                    if backup.due(db, datetime.now(tz)):
                        cfg = runtime_config.load(db).backup
                        r = backup.run_and_record(db, include_vectors=cfg.include_vectors, keep=cfg.keep, by="schedule")
                        logger.info("Scheduled backup written: %s (%d bytes)", r["file"], r["size"])
                finally:
                    db.close()

            await asyncio.to_thread(tick)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Scheduled backup failed", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    configure_logging(s.log_level)
    problems = s.production_problems()
    if problems:
        raise RuntimeError("Refusing to start in production: " + " ".join(problems))
    if s.is_production and not s.cookie_secure and not s.allow_insecure_http:
        logger.warning(
            "COOKIE_SECURE is off in production: sign-in cookies travel unencrypted. Serve the app over HTTPS "
            "(the bundled proxy does this) or set ALLOW_INSECURE_HTTP=true to accept the risk on a closed network."
        )
    s.data_dir.mkdir(parents=True, exist_ok=True)
    s.uploads_dir.mkdir(parents=True, exist_ok=True)
    if getattr(app.state, "skip_migrations", False) is False:
        run_migrations()
    bootstrap()
    tasks: list[asyncio.Task] = []
    if getattr(app.state, "skip_migrations", False) is False:
        tasks.append(asyncio.create_task(_recover_documents()))
        tasks.append(asyncio.create_task(_backup_scheduler()))
        tasks.append(asyncio.create_task(_webhook_worker()))
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()


def create_app(*, skip_migrations: bool = False) -> FastAPI:
    app = FastAPI(
        title="GMS Clinical AI",
        version=system.APP_VERSION,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.skip_migrations = skip_migrations
    app.add_middleware(SecurityMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError):
        return JSONResponse({"detail": exc.message, "code": exc.code, **exc.extra}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        msgs = []
        for e in exc.errors():
            loc = ".".join(str(x) for x in e["loc"] if x not in ("body", "query", "path"))
            msgs.append(f"{loc}: {e['msg']}" if loc else e["msg"])
        return JSONResponse({"detail": "; ".join(msgs), "code": "validation_error"}, status_code=422)

    for r in (
        auth,
        org,
        patient_tools,
        patients,
        documents,
        care,
        knowledge,
        ai,
        settings,
        system,
        audit,
        verify,
        letters,
        rxlib,
    ):
        app.include_router(r.router)
    for sub in (integrations.admin, integrations.partner, integrations.exports):
        app.include_router(sub)

    @app.get("/api/health", tags=["system"])
    def liveness():
        return {"status": "ok", "version": system.APP_VERSION}

    # Production: serve the built frontend from the same origin.
    dist = PROJECT_ROOT / "frontend" / "dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            target = dist / path
            if path and target.is_file() and dist in target.resolve().parents:
                return FileResponse(target)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
