#!/usr/bin/env python
"""Seed synthetic ophthalmology demo patients (spec §88).

Three clearly fictional patients spanning the bundled ophthalmology knowledge base
domain (data/eye_conditions.json — cataract, glaucoma, diabetic retinopathy), each with
several months of encounter history so the Timeline/Overview/Conditions/Medications
tabs have real data to show. Report/lab-derived timeline events join once Phase 05/06
land; this seed only touches structured data that exists today.

Idempotent by MRN — an existing DEMO-* patient (and its records) is left untouched on
re-run, so this is safe to call from start-demo.bat every time.

Usage:
    python scripts/seed_demo_patients.py
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.allergy import Allergy, AllergySeverity  # noqa: E402
from app.models.condition import Condition, ConditionStatus  # noqa: E402
from app.models.encounter import Encounter, EncounterStatus, EncounterType  # noqa: E402
from app.models.medication import Medication  # noqa: E402
from app.models.patient import Patient, Sex  # noqa: E402
from app.models.user import User  # noqa: E402

NOW = datetime.now(UTC)


def _months_ago(n: int) -> datetime:
    return NOW - timedelta(days=30 * n)


def _encounter_number(mrn: str, seq: int) -> str:
    return f"{mrn}-ENC{seq:03d}"


def _seed_cataract_patient(db, created_by: str | None) -> None:
    patient = Patient(
        mrn="DEMO-1001",
        first_name="Margaret",
        last_name="Wallace",
        date_of_birth=date(1953, 4, 12),
        sex=Sex.FEMALE,
        phone="555-0101",
        synthetic=True,
    )
    db.add(patient)
    db.flush()

    e1 = Encounter(
        patient_id=patient.id,
        encounter_number=_encounter_number(patient.mrn, 1),
        encounter_type=EncounterType.OUTPATIENT,
        start_datetime=_months_ago(5),
        end_datetime=_months_ago(5) + timedelta(minutes=30),
        status=EncounterStatus.COMPLETED,
        chief_complaint="Gradual painless vision loss, worse at night; difficulty reading",
        clinician_note="Slit-lamp exam shows bilateral nuclear sclerotic cataract, more advanced OD. "
        "Visual acuity 20/50 OD, 20/40 OS. Discussed surgical options; patient prefers to "
        "monitor for now.",
        created_by=created_by,
    )
    e2 = Encounter(
        patient_id=patient.id,
        encounter_number=_encounter_number(patient.mrn, 2),
        encounter_type=EncounterType.OUTPATIENT,
        start_datetime=_months_ago(1),
        end_datetime=_months_ago(1) + timedelta(minutes=20),
        status=EncounterStatus.COMPLETED,
        chief_complaint="Follow-up — increased glare while driving at night",
        clinician_note="Visual acuity now 20/70 OD, 20/40 OS. Cataract now visually significant OD. "
        "Referred for cataract surgery evaluation, right eye first.",
        created_by=created_by,
    )
    db.add_all([e1, e2])
    db.flush()

    db.add_all(
        [
            Condition(
                patient_id=patient.id,
                encounter_id=e1.id,
                display="Cataract, bilateral (nuclear sclerotic)",
                status=ConditionStatus.ACTIVE,
                onset_date=_months_ago(5).date(),
                notes="More advanced in the right eye; surgical referral placed at most recent visit.",
            ),
            Condition(
                patient_id=patient.id,
                display="Presbyopia",
                status=ConditionStatus.ACTIVE,
                onset_date=date(2015, 1, 1),
            ),
        ]
    )
    db.add(
        Medication(
            patient_id=patient.id,
            encounter_id=e1.id,
            medication_name="Artificial tears (carboxymethylcellulose 0.5%)",
            dose="1 drop",
            route="ophthalmic",
            frequency="as needed",
            start_date=_months_ago(5).date(),
            active=True,
            source="clinician entered",
        )
    )
    # No allergy rows for this patient — deliberately left undocumented rather than
    # inventing "no known allergies" as a fact nobody actually confirmed (spec §2).


def _seed_glaucoma_patient(db, created_by: str | None) -> None:
    patient = Patient(
        mrn="DEMO-1002",
        first_name="Robert",
        last_name="Klein",
        date_of_birth=date(1958, 9, 3),
        sex=Sex.MALE,
        phone="555-0102",
        synthetic=True,
    )
    db.add(patient)
    db.flush()

    e1 = Encounter(
        patient_id=patient.id,
        encounter_number=_encounter_number(patient.mrn, 1),
        encounter_type=EncounterType.OUTPATIENT,
        start_datetime=_months_ago(10),
        end_datetime=_months_ago(10) + timedelta(minutes=40),
        status=EncounterStatus.COMPLETED,
        chief_complaint="Referred by optometrist for elevated intraocular pressure on routine exam",
        clinician_note="IOP 26 mmHg OD, 25 mmHg OS. Optic disc cupping consistent with early glaucomatous "
        "damage. Visual field testing shows early superior arcuate defect OD. Diagnosis: "
        "primary open-angle glaucoma. Starting topical therapy.",
        created_by=created_by,
    )
    e2 = Encounter(
        patient_id=patient.id,
        encounter_number=_encounter_number(patient.mrn, 2),
        encounter_type=EncounterType.OUTPATIENT,
        start_datetime=_months_ago(7),
        end_datetime=_months_ago(7) + timedelta(minutes=25),
        status=EncounterStatus.COMPLETED,
        chief_complaint="3-month glaucoma follow-up",
        clinician_note="IOP improved to 19 mmHg OD, 18 mmHg OS on latanoprost. Adding timolol for "
        "additional IOP control given target of <18 mmHg.",
        created_by=created_by,
    )
    e3 = Encounter(
        patient_id=patient.id,
        encounter_number=_encounter_number(patient.mrn, 3),
        encounter_type=EncounterType.OUTPATIENT,
        start_datetime=_months_ago(1),
        end_datetime=_months_ago(1) + timedelta(minutes=25),
        status=EncounterStatus.COMPLETED,
        chief_complaint="Routine glaucoma follow-up",
        clinician_note="IOP 16 mmHg OD, 17 mmHg OS — at target. Optic disc stable compared to prior exam. "
        "Continue current regimen.",
        created_by=created_by,
    )
    db.add_all([e1, e2, e3])
    db.flush()

    db.add(
        Condition(
            patient_id=patient.id,
            encounter_id=e1.id,
            display="Primary open-angle glaucoma, bilateral",
            status=ConditionStatus.ACTIVE,
            onset_date=_months_ago(10).date(),
            notes="IOP at target as of most recent follow-up; monitor visual fields annually.",
        )
    )
    db.add_all(
        [
            Medication(
                patient_id=patient.id,
                encounter_id=e1.id,
                medication_name="Latanoprost 0.005%",
                dose="1 drop",
                route="ophthalmic",
                frequency="nightly, both eyes",
                start_date=_months_ago(10).date(),
                active=True,
                source="clinician entered",
            ),
            Medication(
                patient_id=patient.id,
                encounter_id=e2.id,
                medication_name="Timolol 0.5%",
                dose="1 drop",
                route="ophthalmic",
                frequency="twice daily, both eyes",
                start_date=_months_ago(7).date(),
                active=True,
                source="clinician entered",
            ),
        ]
    )
    db.add(
        Allergy(
            patient_id=patient.id,
            substance="Sulfonamides (sulfa drugs)",
            reaction="Diffuse rash",
            severity=AllergySeverity.MODERATE,
            source="patient reported",
        )
    )


def _seed_diabetic_retinopathy_patient(db, created_by: str | None) -> None:
    patient = Patient(
        mrn="DEMO-1003",
        first_name="Elena",
        last_name="Novak",
        date_of_birth=date(1970, 11, 20),
        sex=Sex.FEMALE,
        phone="555-0103",
        synthetic=True,
    )
    db.add(patient)
    db.flush()

    e1 = Encounter(
        patient_id=patient.id,
        encounter_number=_encounter_number(patient.mrn, 1),
        encounter_type=EncounterType.OUTPATIENT,
        start_datetime=_months_ago(8),
        end_datetime=_months_ago(8) + timedelta(minutes=45),
        status=EncounterStatus.COMPLETED,
        chief_complaint="Annual diabetic eye exam — reports occasional floaters",
        clinician_note="17-year history of type 2 diabetes, HbA1c poorly controlled per PCP records. "
        "Dilated fundus exam shows scattered microaneurysms and dot-blot hemorrhages, "
        "moderate nonproliferative diabetic retinopathy, both eyes. No macular edema on OCT. "
        "Counseled on glycemic control; recheck in 3-4 months given moderate severity.",
        created_by=created_by,
    )
    e2 = Encounter(
        patient_id=patient.id,
        encounter_number=_encounter_number(patient.mrn, 2),
        encounter_type=EncounterType.OUTPATIENT,
        start_datetime=_months_ago(4),
        end_datetime=_months_ago(4) + timedelta(minutes=40),
        status=EncounterStatus.COMPLETED,
        chief_complaint="Follow-up diabetic retinopathy — new floaters, mild blur OD",
        clinician_note="Fundus exam shows progression with increased hemorrhage count OD; early "
        "non-central macular edema on OCT OD. Discussed anti-VEGF injection option; patient "
        "wants to try tighter glycemic control first with repeat OCT in 6-8 weeks.",
        created_by=created_by,
    )
    e3 = Encounter(
        patient_id=patient.id,
        encounter_number=_encounter_number(patient.mrn, 3),
        encounter_type=EncounterType.OUTPATIENT,
        start_datetime=_months_ago(1),
        end_datetime=None,
        status=EncounterStatus.ACTIVE,
        chief_complaint="Current visit — persistent blurring OD despite improved glucose control",
        clinician_note="Macular edema OD unchanged on repeat OCT. Discussing intravitreal anti-VEGF "
        "injection as next step given lack of improvement.",
        created_by=created_by,
    )
    db.add_all([e1, e2, e3])
    db.flush()

    db.add_all(
        [
            Condition(
                patient_id=patient.id,
                encounter_id=e1.id,
                display="Type 2 diabetes mellitus",
                status=ConditionStatus.ACTIVE,
                onset_date=date(2009, 3, 1),
                notes="Longstanding, historically poor glycemic control.",
            ),
            Condition(
                patient_id=patient.id,
                encounter_id=e1.id,
                display="Moderate nonproliferative diabetic retinopathy, bilateral",
                status=ConditionStatus.ACTIVE,
                onset_date=_months_ago(8).date(),
            ),
            Condition(
                patient_id=patient.id,
                encounter_id=e2.id,
                display="Diabetic macular edema, right eye (non-central)",
                status=ConditionStatus.ACTIVE,
                onset_date=_months_ago(4).date(),
                notes="Unchanged on most recent OCT; anti-VEGF injection under discussion.",
            ),
        ]
    )
    db.add(
        Medication(
            patient_id=patient.id,
            medication_name="Metformin",
            dose="1000",
            dose_unit="mg",
            route="oral",
            frequency="twice daily",
            start_date=date(2009, 4, 1),
            active=True,
            source="clinician entered",
        )
    )
    db.add(
        Allergy(
            patient_id=patient.id,
            substance="Penicillin",
            reaction="Anaphylaxis",
            severity=AllergySeverity.SEVERE,
            source="patient reported",
        )
    )


SEEDERS = {
    "DEMO-1001": ("Margaret Wallace - cataract", _seed_cataract_patient),
    "DEMO-1002": ("Robert Klein - glaucoma", _seed_glaucoma_patient),
    "DEMO-1003": ("Elena Novak - diabetic retinopathy", _seed_diabetic_retinopathy_patient),
}


def main() -> int:
    db = SessionLocal()
    try:
        doctor = db.scalar(select(User).where(User.email == "doctor@gms.local"))
        created_by = doctor.id if doctor else None
        if created_by is None:
            print("[warn] doctor@gms.local not found — run scripts/seed_demo.py first for a real "
                  "'created_by' on seeded encounters. Continuing with created_by=NULL.")

        for mrn, (label, seed_fn) in SEEDERS.items():
            if db.scalar(select(Patient.id).where(Patient.mrn == mrn)) is not None:
                print(f"[skip] {mrn} ({label}) already exists - left untouched")
                continue
            seed_fn(db, created_by)
            print(f"[created] {mrn} ({label})")

        db.commit()
    except OperationalError as exc:
        print(f"Database error - have you run migrations yet? (alembic upgrade head)\n{exc}")
        db.rollback()
        return 1
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
