"""Post-generation citation validation: labels the model used that do not exist in
the provided context are removed (and reported), never shown as real sources."""

from __future__ import annotations

import re

_LABEL = re.compile(r"\[((?:[PK]\d{1,3}|R)(?:\s*,\s*(?:[PK]\d{1,3}|R))*)\]")


def validate(answer: str, allowed: set[str]) -> tuple[str, list[str], list[str]]:
    used: list[str] = []
    invalid: list[str] = []

    def repl(m: re.Match) -> str:
        labels = [x.strip() for x in m.group(1).split(",")]
        keep = []
        for label in labels:
            if label in allowed:
                keep.append(label)
                if label not in used:
                    used.append(label)
            elif label not in invalid:
                invalid.append(label)
        return "".join(f"[{k}]" for k in keep)

    cleaned = _LABEL.sub(repl, answer)
    return cleaned, used, invalid


def coverage(answer: str) -> float | None:
    """Share of substantive sentences carrying at least one citation."""
    body = re.sub(r"^#+ .*$", "", answer, flags=re.MULTILINE)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n+", body) if len(s.split()) >= 5]
    if not sentences:
        return None
    cited = sum(1 for s in sentences if _LABEL.search(s))
    return round(cited / len(sentences), 2)
