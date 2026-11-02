"""Builds small test PDFs with positioned text (reportlab, BSD-licensed)."""

from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def make_pdf(items: list[tuple[float, float, str]], *, size: int = 10) -> bytes:
    """items: (x, y_from_top, text) in PDF points on an A4 page."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    height = A4[1]
    c.setFont("Helvetica", size)
    for x, y, text in items:
        c.drawString(x, height - y, text)
    c.save()
    return buf.getvalue()


def lines_pdf(lines: list[str], *, x: float = 50, y: float = 60, step: float = 15, size: int = 10) -> bytes:
    return make_pdf([(x, y + i * step, line) for i, line in enumerate(lines)], size=size)
