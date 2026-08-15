"""Shared pipe-delimited table parsing — reused by `labs.py` and `medications.py`.

`pdf.py`, `docx.py`, and `xlsx.py` all render extracted tables the same way: rows
joined with `" | "` (PDF/DOCX additionally prefix a `[Table]` marker line; XLSX doesn't
need one since a whole sheet already reads as one logical block). This module finds
those blocks and, given a set of recognized header keywords, tells the caller which
column is which — so `labs.py`/`medications.py` don't each re-implement table detection.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class TableBlock:
    header: list[str]
    rows: list[list[str]]


def find_table_blocks(text: str, is_header: Callable[[list[str]], bool]) -> list[TableBlock]:
    """Splits page/sheet text into tables.

    A single contiguous run of pipe-delimited lines can itself contain more than one
    logical table back-to-back with no blank line between them — e.g. an XLSX sheet
    where a 2-column "Patient Name | Elena Novak" identity block precedes the real
    "Test | Result | Unit | Reference Range" data table, because `xlsx.py` silently
    drops fully-empty rows rather than preserving them as a blank-line separator. So
    rather than always treating a run's first line as its header, this looks for lines
    the caller recognizes as a genuine header (`is_header`) and starts a new table at
    each one. Rows appearing before any recognized header have nothing to attach to and
    are dropped — never guessed into a wrong table.
    """
    blocks: list[TableBlock] = []
    current_header: list[str] | None = None
    current_rows: list[list[str]] = []

    def _flush() -> None:
        nonlocal current_header, current_rows
        if current_header is not None and current_rows:
            blocks.append(TableBlock(header=current_header, rows=current_rows))
        current_header = None
        current_rows = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == "[Table]" or not line:
            _flush()
            continue
        if " | " not in line:
            _flush()
            continue

        cells = [c.strip() for c in line.split(" | ")]
        if is_header(cells):
            _flush()
            current_header = cells
        elif current_header is not None:
            current_rows.append(cells)
        # else: a pipe-delimited line before any recognized header in this run —
        # nothing to attach it to, so it's dropped rather than misused as a header.

    _flush()
    return blocks


def find_header_column(header: list[str], keywords: tuple[str, ...]) -> int | None:
    """Index of the first header cell whose text contains any of `keywords`
    (case-insensitive substring match) — or None if no column matches."""
    for index, cell in enumerate(header):
        lowered = cell.lower()
        if any(keyword in lowered for keyword in keywords):
            return index
    return None
