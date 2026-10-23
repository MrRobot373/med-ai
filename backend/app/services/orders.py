"""Investigation orders and matching returned reports to them. A report uploaded by
the front desk or the doctor is linked to the open order it answers ("USG abdomen" ↔
"Ultrasonography of whole abdomen") so it surfaces for review."""

from __future__ import annotations

import re
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import Document, Order

TEST_GROUPS: dict[str, tuple[str, ...]] = {
    "ultrasound": ("usg", "ultrasound", "ultrasonography", "sonography", "sonogram", "doppler"),
    "xray": ("x-ray", "xray", "x ray", "radiograph", "cxr", "skiagram"),
    "ct": ("ct", "cect", "ncct", "hrct", "computed tomography", "ct scan"),
    "mri": ("mri", "mr imaging", "magnetic resonance"),
    "ecg": ("ecg", "ekg", "electrocardiogram"),
    "echo": ("echo", "2d echo", "echocardiogram", "echocardiography"),
    "tmt": ("tmt", "treadmill", "stress test", "exercise ecg"),
    "endoscopy": ("endoscopy", "ogd", "ugi scopy", "gastroscopy", "colonoscopy"),
    "cbc": ("cbc", "complete blood count", "haemogram", "hemogram", "blood count"),
    "lft": ("lft", "liver function"),
    "kft": ("kft", "rft", "renal function", "kidney function", "creatinine"),
    "lipid": ("lipid", "cholesterol"),
    "hba1c": ("hba1c", "glycated", "glycosylated", "a1c"),
    "glucose": ("fbs", "ppbs", "rbs", "blood sugar", "glucose"),
    "thyroid": ("tft", "thyroid", "tsh"),
    "urine": ("urine routine", "urinalysis", "urine r/m", "urine culture", "urine"),
    "stool": ("stool",),
    "pancreas": ("amylase", "lipase"),
    "hpylori": ("h. pylori", "h pylori", "helicobacter", "urea breath"),
    "electrolytes": ("electrolytes", "sodium", "potassium"),
    "uacr": ("uacr", "microalbumin", "albumin creatinine"),
    "vitamin": ("vitamin d", "vitamin b12", "b12"),
    "pft": ("pft", "spirometry", "pulmonary function"),
}
REGIONS = (
    "abdomen",
    "chest",
    "pelvis",
    "kub",
    "brain",
    "head",
    "neck",
    "spine",
    "knee",
    "thyroid",
    "liver",
    "kidney",
    "renal",
    "cardiac",
    "heart",
)
CATEGORY_OF = {
    "tmt": "cardiology",
    "ultrasound": "radiology",
    "xray": "radiology",
    "ct": "radiology",
    "mri": "radiology",
    "ecg": "cardiology",
    "echo": "cardiology",
    "endoscopy": "other",
    "pft": "other",
}


def _groups(text: str) -> set[str]:
    low = f" {text.lower()} "
    found = set()
    for group, words in TEST_GROUPS.items():
        for w in words:
            if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", low):
                found.add(group)
                break
    return found


def _regions(text: str) -> set[str]:
    low = text.lower()
    return {r for r in REGIONS if r in low}


def guess_category(test_name: str) -> str:
    for g in _groups(test_name):
        if g in CATEGORY_OF:
            return CATEGORY_OF[g]
    return "lab"


def match_score(order: Order, doc: Document, text: str = "") -> float:
    order_groups = _groups(order.test_name)
    if not order_groups:
        return 0.0
    head = f"{doc.title} {doc.filename} {doc.kind or ''}"
    head_groups = _groups(head)
    body_groups = _groups(text[:3000])
    score = 2.0 * len(order_groups & head_groups) + 1.0 * len(order_groups & body_groups)
    if score == 0:
        return 0.0
    oreg = _regions(order.test_name)
    if oreg:
        dreg = _regions(head + " " + text[:1500])
        score += 1.0 if oreg & dreg else -0.5
    return score


def open_orders(db: Session, patient_id: str) -> list[Order]:
    return list(
        db.scalars(
            select(Order)
            .where(Order.patient_id == patient_id, Order.status == "ordered")
            .order_by(Order.ordered_at.desc())
        )
    )


def attach(db: Session, order: Order, doc: Document) -> None:
    order.result_document_id = doc.id
    order.status = "result_received"
    order.result_at = utcnow()
    if doc.encounter_id is None and order.encounter_id:
        doc.encounter_id = order.encounter_id


def auto_match(db: Session, doc: Document, text: str) -> Order | None:
    """Link a newly processed report to the best open order, if one clearly matches."""
    if doc.patient_id is None or doc.identity_status == "mismatch":
        return None
    if db.scalar(select(Order).where(Order.result_document_id == doc.id)) is not None:
        return None
    # A report can only answer an order placed before it (one day of slack for same-day paperwork).
    candidates = [
        o
        for o in open_orders(db, doc.patient_id)
        if doc.document_date is None or doc.document_date >= o.ordered_at.date() - timedelta(days=1)
    ]
    scored = sorted(((match_score(o, doc, text), o) for o in candidates), key=lambda x: -x[0])
    if not scored or scored[0][0] < 1.0:
        return None
    if len(scored) > 1 and scored[1][0] == scored[0][0]:
        # Two equally good candidates — take the oldest open one (asked for first).
        best = min((o for s, o in scored if s == scored[0][0]), key=lambda o: o.ordered_at)
    else:
        best = scored[0][1]
    attach(db, best, doc)
    return best
