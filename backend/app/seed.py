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


def _report_pdf(
    title: str, patient: tuple[str, str, date | None], report_date: date, sections: list[tuple[str, str]], facility: str
) -> bytes:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 60), facility, fontsize=15)
    page.insert_text((50, 82), title, fontsize=12)
    y = 108
    name, mrn, dob = patient
    for line in (
        f"Patient name: {name}",
        f"MRN: {mrn}",
        f"Date of birth: {dob.isoformat() if dob else 'not stated'}",
        f"Report date: {report_date.isoformat()}",
    ):
        page.insert_text((50, y), line, fontsize=10)
        y += 15
    y += 10
    for heading, body in sections:
        page.insert_text((50, y), heading.upper(), fontsize=10)
        y += 6
        rect = pymupdf.Rect(50, y, 545, y + 140)
        page.insert_textbox(rect, body, fontsize=10)
        y += 18 + 13 * (len(body) // 85 + body.count("\n") + 1)
    page.insert_text((50, 800), "Synthetic demonstration document — not a real patient.", fontsize=8)
    data = doc.tobytes()
    doc.close()
    return data


def _ecg_png(name: str, mrn: str, when: date) -> bytes:
    """Synthetic lead-II rhythm strip: irregularly irregular narrow-complex rhythm without
    P waves (atrial fibrillation). Clearly labelled as a demo tracing."""
    import io
    import math
    import random

    from PIL import Image, ImageDraw

    rnd = random.Random(1004)
    w, h, px_mm = 1800, 560, 7
    img = Image.new("RGB", (w, h), (255, 250, 250))
    d = ImageDraw.Draw(img)
    for x in range(0, w, px_mm):
        d.line([(x, 70), (x, h)], fill=(250, 214, 214) if x % (px_mm * 5) else (238, 160, 160), width=1)
    for y in range(70, h, px_mm):
        d.line([(0, y), (w, y)], fill=(250, 214, 214) if (y - 70) % (px_mm * 5) else (238, 160, 160), width=1)
    d.rectangle([(0, 0), (w, 66)], fill=(255, 255, 255))
    d.text((20, 14), f"{name}   MRN {mrn}   {when.isoformat()}   Lead II   25 mm/s   10 mm/mV", fill=(20, 30, 60))
    d.text(
        (20, 38), "SYNTHETIC DEMO TRACING - irregularly irregular rhythm, no discernible P waves", fill=(170, 40, 40)
    )
    base, mv, sec = 330, px_mm * 10, px_mm * 25
    pts, t = [], 0.0
    beats, tb = [], 0.25
    while tb < w / sec:
        beats.append(tb)
        tb += rnd.uniform(0.45, 1.05)
    while t * sec < w:
        v = 0.04 * math.sin(2 * math.pi * 6.3 * t) + 0.03 * math.sin(2 * math.pi * 8.9 * t + 1)  # f-waves
        for b in beats:
            dt = t - b
            v += (
                -0.12 * math.exp(-(((dt + 0.02) / 0.008) ** 2))
                + 1.25 * math.exp(-((dt / 0.011) ** 2))
                - 0.28 * math.exp(-(((dt - 0.025) / 0.01) ** 2))
            )
            v += 0.25 * math.exp(-(((dt - 0.26) / 0.05) ** 2))  # T wave
        pts.append((t * sec, base - v * mv))
        t += 1 / 500
    d.line(pts, fill=(15, 20, 35), width=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _ct_phantom_dicom(name: str, mrn: str, when: date) -> bytes:
    """Shepp–Logan head phantom (the standard synthetic CT test image) as a DICOM file."""
    import io

    import numpy as np
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid

    n = 512
    y, x = np.mgrid[-1 : 1 : n * 1j, -1 : 1 : n * 1j]
    img = np.zeros((n, n), dtype=np.float32)
    # (intensity, a, b, x0, y0, phi-degrees) — modified Shepp-Logan, scaled to Hounsfield-like units
    for val, a, b, x0, y0, phi in [
        (1000, 0.69, 0.92, 0, 0, 0),
        (-800, 0.6624, 0.874, 0, -0.0184, 0),
        (-200, 0.11, 0.31, 0.22, 0, -18),
        (-200, 0.16, 0.41, -0.22, 0, 18),
        (100, 0.21, 0.25, 0, 0.35, 0),
        (100, 0.046, 0.046, 0, 0.1, 0),
        (100, 0.046, 0.046, 0, -0.1, 0),
        (100, 0.046, 0.023, -0.08, -0.605, 0),
        (100, 0.023, 0.023, 0, -0.606, 0),
        (100, 0.023, 0.046, 0.06, -0.605, 0),
    ]:
        t = np.deg2rad(phi)
        xr, yr = (x - x0) * np.cos(t) + (y - y0) * np.sin(t), -(x - x0) * np.sin(t) + (y - y0) * np.cos(t)
        img[(xr / a) ** 2 + (yr / b) ** 2 <= 1] += val
    pixels = np.flipud(np.clip(img + 24, 0, 4095)).astype(np.uint16)
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = CTImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID, ds.SOPInstanceUID = CTImageStorage, meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID, ds.SeriesInstanceUID = generate_uid(), generate_uid()
    last, first = name.split()[-1], name.split()[0]
    ds.PatientName, ds.PatientID = f"{last}^{first}", mrn
    ds.Modality, ds.BodyPartExamined = "CT", "HEAD"
    ds.StudyDescription, ds.SeriesDescription = "CT HEAD (SYNTHETIC TEST PHANTOM)", "Axial 5 mm"
    ds.StudyDate = when.strftime("%Y%m%d")
    ds.InstitutionName = "GMS Imaging (demo)"
    ds.ImageComments = "Shepp-Logan phantom - synthetic test image, not a patient scan"
    ds.Rows = ds.Columns = n
    ds.SamplesPerPixel, ds.PhotometricInterpretation = 1, "MONOCHROME2"
    ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 16, 12, 11, 0
    ds.WindowCenter, ds.WindowWidth = 240, 520
    ds.SliceThickness, ds.PixelSpacing = 5, [0.45, 0.45]
    ds.PixelData = pixels.tobytes()
    buf = io.BytesIO()
    ds.save_as(buf, enforce_file_format=True)
    return buf.getvalue()


IMAGING = {
    "DEMO-1001": [
        (
            "pdf",
            12,
            "Renal ultrasound report",
            [
                (
                    "Clinical indication",
                    "Declining eGFR and albuminuria in type 2 diabetes. Assess renal size and exclude obstruction.",
                ),
                (
                    "Findings",
                    "Right kidney 10.1 cm, left kidney 10.4 cm. Mildly increased cortical echogenicity bilaterally with preserved corticomedullary differentiation. No hydronephrosis. No calculi. No focal lesion. Bladder unremarkable.",
                ),
                (
                    "Impression",
                    "Mild bilateral increase in cortical echogenicity, consistent with medical renal disease. No obstruction.",
                ),
            ],
        )
    ],
    "DEMO-1004": [
        ("ecg", 25, "ECG — lead II rhythm strip", None),
        (
            "pdf",
            26,
            "Echocardiogram report",
            [
                ("Indication", "Heart failure with reduced ejection fraction — follow-up of LV function on therapy."),
                (
                    "Findings",
                    "Dilated left ventricle with global hypokinesis. Biplane LVEF 35%. Moderate functional mitral regurgitation. Left atrium severely dilated. Rhythm atrial fibrillation during study. Estimated RVSP 38 mmHg.",
                ),
                (
                    "Impression",
                    "HFrEF with LVEF 35% (previously 30%). Moderate functional MR. Severe left atrial dilatation.",
                ),
            ],
        ),
    ],
    "DEMO-1003": [("dicom", 40, "CT head — synthetic phantom", None)],
}


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
        for kind, days, title, sections in IMAGING.get(p.mrn, []):
            d = ago(days).date()
            if kind == "pdf":
                data, fname, mime = (
                    _report_pdf(title, ident, d, sections, "GMS Imaging Department"),
                    f"{p.mrn}-{days}.pdf",
                    "application/pdf",
                )
            elif kind == "ecg":
                data, fname, mime = _ecg_png(p.full_name, p.mrn, d), f"{p.mrn}-ecg.png", "image/png"
            else:
                data, fname, mime = (
                    _ct_phantom_dicom(p.full_name, p.mrn, d),
                    f"{p.mrn}-ct-head.dcm",
                    "application/dicom",
                )
            doc = documents.create(
                db,
                clinician,
                data=data,
                filename=fname,
                declared_mime=mime,
                scope="patient",
                patient=p,
                title=title,
                kind="ecg" if kind == "ecg" else "imaging",
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
