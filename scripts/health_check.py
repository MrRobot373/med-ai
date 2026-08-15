#!/usr/bin/env python
"""Standalone health check — runs the exact same checks as `/api/health`, without
needing the FastAPI server itself to be up. Used by `start-demo.bat`/`health-check.bat`
to verify dependencies before starting the app, and by developers for quick diagnosis.

Usage:
    python scripts/health_check.py
Exit code is 0 only if every checked component is fully healthy.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.config.settings import get_settings  # noqa: E402
from app.db.session import check_database_reachable  # noqa: E402
from app.integrations.embedding_health import check_embedding_health  # noqa: E402
from app.integrations.ollama_client import check_ollama_health  # noqa: E402
from app.integrations.qdrant_client import check_qdrant_health  # noqa: E402
from app.integrations.reranker_health import check_reranker_health  # noqa: E402


def _line(name: str, ok: bool, detail: str = "") -> bool:
    icon = "OK  " if ok else "FAIL"
    # Plain hyphen, not an em dash: this script is invoked from health-check.bat via
    # plain cmd.exe, whose default console codepage (cp1252/850) mangles non-ASCII
    # punctuation into "?"/garbage — an em dash is exactly that kind of silent breakage.
    print(f"[{icon}] {name}" + (f" - {detail}" if detail else ""))
    return ok


async def main() -> int:
    settings = get_settings()
    all_ok = True

    db_ok, db_error = check_database_reachable()
    all_ok &= _line("SQLite database", db_ok, db_error or "")

    ollama = await check_ollama_health(settings)
    all_ok &= _line("Ollama service", ollama.reachable, ollama.error or f"version {ollama.version}")
    all_ok &= _line(
        f"Ollama model '{settings.ollama_model}'", ollama.model_available, ollama.error or ""
    )

    qdrant = await check_qdrant_health(settings)
    points_summary = ", ".join(f"{name}={count}" for name, count in qdrant.points_by_collection.items())
    all_ok &= _line(
        "Qdrant service", qdrant.reachable, qdrant.error or f"{len(qdrant.collections)} collections ({points_summary})"
    )

    embedding = check_embedding_health(settings)
    _line(
        f"Embedding model '{settings.embedding_model}'",
        embedding.package_installed,
        embedding.error or f"status={embedding.status} (loads lazily on first real use, not at startup)",
    )

    reranker = check_reranker_health(settings)
    _line(
        f"Reranker model '{settings.reranker_model}'",
        reranker.package_installed,
        reranker.error or f"status={reranker.status} (loads lazily on first real use, not at startup)",
    )

    print()
    print("All critical checks passed." if all_ok else "One or more critical checks failed.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
