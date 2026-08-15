"""Section-aware chunking — spec §55.

Splits already-extracted, page-tagged text (the same `[{"page": int, "text": str}]`
shape produced by `pdf.py`/`docx.py`/`xlsx.py` and stored on `Report.extracted_content`)
into ~400-700 token passages with ~60-100 token overlap, respecting paragraph and
table boundaries rather than cutting blindly every N characters (spec §55/§56):

- Our own extractors already separate distinct logical elements (paragraphs, `[Table]`
  blocks) with blank lines, so a blank-line split recovers real document structure
  without needing a full layout parser.
- A `[Table]` block is never split across chunks, even if that makes one chunk larger
  than the target — spec §56 "do not destroy tables."
- A short, punctuation-free line is treated as a heading and tracked as the current
  section, both for chunk metadata and for the embedded "title / section / content"
  representation spec §55 asks for.

Token counts are an approximation (~1.3x word count, a common rule of thumb for
English text) — there's no real tokenizer for Qwen3-Embedding wired in here, and an
approximation is sufficient for sizing chunks. If a real tokenizer becomes available,
`_approx_tokens` is the one function to swap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_MAX_WORDS = 8
_HEADING_MAX_CHARS = 80


@dataclass
class ChunkResult:
    text: str  # embedded representation: "title\nsection\n\ncontent" (spec §55)
    raw_text: str  # content only, for display/citation excerpts
    page: int | None
    section: str | None
    chunk_index: int
    token_count: int


def _approx_tokens(text: str) -> int:
    words = text.split()
    return max(1, round(len(words) * 1.3))


def _looks_like_heading(block: str) -> bool:
    if "\n" in block or block.startswith("[Table]") or " | " in block:
        return False
    stripped = block.strip()
    if not stripped or len(stripped) > _HEADING_MAX_CHARS:
        return False
    if stripped.endswith((".", ",", ";")):
        return False
    return len(stripped.split()) <= _HEADING_MAX_WORDS


def _split_blocks(page_text: str) -> list[str]:
    """Blank-line-separated logical units — paragraphs, `[Table]` blocks, headings.
    A `[Table]` marker's following lines are pulled into the same block even if the
    extractor didn't blank-line-separate them internally (it doesn't need to)."""
    blocks: list[str] = []
    for raw_block in re.split(r"\n\s*\n", page_text):
        block = raw_block.strip()
        if block:
            blocks.append(block)
    return blocks


def chunk_pages(
    pages: list[dict],
    document_title: str,
    target_tokens: int = 550,
    overlap_tokens: int = 80,
) -> list[ChunkResult]:
    chunks: list[ChunkResult] = []
    current_section: str | None = None
    # The section captured when THIS chunk's buffer started — deliberately separate
    # from `current_section`, which keeps advancing as headings are seen. Reading
    # `current_section` at flush time (flushing is lazy, triggered by the next
    # overflowing block) would attribute a chunk to whatever heading came *after* its
    # actual content — a real bug caught during testing.
    buffer_section: str | None = None
    buffer_blocks: list[str] = []
    buffer_page: int | None = None
    chunk_index = 0

    def _flush() -> None:
        nonlocal buffer_blocks, buffer_page, chunk_index
        if not buffer_blocks:
            return
        raw_text = "\n\n".join(buffer_blocks)
        header = "\n".join(part for part in (document_title, buffer_section) if part)
        embedded = f"{header}\n\n{raw_text}" if header else raw_text
        chunks.append(
            ChunkResult(
                text=embedded,
                raw_text=raw_text,
                page=buffer_page,
                section=buffer_section,
                chunk_index=chunk_index,
                token_count=_approx_tokens(embedded),
            )
        )
        chunk_index += 1
        buffer_blocks = []
        buffer_page = None

    for page_dict in pages:
        page_num = page_dict.get("page")
        for block in _split_blocks(page_dict.get("text", "")):
            if _looks_like_heading(block):
                current_section = block
                continue

            candidate_tokens = _approx_tokens("\n\n".join([*buffer_blocks, block]))
            if buffer_blocks and candidate_tokens > target_tokens:
                _flush()
                # Carry the tail of the previous chunk forward as overlap so a passage
                # near a chunk boundary doesn't lose surrounding context entirely. The
                # overlap opens the new chunk, which now belongs to the current section.
                overlap_text = _tail_by_tokens(chunks[-1].raw_text, overlap_tokens)
                buffer_blocks = [overlap_text] if overlap_text else []
                buffer_section = current_section

            if not buffer_blocks:
                buffer_section = current_section  # first content of a fresh chunk

            buffer_blocks.append(block)
            buffer_page = page_num

    _flush()
    return chunks


def _tail_by_tokens(text: str, max_tokens: int) -> str:
    words = text.split()
    approx_words = max(1, round(max_tokens / 1.3))
    if len(words) <= approx_words:
        return text
    return " ".join(words[-approx_words:])
