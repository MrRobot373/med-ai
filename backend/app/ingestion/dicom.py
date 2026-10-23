"""DICOM (radiology) support: header metadata as searchable text, and pixel data
rendered to an 8-bit PNG for previews and vision-model description."""

from __future__ import annotations

import io

from PIL import Image

_META_FIELDS = [
    ("Modality", "Modality"),
    ("BodyPartExamined", "Body part"),
    ("StudyDescription", "Study"),
    ("SeriesDescription", "Series"),
    ("StudyDate", "Study date"),
    ("InstitutionName", "Institution"),
    ("PatientName", "Patient name"),
    ("PatientID", "Patient ID"),
    ("SliceThickness", "Slice thickness"),
    ("ImageComments", "Comments"),
]


def is_dicom(data: bytes) -> bool:
    return len(data) > 132 and data[128:132] == b"DICM"


def _read(data: bytes):
    import pydicom

    return pydicom.dcmread(io.BytesIO(data), force=True)


def metadata_text(data: bytes) -> str:
    ds = _read(data)
    lines = ["## DICOM study"]
    for tag, label in _META_FIELDS:
        value = getattr(ds, tag, None)
        if value not in (None, ""):
            if tag == "StudyDate" and len(str(value)) == 8:
                value = f"{str(value)[:4]}-{str(value)[4:6]}-{str(value)[6:]}"
            if tag == "PatientID":
                lines.append(f"MRN: {value}")
            else:
                lines.append(f"{label}: {value}")
    return "\n".join(lines)


def study_date(data: bytes) -> str | None:
    value = str(getattr(_read(data), "StudyDate", "") or "")
    return f"{value[:4]}-{value[4:6]}-{value[6:]}" if len(value) == 8 and value.isdigit() else None


def render_png(data: bytes, max_dim: int = 1600) -> bytes:
    import numpy as np

    ds = _read(data)
    arr = ds.pixel_array.astype("float32")
    if arr.ndim == 3 and arr.shape[-1] not in (3, 4):  # multi-frame: middle frame
        arr = arr[arr.shape[0] // 2]
    try:
        from pydicom.pixels import apply_modality_lut, apply_voi_lut

        # Stored values → real units (e.g. Hounsfield) first; the window is defined in those units.
        arr = apply_modality_lut(arr, ds).astype("float32")
        arr = apply_voi_lut(arr, ds).astype("float32")
    except Exception:
        center, width = getattr(ds, "WindowCenter", None), getattr(ds, "WindowWidth", None)
        if center is not None and width is not None:
            c = float(center[0] if hasattr(center, "__len__") else center)
            w = float(width[0] if hasattr(width, "__len__") else width)
            arr = np.clip(arr, c - w / 2, c + w / 2)
    lo, hi = float(arr.min()), float(arr.max())
    arr = (arr - lo) / (hi - lo or 1.0) * 255.0
    if getattr(ds, "PhotometricInterpretation", "") == "MONOCHROME1":
        arr = 255.0 - arr
    img = Image.fromarray(arr.astype("uint8"))
    img.thumbnail((max_dim, max_dim))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
