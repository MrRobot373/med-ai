"""Patient-specific clinical scores and safety checks, computed deterministically from
documented chart data using published rules. A score only appears when it applies to
this patient (e.g. CHA2DS2-VASc only with atrial fibrillation) and every input shows
where it came from; missing inputs are listed rather than assumed."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clinical.context import age, latest_observations
from app.models import Condition, Encounter, Medication, Observation, Patient


@dataclass
class Input:
    label: str
    value: str
    source: str  # "result", "problem list", "demographics", "medication list", "encounter vitals"
    date: str | None = None
    document_id: str | None = None


@dataclass
class Score:
    id: str
    kind: str  # "score" | "check"
    name: str
    value: str
    category: str
    level: int  # 0..len(levels)-1, higher = more concerning
    levels: list[str]
    summary: str
    reference: str
    inputs: list[Input] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    note: str | None = None


def _has(conditions: list[Condition], *keywords: str) -> Condition | None:
    """Whole-word match ("tia" must not match "essential"); a keyword may be a word prefix
    ("thromboembol" matches "thromboembolism")."""
    patterns = [re.compile(r"\b" + re.escape(k)) for k in keywords]
    for c in conditions:
        if c.status != "refuted" and any(pt.search(c.name.lower()) for pt in patterns):
            return c
    return None


def _obs_input(o: Observation, label: str | None = None) -> Input:
    return Input(
        label or o.name,
        f"{o.value_num:g} {o.unit or ''}".strip(),
        "result",
        o.observed_at.date().isoformat(),
        o.document_id,
    )


def _ckd(obs: dict[str, Observation]) -> Score | None:
    egfr = obs.get("egfr")
    if egfr is None or egfr.value_num is None:
        return None
    g = egfr.value_num
    gcat = (
        "G1" if g >= 90 else "G2" if g >= 60 else "G3a" if g >= 45 else "G3b" if g >= 30 else "G4" if g >= 15 else "G5"
    )
    uacr = obs.get("uacr")
    inputs = [_obs_input(egfr, "eGFR")]
    missing = []
    if uacr is not None and uacr.value_num is not None:
        a = uacr.value_num
        acat = "A1" if a < 30 else "A2" if a <= 300 else "A3"
        inputs.append(_obs_input(uacr, "UACR"))
    else:
        acat = None
        missing.append("Urine albumin-to-creatinine ratio (UACR)")
    grid = {
        "G1": [0, 1, 2],
        "G2": [0, 1, 2],
        "G3a": [1, 2, 3],
        "G3b": [2, 3, 3],
        "G4": [3, 3, 3],
        "G5": [3, 3, 3],
    }
    if acat:
        level = grid[gcat][["A1", "A2", "A3"].index(acat)]
    else:
        level = {"G1": 0, "G2": 0, "G3a": 1, "G3b": 2, "G4": 3, "G5": 3}[gcat]
    if gcat in ("G1", "G2") and acat in (None, "A1"):
        return None  # no CKD markers documented — not applicable
    levels = ["Low", "Moderate", "High", "Very high"]
    return Score(
        id="ckd_kdigo",
        kind="score",
        name="CKD stage (KDIGO)",
        value=f"{gcat} {acat or ''}".strip(),
        category=f"{levels[level]} risk",
        level=level,
        levels=levels,
        summary=f"eGFR {g:g}" + (f" · UACR {uacr.value_num:g} mg/g" if acat else " · albuminuria not measured"),
        reference="KDIGO 2024 CKD guideline — GFR (G) and albuminuria (A) categories, prognosis heat map",
        inputs=inputs,
        missing=missing,
        note="Staged from the latest values; CKD requires abnormalities persisting > 3 months.",
    )


def _cha2ds2vasc(p: Patient, conditions: list[Condition], obs: dict[str, Observation]) -> Score | None:
    af = _has(conditions, "atrial fibrillation", "atrial flutter")
    if af is None:
        return None
    inputs = [Input("Atrial fibrillation", af.name, "problem list")]
    missing = []
    points = 0
    a = age(p.date_of_birth)
    if a is None:
        missing.append("Age (date of birth)")
    else:
        pts = 2 if a >= 75 else 1 if a >= 65 else 0
        points += pts
        inputs.append(Input(f"Age {a} (+{pts})", str(a), "demographics"))
    if p.sex == "female":
        points += 1
        inputs.append(Input("Female sex (+1)", "female", "demographics"))
    elif p.sex not in ("male",):
        missing.append("Sex")
    lvef = obs.get("lvef")
    for keys, label, pts in (
        (("heart failure", "hfref", "hfpef", "ventricular dysfunction", "cardiomyopathy"), "Heart failure", 1),
        (("hypertension",), "Hypertension", 1),
        (("diabetes",), "Diabetes", 1),
        (
            ("stroke", "transient ischaemic", "transient ischemic", "tia", "thromboembol"),
            "Stroke / TIA / thromboembolism",
            2,
        ),
        (
            ("myocardial infarction", "coronary", "peripheral arter", "aortic plaque", "vascular disease"),
            "Vascular disease",
            1,
        ),
    ):
        c = _has(conditions, *keys)
        if (
            c is None
            and label == "Heart failure"
            and lvef is not None
            and lvef.value_num is not None
            and lvef.value_num <= 40
        ):
            points += 1
            inputs.append(_obs_input(lvef, "LVEF ≤ 40% (+1)"))
            continue
        if c is not None:
            points += pts
            inputs.append(Input(f"{label} (+{pts})", c.name, "problem list"))
    female = p.sex == "female"
    threshold_rec, threshold_consider = (3, 2) if female else (2, 1)
    if points >= threshold_rec:
        level, category = 2, "Anticoagulation recommended"
    elif points >= threshold_consider:
        level, category = 1, "Anticoagulation should be considered"
    else:
        level, category = 0, "Low stroke risk"
    return Score(
        id="cha2ds2vasc",
        kind="score",
        name="CHA₂DS₂-VASc",
        value=str(points),
        category=category,
        level=level,
        levels=["Low", "Consider", "Recommended"],
        summary=f"Stroke-risk score {points} in atrial fibrillation",
        reference="Lip GY et al. Chest 2010; 2023 ACC/AHA/ACCP/HRS AF guideline thresholds",
        inputs=inputs,
        missing=missing,
        note="Only documented problems are counted; undocumented risk factors score 0.",
    )


def _glycaemic(conditions: list[Condition], obs: dict[str, Observation]) -> Score | None:
    dm = _has(conditions, "diabetes")
    a1c = obs.get("hba1c")
    if dm is None or a1c is None or a1c.value_num is None:
        return None
    v = a1c.value_num
    level = 0 if v < 7 else 1 if v < 8 else 2 if v < 9 else 3
    levels = ["At target", "Above", "Well above", "Markedly above"]
    return Score(
        id="glycaemic",
        kind="score",
        name="Glycaemic control",
        value=f"{v:g}%",
        category=f"{levels[level]} general target" if level else "At general target",
        level=level,
        levels=levels,
        summary="HbA1c against the commonly used < 7% target",
        reference="ADA Standards of Care — individualised HbA1c targets (< 7% for many adults)",
        inputs=[Input("Diabetes", dm.name, "problem list"), _obs_input(a1c, "HbA1c")],
        note="Targets should be individualised (e.g. < 8% with frailty or hypoglycaemia risk).",
    )


def _active_med(meds: list[Medication], name: str) -> Medication | None:
    return next((m for m in meds if m.status == "active" and name in m.name.lower()), None)


def _latest_weight(db: Session, p: Patient, obs: dict[str, Observation]) -> Input | None:
    w = obs.get("weight")
    if w is not None and w.value_num is not None:
        return _obs_input(w, "Weight")
    for e in db.scalars(select(Encounter).where(Encounter.patient_id == p.id).order_by(Encounter.started_at.desc())):
        v = (e.vitals or {}).get("weight_kg")
        if v not in (None, ""):
            return Input("Weight", f"{v} kg", "encounter vitals", e.started_at.date().isoformat())
    return None


def _metformin(meds: list[Medication], obs: dict[str, Observation]) -> Score | None:
    m = _active_med(meds, "metformin")
    egfr = obs.get("egfr")
    if m is None or egfr is None or egfr.value_num is None:
        return None
    g = egfr.value_num
    if g >= 45:
        level, category = 0, "No renal dose limit at this eGFR"
    elif g >= 30:
        level, category = 2, "Review dose — max 1,000 mg/day; do not initiate"
    else:
        level, category = 3, "Contraindicated below eGFR 30"
    return Score(
        id="metformin_renal",
        kind="check",
        name="Metformin · renal dosing",
        value=f"eGFR {g:g}",
        category=category,
        level=level,
        levels=["OK", "Monitor", "Review", "Stop"],
        summary=f"{m.name} {m.dose or ''} {m.frequency or ''}".strip(),
        reference="FDA metformin labelling; KDIGO 2022 Diabetes in CKD (dose reduction at eGFR 30–44)",
        inputs=[
            Input("Medication", f"{m.name} {m.dose or ''} {m.frequency or ''}".strip(), "medication list"),
            _obs_input(egfr, "eGFR"),
        ],
    )


def _apixaban(db: Session, p: Patient, meds: list[Medication], obs: dict[str, Observation]) -> Score | None:
    m = _active_med(meds, "apixaban")
    if m is None:
        return None
    met, inputs, missing = (
        0,
        [Input("Medication", f"{m.name} {m.dose or ''} {m.frequency or ''}".strip(), "medication list")],
        [],
    )
    a = age(p.date_of_birth)
    if a is None:
        missing.append("Age")
    else:
        met += a >= 80
        inputs.append(Input(f"Age ≥ 80: {'yes' if a >= 80 else 'no'}", str(a), "demographics"))
    w = _latest_weight(db, p, obs)
    if w is None:
        missing.append("Body weight")
    else:
        kg = float("".join(ch for ch in w.value.split()[0] if ch.isdigit() or ch == "."))
        met += kg <= 60
        w.label = f"Weight ≤ 60 kg: {'yes' if kg <= 60 else 'no'}"
        inputs.append(w)
    cr = obs.get("creatinine")
    if cr is None or cr.value_num is None:
        missing.append("Serum creatinine")
    else:
        met += cr.value_num >= 1.5
        inputs.append(_obs_input(cr, f"Creatinine ≥ 1.5 mg/dL: {'yes' if cr.value_num >= 1.5 else 'no'}"))
    on_full = "5" in (m.dose or "") and "2.5" not in (m.dose or "")
    if met >= 2:
        level, category = (
            (3, "Criteria for 2.5 mg twice daily met — on 5 mg")
            if on_full
            else (0, "Reduced dose criteria met — dose consistent")
        )
    elif met == 1 or missing:
        level, category = 1, f"{met} of 3 criteria met" + (" — some inputs missing" if missing else "")
    else:
        level, category = 0, "Standard dose criteria"
    return Score(
        id="apixaban_dose",
        kind="check",
        name="Apixaban · dose criteria (AF)",
        value=f"{met} of 3",
        category=category,
        level=level,
        levels=["OK", "Monitor", "Review", "Act"],
        summary="Reduce to 2.5 mg twice daily if ≥ 2 of: age ≥ 80, weight ≤ 60 kg, creatinine ≥ 1.5 mg/dL",
        reference="Apixaban (Eliquis) prescribing information — non-valvular AF dosing",
        inputs=inputs,
        missing=missing,
    )


def compute(db: Session, p: Patient) -> list[dict]:
    conditions = list(db.scalars(select(Condition).where(Condition.patient_id == p.id)))
    meds = list(db.scalars(select(Medication).where(Medication.patient_id == p.id)))
    obs = {o.code: o for o in latest_observations(db, p.id, limit_codes=60)}
    items = [
        _ckd(obs),
        _cha2ds2vasc(p, conditions, obs),
        _glycaemic(conditions, obs),
        _metformin(meds, obs),
        _apixaban(db, p, meds, obs),
    ]
    out = [asdict(s) for s in items if s is not None]
    out.sort(key=lambda s: (-s["level"] / max(len(s["levels"]) - 1, 1), s["kind"] != "score"))
    return out
