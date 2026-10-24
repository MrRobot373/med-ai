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
import os
import re
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

DIM = 384
app = FastAPI(title="GMS mock AI")

# MOCK_AI_PLAIN=1 drops the "[mock]" markers (for screen recordings of the interface).
TAG = "" if os.getenv("MOCK_AI_PLAIN") == "1" else " [mock]"
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


_NOISE = re.compile(
    r"tel[:. ]|@|road|shop |lab no|patient name|patient id|age / sex|referred by|collected|reported|page \d|^investigation|end of report|method:",
    re.I,
)
_TOPICS = {
    "kidney": ("creatinine", "egfr", "urea", "albumin", "potassium", "ckd"),
    "renal": ("creatinine", "egfr", "albumin"),
    "sugar": ("hba1c", "glucose"),
    "diabetes": ("hba1c", "glucose"),
    "heart": ("bnp", "lvef", "ejection"),
    "liver": ("alt", "ast", "bilirubin"),
}


def _row(line: str) -> str:
    """'Serum Creatinine | 1.62 | H | mg/dL | 0.50 - 1.10' -> 'Serum Creatinine 1.62 mg/dL (high; reference 0.50 - 1.10)'."""
    parts = [x.strip() for x in line.split("|") if x.strip()]
    if len(parts) < 2 or not re.match(r"^[<>]?\d", parts[1]):
        return line.lstrip("•-* ").strip()
    flag = next((x for x in parts[2:] if x in ("H", "L")), None)
    rest = [x for x in parts[2:] if x not in ("H", "L")]
    unit = rest[0] if rest and not re.search(r"\d", rest[0]) else ""
    ref = next((x for x in rest if re.search(r"\d", x)), None)
    note = ", ".join(filter(None, [{"H": "high", "L": "low"}.get(flag), f"reference {ref}" if ref else None]))
    return f"{parts[0]} {parts[1]} {unit}".strip() + (f" ({note})" if note else "")


def _labels(text: str, question: str = "") -> list[tuple[str, str]]:
    """(label, the most relevant line) for each evidence block in the prompt."""
    q = question.lower()
    keys = {w for w in re.findall(r"[a-z0-9]{3,}", q)}
    for topic, extra in _TOPICS.items():
        if topic in q:
            keys |= set(extra)
    out = []
    for m in re.finditer(r"^\[([PK]\d+)\][^\n]*\n(.+?)(?=\n\n---|\n\n=====|\Z)", text, re.S | re.M):
        lines = [
            ln.strip()
            for ln in m.group(2).splitlines()
            if ln.strip() and not ln.strip().startswith(("#", "_")) and not _NOISE.search(ln)
        ]
        if not lines:
            continue
        scored = sorted(lines, key=lambda ln: -(3 * sum(k in ln.lower() for k in keys) + bool(re.search(r"\d", ln))))
        best = scored[0]
        sentence = _row(best) if "|" in best else re.split(r"(?<=[.!?])\s", " ".join(best.lstrip("•-* ").split()))[0]
        out.append((m.group(1), sentence[:220]))
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
    labels = _labels(user, question)
    has_record = "PATIENT RECORD [R]" in user
    if not labels and not has_record:
        return (
            "Insufficient evidence is available in the selected patient record and knowledge sources to answer this "
            "reliably.\n\nThe provided material did not cover this question."
        )
    lines = [] if not TAG else [f"**Mock answer** (synthetic — for interface testing) to: _{question[:120]}_", ""]
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


def _field(prompt: str, label: str) -> str:
    m = re.search(rf"^{re.escape(label)}:? (.+)$", prompt, re.M)
    return m.group(1).strip() if m else ""


def _impression(prompt: str) -> list[str]:
    """The numbered lines under a report's IMPRESSION heading, as written in the report."""
    m = re.search(r"^IMPRESSION\s*\n((?:\s*\d+\..+\n?)+)", prompt, re.M | re.I)
    return [re.sub(r"^\s*\d+\.\s*", "", x).strip() for x in m.group(1).splitlines() if x.strip()][:5] if m else []


def _copilot(prompt: str) -> dict | None:
    """Plausible, input-aware answers for the consultation tools (interface testing only)."""
    problems = _field(prompt, "Active problems")
    if '"ask_about"' in prompt:
        abnormal = re.findall(r"^Abnormal: (.+)$", prompt, re.M)
        orders = re.findall(r"^Order (.+?) \(", prompt, re.M)
        last = _field(prompt, "Last visit")
        return {
            "headline": f"Known {problems[:90] or 'patient'} — review changes since the last visit.{TAG}",
            "since_last_visit": ([f"Last visit {last[:120]}"] if last else [])
            + [f"New abnormal result: {a}" for a in abnormal[:3]],
            "ask_about": [
                {
                    "question": "Have the symptoms from the last visit settled completely?",
                    "why": f"Previous visit: {last[:80] or 'see record'}",
                },
                {
                    "question": "Any change in weight, appetite or energy?",
                    "why": "Weight trend is relevant to the chronic conditions on file.",
                },
                {
                    "question": "Are all current medicines being taken as prescribed? Any side effects?",
                    "why": "Adherence before changing doses.",
                },
            ],
            "watch_outs": ["Check kidney function before dosing renally cleared drugs."]
            + ([f"Pending: {o}" for o in orders[:2]]),
            "consider_today": [f"Review {o}" for o in orders[:2]] or ["Routine chronic-care review"],
        }
    if '"history_links"' in prompt:
        complaint = _field(prompt, "Chief complaint")
        dx = _field(prompt, "Working diagnosis")
        return {
            "verdict": "partly_consistent",
            "summary": f"“{dx}” fits “{complaint[:80]}”, but given the history keep a serious alternative in mind.{TAG}",
            "supporting": [f"Presenting complaint: {complaint[:100]}"],
            "against": ["No examination findings recorded yet"],
            "consider": [
                {
                    "diagnosis": "A more serious alternative relevant to age and comorbidities",
                    "why": f"Documented problems: {problems[:100]}",
                    "how_to_check": "Targeted examination and a basic test",
                },
            ],
            "red_flags": ["Persistent vomiting, GI bleeding, severe or worsening pain, fever"],
            "suggested_tests": [{"test": "Ultrasound abdomen", "why": "Characterise the cause if pain persists"}],
            "history_links": [f"Existing conditions: {problems[:120]}"],
        }
    if '"dose_assessment"' in prompt:
        items = []
        for m in re.finditer(r"^\[(\d+)\] (.+?) \| resolved: (.+?) \| (.+?) \| rules: (.+)$", prompt, re.M):
            idx, line, _resolved, _per_day, rules = m.groups()
            flagged = "critical" in rules
            warned = "warning" in rules
            items.append(
                {
                    "index": int(idx),
                    "drug": line.split(" ")[0],
                    "verdict": "avoid" if flagged else ("adjust" if warned else "appropriate"),
                    "dose_assessment": "high" if "too high" in rules else ("adequate" if not flagged else "unclear"),
                    "comment": ("Agree with the rule check: " + rules.split(" — ")[0])
                    if (flagged or warned)
                    else f"Dose and choice look reasonable for this patient.{TAG}",
                    "suggestion": "Consider a safer alternative or adjusted dose." if flagged else None,
                }
            )
        overall = (
            "unsafe"
            if any(i["verdict"] == "avoid" for i in items)
            else ("review" if any(i["verdict"] == "adjust" for i in items) else "appropriate")
        )
        return {
            "overall": overall,
            "summary": f"{len(items)} medicine(s) reviewed against age, kidney function and current medicines.{TAG}",
            "items": items,
            "diagnosis_fit": "Choices are consistent with the working diagnosis.",
            "missing": [],
            "monitoring": ["Recheck creatinine and potassium if renally cleared drugs were adjusted"],
            "counselling": ["Take after food", "Return if symptoms worsen"],
        }
    if '"answers_question"' in prompt:
        reason = _field(prompt, "Reason for the test")
        return {
            "answers_question": f"The report answers the question asked: “{reason[:120]}”.{TAG}",
            "key_findings": _impression(prompt) or ["Findings as described in the report impression"],
            "abnormal": [],
            "change_from_previous": None,
            "next_steps": ["Discuss the result with the patient", "Correlate clinically"],
            "urgency": "routine",
            "patient_explanation": "Your scan has been reviewed. The doctor will explain what it means for your treatment.",
        }
    return None


def _structured(prompt: str) -> dict:
    copilot = _copilot(prompt)
    if copilot is not None:
        return copilot
    if '"subjective"' in prompt:
        return {
            "subjective": f"Patient-reported history as documented in the encounter note.{TAG}",
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
        text = "## Visual description\nSynthetic description from the mock vision model — no text was recognised and no findings are reported."
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
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
