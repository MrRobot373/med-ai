"""Builds the patient-files/ folder: one folder per patient with their reports, images,
prescriptions and a registration.json the seed loads.

    backend/.venv/bin/python scripts/patient_files/build.py [output_dir]

Re-running replaces the output. All people and organisations are fictional; images come
from openly licensed datasets listed in each folder's IMAGE_SOURCES.md."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import cohort_a
import cohort_b
import cohort_c
from common import MANIFEST, Patient

ROOT = HERE.parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "patient-files"


def folder_name(p: Patient) -> str:
    return f"{p.folder_no:02d} - {p.full_name} ({p.uhid})"


def registration(p: Patient) -> dict:
    """What the seed needs to recreate the chart; documents are listed with their metadata."""
    return {
        "uhid": p.uhid,
        "honorific": p.honorific,
        "first_name": p.first_name,
        "last_name": p.last_name,
        "date_of_birth": p.dob.isoformat(),
        "sex": p.sex,
        "phone": p.phone,
        "email": p.email,
        "address": p.address,
        "blood_group": p.blood_group,
        "tags": p.tags,
        "summary": p.summary,
        "conditions": [
            {"name": c[0], "code": c[1], "since": c[2].isoformat(), "status": c[3] if len(c) > 3 else "active"} for c in p.conditions
        ],
        "allergies": [{"substance": a[0], "reaction": a[1], "severity": a[2]} for a in p.allergies],
        "medications": [
            {"name": m[0], "dose": m[1], "frequency": m[2], "indication": m[3], "since": m[4].isoformat()} for m in p.outside_meds
        ],
        "visits": [
            {
                **{k: v for k, v in v.items() if k not in ("date", "rx")},
                "date": v["date"].isoformat(),
                "prescription": None
                if not v.get("rx")
                else {
                    "items": [
                        {"drug": i[0], "dose": i[1], "frequency": i[2], "duration_days": i[3], "instructions": i[4]}
                        for i in v["rx"]["items"]
                    ],
                    "advice": v["rx"].get("advice"),
                    "follow_up_days": v["rx"].get("follow_up_days"),
                    "long_term": bool(v["rx"].get("chronic")),
                },
            }
            for v in p.visits
        ],
        "orders": [{"date": o[0].isoformat(), "test": o[1], "category": o[2], "reason": o[3], "visit": o[4]} for o in p.orders],
        "today": None if not p.today else {"time": p.today[0], "reason": p.today[1], "status": p.today[2]},
        "documents": [
            {"file": d.path, "title": d.title, "kind": d.kind, "date": d.on.isoformat(), "load": not d.pending}
            for d in sorted(p.docs, key=lambda d: (d.on, d.path))
        ],
    }


def sources_md(p: Patient) -> str | None:
    rows = [d for d in p.docs if d.source]
    if not rows:
        return None
    lines = [
        f"# Image sources — {p.full_name}",
        "",
        "The pictures in this folder are real, de-identified medical images from openly licensed research datasets. "
        "The patient, the headers burned into the images and all reports are fictional and were written for this demonstration set.",
        "",
    ]
    for d in rows:
        m = MANIFEST[d.source]
        lines += [f"## {d.path}", "", f"- Source: {m['dataset']}", f"- Licence: {m['license']}", f"- Citation: {m['citation']}", ""]
    return "\n".join(lines)


def main() -> int:
    patients = [f() for f in cohort_a.PATIENTS + cohort_b.PATIENTS + cohort_c.PATIENTS]
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    index = []
    for p in patients:
        base = OUT / folder_name(p)
        for d in p.docs:
            target = base / d.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(d.make())
        (base / "registration.json").write_text(json.dumps(registration(p), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        src = sources_md(p)
        if src:
            (base / "IMAGE_SOURCES.md").write_text(src + "\n", encoding="utf-8")
        index.append((p, len(p.docs)))
        print(f"{folder_name(p)}: {len(p.docs)} documents")
    readme = [
        "# Patient files",
        "",
        "Fifteen patient folders as a clinic would receive them: laboratory reports, imaging reports with the images "
        "(X-ray, ultrasound, CT and MRI — some as DICOM), ECG printouts, hospital discharge summaries and other doctors' prescriptions. "
        "`python -m app.seed demo` loads every folder into the application. Files under `To upload/` are left out so they can be "
        "uploaded during a walkthrough (for example by the front desk).",
        "",
        "All people, organisations and reports are fictional. The medical images are real, de-identified images from openly "
        "licensed datasets; each folder's `IMAGE_SOURCES.md` lists the dataset, licence and citation. Rebuild with "
        "`backend/.venv/bin/python scripts/patient_files/build.py`.",
        "",
        "| Folder | Patient | Documents |",
        "|---|---|---|",
    ]
    for p, n in index:
        readme.append(f"| {folder_name(p)} | {p.summary} | {n} |")
    (OUT / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    print(f"Wrote {len(patients)} patients to {OUT} ({date.today().isoformat()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
