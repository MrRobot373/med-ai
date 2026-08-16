#!/usr/bin/env python
"""Uploads and ingests the synthetic sample report files
(`scripts/generate_sample_reports.py`) into their matching seeded demo patients,
through the exact real pipeline `app/services/reports.py` uses for a live upload
(`create_report()` + `run_ingestion_task()`) — not just files sitting in
`data/sample_reports/` waiting for a manual upload during a live demo.

This is what makes spec §88's "previous reports, current report... lab history...
at least one meaningful report comparison" genuinely real out of the box: after this
runs, demo patients have real extracted labs/observations, real vision analyses on
their image reports, and real RAG-indexed chunks — the same as if a clinician had
uploaded each file by hand.

Idempotent — `create_report()` already dedups by (patient_id, file_hash), so
re-running this (e.g. every `start-demo.bat`) never accumulates duplicate reports or
re-runs the slow parts (embedding/vision analysis) for files already ingested.

Must run AFTER `scripts/seed_demo_patients.py` (patients must exist) and
`scripts/generate_sample_reports.py` (files must exist) — `start-demo.bat` runs all
three in that order.

Usage:
    python scripts/seed_demo_reports.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlalchemy.orm import Session as DbSession  # noqa: E402

from app.config.settings import Settings, get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.models.report import PatientMatchStatus, Report  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import reports as report_service  # noqa: E402

SAMPLE_REPORTS_DIR = REPO_ROOT / "data" / "sample_reports"

# (MRN, filename) — every file here is auto-ingested into its matching patient.
# `mismatch_example_different_patient.pdf` is deliberately NOT listed: its whole
# purpose (spec §30) is to demonstrate the identity-mismatch banner on a live,
# presenter-driven upload, so it stays sitting in data/sample_reports/ instead.
FILES_BY_PATIENT: list[tuple[str, str]] = [
    ("DEMO-1001", "wallace_cataract_preop_consult.pdf"),
    ("DEMO-1001", "wallace_referral_scanned.pdf"),
    ("DEMO-1002", "klein_glaucoma_baseline.docx"),
    ("DEMO-1002", "klein_glaucoma_followup.docx"),
    ("DEMO-1002", "klein_injection_test_note.pdf"),
    ("DEMO-1003", "novak_metabolic_labs_baseline.xlsx"),
    ("DEMO-1003", "novak_metabolic_labs.xlsx"),
    ("DEMO-1003", "novak_oct_report_scanned.png"),
    ("DEMO-1004", "patel_amd_consult.pdf"),
    ("DEMO-1004", "patel_amd_oct_scanned.png"),
    ("DEMO-1005", "ferreira_multimorbidity_consult.pdf"),
]


async def _ingest_one(db: DbSession, settings: Settings, patient_id: str, path: Path, uploaded_by: str | None) -> str:
    # Idempotency is checked by (patient_id, source_filename) here, NOT by
    # create_report()'s own file-hash dedup alone — a real, non-obvious finding from
    # live-testing this script: PyMuPDF/python-docx/openpyxl do not emit byte-
    # identical output across separate calls even for textually-identical content
    # (likely internal object/xref ordering or zip-entry metadata), so re-running
    # `generate_sample_reports.py` produces a *different* file_hash for "the same"
    # file every time. Relying on create_report()'s hash-based DuplicateReportError
    # alone would silently accumulate duplicate reports on every `start-demo.bat` run
    # instead of leaving an already-seeded patient's reports untouched.
    existing = db.scalar(
        select(Report).where(
            Report.patient_id == patient_id, Report.source_filename == path.name, Report.archived.is_(False)
        )
    )
    if existing is not None:
        # Confirm even on an already-seeded report — a prior run of this script may
        # predate the mismatch-confirmation fix below, or ingestion may have finished
        # after that run's own confirmation attempt. Idempotent either way (a second
        # confirm_patient_match() call on an already-matched report is a no-op).
        if existing.patient_match_status == PatientMatchStatus.MISMATCH:
            report_service.confirm_patient_match(db, settings, existing, reviewed_by=uploaded_by)
            return "skip (already uploaded, confirmed match)"
        return "skip (already uploaded)"

    content = path.read_bytes()
    try:
        report = report_service.create_report(db, settings, patient_id, path.name, content, uploaded_by=uploaded_by)
    except report_service.DuplicateReportError:
        return "skip (already uploaded)"
    except report_service.UploadValidationError as exc:
        return f"FAILED validation: {exc}"
    await report_service.run_ingestion_task(report.id, settings)

    # A real, live-verification finding: the OCT-style PNGs' baked-in patient name/
    # MRN text is small and plain, and real (unmocked) OCR sometimes misreads it —
    # the exact same "correctly conservative" MISMATCH the identity checker is
    # designed to raise on genuine uncertainty (spec §30), and the exact same failure
    # mode Phase 05's live testing already documented once for a different file. A
    # flagged report is never indexed (spec §16), so left alone this would silently
    # leave a demo patient's real, successfully-analyzed vision findings unsearchable.
    # Unlike a live clinician facing an actual unknown upload, this script knows with
    # certainty which patient each file belongs to (it uploaded it, for that patient,
    # itself) — confirming it here is that same certainty a clinician reviewing the
    # banner would have, going through the real confirm_patient_match() workflow
    # rather than bypassing the identity check itself.
    db.refresh(report)
    if report.patient_match_status == PatientMatchStatus.MISMATCH:
        report_service.confirm_patient_match(db, settings, report, reviewed_by=uploaded_by)
        return "ingested (confirmed match)"
    return "ingested"


async def main() -> int:
    settings = get_settings()
    db = SessionLocal()
    try:
        doctor = db.scalar(select(User).where(User.email == "doctor@gms.local"))
        uploaded_by = doctor.id if doctor else None
        if uploaded_by is None:
            print("[warn] doctor@gms.local not found — run scripts/seed_demo.py first. Continuing with uploaded_by=NULL.")

        for mrn, filename in FILES_BY_PATIENT:
            path = SAMPLE_REPORTS_DIR / filename
            if not path.exists():
                print(f"[skip] {filename} not found — run scripts/generate_sample_reports.py first")
                continue
            patient = db.scalar(select(Patient).where(Patient.mrn == mrn))
            if patient is None:
                print(f"[skip] patient {mrn} not found — run scripts/seed_demo_patients.py first")
                continue
            outcome = await _ingest_one(db, settings, patient.id, path, uploaded_by)
            print(f"[{outcome}] {filename} -> {mrn}")
    except OperationalError as exc:
        print(f"Database error - have you run migrations yet? (alembic upgrade head)\n{exc}")
        return 1
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
