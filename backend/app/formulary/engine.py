"""Deterministic prescription checks. Every finding says what fired and on which
patient fact, so the doctor can judge it. The rules never block: critical findings
need a recorded reason to finalise, everything else is advisory. A second opinion
from the clinical model (MedGemma by default) is layered on top separately."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from app.formulary.catalog import Formulary, Generic, Resolved, fmt_amount
from app.formulary.dosing import Dose, Frequency, parse_dose, parse_frequency
from app.formulary.facts import PatientFacts

SEVERITY_ORDER = {"ok": 0, "info": 1, "warning": 2, "critical": 3}
PREGNANCY_SEVERITY = {"contraindicated": "critical", "avoid": "warning", "caution": "info"}


@dataclass
class Finding:
    code: str
    severity: str  # info | warning | critical
    title: str
    detail: str
    generic: str | None = None
    basis: str | None = None  # the patient fact behind it, e.g. "eGFR 38 (reported, 2026-09-12)"


@dataclass
class ItemInput:
    drug: str
    dose: str | None = "1 tab"
    frequency: str | None = "BD"
    duration_days: int | None = None
    strength: float | None = None
    instructions: str | None = None
    route: str | None = None


@dataclass
class ItemResult:
    index: int
    drug: str
    recognised: bool
    description: str
    generics: list[dict]
    form: str
    frequency_label: str
    per_dose: dict[str, float] = field(default_factory=dict)
    per_day: dict[str, float] = field(default_factory=dict)
    status: str = "ok"
    findings: list[Finding] = field(default_factory=list)

    def add(self, f: Finding) -> None:
        if any(
            x.code == f.code and x.title == f.title and (x.generic == f.generic or f.code == "interaction")
            for x in self.findings
        ):
            return
        self.findings.append(f)
        if SEVERITY_ORDER[f.severity] > SEVERITY_ORDER[self.status]:
            self.status = f.severity


def _fmt(v: float, unit: str) -> str:
    return f"{fmt_amount(round(v, 2))} {unit}"


def _egfr_basis(facts: PatientFacts) -> str:
    e = facts.egfr
    return f"eGFR {e.value:g} ({e.source}{', ' + e.date if e.date else ''})" if e else ""


def _amounts(r: Resolved, dose: Dose, freq: Frequency, g: Generic) -> tuple[float | None, str | None]:
    """Amount of one generic per administration, or a reason it cannot be computed."""
    if dose.quantity is None:
        return None, "Dose quantity could not be read"
    if dose.unit in ("mg", "mcg", "iu"):
        if len(r.generics) > 1:
            return None, "Dose written in mg for a combination product — write tablets/capsules instead"
        if dose.unit == g.unit.lower():
            return dose.quantity, None
        if dose.unit == "mg" and g.unit == "mcg":
            return dose.quantity * 1000, None
        if dose.unit == "mcg" and g.unit == "mg":
            return dose.quantity / 1000, None
        return dose.quantity, None
    per_unit = r.components.get(g.id)
    if per_unit is None:
        return None, "Strength not specified"
    if dose.unit == "ml":
        if not r.per_ml:
            return None, "Dose in mL for a solid form"
        return dose.quantity * per_unit, None
    if r.per_ml:
        return None, "Liquid product — write the dose in mL"
    return dose.quantity * per_unit, None


def _match_ref(ref: str, gid: str, tags: list[str]) -> bool:
    return ref == gid or (ref.startswith("class:") and ref[6:] in tags)


def _ref_label(fm: Formulary, ref: str) -> str:
    return (
        ref[6:].replace("_", " ")
        if ref.startswith("class:")
        else (fm.generics[ref].name if ref in fm.generics else ref)
    )


def check(fm: Formulary, facts: PatientFacts, items: list[ItemInput]) -> dict:
    resolved: list[Resolved] = [fm.resolve(it.drug, it.strength, parse_dose(it.dose).unit) for it in items]
    results: list[ItemResult] = []
    for idx, (it, r) in enumerate(zip(items, resolved, strict=True)):
        dose = parse_dose(it.dose)
        freq = parse_frequency(it.frequency, it.instructions)
        res = ItemResult(
            idx,
            it.drug,
            r.matched,
            r.describe(),
            [{"id": g.id, "name": g.name, "class": g.drug_class, "unit": g.unit} for g in r.generics],
            r.form,
            freq.label,
        )
        results.append(res)
        if not r.matched:
            res.add(
                Finding(
                    "unknown_drug",
                    "info",
                    "Not in the formulary",
                    "This medicine was not recognised, so rule checks could not run. The AI review still considers it.",
                )
            )
            continue
        if freq.per_day is None:
            res.add(
                Finding(
                    "frequency",
                    "warning",
                    "Frequency not understood",
                    f"“{it.frequency}” — use OD, BD, TDS, QID, HS, SOS, STAT, weekly or 1-0-1.",
                )
            )
        if freq.prn and freq.assumed:
            res.add(
                Finding(
                    "prn_max",
                    "info",
                    "As-needed without a maximum",
                    f"Daily totals assume up to {int(freq.per_day)} doses a day. Add “max N/day” to the instructions.",
                )
            )
        for g in r.generics:
            _check_generic(fm, facts, it, r, g, dose, freq, res)
        _check_special(fm, facts, it, r, dose, freq, res)

    _check_totals(fm, results)
    _check_duplicates(fm, facts, resolved, results)
    _check_interactions(fm, facts, resolved, results)
    _check_allergies(fm, facts, resolved, results)

    for res in results:
        res.findings.sort(key=lambda f: -SEVERITY_ORDER[f.severity])
    counts = {
        s: sum(1 for res in results for f in res.findings if f.severity == s) for s in ("critical", "warning", "info")
    }
    return {
        "region": fm.region,
        "formulary_version": fm.meta.get("version"),
        "source_note": fm.meta.get("source_note"),
        "items": [{**asdict(res), "findings": [asdict(f) for f in res.findings]} for res in results],
        "summary": counts,
        "status": max((res.status for res in results), key=lambda s: SEVERITY_ORDER[s], default="ok"),
    }


def _check_generic(
    fm: Formulary,
    facts: PatientFacts,
    it: ItemInput,
    r: Resolved,
    g: Generic,
    dose: Dose,
    freq: Frequency,
    res: ItemResult,
) -> None:
    d = g.data
    unit = g.unit
    prefix = f"{g.name}: " if len(r.generics) > 1 else ""
    per_admin, why = _amounts(r, dose, freq, g)
    if per_admin is None:
        res.add(
            Finding(
                "strength_missing",
                "info",
                f"{prefix}Dose not checked",
                f"{why}. Pick the strength (e.g. “{g.name} 500”) to check the dose.",
                g.id,
            )
        )
    per_day = per_admin * freq.per_day if per_admin is not None and freq.per_day is not None else None
    if per_admin is not None:
        res.per_dose[g.id] = round(per_admin, 3)
    if per_day is not None:
        res.per_day[g.id] = round(per_day, 3)

    # -- weekly-only drugs -------------------------------------------------------------------
    if d.get("weekly_only") and not freq.weekly and freq.per_day is not None:
        res.add(
            Finding(
                "weekly_only",
                "critical",
                f"{g.name} is given once WEEKLY",
                "Daily dosing has caused fatal toxicity. Change the frequency to weekly.",
                g.id,
            )
        )
        per_day_check = per_admin  # compare the weekly dose against weekly limits
    elif d.get("weekly_only"):
        per_day_check = per_admin
    else:
        per_day_check = per_day

    # -- limits, adjusted for the patient -------------------------------------------------------
    max_daily, reason = d.get("max_daily"), "adult maximum"
    if (
        facts.elderly
        and (d.get("elderly") or {}).get("max_daily") is not None
        and d["elderly"]["max_daily"] < (max_daily or 1e12)
    ):
        max_daily, reason = d["elderly"]["max_daily"], f"maximum at age {facts.age}"
    hep = d.get("hepatic") or {}
    if facts.hepatic and hep.get("max_daily") is not None and hep["max_daily"] < (max_daily or 1e12):
        max_daily, reason = hep["max_daily"], "maximum in hepatic impairment"
    renal_rule = None
    if facts.egfr is not None and d.get("renal"):
        applicable = [x for x in d["renal"] if facts.egfr.value < x["below"]]
        if applicable:
            renal_rule = min(applicable, key=lambda x: x["below"])
            if renal_rule.get("max_daily") is not None and renal_rule["max_daily"] < (max_daily or 1e12):
                max_daily, reason = renal_rule["max_daily"], f"renal maximum (eGFR {facts.egfr.value:g})"

    if per_admin is not None and d.get("max_single") is not None and per_admin > d["max_single"] * 1.001:
        res.add(
            Finding(
                "dose_single_high",
                "critical",
                f"{prefix}Single dose too high",
                f"{_fmt(per_admin, unit)} per dose exceeds the {_fmt(d['max_single'], unit)} maximum single dose.",
                g.id,
            )
        )
    if per_day_check is not None and max_daily is not None and per_day_check > max_daily * 1.001:
        note = d.get("max_daily_note")
        what = "weekly dose" if d.get("weekly_only") else "per day"
        res.add(
            Finding(
                "dose_daily_high",
                "critical",
                f"{prefix}{'Weekly' if d.get('weekly_only') else 'Daily'} dose too high",
                f"{_fmt(per_day_check, unit)} {what} exceeds the {reason} of {_fmt(max_daily, unit)}."
                + (f" {note}" if note else ""),
                g.id,
                _egfr_basis(facts) if "renal" in reason else (f"Age {facts.age}" if "age" in reason else None),
            )
        )
    usual = d.get("usual")
    if usual and per_day_check is not None and not freq.single and not freq.prn:
        lo, hi = usual
        if per_day_check < lo * 0.999 and not (renal_rule or facts.elderly or facts.hepatic):
            res.add(
                Finding(
                    "dose_low",
                    "info",
                    f"{prefix}Below the usual dose",
                    f"{_fmt(per_day_check, unit)}{' per week' if d.get('weekly_only') else '/day'} is below the usual adult range of {fmt_amount(lo)}–{_fmt(hi, unit)}. Fine if intentional (titration, low weight); otherwise it may be under-treating.",
                    g.id,
                )
            )
        elif per_day_check < lo * 0.999:
            res.add(
                Finding(
                    "dose_low",
                    "info",
                    f"{prefix}Below the usual dose",
                    f"{_fmt(per_day_check, unit)}/day is below the usual adult range ({fmt_amount(lo)}–{_fmt(hi, unit)}) — reasonable as a cautious start for this patient.",
                    g.id,
                )
            )
        elif per_day_check > hi * 1.001 and (max_daily is None or per_day_check <= max_daily * 1.001):
            res.add(
                Finding(
                    "dose_above_usual",
                    "info",
                    f"{prefix}Above the usual dose",
                    f"{_fmt(per_day_check, unit)}/day is above the usual range ({fmt_amount(lo)}–{_fmt(hi, unit)}) but within the maximum.",
                    g.id,
                )
            )

    # -- kidney --------------------------------------------------------------------------------
    if renal_rule:
        basis = _egfr_basis(facts)
        if renal_rule.get("avoid"):
            res.add(
                Finding(
                    "renal",
                    renal_rule.get("severity", "critical"),
                    f"{prefix}Kidney function: avoid",
                    renal_rule["note"],
                    g.id,
                    basis,
                )
            )
        else:
            within = (
                per_day_check is not None
                and renal_rule.get("max_daily") is not None
                and per_day_check <= renal_rule["max_daily"] * 1.001
            )
            res.add(
                Finding(
                    "renal",
                    "info" if within else renal_rule.get("severity", "warning"),
                    f"{prefix}Kidney dose adjustment",
                    renal_rule["note"],
                    g.id,
                    basis,
                )
            )
    elif (
        d.get("renal")
        and facts.egfr is None
        and any(x["below"] >= 30 for x in d["renal"])
        and (facts.elderly or facts.condition_matches(["kidney", "renal", "ckd", "nephropathy"]))
    ):
        res.add(
            Finding(
                "renal_unknown",
                "info",
                f"{prefix}No recent kidney function",
                "This medicine needs dose adjustment in reduced kidney function and no creatinine/eGFR is on file. Consider checking it.",
                g.id,
            )
        )

    # -- liver ---------------------------------------------------------------------------------
    if facts.hepatic and hep:
        res.add(
            Finding(
                "hepatic",
                hep.get("severity", "warning")
                if (hep.get("avoid") or hep.get("max_daily") is None or (per_day_check or 0) > hep["max_daily"])
                else "info",
                f"{prefix}Liver: {'avoid' if hep.get('avoid') else 'caution'}",
                hep["note"],
                g.id,
                str(facts.hepatic.source),
            )
        )

    # -- older adults -------------------------------------------------------------------------
    eld = d.get("elderly")
    if facts.elderly and eld:
        res.add(
            Finding(
                "elderly",
                eld.get("severity", "info"),
                f"{prefix}Age {facts.age}",
                eld["note"],
                g.id,
                f"Age {facts.age}",
            )
        )

    # -- pregnancy -----------------------------------------------------------------------------
    preg = d.get("pregnancy") or {}
    if facts.pregnant and preg.get("level") in PREGNANCY_SEVERITY:
        res.add(
            Finding(
                "pregnancy",
                PREGNANCY_SEVERITY[preg["level"]],
                f"{prefix}Pregnancy: {preg['level']}",
                preg.get("note", ""),
                g.id,
                "Pregnancy on problem list",
            )
        )

    # -- children -------------------------------------------------------------------------------
    paeds = d.get("paeds") or {}
    if facts.age is not None and facts.age < 18:
        if paeds.get("min_age") is not None and facts.age < paeds["min_age"]:
            res.add(
                Finding(
                    "paediatric",
                    paeds.get("severity", "warning"),
                    f"{prefix}Not recommended at age {facts.age}",
                    paeds.get("note") or f"Not recommended under {paeds['min_age']:g} years.",
                    g.id,
                    f"Age {facts.age}",
                )
            )
        if facts.age < 12:
            w = facts.weight.value if facts.weight else None
            if w is None and (paeds.get("mg_kg_day_max") or paeds.get("mg_kg_dose_max")):
                res.add(
                    Finding(
                        "paediatric_weight",
                        "warning",
                        f"{prefix}Weight needed",
                        "Children's doses are weight-based — record the weight to check this dose.",
                        g.id,
                    )
                )
            elif w:
                if (
                    paeds.get("mg_kg_dose_max")
                    and per_admin is not None
                    and per_admin > paeds["mg_kg_dose_max"] * w * 1.05
                ):
                    res.add(
                        Finding(
                            "paediatric_dose",
                            "critical",
                            f"{prefix}Dose too high for weight",
                            f"{_fmt(per_admin, unit)} per dose = {per_admin / w:.1f} {unit}/kg; maximum {paeds['mg_kg_dose_max']:g} {unit}/kg ({_fmt(paeds['mg_kg_dose_max'] * w, unit)} at {w:g} kg).",
                            g.id,
                            f"Weight {w:g} kg",
                        )
                    )
                if paeds.get("mg_kg_day_max") and per_day is not None and per_day > paeds["mg_kg_day_max"] * w * 1.05:
                    res.add(
                        Finding(
                            "paediatric_dose",
                            "critical",
                            f"{prefix}Daily dose too high for weight",
                            f"{_fmt(per_day, unit)}/day = {per_day / w:.1f} {unit}/kg/day; maximum {paeds['mg_kg_day_max']:g} {unit}/kg/day.",
                            g.id,
                            f"Weight {w:g} kg",
                        )
                    )
    cap = d.get("mg_kg_day_cap")
    if cap and facts.weight and per_day is not None and per_day > cap * facts.weight.value * 1.05:
        res.add(
            Finding(
                "weight_cap",
                "warning",
                f"{prefix}Above the weight-based limit",
                f"{_fmt(per_day, unit)}/day exceeds {cap:g} {unit}/kg/day ({_fmt(cap * facts.weight.value, unit)} at {facts.weight.value:g} kg).",
                g.id,
                f"Weight {facts.weight.value:g} kg",
            )
        )

    # -- problems --------------------------------------------------------------------------------
    for rule in d.get("conditions", []):
        hit = facts.condition_matches(rule["match"])
        if hit:
            res.add(
                Finding("condition", rule["severity"], f"{prefix}{hit}", rule["note"], g.id, f"Problem list: {hit}")
            )

    # -- labs ----------------------------------------------------------------------------------
    fired_codes: set[str] = set()
    for rule in d.get("labs", []):
        lab = facts.labs.get(rule["code"])
        if lab is None or rule["code"] in fired_codes:
            continue
        v = lab["value"]
        if ("above" in rule and v > rule["above"]) or ("below" in rule and v < rule["below"]):
            fired_codes.add(rule["code"])
            res.add(
                Finding(
                    "lab",
                    rule["severity"],
                    f"{prefix}{lab['name']} {v:g}{(' ' + lab['unit']) if lab.get('unit') else ''}",
                    rule["note"],
                    g.id,
                    f"{lab['name']} {v:g} ({lab.get('date')})",
                )
            )

    # -- course length ----------------------------------------------------------------------------
    if d.get("max_days") and it.duration_days and it.duration_days > d["max_days"]:
        res.add(
            Finding(
                "duration",
                "warning",
                f"{prefix}Long course",
                f"{it.duration_days} days — usually limited to {d['max_days']} days.",
                g.id,
            )
        )


def _check_special(
    fm: Formulary, facts: PatientFacts, it: ItemInput, r: Resolved, dose: Dose, freq: Frequency, res: ItemResult
) -> None:
    """Apixaban AF dose criteria (ABC: age ≥80, weight ≤60 kg, creatinine ≥1.5 mg/dL)."""
    if "apixaban" not in r.generic_ids or "apixaban" not in res.per_dose:
        return
    criteria = []
    if facts.age is not None and facts.age >= 80:
        criteria.append(f"age {facts.age}")
    if facts.weight and facts.weight.value <= 60:
        criteria.append(f"weight {facts.weight.value:g} kg")
    if facts.creatinine and facts.creatinine.value >= 1.5:
        criteria.append(f"creatinine {facts.creatinine.value:g}")
    per = res.per_dose["apixaban"]
    if not facts.condition_matches(["atrial fibrillation", "af"]):
        return
    if len(criteria) >= 2 and per > 2.5:
        res.add(
            Finding(
                "apixaban_dose",
                "warning",
                "Apixaban: reduced dose criteria met",
                f"{' and '.join(criteria)} — the AF dose is 2.5 mg twice daily.",
                "apixaban",
                ", ".join(criteria),
            )
        )
    elif len(criteria) < 2 and per < 5 and facts.weight and facts.creatinine and facts.age is not None:
        res.add(
            Finding(
                "apixaban_dose",
                "warning",
                "Apixaban may be under-dosed",
                f"Only {len(criteria)} of 3 dose-reduction criteria met ({', '.join(criteria) or 'none'}) — the AF dose would be 5 mg twice daily.",
                "apixaban",
            )
        )


def _check_totals(fm: Formulary, results: list[ItemResult]) -> None:
    """The same ingredient in several products (e.g. Dolo + Combiflam) — check the sum."""
    by_generic: dict[str, list[ItemResult]] = {}
    for res in results:
        for gid in res.per_day:
            by_generic.setdefault(gid, []).append(res)
    for gid, items in by_generic.items():
        g = fm.generics.get(gid)
        if len(items) < 2 or g is None or g.data.get("max_daily") is None:
            continue
        total = sum(r.per_day[gid] for r in items)
        if total > g.data["max_daily"] * 1.001:
            for r in items:
                r.add(
                    Finding(
                        "combined_total",
                        "critical",
                        f"Combined {g.name} too high",
                        f"{' + '.join(x.drug for x in items)} add up to {_fmt(total, g.unit)}/day (maximum {_fmt(g.data['max_daily'], g.unit)}).",
                        gid,
                    )
                )


def _check_duplicates(fm: Formulary, facts: PatientFacts, resolved: list[Resolved], results: list[ItemResult]) -> None:
    for i, r in enumerate(resolved):
        for j, other in enumerate(resolved):
            if j <= i:
                continue
            same = set(r.generic_ids) & set(other.generic_ids)
            for gid in same:
                for k in (i, j):
                    results[k].add(
                        Finding(
                            "duplicate",
                            "critical",
                            f"{fm.generics[gid].name} prescribed twice",
                            f"Both {results[i].drug} and {results[j].drug} contain {fm.generics[gid].name} — total dose adds up.",
                            gid,
                        )
                    )
            classes_i = {t for g in r.generics for t in g.tags} & fm.duplicate_classes
            classes_j = {t for g in other.generics for t in g.tags} & fm.duplicate_classes
            for cls in sorted(classes_i & classes_j):
                if same and all(cls in fm.generics[g].tags for g in same):
                    continue
                for k in (i, j):
                    results[k].add(
                        Finding(
                            "duplicate_class",
                            "warning",
                            f"Two {cls.replace('_', ' ').upper() if len(cls) <= 4 else cls.replace('_', ' ')}s",
                            f"{results[i].drug} and {results[j].drug} are from the same class — usually one is enough.",
                        )
                    )
        for med in facts.current_meds:
            same = set(r.generic_ids) & set(med.generic_ids)
            if same:
                names = ", ".join(fm.generics[g].name for g in same if g in fm.generics)
                results[i].add(
                    Finding(
                        "current_same",
                        "info",
                        f"Already taking {med.name}",
                        f"{names} is on the current medication list ({med.dose or ''} {med.frequency or ''}).".replace(
                            "  ", " "
                        )
                        + " Finalising replaces that entry with this one.",
                        basis="Current medications",
                    )
                )
                continue
            shared = {t for g in r.generics for t in g.tags} & set(med.tags) & fm.duplicate_classes
            for cls in sorted(shared):
                results[i].add(
                    Finding(
                        "current_class",
                        "warning",
                        f"Already on a {cls.replace('_', ' ')}: {med.name}",
                        f"{results[i].drug} duplicates the class of the current {med.name}. Stop one, or confirm both are intended.",
                        basis="Current medications",
                    )
                )


def _check_interactions(
    fm: Formulary, facts: PatientFacts, resolved: list[Resolved], results: list[ItemResult]
) -> None:
    # Participants: each new item's generics, plus current medicines and relevant problems.
    new: list[tuple[int, str, list[str], str]] = []
    for i, r in enumerate(resolved):
        for g in r.generics:
            new.append((i, g.id, g.tags, results[i].drug))
    existing: list[tuple[str, list[str], str]] = []
    replaced = {gid for r in resolved for gid in r.generic_ids}
    for med in facts.current_meds:
        for gid in med.generic_ids:
            if gid not in replaced:
                existing.append((gid, med.tags, f"{med.name} (current)"))
    if facts.condition_matches(["alcohol"]):
        existing.append(("alcohol", [], "Alcohol use (problem list)"))

    for rule in fm.interactions:
        for side_a, side_b in ((rule["a"], rule["b"]), (rule["b"], rule["a"])):
            for i, gid, tags, label in new:
                if not any(_match_ref(ref, gid, tags) for ref in side_a):
                    continue
                partners = [
                    (j, g2, l2) for j, g2, t2, l2 in new if j != i and any(_match_ref(ref, g2, t2) for ref in side_b)
                ]
                partners += [
                    (None, g2, l2) for g2, t2, l2 in existing if any(_match_ref(ref, g2, t2) for ref in side_b)
                ]
                for _j, g2, l2 in partners:
                    if g2 == gid:
                        continue
                    results[i].add(
                        Finding(
                            "interaction",
                            rule["severity"],
                            f"{rule['title']}: with {l2}",
                            rule["note"],
                            gid,
                            f"{label} + {l2}",
                        )
                    )


def _check_allergies(fm: Formulary, facts: PatientFacts, resolved: list[Resolved], results: list[ItemResult]) -> None:
    for i, r in enumerate(resolved):
        for g in r.generics:
            drug_groups = set(g.data.get("allergy", []))
            for a in facts.allergies:
                groups = set(a["groups"])
                direct = re.search(r"\b" + re.escape(g.name.lower().split()[0]), a["substance"].lower())
                if direct or drug_groups & groups:
                    reaction = f" (reaction: {a['reaction']})" if a.get("reaction") else ""
                    results[i].add(
                        Finding(
                            "allergy",
                            "critical",
                            f"Allergy: {a['substance']}",
                            f"{g.name} — documented {a['substance']} allergy{reaction}.",
                            g.id,
                            "Allergy list",
                        )
                    )
                    continue
                for cross in fm.cross_reactivity:
                    if (
                        cross["allergy"] in groups
                        and cross["drug_group"] in drug_groups
                        and cross["allergy"] != cross["drug_group"]
                    ):
                        results[i].add(
                            Finding(
                                "cross_allergy",
                                cross["severity"],
                                f"Cross-reactivity: {a['substance']} allergy",
                                cross["note"],
                                g.id,
                                "Allergy list",
                            )
                        )
