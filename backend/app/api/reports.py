"""Report ingestion endpoints (spec §104 Reports, §29 upload pipeline).

Upload returns immediately with `ingestion_status: queued`; actual parsing/OCR/identity
checking runs in a `BackgroundTask` after the response is sent (spec §122 — a local
persistent-job-table + background worker, not a Celery/Redis queue). The frontend
polls `GET /api/reports/{id}/status` to reflect real progress, never a fake bar.
"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.api.common import get_patient_or_404
from app.api.deps import DbDep, SettingsDep
from app.auth.dependencies import CurrentUser, WriteUser
from app.ingestion import dicom as dicom_module
from app.models.report import Report
from app.schemas.reconciliation import ReconciliationResult
from app.schemas.report import ReportDetail, ReportListItem, ReportPage, ReportStatus
from app.services import reconciliation as reconciliation_service
from app.services import reports as report_service

router = APIRouter(prefix="/api", tags=["reports"])


def _get_report_or_404(db: DbDep, report_id: str) -> Report:
    report = report_service.get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


@router.get("/patients/{patient_id}/reports", response_model=list[ReportListItem])
def list_patient_reports(
    patient_id: str, db: DbDep, _current_user: CurrentUser, include_archived: bool = False
) -> list[ReportListItem]:
    get_patient_or_404(db, patient_id)
    reports = report_service.list_reports(db, patient_id, include_archived=include_archived)
    return [ReportListItem.model_validate(r) for r in reports]


@router.post("/patients/{patient_id}/reports", response_model=ReportListItem, status_code=status.HTTP_201_CREATED)
async def upload_patient_report(
    patient_id: str,
    background_tasks: BackgroundTasks,
    db: DbDep,
    settings: SettingsDep,
    current_user: WriteUser,
    file: Annotated[UploadFile, File()],
    allow_duplicate: bool = False,
) -> ReportListItem:
    get_patient_or_404(db, patient_id)
    content = await file.read()

    try:
        report = report_service.create_report(
            db,
            settings,
            patient_id,
            file.filename or "upload",
            content,
            uploaded_by=current_user.id,
            allow_duplicate=allow_duplicate,
        )
    except report_service.UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except report_service.DuplicateReportError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    background_tasks.add_task(report_service.run_ingestion_task, report.id, settings)
    return ReportListItem.model_validate(report)


@router.get("/reports/{report_id}", response_model=ReportDetail)
def get_report_detail(report_id: str, db: DbDep, _current_user: CurrentUser) -> ReportDetail:
    report = _get_report_or_404(db, report_id)
    pages_raw = json.loads(report.extracted_content) if report.extracted_content else []
    return ReportDetail(
        **ReportListItem.model_validate(report).model_dump(),
        extraction_error=report.extraction_error,
        pages=[ReportPage(**p) for p in pages_raw],
    )


@router.get("/reports/{report_id}/status", response_model=ReportStatus)
def get_report_status(report_id: str, db: DbDep, _current_user: CurrentUser) -> ReportStatus:
    report = _get_report_or_404(db, report_id)
    job = report_service.latest_job(db, report_id)
    return ReportStatus(
        id=report.id,
        ingestion_status=report.ingestion_status,
        extraction_status=report.extraction_status,
        stage=job.stage if job else None,
        error=report.extraction_error or (job.error_message if job else None),
    )


@router.get("/reports/{report_id}/file")
def download_report_file(report_id: str, db: DbDep, settings: SettingsDep, _current_user: CurrentUser) -> FileResponse:
    report = _get_report_or_404(db, report_id)
    path = report_service.file_path_for(settings, report)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found")
    return FileResponse(path, media_type=report.mime_type, filename=report.source_filename)


@router.get("/reports/{report_id}/preview")
def get_report_preview(report_id: str, db: DbDep, settings: SettingsDep, _current_user: CurrentUser) -> Response:
    """DICOM isn't browser-renderable — this generates a flat PNG preview on demand
    (spec §62 "safe preview generation when supported"). Regular images are already
    directly viewable via GET /reports/{id}/file, so this endpoint only applies to
    DICOM."""
    report = _get_report_or_404(db, report_id)
    if report.mime_type != "application/dicom":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preview is only generated for DICOM reports — use /file directly for images",
        )
    path = report_service.file_path_for(settings, report)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found")

    png_bytes = dicom_module.render_preview_png(path.read_bytes())
    if png_bytes is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Preview could not be generated for this DICOM file (unsupported pixel encoding)",
        )
    return Response(content=png_bytes, media_type="image/png")


@router.post("/reports/{report_id}/confirm-match", response_model=ReportListItem)
def confirm_report_match(report_id: str, db: DbDep, settings: SettingsDep, current_user: WriteUser) -> ReportListItem:
    report = _get_report_or_404(db, report_id)
    updated = report_service.confirm_patient_match(db, settings, report, current_user.id)
    return ReportListItem.model_validate(updated)


@router.post("/reports/{report_id}/archive", response_model=ReportListItem)
def archive_report(report_id: str, db: DbDep, settings: SettingsDep, _current_user: WriteUser) -> ReportListItem:
    report = _get_report_or_404(db, report_id)
    updated = report_service.archive_report(db, settings, report)
    return ReportListItem.model_validate(updated)


@router.get("/reports/{report_id}/medication-reconciliation", response_model=ReconciliationResult)
def get_medication_reconciliation(report_id: str, db: DbDep, _current_user: CurrentUser) -> ReconciliationResult:
    """Read-only comparison (spec §36) — never mutates the medication list, so any
    authenticated role may view it (write-gating happens if/when a clinician acts on
    what it surfaces, e.g. adding a newly-detected medication through the normal
    medications endpoint)."""
    report = _get_report_or_404(db, report_id)
    return reconciliation_service.reconcile_report(db, report)
