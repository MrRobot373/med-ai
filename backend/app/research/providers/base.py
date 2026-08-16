"""Common shape every trusted-source provider returns — spec §65. Each provider's
`search()` is independently best-effort: a network failure, timeout, or malformed
response returns an empty list rather than raising, so one unreachable source never
sinks the rest of a Research query (spec §122's "never let one stage's failure sink
the whole pipeline," applied here to external services instead of ingestion stages).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from app.models.web_cache import AuthorityTier, WebSource


@dataclass
class WebResult:
    title: str
    url: str
    text: str  # abstract/excerpt/summary — real, fetched content, never invented
    source: WebSource
    authority_tier: AuthorityTier
    published_at: date | None = None
    study_type: str | None = None  # "systematic_review" | "rct" | "observational" | None


# Found live (Phase 11): PubMed's esearch and openFDA's field-search both expect a
# keyword/boolean query, not a full natural-language sentence. A clinician question
# sent verbatim — punctuation and all — either returns zero hits (PubMed's esearch
# implicitly ANDs every space-separated word, so a single filler word like "what" or
# "for" that never co-occurs with the clinical terms in any article's metadata zeroes
# out the whole result set) or is rejected outright as invalid query syntax (openFDA
# 400'd on a literal quoted full-sentence phrase containing "(SLT)" and "?"). Only
# applied to PubMed/FDA, whose query languages are confirmed to need it — NOT to
# ClinicalTrials.gov or SearXNG, which are free-text search engines built to handle
# natural language directly; stripping stopwords there would more likely hurt
# relevance than help it.
_NON_WORD_PATTERN = re.compile(r"[^\w\s-]")
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "what", "which", "who", "whom", "this", "that", "these", "those",
        "for", "as", "of", "in", "on", "to", "and", "or", "with", "without",
        "do", "does", "did", "can", "could", "should", "would", "will", "shall",
        "may", "might", "must", "about", "into", "over", "under", "between",
        "from", "by", "at", "it", "its", "there", "if", "how", "when",
    }
)


def clean_search_terms(query: str) -> str:
    """Strips punctuation and common English stopwords down to the content keywords a
    keyword-search API can actually match against. Deliberately lossy (a stripped
    question is no longer grammatical) — the goal is a better match, not a readable
    string; nothing here is shown to a clinician, only sent to a search API."""
    cleaned = _NON_WORD_PATTERN.sub(" ", query)
    words = [w for w in re.sub(r"\s+", " ", cleaned).strip().split(" ") if w]
    kept = [w for w in words if w.lower() not in _STOPWORDS]
    # Every word being a stopword is degenerate input (e.g. "what is it") — fall back
    # to the punctuation-stripped original rather than sending an empty query.
    return " ".join(kept) if kept else " ".join(words)
