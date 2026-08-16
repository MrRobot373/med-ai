"""Vision AI endpoints (spec §104, §58-61). Reads use `CurrentUser`; triggering
analysis or a comparison invokes real generation against the shared Ollama model —
same write-gating rationale as sending a chat message (Phase 08) — so both use
`WriteUser`.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status

from app.api.common import get_patient_or_404
from app.api.deps import DbDep, SettingsDep
from app.auth.dependencies import CurrentUser, WriteUser
from app.models.report import Report
from app.models.vision_analysis import VisionAnalysis
from app.schemas.vision import (
    ComparisonEvidenceOut,
    VisionAnalysisOut,
    VisionCompareRequest,
    VisionCompareResponse,
)
from app.services import reports as report_service
from app.services import vision as vision_service

router = APIRouter(prefix="/api", tags=["vision"])


def _get_report_or_404(db: DbDep, report_id: str) -> Report:
    report = report_service.get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


def _to_out(report_id: str, row: VisionAnalysis) -> VisionAnalysisOut:
    payload = json.loads(row.payload) if row.payload else {}
    return VisionAnalysisOut(
        report_id=report_id,
        status=row.status,
        model=row.model,
        analysis_error=row.analysis_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
        **payload,
    )


@router.get("/reports/{report_id}/vision", response_model=VisionAnalysisOut)
def get_vision_analysis(report_id: str, db: DbDep, _current_user: CurrentUser) -> VisionAnalysisOut:
    _get_report_or_404(db, report_id)
    row = vision_service.get_analysis(db, report_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No vision analysis has been run for this report yet"
        )
    return _to_out(report_id, row)


@router.post("/reports/{report_id}/vision/analyze", response_model=VisionAnalysisOut)
async def analyze_report(report_id: str, db: DbDep, settings: SettingsDep, _current_user: WriteUser) -> VisionAnalysisOut:
    report = _get_report_or_404(db, report_id)
    row = await vision_service.run_analysis(db, settings, report)
    return _to_out(report_id, row)


@router.post("/patients/{patient_id}/vision/compare", response_model=VisionCompareResponse)
async def compare_vision(
    patient_id: str, payload: VisionCompareRequest, db: DbDep, settings: SettingsDep, _current_user: WriteUser
) -> VisionCompareResponse:
    get_patient_or_404(db, patient_id)
    previous_report = _get_report_or_404(db, payload.previous_report_id)
    current_report = _get_report_or_404(db, payload.current_report_id)

    for report in (previous_report, current_report):
        if report.patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Both images must belong to the patient in the URL",
            )

    try:
        result, evidence = await vision_service.compare_reports(db, settings, previous_report, current_report)
    except vision_service.ReportsNotComparableError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return VisionCompareResponse(
        previous_report_id=previous_report.id,
        current_report_id=current_report.id,
        previous_findings=result.previous_findings,
        current_findings=result.current_findings,
        observable_changes=result.observable_changes,
        differences=result.differences,
        limitations=result.limitations,
        clinical_evidence=[
            ComparisonEvidenceOut(source_title=e.source_title, page=e.page, section=e.section, excerpt=e.excerpt)
            for e in evidence
        ],
    )
