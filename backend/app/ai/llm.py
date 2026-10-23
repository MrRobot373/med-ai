"""LLM client — one interface over two wire protocols:

* `ollama`  — Ollama's native `/api/chat` (local models, multimodal via `images`).
* `openai`  — any OpenAI-compatible `/chat/completions` endpoint: OpenAI, LM Studio,
  vLLM, llama.cpp server, LocalAI, OpenRouter, Groq, Together, Azure-style gateways…

Streaming is real token streaming from the provider. A process-wide semaphore per
endpoint+model bounds concurrent generations (protects a single local GPU).
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import httpx

from app.core.errors import ServiceUnavailable
from app.core.logging import get_logger
from app.services.runtime_config import LLMConfig, VisionConfig

logger = get_logger(__name__)


@dataclass
class ChatMessage:
    role: str
    content: str
    images: list[str] = field(default_factory=list)  # base64 (no data: prefix)
    image_mime: str = "image/png"


class LLMError(ServiceUnavailable):
    pass


_semaphores: dict[tuple, asyncio.Semaphore] = {}


def _semaphore(cfg: LLMConfig) -> asyncio.Semaphore:
    key = (cfg.base_url, cfg.model, cfg.max_concurrency)
    sem = _semaphores.get(key)
    if sem is None:
        sem = _semaphores[key] = asyncio.Semaphore(cfg.max_concurrency)
    return sem


class _ThinkFilter:
    """Removes `<think>…</think>` spans that some servers inline into `content`."""

    def __init__(self) -> None:
        self.buffer = ""
        self.inside = False

    def feed(self, text: str) -> str:
        self.buffer += text
        out = []
        while self.buffer:
            if self.inside:
                end = self.buffer.find("</think>")
                if end == -1:
                    self.buffer = self.buffer[-8:]
                    return "".join(out)
                self.buffer = self.buffer[end + 8 :]
                self.inside = False
            else:
                start = self.buffer.find("<think>")
                if start == -1:
                    # keep a short tail in case a tag is split across chunks
                    safe = len(self.buffer) - 7
                    if safe > 0:
                        out.append(self.buffer[:safe])
                        self.buffer = self.buffer[safe:]
                    return "".join(out)
                out.append(self.buffer[:start])
                self.buffer = self.buffer[start + 7 :]
                self.inside = True
        return "".join(out)

    def flush(self) -> str:
        rest = "" if self.inside else self.buffer
        self.buffer = ""
        return rest


def _headers(cfg: LLMConfig) -> dict[str, str]:
    headers = {"Content-Type": "application/json", **cfg.extra_headers}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    return headers


def _base(cfg: LLMConfig) -> str:
    return cfg.base_url.rstrip("/")


class LLMClient:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    @property
    def model(self) -> str:
        return self.cfg.model

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> AsyncIterator[str]:
        temperature = self.cfg.temperature if temperature is None else temperature
        max_tokens = self.cfg.max_output_tokens if max_tokens is None else max_tokens
        think = _ThinkFilter()
        async with _semaphore(self.cfg):
            if self.cfg.provider == "ollama":
                gen = self._ollama_stream(messages, temperature, max_tokens, json_mode)
            else:
                gen = self._openai_stream(messages, temperature, max_tokens, json_mode)
            async for piece in gen:
                visible = piece if self.cfg.reasoning else think.feed(piece)
                if visible:
                    yield visible
            tail = think.flush()
            if tail and not self.cfg.reasoning:
                yield tail

    async def complete(self, messages: list[ChatMessage], **kwargs) -> str:
        parts = [p async for p in self.stream(messages, **kwargs)]
        return "".join(parts).strip()

    # ---- Ollama ---------------------------------------------------------------
    async def _ollama_stream(self, messages, temperature, max_tokens, json_mode) -> AsyncIterator[str]:
        payload: dict = {
            "model": self.cfg.model,
            "messages": [
                {"role": m.role, "content": m.content, **({"images": m.images} if m.images else {})} for m in messages
            ],
            "stream": True,
            "think": self.cfg.reasoning,
            "options": {"temperature": temperature, "num_predict": max_tokens, "num_ctx": self.cfg.context_window},
        }
        if json_mode:
            payload["format"] = "json"
        url = f"{_base(self.cfg)}/api/chat"
        for attempt in range(2):
            try:
                async with (
                    httpx.AsyncClient(timeout=self.cfg.timeout_seconds) as client,
                    client.stream("POST", url, json=payload, headers=_headers(self.cfg)) as resp,
                ):
                    if resp.status_code >= 400:
                        body = (await resp.aread()).decode(errors="replace")
                        if attempt == 0 and "think" in body.lower():
                            # Model does not support the `think` switch — retry without it.
                            payload.pop("think", None)
                            continue
                        raise LLMError(_explain_http(resp.status_code, body, self.cfg))
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                        except ValueError:
                            continue
                        if chunk.get("error"):
                            raise LLMError(f"Model error: {chunk['error']}")
                        content = (chunk.get("message") or {}).get("content") or ""
                        if content:
                            yield content
                        if chunk.get("done"):
                            return
                return
            except httpx.HTTPError as exc:
                raise LLMError(f"Cannot reach the language model at {url} ({exc.__class__.__name__}).") from exc

    # ---- OpenAI-compatible ----------------------------------------------------
    def _openai_messages(self, messages: list[ChatMessage]) -> list[dict]:
        out = []
        for m in messages:
            if m.images:
                parts: list[dict] = [{"type": "text", "text": m.content}]
                parts += [
                    {"type": "image_url", "image_url": {"url": f"data:{m.image_mime};base64,{img}"}} for img in m.images
                ]
                out.append({"role": m.role, "content": parts})
            else:
                out.append({"role": m.role, "content": m.content})
        return out

    async def _openai_stream(self, messages, temperature, max_tokens, json_mode) -> AsyncIterator[str]:
        payload: dict = {
            "model": self.cfg.model,
            "messages": self._openai_messages(messages),
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        url = f"{_base(self.cfg)}/chat/completions"
        for attempt in range(2):
            try:
                async with (
                    httpx.AsyncClient(timeout=self.cfg.timeout_seconds) as client,
                    client.stream("POST", url, json=payload, headers=_headers(self.cfg)) as resp,
                ):
                    if resp.status_code >= 400:
                        body = (await resp.aread()).decode(errors="replace")
                        if attempt == 0 and resp.status_code in (400, 422) and "response_format" in payload:
                            payload.pop("response_format")  # server lacks JSON mode; prompt still asks for JSON
                            continue
                        raise LLMError(_explain_http(resp.status_code, body, self.cfg))
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            return
                        try:
                            chunk = json.loads(data)
                        except ValueError:
                            continue
                        if chunk.get("error"):
                            raise LLMError(f"Model error: {chunk['error']}")
                        for choice in chunk.get("choices") or []:
                            content = (choice.get("delta") or {}).get("content") or ""
                            if content:
                                yield content
                return
            except httpx.HTTPError as exc:
                raise LLMError(f"Cannot reach the language model at {url} ({exc.__class__.__name__}).") from exc

    # ---- Discovery / health ---------------------------------------------------
    async def list_models(self) -> list[str]:
        return await list_models(self.cfg.provider, self.cfg.base_url, self.cfg.api_key)

    async def test(self) -> dict:
        started = time.perf_counter()
        reply = await self.complete(
            [ChatMessage("user", "Reply with the single word: ready")], max_tokens=16, temperature=0
        )
        return {"ok": True, "latency_ms": int((time.perf_counter() - started) * 1000), "sample": reply[:80]}


def _explain_http(status: int, body: str, cfg: LLMConfig) -> str:
    snippet = body.strip().replace("\n", " ")[:300]
    if status in (401, 403):
        return f"The model endpoint rejected the credentials (HTTP {status}). Check the API key."
    if status == 404 and "model" in snippet.lower():
        hint = f" Run: ollama pull {cfg.model}" if cfg.provider == "ollama" else ""
        return f"Model '{cfg.model}' is not available at {cfg.base_url}.{hint}"
    return f"Model endpoint error (HTTP {status}): {snippet}"


async def list_models(provider: str, base_url: str, api_key: str | None) -> list[str]:
    base = base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    url = f"{base}/api/tags" if provider == "ollama" else f"{base}/models"
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ServiceUnavailable(f"Could not list models at {url}: {exc}") from exc
    if provider == "ollama":
        return sorted(m.get("name", "") for m in data.get("models", []) if m.get("name"))
    return sorted(m.get("id", "") for m in data.get("data", []) if m.get("id"))


def vision_llm_config(main: LLMConfig, vision: VisionConfig) -> LLMConfig:
    if vision.use_main_llm:
        return main.model_copy(update={"temperature": vision.temperature})
    return main.model_copy(
        update={
            "provider": vision.provider,
            "base_url": vision.base_url,
            "api_key": vision.api_key,
            "model": vision.model,
            "temperature": vision.temperature,
        }
    )


def parse_json_response(text: str) -> dict:
    """Parse a model's JSON answer, tolerating ```json fences or prose around it."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        value = json.loads(cleaned)
        if isinstance(value, dict):
            return value
    except ValueError:
        pass
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            value = json.loads(cleaned[start : end + 1])
            if isinstance(value, dict):
                return value
        except ValueError:
            pass
    raise ValueError("The model did not return valid JSON.")
