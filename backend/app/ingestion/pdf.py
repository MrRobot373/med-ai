"""PDF reading and page rendering on pypdfium2 (Apache-2.0 / BSD) — no AGPL code.

PDFium is not thread-safe, and request handlers run on a thread pool, so every call into it goes
through one process-wide lock. Pages are small and rendering is fast; the lock is held only while
a document is open.
"""

from __future__ import annotations

import io
import threading

import pypdfium2 as pdfium
from PIL import Image

from app.core.errors import AppError

_lock = threading.RLock()

#: A page is split into a new word when the gap to the previous character exceeds this fraction
#: of the character height (PDFs that place words without a space character).
_WORD_GAP = 0.45


def page_count(data: bytes) -> int:
    with _lock:
        pdf = pdfium.PdfDocument(data)
        try:
            return len(pdf)
        finally:
            pdf.close()


def check_limits(data: bytes, max_pages: int) -> int:
    """Rejects documents with an implausible number of pages (zip-bomb style PDFs) and returns the count."""
    try:
        n = page_count(data)
    except Exception as exc:  # corrupt or encrypted file
        raise AppError(
            "This PDF could not be opened. It may be damaged or password-protected.", status_code=415
        ) from exc
    if n > max_pages:
        raise AppError(
            f"This PDF has {n} pages; the limit is {max_pages}. Split it and upload the parts.", status_code=413
        )
    return n


def _words(page) -> list[tuple[float, float, float, float, str]]:
    """Words as (x0, y0, x1, y1, text) with the origin at the top-left, like most layout tools."""
    height = page.get_size()[1]
    tp = page.get_textpage()
    try:
        n = tp.count_chars()
        if not n:
            return []
        # Walk the characters one by one so each box stays aligned with its character.
        out: list[tuple[float, float, float, float, str]] = []
        cur: list[str] = []
        box: list[float] | None = None
        last_right = None
        word_h = 0.0

        def flush():
            nonlocal cur, box, last_right
            if cur and box:
                out.append((box[0], height - box[3], box[2], height - box[1], "".join(cur)))
            cur, box, last_right = [], None, None

        for i in range(n):
            ch = tp.get_text_range(i, 1)
            if not ch or ch.isspace() or ch in "\x00\x02￾￿":
                flush()
                continue
            left, bottom, right, top = tp.get_charbox(i)
            h = top - bottom
            if h <= 0.1:  # generated/degenerate box
                flush()
                continue
            # Compare the gap with the tallest character so far: "." and "-" have tiny boxes.
            if cur and last_right is not None and (left - last_right) > max(word_h, h) * _WORD_GAP:
                flush()
            if box is None:
                box = [left, bottom, right, top]
                word_h = h
            else:
                box = [min(box[0], left), min(box[1], bottom), max(box[2], right), max(box[3], top)]
                word_h = max(word_h, h)
            cur.append(ch)
            last_right = right
        flush()
        return out
    finally:
        tp.close()


def layout_text(words: list[tuple]) -> str:
    """Rebuilds printed lines from word positions. Words on one baseline form a line;
    a wide horizontal gap becomes " | " so column layouts (lab tables) keep their cells:
    "Haemoglobin | 12.9 | g/dL | 13.0 - 17.0 | L". Prose keeps ordinary spacing."""
    if not words:
        return ""
    rows: list[list] = []
    for w in sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        mid = (w[1] + w[3]) / 2
        if rows and abs(mid - rows[-1][0][4]) <= max(2.5, (w[3] - w[1]) * 0.35):
            rows[-1][1].append(w)
        else:
            rows.append([(0, 0, 0, 0, mid), [w]])
    lines = []
    for _anchor, row in rows:
        row.sort(key=lambda w: w[0])
        height = max(w[3] - w[1] for w in row) or 10
        parts = [row[0][4]]
        for prev, cur in zip(row, row[1:], strict=False):
            gap = cur[0] - prev[2]
            sep = " | " if gap > height * 1.6 and prev[4] != "|" and cur[4] != "|" else " "
            parts.append(sep + cur[4])
        lines.append("".join(parts))
    return "\n".join(lines)


def extract_pages(data: bytes) -> list[dict]:
    """[{"page": 1, "text": ...}] with table columns kept apart."""
    with _lock:
        pdf = pdfium.PdfDocument(data)
        try:
            pages = []
            for i in range(len(pdf)):
                page = pdf[i]
                try:
                    text = layout_text(_words(page))
                    if not text:
                        tp = page.get_textpage()
                        try:
                            text = tp.get_text_range() or ""
                        finally:
                            tp.close()
                finally:
                    page.close()
                pages.append({"page": i + 1, "text": text})
            return pages
        finally:
            pdf.close()


def render_png(data: bytes, page_no: int, *, width: int | None = None, dpi: int | None = None) -> tuple[bytes, int]:
    """PNG of one page (1-based, clamped) and the page count. Give a pixel `width` or a `dpi`."""
    with _lock:
        pdf = pdfium.PdfDocument(data)
        try:
            count = len(pdf)
            page = pdf[min(max(page_no, 1), count) - 1]
            try:
                w_pt = max(page.get_size()[0], 1)
                scale = (width / w_pt) if width else ((dpi or 150) / 72)
                img = page.render(scale=scale).to_pil().convert("RGB")
            finally:
                page.close()
        finally:
            pdf.close()
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue(), count


def guard_image(data: bytes, max_pixels: int) -> None:
    """Rejects images whose decoded size is absurd (decompression bombs) without decoding them fully."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.width * im.height > max_pixels:
                raise AppError(
                    f"This image is {im.width}×{im.height} pixels, which is more than the {max_pixels:,}-pixel limit.",
                    status_code=413,
                )
    except AppError:
        raise
    except Exception as exc:
        raise AppError("This image could not be read.", status_code=415) from exc
