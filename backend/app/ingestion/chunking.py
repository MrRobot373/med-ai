"""Structure-aware chunking: split on headings/paragraphs first, then pack into
~N-token windows with overlap. Each chunk keeps its page and nearest heading."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING = re.compile(r"^(#{1,6}\s+.+|[A-Z][A-Z0-9 /&\-]{3,60}:?)$")


@dataclass
class ChunkDraft:
    text: str
    page: int | None
    section: str | None
    tokens: int


def _tokens(text: str) -> int:
    return max(1, int(len(text.split()) * 1.33))


def chunk_pages(pages: list[dict], target_tokens: int = 550, overlap_tokens: int = 80) -> list[ChunkDraft]:
    blocks: list[tuple[str, int, str | None, bool]] = []
    for page in pages:
        section = None
        for para in re.split(r"\n\s*\n", page["text"]):
            para = para.strip()
            if not para:
                continue
            first = para.splitlines()[0].strip()
            is_heading = bool(_HEADING.match(first)) and len(first) < 80
            if is_heading:
                section = first.lstrip("#").strip().rstrip(":")
            blocks.append((para, page["page"], section, is_heading))

    chunks: list[ChunkDraft] = []
    buf: list[str] = []
    buf_tokens = 0
    buf_page: int | None = None
    buf_section: str | None = None
    fresh = False  # buffer holds content not yet emitted (beyond carried-over overlap)

    def flush():
        nonlocal buf, buf_tokens, fresh
        fresh = False
        if buf:
            text = "\n\n".join(buf).strip()
            chunks.append(ChunkDraft(text, buf_page, buf_section, _tokens(text)))
            # carry an overlap tail into the next chunk
            words = text.split()
            tail_words = int(overlap_tokens / 1.33)
            buf = [" ".join(words[-tail_words:])] if overlap_tokens and len(words) > tail_words else []
            buf_tokens = _tokens(buf[0]) if buf else 0

    for text, page, section, is_heading in blocks:
        t = _tokens(text)
        if is_heading and buf_tokens > target_tokens * 0.4:
            flush()
            buf, buf_tokens = [], 0  # a new topic starts clean, without overlap
        if t > target_tokens:
            # very long paragraph: split by sentences
            sentences: list[str] = []
            for sent in re.split(r"(?<=[.!?])\s+", text):
                words = sent.split()
                window = max(20, int(target_tokens / 1.33) - int(overlap_tokens / 1.33))
                if _tokens(sent) > target_tokens:
                    # unpunctuated runs (tables, OCR output): fall back to word windows
                    sentences += [" ".join(words[i : i + window]) for i in range(0, len(words), window)]
                else:
                    sentences.append(sent)
            for s in sentences:
                st = _tokens(s)
                if buf_tokens + st > target_tokens and buf_tokens > overlap_tokens:
                    flush()
                if not buf:
                    buf_page, buf_section = page, section
                buf.append(s)
                buf_tokens += st
                fresh = True
            continue
        if buf_tokens + t > target_tokens and buf_tokens > overlap_tokens:
            flush()
        if not buf or buf_tokens <= overlap_tokens:
            buf_page, buf_section = page, section
        buf.append(text)
        buf_tokens += t
        fresh = True
    if buf and fresh:
        text = "\n\n".join(buf).strip()
        chunks.append(ChunkDraft(text, buf_page, buf_section, _tokens(text)))
    return [c for c in chunks if c.text.strip()]
