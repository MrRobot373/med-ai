"""Qdrant collection management — spec §14. Creates `medical_knowledge`,
`patient_documents`, and `patient_vision` (`web_cache` joins in Phase 11 — adding a
collection later is just another call to `ensure_collection`, nothing here needs to
change shape).

Vector size is read from the embedding model at setup time (spec §5 "never manually
hardcode vector dimension"), not assumed from the model name.
"""

from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.config.settings import Settings
from app.logging import get_logger
from app.models.chunk import PATIENT_SCOPED_COLLECTIONS

logger = get_logger(__name__)


def get_qdrant_client(settings: Settings) -> QdrantClient:
    # check_compatibility spawns a background thread that pings Qdrant and logs a
    # version-mismatch warning — redundant here since docker-compose.yml already pins
    # an exact, tested Qdrant version (spec §7), and the thread can outlive a short-
    # lived script/test process and log to an already-closed stream on exit.
    return QdrantClient(
        url=settings.qdrant_url, api_key=settings.qdrant_api_key, timeout=10.0, check_compatibility=False
    )


def ensure_collection(client: QdrantClient, name: str, vector_size: int) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if name in existing:
        return
    logger.info("Creating Qdrant collection %s (dim=%s)", name, vector_size)
    client.create_collection(
        collection_name=name,
        vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
    )
    # patient_id is filtered on every patient-scoped query (spec §16 mandatory
    # isolation) — a payload index makes that filter fast instead of a full scan.
    if name in {c.value for c in PATIENT_SCOPED_COLLECTIONS}:
        client.create_payload_index(
            collection_name=name, field_name="patient_id", field_schema=qmodels.PayloadSchemaType.KEYWORD
        )
