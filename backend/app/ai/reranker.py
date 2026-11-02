"""Rerankers: none (keep fusion order), remote HTTP (`/rerank` — Cohere/Jina/vLLM/
llama.cpp/TEI shapes), in-process cross-encoder, or the main LLM as a judge."""

from __future__ import annotations

import asyncio
import threading

import httpx

from app.ai.llm import ChatMessage, LLMClient, parse_json_response
from app.core.errors import ServiceUnavailable
from app.services.runtime_config import LLMConfig, RerankerConfig


class RerankError(ServiceUnavailable):
    pass


_local: dict[tuple[str, str], object] = {}
_lock = threading.Lock()


class Reranker:
    def __init__(self, cfg: RerankerConfig, llm_cfg: LLMConfig):
        self.cfg = cfg
        self.llm_cfg = llm_cfg

    @property
    def enabled(self) -> bool:
        return self.cfg.provider != "none"

    @property
    def label(self) -> str:
        return {"none": "disabled", "llm": f"LLM judge ({self.llm_cfg.model})"}.get(self.cfg.provider, self.cfg.model)

    async def score(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        if self.cfg.provider == "remote":
            return await self._remote(query, documents)
        if self.cfg.provider == "local":
            return await asyncio.to_thread(self._local_score, query, documents)
        if self.cfg.provider == "llm":
            return await self._llm(query, documents)
        return [0.0] * len(documents)

    async def _remote(self, query: str, documents: list[str]) -> list[float]:
        url = f"{self.cfg.base_url.rstrip('/')}/rerank"
        headers = {"Authorization": f"Bearer {self.cfg.api_key}"} if self.cfg.api_key else {}
        cohere_style = {"model": self.cfg.model, "query": query, "documents": documents, "top_n": len(documents)}
        tei_style = {"query": query, "texts": documents}
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, json=cohere_style, headers=headers)
                if resp.status_code in (400, 404, 422):
                    resp = await client.post(url, json=tei_style, headers=headers)
        except httpx.HTTPError as exc:
            raise RerankError(f"Cannot reach the reranker at {url} ({exc.__class__.__name__}).") from exc
        if resp.status_code >= 400:
            raise RerankError(f"Reranker error (HTTP {resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        rows = data if isinstance(data, list) else data.get("results") or data.get("data") or []
        scores = [0.0] * len(documents)
        for row in rows:
            idx = row.get("index")
            value = row.get("relevance_score", row.get("score"))
            if isinstance(idx, int) and 0 <= idx < len(documents) and value is not None:
                scores[idx] = float(value)
        return scores

    def _local_score(self, query: str, documents: list[str]) -> list[float]:
        key = (self.cfg.model, self.cfg.device)
        with _lock:
            model = _local.get(key)
            if model is None:
                try:
                    from sentence_transformers import CrossEncoder
                except ImportError as exc:
                    raise RerankError(
                        'In-process reranking needs the optional dependency: pip install -e ".[local-models]"'
                    ) from exc
                model = CrossEncoder(self.cfg.model, device=self.cfg.device)
                _local[key] = model
        return [float(s) for s in model.predict([(query, d) for d in documents])]  # type: ignore[attr-defined]

    async def _llm(self, query: str, documents: list[str]) -> list[float]:
        listing = "\n\n".join(f"[{i}] {d[:900]}" for i, d in enumerate(documents))
        prompt = (
            "Rate how useful each passage is for answering the question, from 0 (irrelevant) to 10 "
            '(directly answers it). Respond with JSON only: {"scores": [numbers in passage order]}.\n\n'
            f"Question: {query}\n\nPassages:\n{listing}"
        )
        client = LLMClient(self.llm_cfg)
        text = await client.complete([ChatMessage("user", prompt)], temperature=0, max_tokens=400, json_mode=True)
        try:
            scores = parse_json_response(text).get("scores", [])
        except ValueError as exc:
            raise RerankError("LLM reranker returned an unreadable answer.") from exc
        return [
            float(scores[i]) if i < len(scores) and isinstance(scores[i], int | float) else 0.0
            for i in range(len(documents))
        ]
