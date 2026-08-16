"""Ingestion pipeline orchestration — spec §29.

Runs inside a FastAPI `BackgroundTask` (see api/reports.py) after the upload response
has already been returned, updating `Report`/`IngestionJob` rows stage by stage so the
frontend polls real status instead of a fake progress bar. Never raises past its own
boundary — any failure is captured into the DB rows rather than crashing the worker or
leaving a report stuck in "processing" forever (spec §122).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session as DbSession

from app.config.settings import Settings
from app.ingestion import classification, identity, labs, ocr, pdf, xlsx
from app.ingestion import dicom as dicom_module
from app.ingestion import docx as docx_parser
from app.ingestion import image as image_module
from app.ingestion.storage import reports_dir
from app.logging import get_logger
from app.models.chunk import ChunkCollection
from app.models.ingestion_job import IngestionJob
from app.models.patient import Patient
from app.models.report import ExtractionStatus, IngestionStatus, PatientMatchStatus, Report
from app.rag.indexing import index_document
from app.services import vision as vision_service
from app.services.observations import save_extracted_observations

logger = get_logger(__name__)

_MONTH_NAMES = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
_MONTH_DATE_PATTERN = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(_MONTH_NAMES) + r")\s+(\d{4})\b", re.IGNORECASE
)
_ISO_DATE_PATTERN = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_SLASH_DATE_PATTERN = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def _extract_report_date(text: str) -> date | None:
    """Best-effort only — returns None (never a guessed/fabricated date) when nothing
    matches, per spec §2 "never invent" values."""
    snippet = text[:3000]

    match = _MONTH_DATE_PATTERN.search(snippet)
    if match:
        day, month_name, year = match.groups()
        month = _MONTH_NAMES.index(month_name.lower()) + 1
        try:
            return date(int(year), month, int(day))
        except ValueError:
            pass

    match = _ISO_DATE_PATTERN.search(snippet)
    if match:
        try:
            return date(int(match[1]), int(match[2]), int(match[3]))
        except ValueError:
            pass

    match = _SLASH_DATE_PATTERN.search(snippet)
    if match:
        try:
            return date(int(match[3]), int(match[1]), int(match[2]))
        except ValueError:
            pass

    return None


_VISION_ANALYZABLE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "application/dicom"}


async def run_ingestion(db: DbSession, report_id: str, settings: Settings) -> None:
    report = db.get(Report, report_id)
    if report is None:
        logger.error("Ingestion requested for missing report_id=%s", report_id)
        return

    job = IngestionJob(
        report_id=report.id,
        status=IngestionStatus.PROCESSING,
        stage="extracting_text",
        started_at=datetime.now(UTC),
    )
    db.add(job)
    report.ingestion_status = IngestionStatus.PROCESSING
    db.commit()

    try:
        file_path = reports_dir(settings, report.patient_id) / report.stored_filename
        content = file_path.read_bytes()

        pages, ocr_used, extraction_status = _extract_content(content, report, settings, job, db)
        full_text = "\n".join(p["text"] for p in pages)

        report.extracted_content = json.dumps(pages)
        report.page_count = len(pages)
        report.ocr_used = ocr_used
        report.extraction_status = extraction_status

        job.stage = "classifying"
        db.commit()
        report.report_type = classification.classify_report(report.source_filename, full_text)

        detected_date = _extract_report_date(full_text)
        if detected_date:
            report.report_date = detected_date

        job.stage = "checking_identity"
        db.commit()
        patient = db.get(Patient, report.patient_id)
        detected = identity.detect_identity(full_text)
        report.source_patient_name = detected.name
        report.source_mrn = detected.mrn
        report.patient_match_status = (
            identity.match_patient(detected, patient) if patient else PatientMatchStatus.UNCONFIRMED
        )

        job.stage = "extracting_labs"
        db.commit()
        try:
            extracted_observations = labs.extract_observations(pages)
            save_extracted_observations(db, report, extracted_observations)
        except Exception:
            # Best-effort per spec §122 (never let one stage's failure sink the whole
            # ingestion) — the report's text/identity results already committed above
            # remain valid even if lab extraction itself hits an unexpected error.
            logger.warning("Lab extraction failed for report_id=%s", report_id, exc_info=True)
            db.rollback()

        # Vision analysis (spec §58/§59) — only attempted for mime types it can
        # actually run against; a PDF/DOCX/XLSX report never gets a VisionAnalysis
        # row at all rather than an always-NOT_APPLICABLE one cluttering every report.
        if report.mime_type in _VISION_ANALYZABLE_MIME_TYPES:
            job.stage = "analyzing_image"
            db.commit()
            try:
                await vision_service.run_analysis(db, settings, report)
            except Exception:
                # Best-effort per spec §122 — same rationale as lab extraction above:
                # a vision failure never sinks the rest of ingestion, which already
                # succeeded (text/identity/OCR results committed above remain valid).
                logger.warning("Vision analysis failed for report_id=%s", report_id, exc_info=True)
                db.rollback()

        job.stage = "indexing"
        db.commit()
        # Never index a report flagged MISMATCH (spec §16 patient isolation): its
        # content is suspected to belong to a *different* patient, so indexing it
        # under this one's patient_id would make it searchable in the wrong patient's
        # clinical AI context — exactly what patient isolation exists to prevent.
        # Indexing runs once the mismatch is confirmed instead (see
        # services/reports.py's confirm_patient_match).
        if report.patient_match_status != PatientMatchStatus.MISMATCH:
            try:
                index_document(
                    db,
                    settings,
                    pages,
                    collection=ChunkCollection.PATIENT_DOCUMENTS,
                    source_title=report.title,
                    source_filename=report.source_filename,
                    file_hash=report.file_hash,
                    patient_id=report.patient_id,
                    report_id=report.id,
                )
            except Exception:
                # Best-effort per spec §122 — e.g. Qdrant unreachable shouldn't leave
                # the report stuck; it just isn't retrievable until reindexed.
                logger.warning("RAG indexing failed for report_id=%s", report_id, exc_info=True)
                db.rollback()

        job.stage = "finalizing"
        report.ingestion_status = IngestionStatus.COMPLETED
        job.status = IngestionStatus.COMPLETED
        job.completed_at = datetime.now(UTC)
        db.commit()

    except Exception as exc:
        logger.exception("Ingestion failed for report_id=%s", report_id)
        db.rollback()
        _mark_failed(db, report_id, str(exc))


def _mark_failed(db: DbSession, report_id: str, error: str) -> None:
    report = db.get(Report, report_id)
    job = (
        db.query(IngestionJob)
        .filter(IngestionJob.report_id == report_id)
        .order_by(IngestionJob.created_at.desc())
        .first()
    )
    truncated = error[:2000]
    if report:
        report.ingestion_status = IngestionStatus.FAILED
        report.extraction_status = ExtractionStatus.FAILED
        report.extraction_error = truncated
    if job:
        job.status = IngestionStatus.FAILED
        job.error_message = truncated
        job.completed_at = datetime.now(UTC)
    db.commit()


def _extract_content(
    content: bytes, report: Report, settings: Settings, job: IngestionJob, db: DbSession
) -> tuple[list[dict], bool, ExtractionStatus]:
    ocr_used = False

    if report.mime_type == "application/pdf":
        result = pdf.extract_pdf_text(content)
        ocr_health = ocr.check_ocr_health(settings)
        pages: list[dict] = []
        for page_content in result.pages:
            text, method = page_content.text, "text"
            if len(text) < settings.ocr_min_chars_per_page and ocr_health.status in ("ready", "not_loaded"):
                job.stage = "running_ocr"
                db.commit()
                try:
                    rendered = pdf.render_page_png(content, page_content.page)
                    ocr_result = ocr.run_ocr(rendered)
                    if len(ocr_result.text) > len(text):
                        text, method = ocr_result.text, "ocr"
                        ocr_used = True
                except Exception:
                    logger.warning("OCR failed for page %s", page_content.page, exc_info=True)
            pages.append({"page": page_content.page, "text": text, "method": method})
        status = ExtractionStatus.SUCCESS if any(p["text"].strip() for p in pages) else ExtractionStatus.PARTIAL
        return pages, ocr_used, status

    if report.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        text = docx_parser.extract_docx_text(content)
        status = ExtractionStatus.SUCCESS if text.strip() else ExtractionStatus.PARTIAL
        return [{"page": 1, "text": text, "method": "text"}], False, status

    if report.mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        sheets = xlsx.extract_xlsx_text(content)
        pages = [
            {"page": i + 1, "text": f"[Sheet: {s.sheet_name}]\n{s.text}", "method": "text"}
            for i, s in enumerate(sheets)
        ]
        status = ExtractionStatus.SUCCESS if pages else ExtractionStatus.PARTIAL
        return pages, False, status

    if report.mime_type in ("image/png", "image/jpeg", "image/webp"):
        ocr_health = ocr.check_ocr_health(settings)
        if ocr_health.status not in ("ready", "not_loaded"):
            return [{"page": 1, "text": "", "method": "none"}], False, ExtractionStatus.NOT_APPLICABLE
        job.stage = "running_ocr"
        db.commit()
        try:
            normalized = image_module.normalize_image(content)
            ocr_result = ocr.run_ocr(normalized)
            status = ExtractionStatus.SUCCESS if ocr_result.text.strip() else ExtractionStatus.PARTIAL
            return [{"page": 1, "text": ocr_result.text, "method": "ocr"}], True, status
        except Exception:
            logger.warning("OCR failed for image report", exc_info=True)
            return [{"page": 1, "text": "", "method": "ocr"}], False, ExtractionStatus.FAILED

    if report.mime_type == "application/dicom":
        summary = dicom_module.read_summary(content)
        lines = [
            f"Modality: {summary.modality}" if summary.modality else None,
            f"Study: {summary.study_description}" if summary.study_description else None,
            f"Series: {summary.series_description}" if summary.series_description else None,
        ]
        text = "\n".join(line for line in lines if line)
        return [{"page": 1, "text": text, "method": "metadata"}], False, ExtractionStatus.SUCCESS

    return [{"page": 1, "text": "", "method": "none"}], False, ExtractionStatus.NOT_APPLICABLE
