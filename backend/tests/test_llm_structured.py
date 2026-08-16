"""Shared structured-JSON generation helper (spec §123) — retry/never-fabricate
discipline, tested once here rather than duplicated per caller (grounding validation,
vision, clinical modules all share this)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.config.settings import get_settings
from app.llm.generation import ChatMessage, GenerationError
from app.llm.structured import generate_structured


class _Widget(BaseModel):
    name: str = ""
    count: int = 0


@pytest.mark.asyncio
async def test_parses_valid_json_on_first_attempt(monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_complete(messages, settings, json_format=False, temperature=None, max_output_tokens=None):
        assert json_format is True
        return '{"name": "widget", "count": 3}'

    monkeypatch.setattr("app.llm.structured.generate_complete", fake_generate_complete)
    result = await generate_structured([ChatMessage(role="user", content="go")], _Widget, get_settings())

    assert result == _Widget(name="widget", count=3)


@pytest.mark.asyncio
async def test_retries_once_on_invalid_json_then_succeeds(monkeypatch: pytest.MonkeyPatch):
    calls = []

    async def fake_generate_complete(messages, settings, json_format=False, temperature=None, max_output_tokens=None):
        calls.append(messages)
        return "not json" if len(calls) == 1 else '{"name": "fixed", "count": 1}'

    monkeypatch.setattr("app.llm.structured.generate_complete", fake_generate_complete)
    result = await generate_structured([ChatMessage(role="user", content="go")], _Widget, get_settings())

    assert len(calls) == 2
    assert result == _Widget(name="fixed", count=1)


@pytest.mark.asyncio
async def test_returns_none_never_fabricates_after_two_failures(monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_complete(messages, settings, json_format=False, temperature=None, max_output_tokens=None):
        return "still not json"

    monkeypatch.setattr("app.llm.structured.generate_complete", fake_generate_complete)
    result = await generate_structured([ChatMessage(role="user", content="go")], _Widget, get_settings())

    assert result is None


@pytest.mark.asyncio
async def test_returns_none_on_generation_error(monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_complete(messages, settings, json_format=False, temperature=None, max_output_tokens=None):
        raise GenerationError("Ollama unreachable")

    monkeypatch.setattr("app.llm.structured.generate_complete", fake_generate_complete)
    result = await generate_structured([ChatMessage(role="user", content="go")], _Widget, get_settings())

    assert result is None
