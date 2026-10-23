"""Renderers for the patient-file documents: lab reports, imaging reports, discharge
summaries, OPD prescriptions, ECG printouts, radiographs/ultrasound frames with the
usual burned-in header, and DICOM files.

All people and organisations are fictional. Images come from openly licensed
datasets (see assets/manifest.json); the text around them is written for this set."""

from __future__ import annotations

import io
import textwrap
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
FONTS = HERE / "fonts"
A4 = (595, 842)
MARGIN = 42
INK = (0.12, 0.13, 0.16)
MUTED = (0.42, 0.44, 0.5)
RULE = (0.82, 0.84, 0.88)


@dataclass
class Org:
    name: str
    tagline: str
    address: str
    phone: str
    color: tuple[float, float, float]
    email: str = ""
    initials: str = ""


@dataclass
class Person:
    """The patient as printed on a document."""

    name: str  # "Mr. Rohit Verma"
    age: str  # "69 Y"
    sex: str  # "Male"
    uhid: str
    phone: str = ""
    dob: date | None = None
    extra: dict = field(default_factory=dict)


def fmt_d(d: date | datetime) -> str:
    return d.strftime("%d/%m/%Y")


def fmt_dt(d: datetime) -> str:
    return d.strftime("%d/%m/%Y %I:%M %p")


class Pdf:
    """Thin helper over PyMuPDF with embedded Liberation Sans (Arial metrics)."""

    def __init__(self) -> None:
        self.doc = pymupdf.open()
        self.page: pymupdf.Page | None = None
        self.y = 0.0
        self.footer_lines: list[str] = []

    def new_page(self) -> pymupdf.Page:
        self.page = self.doc.new_page(width=A4[0], height=A4[1])
        for name, file in (("ls", "LiberationSans-Regular.ttf"), ("lsb", "LiberationSans-Bold.ttf"), ("lsi", "LiberationSans-Italic.ttf")):
            self.page.insert_font(fontname=name, fontfile=str(FONTS / file))
        return self.page

    def text(self, x, y, s, size=9.0, bold=False, italic=False, color=INK) -> None:
        self.page.insert_text((x, y), s, fontsize=size, fontname="lsb" if bold else "lsi" if italic else "ls", color=color)

    def rtext(self, x_right, y, s, size=9.0, bold=False, color=INK) -> None:
        font = pymupdf.Font(fontfile=str(FONTS / ("LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf")))
        self.text(x_right - font.text_length(s, fontsize=size), y, s, size, bold, color=color)

    def width(self, s, size=9.0, bold=False) -> float:
        font = pymupdf.Font(fontfile=str(FONTS / ("LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf")))
        return font.text_length(s, fontsize=size)

    def wrap(self, x, s, size=9.0, width=None, bold=False, gap=1.45, color=INK) -> None:
        width = width or (A4[0] - MARGIN - x)
        chars = max(20, int(width / (size * 0.5)))
        for para in s.split("\n"):
            for line in textwrap.wrap(para, chars) or [""]:
                self.ensure(size * gap + 2)
                self.y += size * gap
                self.text(x, self.y, line, size, bold, color=color)

    def wrap_beside(self, x, s, size, *, clear_below: float, narrow: float, bold=False, gap=1.45) -> None:
        """Wraps line by line: narrow while beside a figure (above clear_below), full width after."""
        words = s.split()
        line = ""
        while words:
            width = narrow if self.y + size * gap < clear_below else A4[0] - MARGIN - x
            chars = max(20, int(width / (size * 0.5)))
            line = words.pop(0)
            while words and len(line) + 1 + len(words[0]) <= chars:
                line += " " + words.pop(0)
            self.ensure(size * gap + 2)
            self.y += size * gap
            self.text(x, self.y, line, size, bold)

    def rule(self, y=None, color=RULE, width=0.6, x0=MARGIN, x1=A4[0] - MARGIN) -> None:
        y = self.y if y is None else y
        self.page.draw_line((x0, y), (x1, y), color=color, width=width)

    def box(self, rect, fill=None, color=None, width=0.6, radius=None) -> None:
        self.page.draw_rect(pymupdf.Rect(*rect), color=color, fill=fill, width=width, radius=radius)

    def image(self, rect, data: bytes) -> None:
        self.page.insert_image(pymupdf.Rect(*rect), stream=data, keep_proportion=True)

    def ensure(self, needed: float) -> None:
        if self.y + needed > A4[1] - 70:
            self.footer()
            self.new_page()
            self.y = MARGIN + 10

    def footer(self) -> None:
        y = A4[1] - 38
        self.rule(y - 12)
        for i, line in enumerate(self.footer_lines):
            self.text(MARGIN, y + i * 10, line, 7, color=MUTED)

    def finish(self) -> bytes:
        self.footer()
        n = len(self.doc)
        for i, page in enumerate(self.doc, start=1):
            self.page = page
            self.rtext(A4[0] - MARGIN, A4[1] - 26, f"Page {i} of {n}", 7, color=MUTED)
        self.doc.subset_fonts()  # embed only the glyphs used
        data = self.doc.tobytes(garbage=4, deflate=True)
        self.doc.close()
        return data


def letterhead(pdf: Pdf, org: Org, title: str | None = None) -> None:
    pdf.new_page()
    c = org.color
    pdf.box((0, 0, A4[0], 6), fill=c)
    # emblem
    pdf.box((MARGIN, 22, MARGIN + 38, 60), fill=c, radius=0.25)
    ini = org.initials or "".join(w[0] for w in org.name.split()[:2]).upper()
    pdf.text(MARGIN + 19 - pdf.width(ini, 14, True) / 2, 46, ini, 14, True, color=(1, 1, 1))
    pdf.text(MARGIN + 50, 38, org.name, 15, True, color=c)
    pdf.text(MARGIN + 50, 51, org.tagline, 8, color=MUTED)
    pdf.rtext(A4[0] - MARGIN, 32, org.address, 7.5, color=MUTED)
    pdf.rtext(A4[0] - MARGIN, 43, f"Tel: {org.phone}", 7.5, color=MUTED)
    if org.email:
        pdf.rtext(A4[0] - MARGIN, 54, org.email, 7.5, color=MUTED)
    pdf.rule(70, color=c, width=1.2)
    pdf.y = 70
    if title:
        pdf.y += 20
        pdf.text(A4[0] / 2 - pdf.width(title, 11.5, True) / 2, pdf.y, title, 11.5, True)
        pdf.y += 4


def patient_block(pdf: Pdf, p: Person, left: list[tuple[str, str]], right: list[tuple[str, str]]) -> None:
    rows = max(len(left), len(right))
    top = pdf.y + 8
    h = rows * 13 + 10
    pdf.box((MARGIN, top, A4[0] - MARGIN, top + h), color=RULE, fill=(0.975, 0.98, 0.985), width=0.6)
    for i, (k, v) in enumerate(left):
        y = top + 15 + i * 13
        pdf.text(MARGIN + 8, y, k, 8, color=MUTED)
        pdf.text(MARGIN + 82, y, ": " + v, 8.5, bold=(k == "Patient Name"))
    for i, (k, v) in enumerate(right):
        y = top + 15 + i * 13
        pdf.text(330, y, k, 8, color=MUTED)
        pdf.text(410, y, ": " + v, 8.5)
    pdf.y = top + h + 6


def signature(pdf: Pdf, people: list[tuple[str, str]], note: str | None = None) -> None:
    pdf.ensure(70)
    pdf.y += 26
    if note:
        pdf.text(MARGIN, pdf.y, note, 7.5, italic=True, color=MUTED)
        pdf.y += 18
    x = A4[0] - MARGIN
    for name, role in reversed(people):
        w = max(pdf.width(name, 9, True), pdf.width(role, 7.5)) + 4
        pdf.text(x - w, pdf.y + 12, name, 9, True)
        pdf.text(x - w, pdf.y + 23, role, 7.5, color=MUTED)
        x -= w + 40
    pdf.y += 30


# --------------------------------------------------------------------------------------------
# Laboratory report
# --------------------------------------------------------------------------------------------


def lab_report(
    org: Org,
    p: Person,
    *,
    collected: datetime,
    reported: datetime,
    ref_by: str,
    lab_no: str,
    sections: list[tuple[str, list]],
    pathologists: list[tuple[str, str]],
    notes: list[str] | None = None,
    sample: str = "Blood",
) -> bytes:
    """sections: [(heading, rows)] where a row is (test, result, unit, range[, method]) or ("#", note)."""
    pdf = Pdf()
    pdf.footer_lines = [f"{org.name} · {org.address}", "Results relate only to the sample received. Electronically verified report."]
    letterhead(pdf, org, "LABORATORY REPORT")
    patient_block(
        pdf,
        p,
        [("Patient Name", p.name), ("Age / Sex", f"{p.age} / {p.sex}"), ("Patient ID", p.uhid), ("Referred By", ref_by)],
        [("Lab No.", lab_no), ("Sample", sample), ("Collected", fmt_dt(collected)), ("Reported", fmt_dt(reported))],
    )
    cols = (MARGIN + 6, 262, 312, 342, 418)

    def header():
        pdf.y += 14
        pdf.box((MARGIN, pdf.y - 10, A4[0] - MARGIN, pdf.y + 4), fill=(0.93, 0.94, 0.96))
        for x, h in zip(cols, ("INVESTIGATION", "RESULT", "", "UNIT", "BIOLOGICAL REF. INTERVAL"), strict=True):
            pdf.text(x, pdf.y, h, 7.5, True, color=MUTED)
        pdf.y += 4

    for heading, rows in sections:
        pdf.ensure(60)
        pdf.y += 24
        pdf.text(MARGIN, pdf.y, heading.upper(), 9.5, True, color=org.color)
        header()
        for row in rows:
            if row[0] == "#":
                pdf.wrap(MARGIN + 6, row[1], 7.5, color=MUTED)
                continue
            test, result, unit, rng = row[:4]
            method = row[4] if len(row) > 4 else None
            pdf.ensure(16)
            pdf.y += 14
            flag = _flag(result, rng)
            pdf.text(cols[0], pdf.y, test, 9)
            pdf.text(cols[1], pdf.y, result, 9, bold=bool(flag))
            if flag:
                pdf.text(cols[2], pdf.y, flag, 9, True, color=(0.75, 0.1, 0.1))
            pdf.text(cols[3], pdf.y, unit, 8.5)
            pdf.text(cols[4], pdf.y, rng, 8.5)
            if method:
                pdf.y += 9
                pdf.text(cols[0] + 6, pdf.y, f"Method: {method}", 6.8, italic=True, color=MUTED)
            pdf.rule(pdf.y + 4, color=(0.9, 0.91, 0.93), width=0.4)
    if notes:
        pdf.y += 12
        pdf.ensure(40)
        pdf.text(MARGIN, pdf.y + 4, "Interpretation / Comments", 8.5, True)
        pdf.y += 4
        for n in notes:
            pdf.wrap(MARGIN, "• " + n, 8)
    pdf.y += 10
    pdf.text(A4[0] / 2 - 40, pdf.y + 6, "*** End of Report ***", 8, color=MUTED)
    signature(pdf, pathologists)
    return pdf.finish()


def _flag(result: str, rng: str) -> str:
    try:
        v = float(result.replace(",", ""))
    except ValueError:
        return ""
    r = rng.replace(" ", "")
    try:
        if "-" in r and not r.startswith("<") and not r.startswith(">"):
            lo, hi = (float(x) for x in r.split("-")[:2])
            return "L" if v < lo else "H" if v > hi else ""
        if r.startswith("<"):
            return "H" if v >= float(r.lstrip("<=")) else ""
        if r.startswith(">"):
            return "L" if v <= float(r.lstrip(">=")) else ""
    except ValueError:
        return ""
    return ""


# --------------------------------------------------------------------------------------------
# Imaging / cardiology report
# --------------------------------------------------------------------------------------------


def imaging_report(
    org: Org,
    p: Person,
    *,
    when: datetime,
    ref_by: str,
    study: str,
    accession: str,
    sections: list[tuple[str, str]],
    impression: list[str],
    doctors: list[tuple[str, str]],
    key_image: bytes | None = None,
    modality: str = "",
) -> bytes:
    pdf = Pdf()
    pdf.footer_lines = [
        f"{org.name} · {org.address}",
        "This report is a professional opinion based on the images and should be correlated clinically.",
    ]
    letterhead(pdf, org, study.upper())
    patient_block(
        pdf,
        p,
        [("Patient Name", p.name), ("Age / Sex", f"{p.age} / {p.sex}"), ("Patient ID", p.uhid), ("Referred By", ref_by)],
        [
            ("Accession No.", accession),
            ("Modality", modality or "-"),
            ("Study Date", fmt_d(when)),
            ("Reported", fmt_dt(when.replace(hour=min(when.hour + 2, 20)))),
        ],
    )
    clear_below, narrow = 0.0, A4[0] - 2 * MARGIN
    if key_image:
        img_w = 150
        top = pdf.y + 12
        pdf.box((A4[0] - MARGIN - img_w, top, A4[0] - MARGIN, top + img_w), fill=(0, 0, 0))
        pdf.image((A4[0] - MARGIN - img_w + 2, top + 2, A4[0] - MARGIN - 2, top + img_w - 2), key_image)
        pdf.text(A4[0] - MARGIN - img_w, top + img_w + 10, "Key image", 7, color=MUTED)
        clear_below, narrow = top + img_w + 16, A4[0] - 2 * MARGIN - img_w - 14
    for heading, body in sections:
        pdf.ensure(40)
        pdf.y += 16
        pdf.text(MARGIN, pdf.y, heading.upper(), 8.5, True, color=org.color)
        pdf.y += 2
        for para in body.split("\n"):
            pdf.wrap_beside(MARGIN, para, 9, clear_below=clear_below, narrow=narrow)
    pdf.ensure(40)
    pdf.y += 18
    pdf.text(MARGIN, pdf.y, "IMPRESSION", 9, True, color=org.color)
    for i, line in enumerate(impression, start=1):
        pdf.wrap_beside(MARGIN + 4, f"{i}. {line}", 9.3, clear_below=clear_below, narrow=narrow - 4, bold=True)
    pdf.y = max(pdf.y, clear_below - 10)
    signature(pdf, doctors, "Kindly correlate clinically. Not valid for medico-legal purposes.")
    return pdf.finish()


# --------------------------------------------------------------------------------------------
# Discharge summary
# --------------------------------------------------------------------------------------------


def discharge_summary(
    org: Org,
    p: Person,
    *,
    admitted: datetime,
    discharged: datetime,
    ipd_no: str,
    consultant: str,
    department: str,
    diagnosis: list[str],
    sections: list[tuple[str, str]],
    investigations: list[tuple[str, str, str, str]] | None,
    medicines: list[tuple[str, str, str, str]],
    advice: list[str],
    follow_up: str,
    doctors: list[tuple[str, str]],
) -> bytes:
    pdf = Pdf()
    pdf.footer_lines = [f"{org.name} · {org.address}", "In case of emergency contact the hospital casualty, available 24 x 7."]
    letterhead(pdf, org, "DISCHARGE SUMMARY")
    patient_block(
        pdf,
        p,
        [("Patient Name", p.name), ("Age / Sex", f"{p.age} / {p.sex}"), ("UHID", p.uhid), ("Consultant", consultant)],
        [("IPD No.", ipd_no), ("Department", department), ("Admitted", fmt_dt(admitted)), ("Discharged", fmt_dt(discharged))],
    )

    def head(t):
        pdf.ensure(40)
        pdf.y += 17
        pdf.text(MARGIN, pdf.y, t.upper(), 8.5, True, color=org.color)
        pdf.y += 2

    head("Final diagnosis")
    for d in diagnosis:
        pdf.wrap(MARGIN + 4, "• " + d, 9.3, bold=True)
    for t, body in sections:
        head(t)
        pdf.wrap(MARGIN, body, 9)
    if investigations:
        head("Key investigations")
        for test, value, unit, rng in investigations:
            pdf.ensure(14)
            pdf.y += 13
            pdf.text(MARGIN + 4, pdf.y, test, 8.8)
            pdf.text(250, pdf.y, value, 8.8, True)
            pdf.text(305, pdf.y, unit, 8.3)
            pdf.text(380, pdf.y, rng, 8.3, color=MUTED)
    head("Medicines on discharge")
    pdf.y += 12
    for x, h in zip((MARGIN + 4, 210, 300, 420), ("Medicine", "Dose", "When", "Duration"), strict=True):
        pdf.text(x, pdf.y, h, 7.5, True, color=MUTED)
    for i, (drug, dose, when_, dur) in enumerate(medicines, start=1):
        pdf.ensure(14)
        pdf.y += 13
        pdf.text(MARGIN + 4, pdf.y, f"{i}. {drug}", 9, True)
        pdf.text(210, pdf.y, dose, 8.8)
        pdf.text(300, pdf.y, when_, 8.8)
        pdf.text(420, pdf.y, dur, 8.8)
    head("Advice on discharge")
    for a in advice:
        pdf.wrap(MARGIN + 4, "• " + a, 9)
    head("Follow-up")
    pdf.wrap(MARGIN, follow_up, 9)
    signature(pdf, doctors)
    return pdf.finish()


# --------------------------------------------------------------------------------------------
# OPD prescription (another doctor's clinic)
# --------------------------------------------------------------------------------------------


def opd_prescription(
    clinic: Org,
    doctor: tuple[str, str, str],
    p: Person,
    *,
    when: datetime,
    vitals: str,
    complaints: str,
    findings: str,
    diagnosis: str,
    medicines: list[tuple[str, str, str, str]],
    advice: list[str],
    follow_up: str | None,
    investigations: list[str] | None = None,
) -> bytes:
    pdf = Pdf()
    pdf.footer_lines = [
        f"{clinic.name} · {clinic.address} · Tel {clinic.phone}",
        "Not valid for medico-legal purposes. Please bring this prescription on your next visit.",
    ]
    pdf.new_page()
    c = clinic.color
    pdf.box((0, 0, A4[0], 6), fill=c)
    name, quals, role = doctor
    pdf.text(MARGIN, 40, name, 16, True, color=c)
    pdf.text(MARGIN, 53, quals, 8.5, color=MUTED)
    pdf.text(MARGIN, 64, role, 8.5, color=MUTED)
    pdf.rtext(A4[0] - MARGIN, 36, clinic.name, 11, True)
    pdf.rtext(A4[0] - MARGIN, 48, clinic.address, 7.5, color=MUTED)
    pdf.rtext(A4[0] - MARGIN, 58, f"Tel: {clinic.phone}", 7.5, color=MUTED)
    pdf.rule(76, color=c, width=1.2)
    pdf.y = 92
    pdf.text(MARGIN, pdf.y, f"{p.name}", 10, True)
    pdf.text(MARGIN + pdf.width(p.name, 10, True) + 10, pdf.y, f"{p.age} / {p.sex}   ·   ID {p.uhid}", 8.5, color=MUTED)
    pdf.rtext(A4[0] - MARGIN, pdf.y, f"Date: {fmt_d(when)}", 9)
    pdf.y += 13
    if vitals:
        pdf.text(MARGIN, pdf.y, vitals, 8.5, color=MUTED)
    pdf.rule(pdf.y + 7)
    pdf.y += 8

    def block(label, body):
        if not body:
            return
        pdf.y += 14
        pdf.text(MARGIN, pdf.y, label, 8.5, True, color=c)
        lines = textwrap.wrap(body, 92) or [""]
        pdf.text(MARGIN + 74, pdf.y, lines[0], 9)
        for line in lines[1:]:
            pdf.y += 12
            pdf.text(MARGIN + 74, pdf.y, line, 9)

    block("C/o", complaints)
    block("O/E", findings)
    block("Diagnosis", diagnosis)
    pdf.y += 26
    pdf.page.insert_text((MARGIN, pdf.y), "Rx", fontsize=22, fontname="lsb", color=c)
    pdf.y += 4
    for i, (drug, dose, when_, dur) in enumerate(medicines, start=1):
        pdf.ensure(30)
        pdf.y += 18
        pdf.text(MARGIN + 10, pdf.y, f"{i}.  {drug}", 10, True)
        pdf.y += 12
        pdf.text(MARGIN + 28, pdf.y, f"{dose}   —   {when_}   —   {dur}", 8.8, color=(0.25, 0.27, 0.32))
    if investigations:
        pdf.y += 18
        pdf.text(MARGIN, pdf.y, "Investigations advised", 8.5, True, color=c)
        for inv in investigations:
            pdf.wrap(MARGIN + 6, "• " + inv, 9)
    if advice:
        pdf.y += 16
        pdf.text(MARGIN, pdf.y, "Advice", 8.5, True, color=c)
        for a in advice:
            pdf.wrap(MARGIN + 6, "• " + a, 9)
    if follow_up:
        pdf.y += 16
        pdf.text(MARGIN, pdf.y, "Review", 8.5, True, color=c)
        pdf.text(MARGIN + 74, pdf.y, follow_up, 9)
    pdf.y = max(pdf.y + 40, 680)
    pdf.rtext(A4[0] - MARGIN, pdf.y, name, 9.5, True)
    pdf.rtext(A4[0] - MARGIN, pdf.y + 11, quals, 7.5, color=MUTED)
    return pdf.finish()


# --------------------------------------------------------------------------------------------
# Images
# --------------------------------------------------------------------------------------------


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / ("LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf")), size)


def burn_in(
    image_path: Path,
    *,
    institution: str,
    name: str,
    sex_age: str,
    uhid: str,
    when: datetime,
    study: str,
    extra: list[str] | None = None,
    max_side: int = 1600,
    quality: int = 90,
) -> bytes:
    """Export-style radiograph/ultrasound frame: the corner annotations a PACS export carries."""
    im = Image.open(image_path).convert("L")
    if max(im.size) > max_side:
        im.thumbnail((max_side, max_side), Image.LANCZOS)
    w, h = im.size
    canvas = im.convert("RGB")
    d = ImageDraw.Draw(canvas)
    s = max(12, int(w / 62))
    f, fb = _font(s), _font(s, True)
    left = [(institution.upper(), fb), (name.upper(), fb), (f"{sex_age}   ID: {uhid}", f), (when.strftime("%d-%b-%Y %H:%M").upper(), f)]
    right = [(study.upper(), fb)] + [(e, f) for e in (extra or [])]
    pad = int(s * 0.7)
    for i, (t, font) in enumerate(left):
        _shadow_text(d, (pad, pad + i * int(s * 1.35)), t, font)
    for i, (t, font) in enumerate(right):
        tw = d.textlength(t, font=font)
        _shadow_text(d, (w - pad - tw, pad + i * int(s * 1.35)), t, font)
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _shadow_text(d: ImageDraw.ImageDraw, xy, text, font) -> None:
    x, y = xy
    d.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0))
    d.text((x, y), text, font=font, fill=(235, 235, 235))


def to_dicom(
    pixels: np.ndarray,
    *,
    modality: str,
    name: str,
    uhid: str,
    dob: date | None,
    sex: str,
    when: datetime,
    institution: str,
    study: str,
    series: str,
    body_part: str,
    window: tuple[float, float],
    spacing: tuple[float, float] = (0.5, 0.5),
    thickness: float | None = None,
    intercept: float = 0.0,
    referring: str = "",
    accession: str = "",
) -> bytes:
    """A single-frame DICOM image with the identifying and study tags a real export carries."""
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import (
        CTImageStorage,
        ExplicitVRLittleEndian,
        MRImageStorage,
        generate_uid,
    )

    sop = CTImageStorage if modality == "CT" else MRImageStorage
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = sop
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID, ds.SOPInstanceUID = sop, meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID, ds.SeriesInstanceUID = generate_uid(), generate_uid()
    parts = name.split()
    ds.PatientName = f"{parts[-1]}^{' '.join(parts[:-1])}".upper()
    ds.PatientID = uhid
    if dob:
        ds.PatientBirthDate = dob.strftime("%Y%m%d")
    ds.PatientSex = {"male": "M", "female": "F"}.get(sex.lower(), "O")
    ds.Modality, ds.BodyPartExamined = modality, body_part
    ds.StudyDescription, ds.SeriesDescription = study, series
    ds.StudyDate = ds.SeriesDate = ds.ContentDate = when.strftime("%Y%m%d")
    ds.StudyTime = ds.ContentTime = when.strftime("%H%M%S")
    ds.InstitutionName = institution
    ds.ReferringPhysicianName = referring
    ds.AccessionNumber = accession
    ds.Manufacturer = "Siemens Healthineers" if modality == "CT" else "GE Healthcare"
    rows, cols = pixels.shape
    ds.Rows, ds.Columns = rows, cols
    ds.SamplesPerPixel, ds.PhotometricInterpretation = 1, "MONOCHROME2"
    if pixels.dtype == np.uint8:
        ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 8, 8, 7, 0
    else:
        pixels = pixels.astype(np.int16)
        ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 16, 16, 15, 1
    ds.RescaleIntercept, ds.RescaleSlope = intercept, 1
    ds.WindowCenter, ds.WindowWidth = window
    ds.PixelSpacing = list(spacing)
    if thickness:
        ds.SliceThickness = thickness
    ds.PixelData = pixels.tobytes()
    buf = io.BytesIO()
    ds.save_as(buf, enforce_file_format=True)
    return buf.getvalue()


# --------------------------------------------------------------------------------------------
# ECG printout from a real PTB-XL recording
# --------------------------------------------------------------------------------------------

LEADS = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]


def read_wfdb(dat: Path) -> np.ndarray:
    """PTB-XL format-16 record → (samples, 12) array in mV (gain 1000/mV, baseline 0)."""
    raw = np.frombuffer(dat.read_bytes(), dtype="<i2")
    return raw.reshape(-1, 12).astype(np.float32) / 1000.0


def heart_rate(lead_ii: np.ndarray, fs: int = 500) -> tuple[int, list[int]]:
    x = lead_ii - np.median(lead_ii)
    thr = 0.55 * np.percentile(x, 99.5)
    peaks, last = [], -fs
    for i in range(1, len(x) - 1):
        if x[i] > thr and x[i] >= x[i - 1] and x[i] >= x[i + 1] and i - last > 0.3 * fs:
            peaks.append(i)
            last = i
    if len(peaks) < 2:
        return 0, peaks
    rr = np.diff(peaks) / fs
    return int(round(60 / rr.mean())), peaks


def ecg_printout(
    dat: Path, *, institution: str, name: str, sex_age: str, uhid: str, when: datetime, interpretation: list[str], referring: str
) -> bytes:
    sig = read_wfdb(dat)
    fs = 500
    hr, _ = heart_rate(sig[:, 1], fs)
    px_mm = 7  # 25 mm/s, 10 mm/mV
    W, H = int(277 * px_mm), int(190 * px_mm)
    top = int(30 * px_mm)
    im = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(im)
    grid_top, grid_bottom = top, H - int(8 * px_mm)
    for mm in range(278):
        x = mm * px_mm
        d.line([(x, grid_top), (x, grid_bottom)], fill=(244, 196, 196) if mm % 5 else (230, 140, 140), width=1)
    for mm in range(int((grid_bottom - grid_top) / px_mm) + 1):
        y = grid_top + mm * px_mm
        d.line([(0, y), (W, y)], fill=(244, 196, 196) if mm % 5 else (230, 140, 140), width=1)
    f, fb, fs_ = _font(int(px_mm * 2.6)), _font(int(px_mm * 3.0), True), _font(int(px_mm * 2.2))
    d.text((px_mm * 4, px_mm * 3), name.upper(), font=fb, fill=(20, 20, 20))
    d.text((px_mm * 4, px_mm * 7.5), f"{sex_age}    ID: {uhid}", font=f, fill=(20, 20, 20))
    d.text((px_mm * 4, px_mm * 11.5), when.strftime("%d-%b-%Y %H:%M").upper() + f"    Ref: {referring}", font=f, fill=(20, 20, 20))
    d.text((px_mm * 4, px_mm * 16), institution, font=fs_, fill=(70, 70, 70))
    d.text((px_mm * 110, px_mm * 3), f"Vent. rate   {hr} BPM", font=f, fill=(20, 20, 20))
    for i, line in enumerate(interpretation):
        d.text((px_mm * 110, px_mm * (7.5 + i * 4)), line, font=fb if i == 0 else f, fill=(20, 20, 20))
    d.text((px_mm * 210, px_mm * 24), "25 mm/s   10 mm/mV   0.05-150 Hz   12 SL", font=fs_, fill=(70, 70, 70))
    # 3 x 4 layout, 2.5 s each, plus 10 s lead II rhythm strip
    seg = int(2.5 * fs)
    row_h = (grid_bottom - grid_top) / 4
    for r in range(3):
        for c in range(4):
            lead = r + 3 * c
            data = sig[c * seg : (c + 1) * seg, lead]
            _trace(d, data, x0=c * 2.5 * 25 * px_mm + px_mm * 6, y0=grid_top + row_h * (r + 0.5), px_mm=px_mm, fs=fs)
            d.text((c * 2.5 * 25 * px_mm + px_mm * 7, grid_top + row_h * r + px_mm * 2), LEADS[lead], font=fb, fill=(10, 10, 10))
    _trace(d, sig[: int(10 * fs), 1], x0=px_mm * 6, y0=grid_top + row_h * 3.5, px_mm=px_mm, fs=fs, scale_len=10)
    d.text((px_mm * 7, grid_top + row_h * 3 + px_mm * 2), "II", font=fb, fill=(10, 10, 10))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=82, optimize=True)
    return buf.getvalue()


def _trace(d: ImageDraw.ImageDraw, data: np.ndarray, *, x0, y0, px_mm, fs, scale_len=2.5) -> None:
    data = data - np.median(data)
    end = int(scale_len * fs)
    pts = [(x0 + (i / fs) * 25 * px_mm, y0 - v * 10 * px_mm) for i, v in enumerate(data[:end]) if i % 2 == 0]
    d.line(pts, fill=(15, 15, 15), width=2)
