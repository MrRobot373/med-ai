"""Real system health endpoints (spec §84).

Every field is computed from a live check performed during the request — never a
hardcoded "Ready" placeholder. If a dependency is down, the endpoint reports that
plainly so the frontend status chip and demo startup script can react honestly
(spec §85/§103: no silent fallback, no fake status).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.config.settings import get_settings
from app.db.session import check_database_reachable
from app.ingestion.ocr import check_ocr_health
from app.integrations.embedding_health import check_embedding_health
from app.integrations.ollama_client import check_ollama_health
from app.integrations.qdrant_client import check_qdrant_health
from app.integrations.reranker_health import check_reranker_health
from app.schemas.health import (
    DatabaseStatus,
    ModelComponentStatus,
    ModelsStatus,
    OllamaStatus,
    OverallHealth,
    QdrantStatus,
)

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", response_model=OverallHealth)
@router.get("/", response_model=OverallHealth, include_in_schema=False)
async def get_overall_health() -> OverallHealth:
    settings = get_settings()

    db_ok, db_error = check_database_reachable()
    ollama = await check_ollama_health(settings)
    qdrant = await check_qdrant_health(settings)

    overall_ok = db_ok and ollama.reachable and ollama.model_available and qdrant.reachable
    return OverallHealth(
        status="ok" if overall_ok else "degraded",
        database=DatabaseStatus(reachable=db_ok, error=db_error),
        ollama=OllamaStatus(
            reachable=ollama.reachable,
            version=ollama.version,
            configured_model=ollama.configured_model,
            model_available=ollama.model_available,
            error=ollama.error,
        ),
        qdrant=QdrantStatus(
            reachable=qdrant.reachable,
            collections=qdrant.collections,
            points_by_collection=qdrant.points_by_collection,
            error=qdrant.error,
        ),
    )


@router.get("/ollama", response_model=OllamaStatus)
async def get_ollama_health() -> OllamaStatus:
    settings = get_settings()
    result = await check_ollama_health(settings)
    return OllamaStatus(
        reachable=result.reachable,
        version=result.version,
        configured_model=result.configured_model,
        model_available=result.model_available,
        error=result.error,
    )


@router.get("/qdrant", response_model=QdrantStatus)
async def get_qdrant_health() -> QdrantStatus:
    settings = get_settings()
    result = await check_qdrant_health(settings)
    return QdrantStatus(
        reachable=result.reachable,
        collections=result.collections,
        points_by_collection=result.points_by_collection,
        error=result.error,
    )


@router.get("/models", response_model=ModelsStatus)
async def get_models_health() -> ModelsStatus:
    settings = get_settings()
    ollama = await check_ollama_health(settings)
    embedding = check_embedding_health(settings)
    reranker = check_reranker_health(settings)
    ocr = check_ocr_health(settings)

    return ModelsStatus(
        llm=OllamaStatus(
            reachable=ollama.reachable,
            version=ollama.version,
            configured_model=ollama.configured_model,
            model_available=ollama.model_available,
            error=ollama.error,
        ),
        embedding=ModelComponentStatus(
            configured_model=embedding.configured_model,
            device=embedding.device,
            status=embedding.status,
            package_installed=embedding.package_installed,
            dimension=embedding.dimension,
            error=embedding.error,
        ),
        reranker=ModelComponentStatus(
            configured_model=reranker.configured_model,
            device=reranker.device,
            status=reranker.status,
            package_installed=reranker.package_installed,
            error=reranker.error,
        ),
        ocr=ModelComponentStatus(
            configured_model="easyocr (en)",
            device="cpu",
            status=ocr.status,
            package_installed=ocr.package_installed,
            error=ocr.error,
        ),
    )
