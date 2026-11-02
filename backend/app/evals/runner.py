"""Measures how well the product actually does its job, on data with known answers.

    python -m app.cli eval                    all suites that can run here
    python -m app.cli eval --suite extraction only the suite(s) named (comma separated)

Suites
  extraction   Reads real lab-report PDFs and compares every value with the one that was printed on them.
               Needs no AI model: it measures the parser itself.                      (patient files must be present)
  retrieval    Asks reference questions and checks that the right source document is among the passages found.
               Measures the embedding / reranking models the clinic has configured.   (reference library must be loaded)
  abstention   Asks questions the reference library cannot answer; the assistant must say so, not invent an answer.
               Measures the language model and the grounding rules.
  grounding    Asks answerable questions; every answer must cite its evidence and cite nothing that was not provided.

The result is saved in data/evals/ and shown in Settings → Clinical content, with the model names it was run against —
so a different model or setting can be compared with the same yardstick before the clinic switches to it.
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path

from sqlalchemy import select

from app.core.config import PROJECT_ROOT, get_settings
from app.db import SessionLocal
from app.ingestion import labs, parsers
from app.models import Conversation, Document, User
from app.services import chat, runtime_config

DATA = Path(__file__).parent / "data"
PATIENT_FILES = PROJECT_ROOT / "patient-files"
SUITES = ("extraction", "retrieval", "abstention", "grounding")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _num(s: str) -> float | None:
    try:
        return float(str(s).replace(",", "").strip())
    except ValueError:
        return None


def _code_of(name: str) -> str | None:
    """The analyte the parser itself would file this printed test name under (None if it does not know it)."""
    o = labs._parse_table_row([name, "1"], 1, name)
    return o.code if o else None


def _same_test(a: str, b: str) -> bool:
    na, nb = _norm(a), _norm(b)
    return bool(na and nb) and (na in nb or nb in na or SequenceMatcher(None, na, nb).ratio() >= 0.6)


# ---------------------------------------------------------------------------------------------- extraction
def extraction() -> dict:
    truth = json.loads((DATA / "lab_truth.json").read_text(encoding="utf-8"))
    present = {k: PATIENT_FILES / k for k in truth if (PATIENT_FILES / k).exists()}
    if not present:
        return {
            "suite": "extraction",
            "status": "skipped",
            "reason": "The patient files are not on this server (they ship only with the demonstration build).",
        }
    expected = found = unexpected = non_numeric = 0
    reports, misses = [], []
    for key, path in present.items():
        parsed = parsers.parse(path.read_bytes(), "application/pdf")
        obs = labs.extract(parsed.pages)
        used: set[int] = set()
        r_exp = r_found = 0
        for row in truth[key]:
            value = _num(row[1])
            if value is None:
                non_numeric += 1
                continue
            r_exp += 1
            code = _code_of(row[0])  # the analyte the parser itself files this printed name under
            hit = next(
                (
                    i
                    for i, o in enumerate(obs)
                    if i not in used
                    and o.value_num is not None
                    and abs(o.value_num - value) < 1e-6
                    and (o.code.split("_")[0] == code.split("_")[0] if code else _same_test(o.name, row[0]))
                ),
                None,
            )
            if hit is None:
                misses.append({"report": key, "test": row[0], "expected": row[1], "unit": row[2]})
            else:
                used.add(hit)
                r_found += 1
        extra = [o for i, o in enumerate(obs) if i not in used]
        expected += r_exp
        found += r_found
        unexpected += len(extra)
        reports.append(
            {
                "report": key,
                "expected": r_exp,
                "found": r_found,
                "unexpected": [f"{o.name} {o.value_num}" for o in extra][:6],
            }
        )
    recall = found / expected if expected else 0.0
    precision = found / (found + unexpected) if (found + unexpected) else 0.0
    return {
        "suite": "extraction",
        "status": "ok",
        "reports": len(reports),
        "values_expected": expected,
        "values_found": found,
        "values_unexpected": unexpected,
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "non_numeric_skipped": non_numeric,
        "pass": recall >= 0.95 and precision >= 0.9,
        "target": "recall ≥ 95 %, precision ≥ 90 %",
        "worst": sorted(reports, key=lambda r: r["found"] - r["expected"])[:5],
        "misses": misses[:25],
    }


# ---------------------------------------------------------------------------------------------- model-backed suites
def _library_ready(db) -> bool:
    return bool(
        db.scalar(select(Document.id).where(Document.scope == "knowledge", Document.status == "ready").limit(1))
    )


def _skip(reason: str, suite: str) -> dict:
    return {"suite": suite, "status": "skipped", "reason": reason}


async def retrieval(db) -> dict:
    from app.rag.retrieve import retrieve

    if not _library_ready(db):
        return _skip("The reference library is empty. Load it first (python -m app.seed knowledge).", "retrieval")
    cfg = runtime_config.load(db)
    cases = json.loads((DATA / "qa.json").read_text(encoding="utf-8"))["retrieval"]
    top1 = top5 = 0
    detail = []
    for c in cases:
        res = await retrieve(db, cfg, c["q"], include_patient=False)
        titles = [_norm(p.document_title) for p in res.passages]
        want = _norm(c["expect"])
        rank = next((i for i, t in enumerate(titles, start=1) if want in t), None)
        top1 += rank == 1
        top5 += rank is not None and rank <= 5
        detail.append(
            {
                "question": c["q"],
                "expected": c["expect"],
                "rank": rank,
                "found": [p.document_title for p in res.passages[:3]],
            }
        )
    n = len(cases)
    return {
        "suite": "retrieval",
        "status": "ok",
        "questions": n,
        "top1": round(top1 / n, 3),
        "recall_at_5": round(top5 / n, 3),
        "pass": top5 / n >= 0.9,
        "target": "right source in the top 5 for ≥ 90 % of questions",
        "detail": detail,
    }


async def _ask(db, user: User, question: str) -> dict:
    conv = Conversation(user_id=user.id, scope="knowledge", title="evaluation")
    db.add(conv)
    db.commit()
    final = None
    try:
        async for ev in chat.answer(db, user, conv, question):
            if ev["event"] in ("done", "error"):
                final = ev
    finally:
        db.delete(conv)
        db.commit()
    return final or {"event": "error", "data": {"message": "no answer"}}


async def abstention(db, user: User) -> dict:
    if not _library_ready(db):
        return _skip("The reference library is empty.", "abstention")
    qs = json.loads((DATA / "qa.json").read_text(encoding="utf-8"))["out_of_scope"]
    ok = 0
    detail = []
    for q in qs:
        ev = await _ask(db, user, q)
        status = ev["data"].get("status") if ev["event"] == "done" else "error"
        good = status == "abstained"
        ok += good
        detail.append(
            {
                "question": q,
                "status": status,
                "ok": good,
                "answer": (ev["data"].get("content") or ev["data"].get("message") or "")[:200],
            }
        )
    rate = ok / len(qs)
    return {
        "suite": "abstention",
        "status": "ok",
        "questions": len(qs),
        "abstained": ok,
        "rate": round(rate, 3),
        "pass": rate >= 0.9,
        "target": "declines ≥ 90 % of questions the library cannot answer",
        "detail": detail,
    }


async def grounding(db, user: User) -> dict:
    if not _library_ready(db):
        return _skip("The reference library is empty.", "grounding")
    cases = json.loads((DATA / "qa.json").read_text(encoding="utf-8"))["retrieval"][:6]
    cited = clean = answered = 0
    detail = []
    for c in cases:
        ev = await _ask(db, user, c["q"])
        if ev["event"] != "done":
            detail.append({"question": c["q"], "status": "error"})
            continue
        d = ev["data"]
        gen = (d.get("trace") or {}).get("generation", {})
        used, invalid = gen.get("citations_used", []), gen.get("invalid_citations_removed", 0)
        if d.get("status") == "complete":
            answered += 1
            cited += bool(used)
            clean += invalid == 0
        detail.append({"question": c["q"], "status": d.get("status"), "citations": used, "invented_citations": invalid})
    rate_c, rate_i = (cited / answered if answered else 0.0), (clean / answered if answered else 0.0)
    return {
        "suite": "grounding",
        "status": "ok",
        "answered": answered,
        "with_citations": round(rate_c, 3),
        "no_invented_citations": round(rate_i, 3),
        "pass": answered > 0 and rate_c >= 0.95 and rate_i >= 0.95,
        "target": "≥ 95 % of answers cite evidence and none cite what was not provided",
        "detail": detail,
    }


# ---------------------------------------------------------------------------------------------- orchestration
async def run(suites: list[str] | None = None) -> dict:
    wanted = [s for s in (suites or SUITES) if s in SUITES]
    db = SessionLocal()
    try:
        cfg = runtime_config.load(db)
        user = db.scalars(select(User).where(User.role == "admin")).first()
        out = []
        for s in wanted:
            t0 = time.perf_counter()
            try:
                if s == "extraction":
                    r = extraction()
                elif s == "retrieval":
                    r = await retrieval(db)
                elif s == "abstention":
                    r = await abstention(db, user)
                else:
                    r = await grounding(db, user)
            except Exception as exc:  # a suite that cannot run says why instead of hiding the others
                r = {"suite": s, "status": "error", "reason": f"{exc.__class__.__name__}: {exc}"}
            r["seconds"] = round(time.perf_counter() - t0, 1)
            out.append(r)
        report = {
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "models": {
                "language": cfg.llm.model,
                "embedding": cfg.embeddings.model,
                "reranker": cfg.reranker.model if cfg.reranker.provider != "none" else None,
                "clinical": cfg.clinical.model if not cfg.clinical.use_main_llm else cfg.llm.model,
            },
            "suites": out,
            "ok": all(r.get("pass", True) for r in out if r["status"] == "ok")
            and not any(r["status"] == "error" for r in out),
        }
    finally:
        db.close()
    folder = get_settings().data_dir / "evals"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"eval-{datetime.now():%Y%m%d-%H%M%S}.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    return report


def latest() -> dict | None:
    folder = get_settings().data_dir / "evals"
    files = sorted(folder.glob("eval-*.json")) if folder.exists() else []
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None
