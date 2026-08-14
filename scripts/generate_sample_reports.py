#!/usr/bin/env python
"""Generates synthetic sample report files for demo upload testing (spec §141 step 11:
"Upload today's synthetic blood report"). Every value is fabricated — nothing here is
real patient data. Reuses the same generators pytest uses (backend/tests/sample_documents.py)
so the demo files and the test fixtures never drift apart.

Usage:
    python scripts/generate_sample_reports.py

Output: data/sample_reports/*.{pdf,docx,xlsx,png}
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from tests.sample_documents import (  # noqa: E402
    make_docx_bytes,
    make_pdf_bytes,
    make_png_bytes,
    make_scanned_pdf_bytes,
    make_xlsx_bytes,
)

OUTPUT_DIR = REPO_ROOT / "data" / "sample_reports"


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # DEMO-1001 — Margaret Wallace, cataract pre-op assessment
    (OUTPUT_DIR / "wallace_cataract_preop_consult.pdf").write_bytes(
        make_pdf_bytes(
            [
                "GMS Eye Clinic - Ophthalmology Consultation Note",
                "",
                "Patient Name: Margaret Wallace",
                "MRN: DEMO-1001",
                "Date: 10 August 2026",
                "",
                "Chief Complaint: Increased glare while driving at night",
                "",
                "Assessment: Visual acuity 20/70 OD, 20/40 OS. Cataract now visually",
                "significant in the right eye. Discussed cataract surgery options.",
                "",
                "Plan: Referral placed for cataract surgery evaluation, right eye first.",
            ]
        )
    )

    # DEMO-1002 — Robert Klein, glaucoma follow-up (DOCX with an IOP table)
    (OUTPUT_DIR / "klein_glaucoma_followup.docx").write_bytes(
        make_docx_bytes(
            paragraphs=[
                "GMS Eye Clinic - Ophthalmology Consultation Note",
                "Patient Name: Robert Klein",
                "MRN: DEMO-1002",
                "Date: 14 August 2026",
                "",
                "Chief Complaint: Routine glaucoma follow-up",
                "",
                "Intraocular pressure at this visit:",
            ],
            table_rows=[
                ["Eye", "IOP (mmHg)", "Target"],
                ["OD", "16", "<18"],
                ["OS", "17", "<18"],
            ],
        )
    )

    # DEMO-1003 — Elena Novak, lab panel (XLSX)
    (OUTPUT_DIR / "novak_metabolic_labs.xlsx").write_bytes(
        make_xlsx_bytes(
            sheet_name="Metabolic Panel",
            rows=[
                ["Patient Name", "Elena Novak"],
                ["MRN", "DEMO-1003"],
                ["Collection Date", "2026-08-10"],
                [],
                ["Test", "Result", "Unit", "Reference Range"],
                ["HbA1c", 8.1, "%", "4.0-5.6"],
                ["Fasting Glucose", 168, "mg/dL", "70-99"],
                ["LDL Cholesterol", 132, "mg/dL", "<100"],
                ["Creatinine", 0.9, "mg/dL", "0.6-1.3"],
            ],
        )
    )

    # DEMO-1003 — a "scanned" OCT report image, exercises the OCR-fallback path
    (OUTPUT_DIR / "novak_oct_report_scanned.png").write_bytes(
        make_png_bytes(
            [
                "GMS Eye Clinic - OCT Report",
                "Patient Name: Elena Novak   MRN: DEMO-1003",
                "Date: 14 August 2026",
                "",
                "Optical Coherence Tomography - Right Eye",
                "Central subfield thickness: 340 microns (elevated)",
                "Impression: Non-central diabetic macular edema, unchanged",
                "from prior study. Recommend anti-VEGF injection.",
            ],
            size=(900, 500),
        )
    )

    # A scanned-style PDF (no text layer) for testing the OCR path via PDF upload too
    (OUTPUT_DIR / "wallace_referral_scanned.pdf").write_bytes(
        make_scanned_pdf_bytes(
            [
                "GMS Eye Clinic - Referral Letter",
                "Patient Name: Margaret Wallace   MRN: DEMO-1001",
                "Date: 12 August 2026",
                "",
                "Dear Doctor,",
                "Please evaluate this patient for cataract surgery.",
                "Visually significant cataract, right eye greater than left.",
            ]
        )
    )

    # Deliberate patient-identity MISMATCH example (spec section 30) - upload this
    # against any seeded patient to demonstrate the mismatch-detection UI.
    (OUTPUT_DIR / "mismatch_example_different_patient.pdf").write_bytes(
        make_pdf_bytes(
            [
                "GMS Eye Clinic - Ophthalmology Consultation Note",
                "Patient Name: Sarah Demo",
                "MRN: DEMO-9999",
                "Date: 14 August 2026",
                "",
                "Chief Complaint: Red, itchy eyes for 3 days",
                "Assessment: Allergic conjunctivitis, bilateral.",
            ]
        )
    )

    print(f"Generated {len(list(OUTPUT_DIR.iterdir()))} sample report files in {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
