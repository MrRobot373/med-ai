"""Document lifecycle: validate → store → parse (vision transcription for images and
scanned pages) → identity check → lab extraction → chunk → index (dense + BM25)."""

from __future__ import annotations

import contextlib
import hashlib
import re
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, Conflict
from app.core.logging import get_logger
from app.db import SessionLocal
from app.ingestion import chunking, identity, labs, parsers
from app.models import Chunk, Document, Observation, Patient, User
from app.rag import indexing
from app.services import audit, runtime_config, vision

logger = get_logger(__name__)

KINDS = (
    "lab_report",
    "imaging",
    "discharge_summary",
    "clinical_note",
    "prescription",
    "referral",
    "pathology",
    "ecg",
    "consent",
    "guideline",
    "protocol",
    "drug_reference",
    "textbook",
    "other",
)

_KIND_HINTS = [
    ("discharge_summary", ("discharge summary", "date of discharge", "discharged on")),
    ("lab_report", ("reference range", "lab report", "laboratory", "specimen", "hba1c", "complete blood count")),
    ("imaging", ("radiology", "impression:", "ct scan", "mri", "x-ray", "ultrasound", "oct ", "fundus")),
    ("pathology", ("histopathology", "biopsy", "cytology")),
    ("ecg", ("ecg", "electrocardiogram", "qrs", "qtc")),
    ("prescription", ("rx", "prescription", "sig:", "dispense")),
    ("referral", ("referral", "referred to", "kindly see")),
    ("clinical_note", ("chief complaint", "history of present illness", "assessment", "plan:")),
]

SCANNED_PAGE_MIN_CHARS = 40
MAX_VISION_PAGES = 20


def guess_kind(text: str, filename: str) -> str:
    hay = (filename + " " + text[:4000]).lower()
    for kind, hints in _KIND_HINTS:
        if any(h in hay for h in hints):
            return kind
    return "other"


_DATE_PATTERNS = [
    re.compile(r"\b(?:date|collected|reported|visit date|report date)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE),
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
]


def guess_date(text: str) -> date | None:
    for pat in _DATE_PATTERNS:
        m = pat.search(text[:5000])
        if m:
            try:
                return date.fromisoformat(m.group(1))
            except ValueError:
                continue
    return None


def create(
    db: Session,
    user: User,
    *,
    data: bytes,
    filename: str,
    declared_mime: str | None,
    scope: str,
    patient: Patient | None = None,
    title: str | None = None,
    kind: str | None = None,
    domain: str | None = None,
    source_org: str | None = None,
    version: str | None = None,
    document_date: date | None = None,
    encounter_id: str | None = None,
) -> Document:
    settings = get_settings()
    if len(data) == 0:
        raise AppError("The file is empty.")
    if len(data) > settings.upload_max_mb * 1024 * 1024:
        raise AppError(f"File exceeds the {settings.upload_max_mb} MB limit.", status_code=413)
    mime = parsers.detect_mime(filename, declared_mime)
    if mime is None:
        raise AppError(
            "Unsupported file type. Use PDF, DOCX, XLSX, CSV, TXT, MD, JSON, PNG, JPG or WEBP.", status_code=415
        )
    if not parsers.verify_magic(parsers.SUPPORTED[mime], data):
        raise AppError("File content does not match its extension.", status_code=415)
    if kind and kind not in KINDS:
        raise AppError(f"Unknown document type '{kind}'.")

    sha = hashlib.sha256(data).hexdigest()
    dup_q = select(Document).where(Document.sha256 == sha, Document.scope == scope, Document.status != "archived")
    if patient:
        dup_q = dup_q.where(Document.patient_id == patient.id)
    existing = db.scalars(dup_q).first()
    if existing:
        raise Conflict(f"This file was already uploaded as '{existing.title}'.", code="duplicate")

    doc_id = uuid.uuid4().hex
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name)[:120] or "file"
    folder = settings.uploads_dir / scope / (patient.id if patient else "library")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{doc_id}_{safe_name}"
    path.write_bytes(data)

    doc = Document(
        id=doc_id,
        scope=scope,
        patient_id=patient.id if patient else None,
        encounter_id=encounter_id,
        title=(title or Path(filename).stem.replace("_", " ")).strip()[:300] or "Untitled",
        filename=Path(filename).name[:300],
        mime_type=mime,
        size_bytes=len(data),
        sha256=sha,
        storage_path=str(path),
        kind=kind or "other",
        domain=domain,
        source_org=source_org,
        version=version,
        document_date=document_date,
        status="processing",
        identity_status="n/a" if scope == "knowledge" else "unverified",
        review_status="pending" if scope == "patient" else "reviewed",
        extraction={"kind_auto": kind is None},
        uploaded_by=user.id,
    )
    db.add(doc)
    db.commit()
    audit.record(
        db,
        user,
        "document.upload",
        f"Uploaded '{doc.title}' ({scope})",
        entity_type="document",
        entity_id=doc.id,
        patient_id=doc.patient_id,
        details={"filename": doc.filename, "size": doc.size_bytes, "mime": mime},
    )
    return doc


async def process(document_id: str) -> None:
    """Background ingestion. Uses its own DB session (runs after the response)."""
    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if doc is None:
            return
        try:
            await _process(db, doc)
        except Exception as exc:
            logger.warning("Ingestion failed for %s", document_id, exc_info=True)
            db.rollback()
            doc = db.get(Document, document_id)
            if doc is not None:
                doc.status = "failed"
                doc.error = getattr(exc, "message", None) or str(exc) or exc.__class__.__name__
                db.commit()
    finally:
        db.close()


async def _process(db: Session, doc: Document) -> None:
    cfg = runtime_config.load(db)
    data = Path(doc.storage_path).read_bytes()
    parsed = parsers.parse(data, doc.mime_type)
    pages = parsed.pages
    methods: dict[int, str] = {p["page"]: "text" for p in pages}

    if parsed.kind == "image":
        text = await vision.transcribe(cfg, data)
        pages = [{"page": 1, "text": text}]
        methods = {1: "vision"}
    elif parsed.kind == "pdf":
        scanned = [p for p in pages if len(p["text"].strip()) < SCANNED_PAGE_MIN_CHARS]
        if scanned:
            import pymupdf

            with pymupdf.open(stream=data, filetype="pdf") as pdf:
                for p in scanned[:MAX_VISION_PAGES]:
                    pix = pdf[p["page"] - 1].get_pixmap(dpi=150)
                    p["text"] = await vision.transcribe(cfg, pix.tobytes("png"))
                    methods[p["page"]] = "vision"

    full_text = "\n\n".join(p["text"] for p in pages)
    if not full_text.strip():
        raise AppError("No readable text could be extracted from this file.")

    if doc.extraction.get("kind_auto") and doc.kind == "other":
        doc.kind = guess_kind(full_text, doc.filename)
    if doc.document_date is None:
        doc.document_date = guess_date(full_text)

    extraction = dict(doc.extraction)
    extraction["page_methods"] = methods
    extraction["characters"] = len(full_text)

    if doc.scope == "patient" and doc.patient_id:
        patient = db.get(Patient, doc.patient_id)
        if doc.identity_status != "match" or not extraction.get("identity_confirmed"):
            result = identity.check(patient, full_text)
            doc.identity_status, doc.identity_detail = result.status, result.detail
        db.execute(delete(Observation).where(Observation.document_id == doc.id))
        # Quarantine: a document that appears to belong to someone else is kept for
        # review but contributes nothing to the chart or to retrieval until confirmed.
        quarantined = doc.identity_status == "mismatch"
        extraction["quarantined"] = quarantined
        doc.is_active = not quarantined
        observed = (
            datetime.combine(doc.document_date, datetime.min.time(), tzinfo=UTC)
            if doc.document_date
            else datetime.now(UTC)
        )
        found = [] if quarantined else labs.extract(pages)
        for o in found:
            db.add(
                Observation(
                    patient_id=doc.patient_id,
                    document_id=doc.id,
                    name=o.name,
                    code=o.code,
                    value_num=o.value_num,
                    value_text=o.value_text,
                    unit=o.unit,
                    ref_low=o.ref_low,
                    ref_high=o.ref_high,
                    ref_text=o.ref_text,
                    flag=o.flag,
                    observed_at=observed,
                    source_page=o.page,
                    source_excerpt=o.excerpt,
                    method="extracted",
                )
            )
        extraction["observations"] = len(found)

    # Re-processing replaces previous chunks.
    old = list(db.scalars(select(Chunk).where(Chunk.document_id == doc.id)))
    if old:
        await indexing.remove_document(db, doc)
        for c in old:
            db.delete(c)
        db.flush()

    drafts = chunking.chunk_pages(pages, cfg.retrieval.chunk_size_tokens, cfg.retrieval.chunk_overlap_tokens)
    chunks = [
        Chunk(
            id=str(uuid.uuid4()),
            document_id=doc.id,
            scope=doc.scope,
            patient_id=doc.patient_id,
            ordinal=i,
            page=d.page,
            section=d.section,
            text=d.text,
            token_count=d.tokens,
        )
        for i, d in enumerate(drafts)
    ]
    db.add_all(chunks)
    db.flush()
    await indexing.index_chunks(db, doc, chunks)

    doc.page_count = len(pages)
    doc.chunk_count = len(chunks)
    doc.extraction = extraction
    doc.status = "ready"
    doc.error = None
    db.commit()


async def remove(db: Session, user: User, doc: Document) -> None:
    await indexing.remove_document(db, doc)
    with contextlib.suppress(OSError):
        Path(doc.storage_path).unlink(missing_ok=True)
    title, patient_id, doc_id = doc.title, doc.patient_id, doc.id
    db.delete(doc)
    db.commit()
    audit.record(
        db,
        user,
        "document.delete",
        f"Deleted '{title}'",
        entity_type="document",
        entity_id=doc_id,
        patient_id=patient_id,
    )


def full_text(db: Session, doc: Document) -> str:
    chunks = db.scalars(select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.ordinal))
    return "\n\n".join(c.text for c in chunks)
