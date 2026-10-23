"""Vision-model helpers: transcribing scanned pages/images into searchable text during
ingestion, and structured image analysis for the Vision tool."""

from __future__ import annotations

import base64
import io

from PIL import Image

from app.ai import registry
from app.ai.llm import ChatMessage, parse_json_response
from app.services.runtime_config import RuntimeConfig

TRANSCRIBE_PROMPT = (
    "You are transcribing a clinical document image for a medical records system.\n"
    "1. Transcribe ALL legible text exactly as written, preserving tables as 'cell | cell' rows.\n"
    "2. Do not add interpretation, do not guess illegible values — write [illegible] instead.\n"
    "3. If the image is a clinical photo or scan with little text, add a final section "
    "'## Visual description' with a neutral, factual description of what is visible."
)

ANALYSIS_PROMPT = """You are assisting a clinician by describing a medical image. Be factual and cautious.
Return JSON only, with exactly these keys:
{
  "image_type": "short description of what kind of image this is",
  "quality": "good | limited | poor, with a short reason",
  "observations": ["neutral visual observations, one per item"],
  "measurements": [{"name": "...", "value": "...", "unit": "..."}],
  "text_found": "any legible text, verbatim",
  "possible_considerations": ["findings a clinician may want to evaluate further, phrased as considerations, not diagnoses"],
  "limitations": ["what cannot be determined from this image"],
  "recommended_review": "what a clinician should verify"
}
Never state a definitive diagnosis. Never invent measurements that are not visible. Use empty lists when nothing applies."""


def prepare_image(data: bytes, max_dim: int) -> tuple[str, str]:
    img = Image.open(io.BytesIO(data))
    img.load()
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((max_dim, max_dim))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode(), "image/png"


async def transcribe(cfg: RuntimeConfig, image_bytes: bytes) -> str:
    b64, mime = prepare_image(image_bytes, cfg.vision.max_image_dimension)
    client = registry.vision_llm(cfg)
    return await client.complete(
        [ChatMessage("user", TRANSCRIBE_PROMPT, images=[b64], image_mime=mime)], temperature=0, max_tokens=2048
    )


async def analyze(cfg: RuntimeConfig, image_bytes: bytes, question: str | None = None) -> tuple[dict, str]:
    b64, mime = prepare_image(image_bytes, cfg.vision.max_image_dimension)
    client = registry.vision_llm(cfg)
    prompt = ANALYSIS_PROMPT + (f"\n\nThe clinician also asks: {question}" if question else "")
    text = await client.complete(
        [ChatMessage("user", prompt, images=[b64], image_mime=mime)], json_mode=True, max_tokens=2048
    )
    return parse_json_response(text), client.model
