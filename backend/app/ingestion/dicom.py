"""DICOM support — spec §62. Detection, metadata summary, best-effort preview
generation, and a de-identification utility for demo workflows.

Scoped deliberately: this is metadata reading + a flat preview image, not a PACS
viewer. Pixel-data decoding is wrapped in a broad try/except because compressed
transfer syntaxes need optional codec packages (pylibjpeg/gdcm) this project doesn't
bundle — "safe preview generation when supported" (spec §62) means exactly that: it
degrades to "not available" rather than crashing ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import pydicom

# Tags cleared by `deidentify()` — deliberately narrow (direct identifiers only) rather
# than a full DICOM PS3.15 de-identification profile, which is out of scope for a demo
# utility. Never claim this output is suitable for real clinical de-identification.
IDENTIFYING_TAGS = (
    "PatientName",
    "PatientID",
    "PatientBirthDate",
    "PatientAddress",
    "PatientTelephoneNumbers",
    "OtherPatientIDs",
    "OtherPatientNames",
    "InstitutionName",
    "InstitutionAddress",
    "ReferringPhysicianName",
)


@dataclass
class DicomSummary:
    modality: str | None
    study_description: str | None
    series_description: str | None
    rows: int | None
    columns: int | None
    contains_identifiers: bool


def is_dicom(head_bytes: bytes) -> bool:
    return head_bytes[128:132] == b"DICM"


def read_summary(content: bytes) -> DicomSummary:
    dataset = pydicom.dcmread(BytesIO(content), force=True)
    contains_identifiers = any(
        getattr(dataset, tag, None) not in (None, "") for tag in IDENTIFYING_TAGS
    )
    return DicomSummary(
        modality=_str_or_none(getattr(dataset, "Modality", None)),
        study_description=_str_or_none(getattr(dataset, "StudyDescription", None)),
        series_description=_str_or_none(getattr(dataset, "SeriesDescription", None)),
        rows=int(dataset.Rows) if hasattr(dataset, "Rows") else None,
        columns=int(dataset.Columns) if hasattr(dataset, "Columns") else None,
        contains_identifiers=contains_identifiers,
    )


def render_preview_png(content: bytes) -> bytes | None:
    try:
        dataset = pydicom.dcmread(BytesIO(content), force=True)
        pixels = dataset.pixel_array.astype("float32")
    except Exception:  # noqa: BLE001 - any decode failure just means "no preview"
        return None

    from PIL import Image  # local import: keep dicom.py usable without Pillow present

    pixels -= pixels.min()
    peak = pixels.max()
    if peak > 0:
        pixels = pixels / peak * 255.0
    image = Image.fromarray(pixels.astype("uint8"))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def deidentify(content: bytes) -> bytes:
    dataset = pydicom.dcmread(BytesIO(content), force=True)
    for tag in IDENTIFYING_TAGS:
        if hasattr(dataset, tag):
            setattr(dataset, tag, "")
    buffer = BytesIO()
    dataset.save_as(buffer)
    return buffer.getvalue()


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
