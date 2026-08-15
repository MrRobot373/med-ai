from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ReconciliationStatus(str, Enum):
    NEWLY_DETECTED = "newly_detected"  # mentioned in this document, not in the current active list
    NOT_IN_DOCUMENT = "not_in_document"  # in the current active list, not mentioned in this document
    UNCHANGED = "matched_unchanged"  # matched by name; dose/instructions match (or aren't comparable)
    REVIEW = "matched_review"  # matched by name; dose/instructions text differs — needs a look


class ReconciliationItem(BaseModel):
    status: ReconciliationStatus
    current_medication_id: str | None = None
    current_medication_name: str | None = None
    current_dose: str | None = None
    current_frequency: str | None = None
    document_medication_name: str | None = None
    document_dose: str | None = None
    document_route: str | None = None
    document_frequency: str | None = None
    source_page: int | None = None
    source_excerpt: str | None = None


class ReconciliationResult(BaseModel):
    report_id: str
    report_title: str
    items: list[ReconciliationItem]
