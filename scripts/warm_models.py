#!/usr/bin/env python
"""Warms the Ollama generation model, embedding model, and reranker (spec §86 steps
6-8: "warm the model / verify embedding model / verify reranker") ahead of a live
demo — so the first real query a presenter runs during the demo isn't the one that
pays the cold-start cost (Ollama loading model weights, sentence-transformers loading
the embedding/reranker checkpoints into CPU memory — see docs/architecture.md's
Phase 07 "CPU embedding performance" notes for how real that cost is).

Best-effort — a warm-up failure is logged but never fatal to `start-demo.bat`: this
script is a latency optimization, not the readiness gate. `scripts/health_check.py`
(run separately) is the authoritative check for whether the demo can actually run.

Usage:
    python scripts/warm_models.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.config.settings import get_settings  # noqa: E402
from app.llm.generation import ChatMessage, GenerationError, generate_complete  # noqa: E402
from app.rag import embeddings, reranker  # noqa: E402


def _line(name: str, ok: bool, seconds: float, detail: str = "") -> None:
    icon = "OK  " if ok else "FAIL"
    print(f"[{icon}] {name} ({seconds:.1f}s)" + (f" - {detail}" if detail else ""))


async def _warm_ollama() -> None:
    settings = get_settings()
    started = time.time()
    try:
        await generate_complete(
            [ChatMessage("user", "Reply with a single word: ready.")],
            settings,
            max_output_tokens=8,
        )
        _line(f"Ollama model '{settings.ollama_model}'", True, time.time() - started)
    except GenerationError as exc:
        _line(f"Ollama model '{settings.ollama_model}'", False, time.time() - started, str(exc))


def _warm_embedding() -> None:
    settings = get_settings()
    started = time.time()
    try:
        embeddings.embed_query("warm-up", settings)
        _line(f"Embedding model '{settings.embedding_model}'", True, time.time() - started)
    except Exception as exc:  # best-effort — never blocks start-demo.bat on this
        _line(f"Embedding model '{settings.embedding_model}'", False, time.time() - started, str(exc))


def _warm_reranker() -> None:
    settings = get_settings()
    started = time.time()
    try:
        reranker.rerank("warm-up", [("warm-up-id", "warm-up passage text")], settings, top_k=1)
        _line(f"Reranker model '{settings.reranker_model}'", True, time.time() - started)
    except Exception as exc:
        _line(f"Reranker model '{settings.reranker_model}'", False, time.time() - started, str(exc))


async def main() -> int:
    print("Warming models ahead of the demo (first CPU load can take a while - this is expected) ...")
    await _warm_ollama()
    # Embedding/reranker loads are both synchronous CPU work — run one after another
    # rather than in a thread pool, matching how the rest of this codebase treats
    # them (see rag/embeddings.py / rag/reranker.py's own lazy-singleton pattern).
    _warm_embedding()
    _warm_reranker()
    print("Done warming. (Failures above are non-fatal here - run scripts/health_check.py for the real readiness check.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
