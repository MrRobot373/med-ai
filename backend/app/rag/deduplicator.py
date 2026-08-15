"""Deduplication and parent expansion — spec §47.

Operates on hydrated `Chunk` rows (not just scored IDs), since merging needs the
actual chunk_index/section/text to decide what's genuinely adjacent. Two rules from
the spec, both implemented here:

1. "If several adjacent chunks belong to the same section: deduplicate overlapping
   information, merge/expand to useful parent context, retain provenance for each
   source." — chunks from the same source document, same section, with consecutive
   `chunk_index` values are merged into one passage; `chunk_ids` on the result lists
   every contributing chunk so provenance is never lost in the merge.
2. "Do not allow one document to dominate the context just because five overlapping
   chunks matched." — `max_per_source` caps how many (merged) passages from a single
   source make it into the final result, keeping the highest-scoring ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.orm import Session as DbSession

from app.models.chunk import Chunk


class _ScoredHit(Protocol):
    chunk_id: str
    score: float


@dataclass
class RetrievedPassage:
    text: str
    score: float
    source_title: str
    source_id: str  # report_id, or a stable "knowledge:<hash-or-filename>" key
    collection: str
    page: int | None
    section: str | None
    chunk_ids: list[str] = field(default_factory=list)


def _source_key(chunk: Chunk) -> str:
    if chunk.report_id:
        return chunk.report_id
    return f"knowledge:{chunk.file_hash or chunk.source_filename or chunk.source_title}"


def deduplicate_and_expand(
    db: DbSession, hits: list[_ScoredHit], max_per_source: int = 3
) -> list[RetrievedPassage]:
    if not hits:
        return []

    score_by_id = {hit.chunk_id: hit.score for hit in hits}
    chunks = db.query(Chunk).filter(Chunk.id.in_(score_by_id.keys())).all()
    chunks_by_id = {chunk.id: chunk for chunk in chunks}

    by_source: dict[str, list[Chunk]] = {}
    for hit in hits:
        chunk = chunks_by_id.get(hit.chunk_id)
        if chunk is None:
            continue  # stale reference (e.g. Qdrant/SQLite briefly out of sync) — skip, don't fabricate
        by_source.setdefault(_source_key(chunk), []).append(chunk)

    passages: list[RetrievedPassage] = []
    for source_chunks in by_source.values():
        source_chunks.sort(key=lambda c: c.chunk_index)
        groups: list[list[Chunk]] = []
        for chunk in source_chunks:
            previous_group = groups[-1] if groups else None
            same_section_adjacent = (
                previous_group is not None
                and previous_group[-1].section == chunk.section
                and chunk.chunk_index - previous_group[-1].chunk_index <= 1
            )
            if same_section_adjacent:
                previous_group.append(chunk)
            else:
                groups.append([chunk])

        source_passages = [_merge_group(group, score_by_id) for group in groups]
        source_passages.sort(key=lambda p: p.score, reverse=True)
        passages.extend(source_passages[:max_per_source])

    passages.sort(key=lambda p: p.score, reverse=True)
    return passages


def _merge_group(group: list[Chunk], score_by_id: dict[str, float]) -> RetrievedPassage:
    first = group[0]
    return RetrievedPassage(
        text="\n\n".join(chunk.text for chunk in group),
        # The best-matching chunk's score represents the merged passage — averaging
        # would understate a group where one chunk is highly relevant and its merged
        # neighbors are only marginally-relevant surrounding context.
        score=max(score_by_id.get(chunk.id, 0.0) for chunk in group),
        source_title=first.source_title,
        source_id=_source_key(first),
        collection=first.collection.value,
        page=first.page,
        section=first.section,
        chunk_ids=[chunk.id for chunk in group],
    )
