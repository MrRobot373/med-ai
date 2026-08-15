"""Indexes a document's already-extracted text into both Qdrant (vectors) and SQLite
(`chunks` — the canonical text store BM25 and citations read from). Shared by report
ingestion (`patient_documents`, patient-scoped) and `scripts/ingest_knowledge.py`
(`medical_knowledge`, unscoped) — same function either way, just a different
collection/patient_id, matching spec's own ingestion pipeline diagram (§29: "RAG
chunking -> Embedding -> Qdrant indexing" as the pipeline's final stages).
"""

from __future__ import annotations

import uuid

from qdrant_client.http import models as qmodels
from sqlalchemy.orm import Session as DbSession

from app.config.settings import Settings
from app.ingestion.chunking import chunk_pages
from app.logging import get_logger
from app.models.chunk import Chunk, ChunkCollection
from app.rag.embeddings import embed_documents
from app.rag.qdrant_setup import ensure_collection, get_qdrant_client

logger = get_logger(__name__)


def index_document(
    db: DbSession,
    settings: Settings,
    pages: list[dict],
    collection: ChunkCollection,
    source_title: str,
    source_filename: str | None = None,
    file_hash: str | None = None,
    patient_id: str | None = None,
    report_id: str | None = None,
) -> list[Chunk]:
    """Idempotent per source: deletes any chunks previously indexed for this exact
    source (by `report_id`, or by `file_hash` for knowledge documents) first, so
    re-running ingestion never accumulates duplicate/stale vector points — spec §31's
    "do not create duplicate [] unnecessarily" applies to the vector index too, not
    just the file upload it was originally written for."""
    delete_indexed_source(db, settings, collection, report_id=report_id, file_hash=file_hash)

    chunk_results = chunk_pages(
        pages,
        document_title=source_title,
        target_tokens=settings.rag_chunk_target_tokens,
        overlap_tokens=settings.rag_chunk_overlap_tokens,
    )
    if not chunk_results:
        return []

    embeddings = embed_documents([c.text for c in chunk_results], settings)

    client = get_qdrant_client(settings)
    ensure_collection(client, collection.value, embeddings.dimension)

    rows: list[Chunk] = []
    points: list[qmodels.PointStruct] = []
    for chunk_result, vector in zip(chunk_results, embeddings.vectors, strict=True):
        chunk_id = str(uuid.uuid4())
        row = Chunk(
            id=chunk_id,
            collection=collection,
            patient_id=patient_id,
            report_id=report_id,
            source_title=source_title,
            source_filename=source_filename,
            file_hash=file_hash,
            page=chunk_result.page,
            section=chunk_result.section,
            chunk_index=chunk_result.chunk_index,
            text=chunk_result.raw_text,
            token_count=chunk_result.token_count,
        )
        db.add(row)
        rows.append(row)
        points.append(
            qmodels.PointStruct(
                id=chunk_id,
                vector=vector,
                # Payload mirrors the filterable metadata (spec §45) — patient_id is
                # the mandatory one (spec §16); the rest just avoid a SQLite round
                # trip for display-only fields a caller may want straight off the hit.
                payload={
                    "patient_id": patient_id,
                    "report_id": report_id,
                    "collection": collection.value,
                    "source_title": source_title,
                    "page": chunk_result.page,
                    "section": chunk_result.section,
                },
            )
        )

    db.commit()
    client.upsert(collection_name=collection.value, points=points)
    return rows


def delete_indexed_source(
    db: DbSession,
    settings: Settings,
    collection: ChunkCollection,
    report_id: str | None = None,
    file_hash: str | None = None,
) -> None:
    """Public so callers outside indexing itself (archiving/deleting a report) can
    deindex it too — a report a clinician archived as wrong/duplicate should stop
    being retrievable, not linger searchable forever."""
    query = db.query(Chunk).filter(Chunk.collection == collection)
    if report_id:
        query = query.filter(Chunk.report_id == report_id)
    elif file_hash:
        query = query.filter(Chunk.file_hash == file_hash)
    else:
        return  # nothing to scope the delete to — never delete indiscriminately

    existing_ids = [row.id for row in query.all()]
    if not existing_ids:
        return
    query.delete(synchronize_session=False)
    db.commit()

    client = get_qdrant_client(settings)
    try:
        client.delete(collection_name=collection.value, points_selector=qmodels.PointIdsList(points=existing_ids))
    except Exception:
        # The collection may not exist yet on a first-ever index — nothing to delete
        # from it. Logged (not silently swallowed) since any other cause here would
        # leave stale Qdrant points behind a deleted SQLite row.
        logger.warning("Failed to delete Qdrant points for collection=%s", collection.value, exc_info=True)
