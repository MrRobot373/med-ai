"""Mock OpenAI-compatible AI server for development, demos without a GPU, and E2E tests.

    python -m app.devtools.mock_ai --port 9100

Then in Settings → AI models choose provider "OpenAI-compatible", base URL
http://localhost:9100/v1 (LLM, embeddings and reranker). It is deterministic and
obviously synthetic: answers are assembled from the evidence it is given, so citation
plumbing, streaming and the UI can be exercised end-to-end. Never use it clinically.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import re
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

DIM = 384
app = FastAPI(title="GMS mock AI")
_WORD = re.compile(r"[a-z0-9]+")


def hash_embed(text: str, dim: int = DIM) -> list[float]:
    vec = [0.0] * dim
    words = _WORD.findall(text.lower())
    for i, w in enumerate(words):
        for gram in (w, w[:5]) + ((f"{w}_{words[i + 1]}",) if i + 1 < len(words) else ()):
            h = int(hashlib.md5(gram.encode()).hexdigest(), 16)
            vec[h % dim] += 1.0 if (h >> 8) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def overlap(q: str, d: str) -> float:
    qs, ds = set(_WORD.findall(q.lower())), set(_WORD.findall(d.lower()))
    return len(qs & ds) / (len(qs) or 1)


@app.get("/v1/models")
def models():
    return {
        "object": "list",
        "data": [{"id": m, "object": "model"} for m in ("mock-clinical-llm", "mock-embed", "mock-rerank")],
    }


@app.post("/v1/embeddings")
async def embeddings(req: Request):
    body = await req.json()
    inputs = body["input"] if isinstance(body["input"], list) else [body["input"]]
    return {
        "object": "list",
        "data": [{"index": i, "embedding": hash_embed(t)} for i, t in enumerate(inputs)],
        "model": body.get("model"),
    }


@app.post("/v1/rerank")
async def rerank(req: Request):
    body = await req.json()
    docs = body.get("documents") or body.get("texts") or []
    return {
        "results": [{"index": i, "relevance_score": round(overlap(body["query"], d), 4)} for i, d in enumerate(docs)]
    }


def _labels(text: str) -> list[tuple[str, str]]:
    """(label, first sentence) for each evidence block in the prompt."""
    out = []
    for m in re.finditer(r"^\[([PKW]\d+)\][^\n]*\n(.+?)(?=\n\n---|\n\n=====|\Z)", text, re.S | re.M):
        lines = [ln.strip() for ln in m.group(2).splitlines() if ln.strip() and not ln.strip().startswith("#") and not ln.strip().startswith("_")]
        body = " ".join(" ".join(lines).split())
        sentence = re.split(r"(?<=[.!?])\s", body)[0][:220] if body else "Relevant passage"
        out.append((m.group(1), sentence))
    return out


def _answer(messages: list[dict]) -> str:
    user = messages[-1]["content"]
    if isinstance(user, list):
        user = " ".join(p.get("text", "") for p in user if isinstance(p, dict))
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    q = re.search(r"QUESTION:\s*(.+)$", user, re.S)
    question = q.group(1).strip() if q else user[-200:]
    if "Reply with the single word" in user:
        return "ready"
    if '"scores"' in user:
        n = len(re.findall(r"^\[\d+\]", user, re.M))
        return json.dumps({"scores": [5] * n})
    if "Respond with a single JSON object" in system or "Return JSON only" in user:
        return json.dumps(_structured(system + user))
    labels = _labels(user)
    has_record = "PATIENT RECORD [R]" in user
    if not labels and not has_record:
        return (
            "Insufficient evidence is available in the selected patient record and knowledge sources to answer this "
            "reliably.\n\nThe provided material did not cover this question."
        )
    lines = [f"**Mock answer** (synthetic — for interface testing) to: _{question[:120]}_", ""]
    if has_record:
        rec = re.search(r"PATIENT RECORD \[R\]\n(.+?)(?:\n\n=====|\Z)", user, re.S).group(1)
        problems = re.search(r"Active problems: (.+)", rec)
        results = re.search(r"Latest results: (.+)", rec)
        if problems:
            lines.append(f"- Documented active problems: {problems.group(1)[:220]} [R]")
        if results:
            lines.append(f"- Latest results on file: {results.group(1)[:260]} [R]")
    for label, sentence in labels[:4]:
        lines.append(f"- {sentence} [{label}]")
    lines += ["", "Please verify these points against the cited sources before acting on them."]
    return "\n".join(lines)


def _structured(prompt: str) -> dict:
    if '"subjective"' in prompt:
        return {
            "subjective": "Patient-reported history as documented in the encounter note [mock].",
            "objective": "Vitals and results as recorded.",
            "assessment": "Assessment pending clinician review.",
            "plan": "- Review results with the clinician\n- Arrange follow-up",
            "missing_information": ["Physical examination findings"],
        }
    if '"one_liner"' in prompt:
        return {
            "one_liner": "Mock summary generated from the structured record.",
            "active_problems": [{"problem": "See record", "status": "active", "citations": ["R"]}],
            "key_findings": [{"finding": "Latest results are listed in the record", "citations": ["R"]}],
            "medications": ["As listed in the chart"],
            "recent_changes": [],
            "missing_information": ["Mock model — no real analysis"],
            "follow_up_considerations": ["Review with a real model configured"],
        }
    if '"considerations"' in prompt:
        return {
            "summary": "Mock differential for interface testing.",
            "considerations": [
                {
                    "condition": "Example consideration",
                    "supporting": ["Documented finding"],
                    "against": [],
                    "suggested_evaluation": ["Clinician assessment"],
                    "citations": ["R"],
                }
            ],
            "red_flags": [],
            "missing_information": ["Examination findings"],
        }
    if '"key_points"' in prompt:
        labels = re.findall(r"^\[(K\d+)\]", prompt, re.M)
        return {
            "answer": "Mock answer drawn from the knowledge library " + " ".join(f"[{x}]" for x in labels[:2]),
            "key_points": ["Mock key point"],
            "abstained": False,
        }
    if '"new_findings"' in prompt:
        return {
            "overview": "Mock comparison of prior and current reports.",
            "new_findings": [],
            "resolved_findings": [],
            "worsened": ["See computed lab changes"],
            "improved": [],
            "unchanged": [],
            "clinically_relevant_changes": ["Review computed lab deltas"],
            "missing_information": [],
        }
    if '"medications"' in prompt and '"status"' in prompt:
        return {"medications": []}
    if '"problems"' in prompt:
        return {
            "problems": [],
            "medications": [],
            "allergies": [],
            "labs": [],
            "procedures": [],
            "symptoms": [],
            "follow_up": [],
        }
    if '"image_type"' in prompt:
        return {
            "image_type": "Mock image analysis",
            "quality": "good",
            "observations": ["Synthetic observation"],
            "measurements": [],
            "text_found": "",
            "possible_considerations": [],
            "limitations": ["Mock model"],
            "recommended_review": "Configure a real vision model.",
        }
    return {"result": "mock"}


@app.post("/v1/chat/completions")
async def chat(req: Request):
    body = await req.json()
    msgs = body.get("messages", [])
    if any(isinstance(m.get("content"), list) for m in msgs) and "JSON" not in json.dumps(msgs)[:4000]:
        text = "LAB REPORT\nPatient name: Image Upload\nHemoglobin | 13.1 | g/dL | 12.0-15.5\n\n## Visual description\nSynthetic transcription from the mock vision model."
    else:
        text = _answer(msgs)
    if not body.get("stream"):
        return JSONResponse(
            {
                "id": "mock",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": body.get("model"),
                "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            }
        )

    async def gen():
        for piece in re.findall(r"\S+\s*", text):
            chunk = {
                "id": "mock",
                "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": {"content": piece}}],
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            await asyncio.sleep(0.015)
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9100)
    args = ap.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port)
