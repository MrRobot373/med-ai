"""XLSX text extraction — each sheet becomes one logical "page" for provenance
purposes, since spreadsheets have sheets rather than pages."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import openpyxl


@dataclass
class SheetContent:
    sheet_name: str
    text: str


def extract_xlsx_text(content: bytes) -> list[SheetContent]:
    workbook = openpyxl.load_workbook(BytesIO(content), data_only=True, read_only=True)
    try:
        results: list[SheetContent] = []
        for worksheet in workbook.worksheets:
            lines = []
            for row in worksheet.iter_rows(values_only=True):
                if all(cell is None for cell in row):
                    continue
                lines.append(" | ".join("" if cell is None else str(cell) for cell in row))
            if lines:
                results.append(SheetContent(sheet_name=worksheet.title, text="\n".join(lines)))
        return results
    finally:
        workbook.close()
