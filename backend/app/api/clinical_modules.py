"""Clinical modules endpoints (spec §104, §63). Every generation-triggering endpoint
requires `WriteUser` (real Ollama calls, same rationale as chat/vision); reading
already-generated drafts only requires `CurrentUser` — any authenticated clinician can
see a patient's drafts, matching how conditions/medications/reports are shared chart
content rather than one user's private history (see services/clinical_modules.py).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.common import get_patient_or_404
from app.api.deps import DbDep, SettingsDep
from app.auth.dependencies import CurrentUser, WriteUser
from app.models.clinical_module_run import ClinicalModuleRun, ClinicalModuleType
from app.models.encounter import Encounter
from app.models.report import Report
from app.schemas.clinical_modules import (
    ClinicalModuleRunOut,
    DifferentialRequest,
    EntityExtractionRequest,
    GuidelineQARequest,
    ReportComparisonRequest,
    SOAPRequest,
    SummaryRequest,
)
from app.services import clinical_modules as module_service

router = APIRouter(prefix="/api", tags=["clinical-modules"])


def _get_encounter_or_404(db: DbDep, patient_id: str, encounter_id: str) -> Encounter:
    encounter = db.get(Encounter, encounter_id)
    if encounter is None or encounter.patient_id != patient_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encounter not found")
    return encounter


def _get_report_or_404(db: DbDep, patient_id: str, report_id: str) -> Report:
    report = db.get(Report, report_id)
    if report is None or report.patient_id != patient_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


def _to_out(run: ClinicalModuleRun) -> ClinicalModuleRunOut:
    return ClinicalModuleRunOut.model_validate(run)


@router.post("/patients/{patient_id}/clinical/summary", response_model=ClinicalModuleRunOut)
async def create_summary(patient_id: str, payload: SummaryRequest, db: DbDep, settings: SettingsDep, current_user: WriteUser) -> ClinicalModuleRunOut:
    patient = get_patient_or_404(db, patient_id)
    encounter = _get_encounter_or_404(db, patient_id, payload.encounter_id) if payload.encounter_id else None
    run = await module_service.run_summary(db, settings, patient, payload.summary_type, encounter, current_user.id)
    return _to_out(run)


@router.post("/patients/{patient_id}/clinical/soap", response_model=ClinicalModuleRunOut)
async def create_soap(patient_id: str, payload: SOAPRequest, db: DbDep, settings: SettingsDep, current_user: WriteUser) -> ClinicalModuleRunOut:
    patient = get_patient_or_404(db, patient_id)
    encounter = _get_encounter_or_404(db, patient_id, payload.encounter_id)
    run = await module_service.run_soap(db, settings, patient, encounter, current_user.id)
    return _to_out(run)


@router.post("/patients/{patient_id}/clinical/entities", response_model=ClinicalModuleRunOut)
async def create_entity_extraction(
    patient_id: str, payload: EntityExtractionRequest, db: DbDep, settings: SettingsDep, current_user: WriteUser
) -> ClinicalModuleRunOut:
    patient = get_patient_or_404(db, patient_id)
    report = _get_report_or_404(db, patient_id, payload.report_id) if payload.report_id else None
    encounter = _get_encounter_or_404(db, patient_id, payload.encounter_id) if payload.encounter_id else None
    try:
        run = await module_service.run_entity_extraction(db, settings, patient, report, encounter, current_user.id)
    except module_service.ClinicalModuleValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return _to_out(run)


@router.post("/patients/{patient_id}/clinical/differential", response_model=ClinicalModuleRunOut)
async def create_differential(
    patient_id: str, payload: DifferentialRequest, db: DbDep, settings: SettingsDep, current_user: WriteUser
) -> ClinicalModuleRunOut:
    patient = get_patient_or_404(db, patient_id)
    encounter = _get_encounter_or_404(db, patient_id, payload.encounter_id) if payload.encounter_id else None
    run = await module_service.run_differential(db, settings, patient, encounter, current_user.id)
    return _to_out(run)


@router.post("/patients/{patient_id}/clinical/report-comparison", response_model=ClinicalModuleRunOut)
async def create_report_comparison(
    patient_id: str, payload: ReportComparisonRequest, db: DbDep, settings: SettingsDep, current_user: WriteUser
) -> ClinicalModuleRunOut:
    patient = get_patient_or_404(db, patient_id)
    previous_report = _get_report_or_404(db, patient_id, payload.previous_report_id)
    current_report = _get_report_or_404(db, patient_id, payload.current_report_id)
    run = await module_service.run_report_comparison(db, settings, patient, previous_report, current_report, current_user.id)
    return _to_out(run)


@router.post("/clinical/guideline-qa", response_model=ClinicalModuleRunOut)
async def create_guideline_qa(payload: GuidelineQARequest, db: DbDep, settings: SettingsDep, current_user: WriteUser) -> ClinicalModuleRunOut:
    run = await module_service.run_guideline_qa(db, settings, payload.question, current_user.id)
    return _to_out(run)


@router.get("/patients/{patient_id}/clinical/runs", response_model=list[ClinicalModuleRunOut])
def list_patient_runs(
    patient_id: str, db: DbDep, _current_user: CurrentUser, module_type: ClinicalModuleType | None = None
) -> list[ClinicalModuleRunOut]:
    get_patient_or_404(db, patient_id)
    runs = module_service.list_runs(db, patient_id=patient_id, module_type=module_type)
    return [_to_out(r) for r in runs]


@router.get("/clinical/runs", response_model=list[ClinicalModuleRunOut])
def list_global_runs(db: DbDep, _current_user: CurrentUser, module_type: ClinicalModuleType | None = None) -> list[ClinicalModuleRunOut]:
    """Currently only meaningful for guideline_qa (patient_id is NULL) — patient-scoped
    module history is fetched per-patient via the route above, which also enforces the
    patient actually exists."""
    runs = module_service.list_runs(db, patient_id=None, module_type=module_type)
    return [_to_out(r) for r in runs]


@router.get("/clinical/runs/{run_id}", response_model=ClinicalModuleRunOut)
def get_run(run_id: str, db: DbDep, _current_user: CurrentUser) -> ClinicalModuleRunOut:
    run = module_service.get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return _to_out(run)
