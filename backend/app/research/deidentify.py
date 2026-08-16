"""External query de-identification — spec §66, MANDATORY: "Before an external query
leaves the machine ... Remove: name, MRN, phone, email, street address, exact direct
identifiers." This is the one gate every outbound Research Mode query passes through,
with no bypass — `services/research.py` calls it before any provider ever sees the
query text.

Deliberately narrow and deterministic rather than general NER-based name detection:
free-text name recognition has a real false-positive cost here (stripping "Marcus
Gunn pupil" or a drug eponym would silently corrupt the clinical question), so this
only ever removes (a) the specific patient's own known identifiers, exactly, when
patient context is given, and (b) identifier-shaped PATTERNS (email, phone, MRN,
street address) that are safe to strip unconditionally. Documented as a deliberate
scope decision, not an oversight — see docs/architecture.md's Phase 11 section.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.patient import Patient

_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)")
_MRN_PATTERN = re.compile(r"\bMRN\s*[:#]?\s*[A-Za-z0-9-]+\b", re.IGNORECASE)
_STREET_SUFFIXES = (
    r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|"
    r"Place|Pl|Terrace|Ter|Circle|Cir|Parkway|Pkwy|Highway|Hwy|Trail|Trl)"
)
_ADDRESS_PATTERN = re.compile(rf"\b\d{{1,5}}\s+[A-Za-z0-9.'-]+(?:\s+[A-Za-z0-9.'-]+)?\s+{_STREET_SUFFIXES}\b\.?", re.IGNORECASE)

_REDACTED = "[redacted]"


@dataclass
class DeidentifyResult:
    sanitized_text: str
    removed_count: int
    removed_categories: list[str] = field(default_factory=list)


def _strip_patient_identifiers(text: str, patient: Patient) -> tuple[str, int]:
    count = 0
    candidates = [
        patient.first_name,
        patient.last_name,
        patient.preferred_name,
        f"{patient.first_name} {patient.last_name}",
        f"{patient.last_name}, {patient.first_name}",
        patient.mrn,
        patient.phone,
        patient.email,
    ]
    for value in candidates:
        if not value or not value.strip():
            continue
        pattern = re.compile(re.escape(value.strip()), re.IGNORECASE)
        text, n = pattern.subn(_REDACTED, text)
        count += n
    return text, count


def deidentify_query(text: str, patient: Patient | None = None) -> DeidentifyResult:
    """Never raises, never returns the original text unexamined — every call passes
    through every pattern below, patient-specific or not."""
    sanitized = text
    removed_count = 0
    categories: list[str] = []

    if patient is not None:
        sanitized, n = _strip_patient_identifiers(sanitized, patient)
        if n:
            removed_count += n
            categories.append("patient_identity")

    for label, pattern in (
        ("email", _EMAIL_PATTERN),
        ("phone", _PHONE_PATTERN),
        ("mrn", _MRN_PATTERN),
        ("address", _ADDRESS_PATTERN),
    ):
        sanitized, n = pattern.subn(_REDACTED, sanitized)
        if n:
            removed_count += n
            categories.append(label)

    # Collapse the whitespace left behind by redactions into something a search
    # query API will still parse sensibly, rather than leaving "[redacted]   [redacted]".
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    return DeidentifyResult(sanitized_text=sanitized, removed_count=removed_count, removed_categories=categories)
