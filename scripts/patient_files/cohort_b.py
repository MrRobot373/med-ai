"""Patients 6-10."""

from __future__ import annotations

from datetime import date, datetime

from common import (
    CLINIC_LITTLE,
    CLINIC_NAVKAR,
    MEDISIGHT,
    SANVITA,
    VEDANT,
    Patient,
    clinic_letter,
    dicom,
    discharge,
    gray,
    imaging,
    lab,
    prescription,
    radiograph,
    still,
)

D = date


def aarav() -> Patient:
    p = Patient(
        6,
        "LCM-10236",
        "Master",
        "Aarav",
        "Kulkarni",
        D(2022, 3, 12),
        "male",
        "+91 98500 72146",
        "Flat 304, Ganga Kingston, NIBM Road, Pune 411048",
        "A+",
        tags=["paediatric"],
        summary="4-year-old (16 kg) treated for right-sided pneumonia this week by his paediatrician; brought by father for a second opinion "
        "on fever that is settling.",
    )
    p.conditions = [("Community-acquired pneumonia", "J18.9", D(2026, 10, 20))]
    p.allergies = []
    p.outside_meds = [
        ("Augmentin Duo", "5 ml", "BD", "Pneumonia", D(2026, 10, 20)),
        ("Calpol 250/5 mL", "5 ml", "SOS", "Fever", D(2026, 10, 20)),
    ]
    p.visits = [
        {
            "date": D(2026, 10, 22),
            "reason": "Fever and cough — second opinion",
            "history": "Fever for 5 days, cough, fast breathing on day 3. Started on co-amoxiclav on 20 Oct. Fever spikes now 2 per day, eating better.",
            "examination": "Alert, playful. RR 32/min. Crepts right base. No chest indrawing.",
            "vitals": {"weight_kg": 16, "temp_f": 99.8, "hr": 118, "spo2": 97},
            "diagnoses": ["Community-acquired pneumonia"],
            "assessment": "Responding to oral co-amoxiclav. No danger signs.",
            "plan": "Continue antibiotic to complete 7 days. Paracetamol by weight. Review in 48 h or earlier if breathing fast.",
            "rx": None,
        }
    ]
    xr, xr_img = radiograph(p, D(2026, 10, 20), MEDISIGHT, "cxr_paediatric_pneumonia", "Chest X-ray AP", extra=["AP SUPINE", "PAEDIATRIC"])
    p.docs = [
        xr,
        imaging(
            p,
            D(2026, 10, 20),
            MEDISIGHT,
            "X-ray Chest AP View",
            [
                ("Clinical details", "4-year-old with fever 3 days, cough and fast breathing."),
                (
                    "Findings",
                    "Patchy air-space opacities in the right mid and lower zones with peribronchial thickening. Left lung clear. "
                    "Cardiothymic silhouette normal. No pleural effusion. No pneumothorax.",
                ),
            ],
            ["Right-sided bronchopneumonia."],
            accession="MI-XR-26-10205",
            modality="Digital radiography (DR)",
            key_image=xr_img,
            ref_by="Dr. Aniket Pawar",
        ),
        lab(
            p,
            D(2026, 10, 20),
            SANVITA,
            "CBC and CRP",
            [
                (
                    "Haematology",
                    [
                        ("Haemoglobin", "11.4", "g/dL", "11.5 - 14.5"),
                        ("Total Leucocyte Count", "18.2", "10^3/µL", "5.0 - 15.5"),
                        ("Platelet count", "402", "10^3/µL", "150 - 450"),
                    ],
                ),
                ("Inflammation", [("CRP", "58", "mg/L", "< 6", "Turbidimetry")]),
            ],
            lab_no="SD/26/102041",
            ref_by="Dr. Aniket Pawar",
            notes=["Neutrophilia (74 %) with raised CRP."],
        ),
        prescription(
            p,
            D(2026, 10, 20),
            CLINIC_LITTLE,
            ("Dr. Aniket Pawar", "MD (Paediatrics), DCH", "Consultant Paediatrician"),
            vitals="Weight 16 kg · Temp 102.2°F · RR 44/min · SpO2 95 %",
            complaints="Fever 3 days, cough, fast breathing since today",
            findings="Crepts right base, no chest indrawing, no danger signs",
            diagnosis="Right-sided pneumonia (non-severe)",
            medicines=[
                ("Syp. Augmentin Duo (400/57 per 5 mL)", "5 mL", "Twice daily", "7 days"),
                ("Syp. Calpol 250 (250 mg/5 mL)", "3.5 mL", "Every 6 hours if fever > 100°F", "3 days"),
                ("Nasal saline drops", "2 drops each nostril", "Three times daily", "5 days"),
            ],
            advice=["Plenty of fluids", "Come back immediately if breathing is fast, child is drowsy or not drinking"],
            follow_up="After 48 hours",
            investigations=["CBC, CRP", "Chest X-ray AP"],
        ),
    ]
    return p


def meenakshi() -> Patient:
    p = Patient(
        7,
        "LCM-10237",
        "Mrs.",
        "Meenakshi",
        "Iyer",
        D(1979, 11, 23),
        "female",
        "+91 98903 55120",
        "17, Shree Krupa, Tilak Road, Sadashiv Peth, Pune 411030",
        "B-",
        tags=["breast"],
        summary="46-year-old bank manager with hypertension who found a lump in the left breast; ultrasound BI-RADS 3. Referred to a breast surgeon.",
    )
    p.conditions = [("Essential hypertension", "I10", D(2021, 4, 1)), ("Left breast lump — BI-RADS 3", "N63.20", D(2026, 9, 26))]
    p.allergies = [("Codeine", "Severe vomiting", "mild")]
    p.visits = [
        {
            "date": D(2026, 9, 26),
            "reason": "Lump in the left breast",
            "history": "Noticed a painless lump in the left breast 2 weeks ago while bathing. No nipple discharge. Mother had breast cancer at 62.",
            "examination": "2 x 2 cm firm, mobile, non-tender lump, left upper outer quadrant. No skin change. No axillary nodes.",
            "vitals": {"bp": "142/88", "hr": 78, "weight_kg": 68},
            "diagnoses": ["Left breast lump"],
            "assessment": "Likely benign (fibroadenoma) but family history — needs imaging.",
            "plan": "Ultrasound breasts. Mammography. Surgical opinion.",
            "rx": {
                "items": [("Amlong 5", "1 tab", "OD", 90, "Morning")],
                "advice": "Continue BP medicine. Reduce salt.",
                "follow_up_days": 7,
                "chronic": True,
            },
        }
    ]
    p.orders = [(D(2026, 9, 26), "USG both breasts", "radiology", "Left breast lump, family history of breast cancer — characterise", 0)]
    p.docs = [
        still(
            p,
            D(2026, 9, 28),
            "us_breast_benign",
            institution="Medisight Imaging & Diagnostics",
            study="USG Breast - Left",
            extra=["L UOQ 2 o'clock, 4 cm FN", "Linear L12-4"],
            path="Radiology/2026-09-28 USG left breast - lesion image.jpg",
            title="USG left breast — lesion image",
        ),
        imaging(
            p,
            D(2026, 9, 28),
            MEDISIGHT,
            "USG Both Breasts",
            [
                ("Clinical details", "Palpable lump, left breast. Mother: breast cancer at 62."),
                (
                    "Left breast",
                    "At 2 o'clock, 4 cm from the nipple: a well-circumscribed oval hypoechoic lesion measuring 21 x 13 mm, parallel to the skin, "
                    "with circumscribed margins and posterior acoustic enhancement. No internal vascularity on Doppler. No calcification.",
                ),
                ("Right breast", "Normal fibroglandular parenchyma. No focal lesion."),
                ("Axillae", "Bilateral axillary nodes with preserved fatty hilum (largest 8 mm), likely reactive."),
            ],
            [
                "Left breast 2 o'clock: oval circumscribed hypoechoic lesion, 21 x 13 mm — likely fibroadenoma. BI-RADS 3 (probably benign).",
                "Short-interval follow-up ultrasound in 6 months, or tissue sampling if clinically indicated given family history.",
            ],
            accession="MI-US-26-09281",
            modality="Ultrasound (high-frequency linear)",
        ),
        lab(
            p,
            D(2026, 9, 26),
            SANVITA,
            "CBC, kidney function and TSH",
            [
                (
                    "Haematology",
                    [("Haemoglobin", "12.6", "g/dL", "12.0 - 15.0"), ("Total Leucocyte Count", "6.4", "10^3/µL", "4.0 - 11.0")],
                ),
                (
                    "Biochemistry",
                    [
                        ("Serum Creatinine", "0.78", "mg/dL", "0.50 - 1.10"),
                        ("Sodium", "140", "mmol/L", "135 - 145"),
                        ("Potassium", "4.1", "mmol/L", "3.5 - 5.1"),
                    ],
                ),
                ("Thyroid", [("TSH", "2.2", "µIU/mL", "0.40 - 4.00")]),
            ],
            lab_no="SD/26/092662",
        ),
        clinic_letter(
            p,
            D(2026, 9, 30),
            VEDANT,
            "Breast surgery opinion",
            [
                ("History", "46-year-old with a 2 cm left breast lump; first-degree relative with breast cancer."),
                ("Examination", "Firm mobile lump, left upper outer quadrant, no skin or nipple change, axilla clear."),
                (
                    "Plan",
                    "Ultrasound-guided core biopsy recommended in view of family history (patient preference). Mammography both breasts before biopsy.",
                ),
            ],
            [
                "Clinically and radiologically benign-appearing lesion (BI-RADS 3).",
                "Core needle biopsy and bilateral mammography scheduled.",
            ],
            [("Dr. Smita Patwardhan", "MS, MCh (Surgical Oncology), Breast Surgeon")],
        ),
    ]
    return p


def kavita() -> Patient:
    p = Patient(
        8,
        "LCM-10238",
        "Mrs.",
        "Kavita",
        "Joshi",
        D(1965, 1, 30),
        "female",
        "+91 94230 17788",
        "Row House 5, Swapnashilp Society, Kothrud, Pune 411038",
        "AB+",
        tags=["diabetes", "ckd", "high-risk"],
        summary="61-year-old with long-standing diabetes and diabetic kidney disease. eGFR has fallen from 46 to 36 over a year; "
        "still on metformin 1 g twice daily. Today: diabetes and kidney review.",
    )
    p.conditions = [
        ("Type 2 diabetes mellitus", "E11.22", D(2008, 6, 1)),
        ("Diabetic nephropathy — CKD stage 3b", "N18.32", D(2024, 11, 1)),
        ("Essential hypertension", "I10", D(2012, 3, 1)),
        ("Non-proliferative diabetic retinopathy", "E11.329", D(2025, 2, 1)),
        ("Dyslipidaemia", "E78.5", D(2015, 1, 1)),
    ]
    p.allergies = []
    p.visits = [
        {
            "date": D(2026, 4, 28),
            "reason": "Diabetes and kidney review",
            "history": "No hypoglycaemia. Mild ankle swelling in the evenings. Eye check done in Feb — mild NPDR.",
            "examination": "Trace pedal oedema. Fundus: done by ophthalmologist.",
            "vitals": {"bp": "148/88", "hr": 80, "weight_kg": 71},
            "diagnoses": ["Type 2 diabetes mellitus", "Diabetic nephropathy — CKD stage 3b"],
            "assessment": "HbA1c 8.4 %. eGFR 41. Albuminuria. BP above target.",
            "plan": "Continue. Needs SGLT2 inhibitor — patient to decide. Repeat KFT and UACR in 6 months.",
            "rx": {
                "items": [
                    ("Glycomet 1000", "1 tab", "BD", 180, "After meals"),
                    ("Amaryl 2", "1 tab", "OD", 180, "Before breakfast"),
                    ("Telma 40", "1 tab", "OD", 180, "Morning"),
                    ("Atorva 20", "1 tab", "HS", 180, None),
                ],
                "advice": "Diabetic, low-salt diet. Protein moderation.",
                "follow_up_days": 180,
                "chronic": True,
            },
        }
    ]
    p.orders = [(D(2026, 10, 10), "KFT, UACR and HbA1c", "lab", "Six-monthly kidney and diabetes monitoring", None)]
    p.today = ("11:30", "Diabetes and kidney review", "expected")

    def kft(on, cr, egfr_note, urea, k, labno, hba1c=None, uacr=None, extra=None):
        rows = [
            ("Serum Creatinine", cr, "mg/dL", "0.50 - 1.10", "Jaffe kinetic"),
            ("Blood Urea Nitrogen", urea, "mg/dL", "7 - 20"),
            ("Sodium", "138", "mmol/L", "135 - 145", "ISE"),
            ("Potassium", k, "mmol/L", "3.5 - 5.1", "ISE"),
        ]
        secs = [("Kidney function", rows)]
        if uacr:
            secs.append(("Urine", [("Urine albumin/creatinine ratio", uacr, "mg/g", "< 30")]))
        if hba1c:
            secs.append(("Diabetes", [("HbA1c", hba1c, "%", "4.0 - 5.6", "HPLC"), ("Fasting glucose", extra or "168", "mg/dL", "70 - 99")]))
        return lab(p, on, SANVITA, "Kidney function test" + (", UACR and HbA1c" if hba1c else ""), secs, lab_no=labno, notes=[egfr_note])

    p.docs = [
        kft(
            D(2025, 10, 15), "1.30", "eGFR by CKD-EPI 2021: 46 mL/min/1.73 m² (G3a).", "24", "4.6", "SD/25/101522", hba1c="8.0", uacr="212"
        ),
        kft(
            D(2026, 4, 20),
            "1.45",
            "eGFR by CKD-EPI 2021: 41 mL/min/1.73 m² (G3b).",
            "27",
            "4.8",
            "SD/26/042033",
            hba1c="8.4",
            uacr="268",
            extra="174",
        ),
        kft(
            D(2026, 10, 12),
            "1.62",
            "eGFR by CKD-EPI 2021: 36 mL/min/1.73 m² (G3b). Declining trend over 12 months.",
            "31",
            "5.2",
            "SD/26/101218",
            hba1c="8.6",
            uacr="320",
            extra="181",
        ),
        imaging(
            p,
            D(2026, 4, 25),
            MEDISIGHT,
            "USG KUB",
            [
                ("Clinical details", "Diabetic kidney disease, declining eGFR."),
                (
                    "Kidneys",
                    "Right kidney 9.2 cm, left kidney 9.4 cm with cortical thickness 0.9 cm bilaterally. Increased cortical echogenicity (grade II) "
                    "with reduced corticomedullary differentiation. No calculus, no hydronephrosis, no mass.",
                ),
                ("Bladder", "Well distended, normal wall. Post-void residue 20 mL."),
            ],
            ["Bilateral grade II medical renal disease with mildly small kidneys.", "No obstructive uropathy."],
            accession="MI-US-26-04251",
            modality="Ultrasound",
        ),
        clinic_letter(
            p,
            D(2026, 2, 11),
            VEDANT,
            "Diabetic retinopathy screening",
            [
                (
                    "Findings",
                    "Visual acuity 6/9 both eyes. Fundus: scattered microaneurysms and dot haemorrhages both eyes, no neovascularisation. No macular oedema on OCT.",
                ),
                ("Advice", "Strict sugar and BP control. Repeat fundus examination in 6 months."),
            ],
            ["Moderate non-proliferative diabetic retinopathy, both eyes, without macular oedema."],
            [("Dr. Varsha Lele", "MS (Ophthalmology), Retina Consultant")],
            kind="clinical_note",
        ),
    ]
    return p


def imran() -> Patient:
    p = Patient(
        9,
        "LCM-10239",
        "Mr.",
        "Imran",
        "Qureshi",
        D(1997, 8, 5),
        "male",
        "+91 77200 38419",
        "Flat 6, Noor Manzil, Kondhwa Khurd, Pune 411048",
        "O-",
        tags=["orthopaedic"],
        summary="29-year-old delivery rider with a distal forearm fracture after a two-wheeler fall; in a below-elbow cast. "
        "Allergic to ibuprofen (facial swelling).",
    )
    p.conditions = [("Fracture of distal forearm, right (closed)", "S52.501A", D(2026, 10, 18))]
    p.allergies = [("Ibuprofen", "Facial and lip swelling within an hour (2023)", "severe")]
    p.outside_meds = [
        ("Ultracet", "1 tab", "TDS", "Fracture pain", D(2026, 10, 18)),
        ("Pan 40", "1 tab", "OD", "Gastric protection", D(2026, 10, 18)),
    ]
    xr, xr_img = radiograph(p, D(2026, 10, 18), MEDISIGHT, "xr_fracture_adult", "X-ray Wrist PA - Right", extra=["RIGHT", "PA"])
    p.docs = [
        xr,
        imaging(
            p,
            D(2026, 10, 18),
            MEDISIGHT,
            "X-ray Right Wrist and Forearm",
            [
                ("Clinical details", "Fall from two-wheeler on an outstretched right hand. Pain and swelling at the wrist."),
                (
                    "Findings",
                    "Fracture of the distal forearm just proximal to the wrist joint, with mild cortical buckling and minimal displacement. "
                    "Radiocarpal joint congruent. Carpal bones and metacarpals intact. Soft-tissue swelling around the wrist.",
                ),
            ],
            ["Minimally displaced fracture of the distal right forearm. Orthopaedic opinion advised."],
            accession="MI-XR-26-10182",
            modality="Digital radiography (DR)",
            key_image=xr_img,
            ref_by="Casualty, Navkar Ortho & Trauma Centre",
        ),
        prescription(
            p,
            D(2026, 10, 18),
            CLINIC_NAVKAR,
            ("Dr. Yash Mehta", "MS (Orthopaedics), DNB", "Consultant Orthopaedic Surgeon"),
            vitals="BP 128/80 · Pulse 88/min",
            complaints="Fall from bike, right wrist pain and swelling 2 hours",
            findings="Tenderness distal forearm, no neurovascular deficit. X-ray: minimally displaced distal forearm fracture.",
            diagnosis="Closed fracture distal right forearm — below-elbow cast applied. Allergy: ibuprofen (angioedema).",
            medicines=[
                ("Tab. Ultracet (tramadol 37.5 + paracetamol 325)", "1 tab", "Three times daily after food", "5 days"),
                ("Tab. Pan 40", "1 tab", "Before breakfast", "5 days"),
                ("Tab. Shelcal 500", "1 tab", "Once daily", "6 weeks"),
            ],
            advice=[
                "Keep the arm elevated, move fingers often",
                "Do not wet the cast",
                "Return immediately for numbness, blue fingers or severe pain",
            ],
            follow_up="After 1 week with check X-ray in cast",
        ),
    ]
    return p


def lakshmi() -> Patient:
    p = Patient(
        10,
        "LCM-10240",
        "Mrs.",
        "Lakshmi",
        "Venkatesh",
        D(1960, 6, 14),
        "female",
        "+91 98221 90433",
        "A-1102, Megapolis Sparklet, Hinjewadi Phase 3, Pune 411057",
        "B+",
        tags=["neurology"],
        summary="66-year-old retired teacher whose headaches and a single seizure led to an MRI showing a right frontal convexity meningioma. "
        "On levetiracetam; awaiting elective surgery.",
    )
    p.conditions = [
        ("Meningioma, right frontal convexity", "D32.0", D(2026, 9, 12)),
        ("Seizure — single focal to bilateral", "R56.9", D(2026, 9, 6)),
        ("Essential hypertension", "I10", D(2014, 1, 1)),
    ]
    p.allergies = []
    p.outside_meds = [
        ("Levipil 500", "1 tab", "BD", "Seizure prophylaxis", D(2026, 9, 8)),
        ("Telma 40", "1 tab", "OD", "Hypertension", D(2014, 2, 1)),
    ]
    when = D(2026, 9, 12)
    p.docs = [
        dicom(
            p,
            when,
            gray("mri_brain_meningioma_coronal"),
            source="mri_brain_meningioma_coronal",
            modality="MR",
            study="MRI BRAIN WITH CONTRAST",
            series="COR T1 POST GAD",
            body_part="BRAIN",
            window=(128, 256),
            org=VEDANT,
            spacing=(0.47, 0.47),
            thickness=5,
            accession="VH-MR-26-09121",
            label="MRI brain - coronal T1 post-contrast",
        ),
        dicom(
            p,
            when,
            gray("mri_brain_meningioma_sagittal"),
            source="mri_brain_meningioma_sagittal",
            modality="MR",
            study="MRI BRAIN WITH CONTRAST",
            series="SAG T1 POST GAD",
            body_part="BRAIN",
            window=(128, 256),
            org=VEDANT,
            spacing=(0.47, 0.47),
            thickness=5,
            accession="VH-MR-26-09121",
            label="MRI brain - sagittal T1 post-contrast",
        ),
        imaging(
            p,
            when,
            VEDANT,
            "MRI Brain (plain and contrast)",
            [
                ("Clinical details", "Headaches for 3 months; one episode of left arm jerking with loss of consciousness on 6 Sept."),
                ("Technique", "Multiplanar multisequence MRI with T1, T2, FLAIR, DWI, SWI and post-gadolinium T1 images on a 3T scanner."),
                (
                    "Findings",
                    "A well-defined extra-axial dural-based lesion over the right frontal convexity measuring 4.2 x 3.6 x 3.4 cm. "
                    "It is isointense on T1, mildly hyperintense on T2 and shows intense homogeneous enhancement with a dural tail. "
                    "CSF cleft partially preserved. Mild perilesional vasogenic oedema; 4 mm midline shift to the left. "
                    "No restricted diffusion. Rest of the brain parenchyma, ventricles and posterior fossa normal for age.",
                ),
            ],
            [
                "Right frontal convexity extra-axial lesion with dural tail — features typical of meningioma (4.2 cm), with mild mass effect.",
                "Neurosurgical opinion recommended.",
            ],
            accession="VH-MR-26-09121",
            modality="MRI 3T",
            ref_by="Dr. Ananya Rao",
        ),
        discharge(
            p,
            datetime(2026, 9, 6, 21, 15),
            datetime(2026, 9, 8, 13, 0),
            VEDANT,
            ipd_no="IP/26/09/1388",
            consultant="Dr. Kiran Deshpande, MCh (Neurosurgery)",
            department="Neurosciences",
            diagnosis=["First seizure (focal to bilateral tonic-clonic)", "Right frontal space-occupying lesion — for MRI"],
            sections=[
                (
                    "Presenting complaints",
                    "Witnessed episode of left arm jerking progressing to generalised shaking for 2 minutes with loss of consciousness and post-ictal drowsiness.",
                ),
                (
                    "Course in hospital",
                    "Loaded with levetiracetam. CT brain showed a hyperdense extra-axial lesion, right frontal. No further seizures. "
                    "Neurologically intact at discharge. MRI brain with contrast arranged as an outpatient.",
                ),
            ],
            investigations=[
                ("Sodium", "136", "mmol/L", "135 - 145"),
                ("Haemoglobin", "12.8", "g/dL", "12.0 - 15.0"),
                ("Random blood glucose", "112", "mg/dL", "70 - 140"),
            ],
            medicines=[
                ("Tab. Levipil 500 mg", "1 tab", "Twice daily", "Until review"),
                ("Tab. Telma 40 mg", "1 tab", "Morning", "Continue"),
            ],
            advice=[
                "No driving, swimming or working at heights",
                "Do not miss levetiracetam doses",
                "Seizure first aid explained to family",
            ],
            follow_up="Neurosurgery OPD with MRI brain within 1 week.",
            doctors=[("Dr. Kiran Deshpande", "MCh (Neurosurgery), Consultant Neurosurgeon")],
        ),
        clinic_letter(
            p,
            D(2026, 9, 20),
            VEDANT,
            "Neurosurgery consultation",
            [
                (
                    "Assessment",
                    "Symptomatic right frontal convexity meningioma (4.2 cm) with seizure and mild mass effect. Good performance status.",
                ),
                (
                    "Plan",
                    "Elective right frontal craniotomy and Simpson grade I excision planned for 2 November. Pre-anaesthetic check-up, "
                    "cardiology fitness (hypertension) and blood grouping. Continue levetiracetam. Stop aspirin-containing medicines 7 days before surgery.",
                ),
            ],
            [
                "Surgery advised: right frontal craniotomy and excision of meningioma.",
                "Pre-operative work-up and physician fitness requested.",
            ],
            [("Dr. Kiran Deshpande", "MCh (Neurosurgery), Consultant Neurosurgeon")],
        ),
        lab(
            p,
            D(2026, 9, 20),
            SANVITA,
            "Pre-operative profile",
            [
                (
                    "Haematology",
                    [
                        ("Haemoglobin", "12.7", "g/dL", "12.0 - 15.0"),
                        ("Platelet count", "221", "10^3/µL", "150 - 410"),
                        ("INR", "1.02", "", "0.8 - 1.2"),
                    ],
                ),
                (
                    "Biochemistry",
                    [
                        ("Serum Creatinine", "0.84", "mg/dL", "0.50 - 1.10"),
                        ("Sodium", "131", "mmol/L", "135 - 145", "ISE"),
                        ("Potassium", "4.2", "mmol/L", "3.5 - 5.1", "ISE"),
                        ("Fasting glucose", "96", "mg/dL", "70 - 99"),
                    ],
                ),
            ],
            lab_no="SD/26/092048",
            notes=["Mild hyponatraemia — review medicines and fluid intake."],
        ),
    ]
    return p


PATIENTS = [aarav, meenakshi, kavita, imran, lakshmi]
