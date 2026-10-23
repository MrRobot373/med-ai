from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from app.api import ai, audit, auth, care, documents, knowledge, patients, settings, system
from app.core.config import PROJECT_ROOT, get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db import SessionLocal
from app.models import User
from app.services import runtime_config

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
            db.add(
                User(
                    email=s.bootstrap_admin_email.lower(),
                    full_name="Administrator",
                    role="admin",
                    password_hash=hash_password(s.bootstrap_admin_password),
                )
            )
            db.commit()
            logger.warning(
                "Created first administrator %s — change the password after signing in.", s.bootstrap_admin_email
            )
        runtime_config.load(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    configure_logging(s.log_level)
    s.data_dir.mkdir(parents=True, exist_ok=True)
    s.uploads_dir.mkdir(parents=True, exist_ok=True)
    if getattr(app.state, "skip_migrations", False) is False:
        run_migrations()
    bootstrap()
    yield


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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError):
        return JSONResponse({"detail": exc.message, "code": exc.code}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        msgs = []
        for e in exc.errors():
            loc = ".".join(str(x) for x in e["loc"] if x not in ("body", "query", "path"))
            msgs.append(f"{loc}: {e['msg']}" if loc else e["msg"])
        return JSONResponse({"detail": "; ".join(msgs), "code": "validation_error"}, status_code=422)

    for r in (auth, patients, documents, care, knowledge, ai, settings, system, audit):
        app.include_router(r.router)

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
