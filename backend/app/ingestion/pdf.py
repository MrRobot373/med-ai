"""PDF text extraction — spec §57 "Scanned Documents", §56 "Table Handling".

Uses `pymupdf` (the modern import name — the `fitz` alias is deprecated). Tables are
converted to pipe-delimited text with a `[Table]` marker rather than being dropped,
per spec §56.
"""

from __future__ import annotations

from dataclasses import dataclass

import pymupdf


@dataclass
class PageContent:
    page: int
    text: str
    method: str  # "text" | "ocr"


@dataclass
class PdfExtractionResult:
    pages: list[PageContent]
    page_count: int


def extract_pdf_text(content: bytes) -> PdfExtractionResult:
    doc = pymupdf.open(stream=content, filetype="pdf")
    try:
        pages: list[PageContent] = []
        for index, page in enumerate(doc):
            text = (page.get_text("text") or "").strip()
            table_text = _extract_tables(page)
            if table_text:
                text = f"{text}\n\n{table_text}".strip()
            pages.append(PageContent(page=index + 1, text=text, method="text"))
        return PdfExtractionResult(pages=pages, page_count=doc.page_count)
    finally:
        doc.close()


def render_page_png(content: bytes, page_number: int, dpi: int = 200) -> bytes:
    """Renders one page to a PNG — used as OCR input when a page's extracted text is
    too sparse to be the real content (i.e. it's a scanned image)."""
    doc = pymupdf.open(stream=content, filetype="pdf")
    try:
        page = doc[page_number - 1]
        pixmap = page.get_pixmap(dpi=dpi)
        return pixmap.tobytes("png")
    finally:
        doc.close()


def _extract_tables(page: pymupdf.Page) -> str:
    try:
        tables = page.find_tables()
    except Exception:  # noqa: BLE001 - table-finding is best-effort, never fatal
        return ""
    blocks = []
    for table in tables:
        rows = table.extract()
        if not rows:
            continue
        lines = [" | ".join("" if cell is None else str(cell).strip() for cell in row) for row in rows]
        blocks.append("[Table]\n" + "\n".join(lines))
    return "\n\n".join(blocks)
