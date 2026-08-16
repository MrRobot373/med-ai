#!/usr/bin/env python
"""Ingests reference PDFs from `data/*.pdf` into the `medical_knowledge` Qdrant
collection (spec §14) — the RAG pipeline's non-patient-scoped source of clinical
guidelines/protocols/reference material. Chunking/embedding reuses exactly the same
`app.rag.indexing.index_document()` the report-ingestion pipeline uses for
`patient_documents`, so the two stay consistent in shape by construction.

Usage:
    python scripts/ingest_knowledge.py                 # default curated set (small,
                                                          fast, genuine guideline docs)
    python scripts/ingest_knowledge.py --all            # every data/*.pdf, INCLUDING
                                                          several-hundred-page textbooks
                                                          (can take a long time on CPU)
    python scripts/ingest_knowledge.py --file NAME.pdf  # one specific file
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.config.settings import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.ingestion import pdf as pdf_module  # noqa: E402
from app.ingestion.storage import sha256_hex  # noqa: E402
from app.models.chunk import Chunk, ChunkCollection  # noqa: E402
from app.rag.indexing import index_document  # noqa: E402

DATA_DIR = REPO_ROOT / "data"

# Curated default: small, genuinely clinical, ophthalmology-domain reference material
# (see docs/architecture.md "Domain note" — this deployment's knowledge base targets
# ophthalmology, not the spec's illustrative cardiology/diabetes examples). The
# remaining data/*.pdf files are full multi-hundred-page textbooks (up to ~1,900
# pages) — real, valuable content, but ingesting all of it on CPU is a knowledge-base
# *population* job better suited to Phase 12 (Knowledge Administration) / Phase 14
# (Demo System) than Phase 07's scope of proving the retrieval pipeline works
# end-to-end against real (if not exhaustive) content. `--all` opts into the rest.
DEFAULT_FILES = (
    "ICOClinicalGuidelines.pdf",
    "Ophthalmology_Referral_Guidelines.pdf",
    "Instruments_book.pdf",
)


def _title_from_filename(filename: str) -> str:
    return Path(filename).stem.replace("_", " ").replace("--", "").strip()


def _already_indexed(db, file_hash: str) -> bool:
    stmt = select(Chunk.id).where(Chunk.collection == ChunkCollection.MEDICAL_KNOWLEDGE, Chunk.file_hash == file_hash).limit(1)
    return db.scalar(stmt) is not None


def ingest_file(path: Path, force: bool = False) -> int | None:
    """Returns the chunk count indexed, or `None` if skipped because this exact file
    content is already indexed. Real, measured problem this guards against: without
    it, `start-demo.bat` re-running this script on every launch re-embeds the same
    ~111 chunks from scratch every time (Phase 07's own measurement: ~11s/chunk on
    CPU once warm) purely because it has no way to tell "already indexed" from
    "changed since last run" — several real minutes wasted on every demo start for
    content that never changed. `--force` (or a genuinely different file_hash, e.g.
    an updated PDF) still re-indexes for real."""
    settings = get_settings()
    content = path.read_bytes()
    file_hash = sha256_hex(content)

    db = SessionLocal()
    try:
        if not force and _already_indexed(db, file_hash):
            return None
        result = pdf_module.extract_pdf_text(content)
        pages = [{"page": page.page, "text": page.text} for page in result.pages]
        rows = index_document(
            db,
            settings,
            pages,
            collection=ChunkCollection.MEDICAL_KNOWLEDGE,
            source_title=_title_from_filename(path.name),
            source_filename=path.name,
            file_hash=file_hash,
        )
        return len(rows)
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="Ingest every PDF in data/, including large textbooks")
    parser.add_argument("--file", help="Ingest a single specific file by name")
    parser.add_argument(
        "--force", action="store_true", help="Re-index even if this exact file content is already indexed"
    )
    args = parser.parse_args()

    if args.file:
        files = [DATA_DIR / args.file]
    elif args.all:
        files = sorted(DATA_DIR.glob("*.pdf"))
    else:
        files = [DATA_DIR / name for name in DEFAULT_FILES]

    total_chunks = 0
    for path in files:
        if not path.exists():
            print(f"SKIP (not found): {path.name}")
            continue
        started = time.time()
        print(f"Ingesting {path.name} ...", flush=True)
        count = ingest_file(path, force=args.force)
        if count is None:
            print("  -> already indexed (unchanged) - skipped. Use --force to re-index anyway.")
            continue
        total_chunks += count
        print(f"  -> {count} chunks in {time.time() - started:.1f}s")

    print(f"Done. {total_chunks} chunks indexed across {len(files)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
