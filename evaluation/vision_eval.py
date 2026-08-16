#!/usr/bin/env python
"""Vision extraction evaluation — spec §95 "vision extraction accuracy", spec §96's
`vision_report_extraction` golden category.

Checks the real, already-persisted `VisionAnalysis` row (spec §60's schema, populated
by a real Ollama vision call during report ingestion — see
`scripts/seed_demo_reports.py`) for structural completeness: real, non-empty content
in the fields a genuine clinical image analysis should populate, not a placeholder or
empty result.

**Honest scope note**: there is no hand-labeled ground truth for these synthetic
images (no clinician verified "this is what the image actually shows" against a real
scan), so this cannot score pixel-level extraction *accuracy* the way
`retrieval_eval.py` scores against known keywords. What IS checkable and genuinely
meaningful: did the real model produce a real, non-generic, non-empty structured
result — the same "did this actually work, for real" bar the rest of this suite
applies everywhere else, applied honestly rather than inventing an accuracy number
with no ground truth behind it.

Usage:
    python evaluation/vision_eval.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.models.report import Report  # noqa: E402
from app.models.vision_analysis import VisionAnalysis, VisionAnalysisStatus  # noqa: E402

GOLDEN_FILE = Path(__file__).parent / "golden_questions.jsonl"


def _load_golden() -> list[dict]:
    rows = [json.loads(line) for line in GOLDEN_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if r["category"] == "vision_report_extraction"]


def evaluate() -> list[dict]:
    db = SessionLocal()
    results: list[dict] = []
    try:
        for question in _load_golden():
            patient = db.query(Patient).filter(Patient.mrn == question["patient_mrn"]).first()
            if patient is None:
                results.append({**question, "skipped": "patient not found — run scripts/seed_demo_patients.py"})
                continue
            report = (
                db.query(Report)
                .filter(Report.patient_id == patient.id, Report.source_filename == question["report_filename"])
                .first()
            )
            if report is None:
                results.append({**question, "skipped": "report not found — run scripts/seed_demo_reports.py"})
                continue
            analysis = db.query(VisionAnalysis).filter(VisionAnalysis.report_id == report.id).first()
            if analysis is None:
                results.append({**question, "skipped": "no VisionAnalysis row yet — run scripts/seed_demo_reports.py"})
                continue

            payload = json.loads(analysis.payload) if analysis.payload else {}
            checks = {
                "status_is_success": analysis.status == VisionAnalysisStatus.SUCCESS,
                "has_image_type": bool(payload.get("image_type")),
                "has_at_least_one_observation": bool(payload.get("observations")),
                "not_a_generic_placeholder": payload.get("image_type", "") not in ("", "unknown", "image"),
            }
            results.append({**question, **checks, "passed": all(checks.values()), "payload": payload})
    finally:
        db.close()
    return results


def print_report(results: list[dict]) -> None:
    print("\n=== Vision Extraction Evaluation ===\n")
    print("(Structural completeness only - no hand-labeled ground truth exists for synthetic images.)\n")
    scored = [r for r in results if "passed" in r]
    for r in results:
        if "skipped" in r:
            print(f"  SKIP  {r['id']:<28} {r['skipped']}")
        else:
            status = "PASS" if r["passed"] else "FAIL"
            obs_count = len(r["payload"].get("observations", []))
            print(f"  {status}  {r['id']:<28} image_type={r['payload'].get('image_type')!r} observations={obs_count}")
    if scored:
        n = len(scored)
        print(f"\nStructural completeness: {sum(r['passed'] for r in scored)}/{n}")


if __name__ == "__main__":
    print_report(evaluate())
