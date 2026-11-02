"""Wire-level tests of the provider clients against mocked HTTP endpoints."""

import json

import httpx
import pytest

from app.ai import embeddings as emb_mod
from app.ai import llm as llm_mod
from app.ai import reranker as rr_mod
from app.ai.llm import ChatMessage, LLMClient
from app.services.runtime_config import EmbeddingConfig, LLMConfig, RerankerConfig

_REAL_CLIENT = httpx.AsyncClient


def _patch(monkeypatch, module, handler):
    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return _REAL_CLIENT(*args, **kwargs)

    monkeypatch.setattr(module.httpx, "AsyncClient", factory)


async def test_openai_compatible_streaming_with_think_tags(monkeypatch):
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        chunks = ["<think>hidden", " reasoning</think>Hello", " clinician"]
        body = (
            "".join(f"data: {json.dumps({'choices': [{'delta': {'content': c}}]})}\n\n" for c in chunks)
            + "data: [DONE]\n\n"
        )
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    _patch(monkeypatch, llm_mod, handler)
    client = LLMClient(LLMConfig(provider="openai", base_url="https://gw.example/v1/", api_key="sk-1", model="m"))
    out = await client.complete([ChatMessage("user", "hi", images=["AAAA"])])
    assert out == "Hello clinician"
    assert seen["url"] == "https://gw.example/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-1"
    assert seen["body"]["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")


async def test_openai_json_mode_falls_back_when_unsupported(monkeypatch):
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        if "response_format" in body:
            return httpx.Response(400, json={"error": "response_format not supported"})
        return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"{\\"a\\":1}"}}]}\n\ndata: [DONE]\n\n')

    _patch(monkeypatch, llm_mod, handler)
    out = await LLMClient(LLMConfig(provider="openai", base_url="http://x/v1", model="m")).complete(
        [ChatMessage("user", "x")], json_mode=True
    )
    assert out == '{"a":1}' and len(calls) == 2


async def test_ollama_streaming_retries_without_think(monkeypatch):
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        if "think" in body:
            return httpx.Response(400, json={"error": "model does not support thinking"})
        lines = [{"message": {"content": "Hi"}, "done": False}, {"message": {"content": " there"}, "done": True}]
        return httpx.Response(200, text="\n".join(json.dumps(x) for x in lines))

    _patch(monkeypatch, llm_mod, handler)
    out = await LLMClient(LLMConfig(provider="ollama", base_url="http://o:11434", model="llama")).complete(
        [ChatMessage("user", "x")]
    )
    assert out == "Hi there"
    assert calls[0]["options"]["num_ctx"] == 8192 and "think" not in calls[1]


async def test_llm_errors_are_explained(monkeypatch):
    _patch(monkeypatch, llm_mod, lambda r: httpx.Response(401, json={"error": "bad key"}))
    with pytest.raises(llm_mod.LLMError, match="credentials"):
        await LLMClient(LLMConfig(provider="openai", base_url="http://x/v1", model="m")).complete(
            [ChatMessage("user", "x")]
        )


async def test_embeddings_both_protocols(monkeypatch):
    def handler(request):
        body = json.loads(request.content)
        if request.url.path.endswith("/api/embed"):
            return httpx.Response(200, json={"embeddings": [[3.0, 4.0] for _ in body["input"]]})
        return httpx.Response(
            200, json={"data": [{"index": i, "embedding": [0.0, 2.0]} for i, _ in enumerate(body["input"])]}
        )

    _patch(monkeypatch, emb_mod, handler)
    o = await emb_mod.Embedder(
        EmbeddingConfig(provider="ollama", base_url="http://o", model="e", batch_size=2)
    ).embed_documents(["a", "b", "c"])
    assert o == [[0.6, 0.8]] * 3  # normalised, batched
    q = await emb_mod.Embedder(EmbeddingConfig(provider="openai", base_url="http://x/v1", model="e")).embed_query("q")
    assert q == [0.0, 1.0]


async def test_remote_reranker_cohere_and_tei_shapes(monkeypatch):
    def cohere(request):
        return httpx.Response(
            200, json={"results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.1}]}
        )

    _patch(monkeypatch, rr_mod, cohere)
    r = rr_mod.Reranker(RerankerConfig(provider="remote", base_url="http://r/v1", model="bge"), LLMConfig())
    assert await r.score("q", ["a", "b"]) == [0.1, 0.9]

    def tei(request):
        body = json.loads(request.content)
        if "documents" in body:
            return httpx.Response(422, json={"error": "unknown field"})
        return httpx.Response(200, json=[{"index": 0, "score": 0.7}, {"index": 1, "score": 0.2}])

    _patch(monkeypatch, rr_mod, tei)
    assert await r.score("q", ["a", "b"]) == [0.7, 0.2]
