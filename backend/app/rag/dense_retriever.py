"""Dense (embedding-similarity) retrieval — spec §43 Stage 5."""

from __future__ import annotations

from dataclasses import dataclass

from qdrant_client.http import models as qmodels

from app.config.settings import Settings
from app.models.chunk import PATIENT_SCOPED_COLLECTIONS, ChunkCollection
from app.rag.embeddings import embed_query
from app.rag.qdrant_setup import get_qdrant_client


@dataclass
class DenseHit:
    chunk_id: str
    score: float


def dense_search(
    query: str,
    collection: ChunkCollection,
    settings: Settings,
    patient_id: str | None = None,
    top_k: int | None = None,
) -> list[DenseHit]:
    """Patient filtering is mandatory, not optional (spec §16): querying any
    patient-scoped collection (`patient_documents`, `patient_vision`) without a
    `patient_id` raises rather than silently searching across every patient's chunks."""
    if collection in PATIENT_SCOPED_COLLECTIONS and not patient_id:
        raise ValueError(f"patient_id is required when searching the {collection.value} collection")

    client = get_qdrant_client(settings)
    query_vector = embed_query(query, settings)
    query_filter = None
    if patient_id:
        query_filter = qmodels.Filter(
            must=[qmodels.FieldCondition(key="patient_id", match=qmodels.MatchValue(value=patient_id))]
        )

    results = client.query_points(
        collection_name=collection.value,
        query=query_vector,
        query_filter=query_filter,
        limit=top_k or settings.rag_dense_top_k,
        with_payload=False,
    ).points

    return [DenseHit(chunk_id=str(point.id), score=point.score) for point in results]
