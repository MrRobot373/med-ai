"""BM25 lexical retrieval on SQLite FTS5 — exact terms (drug names, lab codes, ICD
codes, abbreviations) that dense embeddings tend to blur."""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.orm import Session

_STOP = set(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "i",
        "in",
        "is",
        "it",
        "its",
        "me",
        "my",
        "of",
        "on",
        "or",
        "our",
        "should",
        "so",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
        "patient",
        "patients",
        "please",
        "tell",
        "about",
        "any",
    ]
)
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-\.]*")


def build_match_query(query: str) -> str | None:
    terms = []
    for tok in _TOKEN.findall(query.lower()):
        tok = tok.strip(".-")
        if len(tok) < 2 or tok in _STOP:
            continue
        terms.append('"' + tok.replace('"', "") + '"')
    if not terms:
        return None
    return " OR ".join(dict.fromkeys(terms))


def index_chunks(db: Session, rows: list[tuple[str, str]]) -> None:
    if rows:
        db.execute(text("INSERT INTO chunks_fts (text, chunk_id) VALUES (:t, :c)"), [{"t": t, "c": c} for c, t in rows])


def delete_chunks(db: Session, chunk_ids: list[str]) -> None:
    for i in range(0, len(chunk_ids), 500):
        batch = chunk_ids[i : i + 500]
        params = {f"c{j}": cid for j, cid in enumerate(batch)}
        placeholders = ",".join(f":c{j}" for j in range(len(batch)))
        db.execute(text(f"DELETE FROM chunks_fts WHERE chunk_id IN ({placeholders})"), params)


def search(
    db: Session,
    query: str,
    scope: str,
    limit: int,
    *,
    patient_id: str | None = None,
    document_ids: list[str] | None = None,
    domains: list[str] | None = None,
) -> list[tuple[str, float]]:
    if scope == "patient" and not patient_id:
        raise ValueError("Patient-scoped lexical search requires a patient_id")
    match = build_match_query(query)
    if not match or limit <= 0:
        return []
    sql = (
        "SELECT c.id, bm25(chunks_fts) AS s FROM chunks_fts "
        "JOIN chunks c ON c.id = chunks_fts.chunk_id JOIN documents d ON d.id = c.document_id "
        "WHERE chunks_fts MATCH :m AND c.scope = :scope AND d.status = 'ready' AND d.is_active = 1"
    )
    params: dict = {"m": match, "scope": scope, "k": limit}
    if patient_id:
        sql += " AND c.patient_id = :pid"
        params["pid"] = patient_id
    if document_ids:
        keys = []
        for i, d in enumerate(document_ids):
            params[f"d{i}"] = d
            keys.append(f":d{i}")
        sql += f" AND c.document_id IN ({','.join(keys)})"
    if domains:
        keys = []
        for i, d in enumerate(domains):
            params[f"dm{i}"] = d
            keys.append(f":dm{i}")
        sql += f" AND d.domain IN ({','.join(keys)})"
    sql += " ORDER BY s LIMIT :k"
    # bm25() is "lower is better"; flip the sign so higher = more relevant everywhere.
    return [(row[0], -float(row[1])) for row in db.execute(text(sql), params)]
