"""Demo data and knowledge-pack loader.

    python -m app.seed demo          # demo users, synthetic patients, reports, knowledge packs
    python -m app.seed knowledge     # (re)load knowledge packs only
    python -m app.seed reprocess     # retry documents that failed (e.g. AI was offline)
    python -m app.seed use-mock-ai http://127.0.0.1:9100/v1   # point all AI roles at the mock server

With the embedded vector store, run seeding while the API server is stopped (the
embedded store is single-process).

All demo patients are fictional and flagged `synthetic`.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.core.config import PROJECT_ROOT, get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db import SessionLocal
from app.models import Allergy, Condition, Document, Encounter, Medication, Patient, User
from app.services import documents

logger = get_logger("seed")
NOW = datetime.now(UTC)
PACKS = PROJECT_ROOT / "knowledge-packs"


def ago(days: int) -> datetime:
    return NOW - timedelta(days=days)


DEMO_USERS = [
    ("doctor@gms.local", "Dr. Ananya Rao", "Dr.", "Internal Medicine", "clinician", "Doctor@12345"),
    ("viewer@gms.local", "Sam Lee", None, "Clinical audit", "viewer", "Viewer@12345"),
]

# Each patient: demographics, problems, meds, allergies, encounters, and lab reports.
PATIENTS = [
    {
        "mrn": "DEMO-1001",
        "first_name": "James",
        "last_name": "Carter",
        "dob": date(1963, 3, 14),
        "sex": "male",
        "phone": "555-0101",
        "tags": ["diabetes", "ckd", "high-risk"],
        "blood_group": "O+",
        "conditions": [
            ("Type 2 diabetes mellitus", "E11.9", "active", 3650),
            ("Essential hypertension", "I10", "active", 4000),
            ("Chronic kidney disease, stage 3a", "N18.31", "active", 400),
            ("Hyperlipidaemia", "E78.5", "active", 2500),
        ],
        "meds": [
            ("Metformin", "1000 mg", "oral", "twice daily", "Type 2 diabetes", 3000),
            ("Lisinopril", "20 mg", "oral", "once daily", "Hypertension / albuminuria", 2000),
            ("Atorvastatin", "40 mg", "oral", "once nightly", "Hyperlipidaemia", 2400),
        ],
        "allergies": [("Penicillin", "Generalised urticarial rash", "moderate")],
        "encounters": [
            (
                200,
                "outpatient",
                "Diabetes and kidney review",
                "HbA1c above target. eGFR 52. Advised dietary review, continue metformin and lisinopril. Repeat labs in 6 months.",
                {"bp": "142/88", "hr": 78, "weight_kg": 94},
            ),
            (
                14,
                "follow_up",
                "Six-month diabetes / CKD follow-up",
                "Reports fatigue and nocturia. Ankle oedema mild. Labs show worsening kidney function and higher HbA1c. Discussed adding SGLT2 inhibitor; review metformin dose for eGFR.",
                {"bp": "148/90", "hr": 82, "weight_kg": 96},
            ),
        ],
        "reports": [
            (
                210,
                "Metabolic panel — prior",
                [
                    ("HbA1c", "7.9", "%", "4.0-5.6", "H"),
                    ("Fasting glucose", "152", "mg/dL", "70-99", "H"),
                    ("Creatinine", "1.32", "mg/dL", "0.70-1.30", "H"),
                    ("eGFR", "52", "mL/min/1.73m2", ">60", "L"),
                    ("Potassium", "4.8", "mmol/L", "3.5-5.1", ""),
                    ("UACR", "45", "mg/g", "<30", "H"),
                    ("LDL cholesterol", "96", "mg/dL", "<100", ""),
                ],
                "Impression: suboptimal glycaemic control; CKD G3a A2.",
            ),
            (
                16,
                "Metabolic panel — current",
                [
                    ("HbA1c", "8.4", "%", "4.0-5.6", "H"),
                    ("Fasting glucose", "171", "mg/dL", "70-99", "H"),
                    ("Creatinine", "1.58", "mg/dL", "0.70-1.30", "H"),
                    ("eGFR", "44", "mL/min/1.73m2", ">60", "L"),
                    ("Potassium", "5.4", "mmol/L", "3.5-5.1", "H"),
                    ("UACR", "128", "mg/g", "<30", "H"),
                    ("LDL cholesterol", "88", "mg/dL", "<100", ""),
                ],
                "Impression: worsening glycaemic control and kidney function (now G3b A2). Mild hyperkalaemia.",
            ),
        ],
    },
    {
        "mrn": "DEMO-1002",
        "first_name": "Priya",
        "last_name": "Sharma",
        "dob": date(1980, 8, 2),
        "sex": "female",
        "phone": "555-0102",
        "tags": ["thyroid", "anaemia"],
        "blood_group": "B+",
        "conditions": [
            ("Primary hypothyroidism", "E03.9", "active", 900),
            ("Iron deficiency anaemia", "D50.9", "active", 150),
        ],
        "meds": [
            ("Levothyroxine", "75 mcg", "oral", "once daily before breakfast", "Hypothyroidism", 900),
            ("Ferrous sulfate", "325 mg", "oral", "alternate days", "Iron deficiency", 120),
        ],
        "allergies": [],
        "encounters": [
            (
                150,
                "outpatient",
                "Fatigue and heavy menstrual bleeding",
                "TSH elevated on current dose; Hb low with low ferritin. Started oral iron on alternate days, increased levothyroxine to 75 mcg. Advised separating iron and levothyroxine by 4 hours.",
                {"bp": "112/72", "hr": 88},
            ),
            (
                20,
                "follow_up",
                "Thyroid and anaemia follow-up",
                "Energy improved. Taking iron and levothyroxine together at breakfast most days.",
                {"bp": "110/70", "hr": 76},
            ),
        ],
        "reports": [
            (
                155,
                "Thyroid and CBC panel",
                [
                    ("TSH", "8.2", "mIU/L", "0.4-4.0", "H"),
                    ("Free T4", "0.8", "ng/dL", "0.9-1.7", "L"),
                    ("Hemoglobin", "10.1", "g/dL", "12.0-15.5", "L"),
                    ("MCV", "74", "fL", "80-100", "L"),
                    ("Ferritin", "8", "ng/mL", "15-150", "L"),
                ],
                "Impression: under-replaced hypothyroidism; microcytic anaemia consistent with iron deficiency.",
            ),
            (
                22,
                "Thyroid and CBC panel — follow-up",
                [
                    ("TSH", "5.1", "mIU/L", "0.4-4.0", "H"),
                    ("Free T4", "1.0", "ng/dL", "0.9-1.7", ""),
                    ("Hemoglobin", "11.6", "g/dL", "12.0-15.5", "L"),
                    ("MCV", "79", "fL", "80-100", "L"),
                    ("Ferritin", "19", "ng/mL", "15-150", ""),
                ],
                "Impression: improving; TSH still above range.",
            ),
        ],
    },
    {
        "mrn": "DEMO-1003",
        "first_name": "Robert",
        "last_name": "Klein",
        "dob": date(1958, 9, 3),
        "sex": "male",
        "phone": "555-0103",
        "tags": ["ophthalmology", "diabetes"],
        "blood_group": "A+",
        "conditions": [
            ("Primary open-angle glaucoma, bilateral", "H40.1131", "active", 300),
            ("Type 2 diabetes mellitus with mild non-proliferative diabetic retinopathy", "E11.329", "active", 1800),
        ],
        "meds": [
            ("Latanoprost 0.005%", "1 drop", "ophthalmic", "nightly, both eyes", "Glaucoma", 300),
            ("Timolol 0.5%", "1 drop", "ophthalmic", "twice daily, both eyes", "Glaucoma", 210),
            ("Metformin", "500 mg", "oral", "twice daily", "Type 2 diabetes", 1800),
        ],
        "allergies": [("Sulfonamide antibiotics", "Rash", "mild")],
        "encounters": [
            (
                300,
                "outpatient",
                "Elevated intraocular pressure on routine exam",
                "IOP 26 mmHg OD, 25 mmHg OS. Optic disc cupping, early superior arcuate field defect OD. Started latanoprost.",
                {"bp": "136/84"},
            ),
            (
                210,
                "follow_up",
                "Glaucoma follow-up",
                "IOP 19/18 on latanoprost; added timolol for target < 18 mmHg.",
                {},
            ),
            (
                30,
                "follow_up",
                "Glaucoma and retinal review",
                "IOP 16/17 at target. Mild NPDR both eyes, no macular oedema on OCT. Continue regimen; annual retinal screening.",
                {"bp": "132/80"},
            ),
        ],
        "reports": [
            (
                32,
                "OCT and tonometry report",
                [
                    ("IOP OD", "16", "mmHg", "10-21", ""),
                    ("IOP OS", "17", "mmHg", "10-21", ""),
                    ("Central subfield thickness", "268", "microns", "", ""),
                    ("HbA1c", "7.1", "%", "4.0-5.6", "H"),
                ],
                "Impression: IOP at target. Mild non-proliferative diabetic retinopathy without centre-involving macular oedema.",
            ),
        ],
    },
    {
        "mrn": "DEMO-1004",
        "first_name": "Maria",
        "last_name": "Gonzalez",
        "dob": date(1954, 1, 22),
        "sex": "female",
        "phone": "555-0104",
        "tags": ["cardiology", "high-risk"],
        "blood_group": "A-",
        "conditions": [
            ("Heart failure with reduced ejection fraction", "I50.22", "active", 500),
            ("Atrial fibrillation, permanent", "I48.21", "active", 700),
            ("Essential hypertension", "I10", "active", 5000),
        ],
        "meds": [
            ("Sacubitril/valsartan", "49/51 mg", "oral", "twice daily", "HFrEF", 400),
            ("Metoprolol succinate", "100 mg", "oral", "once daily", "HFrEF / rate control", 600),
            ("Apixaban", "5 mg", "oral", "twice daily", "Stroke prevention in AF", 700),
            ("Furosemide", "40 mg", "oral", "once daily", "Congestion", 500),
        ],
        "allergies": [("Sulfa drugs", "Angioedema", "severe")],
        "encounters": [
            (
                180,
                "inpatient",
                "Admission for decompensated heart failure",
                "IV diuresis, LVEF 30% on echo. Discharged on sacubitril/valsartan, metoprolol, apixaban, furosemide.",
                {"bp": "128/76", "hr": 96, "weight_kg": 61},
            ),
            (
                25,
                "outpatient",
                "Heart failure clinic review",
                "NYHA II, euvolaemic. Weight 58 kg. Creatinine 1.5. Discuss adding SGLT2 inhibitor and MRA; review apixaban dose criteria.",
                {"bp": "118/70", "hr": 72, "weight_kg": 58},
            ),
        ],
        "reports": [
            (
                182,
                "Cardiology labs and echo — admission",
                [
                    ("BNP", "1450", "pg/mL", "<100", "H"),
                    ("Creatinine", "1.4", "mg/dL", "0.5-1.1", "H"),
                    ("Potassium", "4.2", "mmol/L", "3.5-5.1", ""),
                    ("LVEF", "30", "%", "52-72", "L"),
                ],
                "Impression: HFrEF with volume overload.",
            ),
            (
                27,
                "Cardiology labs and echo — clinic",
                [
                    ("BNP", "620", "pg/mL", "<100", "H"),
                    ("Creatinine", "1.5", "mg/dL", "0.5-1.1", "H"),
                    ("Potassium", "4.6", "mmol/L", "3.5-5.1", ""),
                    ("LVEF", "35", "%", "52-72", "L"),
                ],
                "Impression: improving natriuretic peptide; LVEF 35%.",
            ),
        ],
        "wrong_patient_report": (
            10,
            "Outside lab result (faxed)",
            "Margaret Wallace",
            "EXT-55821",
            [("Hemoglobin", "9.2", "g/dL", "12.0-15.5", "L"), ("INR", "3.4", "", "2.0-3.0", "H")],
        ),
    },
    {
        "mrn": "DEMO-1005",
        "first_name": "Daniel",
        "last_name": "Okafor",
        "dob": date(1991, 11, 5),
        "sex": "male",
        "phone": "555-0105",
        "tags": ["respiratory"],
        "blood_group": "O-",
        "conditions": [
            ("Asthma, moderate persistent", "J45.40", "active", 4000),
            ("Allergic rhinitis", "J30.9", "active", 4000),
        ],
        "meds": [
            ("Budesonide/formoterol 160/4.5", "2 inhalations", "inhaled", "twice daily and as needed", "Asthma", 700),
            ("Cetirizine", "10 mg", "oral", "once daily", "Allergic rhinitis", 1500),
        ],
        "allergies": [("Aspirin", "Bronchospasm", "severe")],
        "encounters": [
            (
                60,
                "emergency",
                "Acute asthma exacerbation",
                "Wheeze, SpO2 93%, PEF 55% predicted. Nebulised salbutamol, oral prednisolone 5 days. Inhaler technique poor.",
                {"spo2": 93, "hr": 108},
            ),
            (
                40,
                "follow_up",
                "Post-exacerbation review",
                "Symptoms controlled. Re-taught inhaler technique. Spirometry ordered.",
                {"spo2": 98, "hr": 74},
            ),
        ],
        "reports": [
            (
                38,
                "Spirometry and blood count",
                [
                    ("FEV1", "2.9", "L", "3.6-4.8", "L"),
                    ("WBC", "7.2", "10^9/L", "4.0-11.0", ""),
                    ("Hemoglobin", "14.6", "g/dL", "13.5-17.5", ""),
                ],
                "Impression: obstructive pattern with 15% (430 mL) bronchodilator reversibility, consistent with asthma. Blood eosinophils 0.45 x10^9/L.",
            ),
        ],
    },
]


def _pdf(
    title: str,
    patient: tuple[str, str, date | None],
    report_date: date,
    rows,
    impression: str,
    facility="GMS Diagnostics Laboratory",
) -> bytes:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    y = 60
    page.insert_text((50, y), facility, fontsize=15, fontname="helv")
    y += 22
    page.insert_text((50, y), title, fontsize=12)
    y += 26
    name, mrn, dob = patient
    for line in (
        f"Patient name: {name}",
        f"MRN: {mrn}",
        f"Date of birth: {dob.isoformat() if dob else 'not stated'}",
        f"Report date: {report_date.isoformat()}",
    ):
        page.insert_text((50, y), line, fontsize=10)
        y += 15
    y += 12
    page.insert_text((50, y), "Test | Result | Unit | Reference range | Flag", fontsize=10)
    y += 16
    for r in rows:
        page.insert_text((50, y), " | ".join(r), fontsize=10)
        y += 15
    y += 14
    page.insert_textbox(pymupdf.Rect(50, y, 545, y + 120), impression, fontsize=10)
    page.insert_text(
        (50, 800), "Electronically verified. Synthetic demonstration document — not a real patient.", fontsize=8
    )
    data = doc.tobytes()
    doc.close()
    return data


def seed_users(db) -> User:
    admin = db.scalars(select(User).where(User.role == "admin")).first()
    for email, name, title, spec, role, pw in DEMO_USERS:
        if not db.scalars(select(User).where(User.email == email)).first():
            db.add(
                User(
                    email=email, full_name=name, title=title, specialty=spec, role=role, password_hash=hash_password(pw)
                )
            )
    db.commit()
    return db.scalars(select(User).where(User.email == "doctor@gms.local")).first() or admin


def seed_patients(db, clinician: User) -> list[str]:
    created_docs: list[str] = []
    for spec in PATIENTS:
        if db.scalars(select(Patient).where(Patient.mrn == spec["mrn"])).first():
            continue
        p = Patient(
            mrn=spec["mrn"],
            first_name=spec["first_name"],
            last_name=spec["last_name"],
            date_of_birth=spec["dob"],
            sex=spec["sex"],
            phone=spec["phone"],
            tags=spec["tags"],
            blood_group=spec.get("blood_group"),
            synthetic=True,
            created_by=clinician.id,
        )
        db.add(p)
        db.flush()
        for name, code, status, days in spec["conditions"]:
            db.add(Condition(patient_id=p.id, name=name, code=code, status=status, onset_date=ago(days).date()))
        for name, dose, route, freq, ind, days in spec["meds"]:
            db.add(
                Medication(
                    patient_id=p.id,
                    name=name,
                    dose=dose,
                    route=route,
                    frequency=freq,
                    indication=ind,
                    start_date=ago(days).date(),
                    status="active",
                )
            )
        for substance, reaction, severity in spec["allergies"]:
            db.add(Allergy(patient_id=p.id, substance=substance, reaction=reaction, severity=severity))
        for days, etype, reason, notes, vitals in spec["encounters"]:
            db.add(
                Encounter(
                    patient_id=p.id,
                    type=etype,
                    status="completed",
                    started_at=ago(days),
                    ended_at=ago(days) + timedelta(minutes=30),
                    reason=reason,
                    notes=notes,
                    vitals=vitals,
                    clinician_id=clinician.id,
                )
            )
        db.commit()
        ident = (p.full_name, p.mrn, p.date_of_birth)
        for days, title, rows, impression in spec["reports"]:
            d = ago(days).date()
            data = _pdf(title, ident, d, rows, impression)
            doc = documents.create(
                db,
                clinician,
                data=data,
                filename=f"{p.mrn}-{title.lower().replace(' ', '-').replace('—', '')}.pdf",
                declared_mime="application/pdf",
                scope="patient",
                patient=p,
                title=title,
                kind="lab_report",
                document_date=d,
            )
            created_docs.append(doc.id)
        if spec.get("wrong_patient_report"):
            days, title, other_name, other_mrn, rows = spec["wrong_patient_report"]
            d = ago(days).date()
            data = _pdf(
                title,
                (other_name, other_mrn, None),
                d,
                rows,
                "Result sent by external laboratory.",
                facility="Riverside Community Lab",
            )
            doc = documents.create(
                db,
                clinician,
                data=data,
                filename="outside-lab-fax.pdf",
                declared_mime="application/pdf",
                scope="patient",
                patient=p,
                title=title,
                kind="lab_report",
                document_date=d,
            )
            created_docs.append(doc.id)
    return created_docs


def seed_knowledge(db, admin: User) -> list[str]:
    created: list[str] = []
    if not PACKS.exists():
        return created
    for path in sorted(PACKS.glob("*/*")):
        if path.is_dir() or path.name.lower() == "readme.md":
            continue
        domain = path.parent.name.replace("-", "_")
        title = path.stem.replace("-", " ").replace("_", " ").title()
        if path.suffix == ".md":
            first = path.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
            title = first or title
        try:
            doc = documents.create(
                db,
                admin,
                data=path.read_bytes(),
                filename=path.name,
                declared_mime=None,
                scope="knowledge",
                title=title,
                kind="guideline",
                domain=domain,
                source_org="GMS demo knowledge pack",
                version="1.0",
            )
            created.append(doc.id)
        except AppError as exc:
            logger.info("Skipping %s: %s", path.name, exc.message)
    return created


async def _process_all(ids: list[str]) -> None:
    for i, doc_id in enumerate(ids, start=1):
        await documents.process(doc_id)
        db = SessionLocal()
        d = db.get(Document, doc_id)
        logger.info("[%d/%d] %s → %s%s", i, len(ids), d.title, d.status, f" ({d.error})" if d.error else "")
        db.close()


def main(argv: list[str]) -> int:
    configure_logging("INFO")
    from app.main import bootstrap, run_migrations

    get_settings().uploads_dir.mkdir(parents=True, exist_ok=True)
    run_migrations()
    bootstrap()
    cmd = argv[1] if len(argv) > 1 else "demo"
    db = SessionLocal()
    try:
        admin = db.scalars(select(User).where(User.role == "admin")).first()
        ids: list[str] = []
        if cmd == "demo":
            clinician = seed_users(db)
            ids += seed_knowledge(db, admin)
            ids += seed_patients(db, clinician)
        elif cmd == "knowledge":
            ids += seed_knowledge(db, admin)
        elif cmd == "use-mock-ai":
            from app.services import runtime_config

            url = argv[2] if len(argv) > 2 else "http://127.0.0.1:9100/v1"
            cfg = runtime_config.load(db)
            cfg = runtime_config.apply_section_update(
                cfg, "llm", {"provider": "openai", "base_url": url, "model": "mock-clinical-llm"}
            )
            cfg = runtime_config.apply_section_update(cfg, "vision", {"use_main_llm": True})
            cfg = runtime_config.apply_section_update(
                cfg, "embeddings", {"provider": "openai", "base_url": url, "model": "mock-embed"}
            )
            cfg = runtime_config.apply_section_update(
                cfg, "reranker", {"provider": "remote", "base_url": url, "model": "mock-rerank"}
            )
            runtime_config.save(db, cfg)
            print(f"All AI roles now use the mock server at {url}")
            return 0
        elif cmd == "reprocess":
            ids = [d.id for d in db.scalars(select(Document).where(Document.status.in_(["failed", "processing"])))]
        else:
            print(__doc__)
            return 2
    finally:
        db.close()
    logger.info("Processing %d documents…", len(ids))
    asyncio.run(_process_all(ids))
    from app.rag.vector_store import reset_clients

    reset_clients()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
