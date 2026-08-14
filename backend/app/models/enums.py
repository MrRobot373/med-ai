"""Enums shared across multiple clinical models — keeping one definition avoids the
same conceptual value (e.g. verification status) drifting into subtly different sets
per table.
"""

from __future__ import annotations

from enum import Enum


class VerificationStatus(str, Enum):
    """Spec §32: every extracted/entered clinical fact carries a verification status so
    the UI can distinguish clinician-confirmed data from provisional/unconfirmed
    entries — and so automated extraction (Phase 05+) never silently overwrites
    something a clinician has already verified."""

    CONFIRMED = "confirmed"
    PROVISIONAL = "provisional"
    UNCONFIRMED = "unconfirmed"
