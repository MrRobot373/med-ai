"""Lab / measurement extraction from report text.

Recognises a registry of common tests (aliases → canonical code) in table rows
("HbA1c | 8.1 | % | 4.0-5.6") and inline text ("Creatinine: 1.6 mg/dL (0.6-1.2) H").

Flags are only set from what the document itself states — its reference range or an
explicit H/L/abnormal marker. No built-in reference ranges are ever applied: real
intervals vary by laboratory, method, age and sex.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# code, display, aliases, typical unit (display grouping only)
REGISTRY: list[tuple[str, str, tuple[str, ...], str | None]] = [
    ("hba1c", "HbA1c", ("hba1c", "hemoglobin a1c", "haemoglobin a1c", "hgb a1c", "glycated hemoglobin", "a1c"), "%"),
    ("glucose_fasting", "Fasting glucose", ("fasting glucose", "fasting blood glucose", "fbg", "fbs"), "mg/dL"),
    ("glucose", "Glucose", ("random glucose", "blood glucose", "glucose"), "mg/dL"),
    ("creatinine", "Creatinine", ("serum creatinine", "creatinine"), "mg/dL"),
    ("egfr", "eGFR", ("egfr", "estimated gfr", "gfr"), "mL/min/1.73m²"),
    ("bun", "BUN", ("blood urea nitrogen", "bun", "urea"), "mg/dL"),
    ("uacr", "Urine albumin/creatinine", ("uacr", "albumin/creatinine ratio", "urine acr", "acr"), "mg/g"),
    ("sodium", "Sodium", ("sodium", "na+", "na"), "mmol/L"),
    ("potassium", "Potassium", ("potassium", "k+"), "mmol/L"),
    ("chloride", "Chloride", ("chloride", "cl-"), "mmol/L"),
    ("bicarbonate", "Bicarbonate", ("bicarbonate", "hco3", "total co2"), "mmol/L"),
    ("calcium", "Calcium", ("calcium", "ca2+"), "mg/dL"),
    ("hemoglobin", "Hemoglobin", ("hemoglobin", "haemoglobin", "hgb", "hb"), "g/dL"),
    ("hematocrit", "Hematocrit", ("hematocrit", "haematocrit", "hct"), "%"),
    ("wbc", "WBC", ("white blood cell count", "white blood cells", "wbc", "total leucocyte count", "tlc"), "10⁹/L"),
    ("platelets", "Platelets", ("platelet count", "platelets", "plt"), "10⁹/L"),
    ("mcv", "MCV", ("mean corpuscular volume", "mcv"), "fL"),
    ("ldl", "LDL cholesterol", ("ldl cholesterol", "ldl-c", "ldl"), "mg/dL"),
    ("hdl", "HDL cholesterol", ("hdl cholesterol", "hdl-c", "hdl"), "mg/dL"),
    ("total_cholesterol", "Total cholesterol", ("total cholesterol", "cholesterol, total", "cholesterol"), "mg/dL"),
    ("triglycerides", "Triglycerides", ("triglycerides", "tg"), "mg/dL"),
    ("alt", "ALT", ("alanine aminotransferase", "alt", "sgpt"), "U/L"),
    ("ast", "AST", ("aspartate aminotransferase", "ast", "sgot"), "U/L"),
    ("alp", "ALP", ("alkaline phosphatase", "alp"), "U/L"),
    ("bilirubin_total", "Total bilirubin", ("total bilirubin", "bilirubin, total", "bilirubin"), "mg/dL"),
    ("albumin", "Albumin", ("serum albumin", "albumin"), "g/dL"),
    ("tsh", "TSH", ("thyroid stimulating hormone", "tsh"), "mIU/L"),
    ("ft4", "Free T4", ("free t4", "ft4"), "ng/dL"),
    ("crp", "CRP", ("c-reactive protein", "crp", "hs-crp"), "mg/L"),
    ("esr", "ESR", ("erythrocyte sedimentation rate", "esr"), "mm/hr"),
    ("inr", "INR", ("inr",), None),
    ("bnp", "BNP", ("nt-probnp", "bnp"), "pg/mL"),
    ("troponin", "Troponin", ("high-sensitivity troponin", "troponin i", "troponin t", "troponin"), "ng/L"),
    ("ferritin", "Ferritin", ("ferritin",), "ng/mL"),
    ("vitamin_d", "Vitamin D (25-OH)", ("25-oh vitamin d", "vitamin d", "25(oh)d"), "ng/mL"),
    ("b12", "Vitamin B12", ("vitamin b12", "b12", "cobalamin"), "pg/mL"),
    ("uric_acid", "Uric acid", ("uric acid",), "mg/dL"),
    ("psa", "PSA", ("prostate specific antigen", "psa"), "ng/mL"),
    ("systolic_bp", "Systolic BP", ("systolic blood pressure", "systolic bp", "sbp"), "mmHg"),
    ("diastolic_bp", "Diastolic BP", ("diastolic blood pressure", "diastolic bp", "dbp"), "mmHg"),
    ("heart_rate", "Heart rate", ("heart rate", "pulse"), "bpm"),
    ("spo2", "SpO₂", ("oxygen saturation", "spo2", "sao2"), "%"),
    ("weight", "Weight", ("body weight", "weight"), "kg"),
    ("bmi", "BMI", ("body mass index", "bmi"), "kg/m²"),
    ("lvef", "LVEF", ("left ventricular ejection fraction", "ejection fraction", "lvef"), "%"),
    ("fev1", "FEV1", ("fev1",), "L"),
    ("iop", "IOP", ("intraocular pressure", "iop"), "mmHg"),
    ("cst", "Central subfield thickness", ("central subfield thickness", "cst"), "µm"),
]


def _pattern(alias: str) -> re.Pattern[str]:
    left = r"(?<![A-Za-z0-9])"
    right = r"(?![A-Za-z0-9])"
    return re.compile(left + re.escape(alias) + right, re.IGNORECASE)


_ALIASES = sorted(
    ((alias, _pattern(alias), code, display, unit) for code, display, aliases, unit in REGISTRY for alias in aliases),
    key=lambda e: len(e[0]),
    reverse=True,
)

_NUM = r"-?\d+(?:[.,]\d+)?"
_VALUE_AFTER = re.compile(
    rf"^[\s:=|\-–]*(?P<cmp>[<>≤≥]=?)?\s*(?P<value>{_NUM})\s*(?P<unit>[a-zA-Zµμ%/^0-9.²³⁹\-]*(?:/[a-zA-Z0-9.²³]+)*)?"
    rf"(?P<rest>.*)$"
)
_RANGE = re.compile(rf"(?P<low>{_NUM})\s*(?:-|–|to)\s*(?P<high>{_NUM})")
_RANGE_LT = re.compile(rf"(?:<|≤|up to)\s*(?P<high>{_NUM})")
_RANGE_GT = re.compile(rf"(?:>|≥)\s*(?P<low>{_NUM})")
_FLAG = re.compile(r"(?<![A-Za-z])(H|L|HIGH|LOW|ABNORMAL|CRITICAL|\*)(?![A-Za-z])", re.IGNORECASE)
_QUAL = re.compile(r"\b(elevated|raised|increased|decreased|reduced)\b", re.IGNORECASE)


@dataclass
class ExtractedObservation:
    code: str
    name: str
    value_num: float | None
    value_text: str | None
    unit: str | None
    ref_low: float | None
    ref_high: float | None
    ref_text: str | None
    flag: str | None
    page: int
    excerpt: str


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _parse_table_row(cells: list[str], page: int, line: str) -> ExtractedObservation | None:
    """`Name | Value | Unit | Range | Flag` style rows (any column order after the name)."""
    name = cells[0]
    match = next(
        (
            (code, display, header_unit_hint)
            for alias, pat, code, display, header_unit_hint in _ALIASES
            if pat.search(name) and len(name[: pat.search(name).start()].strip(" -•*")) <= 3
        ),
        None,
    )
    if match is None:
        return None
    code, display, _ = match
    hu = re.search(r"\(([^)]{1,15})\)", name)
    unit = hu.group(1) if hu else None
    value = None
    ref_low = ref_high = None
    ref_text = flag_cell = None
    for cell in cells[1:]:
        c = cell.strip()
        if not c:
            continue
        if value is None and re.fullmatch(rf"[<>]?\s*{_NUM}", c):
            value = _num(re.search(_NUM, c).group())
            continue
        rm = _RANGE.fullmatch(c) or None
        if rm:
            ref_low, ref_high, ref_text = _num(rm.group("low")), _num(rm.group("high")), c
            continue
        lt, gt = _RANGE_LT.fullmatch(c), _RANGE_GT.fullmatch(c)
        if lt or gt:
            ref_text = c
            if lt:
                ref_high = _num(lt.group("high"))
            else:
                ref_low = _num(gt.group("low"))
            continue
        if _FLAG.fullmatch(c):
            flag_cell = c.lower()
            continue
        if value is not None and unit is None and len(c) <= 15:
            unit = c
    if value is None:
        return None
    flag = _flag_from(value, ref_low, ref_high)
    if flag_cell and flag in (None, "normal"):
        flag = {"h": "high", "high": "high", "l": "low", "low": "low"}.get(flag_cell, "abnormal")
    return _with_side(
        ExtractedObservation(
            code=code,
            name=display,
            value_num=value,
            value_text=None,
            unit=unit,
            ref_low=ref_low,
            ref_high=ref_high,
            ref_text=ref_text,
            flag=flag,
            page=page,
            excerpt=line.strip()[:300],
        ),
        name,
    )


_SIDE = re.compile(r"(?<![A-Za-z])(OD|OS|OU|right eye|left eye|left|right)(?![A-Za-z])", re.IGNORECASE)
_SIDE_NAMES = {"od": "OD", "right eye": "OD", "right": "OD", "os": "OS", "left eye": "OS", "left": "OS", "ou": "OU"}


def _with_side(obs: ExtractedObservation, label: str) -> ExtractedObservation:
    """Per-eye / per-side measurements become separate series (IOP OD vs IOP OS)."""
    m = _SIDE.search(label)
    if m:
        side = _SIDE_NAMES[m.group(1).lower()]
        obs.code = f"{obs.code}_{side.lower()}"
        obs.name = f"{obs.name} {side}"
    return obs


def _flag_from(value: float, low: float | None, high: float | None) -> str | None:
    if low is not None and value < low:
        return "low"
    if high is not None and value > high:
        return "high"
    if low is not None or high is not None:
        return "normal"
    return None


def _parse_line(line: str, page: int) -> ExtractedObservation | None:
    if line.count("|") >= 1:
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 2:
            return _parse_table_row(cells, page, line)
    lowered = line.lower()
    for _alias, pat, code, display, typical_unit in _ALIASES:
        m = pat.search(line)
        if not m:
            continue
        # only match when the test name starts the line/cell (avoids prose mentions)
        prefix = line[: m.start()].strip(" |:-•*\t")
        if prefix and len(prefix) > 3:
            continue
        after = line[m.end() :]
        # skip "(units)" right after the name, e.g. "Creatinine (mg/dL) | 1.2"
        header_unit = None
        hu = re.match(r"\s*\(([^)]{1,15})\)", after)
        if hu and not re.match(rf"\s*\(\s*{_NUM}", after):
            header_unit = hu.group(1)
            after = after[hu.end() :]
        vm = _VALUE_AFTER.match(after)
        if not vm:
            return None
        value = _num(vm.group("value"))
        unit = (vm.group("unit") or "").strip(" |") or header_unit or None
        if unit and re.fullmatch(_NUM, unit):
            unit = header_unit
        rest = vm.group("rest") or ""
        ref_low = ref_high = None
        ref_text = None
        rm = _RANGE.search(rest)
        if rm:
            ref_low, ref_high = _num(rm.group("low")), _num(rm.group("high"))
            ref_text = rm.group(0)
        else:
            lt = _RANGE_LT.search(rest)
            gt = _RANGE_GT.search(rest)
            if lt:
                ref_high, ref_text = _num(lt.group("high")), lt.group(0)
            elif gt:
                ref_low, ref_text = _num(gt.group("low")), gt.group(0)
        flag = None
        if ref_low is not None and value < ref_low:
            flag = "low"
        elif ref_high is not None and value > ref_high:
            flag = "high"
        elif ref_low is not None or ref_high is not None:
            flag = "normal"
        fm = _FLAG.search(rest.replace(ref_text, " ") if ref_text else rest)
        if fm and flag in (None, "normal"):
            token = fm.group(1).lower()
            flag = {"h": "high", "high": "high", "l": "low", "low": "low"}.get(token, "abnormal")
        elif flag is None and _QUAL.search(rest):
            q = _QUAL.search(rest).group(1).lower()
            flag = "high" if q in ("elevated", "raised", "increased") else "low"
        _ = lowered, typical_unit
        return _with_side(
            ExtractedObservation(
                code=code,
                name=display,
                value_num=value,
                value_text=None,
                unit=unit,
                ref_low=ref_low,
                ref_high=ref_high,
                ref_text=ref_text,
                flag=flag,
                page=page,
                excerpt=line.strip()[:300],
            ),
            line[: m.end() + 12],
        )
    return None


def extract(pages: list[dict]) -> list[ExtractedObservation]:
    out: list[ExtractedObservation] = []
    seen: set[tuple[str, float | None, int]] = set()
    for page in pages:
        for raw in page["text"].splitlines():
            line = raw.strip()
            if not line or len(line) > 220:
                continue
            obs = _parse_line(line, page["page"])
            if obs is None:
                continue
            key = (obs.code, obs.value_num, obs.page)
            if key in seen:
                continue
            seen.add(key)
            out.append(obs)
    return out
