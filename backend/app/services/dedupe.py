"""Finding duplicate patients, merging two charts, and reading patient lists from CSV / Excel."""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from datetime import date, datetime
from difflib import SequenceMatcher

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Allergy, Condition, Counter, Medication, Patient
from app.services import runtime_config

# ---------------------------------------------------------------- matching


def norm_name(first: str, last: str) -> str:
    return re.sub(r"[^a-z ]", "", f"{first} {last}".lower()).strip()


def phone_key(phone: str | None) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-10:] if len(digits) >= 10 else ""


def name_similarity(a: str, b: str) -> float:
    """Order-insensitive similarity, so "Verma Rohit" matches "Rohit Verma"."""
    ta, tb = sorted(a.split()), sorted(b.split())
    return max(SequenceMatcher(None, a, b).ratio(), SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio())


def compare(a: dict, b: dict) -> tuple[int, list[str]]:
    """Score two people (dicts with first_name, last_name, date_of_birth, phone, email). 0-100 and the reasons."""
    sim = name_similarity(norm_name(a["first_name"], a["last_name"]), norm_name(b["first_name"], b["last_name"]))
    same_dob = bool(a.get("date_of_birth")) and a.get("date_of_birth") == b.get("date_of_birth")
    same_phone = bool(phone_key(a.get("phone"))) and phone_key(a.get("phone")) == phone_key(b.get("phone"))
    same_email = bool(a.get("email")) and (a.get("email") or "").lower() == (b.get("email") or "").lower()
    conflicting_dob = bool(a.get("date_of_birth")) and bool(b.get("date_of_birth")) and not same_dob
    reasons: list[str] = []
    score = 0
    if sim >= 0.97:
        score += 45
        reasons.append("same name")
    elif sim >= 0.82:
        score += 30
        reasons.append("similar name")
    elif sim >= 0.65:
        score += 12
        reasons.append("name partly matches")
    if same_dob:
        score += 35
        reasons.append("same date of birth")
    if same_phone:
        score += 30
        reasons.append("same phone number")
    if same_email:
        score += 25
        reasons.append("same email")
    if conflicting_dob:
        score -= 30
    if sim < 0.5 and not (same_phone and same_dob):
        score = min(score, 25)  # a shared family phone alone is not a duplicate
    return max(0, min(100, score)), reasons


STRONG = 70
POSSIBLE = 45


def _row(p: Patient) -> dict:
    return {
        "first_name": p.first_name,
        "last_name": p.last_name,
        "date_of_birth": p.date_of_birth,
        "phone": p.phone,
        "email": p.email,
    }


def find_matches(db: Session, person: dict, *, exclude_id: str | None = None, limit: int = 5) -> list[dict]:
    """Existing active patients who may be the same person as `person`."""
    last = (person.get("last_name") or "").strip().lower()
    first = (person.get("first_name") or "").strip().lower()
    pk = phone_key(person.get("phone"))
    stmt = select(Patient).where(Patient.status == "active", Patient.merged_into_id.is_(None))
    if exclude_id:
        stmt = stmt.where(Patient.id != exclude_id)
    conds = []
    if last:
        conds += [func.lower(Patient.last_name) == last, func.lower(Patient.first_name) == last]
    if first:
        conds += [func.lower(Patient.first_name) == first, func.lower(Patient.last_name) == first]
    if person.get("date_of_birth"):
        conds.append(Patient.date_of_birth == person["date_of_birth"])
    if pk:
        conds.append(Patient.phone.like(f"%{pk[-6:]}%"))
    if person.get("email"):
        conds.append(func.lower(Patient.email) == person["email"].lower())
    if not conds:
        return []
    from sqlalchemy import or_

    out = []
    for p in db.scalars(stmt.where(or_(*conds)).limit(400)):
        score, reasons = compare(person, _row(p))
        if score >= POSSIBLE:
            out.append(
                {
                    "id": p.id,
                    "mrn": p.mrn,
                    "name": p.full_name,
                    "date_of_birth": p.date_of_birth,
                    "phone": p.phone,
                    "score": score,
                    "strong": score >= STRONG,
                    "reasons": reasons,
                }
            )
    out.sort(key=lambda m: -m["score"])
    return out[:limit]


def scan_all(db: Session, limit: int = 100) -> list[dict]:
    """Pairs of active patients that look like the same person, found by blocking on name, date of birth and phone."""
    people = list(db.scalars(select(Patient).where(Patient.status == "active", Patient.merged_into_id.is_(None))))
    blocks: dict[str, list[Patient]] = defaultdict(list)
    for p in people:
        for key in {
            f"n:{sorted([p.first_name.lower(), p.last_name.lower()])}",
            f"d:{p.date_of_birth}:{p.last_name[:3].lower()}" if p.date_of_birth else "",
            f"p:{phone_key(p.phone)}" if phone_key(p.phone) else "",
        }:
            if key:
                blocks[key].append(p)
    seen: set[tuple[str, str]] = set()
    pairs = []
    for group in blocks.values():
        if len(group) < 2 or len(group) > 40:
            continue
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                k = (min(a.id, b.id), max(a.id, b.id))
                if k in seen:
                    continue
                seen.add(k)
                score, reasons = compare(_row(a), _row(b))
                if score >= STRONG:
                    pairs.append({"a": _summary(db, a), "b": _summary(db, b), "score": score, "reasons": reasons})
    pairs.sort(key=lambda x: -x["score"])
    return pairs[:limit]


def _summary(db: Session, p: Patient) -> dict:
    from app.models import Encounter, Prescription

    return {
        "id": p.id,
        "mrn": p.mrn,
        "name": p.full_name,
        "date_of_birth": p.date_of_birth,
        "phone": p.phone,
        "visits": db.scalar(select(func.count()).select_from(Encounter).where(Encounter.patient_id == p.id)) or 0,
        "prescriptions": db.scalar(
            select(func.count()).select_from(Prescription).where(Prescription.patient_id == p.id)
        )
        or 0,
        "created_at": p.created_at,
    }


# ---------------------------------------------------------------- merging


def _patient_tables() -> list[str]:
    """Every table with a patient_id column except the audit trail, which is never rewritten."""
    names = []
    for t in Base.metadata.sorted_tables:
        if t.name in ("audit_logs", "patients"):
            continue
        if "patient_id" in t.c:
            names.append(t.name)
    return names


def merge(db: Session, keep: Patient, dupe: Patient) -> dict:
    """Moves everything from `dupe` into `keep`. Returns counts per table. The caller commits and re-points vectors."""
    if keep.id == dupe.id:
        raise HTTPException(422, "Choose two different charts.")
    if dupe.merged_into_id or keep.merged_into_id:
        raise HTTPException(409, "One of these charts has already been merged into another.")
    moved: dict[str, int] = {}
    for table in _patient_tables():
        res = db.execute(
            text(f"UPDATE {table} SET patient_id = :k WHERE patient_id = :d"), {"k": keep.id, "d": dupe.id}
        )
        if res.rowcount:
            moved[table] = res.rowcount
    db.flush()
    db.expire_all()
    removed = _dedupe_lists(db, keep)
    for f in ("date_of_birth", "phone", "email", "address", "blood_group"):
        if not getattr(keep, f) and getattr(dupe, f):
            setattr(keep, f, getattr(dupe, f))
    if keep.sex in ("", "unknown") and dupe.sex not in ("", "unknown"):
        keep.sex = dupe.sex
    note = f"Merged chart {dupe.mrn} ({dupe.full_name}) into this one on {datetime.now().date().isoformat()}."
    keep.notes = f"{keep.notes}\n{note}" if keep.notes else note
    keep.tags = sorted(set(keep.tags or []) | set(dupe.tags or []))
    dupe.status = "archived"
    dupe.merged_into_id = keep.id
    return {"moved": moved, "duplicates_removed": removed}


def _dedupe_lists(db: Session, keep: Patient) -> int:
    """After a merge the same active problem, allergy or medicine (same dose) can appear twice: keep the oldest."""
    keys = {
        Condition: lambda r: (r.name or "").strip().lower(),
        Allergy: lambda r: (r.substance or "").strip().lower(),
        Medication: lambda r: (
            (r.name or "").strip().lower(),
            (r.dose or "").strip().lower(),
            (r.frequency or "").strip().lower(),
        ),
    }
    removed = 0
    for model, key in keys.items():
        seen: set = set()
        for r in db.scalars(
            select(model).where(model.patient_id == keep.id, model.status == "active").order_by(model.created_at)
        ):
            k = key(r)
            if k in seen:
                db.delete(r)
                removed += 1
            else:
                seen.add(k)
    return removed


# ---------------------------------------------------------------- MRN numbers


def mrn_prefix(db: Session) -> str:
    org = runtime_config.load(db).branding.organization or ""
    words = [w for w in re.split(r"\W+", org) if w]
    initials = "".join(w[0] for w in words).upper()
    return (initials if 2 <= len(initials) <= 5 else (words[0][:3].upper() if words else "PT")) or "PT"


def next_mrn(db: Session) -> str:
    """The next unused MRN, e.g. LCM-00016, never colliding with one a person typed by hand."""
    prefix = mrn_prefix(db)
    row = db.get(Counter, "MRN")
    if row is None:
        row = Counter(key="MRN", value=db.scalar(select(func.count()).select_from(Patient)) or 0)
        db.add(row)
    while True:
        row.value += 1
        mrn = f"{prefix}-{row.value:05d}"
        if not db.scalars(select(Patient).where(func.lower(Patient.mrn) == mrn.lower())).first():
            db.flush()
            return mrn


# ---------------------------------------------------------------- import

MAX_ROWS = 5000
MAX_BYTES = 8 * 1024 * 1024
FIELDS = {
    "mrn": ["mrn", "uhid", "patient id", "patient no", "id", "reg no", "registration no", "file no", "op no"],
    "full_name": ["name", "patient name", "full name", "patient"],
    "first_name": ["first name", "firstname", "given name", "fname"],
    "last_name": ["last name", "lastname", "surname", "family name", "lname"],
    "date_of_birth": ["dob", "date of birth", "birth date", "birthdate", "d.o.b"],
    "sex": ["sex", "gender"],
    "phone": ["phone", "mobile", "contact", "phone no", "mobile no", "contact no", "cell", "telephone"],
    "email": ["email", "e-mail", "email id"],
    "address": ["address", "residence", "location"],
    "blood_group": ["blood group", "blood type", "bg"],
    "notes": ["notes", "remarks", "comments"],
}
_SEX = {
    "m": "male",
    "male": "male",
    "man": "male",
    "f": "female",
    "female": "female",
    "woman": "female",
    "o": "other",
    "other": "other",
    "t": "other",
}


def read_table(filename: str, data: bytes) -> tuple[list[str], list[list[str]]]:
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "That file is larger than 8 MB. Split it and import in parts.")
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        try:
            ws = load_workbook(io.BytesIO(data), read_only=True, data_only=True).active
        except Exception as exc:
            raise HTTPException(422, "This Excel file could not be read.") from exc
        rows = [
            ["" if c is None else (c.date().isoformat() if isinstance(c, datetime) else str(c)) for c in r]
            for r in ws.iter_rows(values_only=True)
        ]
    elif name.endswith((".csv", ".txt", ".tsv")):
        raw = data.decode("utf-8-sig", errors="replace")
        try:
            dialect = csv.Sniffer().sniff(raw[:4096], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows = [list(r) for r in csv.reader(io.StringIO(raw), dialect)]
    else:
        raise HTTPException(422, "Use a .csv or .xlsx file.")
    rows = [[c.strip() for c in r] for r in rows if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise HTTPException(422, "The file needs a heading row and at least one patient.")
    if len(rows) - 1 > MAX_ROWS:
        raise HTTPException(413, f"More than {MAX_ROWS} patients in one file. Split it and import in parts.")
    return rows[0], rows[1:]


def suggest_mapping(headers: list[str]) -> dict[str, int | None]:
    low = [re.sub(r"[^a-z0-9. ]", " ", h.lower()).strip() for h in headers]
    mapping: dict[str, int | None] = {}
    used: set[int] = set()
    for field, names in FIELDS.items():
        idx = next((i for i, h in enumerate(low) if h in names and i not in used), None)
        if idx is not None:
            used.add(idx)
        mapping[field] = idx
    if mapping["full_name"] is not None and mapping["first_name"] is not None:
        mapping["full_name"] = None  # separate columns win
    return mapping


def parse_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%d %b %Y",
        "%d %B %Y",
        "%m/%d/%Y",
    ):
        try:
            d = datetime.strptime(s[:19] if fmt == "%Y-%m-%d" else s, fmt).date()
        except ValueError:
            continue
        if fmt.endswith("%y") and d.year > date.today().year:
            d = d.replace(year=d.year - 100)
        if date(1900, 1, 1) <= d <= date.today():
            return d
    raise ValueError(f"Date “{s}” is not recognised (use dd/mm/yyyy)")


def split_name(full: str) -> tuple[str, str]:
    full = re.sub(r"^(dr|mr|mrs|ms|miss|smt|shri|master|baby)\.?\s+", "", full.strip(), flags=re.I)
    if "," in full:
        last, first = [x.strip() for x in full.split(",", 1)]
        return first, last
    parts = full.split()
    return (" ".join(parts[:-1]), parts[-1]) if len(parts) > 1 else (full, "")


def build_rows(db: Session, headers: list[str], rows: list[list[str]], mapping: dict[str, int | None]) -> list[dict]:
    """Validates every row. status: new | exists | possible_duplicate | duplicate_in_file | error."""
    existing = {m.lower() for (m,) in db.execute(select(Patient.mrn))}
    seen_mrn: set[str] = set()
    seen_person: set[tuple] = set()
    out = []

    def cell(r: list[str], field: str) -> str:
        i = mapping.get(field)
        return r[i].strip() if i is not None and i < len(r) else ""

    for n, r in enumerate(rows, start=2):  # row 1 is the heading
        item: dict = {"row": n, "status": "new", "errors": [], "match": None}
        first, last = cell(r, "first_name"), cell(r, "last_name")
        if not first and cell(r, "full_name"):
            first, last = split_name(cell(r, "full_name"))
        sex = _SEX.get(cell(r, "sex").lower(), "unknown")
        dob = None
        try:
            dob = parse_date(cell(r, "date_of_birth"))
        except ValueError as exc:
            item["errors"].append(str(exc))
        if not first:
            item["errors"].append("Name is missing")
        email = cell(r, "email") or None
        if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            item["errors"].append(f"Email “{email}” is not valid")
            email = None
        mrn = cell(r, "mrn")
        item["person"] = {
            "mrn": mrn or None,
            "first_name": first,
            "last_name": last or "",
            "date_of_birth": dob.isoformat() if dob else None,
            "sex": sex,
            "phone": cell(r, "phone") or None,
            "email": email,
            "address": cell(r, "address") or None,
            "blood_group": cell(r, "blood_group") or None,
            "notes": cell(r, "notes") or None,
        }
        if item["errors"]:
            item["status"] = "error"
        elif mrn and mrn.lower() in existing:
            item["status"] = "exists"
        elif mrn and mrn.lower() in seen_mrn:
            item["status"] = "duplicate_in_file"
        else:
            sig = (norm_name(first, last), dob, phone_key(cell(r, "phone")))
            if sig in seen_person and sig[0]:
                item["status"] = "duplicate_in_file"
            else:
                match = find_matches(db, {**item["person"], "date_of_birth": dob}, limit=1)
                if match and match[0]["strong"]:
                    item["status"] = "possible_duplicate"
                    item["match"] = {k: match[0][k] for k in ("id", "mrn", "name", "reasons")}
            seen_person.add(sig)
        if mrn:
            seen_mrn.add(mrn.lower())
        out.append(item)
    return out
