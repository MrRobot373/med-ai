"""Structured medication-list extraction from ingested report text — feeds medication
reconciliation (spec §36).

Deliberately scoped to a clearly delimited medications section (a heading like
"Current Medications:" followed by a table or a list of lines) rather than attempting
free-text NLP over an entire document — a much higher-precision target that still
covers the common real-world shape of a discharge summary/consultation note's
medication list. Every extraction stays traceable to its exact source line for
clinician review (spec §32); nothing here writes to the `medications` table directly —
see `app/services/reconciliation.py` for the read-only comparison that uses this.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ingestion._tabular import find_header_column, find_table_blocks

_SECTION_HEADER_PATTERN = re.compile(
    r"^(current medications?|discharge medications?|medications? on discharge|medications?|medication list)\s*:?\s*$",
    re.IGNORECASE,
)

_HEADER_NAME_KEYWORDS = ("medication", "drug", "name")
_HEADER_DOSE_KEYWORDS = ("dose", "dosage", "strength")
_HEADER_ROUTE_KEYWORDS = ("route",)
_HEADER_FREQUENCY_KEYWORDS = ("frequency", "freq", "instructions")

# A trailing `\b` would fail right after "%" — "%" and a following space are both
# non-word characters, so there's no word/non-word boundary transition for `\b` to
# match there (the same class of bug fixed in `identity.py`'s label-boundary regex).
# `(?=\W|$)` requires the next character to be non-word or end-of-string instead.
_DOSE_PATTERN = re.compile(r"\d+(?:\.\d+)?\s?(?:mg|mcg|g|%|mL|ml|units?|iu)(?=\W|$)", re.IGNORECASE)
_FREQUENCY_PATTERN = re.compile(
    r"once daily|twice daily|three times daily|four times daily|nightly|weekly|prn|as needed"
    r"|\bbid\b|\btid\b|\bqid\b|\bqhs\b|\bqam\b|\bqpm\b|\bqd\b|every \d+ hours?",
    re.IGNORECASE,
)
_ROUTE_PATTERN = re.compile(
    r"\b(po|iv|im|sc|subcutaneous|topical|oral|ophthalmic|eye drops?|inhaled)\b", re.IGNORECASE
)


@dataclass
class ExtractedMedication:
    medication_name: str
    dose: str | None
    route: str | None
    frequency: str | None
    source_page: int
    source_excerpt: str


def extract_medications(pages: list[dict]) -> list[ExtractedMedication]:
    results: list[ExtractedMedication] = []
    for page_dict in pages:
        section = _find_medication_section(page_dict["text"])
        if not section:
            continue
        table_hits = _extract_from_tables(section, page_dict["page"])
        results.extend(table_hits if table_hits else _extract_from_lines(section, page_dict["page"]))
    return results


def _find_medication_section(text: str) -> str | None:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if _SECTION_HEADER_PATTERN.match(line.strip()):
            start = index + 1
            break
    if start is None:
        return None

    # A single blank line does *not* end the section: DOCX extraction represents every
    # paragraph break — including the gap between two consecutive medication lines —
    # as exactly one blank line (verified live: "Latanoprost...\n\nTimolol...\n\n
    # Brimonidine..." for a genuine three-line list), so treating any blank line as
    # the section's end silently dropped every medication after the first. Instead,
    # end the section at a line that itself looks like the start of a new heading
    # (ends with ":" and isn't itself a dose line, e.g. "Intraocular pressure at this
    # visit:"), or after two consecutive blank lines (a true paragraph gap in
    # single-newline-separated text), or at end of text.
    section_lines: list[str] = []
    blank_run = 0
    for line in lines[start:]:
        stripped = line.strip()
        if not stripped:
            blank_run += 1
            if not section_lines:
                continue  # blank line(s) right after the heading are just spacing
            if blank_run >= 2:
                break
            continue
        blank_run = 0
        if section_lines and stripped.endswith(":") and not _DOSE_PATTERN.search(stripped):
            break  # looks like the start of an unrelated new section
        section_lines.append(line)
    return "\n".join(section_lines) if section_lines else None


def _is_medication_table_header(cells: list[str]) -> bool:
    return find_header_column(cells, _HEADER_NAME_KEYWORDS) is not None


def _extract_from_tables(section_text: str, page: int) -> list[ExtractedMedication]:
    results: list[ExtractedMedication] = []
    for block in find_table_blocks(section_text, _is_medication_table_header):
        name_col = find_header_column(block.header, _HEADER_NAME_KEYWORDS)
        if name_col is None:
            continue
        dose_col = find_header_column(block.header, _HEADER_DOSE_KEYWORDS)
        route_col = find_header_column(block.header, _HEADER_ROUTE_KEYWORDS)
        freq_col = find_header_column(block.header, _HEADER_FREQUENCY_KEYWORDS)

        for row in block.rows:
            if name_col >= len(row):
                continue
            name = row[name_col].strip()
            if not name:
                continue
            results.append(
                ExtractedMedication(
                    medication_name=name,
                    dose=_cell(row, dose_col),
                    route=_cell(row, route_col),
                    frequency=_cell(row, freq_col),
                    source_page=page,
                    source_excerpt=" | ".join(row),
                )
            )
    return results


def _cell(row: list[str], index: int | None) -> str | None:
    if index is None or index >= len(row):
        return None
    return row[index].strip() or None


def _extract_from_lines(section_text: str, page: int) -> list[ExtractedMedication]:
    results: list[ExtractedMedication] = []
    for raw_line in section_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or " | " in stripped:
            continue

        dose_match = _DOSE_PATTERN.search(stripped)
        if not dose_match:
            continue  # require at least a recognizable dose to count as a real hit

        name = stripped[: dose_match.start()].strip(" -*•")
        if not name or not name[0].isupper():
            continue

        route_match = _ROUTE_PATTERN.search(stripped)
        freq_match = _FREQUENCY_PATTERN.search(stripped)
        results.append(
            ExtractedMedication(
                medication_name=name,
                dose=dose_match.group().strip(),
                route=route_match.group().strip() if route_match else None,
                frequency=freq_match.group().strip() if freq_match else None,
                source_page=page,
                source_excerpt=stripped,
            )
        )
    return results
