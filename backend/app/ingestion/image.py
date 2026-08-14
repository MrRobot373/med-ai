"""Image handling — loading/normalizing uploaded images and PDF-rendered pages before
OCR, and reading basic dimensions for provenance/`Attachment`-style metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image


@dataclass
class ImageInfo:
    width: int
    height: int
    format: str | None


def load_image_info(content: bytes) -> ImageInfo:
    with Image.open(BytesIO(content)) as img:
        return ImageInfo(width=img.width, height=img.height, format=img.format)


def normalize_for_ocr(content: bytes, max_dimension: int = 2000) -> bytes:
    """Converts to RGB PNG and downsizes very large images — keeps OCR fast without
    materially hurting recognition quality for typical document photos/scans."""
    with Image.open(BytesIO(content)) as img:
        img = img.convert("RGB")
        if max(img.size) > max_dimension:
            ratio = max_dimension / max(img.size)
            img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))))
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()
