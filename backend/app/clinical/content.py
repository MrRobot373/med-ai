"""Which clinical content ships in this version, and who has approved *exactly this* version of it.

Prescription rules, drug data, calculators and the reference library are medical content, not just code. A named
professional reads them and signs. The signature is tied to a fingerprint (SHA-256) of the content they reviewed:
the moment any of it changes — a new product version, an edited rule — the approval no longer applies and the
administrator sees "changed since it was reviewed" until it is signed again.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.core.config import PROJECT_ROOT

APP = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Area:
    key: str
    label: str
    what: str
    roles: tuple[str, ...]  # who must sign; each role by a different person
    paths: tuple[Path, ...]


AREAS: dict[str, Area] = {
    "formulary": Area(
        "formulary",
        "Prescription safety rules and drug database",
        "The medicines the system knows, their doses, interactions, allergy groups and the rules that raise alerts, plus the clinical test cases that prove they work.",
        ("clinical_lead", "pharmacist"),
        (
            APP / "formulary" / "data",
            APP / "formulary" / "engine.py",
            APP / "formulary" / "dosing.py",
            APP / "formulary" / "catalog.py",
            APP / "formulary" / "facts.py",
            APP / "clinical" / "testbank.json",
        ),
    ),
    "calculators": Area(
        "calculators",
        "Clinical scores and calculators",
        "The risk scores and calculators doctors can run on a patient (their formulas and thresholds).",
        ("clinical_lead",),
        (APP / "clinical" / "scores.py",),
    ),
    "knowledge": Area(
        "knowledge",
        "Reference library",
        "The reference documents the assistant quotes from when answering clinical questions.",
        ("clinical_lead",),
        (PROJECT_ROOT / "knowledge-packs",),
    ),
}
ROLE_LABEL = {"clinical_lead": "Clinical lead (doctor)", "pharmacist": "Pharmacist"}


def _files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return (
        sorted(p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
        if path.exists()
        else []
    )


def content_hash(area: Area) -> str:
    h = hashlib.sha256()
    for root in area.paths:
        base = root if root.is_dir() else root.parent
        for f in _files(root):
            h.update(f.relative_to(base).as_posix().encode() + b"\0")
            h.update(hashlib.sha256(f.read_bytes()).digest())
    return h.hexdigest()
