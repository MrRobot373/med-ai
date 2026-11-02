"""Checks an uploaded patient document against the selected patient so a report filed
under the wrong chart is caught before it reaches retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import Patient

_MRN_LABEL = re.compile(
    r"\b(?:MRN|UHID|patient\s*id|hospital\s*no\.?|reg(?:istration)?\s*no\.?)\s*\|?\s*[:#]?\s*([A-Z0-9][A-Z0-9\-/]{2,})",
    re.IGNORECASE,
)
# Table layouts put a column separator ("|") between a label and its value.
_NAME_LABEL = re.compile(
    r"\b(?:patient(?:\s*name)?|name)\s*\|?\s*[:\-]\s*([A-Za-z][A-Za-z .,'\-]{2,60})", re.IGNORECASE
)


@dataclass
class IdentityResult:
    status: str  # match | mismatch | unverified
    detail: str


def check(patient: Patient, text: str) -> IdentityResult:
    if not text.strip():
        return IdentityResult("unverified", "No readable text to verify against the patient record.")
    head = text[:6000]
    lowered = head.lower()
    mrn_found = [m.group(1).strip().rstrip(".,") for m in _MRN_LABEL.finditer(head)]
    names_found = [m.group(1).strip() for m in _NAME_LABEL.finditer(head)]

    mrn_match = patient.mrn.lower() in lowered
    first, last = patient.first_name.lower(), patient.last_name.lower()
    name_match = last in lowered and first in lowered

    foreign_mrn = [m for m in mrn_found if m.lower() != patient.mrn.lower() and patient.mrn.lower() not in m.lower()]
    # A shared surname is common (relatives, unrelated namesakes), so a name only counts as
    # this patient's when the given name is in it too.
    given = first.split()[0] if first.split() else first
    foreign_names = [n for n in names_found if given not in n.lower() and len(n.split()) >= 2]

    if foreign_names and not name_match:
        return IdentityResult("mismatch", f"Document names '{foreign_names[0]}', not {patient.full_name}.")
    if mrn_match and not foreign_mrn:
        return IdentityResult("match", f"MRN {patient.mrn} found in document.")
    if name_match and not foreign_names:
        # Outside labs print their own patient numbers; the name is what identifies the patient there.
        return IdentityResult("match", f"Patient name '{patient.full_name}' found in document.")
    if foreign_mrn and not mrn_match:
        return IdentityResult("mismatch", f"Document lists identifier {foreign_mrn[0]}, not {patient.mrn}.")
    return IdentityResult("unverified", "No patient identifiers found in the document.")
