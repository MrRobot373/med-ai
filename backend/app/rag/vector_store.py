"""Qdrant access. `embedded` mode stores vectors in a local folder (nothing extra to
run); `server` mode talks to a Qdrant server. Two collections: patient documents and
the shared knowledge library — patient vectors are always filtered by patient_id."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.core.config import get_settings
from app.core.errors import ServiceUnavailable
from app.services.runtime_config import VectorStoreConfig

_clients: dict[tuple, QdrantClient] = {}
_lock = threading.RLock()


class VectorStoreError(ServiceUnavailable):
    pass


@dataclass
class VectorHit:
    chunk_id: str
    score: float


def _client(cfg: VectorStoreConfig) -> QdrantClient:
    key = (cfg.mode, cfg.url if cfg.mode == "server" else str(get_settings().vector_dir), cfg.api_key)
    with _lock:
        client = _clients.get(key)
        if client is None:
            if cfg.mode == "server":
                client = QdrantClient(url=cfg.url, api_key=cfg.api_key or None, timeout=30)
            elif str(get_settings().vector_dir) == ":memory:":
                client = QdrantClient(location=":memory:")
            else:
                get_settings().vector_dir.mkdir(parents=True, exist_ok=True)
                client = QdrantClient(path=str(get_settings().vector_dir))
            _clients[key] = client
        return client


def reset_clients() -> None:
    with _lock:
        for client in _clients.values():
            try:
                client.close()
            except Exception:  # pragma: no cover
                pass
        _clients.clear()


def collection_name(cfg: VectorStoreConfig, scope: str) -> str:
    return f"{cfg.collection_prefix}_{'patient' if scope == 'patient' else 'knowledge'}"


class VectorStore:
    def __init__(self, cfg: VectorStoreConfig):
        self.cfg = cfg

    async def _run(self, fn, *args, **kwargs):
        def call():
            with _lock:
                return fn(*args, **kwargs)

        try:
            return await asyncio.to_thread(call)
        except VectorStoreError:
            raise
        except Exception as exc:
            where = self.cfg.url if self.cfg.mode == "server" else "embedded store"
            raise VectorStoreError(f"Vector store error ({where}): {exc}") from exc

    def _ensure(self, scope: str, dimension: int) -> None:
        client = _client(self.cfg)
        name = collection_name(self.cfg, scope)
        if client.collection_exists(name):
            info = client.get_collection(name)
            vectors = info.config.params.vectors
            size = vectors.size if isinstance(vectors, qm.VectorParams) else None
            if size is not None and size != dimension:
                raise VectorStoreError(
                    f"Collection '{name}' holds {size}-dimensional vectors but the embedding model produces "
                    f"{dimension}. Re-index the library from Settings → Retrieval."
                )
            return
        client.create_collection(name, vectors_config=qm.VectorParams(size=dimension, distance=qm.Distance.COSINE))
        if self.cfg.mode == "server":  # payload indexes only exist on a Qdrant server
            for field in ("document_id", "patient_id", "domain"):
                client.create_payload_index(name, field, qm.PayloadSchemaType.KEYWORD)

    async def upsert(self, scope: str, ids: list[str], vectors: list[list[float]], payloads: list[dict]) -> None:
        if not ids:
            return

        def op():
            self._ensure(scope, len(vectors[0]))
            _client(self.cfg).upsert(
                collection_name(self.cfg, scope),
                points=[
                    qm.PointStruct(id=i, vector=v, payload=p) for i, v, p in zip(ids, vectors, payloads, strict=True)
                ],
                wait=True,
            )

        await self._run(op)

    async def search(
        self,
        scope: str,
        vector: list[float],
        limit: int,
        *,
        patient_id: str | None = None,
        document_ids: list[str] | None = None,
        domains: list[str] | None = None,
    ) -> list[VectorHit]:
        if scope == "patient" and not patient_id:
            raise ValueError("Patient-scoped vector search requires a patient_id")

        def op():
            client = _client(self.cfg)
            name = collection_name(self.cfg, scope)
            if not client.collection_exists(name):
                return []
            must: list = []
            if patient_id:
                must.append(qm.FieldCondition(key="patient_id", match=qm.MatchValue(value=patient_id)))
            if document_ids:
                must.append(qm.FieldCondition(key="document_id", match=qm.MatchAny(any=document_ids)))
            if domains:
                must.append(qm.FieldCondition(key="domain", match=qm.MatchAny(any=domains)))
            res = client.query_points(
                name, query=vector, limit=limit, query_filter=qm.Filter(must=must) if must else None
            )
            return [VectorHit(str(p.id), float(p.score)) for p in res.points]

        return await self._run(op)

    async def delete_document(self, scope: str, document_id: str) -> None:
        def op():
            client = _client(self.cfg)
            name = collection_name(self.cfg, scope)
            if client.collection_exists(name):
                client.delete(
                    name,
                    points_selector=qm.FilterSelector(
                        filter=qm.Filter(
                            must=[qm.FieldCondition(key="document_id", match=qm.MatchValue(value=document_id))]
                        )
                    ),
                )

        await self._run(op)

    async def drop_all(self) -> None:
        def op():
            client = _client(self.cfg)
            for scope in ("patient", "knowledge"):
                name = collection_name(self.cfg, scope)
                if client.collection_exists(name):
                    client.delete_collection(name)

        await self._run(op)

    async def stats(self) -> dict:
        def op():
            client = _client(self.cfg)
            out = {}
            for scope in ("patient", "knowledge"):
                name = collection_name(self.cfg, scope)
                out[scope] = client.count(name).count if client.collection_exists(name) else 0
            return out

        return await self._run(op)
