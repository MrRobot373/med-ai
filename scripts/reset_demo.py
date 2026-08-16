#!/usr/bin/env python
"""Returns the demo to a known clean state (spec §87). Deletes the SQLite database
file, all uploaded/knowledge file storage, and every Qdrant collection's points, then
re-seeds everything from scratch: migrations -> demo accounts -> demo patients ->
sample report files -> real report ingestion -> knowledge base ingestion.

This operates ONLY against the locally configured demo environment (spec §87: "never
delete real user data without explicit confirmation... demo reset should operate only
against the configured demo environment") — there is no multi-tenant/production mode
in this build (see docs/architecture.md's Phase status table: this is a single-
deployment local demo system), so "the demo environment" is simply whatever
DATABASE_URL/UPLOAD_DIR this process is configured with; nothing outside those paths
is ever touched. Requires interactive confirmation unless `--yes` is passed —
`reset-demo.bat` prompts once itself before invoking this with `--yes`, so a presenter
still can't trigger a wipe with a single accidental double-click.

Run this only while the backend/frontend are stopped (`stop-demo.bat` first) —
deleting the SQLite file while a server process holds it open will fail on Windows.

Usage:
    python scripts/reset_demo.py           # prompts for confirmation
    python scripts/reset_demo.py --yes     # no prompt (used by reset-demo.bat, which
                                              already confirmed once itself)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(BACKEND_ROOT))

from app.config.settings import get_settings  # noqa: E402
from app.rag.qdrant_setup import get_qdrant_client  # noqa: E402

_COLLECTIONS = ("medical_knowledge", "patient_documents", "patient_vision")


def _delete_sqlite(settings) -> None:
    if not settings.database_url.startswith("sqlite"):
        print(f"  SKIP: DATABASE_URL is not SQLite ({settings.database_url}) — not deleting a non-local database.")
        return
    path = Path(settings.database_url.removeprefix("sqlite:///"))
    if path.exists():
        path.unlink()
        print(f"  Deleted {path}")
    else:
        print(f"  {path} did not exist — nothing to delete.")


def _clear_uploads(settings) -> None:
    upload_dir = Path(settings.upload_dir)
    if upload_dir.exists():
        shutil.rmtree(upload_dir)
        print(f"  Cleared {upload_dir}")
    else:
        print(f"  {upload_dir} did not exist — nothing to clear.")


def _clear_qdrant(settings) -> None:
    client = get_qdrant_client(settings)
    existing = {c.name for c in client.get_collections().collections}
    for name in _COLLECTIONS:
        if name in existing:
            client.delete_collection(name)
            print(f"  Deleted Qdrant collection '{name}' (recreated automatically on next real indexing)")
        else:
            print(f"  Qdrant collection '{name}' did not exist — nothing to clear.")


def _run(args: list[str], cwd: Path) -> None:
    print(f"  $ {' '.join(args)}")
    subprocess.run(args, cwd=str(cwd), check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="Skip the interactive confirmation prompt")
    args = parser.parse_args()

    settings = get_settings()

    print("This will PERMANENTLY DELETE all current demo data:")
    print(f"  - the SQLite database ({settings.database_url})")
    print(f"  - all uploaded/knowledge files under {settings.upload_dir}")
    print(f"  - all points in Qdrant collections: {', '.join(_COLLECTIONS)}")
    print("...then re-seed a fresh, known-clean demo state (accounts, patients, reports, knowledge base).")
    if not args.yes:
        answer = input("Type YES to continue: ").strip()
        if answer != "YES":
            print("Aborted — nothing was deleted.")
            return 1

    python = sys.executable

    try:
        print("[1/9] Deleting SQLite database...")
        _delete_sqlite(settings)

        print("[2/9] Clearing uploaded/knowledge file storage...")
        _clear_uploads(settings)

        print("[3/9] Clearing Qdrant collections...")
        _clear_qdrant(settings)

        print("[4/9] Running database migrations...")
        _run([python, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_ROOT)

        print("[5/9] Seeding demo accounts...")
        _run([python, str(SCRIPTS_DIR / "seed_demo.py")], cwd=REPO_ROOT)

        print("[6/9] Seeding demo patients...")
        _run([python, str(SCRIPTS_DIR / "seed_demo_patients.py")], cwd=REPO_ROOT)

        print("[7/9] Generating sample report files...")
        _run([python, str(SCRIPTS_DIR / "generate_sample_reports.py")], cwd=REPO_ROOT)

        print("[8/9] Ingesting sample reports into demo patients (real pipeline)...")
        _run([python, str(SCRIPTS_DIR / "seed_demo_reports.py")], cwd=REPO_ROOT)

        print("[9/9] Ingesting reference clinical guidelines into the knowledge base...")
        _run([python, str(SCRIPTS_DIR / "ingest_knowledge.py")], cwd=REPO_ROOT)
    except subprocess.CalledProcessError as exc:
        print(f"\nFAILED at step: {' '.join(exc.cmd)} (exit code {exc.returncode})")
        return 1

    print("\nDone. Demo reset to a known-clean state.")
    print("Demo account credentials: data/sqlite/.demo_credentials.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
