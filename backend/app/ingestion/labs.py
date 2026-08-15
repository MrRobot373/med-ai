"""Structured lab/observation extraction from ingested report text — spec §33
"Laboratory Trend Engine".

Two complementary strategies, tried per table block / text line:

1. **Table, long format** — a header row naming Test/Result/Unit/Reference-Range-style
   columns (the layout our own PDF/DOCX/XLSX table extractors already produce for a
   genuine lab panel, and the shape spec §33's own example uses).
2. **Table, wide format** — no such header, but a column header itself names a known
   test (optionally with a unit in parentheses, e.g. "IOP (mmHg)"), with each row
   representing one measurement dimension (e.g. per-eye: OD/OS). Generic support for
   "vitals-style" tables, not hardcoded to any one test.
3. **Inline** — a single free-text mention, e.g. an OCT report's "Central subfield
   thickness: 340 microns (elevated)".

`_REGISTRY` below provides canonical names / aliases / a *typical* unit for grouping
and display only — it is deliberately NOT a source of reference ranges. Real reference
intervals vary by lab, sex, age, and method; baking one in as a "default" would be
exactly the kind of invented clinical fact spec §2 prohibits. `abnormal_flag` is set
only when the source document itself states a range (a Reference Range/Target column)
or an explicit qualitative annotation ("(elevated)", "(low)", ...) — never inferred
from a hardcoded threshold.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ingestion._tabular import TableBlock, find_header_column, find_table_blocks


@dataclass(frozen=True)
class _TestDef:
    canonical: str  # stored as normalized_name, e.g. "hba1c"
    display: str  # human label, e.g. "HbA1c"
    aliases: tuple[str, ...]
    canonical_unit: str | None


# The spec §33 explicit generic list, plus a few ophthalmology measurements relevant
# to this deployment's domain (see docs/architecture.md "Domain note") — the registry
# is intentionally extensible rather than limited to the spec's illustrative examples.
_REGISTRY: tuple[_TestDef, ...] = (
    _TestDef("hba1c", "HbA1c", ("hba1c", "hemoglobin a1c", "hgb a1c", "a1c"), "%"),
    _TestDef("glucose", "Glucose", ("fasting glucose", "glucose"), "mg/dL"),
    _TestDef("creatinine", "Creatinine", ("creatinine",), "mg/dL"),
    _TestDef("egfr", "eGFR", ("egfr", "gfr"), "mL/min/1.73m2"),
    _TestDef("sodium", "Sodium", ("sodium", "na+"), "mmol/L"),
    _TestDef("potassium", "Potassium", ("potassium", "k+"), "mmol/L"),
    _TestDef("bun", "BUN", ("bun", "blood urea nitrogen"), "mg/dL"),
    _TestDef("hemoglobin", "Hemoglobin", ("hemoglobin", "haemoglobin", "hgb"), "g/dL"),
    _TestDef("platelets", "Platelets", ("platelets", "platelet count"), "10^9/L"),
    _TestDef("ldl_cholesterol", "LDL Cholesterol", ("ldl cholesterol", "ldl"), "mg/dL"),
    _TestDef("hdl_cholesterol", "HDL Cholesterol", ("hdl cholesterol", "hdl"), "mg/dL"),
    _TestDef("total_cholesterol", "Total Cholesterol", ("total cholesterol",), "mg/dL"),
    _TestDef("iop", "IOP", ("intraocular pressure", "iop"), "mmHg"),
    _TestDef(
        "central_subfield_thickness",
        "Central Subfield Thickness",
        ("central subfield thickness", "cst"),
        "microns",
    ),
)


def _alias_pattern(alias: str) -> re.Pattern[str]:
    # A trailing/leading `\b` only makes sense next to a word character — aliases like
    # "na+"/"k+" end in a symbol, where a strict `\b` would fail to match "Na+ " at a
    # word/space boundary (both sides non-word).
    left = r"\b" if alias[0].isalnum() else ""
    right = r"\b" if alias[-1].isalnum() else ""
    return re.compile(left + re.escape(alias) + right)


# Longest alias first, so e.g. "central subfield thickness" is tried before the
# shorter "cst", and "fasting glucose" before bare "glucose".
_ALIAS_ENTRIES: tuple[tuple[re.Pattern[str], _TestDef], ...] = tuple(
    sorted(
        ((alias, _alias_pattern(alias), test_def) for test_def in _REGISTRY for alias in test_def.aliases),
        key=lambda entry: len(entry[0]),
        reverse=True,
    )
)
_ALIAS_ENTRIES = tuple((pattern, test_def) for _alias, pattern, test_def in _ALIAS_ENTRIES)

_HEADER_NAME_KEYWORDS = ("test", "name", "parameter", "analyte")
_HEADER_VALUE_KEYWORDS = ("result", "value")
_HEADER_UNIT_KEYWORDS = ("unit",)
_HEADER_RANGE_KEYWORDS = ("reference", "range", "normal", "target")

_QUALIFIER_WORDS = ("od", "os", "ou", "right eye", "left eye", "both eyes", "right", "left")

_NUMERIC_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")
_RANGE_PATTERN = re.compile(r"^(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)$")
_RANGE_LT_PATTERN = re.compile(r"^<\s*(-?\d+(?:\.\d+)?)$")
_RANGE_GT_PATTERN = re.compile(r"^>\s*(-?\d+(?:\.\d+)?)$")
_QUALITATIVE_PATTERN = re.compile(r"\((elevated|high|low|decreased|increased|abnormal|normal)\)", re.IGNORECASE)
_PAREN_UNIT_PATTERN = re.compile(r"\(([^)]+)\)")
_INLINE_VALUE_PATTERN = re.compile(r"[:\s]+(-?\d+(?:\.\d+)?)\s*([a-zA-Z%/^0-9.]*)")


@dataclass
class ExtractedObservation:
    observation_name: str
    normalized_name: str
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    reference_low: float | None
    reference_high: float | None
    abnormal_flag: bool | None
    source_page: int
    extraction_method: str  # "table" | "inline"
    source_excerpt: str


def extract_observations(pages: list[dict]) -> list[ExtractedObservation]:
    results: list[ExtractedObservation] = []
    for page_dict in pages:
        page_num = page_dict["page"]
        text = page_dict["text"]

        already: set[str] = set()
        for block in find_table_blocks(text, _is_lab_table_header):
            long_format = _extract_long_format(block, page_num)
            if long_format:
                results.extend(long_format)
                already.update(o.normalized_name.split(":")[0] for o in long_format)
                continue
            wide_format = _extract_wide_format(block, page_num)
            results.extend(wide_format)
            already.update(o.normalized_name.split(":")[0] for o in wide_format)

        results.extend(_extract_inline(text, page_num, already))
    return results


_PLAIN_NUMBER_PATTERN = re.compile(r"^-?\d+(?:\.\d+)?$")


def _is_lab_table_header(cells: list[str]) -> bool:
    name_col = find_header_column(cells, _HEADER_NAME_KEYWORDS)
    value_col = find_header_column(cells, _HEADER_VALUE_KEYWORDS)
    if name_col is not None and value_col is not None:
        return True  # long format: "Test | Result | Unit | Reference Range"
    if any(_PLAIN_NUMBER_PATTERN.match(cell) for cell in cells):
        # A row holding an actual measured value ("HbA1c | 8.1 | % | 4.0-5.6") is data,
        # not a header — even though its own name cell ("HbA1c") matches the registry
        # just as readily as a genuine wide-format header column name would.
        return False
    if name_col is None and value_col is None:
        return any(_match_registry(cell) for cell in cells)  # wide format: "IOP (mmHg)"
    return False


def _match_registry(text: str) -> _TestDef | None:
    for pattern, test_def in _ALIAS_ENTRIES:
        if pattern.search(text.lower()):
            return test_def
    return None


def _to_float(text: str) -> float | None:
    match = _NUMERIC_PATTERN.search(text)
    return float(match.group()) if match else None


def _parse_range(text: str) -> tuple[float | None, float | None]:
    stripped = text.strip()
    if not stripped:
        return None, None
    match = _RANGE_PATTERN.match(stripped)
    if match:
        return float(match.group(1)), float(match.group(2))
    match = _RANGE_LT_PATTERN.match(stripped)
    if match:
        return None, float(match.group(1))
    match = _RANGE_GT_PATTERN.match(stripped)
    if match:
        return float(match.group(1)), None
    return None, None


def _compute_abnormal(value: float | None, low: float | None, high: float | None) -> bool | None:
    if value is None or (low is None and high is None):
        return None
    return bool((low is not None and value < low) or (high is not None and value > high))


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "unknown"


def _extract_long_format(block: TableBlock, page: int) -> list[ExtractedObservation]:
    name_col = find_header_column(block.header, _HEADER_NAME_KEYWORDS)
    value_col = find_header_column(block.header, _HEADER_VALUE_KEYWORDS)
    if name_col is None or value_col is None:
        return []

    unit_col = find_header_column(block.header, _HEADER_UNIT_KEYWORDS)
    range_col = find_header_column(block.header, _HEADER_RANGE_KEYWORDS)

    results: list[ExtractedObservation] = []
    for row in block.rows:
        if name_col >= len(row) or value_col >= len(row):
            continue
        raw_name = row[name_col].strip()
        raw_value = row[value_col].strip()
        if not raw_name or not raw_value:
            continue

        test_def = _match_registry(raw_name)
        canonical = test_def.canonical if test_def else _slugify(raw_name)
        unit = None
        if unit_col is not None and unit_col < len(row):
            unit = row[unit_col].strip() or None
        if unit is None and test_def:
            unit = test_def.canonical_unit

        low = high = None
        if range_col is not None and range_col < len(row):
            low, high = _parse_range(row[range_col])

        value_numeric = _to_float(raw_value)
        results.append(
            ExtractedObservation(
                observation_name=raw_name,
                normalized_name=canonical,
                value_numeric=value_numeric,
                value_text=None if value_numeric is not None else raw_value,
                unit=unit,
                reference_low=low,
                reference_high=high,
                abnormal_flag=_compute_abnormal(value_numeric, low, high),
                source_page=page,
                extraction_method="table",
                source_excerpt=" | ".join(row),
            )
        )
    return results


def _extract_wide_format(block: TableBlock, page: int) -> list[ExtractedObservation]:
    name_col = find_header_column(block.header, _HEADER_NAME_KEYWORDS)
    value_col = find_header_column(block.header, _HEADER_VALUE_KEYWORDS)
    if name_col is not None or value_col is not None:
        return []  # already handled by long-format

    matches: dict[int, tuple[_TestDef, str | None]] = {}
    for idx, cell in enumerate(block.header):
        test_def = _match_registry(cell)
        if test_def:
            paren = _PAREN_UNIT_PATTERN.search(cell)
            unit = paren.group(1).strip() if paren else test_def.canonical_unit
            matches[idx] = (test_def, unit)
    if not matches:
        return []

    range_col = find_header_column(block.header, _HEADER_RANGE_KEYWORDS)
    qualifier_col = 0 if 0 not in matches else None

    results: list[ExtractedObservation] = []
    for row in block.rows:
        qualifier = None
        if qualifier_col is not None and qualifier_col < len(row):
            candidate = row[qualifier_col].strip()
            if candidate.lower() in _QUALIFIER_WORDS:
                qualifier = candidate

        for idx, (test_def, unit) in matches.items():
            if idx >= len(row):
                continue
            raw_value = row[idx].strip()
            if not raw_value:
                continue

            low = high = None
            if range_col is not None and range_col < len(row):
                low, high = _parse_range(row[range_col])

            value_numeric = _to_float(raw_value)
            name = f"{test_def.display} ({qualifier})" if qualifier else test_def.display
            normalized = f"{test_def.canonical}:{_slugify(qualifier)}" if qualifier else test_def.canonical
            results.append(
                ExtractedObservation(
                    observation_name=name,
                    normalized_name=normalized,
                    value_numeric=value_numeric,
                    value_text=None if value_numeric is not None else raw_value,
                    unit=unit,
                    reference_low=low,
                    reference_high=high,
                    abnormal_flag=_compute_abnormal(value_numeric, low, high),
                    source_page=page,
                    extraction_method="table",
                    source_excerpt=" | ".join(row),
                )
            )
    return results


def _extract_inline(text: str, page: int, already: set[str]) -> list[ExtractedObservation]:
    results: list[ExtractedObservation] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or " | " in stripped:
            continue  # table lines are handled by the table pass

        test_def = _match_registry(stripped)
        if test_def is None or test_def.canonical in already:
            continue

        pattern = next(p for p, d in _ALIAS_ENTRIES if d is test_def and p.search(stripped.lower()))
        match = pattern.search(stripped.lower())
        rest = stripped[match.end() :]
        value_match = _INLINE_VALUE_PATTERN.search(rest)
        if not value_match:
            continue

        value_numeric = float(value_match.group(1))
        unit = value_match.group(2).strip() or test_def.canonical_unit

        qualitative = _QUALITATIVE_PATTERN.search(stripped)
        abnormal = None
        if qualitative:
            abnormal = qualitative.group(1).lower() != "normal"

        results.append(
            ExtractedObservation(
                observation_name=test_def.display,
                normalized_name=test_def.canonical,
                value_numeric=value_numeric,
                value_text=None,
                unit=unit,
                reference_low=None,
                reference_high=None,
                abnormal_flag=abnormal,
                source_page=page,
                extraction_method="inline",
                source_excerpt=stripped,
            )
        )
        already.add(test_def.canonical)
    return results
