#!/usr/bin/env python
"""Latency evaluation — spec §95 "time to first token / total response latency" and
spec §100's full performance-instrumentation list. Every number here is a real, timed
measurement against the real seeded demo data and the real embedding/reranker/Ollama
models configured in `.env` (CPU or GPU, whichever this deployment is actually
running) — never simulated or estimated.

Usage:
    python evaluation/latency_eval.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.chat.context_builder import build_evidence_block, label_evidence  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.ingestion.chunking import chunk_pages  # noqa: E402
from app.llm.generation import ChatMessage, GenerationError, generate_stream  # noqa: E402
from app.models.chunk import Chunk, ChunkCollection  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.rag import dense_retriever, embeddings, reranker, sparse_retriever  # noqa: E402
from app.rag.deduplicator import deduplicate_and_expand  # noqa: E402
from app.rag.fusion import reciprocal_rank_fusion  # noqa: E402

QUERY = "What dose of Latanoprost is the patient prescribed and what is the intraocular pressure trend?"

T = TypeVar("T")


def _timed(fn: Callable[[], T]) -> tuple[T, float]:
    start = time.perf_counter()
    result = fn()
    return result, time.perf_counter() - start


def _time_synthetic_ingestion(settings) -> float:
    """A representative ingestion timing without touching the DB/Qdrant or any real
    report — the same real `chunk_pages()` + `embed_documents()` calls a real upload
    runs, against a synthetic multi-page document sized like a typical consultation
    note, so this number doesn't depend on which real report happens to exist."""
    pages = [
        {
            "page": i + 1,
            "text": (
                "GMS Eye Clinic - Ophthalmology Consultation Note\n\n"
                "Assessment: intraocular pressure stable on current regimen, visual "
                "acuity unchanged, no new findings on dilated fundus examination.\n\n"
                "Plan: continue current medications, follow up in three months."
            )
            * 3,
        }
        for i in range(3)
    ]

    def _run():
        chunks = chunk_pages(pages, document_title="latency-eval synthetic document")
        embeddings.embed_documents([c.text for c in chunks], settings)
        return len(chunks)

    _, elapsed = _timed(_run)
    return elapsed


async def evaluate() -> dict[str, Any]:
    settings = get_settings()
    db = SessionLocal()
    timings: dict[str, Any] = {}
    try:
        patient = db.query(Patient).filter(Patient.mrn == "DEMO-1002").first()
        patient_id = patient.id if patient else None

        # Warm both models first, excluded from the timed numbers below — the first
        # real call to either pays a one-time model-load cost (into CPU RAM or GPU
        # VRAM, whichever `.env` configures) that isn't part of steady-state per-query
        # latency; timing it in would conflate "how slow is a real query" with "how
        # slow is loading the model," the same distinction scripts/warm_models.py
        # exists to separate out for the live demo.
        embeddings.embed_query("warm-up", settings)
        reranker.rerank("warm-up", [("warm-up-id", "warm-up text")], settings, top_k=1)

        _, timings["embedding_query_s"] = _timed(lambda: embeddings.embed_query(QUERY, settings))

        dense_hits, timings["dense_search_s"] = _timed(
            lambda: dense_retriever.dense_search(
                QUERY, ChunkCollection.PATIENT_DOCUMENTS, settings, patient_id=patient_id
            )
        )
        sparse_hits, timings["sparse_search_s"] = _timed(
            lambda: sparse_retriever.sparse_search(
                db, QUERY, ChunkCollection.PATIENT_DOCUMENTS, patient_id=patient_id, top_k=settings.rag_sparse_top_k
            )
        )
        fused, timings["fusion_s"] = _timed(
            lambda: reciprocal_rank_fusion(dense_hits, sparse_hits, k=settings.rag_rrf_k, top_k=settings.rag_fusion_top_k)
        )

        chunk_ids = [h.chunk_id for h in fused]
        texts_by_id = {row.id: row.text for row in db.query(Chunk.id, Chunk.text).filter(Chunk.id.in_(chunk_ids)).all()}
        candidates = [(h.chunk_id, texts_by_id[h.chunk_id]) for h in fused if h.chunk_id in texts_by_id]

        reranked, timings["reranking_s"] = _timed(
            lambda: reranker.rerank(QUERY, candidates, settings, top_k=settings.rag_rerank_top_k)
        )
        passages, timings["deduplication_s"] = _timed(lambda: deduplicate_and_expand(db, reranked))
        _, timings["context_building_s"] = _timed(lambda: build_evidence_block(label_evidence(passages, [])))

        timings["synthetic_ingestion_s"] = _time_synthetic_ingestion(settings)

        messages = [ChatMessage("system", "You are a helpful clinical assistant."), ChatMessage("user", QUERY)]
        gen_start = time.perf_counter()
        first_token_at: float | None = None
        token_count = 0
        try:
            async for _delta in generate_stream(messages, settings):
                if first_token_at is None:
                    first_token_at = time.perf_counter()
                token_count += 1
            gen_end = time.perf_counter()
            timings["llm_time_to_first_token_s"] = (first_token_at - gen_start) if first_token_at else None
            timings["llm_total_generation_s"] = gen_end - gen_start
            timings["llm_tokens_streamed"] = token_count
        except GenerationError as exc:
            timings["llm_error"] = str(exc)
    finally:
        db.close()
    return timings


def print_report(timings: dict[str, Any]) -> None:
    print("\n=== Latency Evaluation (real, measured - see .env for CPU/GPU device) ===\n")
    for key, value in timings.items():
        if value is None:
            print(f"  {key:<32} n/a")
        elif isinstance(value, float):
            print(f"  {key:<32} {value:.3f}s")
        else:
            print(f"  {key:<32} {value}")


if __name__ == "__main__":
    print_report(asyncio.run(evaluate()))
