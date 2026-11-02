"""The patient facts a prescription is checked against: age, sex, weight, kidney and
liver function, pregnancy, problems, allergies, current medicines and recent labs.
Each fact records where it came from so the doctor can see why a check fired."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clinical.context import age as age_of
from app.clinical.context import latest_observations
from app.formulary.catalog import Formulary, norm
from app.models import Allergy, Condition, Encounter, Medication, Observation, Patient

HEPATIC_TERMS = (
    "cirrhosis",
    "hepatic impairment",
    "liver failure",
    "chronic liver disease",
    "hepatic failure",
    "liver disease",
    "hepatitis",
)


@dataclass
class Fact:
    value: float | str | bool | None
    source: str
    date: str | None = None
    document_id: str | None = None


@dataclass
class CurrentMed:
    id: str
    name: str
    generic_ids: list[str]
    tags: list[str]
    dose: str | None
    frequency: str | None


@dataclass
class PatientFacts:
    patient_id: str
    name: str
    age: int | None
    sex: str
    weight: Fact | None = None
    egfr: Fact | None = None
    creatinine: Fact | None = None
    hepatic: Fact | None = None
    pregnant: bool = False
    conditions: list[str] = field(default_factory=list)
    allergies: list[dict] = field(default_factory=list)
    current_meds: list[CurrentMed] = field(default_factory=list)
    labs: dict[str, dict] = field(default_factory=dict)

    @property
    def elderly(self) -> bool:
        return self.age is not None and self.age >= 65

    def condition_matches(self, keywords: list[str]) -> str | None:
        for name in self.conditions:
            low = name.lower()
            if any(re.search(r"\b" + re.escape(k.lower()), low) for k in keywords):
                return name
        return None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["elderly"] = self.elderly
        return data


def ckd_epi_2021(creatinine_mg_dl: float, age: int, sex: str) -> float:
    """CKD-EPI 2021 race-free creatinine equation (mL/min/1.73 m²)."""
    female = sex == "female"
    kappa, alpha = (0.7, -0.241) if female else (0.9, -0.302)
    ratio = creatinine_mg_dl / kappa
    egfr = 142 * min(ratio, 1) ** alpha * max(ratio, 1) ** -1.200 * 0.9938**age
    return egfr * 1.012 if female else egfr


def _obs_fact(o: Observation) -> Fact:
    return Fact(o.value_num, "result", o.observed_at.date().isoformat(), o.document_id)


def build(db: Session, patient: Patient, formulary: Formulary, exclude_prescription: str | None = None) -> PatientFacts:
    facts = PatientFacts(patient.id, patient.full_name, age_of(patient.date_of_birth), patient.sex or "unknown")
    obs = {o.code: o for o in latest_observations(db, patient.id, limit_codes=80) if o.value_num is not None}
    for code, o in obs.items():
        facts.labs[code] = {
            "name": o.name,
            "value": o.value_num,
            "unit": o.unit,
            "flag": o.flag,
            "ref_high": o.ref_high,
            "ref_low": o.ref_low,
            "date": o.observed_at.date().isoformat(),
            "document_id": o.document_id,
        }

    # Weight: latest result, else latest encounter vitals.
    if "weight" in obs:
        facts.weight = _obs_fact(obs["weight"])
    else:
        for e in db.scalars(
            select(Encounter).where(Encounter.patient_id == patient.id).order_by(Encounter.started_at.desc())
        ):
            w = (e.vitals or {}).get("weight_kg")
            if w not in (None, ""):
                try:
                    facts.weight = Fact(float(w), "encounter vitals", e.started_at.date().isoformat())
                    break
                except (TypeError, ValueError):
                    continue
        # Vitals heart rate / BP feed lab-style rules when no result exists.
        for e in db.scalars(
            select(Encounter).where(Encounter.patient_id == patient.id).order_by(Encounter.started_at.desc()).limit(1)
        ):
            v = e.vitals or {}
            if "heart_rate" not in facts.labs and v.get("hr"):
                facts.labs["heart_rate"] = {
                    "name": "Heart rate",
                    "value": float(v["hr"]),
                    "unit": "bpm",
                    "date": e.started_at.date().isoformat(),
                    "source": "vitals",
                }
            bp = str(v.get("bp") or "")
            if "systolic_bp" not in facts.labs and "/" in bp:
                try:
                    facts.labs["systolic_bp"] = {
                        "name": "Systolic BP",
                        "value": float(bp.split("/")[0]),
                        "unit": "mmHg",
                        "date": e.started_at.date().isoformat(),
                        "source": "vitals",
                    }
                except ValueError:
                    pass

    # Kidney function: a reported eGFR unless the creatinine is newer, then CKD-EPI 2021.
    cr = obs.get("creatinine")
    if cr is not None:
        value = cr.value_num / 88.4 if (cr.unit or "").lower().startswith("µmol") or cr.value_num > 20 else cr.value_num
        facts.creatinine = Fact(round(value, 2), "result", cr.observed_at.date().isoformat(), cr.document_id)
    reported = obs.get("egfr")
    if reported is not None and (cr is None or reported.observed_at >= cr.observed_at):
        facts.egfr = Fact(
            reported.value_num, "reported eGFR", reported.observed_at.date().isoformat(), reported.document_id
        )
    elif cr is not None and facts.age is not None and facts.sex in ("male", "female"):
        facts.egfr = Fact(
            round(ckd_epi_2021(facts.creatinine.value, facts.age, facts.sex)),
            "calculated (CKD-EPI 2021 from creatinine)",
            facts.creatinine.date,
            cr.document_id,
        )

    conditions = list(
        db.scalars(
            select(Condition).where(
                Condition.patient_id == patient.id, Condition.status.in_(["active", "chronic", "recurrence", "relapse"])
            )
        )
    )
    facts.conditions = [c.name for c in conditions]

    # Liver: a documented diagnosis, or transaminases ≥ 3× the upper limit.
    hep = facts.condition_matches(list(HEPATIC_TERMS))
    if hep and "fatty" not in hep.lower():
        facts.hepatic = Fact(True, f"problem list: {hep}")
    else:
        for code in ("alt", "ast"):
            o = obs.get(code)
            if o is not None:
                uln = o.ref_high or 40
                if o.value_num >= 3 * uln:
                    facts.hepatic = Fact(
                        True,
                        f"{o.name} {o.value_num:g} U/L (≥3× upper limit)",
                        o.observed_at.date().isoformat(),
                        o.document_id,
                    )
                    break
    preg = facts.condition_matches(["pregnan"])
    facts.pregnant = bool(preg) and facts.sex != "male"

    for a in db.scalars(select(Allergy).where(Allergy.patient_id == patient.id, Allergy.status == "active")):
        facts.allergies.append(
            {
                "substance": a.substance,
                "reaction": a.reaction,
                "severity": a.severity,
                "groups": allergy_groups(formulary, a.substance),
            }
        )

    meds = db.scalars(select(Medication).where(Medication.patient_id == patient.id, Medication.status == "active"))
    for m in meds:
        if exclude_prescription and m.prescription_id == exclude_prescription:
            continue
        r = formulary.resolve(m.generic or m.name)
        if not r.generics and m.generic:
            r = formulary.resolve(m.name)
        gids = r.generic_ids or [norm(m.name)]
        tags = sorted({t for g in r.generics for t in g.tags})
        facts.current_meds.append(CurrentMed(m.id, m.name, gids, tags, m.dose, m.frequency))
    return facts


def allergy_groups(formulary: Formulary, substance: str) -> list[str]:
    low = substance.lower()
    groups = [
        g for g, words in formulary.allergy_groups.items() if any(re.search(r"\b" + re.escape(w), low) for w in words)
    ]
    generic = formulary.find_generic(substance)
    if generic:
        groups += [g for g in generic.data.get("allergy", []) if g not in groups]
    return groups


def today() -> date:
    return date.today()
