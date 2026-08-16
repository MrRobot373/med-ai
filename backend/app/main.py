"""FastAPI application entrypoint.

Routers are added incrementally per phase (see docs/architecture.md for the build
sequence) and registered the same way: `app.include_router(...)`.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.clinical_modules import router as clinical_modules_router
from app.api.dashboard import router as dashboard_router
from app.api.feedback import router as feedback_router
from app.api.health import router as health_router
from app.api.knowledge import router as knowledge_router
from app.api.patients import router as patients_router
from app.api.reports import router as reports_router
from app.api.research import router as research_router
from app.api.vision import router as vision_router
from app.config.settings import get_settings
from app.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("GMS Clinical AI backend starting (env=%s)", settings.app_env)
    yield
    logger.info("GMS Clinical AI backend shutting down")


app = FastAPI(
    title="GMS Clinical AI",
    description="Local-first multimodal clinical RAG & decision-support platform.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(patients_router)
app.include_router(reports_router)
app.include_router(chat_router)
app.include_router(vision_router)
app.include_router(clinical_modules_router)
app.include_router(research_router)
app.include_router(knowledge_router)
app.include_router(audit_router)
app.include_router(feedback_router)
app.include_router(dashboard_router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"name": "GMS Clinical AI", "status": "running", "docs": "/docs"}
