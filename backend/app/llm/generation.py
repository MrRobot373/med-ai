"""Ollama generation client — shared by `app/chat/` (Phase 08) and `app/vision/`
(Phase 09), since both are just different callers of the same local model (spec §58
"use Qwen3.5 vision capability rather than loading a second large VLM into GPU
memory" — there is exactly one model, one endpoint, one concurrency budget, whether
the call carries images or not). Real token streaming (spec §119 "no fake streaming"),
never simulated by chunking an already-complete response client-side.

A single process-wide semaphore enforces spec §121 ("do not launch multiple
simultaneous heavy Qwen generations for the same user unintentionally") — sized from
`settings.chat_max_concurrent_generations` (default 1, appropriate for a one-machine
demo; a real multi-user deployment would raise it, still without needing a separate
task queue per spec §135). Vision calls share this exact semaphore rather than getting
their own, so a chat generation and a vision analysis can never run concurrently and
contend for the same 8 GB of VRAM.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from app.config.settings import Settings
from app.logging import get_logger

logger = get_logger(__name__)

_semaphore: asyncio.Semaphore | None = None
_semaphore_size: int | None = None


def _get_semaphore(settings: Settings) -> asyncio.Semaphore:
    global _semaphore, _semaphore_size
    if _semaphore is None or _semaphore_size != settings.chat_max_concurrent_generations:
        _semaphore = asyncio.Semaphore(settings.chat_max_concurrent_generations)
        _semaphore_size = settings.chat_max_concurrent_generations
    return _semaphore


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str
    # Base64-encoded image bytes (no data: URI prefix) — Ollama's per-message
    # `images` field. None/empty for every text-only chat call; vision analysis is
    # the only caller that populates this (spec §59's "Qwen3.5 Vision" stage).
    images: list[str] | None = None


class GenerationError(Exception):
    """Raised when Ollama is unreachable, the configured model is missing, or
    generation otherwise fails outright — distinct from an honest abstention, which is
    a normal, successfully-generated answer (spec §119 "show a meaningful error if
    generation fails")."""


def _message_dict(m: ChatMessage) -> dict:
    d = {"role": m.role, "content": m.content}
    if m.images:
        d["images"] = m.images
    return d


async def generate_stream(
    messages: list[ChatMessage],
    settings: Settings,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
) -> AsyncIterator[str]:
    """Yields content deltas as they arrive from Ollama. The caller breaking out of
    iteration early (e.g. spec §120 cancellation on client disconnect) closes the
    underlying HTTP stream via the `async with` block's exit, which also releases the
    concurrency semaphore — no generation keeps running unattended in the background."""
    semaphore = _get_semaphore(settings)
    async with semaphore:
        payload = {
            "model": settings.ollama_model,
            "messages": [_message_dict(m) for m in messages],
            "stream": True,
            # Hybrid-reasoning models (e.g. qwen3.5) default to an extended "thinking"
            # phase that Ollama returns in a separate `message.thinking` field, never
            # `message.content`. We only ever read `content`, so left enabled this is
            # not just wasted compute — confirmed live, a trivial prompt burned 2200+
            # thinking tokens (~5 minutes) before any visible content, and under a
            # constrained num_predict the thinking phase alone can exhaust the whole
            # token budget, yielding an EMPTY answer with nothing ever streamed. Also
            # doubly correct per spec's "no hidden chain-of-thought" requirement —
            # disabling it outright is more honest than silently discarding it.
            "think": False,
            "options": {
                "temperature": settings.chat_temperature if temperature is None else temperature,
                "num_predict": settings.chat_max_output_tokens if max_output_tokens is None else max_output_tokens,
            },
        }
        url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
        try:
            async with (
                httpx.AsyncClient(timeout=settings.ollama_request_timeout_seconds) as client,
                client.stream("POST", url, json=payload) as response,
            ):
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except ValueError:
                        continue  # a malformed line is skipped, not fatal to the whole stream
                    if chunk.get("error"):
                        raise GenerationError(str(chunk["error"]))
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if chunk.get("done"):
                        return
        except httpx.HTTPError as exc:
            logger.warning("Ollama streaming generation failed", exc_info=True)
            raise GenerationError(f"Could not reach Ollama at {url}: {exc}") from exc


async def generate_complete(
    messages: list[ChatMessage],
    settings: Settings,
    json_format: bool = False,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
) -> str:
    """Non-streaming — used for the grounding-validation pass and vision structured
    extraction, both of which need one complete, parseable response rather than a
    token stream a clinician watches live."""
    semaphore = _get_semaphore(settings)
    async with semaphore:
        payload = {
            "model": settings.ollama_model,
            "messages": [_message_dict(m) for m in messages],
            "stream": False,
            "think": False,  # see generate_stream's comment on why thinking is disabled outright
            "options": {
                "temperature": settings.chat_temperature if temperature is None else temperature,
                "num_predict": settings.chat_max_output_tokens if max_output_tokens is None else max_output_tokens,
            },
        }
        if json_format:
            payload["format"] = "json"
        url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=settings.ollama_request_timeout_seconds) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            logger.warning("Ollama generation failed", exc_info=True)
            raise GenerationError(f"Could not reach Ollama at {url}: {exc}") from exc

        if data.get("error"):
            raise GenerationError(str(data["error"]))
        return data.get("message", {}).get("content", "")
