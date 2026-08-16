"""Vision analysis structured-output parsing (spec §60/§61/§123) — mirrors
`grounding_validator`'s validate/repair-retry/never-fabricate discipline, tested
directly here since it's a standalone unit (real `generate_complete` mocked)."""

from __future__ import annotations

import pytest

from app.config.settings import get_settings
from app.vision.analyzer import VisionComparison, VisionObservation, analyze_image, compare_images

VALID_OBSERVATION_JSON = (
    '{"image_type": "fundus photograph", "visible_text": [], '
    '"observations": ["optic disc visible"], "measurements_visible": [], '
    '"clinical_entities": ["optic disc"], "quality_limitations": [], "uncertainties": []}'
)

VALID_COMPARISON_JSON = (
    '{"previous_findings": ["baseline appearance"], "current_findings": ["mild change"], '
    '"observable_changes": ["slight increase in cupping"], '
    '"differences": ["cup-to-disc ratio appears larger"], "limitations": []}'
)

TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.asyncio
async def test_analyze_image_parses_valid_json(monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_complete(messages, settings, json_format=False, temperature=None, max_output_tokens=None, num_ctx=None):
        assert json_format is True
        return VALID_OBSERVATION_JSON

    monkeypatch.setattr("app.llm.structured.generate_complete", fake_generate_complete)
    result = await analyze_image(TINY_PNG, get_settings())

    assert isinstance(result, VisionObservation)
    assert result.image_type == "fundus photograph"
    assert result.observations == ["optic disc visible"]


@pytest.mark.asyncio
async def test_analyze_image_retries_once_then_succeeds(monkeypatch: pytest.MonkeyPatch):
    calls = []

    async def fake_generate_complete(messages, settings, json_format=False, temperature=None, max_output_tokens=None, num_ctx=None):
        calls.append(messages)
        if len(calls) == 1:
            return "not valid json at all"
        return VALID_OBSERVATION_JSON

    monkeypatch.setattr("app.llm.structured.generate_complete", fake_generate_complete)
    result = await analyze_image(TINY_PNG, get_settings())

    assert len(calls) == 2
    assert result is not None
    assert result.observations == ["optic disc visible"]


@pytest.mark.asyncio
async def test_analyze_image_returns_none_never_fabricates_after_two_failures(monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_complete(messages, settings, json_format=False, temperature=None, max_output_tokens=None, num_ctx=None):
        return "still not json"

    monkeypatch.setattr("app.llm.structured.generate_complete", fake_generate_complete)
    result = await analyze_image(TINY_PNG, get_settings())

    assert result is None


@pytest.mark.asyncio
async def test_compare_images_sends_both_images_in_order(monkeypatch: pytest.MonkeyPatch):
    captured = {}

    async def fake_generate_complete(messages, settings, json_format=False, temperature=None, max_output_tokens=None, num_ctx=None):
        captured["images"] = messages[-1].images
        return VALID_COMPARISON_JSON

    monkeypatch.setattr("app.llm.structured.generate_complete", fake_generate_complete)
    result = await compare_images(TINY_PNG, TINY_PNG, get_settings())

    assert isinstance(result, VisionComparison)
    assert result.differences == ["cup-to-disc ratio appears larger"]
    assert len(captured["images"]) == 2  # previous + current, one user message


@pytest.mark.asyncio
async def test_analyze_image_returns_none_on_generation_error(monkeypatch: pytest.MonkeyPatch):
    from app.llm.generation import GenerationError

    async def fake_generate_complete(messages, settings, json_format=False, temperature=None, max_output_tokens=None, num_ctx=None):
        raise GenerationError("Ollama unreachable")

    monkeypatch.setattr("app.llm.structured.generate_complete", fake_generate_complete)
    result = await analyze_image(TINY_PNG, get_settings())

    assert result is None
