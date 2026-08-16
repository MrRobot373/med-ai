"""Web Research endpoints (spec §104, §64-72). Read-only status is `CurrentUser`;
the query endpoint invokes real generation (plus real outbound network calls to
external providers when Research Mode is enabled) — `WriteUser`, same rationale as
every other generation-triggering endpoint in this app.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.common import get_patient_or_404
from app.api.deps import DbDep, SettingsDep
from app.auth.dependencies import CurrentUser, WriteUser
from app.models.clinical_module_run import ClinicalModuleRun, ClinicalModuleType
from app.schemas.clinical_modules import ClinicalModuleRunOut
from app.schemas.research import ResearchQueryRequest, ResearchStatusOut
from app.services import clinical_modules as module_service
from app.services import research as research_service

router = APIRouter(prefix="/api/research", tags=["research"])


def _to_out(run: ClinicalModuleRun) -> ClinicalModuleRunOut:
    return ClinicalModuleRunOut.model_validate(run)


@router.get("/status", response_model=ResearchStatusOut)
def get_research_status(settings: SettingsDep, _current_user: CurrentUser) -> ResearchStatusOut:
    """Real capability check, never assumed (spec §103) — mirrors /api/health's own
    honesty: Research Mode being enabled in config doesn't mean SearXNG is actually
    reachable right now, so the two are checked and reported separately."""
    if not settings.enable_research:
        return ResearchStatusOut(enabled=False, searxng_reachable=False, sources_available=[])
    return ResearchStatusOut(
        enabled=True,
        searxng_reachable=research_service.searxng_reachable(settings),
        sources_available=research_service.available_sources(settings),
    )


@router.post("/query", response_model=ClinicalModuleRunOut)
async def query_research(payload: ResearchQueryRequest, db: DbDep, settings: SettingsDep, current_user: WriteUser) -> ClinicalModuleRunOut:
    patient = get_patient_or_404(db, payload.patient_id) if payload.patient_id else None
    if payload.sources and not settings.enable_research:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Research Mode is not enabled for this deployment — external sources cannot be queried",
        )
    run = await research_service.run_research(
        db, settings, payload.question, patient, payload.sources, payload.date_range, payload.prefer_reviews, current_user.id
    )
    return _to_out(run)


@router.get("/runs", response_model=list[ClinicalModuleRunOut])
def list_research_runs(db: DbDep, _current_user: CurrentUser, patient_id: str | None = None) -> list[ClinicalModuleRunOut]:
    runs = module_service.list_runs(db, patient_id=patient_id, module_type=ClinicalModuleType.RESEARCH)
    return [_to_out(r) for r in runs]
