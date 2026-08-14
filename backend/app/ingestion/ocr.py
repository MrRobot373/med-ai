"""OCR engine wrapper — lazy-loaded easyocr, CPU-only (spec §12: OCR runs on CPU,
leaving the GPU free for the main LLM). Same "honest not-loaded status" pattern as
`app/integrations/embedding_health.py` — model weights (~100 MB) download on first
real use, not at import/health-check time.
"""

from __future__ import annotations

import importlib.util
import threading
from dataclasses import dataclass

from app.config.settings import Settings

_reader = None
_reader_lock = threading.Lock()


@dataclass
class OcrHealth:
    package_installed: bool
    enabled: bool
    status: str  # "ready" | "not_loaded" | "package_missing" | "disabled"
    error: str | None = None


@dataclass
class OcrResult:
    text: str
    mean_confidence: float | None


def check_ocr_health(settings: Settings) -> OcrHealth:
    installed = importlib.util.find_spec("easyocr") is not None

    if not settings.enable_ocr:
        return OcrHealth(package_installed=installed, enabled=False, status="disabled")

    if not installed:
        return OcrHealth(
            package_installed=False,
            enabled=True,
            status="package_missing",
            error="easyocr is not installed. Install the 'ocr' extra to enable scanned-document support.",
        )

    return OcrHealth(package_installed=True, enabled=True, status="ready" if _reader is not None else "not_loaded")


def _get_reader():
    global _reader
    if _reader is None:
        with _reader_lock:
            if _reader is None:
                import easyocr

                _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def run_ocr(image_bytes: bytes) -> OcrResult:
    """Raises if easyocr isn't installed — callers must check `check_ocr_health` first
    and treat OCR as unavailable rather than letting this raise mid-pipeline."""
    reader = _get_reader()
    results = reader.readtext(image_bytes, detail=1)
    lines: list[str] = []
    confidences: list[float] = []
    for _bbox, text, confidence in results:
        lines.append(text)
        confidences.append(float(confidence))
    mean_confidence = sum(confidences) / len(confidences) if confidences else None
    return OcrResult(text="\n".join(lines), mean_confidence=mean_confidence)
