"""Embedding providers behind one interface: Ollama `/api/embed`, OpenAI-compatible
`/embeddings`, or an in-process sentence-transformers model. The vector dimension is
always detected from real output, never assumed."""

from __future__ import annotations

import asyncio
import math
import threading

import httpx

from app.core.errors import ServiceUnavailable
from app.services.runtime_config import EmbeddingConfig


class EmbeddingError(ServiceUnavailable):
    pass


_local_models: dict[tuple[str, str], object] = {}
_local_lock = threading.Lock()


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class Embedder:
    def __init__(self, cfg: EmbeddingConfig):
        self.cfg = cfg

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.cfg.batch_size):
            out.extend(await self._embed(texts[i : i + self.cfg.batch_size]))
        return [_normalize(v) for v in out]

    async def embed_query(self, text: str) -> list[float]:
        query = f"{self.cfg.query_instruction}{text}" if self.cfg.query_instruction else text
        return _normalize((await self._embed([query]))[0])

    async def dimension(self) -> int:
        return len(await self.embed_query("dimension probe"))

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.cfg.provider == "local":
            return await asyncio.to_thread(self._local_embed, texts)
        base = self.cfg.base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {self.cfg.api_key}"} if self.cfg.api_key else {}
        if self.cfg.provider == "ollama":
            url, payload = f"{base}/api/embed", {"model": self.cfg.model, "input": texts}
        else:
            url, payload = f"{base}/embeddings", {"model": self.cfg.model, "input": texts}
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise EmbeddingError(f"Cannot reach the embedding service at {url} ({exc.__class__.__name__}).") from exc
        if resp.status_code >= 400:
            raise EmbeddingError(f"Embedding service error (HTTP {resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        if self.cfg.provider == "ollama":
            vectors = data.get("embeddings") or []
        else:
            vectors = [d["embedding"] for d in sorted(data.get("data", []), key=lambda d: d.get("index", 0))]
        if len(vectors) != len(texts):
            raise EmbeddingError("Embedding service returned an unexpected number of vectors.")
        return vectors

    def _local_embed(self, texts: list[str]) -> list[list[float]]:
        key = (self.cfg.model, self.cfg.device)
        with _local_lock:
            model = _local_models.get(key)
            if model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError as exc:
                    raise EmbeddingError(
                        'In-process embeddings need the optional dependency: pip install -e ".[local-models]"'
                    ) from exc
                model = SentenceTransformer(self.cfg.model, device=self.cfg.device)
                _local_models[key] = model
        return [list(map(float, v)) for v in model.encode(texts, batch_size=self.cfg.batch_size)]  # type: ignore[attr-defined]
