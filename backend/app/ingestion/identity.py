"""Patient identity extraction/matching — spec §30 "Patient Identity Checking During
Upload". Conservative by design: only claims MATCHED or MISMATCH when reasonably
confident; anything else is UNCONFIRMED rather than a false positive in either
direction. A document is never silently auto-attached on a mismatch (that's enforced
by the pipeline/API layer, not here — this module only classifies).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.patient import Patient
from app.models.report import PatientMatchStatus

# `[:\s|]+` (not just `[:\s]+`) so this also matches spreadsheet-style extracted text,
# where a "Label | Value" cell pair renders as "Patient Name | Elena Novak" rather than
# "Patient Name: Elena Novak" — found via live testing against a real XLSX upload.
#
# `_LABEL_BOUNDARY` is a non-consuming stop point placed at the end of both capture
# groups so a value never bleeds into the *next* labeled field when a document (or
# flattened OCR/table text) puts several fields on one line with no newline between
# them, e.g. "Patient: Elena Novak MRN: DEMO-1003" — without this, the greedy value
# class happily swallows " MRN" into the name, and (separately) an MRN value containing
# an internal space, like an OCR-misread hyphen ("DEMO 1003" for "DEMO-1003"), gets
# truncated at that space instead of captured whole. Found via live testing against a
# real scanned-image upload.
# Horizontal whitespace (`[ \t]`) only for the label lookahead — a bare `\r?\n` is its
# own, unconditional stop so a value never bleeds onto a *different* line just because
# whatever follows there isn't one of the recognized label words (e.g. a third
# unrelated row like "HbA1c | 8.1" after "MRN | DEMO-TEST-XLSX").
_LABEL_BOUNDARY = (
    r"(?=[ \t]*(?:MRN|Medical Record Number|Patient ID|Patient Name|Patient|"
    r"DOB|Date of Birth|Age|Sex|Gender|Date)\b|[:|]|\r?\n|$)"
)
_MRN_PATTERN = re.compile(
    r"(?:MRN|Medical Record Number|Patient ID)[:\s|]+([A-Za-z0-9][A-Za-z0-9\-\s]{2,19}?)" + _LABEL_BOUNDARY,
    re.IGNORECASE,
)
_NAME_PATTERN = re.compile(
    r"(?:Patient Name|Patient)[:\s|]+([A-Za-z][A-Za-z .'\-]{2,60}?)" + _LABEL_BOUNDARY,
    re.IGNORECASE,
)


@dataclass
class DetectedIdentity:
    name: str | None
    mrn: str | None


def detect_identity(text: str) -> DetectedIdentity:
    # Identity fields are almost always near the top of a clinical document — limiting
    # the search window avoids accidentally matching an unrelated "Patient:" mention
    # deep in a multi-page report (e.g. a quoted prior note).
    snippet = text[:3000]

    mrn_match = _MRN_PATTERN.search(snippet)
    mrn = mrn_match.group(1).strip() if mrn_match else None

    name = None
    name_match = _NAME_PATTERN.search(snippet)
    if name_match:
        candidate = name_match.group(1).splitlines()[0].strip()
        if 1 < len(candidate.split()) <= 5:
            name = candidate

    return DetectedIdentity(name=name, mrn=mrn)


def match_patient(detected: DetectedIdentity, patient: Patient) -> PatientMatchStatus:
    if detected.mrn is None and detected.name is None:
        return PatientMatchStatus.UNCONFIRMED

    mrn_match = detected.mrn.strip().lower() == patient.mrn.strip().lower() if detected.mrn else None

    name_match = None
    if detected.name:
        detected_norm = _normalize_name(detected.name)
        forward = _normalize_name(f"{patient.first_name} {patient.last_name}")
        reversed_ = _normalize_name(f"{patient.last_name} {patient.first_name}")
        name_match = detected_norm in (forward, reversed_) or (
            len(detected_norm) > 3 and (detected_norm in forward or forward in detected_norm)
        )

    if mrn_match is True or name_match is True:
        if mrn_match is False or name_match is False:
            return PatientMatchStatus.MISMATCH  # conflicting signals — don't guess
        return PatientMatchStatus.MATCHED

    if mrn_match is False or name_match is False:
        return PatientMatchStatus.MISMATCH

    return PatientMatchStatus.UNCONFIRMED


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z ]", "", name.lower()).strip()
