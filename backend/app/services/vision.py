"""Vision analysis persistence + orchestration (spec §58-61). `api/vision.py` calls
into this; `app/vision/analyzer.py` has the actual Ollama-calling logic and knows
nothing about SQLAlchemy, reports, or Qdrant indexing.
"""

from __future__ import annotations

from sqlalchemy.orm import Session as DbSession

from app.config.settings import Settings
from app.ingestion import dicom as dicom_module
from app.ingestion.storage import file_path_for
from app.logging import get_logger
from app.models.chunk import ChunkCollection
from app.models.report import PatientMatchStatus, Report
from app.models.vision_analysis import VisionAnalysis, VisionAnalysisStatus
from app.rag.indexing import index_document
from app.rag.pipeline import retrieve
from app.vision.analyzer import VisionComparison, VisionObservation, analyze_image, compare_images

logger = get_logger(__name__)

_ANALYZABLE_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}


class NotAnalyzableError(Exception):
    """Raised when a report's file type/content isn't something vision analysis can
    run against at all (spec §60's NOT_APPLICABLE distinction) — e.g. a non-image
    report, or a DICOM file whose pixel data couldn't be decoded into a preview."""


def get_analysis(db: DbSession, report_id: str) -> VisionAnalysis | None:
    return db.query(VisionAnalysis).filter(VisionAnalysis.report_id == report_id).first()


def _image_bytes_for(settings: Settings, report: Report) -> bytes:
    """Returns real, analyzable image bytes for a report, or raises
    `NotAnalyzableError` — never silently substitutes different content."""
    path = file_path_for(settings, report)
    if not path.exists():
        raise NotAnalyzableError("Stored file not found")
    content = path.read_bytes()

    if report.mime_type in _ANALYZABLE_IMAGE_TYPES:
        return content

    if report.mime_type == "application/dicom":
        preview = dicom_module.render_preview_png(content)
        if preview is None:
            raise NotAnalyzableError("DICOM pixel data could not be decoded into a preview image")
        return preview

    raise NotAnalyzableError(f"Vision analysis does not apply to mime type '{report.mime_type}'")


def _observation_text(obs: VisionObservation) -> str:
    """Normalized text for image-to-RAG indexing (spec §59's "structured
    observations -> clinical entity extraction -> RAG query generation" stages) —
    plain labeled lines, not the raw JSON, so it reads like ordinary retrievable
    clinical text rather than a data dump."""
    lines = []
    if obs.image_type:
        lines.append(f"Image type: {obs.image_type}")
    if obs.visible_text:
        lines.append("Visible text: " + "; ".join(obs.visible_text))
    if obs.observations:
        lines.append("Observations: " + "; ".join(obs.observations))
    if obs.measurements_visible:
        lines.append("Measurements visible: " + "; ".join(obs.measurements_visible))
    if obs.clinical_entities:
        lines.append("Clinical entities: " + "; ".join(obs.clinical_entities))
    if obs.quality_limitations:
        lines.append("Image quality limitations: " + "; ".join(obs.quality_limitations))
    if obs.uncertainties:
        lines.append("Uncertainties: " + "; ".join(obs.uncertainties))
    return "\n".join(lines)


def _get_or_create(db: DbSession, report_id: str) -> VisionAnalysis:
    existing = get_analysis(db, report_id)
    if existing:
        return existing
    row = VisionAnalysis(report_id=report_id, status=VisionAnalysisStatus.FAILED)
    db.add(row)
    return row


async def run_analysis(db: DbSession, settings: Settings, report: Report) -> VisionAnalysis:
    """Idempotent per report (spec's own "re-running never accumulates" convention,
    same as `index_document`): a re-run updates the existing row and, on success,
    re-indexes into `patient_vision` (which itself replaces any prior chunks for this
    report) rather than creating a parallel history."""
    row = _get_or_create(db, report.id)

    try:
        image_bytes = _image_bytes_for(settings, report)
    except NotAnalyzableError as exc:
        row.status = VisionAnalysisStatus.NOT_APPLICABLE
        row.analysis_error = str(exc)
        row.payload = None
        db.commit()
        return row

    result = await analyze_image(image_bytes, settings)
    if result is None:
        row.status = VisionAnalysisStatus.FAILED
        row.analysis_error = "Vision model did not return valid structured output after retry"
        row.model = settings.ollama_model
        db.commit()
        return row

    row.status = VisionAnalysisStatus.SUCCESS
    row.model = settings.ollama_model
    row.payload = result.model_dump_json()
    row.analysis_error = None
    db.commit()

    _index_observation(db, settings, report, result)
    return row


def _index_observation(db: DbSession, settings: Settings, report: Report, result: VisionObservation) -> None:
    # Never index a MISMATCH report — same rule as text reports (spec §16 patient
    # isolation): its content is suspected to belong to a different patient, so
    # indexing it under this patient_id would make it wrongly searchable. Indexing
    # runs once the mismatch is confirmed instead (see `reindex_if_present` below,
    # called from services/reports.py's confirm_patient_match).
    if report.patient_match_status == PatientMatchStatus.MISMATCH:
        return
    text = _observation_text(result)
    if not text.strip():
        return
    try:
        index_document(
            db,
            settings,
            [{"page": 1, "text": text, "method": "vision"}],
            collection=ChunkCollection.PATIENT_VISION,
            source_title=report.title,
            source_filename=report.source_filename,
            file_hash=report.file_hash,
            patient_id=report.patient_id,
            report_id=report.id,
        )
    except Exception:
        # Best-effort per spec §122 — e.g. Qdrant unreachable shouldn't leave the
        # analysis itself un-recorded; it just isn't retrievable in chat until
        # re-indexed.
        logger.warning("Vision indexing failed for report_id=%s", report.id, exc_info=True)
        db.rollback()


def reindex_if_present(db: DbSession, settings: Settings, report: Report) -> None:
    """Called once a previously-MISMATCHED report's identity is confirmed (spec §16)
    — re-indexes an already-successful vision analysis from its stored payload
    without re-calling the (slow, heavy) vision model, matching how
    `services/reports.py` re-indexes text content from `extracted_content` rather
    than re-running OCR."""
    row = get_analysis(db, report.id)
    if row is None or row.status != VisionAnalysisStatus.SUCCESS or not row.payload:
        return
    result = VisionObservation.model_validate_json(row.payload)
    _index_observation(db, settings, report, result)


class ComparisonEvidenceItem:
    """Plain data holder for the deterministic RAG lookup attached to a comparison —
    not a DB row (comparisons are computed live, not persisted; see
    docs/architecture.md's Phase 09 section for why)."""

    __slots__ = ("excerpt", "page", "section", "source_title")

    def __init__(self, source_title: str, page: int | None, section: str | None, excerpt: str):
        self.source_title = source_title
        self.page = page
        self.section = section
        self.excerpt = excerpt


class ReportsNotComparableError(Exception):
    pass


async def compare_reports(
    db: DbSession, settings: Settings, previous_report: Report, current_report: Report
) -> tuple[VisionComparison, list[ComparisonEvidenceItem]]:
    """Stateless — computed fresh on every call rather than persisted (spec §61 just
    says "support selecting two patient images" and "show" the comparison; there's no
    requirement to version/cache it, and doing so would need its own migration for a
    feature that's inherently ad-hoc/exploratory). Both images are re-sent to the
    vision model together in one call so the comparison is a genuine joint
    observation, not two independent analyses diffed after the fact."""
    if previous_report.patient_id != current_report.patient_id:
        raise ReportsNotComparableError("Both images must belong to the same patient")

    try:
        previous_bytes = _image_bytes_for(settings, previous_report)
        current_bytes = _image_bytes_for(settings, current_report)
    except NotAnalyzableError as exc:
        raise ReportsNotComparableError(str(exc)) from exc

    result = await compare_images(previous_bytes, current_bytes, settings)
    if result is None:
        raise ReportsNotComparableError("Vision model did not return a valid comparison after retry")

    evidence: list[ComparisonEvidenceItem] = []
    if result.differences:
        # Spec §61: "where useful, retrieve relevant local knowledge based on
        # extracted differences" — a real, deterministic RAG call against the shared
        # knowledge base, not the model inventing its own "clinical evidence" text.
        query = " ".join(result.differences)
        passages = retrieve(db, query, settings, collection=ChunkCollection.MEDICAL_KNOWLEDGE, max_per_source=2)
        evidence = [ComparisonEvidenceItem(p.source_title, p.page, p.section, p.text[:600]) for p in passages]

    return result, evidence
