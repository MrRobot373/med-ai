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

from app.config.settings import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.ingestion import pdf as pdf_module  # noqa: E402
from app.ingestion.storage import sha256_hex  # noqa: E402
from app.models.chunk import ChunkCollection  # noqa: E402
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


def ingest_file(path: Path) -> int:
    settings = get_settings()
    content = path.read_bytes()
    result = pdf_module.extract_pdf_text(content)
    pages = [{"page": page.page, "text": page.text} for page in result.pages]

    db = SessionLocal()
    try:
        rows = index_document(
            db,
            settings,
            pages,
            collection=ChunkCollection.MEDICAL_KNOWLEDGE,
            source_title=_title_from_filename(path.name),
            source_filename=path.name,
            file_hash=sha256_hex(content),
        )
        return len(rows)
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="Ingest every PDF in data/, including large textbooks")
    parser.add_argument("--file", help="Ingest a single specific file by name")
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
        count = ingest_file(path)
        total_chunks += count
        print(f"  -> {count} chunks in {time.time() - started:.1f}s")

    print(f"Done. {total_chunks} chunks indexed across {len(files)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
