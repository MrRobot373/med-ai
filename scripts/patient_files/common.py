"""Shared organisations, clinicians and document helpers for the patient files.
Every organisation and person here is fictional; addresses use real localities only
so that documents read naturally."""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path

import numpy as np
import render as R
from PIL import Image

ASSETS = Path(__file__).parent / "assets"
MANIFEST = json.loads((ASSETS / "manifest.json").read_text())

# ---- organisations --------------------------------------------------------------------------
SANVITA = R.Org(
    "Sanvita Diagnostics",
    "Pathology · Biochemistry · Molecular diagnostics",
    "Shop 4, Karve Road, Kothrud, Pune 411038",
    "+91 20 2546 1180",
    (0.07, 0.38, 0.55),
    "reports@sanvita.example",
    "SD",
)
PRAKRUTI = R.Org(
    "Prakruti Pathology Laboratory",
    "Clinical laboratory · Home sample collection",
    "2nd Floor, Thatte Nagar, College Road, Nashik 422005",
    "+91 253 231 7744",
    (0.47, 0.18, 0.43),
    "lab@prakruti.example",
    "PP",
)
AROGYAM = R.Org(
    "Arogyam Path Labs",
    "Quality diagnostics since 1998",
    "B-12, Lokhandwala Complex, Andheri West, Mumbai 400053",
    "+91 22 2636 9012",
    (0.16, 0.45, 0.25),
    "care@arogyam.example",
    "AP",
)
MEDISIGHT = R.Org(
    "Medisight Imaging & Diagnostics",
    "Digital X-ray · Ultrasound · CT · MRI",
    "Prabhat Road, Lane 7, Erandwane, Pune 411004",
    "+91 20 2567 3300",
    (0.11, 0.24, 0.47),
    "imaging@medisight.example",
    "MI",
)
SAHYOG = R.Org(
    "Sahyog Scan Centre",
    "Sonography · Doppler · Digital X-ray",
    "Near Mahamarg Bus Stand, Mumbai Naka, Nashik 422001",
    "+91 253 250 1188",
    (0.55, 0.27, 0.07),
    "scans@sahyog.example",
    "SS",
)
OJAS = R.Org(
    "Ojas Heart Clinic",
    "ECG · 2D Echo · TMT · Holter",
    "Ground Floor, Sai Plaza, Baner Road, Pune 411045",
    "+91 20 2729 4410",
    (0.70, 0.12, 0.17),
    "echo@ojasheart.example",
    "OH",
)
PANCHAVATI = R.Org(
    "Panchavati Care Hospital",
    "Multispeciality hospital · 24 x 7 emergency",
    "Peth Road, Panchavati, Nashik 422003",
    "+91 253 262 9000",
    (0.04, 0.42, 0.42),
    "ipd@panchavaticare.example",
    "PC",
)
VEDANT = R.Org(
    "Vedant Multispeciality Hospital",
    "Neurosciences · Cardiac care · Critical care",
    "Survey No. 41, Aundh-Baner Link Road, Pune 411007",
    "+91 20 6712 4000",
    (0.20, 0.25, 0.55),
    "discharge@vedanthospital.example",
    "VH",
)
GMS = R.Org(
    "GMS Health Clinic",
    "Internal medicine · Diabetes · Hypertension",
    "Office 3, Siddhi Towers, Paud Road, Pune 411038",
    "+91 20 2543 7788",
    (0.14, 0.42, 0.99),
    "clinic@gmshealth.example",
    "GMS",
)

CLINIC_SHRAVANI = R.Org(
    "Shravani Women's Clinic", "", "Bhandarkar Road, Deccan Gymkhana, Pune 411004", "+91 20 2565 1290", (0.62, 0.20, 0.40)
)
CLINIC_LITTLE = R.Org("Little Steps Child Clinic", "", "DP Road, Aundh, Pune 411007", "+91 20 2588 4421", (0.10, 0.50, 0.55))
CLINIC_NAVKAR = R.Org(
    "Navkar Ortho & Trauma Centre", "", "Sinhgad Road, Vadgaon Budruk, Pune 411041", "+91 20 2435 9060", (0.25, 0.30, 0.40)
)
CLINIC_BREATHE = R.Org("Breathe Easy Chest Clinic", "", "Senapati Bapat Road, Pune 411016", "+91 20 2565 8800", (0.05, 0.45, 0.60))
CLINIC_UROCARE = R.Org("UroCare Clinic", "", "Law College Road, Erandwane, Pune 411004", "+91 20 2546 0505", (0.30, 0.35, 0.15))
CLINIC_NTEP = R.Org("NTEP Treatment Unit, Kasba Peth", "", "Ward Office, Kasba Peth, Pune 411011", "+91 20 2445 0011", (0.30, 0.30, 0.30))
CLINIC_AASHA = R.Org("Aasha Gynaec & Maternity Clinic", "", "Kondhwa Main Road, Pune 411048", "+91 20 2683 3301", (0.55, 0.15, 0.35))

PATHOLOGISTS = {
    "SD": [("Dr. Shalini Kulkarni", "MD (Pathology), Consultant Pathologist"), ("Dr. Rahul Bhide", "MD (Biochemistry)")],
    "PP": [("Dr. Vaishali Thorat", "MD (Pathology)")],
    "AP": [("Dr. Kunal Mehta", "MD (Pathology), Lab Director")],
}
RADIOLOGISTS = {
    "MI": [("Dr. Prasad Gokhale", "MD (Radio-diagnosis), Consultant Radiologist")],
    "SS": [("Dr. Manisha Pagar", "DMRD, DNB (Radiology)")],
    "PC": [("Dr. Sanjay Wagh", "MD (Radiology)")],
    "VH": [("Dr. Rohini Apte", "MD, DNB (Radio-diagnosis), Neuroradiology")],
}
DR_RAO = "Dr. Ananya Rao"


@dataclass
class Doc:
    path: str  # relative to the patient folder
    title: str
    kind: str  # lab_report | imaging | ecg | discharge_summary | prescription | referral | clinical_note
    on: date
    make: Callable[[], bytes]
    pending: bool = False  # kept in "To upload" for a live demo, not loaded by the seed
    source: str | None = None  # key in assets/manifest.json for images taken from an open dataset


@dataclass
class Patient:
    folder_no: int
    uhid: str
    honorific: str
    first_name: str
    last_name: str
    dob: date
    sex: str
    phone: str
    address: str
    blood_group: str
    email: str | None = None
    tags: list[str] = field(default_factory=list)
    conditions: list[tuple] = field(default_factory=list)  # (name, code, since[, status])
    allergies: list[tuple] = field(default_factory=list)  # (substance, reaction, severity)
    outside_meds: list[tuple] = field(default_factory=list)  # (name, dose, frequency, indication, since)
    visits: list[dict] = field(default_factory=list)
    orders: list[tuple] = field(default_factory=list)  # (date, test, category, reason, visit_index|None)
    today: tuple | None = None  # (HH:MM, reason, status)
    notes: str = ""
    docs: list[Doc] = field(default_factory=list)
    summary: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def age_on(self, d: date) -> int:
        return d.year - self.dob.year - ((d.month, d.day) < (self.dob.month, self.dob.day))

    def person(self, on: date) -> R.Person:
        a = self.age_on(on)
        age = f"{a} Y" if a >= 2 else f"{(on - self.dob).days // 30} M"
        return R.Person(f"{self.honorific} {self.full_name}", age, self.sex.title(), self.uhid, self.phone, self.dob)

    def sex_age(self, on: date) -> str:
        return f"{'M' if self.sex == 'male' else 'F'}/{self.age_on(on)}Y"


def at(d: date, hh: int = 9, mm: int = 0) -> datetime:
    return datetime.combine(d, time(hh, mm))


# ---- document builders ------------------------------------------------------------------------


def lab(
    p: Patient,
    on: date,
    org: R.Org,
    title: str,
    sections,
    *,
    lab_no: str,
    ref_by: str = DR_RAO,
    notes=None,
    sample: str = "Blood",
    folder: str = "Lab reports",
    hour: int = 8,
    printed_for: R.Person | None = None,
) -> Doc:
    def make() -> bytes:
        return R.lab_report(
            org,
            printed_for or p.person(on),
            collected=at(on, hour, 15),
            reported=at(on, min(hour + 6, 19), 40),
            ref_by=ref_by,
            lab_no=lab_no,
            sections=sections,
            pathologists=PATHOLOGISTS[org.initials],
            notes=notes,
            sample=sample,
        )

    short = org.name.split()[0]
    return Doc(f"{folder}/{on.isoformat()} {title} - {short}.pdf", title, "lab_report", on, make)


def asset_bytes(key: str) -> bytes:
    return (ASSETS / MANIFEST[key]["file"]).read_bytes()


def thumb(img: bytes, side: int = 600) -> bytes:
    im = Image.open(io.BytesIO(img)).convert("L")
    im.thumbnail((side, side))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def radiograph(
    p: Patient, on: date, org: R.Org, asset: str, study: str, *, extra=None, folder="Radiology", name: str | None = None, hour: int = 11
) -> tuple[Doc, Callable[[], bytes]]:
    def make() -> bytes:
        return R.burn_in(
            ASSETS / MANIFEST[asset]["file"],
            institution=org.name,
            name=f"{p.last_name} {p.first_name}",
            sex_age=p.sex_age(on),
            uhid=p.uhid,
            when=at(on, hour, 20),
            study=study,
            extra=extra,
        )

    fname = name or study.title()
    return Doc(f"{folder}/{on.isoformat()} {fname}.jpg", fname, "imaging", on, make, source=asset), make


def imaging(
    p: Patient,
    on: date,
    org: R.Org,
    study: str,
    sections,
    impression,
    *,
    accession: str,
    modality: str,
    ref_by: str = DR_RAO,
    key_image: Callable[[], bytes] | None = None,
    folder="Radiology",
    kind: str = "imaging",
    doctors=None,
    pending: bool = False,
    hour: int = 11,
) -> Doc:
    def make() -> bytes:
        return R.imaging_report(
            org,
            p.person(on),
            when=at(on, hour, 30),
            ref_by=ref_by,
            study=study,
            accession=accession,
            sections=sections,
            impression=impression,
            doctors=doctors or RADIOLOGISTS.get(org.initials, [("Dr. Prasad Gokhale", "MD (Radio-diagnosis)")]),
            key_image=thumb(key_image()) if key_image else None,
            modality=modality,
        )

    return Doc(f"{folder}/{on.isoformat()} {study} report - {org.name.split()[0]}.pdf", f"{study} report", kind, on, make, pending=pending)


def prescription(
    p: Patient,
    on: date,
    clinic: R.Org,
    doctor,
    *,
    vitals,
    complaints,
    findings,
    diagnosis,
    medicines,
    advice,
    follow_up,
    investigations=None,
    title=None,
) -> Doc:
    def make() -> bytes:
        return R.opd_prescription(
            clinic,
            doctor,
            p.person(on),
            when=at(on, 18, 5),
            vitals=vitals,
            complaints=complaints,
            findings=findings,
            diagnosis=diagnosis,
            medicines=medicines,
            advice=advice,
            follow_up=follow_up,
            investigations=investigations,
        )

    t = title or f"Prescription - {doctor[0]}"
    return Doc(f"Prescriptions/{on.isoformat()} {t}.pdf", t, "prescription", on, make)


def discharge(p: Patient, admitted: datetime, discharged: datetime, org: R.Org, **kw) -> Doc:
    def make() -> bytes:
        return R.discharge_summary(org, p.person(discharged.date()), admitted=admitted, discharged=discharged, **kw)

    return Doc(
        f"Hospital/{discharged.date().isoformat()} Discharge summary - {org.name.split()[0]}.pdf",
        "Discharge summary",
        "discharge_summary",
        discharged.date(),
        make,
    )


def dicom(
    p: Patient,
    on: date,
    pixels: np.ndarray,
    *,
    modality,
    study,
    series,
    body_part,
    window,
    org: R.Org,
    spacing=(0.5, 0.5),
    thickness=None,
    intercept=0.0,
    accession="",
    label: str,
    folder="Radiology",
    source: str,
) -> Doc:
    def make() -> bytes:
        return R.to_dicom(
            pixels,
            modality=modality,
            name=p.full_name,
            uhid=p.uhid,
            dob=p.dob,
            sex=p.sex,
            when=at(on, 12, 5),
            institution=org.name,
            study=study,
            series=series,
            body_part=body_part,
            window=window,
            spacing=spacing,
            thickness=thickness,
            intercept=intercept,
            referring=DR_RAO,
            accession=accession,
        )

    return Doc(f"{folder}/{on.isoformat()} {label}.dcm", label, "imaging", on, make, source=source)


def gray(asset: str) -> np.ndarray:
    return np.asarray(Image.open(ASSETS / MANIFEST[asset]["file"]).convert("L"), dtype=np.uint8)


def ecg(p: Patient, on: date, record: str, interpretation, org: R.Org = OJAS, ref_by: str = DR_RAO, hour=10) -> Doc:
    def make() -> bytes:
        return R.ecg_printout(
            ASSETS / f"ecg_{record}.dat",
            institution=f"{org.name}, {org.address}",
            name=f"{p.last_name} {p.first_name}",
            sex_age=p.sex_age(on),
            uhid=p.uhid,
            when=at(on, hour, 12),
            interpretation=interpretation,
            referring=ref_by,
        )

    return Doc(
        f"ECG & cardiology/{on.isoformat()} ECG 12-lead - {org.name.split()[0]}.jpg", "ECG 12-lead", "ecg", on, make, source=f"ecg_{record}"
    )


def clinic_letter(
    p: Patient,
    on: date,
    org: R.Org,
    title: str,
    sections,
    impression,
    doctors,
    *,
    folder="Letters & referrals",
    ref_by=DR_RAO,
    kind="referral",
) -> Doc:
    def make() -> bytes:
        return R.imaging_report(
            org,
            p.person(on),
            when=at(on, 17, 0),
            ref_by=ref_by,
            study=title,
            accession="-",
            sections=sections,
            impression=impression,
            doctors=doctors,
            modality="Consultation",
        )

    return Doc(f"{folder}/{on.isoformat()} {title} - {org.name.split()[0]}.pdf", title, kind, on, make)


def still(
    p: Patient,
    on: date,
    asset: str,
    *,
    institution: str,
    study: str,
    extra: list[str],
    path: str,
    title: str,
    hour: int = 11,
    minute: int = 40,
) -> Doc:
    """An ultrasound/radiograph frame exported with its corner annotations."""

    def make() -> bytes:
        return R.burn_in(
            ASSETS / MANIFEST[asset]["file"],
            institution=institution,
            name=f"{p.last_name} {p.first_name}",
            sex_age=p.sex_age(on),
            uhid=p.uhid,
            when=at(on, hour, minute),
            study=study,
            extra=extra,
        )

    return Doc(path, title, "imaging", on, make, source=asset)
