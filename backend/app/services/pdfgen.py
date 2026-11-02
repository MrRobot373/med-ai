"""PDF documents the server produces: prescriptions, letters and certificates.

One renderer for every output, so what is printed, downloaded and shared is the same page. Built with
ReportLab (BSD) and the Liberation Sans fonts (SIL OFL) embedded, so the PDF looks the same on every
machine and prints without the browser's header and footer.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, A5, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.services.runtime_config import PrintConfig

ASSETS = Path(__file__).resolve().parents[1] / "assets"
FREQ = {
    "OD": "Once a day",
    "BD": "Twice a day",
    "TDS": "Three times a day",
    "QID": "Four times a day",
    "HS": "At bedtime",
    "SOS": "When needed",
    "STAT": "Immediately, once",
    "Weekly": "Once a week",
}
PAPER = {"A4": A4, "A5": A5, "Letter": letter}
SIZES = {"small": 8.6, "medium": 9.8, "large": 11.2}
MUTED = colors.HexColor("#5B6B82")
HAIRLINE = colors.HexColor("#D5DCE6")
SHADE = colors.HexColor("#F3F6FA")
_fonts_ready = False


def _fonts() -> None:
    global _fonts_ready
    if _fonts_ready:
        return
    for name, file in (("LS", "Regular"), ("LS-B", "Bold"), ("LS-I", "Italic")):
        pdfmetrics.registerFont(TTFont(name, str(ASSETS / "fonts" / f"LiberationSans-{file}.ttf")))
    pdfmetrics.registerFontFamily("LS", normal="LS", bold="LS-B", italic="LS-I", boldItalic="LS-B")
    _fonts_ready = True


@dataclass
class Party:
    name: str = ""
    lines: list[str] = field(default_factory=list)


@dataclass
class Sheet:
    """Everything a letterhead page needs, resolved from branding, print settings, branch and doctor."""

    org_title: str
    org_subtitle: str
    address_lines: list[str]
    contact_line: str
    registration_line: str
    footer_text: str
    disclaimer: str
    logo_png: bytes | None
    doctor_name: str
    doctor_lines: list[str]
    signature_png: bytes | None
    cfg: PrintConfig


def _data_url_bytes(url: str | None) -> bytes | None:
    if not url or "," not in url:
        return None
    try:
        return base64.b64decode(url.split(",", 1)[1])
    except Exception:
        return None


def _flat_png(raw: bytes | None, max_px: int = 600) -> bytes | None:
    """Re-encodes any image as an opaque PNG (ReportLab is fussy about alpha and palettes)."""
    if not raw:
        return None
    try:
        from PIL import Image as PILImage

        im = PILImage.open(io.BytesIO(raw)).convert("RGBA")
        bg = PILImage.new("RGBA", im.size, "white")
        bg.alpha_composite(im)
        out = bg.convert("RGB")
        out.thumbnail((max_px, max_px))
        buf = io.BytesIO()
        out.save(buf, "PNG")
        return buf.getvalue()
    except Exception:
        return None


def default_logo() -> bytes:
    return (ASSETS / "brand-mark.png").read_bytes()


def make_sheet(
    cfg: PrintConfig,
    *,
    organization: str,
    tagline: str,
    logo_data_url: str | None,
    branch: dict | None,
    doctor: dict | None,
) -> Sheet:
    b = branch or {}
    address = (b.get("address") or cfg.address or "").strip()
    phone = b.get("phone") or cfg.phone
    email = b.get("email") or cfg.email
    contact = "  ·  ".join(x for x in (f"Tel {phone}" if phone else "", email, cfg.website) if x)
    reg = "  ·  ".join(
        x for x in (b.get("registration") or cfg.clinic_registration, f"GSTIN {cfg.tax_id}" if cfg.tax_id else "") if x
    )
    d = doctor or {}
    dlines = []
    if d.get("qualifications"):
        dlines.append(d["qualifications"])
    if cfg.show_registration_no and d.get("registration_no"):
        council = f" ({d['registration_council']})" if d.get("registration_council") else ""
        dlines.append(f"Reg. No. {d['registration_no']}{council}")
    if d.get("phone"):
        dlines.append(f"Tel {d['phone']}")
    return Sheet(
        org_title=cfg.title or organization,
        org_subtitle=cfg.subtitle or tagline,
        address_lines=[ln.strip() for ln in address.splitlines() if ln.strip()],
        contact_line=contact,
        registration_line=reg,
        footer_text=b.get("footer_text") or cfg.footer_text,
        disclaimer=cfg.disclaimer,
        logo_png=(_flat_png(_data_url_bytes(logo_data_url)) or default_logo()) if cfg.show_logo else None,
        doctor_name=d.get("name", ""),
        doctor_lines=dlines,
        signature_png=_flat_png(_data_url_bytes(d.get("signature_data_url")), 500),
        cfg=cfg,
    )


def _styles(cfg: PrintConfig) -> dict[str, ParagraphStyle]:
    _fonts()
    base = SIZES[cfg.font_size]
    accent = colors.HexColor(cfg.accent if cfg.accent.startswith("#") and len(cfg.accent) in (4, 7) else "#16233B")
    s = {
        "body": ParagraphStyle(
            "body", fontName="LS", fontSize=base, leading=base * 1.35, textColor=colors.HexColor("#111827")
        ),
    }
    s["small"] = ParagraphStyle(
        "small", parent=s["body"], fontSize=base - 1.4, leading=(base - 1.4) * 1.35, textColor=MUTED
    )
    s["muted"] = ParagraphStyle("muted", parent=s["body"], textColor=MUTED)
    s["bold"] = ParagraphStyle("bold", parent=s["body"], fontName="LS-B")
    s["title"] = ParagraphStyle(
        "title", parent=s["body"], fontName="LS-B", fontSize=base + 5, leading=(base + 5) * 1.2, textColor=accent
    )
    s["h"] = ParagraphStyle(
        "h", parent=s["body"], fontName="LS-B", fontSize=base, textColor=accent, spaceBefore=base * 0.9, spaceAfter=2
    )
    s["th"] = ParagraphStyle(
        "th", parent=s["body"], fontName="LS-B", fontSize=base - 1.6, leading=(base - 1.6) * 1.3, textColor=MUTED
    )
    s["right"] = ParagraphStyle("right", parent=s["body"], alignment=TA_RIGHT)
    s["rightbold"] = ParagraphStyle("rightbold", parent=s["bold"], alignment=TA_RIGHT)
    s["rightsmall"] = ParagraphStyle("rightsmall", parent=s["small"], alignment=TA_RIGHT)
    s["center"] = ParagraphStyle("center", parent=s["small"], alignment=TA_CENTER)
    s["rx"] = ParagraphStyle(
        "rx", fontName="Times-BoldItalic", fontSize=base * 2.6, leading=base * 3.0, textColor=accent
    )
    s["_accent"] = accent  # type: ignore[assignment]
    return s


def _p(text: str | None, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text or "").replace("\n", "<br/>"), style)


def _letterhead(sheet: Sheet, st: dict, width: float) -> list:
    accent = st["_accent"]
    left: list = [_p(sheet.org_title, st["title"])]
    if sheet.org_subtitle:
        left.append(_p(sheet.org_subtitle, st["small"]))
    for ln in sheet.address_lines:
        left.append(_p(ln, st["small"]))
    if sheet.contact_line:
        left.append(_p(sheet.contact_line, st["small"]))
    if sheet.registration_line:
        left.append(_p(sheet.registration_line, st["small"]))
    cells = []
    widths = []
    if sheet.logo_png:
        img = Image(io.BytesIO(sheet.logo_png))
        h = 15 * mm
        img.drawHeight = h
        img.drawWidth = h * img.imageWidth / img.imageHeight
        cells.append(img)
        widths.append(img.drawWidth + 4 * mm)
    right_w = 56 * mm if sheet.doctor_name or sheet.doctor_lines else 0
    cells.append(left)
    widths.append(width - sum(widths) - right_w)
    if right_w:
        right = [_p(sheet.doctor_name, st["rightbold"])] + [_p(x, st["rightsmall"]) for x in sheet.doctor_lines]
        cells.append(right)
        widths.append(right_w)
    t = Table([cells], colWidths=widths)
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("LINEBELOW", (0, 0), (-1, 0), 1.4, accent),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ]
        )
    )
    return [t, Spacer(1, 4 * mm)]


def _qr(text: str, size: float = 20 * mm) -> Drawing:
    w = QrCodeWidget(text, barLevel="M")
    x0, y0, x1, y1 = w.getBounds()
    d = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    d.add(w)
    return d


def _build(flow: list, sheet: Sheet, *, title: str, running_label: str) -> bytes:
    _fonts()
    cfg = sheet.cfg
    page = PAPER[cfg.paper]
    margin = (10 if cfg.paper == "A5" else 14) * mm
    buf = io.BytesIO()
    footer_h = 14 * mm
    doc = BaseDocTemplate(
        buf,
        pagesize=page,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin + footer_h,
        title=title,
        author=sheet.org_title,
        subject=running_label,
    )
    frame = Frame(
        margin,
        margin + footer_h,
        page[0] - 2 * margin,
        page[1] - 2 * margin - footer_h,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="body",
    )
    base = SIZES[cfg.font_size]

    def decorate(canvas, d):
        canvas.saveState()
        canvas.setFont("LS", base - 2)
        canvas.setFillColor(MUTED)
        y = margin + footer_h - 3 * mm
        canvas.setStrokeColor(HAIRLINE)
        canvas.setLineWidth(0.5)
        canvas.line(margin, y + 2 * mm, page[0] - margin, y + 2 * mm)
        lines = [x for x in (sheet.footer_text, sheet.disclaimer) if x]
        for i, ln in enumerate(lines[:2]):
            canvas.drawString(margin, y - i * (base - 0.5), ln[:160])
        canvas.drawRightString(page[0] - margin, y, f"Page {d.page}")
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=decorate)])
    doc.build(flow)
    return buf.getvalue()


def _signature_block(sheet: Sheet, st: dict, width: float, code: str | None, rx_id: str | None) -> Table:
    cfg = sheet.cfg
    left: list = []
    if rx_id:
        left.append(_p(f"Prescription ID {rx_id[:8].upper()}", st["small"]))
    if code and cfg.show_qr:
        left.append(Spacer(1, 1.5 * mm))
        left.append(_qr(code))
        left.append(_p("Scan to verify", st["small"]))
    sig: list = []
    if sheet.signature_png:
        img = Image(io.BytesIO(sheet.signature_png))
        h = 13 * mm
        img.drawHeight, img.drawWidth = h, h * img.imageWidth / img.imageHeight
        img.hAlign = "CENTER"
        sig.append(img)
    else:
        sig.append(Spacer(1, 13 * mm))
    sig.append(_p(sheet.doctor_name, st["center"]))
    sig.append(_p(cfg.signature_label, st["center"]))
    t = Table([[left, sig]], colWidths=[width - 62 * mm, 62 * mm])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("LINEABOVE", (1, 0), (1, 0), 0.6, MUTED),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return t


def prescription_pdf(rx: dict, sheet: Sheet) -> bytes:
    """`rx` is the printable view built by `printing.prescription_view`."""
    cfg = sheet.cfg
    st = _styles(cfg)
    accent = st["_accent"]
    page = PAPER[cfg.paper]
    width = page[0] - 2 * (10 if cfg.paper == "A5" else 14) * mm

    flow: list = _letterhead(sheet, st, width)
    pt = rx["patient"]
    who = f"<b>{escape(pt['name'])}</b>  ·  {escape(str(pt['age']) + ' y' if pt.get('age') is not None else '—')}  ·  {escape(pt.get('sex') or '')}  ·  {escape(pt['mrn'])}"
    if pt.get("phone"):
        who += f"  ·  {escape(pt['phone'])}"
    box = [[Paragraph(who, st["body"]), Paragraph(f"Date: <b>{escape(rx['date'])}</b>", st["right"])]]
    v = rx.get("vitals") or {}
    vit = [
        f"BP {v['bp']}" if v.get("bp") else "",
        f"Pulse {v['hr']}" if v.get("hr") else "",
        f"Temp {v['temp_f']}°F" if v.get("temp_f") else "",
        f"SpO2 {v['spo2']}%" if v.get("spo2") else "",
        f"Weight {v['weight_kg']} kg" if v.get("weight_kg") else "",
    ]
    vit = [x for x in vit if x]
    if cfg.show_vitals and vit:
        box.append([_p("  ·  ".join(vit), st["small"]), ""])
    t = Table(box, colWidths=[width * 0.72, width * 0.28])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SHADE),
                ("BOX", (0, 0), (-1, -1), 0.5, HAIRLINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("SPAN", (0, 1), (1, 1)) if len(box) > 1 else ("NOP", (0, 0), (0, 0)),
            ]
        )
    )
    flow.append(t)
    if cfg.show_complaint and rx.get("complaint"):
        flow.append(Spacer(1, 2.5 * mm))
        flow.append(Paragraph(f"<b>Complaint:</b> {escape(rx['complaint'])}", st["body"]))
    if rx.get("diagnosis"):
        flow.append(Spacer(1, 1 * mm))
        flow.append(Paragraph(f"<b>Diagnosis:</b> {escape(rx['diagnosis'])}", st["body"]))

    flow.append(Paragraph("Rx", st["rx"]))
    head = [Paragraph(h, st["th"]) for h in ("#", "MEDICINE", "DOSE", "WHEN", "DAYS", "INSTRUCTIONS")]
    rows = [head]
    for n, i in enumerate(rx["items"], start=1):
        med = f"<b>{escape(i['drug'])}</b>"
        if cfg.show_generic and i.get("generic"):
            gen = " + ".join(g.replace("_", " ") for g in i["generic"].split("+"))
            med += f"<br/><font size='{SIZES[cfg.font_size] - 1.6}' color='#5B6B82'>{escape(gen)}</font>"
        when = escape(i["frequency"]) + (
            f"<br/><font size='{SIZES[cfg.font_size] - 1.6}' color='#5B6B82'>{FREQ[i['frequency']]}</font>"
            if i["frequency"] in FREQ
            else ""
        )
        rows.append(
            [
                Paragraph(str(n), st["muted"]),
                Paragraph(med, st["body"]),
                Paragraph(escape(i["dose"] or ""), st["body"]),
                Paragraph(when, st["body"]),
                Paragraph(str(i["duration_days"] if i.get("duration_days") is not None else "—"), st["body"]),
                Paragraph(escape(i.get("instructions") or ""), st["body"]),
            ]
        )
    cw = [7 * mm, width * 0.34, width * 0.12, width * 0.17, 11 * mm]
    cw.append(width - sum(cw))
    tbl = Table(rows, colWidths=cw, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, accent),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, HAIRLINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ]
        )
    )
    flow.append(tbl)

    if rx.get("advice"):
        flow.append(Paragraph("Advice", st["h"]))
        flow.append(_p(rx["advice"], st["body"]))
    if rx.get("follow_up"):
        note = f" — {cfg.follow_up_note}" if cfg.follow_up_note else ""
        flow.append(Spacer(1, 2 * mm))
        flow.append(Paragraph(f"<b>Follow-up:</b> {escape(rx['follow_up'])}{escape(note)}", st["body"]))
    flow.append(Spacer(1, 10 * mm))
    flow.append(KeepTogether([_signature_block(sheet, st, width, rx.get("verify_code"), rx.get("id"))]))
    return _build(flow, sheet, title=f"Prescription — {pt['name']}", running_label="Prescription")


def render_first_page_png(pdf: bytes, width: int = 900) -> bytes:
    from app.ingestion import pdf as pdf_io

    return pdf_io.render_png(pdf, 1, width=width)[0]


def today_str(d: date | None = None) -> str:
    return (d or date.today()).strftime("%d %b %Y")
