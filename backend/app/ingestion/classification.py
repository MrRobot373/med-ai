"""Report type classification — a keyword heuristic, not a fabricated ML confidence
score (spec §2 "never generate a fake medical certainty percentage"). Keyword lists
lean toward the ophthalmology domain this deployment's knowledge base covers, but
`OTHER` is always the honest fallback rather than forcing a guess.
"""

from __future__ import annotations

from app.models.report import ReportType

_KEYWORDS: dict[ReportType, tuple[str, ...]] = {
    ReportType.LAB_REPORT: (
        "laboratory",
        "hematology",
        "cbc",
        "complete blood count",
        "reference range",
        "specimen",
        "chemistry panel",
        "hba1c",
        "glucose",
        "creatinine",
        "lipid panel",
        "platelet",
        "wbc",
        "rbc",
    ),
    ReportType.IMAGING_REPORT: (
        "optical coherence tomography",
        " oct ",
        "fundus",
        "fundoscopy",
        "visual field",
        "perimetry",
        "fluorescein angiography",
        "slit-lamp",
        "slit lamp",
        "b-scan",
        "topography",
        "pachymetry",
        "mri",
        "ct scan",
        "x-ray",
        "radiograph",
        "ultrasound",
    ),
    ReportType.DISCHARGE_SUMMARY: (
        "discharge summary",
        "discharge diagnosis",
        "discharge instructions",
        "hospital course",
    ),
    ReportType.REFERRAL_LETTER: (
        "referral",
        "referring physician",
        "dear doctor",
        "please evaluate",
        "kindly review",
    ),
    ReportType.CONSULTATION_NOTE: (
        "chief complaint",
        "history of present illness",
        "assessment and plan",
        "clinical impression",
        "consultation note",
    ),
}


def classify_report(filename: str, text: str) -> ReportType:
    haystack = f" {filename.lower()} {text.lower()[:5000]} "  # padded so " oct " etc. can match at boundaries

    best_type = ReportType.OTHER
    best_score = 0
    for report_type, keywords in _KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in haystack)
        if score > best_score:
            best_score = score
            best_type = report_type

    return best_type
