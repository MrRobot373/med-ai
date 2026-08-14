"""Report upload/ingestion service (spec §29/§31)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.config.settings import Settings
from app.db.session import SessionLocal
from app.ingestion import validators
from app.ingestion.pipeline import run_ingestion
from app.ingestion.storage import (
    delete_file,
    generate_stored_filename,
    reports_dir,
    sha256_hex,
    write_file,
)
from app.logging import get_logger
from app.models.ingestion_job import IngestionJob
from app.models.report import ExtractionStatus, IngestionStatus, PatientMatchStatus, Report

logger = get_logger(__name__)


class DuplicateReportError(Exception):
    def __init__(self, existing: Report):
        self.existing = existing
        super().__init__("An identical file has already been uploaded for this patient")


class UploadValidationError(Exception):
    pass


def create_report(
    db: DbSession,
    settings: Settings,
    patient_id: str,
    filename: str,
    content: bytes,
    uploaded_by: str | None,
    allow_duplicate: bool = False,
) -> Report:
    result = validators.validate_upload(
        filename, content[: validators.MAGIC_SNIFF_BYTES], len(content), settings.upload_max_mb
    )
    if not result.ok:
        raise UploadValidationError(result.error)

    file_hash = sha256_hex(content)

    if not allow_duplicate:
        existing = db.scalar(
            select(Report).where(
                Report.patient_id == patient_id,
                Report.file_hash == file_hash,
                Report.archived.is_(False),
            )
        )
        if existing:
            raise DuplicateReportError(existing)

    display_name = validators.sanitize_display_filename(filename)
    stored_filename = generate_stored_filename(result.extension)
    destination = reports_dir(settings, patient_id) / stored_filename
    write_file(destination, content)

    report = Report(
        patient_id=patient_id,
        title=display_name,
        source_filename=display_name,
        stored_filename=stored_filename,
        file_hash=file_hash,
        mime_type=result.mime_type,
        file_size_bytes=len(content),
        ingestion_status=IngestionStatus.QUEUED,
        extraction_status=ExtractionStatus.PENDING,
        patient_match_status=PatientMatchStatus.NOT_CHECKED,
        uploaded_by=uploaded_by,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_report(db: DbSession, report_id: str) -> Report | None:
    return db.get(Report, report_id)


def list_reports(db: DbSession, patient_id: str, include_archived: bool = False) -> list[Report]:
    stmt = select(Report).where(Report.patient_id == patient_id)
    if not include_archived:
        stmt = stmt.where(Report.archived.is_(False))
    stmt = stmt.order_by(Report.report_date.desc().nulls_last(), Report.created_at.desc())
    return list(db.scalars(stmt))


def latest_job(db: DbSession, report_id: str) -> IngestionJob | None:
    stmt = (
        select(IngestionJob)
        .where(IngestionJob.report_id == report_id)
        .order_by(IngestionJob.created_at.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def archive_report(db: DbSession, report: Report) -> Report:
    report.archived = True
    db.commit()
    db.refresh(report)
    return report


def confirm_patient_match(db: DbSession, report: Report, reviewed_by: str) -> Report:
    report.patient_match_status = PatientMatchStatus.MATCHED
    report.identity_reviewed_by = reviewed_by
    report.identity_reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(report)
    return report


def file_path_for(settings: Settings, report: Report) -> Path:
    return reports_dir(settings, report.patient_id) / report.stored_filename


def delete_report_and_file(db: DbSession, settings: Settings, report: Report) -> None:
    delete_file(file_path_for(settings, report))
    db.delete(report)
    db.commit()


def run_ingestion_task(report_id: str, settings: Settings) -> None:
    """The actual `BackgroundTasks` callable — opens its OWN db session rather than
    reusing the request's, since the request's session is closed by the time a
    background task runs (spec-agnostic FastAPI/Starlette lifecycle detail, not
    something safe to assume away)."""
    db = SessionLocal()
    try:
        run_ingestion(db, report_id, settings)
    except Exception:
        logger.exception("Unhandled error running ingestion task for report_id=%s", report_id)
    finally:
        db.close()
