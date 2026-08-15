"""Section-aware chunking — spec §55. Pure unit tests against
`app/ingestion/chunking.py` (no DB/models/embedding needed)."""

from __future__ import annotations

from app.ingestion.chunking import chunk_pages


def test_headings_are_tracked_per_chunk_not_globally_at_flush_time():
    # Regression test: chunk metadata used to reflect whatever heading was most
    # recently seen at flush time (flushing is lazy), attributing a chunk's content
    # to the *next* section instead of the one it actually appeared under.
    pages = [
        {
            "page": 1,
            "text": (
                "Chief Complaint\n\n"
                "Increased glare while driving at night, worsening over six months.\n\n"
                "Assessment\n\n"
                "Cataract now visually significant in the right eye."
            ),
        }
    ]
    chunks = chunk_pages(pages, document_title="Doc", target_tokens=10, overlap_tokens=3)
    sections = [c.section for c in chunks]
    assert sections[0] == "Chief Complaint"
    assert "glare" in chunks[0].raw_text
    assert sections[-1] == "Assessment"
    assert "Cataract" in chunks[-1].raw_text


def test_table_block_is_never_split_across_chunks():
    pages = [
        {
            "page": 1,
            "text": (
                "Intraocular pressure at this visit:\n\n"
                "[Table]\nEye | IOP (mmHg) | Target\nOD | 16 | <18\nOS | 17 | <18\n\n"
                "Plan\n\nFollow-up in 4 weeks."
            ),
        }
    ]
    chunks = chunk_pages(pages, document_title="Doc", target_tokens=5, overlap_tokens=2)
    table_chunks = [c for c in chunks if "[Table]" in c.raw_text]
    assert len(table_chunks) == 1
    assert "OD | 16 | <18" in table_chunks[0].raw_text
    assert "OS | 17 | <18" in table_chunks[0].raw_text


def test_small_document_produces_one_chunk():
    pages = [{"page": 1, "text": "Short note.\n\nNothing more to say."}]
    chunks = chunk_pages(pages, document_title="Doc")
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0


def test_embedded_representation_includes_title_and_section():
    pages = [{"page": 1, "text": "Assessment\n\nStable, no changes."}]
    chunks = chunk_pages(pages, document_title="Wallace Consult")
    assert chunks[0].text.startswith("Wallace Consult\nAssessment")
    # The raw (display/citation) text does NOT repeat the title/section prefix.
    assert chunks[0].raw_text == "Stable, no changes."


def test_empty_pages_produce_no_chunks():
    assert chunk_pages([], document_title="Doc") == []
    assert chunk_pages([{"page": 1, "text": ""}], document_title="Doc") == []
