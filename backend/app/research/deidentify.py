"""Every outbound research query passes through here. Removes the active patient's own
identifiers exactly, plus identifier-shaped patterns (emails, phones, MRNs, dates of
birth, street addresses). Deliberately not NER-based: stripping eponyms like
"Marcus Gunn pupil" would corrupt the clinical question."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models import Patient

_PATTERNS = [
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("phone", re.compile(r"(?<!\d)(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)")),
    ("mrn", re.compile(r"\b(?:MRN|UHID|ID)\s*[:#]?\s*[A-Za-z0-9-]{3,}\b", re.IGNORECASE)),
    ("date", re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")),
    (
        "address",
        re.compile(
            r"\b\d{1,5}\s+[A-Za-z0-9.'-]+(?:\s+[A-Za-z0-9.'-]+)?\s+(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Boulevard|Blvd|Way|Court|Ct)\b\.?",
            re.IGNORECASE,
        ),
    ),
]


@dataclass
class Deidentified:
    text: str
    removed: int = 0
    categories: list[str] = field(default_factory=list)


def deidentify(text: str, patient: Patient | None = None) -> Deidentified:
    out = Deidentified(text)
    if patient is not None:
        for value in sorted(
            filter(
                None,
                [
                    patient.full_name,
                    f"{patient.last_name}, {patient.first_name}",
                    patient.first_name,
                    patient.last_name,
                    patient.mrn,
                    patient.phone,
                    patient.email,
                ],
            ),
            key=len,
            reverse=True,
        ):
            pattern = re.compile(r"(?<!\w)" + re.escape(value.strip()) + r"(?!\w)", re.IGNORECASE)
            out.text, n = pattern.subn("the patient", out.text)
            if n:
                out.removed += n
                if "patient_identity" not in out.categories:
                    out.categories.append("patient_identity")
    for label, pattern in _PATTERNS:
        out.text, n = pattern.subn("", out.text)
        if n:
            out.removed += n
            out.categories.append(label)
    out.text = re.sub(r"\bthe patient(?:\s+the patient)+", "the patient", out.text)
    out.text = re.sub(r"\s+", " ", out.text).strip()
    return out
