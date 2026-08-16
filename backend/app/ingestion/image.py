"""Image handling — loading/normalizing uploaded images and PDF-rendered pages before
OCR or vision analysis, and reading basic dimensions for provenance/`Attachment`-style
metadata.
"""

from __future__ import annotations

import base64
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


def normalize_image(content: bytes, max_dimension: int = 2000) -> bytes:
    """Converts to RGB PNG and downsizes very large images — keeps OCR (Phase 05) and
    vision analysis (Phase 09) fast without materially hurting recognition quality for
    typical document photos/scans. Both callers pass their own `max_dimension`
    (OCR: 2000px default; vision: `settings.vision_max_image_dimension`, 1600px
    default) rather than sharing one hardcoded value."""
    with Image.open(BytesIO(content)) as img:
        img = img.convert("RGB")
        if max(img.size) > max_dimension:
            ratio = max_dimension / max(img.size)
            img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))))
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()


def normalize_image_b64(content: bytes, max_dimension: int) -> str:
    """`normalize_image()` + base64-encode — Ollama's `images` field wants a plain
    base64 string, no `data:` URI prefix."""
    return base64.b64encode(normalize_image(content, max_dimension)).decode("ascii")
