"""Deduplication and parent expansion — spec §47. Uses the real DB session (needs
hydrated `Chunk` rows) but no embedding/reranker/Qdrant — pure DB + merge logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.db.session import SessionLocal
from app.models.chunk import Chunk, ChunkCollection
from app.rag.deduplicator import deduplicate_and_expand


@dataclass
class _Hit:
    chunk_id: str
    score: float


def _make_chunk(db, **overrides) -> Chunk:
    defaults = {
        "collection": ChunkCollection.MEDICAL_KNOWLEDGE,
        "source_title": "ICO Glaucoma Guidelines",
        "source_filename": "ico.pdf",
        "file_hash": "abc123",
        "page": 1,
        "section": "Diagnosis",
        "chunk_index": 0,
        "text": "some text",
        "token_count": 10,
    }
    defaults.update(overrides)
    chunk = Chunk(**defaults)
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk


def test_adjacent_same_section_chunks_are_merged_with_full_provenance():
    db = SessionLocal()
    try:
        c1 = _make_chunk(db, chunk_index=0, text="Open-angle glaucoma is diagnosed by...")
        c2 = _make_chunk(db, chunk_index=1, text="...elevated intraocular pressure and optic nerve changes.")
        hits = [_Hit(c1.id, 0.9), _Hit(c2.id, 0.7)]

        passages = deduplicate_and_expand(db, hits)

        assert len(passages) == 1
        assert set(passages[0].chunk_ids) == {c1.id, c2.id}
        assert "Open-angle glaucoma" in passages[0].text
        assert "optic nerve changes" in passages[0].text
        # The merged passage's score is the best-matching contributor's score, not an
        # average that would understate a group with one highly-relevant chunk.
        assert passages[0].score == 0.9
    finally:
        db.query(Chunk).delete()
        db.commit()
        db.close()


def test_non_adjacent_chunks_from_same_source_are_not_merged():
    db = SessionLocal()
    try:
        c1 = _make_chunk(db, chunk_index=0, section="Diagnosis", text="Diagnosis text")
        c2 = _make_chunk(db, chunk_index=5, section="Diagnosis", text="Unrelated later text")
        hits = [_Hit(c1.id, 0.9), _Hit(c2.id, 0.8)]

        passages = deduplicate_and_expand(db, hits, max_per_source=5)

        assert len(passages) == 2
    finally:
        db.query(Chunk).delete()
        db.commit()
        db.close()


def test_different_sections_are_not_merged_even_if_adjacent():
    db = SessionLocal()
    try:
        c1 = _make_chunk(db, chunk_index=0, section="Diagnosis", text="Diagnosis text")
        c2 = _make_chunk(db, chunk_index=1, section="Treatment", text="Treatment text")
        hits = [_Hit(c1.id, 0.9), _Hit(c2.id, 0.8)]

        passages = deduplicate_and_expand(db, hits, max_per_source=5)

        assert len(passages) == 2
    finally:
        db.query(Chunk).delete()
        db.commit()
        db.close()


def test_max_per_source_caps_one_document_from_dominating():
    db = SessionLocal()
    try:
        # 5 non-adjacent (so non-mergeable) chunks from the SAME source — without a
        # cap, this one document would occupy the entire result set.
        chunks = [_make_chunk(db, chunk_index=i * 3, section=f"Section {i}", text=f"content {i}") for i in range(5)]
        hits = [_Hit(c.id, 1.0 - i * 0.1) for i, c in enumerate(chunks)]

        passages = deduplicate_and_expand(db, hits, max_per_source=2)

        assert len(passages) == 2
        # The two highest-scoring passages are kept, not an arbitrary subset.
        assert {p.chunk_ids[0] for p in passages} == {chunks[0].id, chunks[1].id}
    finally:
        db.query(Chunk).delete()
        db.commit()
        db.close()


def test_empty_hits_returns_empty_list():
    db = SessionLocal()
    try:
        assert deduplicate_and_expand(db, []) == []
    finally:
        db.close()
