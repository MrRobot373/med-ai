"""Hybrid retrieval: dense (vectors) + lexical (BM25) → reciprocal-rank fusion →
reranking → de-duplication → token-budgeted context. Every stage is timed and recorded
in a trace so the UI can show exactly why each passage was chosen.

Patient isolation: a patient-scoped search is only ever filtered by that patient's id,
in both indexes. Knowledge passages never carry patient data.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import registry
from app.models import Chunk, Document
from app.rag import lexical
from app.services.runtime_config import RuntimeConfig


@dataclass
class Passage:
    chunk_id: str
    document_id: str
    document_title: str
    scope: str
    page: int | None
    section: str | None
    text: str
    kind: str
    domain: str | None
    document_date: str | None
    source_org: str | None
    dense_rank: int | None = None
    lexical_rank: int | None = None
    fused_score: float = 0.0
    rerank_score: float | None = None
    label: str = ""

    def public(self, excerpt_chars: int = 600) -> dict:
        d = asdict(self)
        d["excerpt"] = self.text[:excerpt_chars]
        d.pop("text")
        return d


@dataclass
class RetrievalResult:
    passages: list[Passage]
    trace: dict = field(default_factory=dict)


def approx_tokens(text: str) -> int:
    return max(1, int(len(text.split()) * 1.33))


def _rrf(lists: list[tuple[list[str], float]], k: int) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ids, weight in lists:
        for rank, cid in enumerate(ids, start=1):
            scores[cid] = scores.get(cid, 0.0) + weight / (k + rank)
    return scores


def _similar(a: str, b: str) -> float:
    wa, wb = set(a.lower().split()), set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


async def retrieve(
    db: Session,
    cfg: RuntimeConfig,
    query: str,
    *,
    patient_id: str | None = None,
    include_knowledge: bool = True,
    include_patient: bool = True,
    document_ids: list[str] | None = None,
    domains: list[str] | None = None,
) -> RetrievalResult:
    r = cfg.retrieval
    timings: dict[str, int] = {}
    t0 = time.perf_counter()

    scopes: list[str] = []
    if patient_id and include_patient:
        scopes.append("patient")
    if include_knowledge:
        scopes.append("knowledge")

    # 1. Dense
    store = registry.vector_store(cfg)
    qvec = await registry.embedder(cfg).embed_query(query) if r.dense_top_k else None
    timings["embed_ms"] = _ms(t0)
    t = time.perf_counter()
    dense_lists: dict[str, list[str]] = {}
    for scope in scopes:
        if qvec is None:
            dense_lists[scope] = []
            continue
        hits = await store.search(
            scope,
            qvec,
            r.dense_top_k,
            patient_id=patient_id if scope == "patient" else None,
            document_ids=document_ids if scope == "patient" else None,
            domains=domains if scope == "knowledge" else None,
        )
        dense_lists[scope] = [h.chunk_id for h in hits]
    timings["dense_ms"] = _ms(t)

    # 2. Lexical
    t = time.perf_counter()
    lexical_lists: dict[str, list[str]] = {}
    for scope in scopes:
        hits = lexical.search(
            db,
            query,
            scope,
            r.lexical_top_k,
            patient_id=patient_id if scope == "patient" else None,
            document_ids=document_ids if scope == "patient" else None,
            domains=domains if scope == "knowledge" else None,
        )
        lexical_lists[scope] = [cid for cid, _ in hits]
    timings["lexical_ms"] = _ms(t)

    # 3. Fusion
    t = time.perf_counter()
    lists = [(ids, r.dense_weight) for ids in dense_lists.values()] + [
        (ids, r.lexical_weight) for ids in lexical_lists.values()
    ]
    fused = _rrf(lists, r.rrf_k)
    candidate_ids = [cid for cid, _ in sorted(fused.items(), key=lambda kv: kv[1], reverse=True)][: r.fusion_top_k]
    timings["fusion_ms"] = _ms(t)

    rows = (
        db.execute(
            select(Chunk, Document)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.id.in_(candidate_ids), Document.status == "ready", Document.is_active.is_(True))
        ).all()
        if candidate_ids
        else []
    )
    by_id = {}
    for chunk, doc in rows:
        # Defense in depth: never let another patient's chunk through, whatever an index returned.
        if chunk.scope == "patient" and chunk.patient_id != patient_id:
            continue
        by_id[chunk.id] = Passage(
            chunk_id=chunk.id,
            document_id=doc.id,
            document_title=doc.title,
            scope=chunk.scope,
            page=chunk.page,
            section=chunk.section,
            text=chunk.text,
            kind=doc.kind,
            domain=doc.domain,
            document_date=doc.document_date.isoformat() if doc.document_date else None,
            source_org=doc.source_org,
        )
    rank_maps = {
        "dense": {cid: i + 1 for ids in dense_lists.values() for i, cid in enumerate(ids)},
        "lexical": {cid: i + 1 for ids in lexical_lists.values() for i, cid in enumerate(ids)},
    }
    candidates: list[Passage] = []
    for cid in candidate_ids:
        p = by_id.get(cid)
        if p is None:
            continue
        p.fused_score = round(fused[cid], 6)
        p.dense_rank = rank_maps["dense"].get(cid)
        p.lexical_rank = rank_maps["lexical"].get(cid)
        candidates.append(p)

    # 4. Rerank
    t = time.perf_counter()
    rer = registry.reranker(cfg)
    reranked = candidates
    if rer.enabled and candidates:
        scores = await rer.score(query, [p.text for p in candidates])
        for p, s in zip(candidates, scores, strict=True):
            p.rerank_score = round(s, 4)
        reranked = sorted(candidates, key=lambda p: p.rerank_score or 0.0, reverse=True)
        reranked = [p for p in reranked if (p.rerank_score or 0.0) >= r.min_rerank_score]
    timings["rerank_ms"] = _ms(t)

    # 5. De-duplicate + budget
    final: list[Passage] = []
    used = 0
    dropped_dupes = 0
    for p in reranked:
        if any(q.document_id == p.document_id and _similar(q.text, p.text) > 0.8 for q in final):
            dropped_dupes += 1
            continue
        cost = approx_tokens(p.text)
        if final and used + cost > r.context_budget_tokens:
            break
        final.append(p)
        used += cost
        if len(final) >= r.final_top_k:
            break

    counters = {"patient": 0, "knowledge": 0}
    for p in final:
        counters[p.scope] += 1
        p.label = f"{'P' if p.scope == 'patient' else 'K'}{counters[p.scope]}"
    timings["total_ms"] = _ms(t0)
    selected = {p.chunk_id: p.label for p in final}

    trace = {
        "query": query,
        "scopes": scopes,
        "patient_id": patient_id,
        "profile": r.profile,
        "params": {
            "dense_top_k": r.dense_top_k,
            "lexical_top_k": r.lexical_top_k,
            "fusion_top_k": r.fusion_top_k,
            "final_top_k": r.final_top_k,
            "rrf_k": r.rrf_k,
            "context_budget_tokens": r.context_budget_tokens,
        },
        "models": {"embedding": cfg.embeddings.model, "reranker": rer.label},
        "counts": {
            "dense": sum(len(v) for v in dense_lists.values()),
            "lexical": sum(len(v) for v in lexical_lists.values()),
            "fused": len(candidates),
            "after_rerank": len(reranked),
            "duplicates_removed": dropped_dupes,
            "final": len(final),
            "context_tokens": used,
        },
        "timings": timings,
        "candidates": [
            {
                "chunk_id": p.chunk_id,
                "document_title": p.document_title,
                "scope": p.scope,
                "page": p.page,
                "dense_rank": p.dense_rank,
                "lexical_rank": p.lexical_rank,
                "fused_score": p.fused_score,
                "rerank_score": p.rerank_score,
                "selected": p.chunk_id in selected,
                "label": selected.get(p.chunk_id),
            }
            for p in reranked[:30]
        ],
    }
    return RetrievalResult(passages=final, trace=trace)


def _ms(t: float) -> int:
    return int((time.perf_counter() - t) * 1000)
