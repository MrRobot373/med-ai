"""Writes chunks into both indexes (vectors + BM25) and keeps them consistent."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import registry
from app.core.logging import get_logger
from app.models import Chunk, Document
from app.rag import lexical
from app.services import runtime_config

logger = get_logger(__name__)


async def index_chunks(db: Session, document: Document, chunks: list[Chunk]) -> None:
    cfg = runtime_config.load(db)
    status = runtime_config.index_status(cfg)
    if status["reindex_required"]:
        _reindex_needed()
    embedder = registry.embedder(cfg)
    vectors = await embedder.embed_documents([c.text for c in chunks]) if chunks else []
    if vectors and cfg.index_signature is None:
        cfg = cfg.model_copy(
            update={"index_signature": runtime_config.embedding_signature(cfg), "index_dimension": len(vectors[0])}
        )
        runtime_config.save(db, cfg)
    payloads = [
        {
            "document_id": document.id,
            "patient_id": document.patient_id,
            "scope": document.scope,
            "domain": document.domain,
            "kind": document.kind,
        }
        for _ in chunks
    ]
    await registry.vector_store(cfg).upsert(document.scope, [c.id for c in chunks], vectors, payloads)
    lexical.index_chunks(db, [(c.id, c.text) for c in chunks])


def _reindex_needed():
    from app.core.errors import ServiceUnavailable

    raise ServiceUnavailable(
        "The embedding model changed since the library was indexed. Re-index from Settings → Retrieval first.",
        code="reindex_required",
    )


async def remove_document(db: Session, document: Document) -> None:
    cfg = runtime_config.load(db)
    chunk_ids = list(db.scalars(select(Chunk.id).where(Chunk.document_id == document.id)))
    lexical.delete_chunks(db, chunk_ids)
    try:
        await registry.vector_store(cfg).delete_document(document.scope, document.id)
    except Exception:
        logger.warning("Vector deletion failed for document %s", document.id, exc_info=True)


async def reindex_all(db: Session, progress=None) -> dict:
    """Drop and rebuild every vector from the stored chunk text (after changing the
    embedding model). BM25 rows are untouched — they don't depend on the embedder."""
    cfg = runtime_config.load(db)
    store = registry.vector_store(cfg)
    embedder = registry.embedder(cfg)
    dimension = await embedder.dimension()
    await store.drop_all()
    docs = list(db.scalars(select(Document).where(Document.status == "ready")))
    total = 0
    for i, doc in enumerate(docs):
        chunks = list(db.scalars(select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.ordinal)))
        if not chunks:
            continue
        vectors = await embedder.embed_documents([c.text for c in chunks])
        payloads = [
            {
                "document_id": doc.id,
                "patient_id": doc.patient_id,
                "scope": doc.scope,
                "domain": doc.domain,
                "kind": doc.kind,
            }
            for _ in chunks
        ]
        await store.upsert(doc.scope, [c.id for c in chunks], vectors, payloads)
        total += len(chunks)
        if progress:
            progress(i + 1, len(docs))
    cfg = runtime_config.load(db).model_copy(
        update={"index_signature": runtime_config.embedding_signature(cfg), "index_dimension": dimension}
    )
    runtime_config.save(db, cfg)
    return {"documents": len(docs), "chunks": total, "dimension": dimension}
