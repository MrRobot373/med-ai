"""Parsing of the way doses are written on Indian prescriptions: "1 tab", "½ tab",
"10 ml", "500 mg"; frequencies "OD/BD/TDS/QID/HS/SOS", "1-0-1", "q8h", "weekly"."""

from __future__ import annotations

import re
from dataclasses import dataclass

FRACTIONS = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3}

FREQUENCIES: dict[str, tuple[float, str]] = {
    "od": (1, "Once daily"),
    "qd": (1, "Once daily"),
    "daily": (1, "Once daily"),
    "once daily": (1, "Once daily"),
    "hs": (1, "At bedtime"),
    "qhs": (1, "At bedtime"),
    "bedtime": (1, "At bedtime"),
    "bd": (2, "Twice daily"),
    "bid": (2, "Twice daily"),
    "twice daily": (2, "Twice daily"),
    "tds": (3, "Three times daily"),
    "tid": (3, "Three times daily"),
    "thrice daily": (3, "Three times daily"),
    "qid": (4, "Four times daily"),
    "qds": (4, "Four times daily"),
    "q4h": (6, "Every 4 hours"),
    "q6h": (4, "Every 6 hours"),
    "q8h": (3, "Every 8 hours"),
    "q12h": (2, "Every 12 hours"),
    "q24h": (1, "Every 24 hours"),
    "q48h": (0.5, "Every 48 hours"),
    "eod": (0.5, "Alternate days"),
    "alternate day": (0.5, "Alternate days"),
    "alternate days": (0.5, "Alternate days"),
    "weekly": (1 / 7, "Once weekly"),
    "once weekly": (1 / 7, "Once weekly"),
    "ow": (1 / 7, "Once weekly"),
    "stat": (1, "Single dose"),
    "once": (1, "Single dose"),
    "single dose": (1, "Single dose"),
    "sos": (0, "As needed"),
    "prn": (0, "As needed"),
}
FREQUENCY_OPTIONS = [
    "OD",
    "BD",
    "TDS",
    "QID",
    "HS",
    "1-0-1",
    "1-1-1",
    "1-0-0",
    "0-0-1",
    "SOS",
    "STAT",
    "Weekly",
    "q8h",
    "q12h",
]
PRN_ASSUMED_PER_DAY = 3


def _num(text: str) -> float | None:
    text = text.strip()
    total = 0.0
    for ch, val in FRACTIONS.items():
        if ch in text:
            total += val
            text = text.replace(ch, "")
    text = text.strip()
    if not text:
        return total or None
    if "/" in text:
        a, _, b = text.partition("/")
        try:
            return total + float(a) / float(b)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return total + float(text)
    except ValueError:
        return None


@dataclass
class Dose:
    quantity: float | None
    unit: str  # "unit" (tab/cap/sachet/puff), "ml", "mg", "mcg", "iu"
    text: str


@dataclass
class Frequency:
    per_day: float | None  # None = could not be read
    label: str
    prn: bool = False
    weekly: bool = False
    single: bool = False
    pattern: bool = False  # "1-0-1": the numbers are units per time of day
    assumed: bool = False  # PRN without a stated maximum


def parse_dose(text: str | None) -> Dose:
    raw = (text or "").strip().lower()
    if not raw:
        return Dose(1.0, "unit", "1")
    m = re.match(r"^([\d.\s/½¼¾⅓⅔]+)\s*([a-zµ]*)", raw)
    if not m:
        return Dose(None, "unit", raw)
    qty = _num(m.group(1))
    word = m.group(2)
    if word in ("ml", "mls", "cc"):
        unit = "ml"
    elif word in ("tsp", "teaspoon"):
        return Dose(qty * 5 if qty is not None else None, "ml", raw)
    elif word in ("mg",):
        unit = "mg"
    elif word in ("g", "gm", "gram", "grams"):
        return Dose(qty * 1000 if qty is not None else None, "mg", raw)
    elif word in ("mcg", "µg", "ug"):
        unit = "mcg"
    elif word in ("iu", "u", "units"):
        unit = "iu"
    else:
        unit = "unit"
    return Dose(qty, unit, raw)


def parse_frequency(text: str | None, instructions: str | None = None) -> Frequency:
    raw = (text or "").strip().lower()
    if not raw:
        return Frequency(None, "Not stated")
    pat = re.fullmatch(r"([\d.½¼¾]+)\s*-\s*([\d.½¼¾]+)\s*-\s*([\d.½¼¾]+)(?:\s*-\s*([\d.½¼¾]+))?", raw)
    if pat:
        vals = [_num(v) or 0 for v in pat.groups() if v is not None]
        slots = ["morning", "afternoon", "night"] if len(vals) == 3 else ["morning", "afternoon", "evening", "night"]
        label = ", ".join(f"{v:g} {s}" for v, s in zip(vals, slots, strict=False) if v)
        return Frequency(sum(vals), label or "None", pattern=True)
    m = re.fullmatch(r"(?:every|q)\s*(\d+)\s*(?:h|hr|hrs|hours?)", raw)
    if m and int(m.group(1)) > 0:
        h = int(m.group(1))
        return Frequency(24 / h, f"Every {h} hours")
    if raw in FREQUENCIES:
        per_day, label = FREQUENCIES[raw]
        if per_day == 0:  # as needed
            cap = None
            if instructions:
                mm = re.search(
                    r"(?:max(?:imum)?|upto|up to)\s*(\d+)\s*(?:times|doses|tabs?)?\s*(?:/|a|per)?\s*day",
                    instructions.lower(),
                )
                cap = int(mm.group(1)) if mm else None
            return Frequency(float(cap or PRN_ASSUMED_PER_DAY), label, prn=True, assumed=cap is None)
        return Frequency(per_day, label, weekly=raw in ("weekly", "once weekly", "ow"), single=label == "Single dose")
    m = re.fullmatch(r"(\d+)\s*(?:x|times)\s*(?:a|/|per)?\s*day", raw)
    if m:
        return Frequency(float(m.group(1)), f"{m.group(1)} times daily")
    return Frequency(None, text or "")
