"""Patients 1-5."""

from __future__ import annotations

from datetime import date, datetime

import render as R
from common import (
    AROGYAM,
    CLINIC_NTEP,
    CLINIC_SHRAVANI,
    CLINIC_UROCARE,
    MEDISIGHT,
    OJAS,
    PANCHAVATI,
    PRAKRUTI,
    SANVITA,
    Patient,
    discharge,
    ecg,
    imaging,
    lab,
    prescription,
    radiograph,
    still,
)

D = date


def rohit() -> Patient:
    p = Patient(
        1,
        "GMS-10231",
        "Mr.",
        "Rohit",
        "Verma",
        D(1957, 5, 10),
        "male",
        "+91 98450 12345",
        "Flat 12, Shubham Co-op Society, Karve Nagar, Pune 411052",
        "B+",
        tags=["diabetes", "hypertension", "regular"],
        summary="69-year-old retired bank officer with diabetes, hypertension and BPH; sulfa allergy. Seen in September for fever "
        "and weight gain; thyroid and sugar tests since. Today: stomach pain for 2 days.",
    )
    p.conditions = [
        ("Type 2 diabetes mellitus", "E11.9", D(2014, 3, 1)),
        ("Essential hypertension", "I10", D(2016, 8, 1)),
        ("Benign prostatic hyperplasia", "N40.0", D(2022, 1, 1)),
        ("Dyslipidaemia", "E78.5", D(2020, 6, 1)),
    ]
    p.allergies = [("Sulfa drugs", "Itchy rash (2019, after Septran)", "moderate")]
    p.outside_meds = [("Urimax 0.4", "1 cap", "HS", "Benign prostatic hyperplasia", D(2025, 11, 8))]
    p.visits = [
        {
            "date": D(2026, 6, 17),
            "reason": "Diabetes and BP review",
            "history": "Regular follow-up. No hypoglycaemia. Nocturia once, stable since starting Urimax.",
            "examination": "Comfortable. Pedal pulses felt. Monofilament sensation intact. No oedema.",
            "vitals": {"bp": "138/84", "hr": 76, "weight_kg": 75},
            "diagnoses": ["Type 2 diabetes mellitus", "Essential hypertension"],
            "assessment": "HbA1c 7.6 % — slightly above target. BP acceptable. LDL 118 on atorvastatin 10.",
            "plan": "Continue medicines for 3 months. HbA1c, kidney function and lipids before the next visit.",
            "rx": {
                "items": [
                    ("Glycomet-GP 1", "1 tab", "BD", 90, "Before breakfast and dinner"),
                    ("Telma 40", "1 tab", "OD", 90, "Morning"),
                    ("Atorva 10", "1 tab", "HS", 90, None),
                    ("Ecosprin 75", "1 tab", "OD", 90, "After lunch"),
                ],
                "advice": "Low-salt, low-sugar diet. Walk 30 minutes daily.",
                "follow_up_days": 90,
                "chronic": True,
            },
        },
        {
            "date": D(2026, 9, 17),
            "reason": "Fever and body ache for 3 days",
            "history": "Fever up to 101°F for 3 days with body ache and mild sore throat. No cough, no urinary symptoms. "
            "Also reports weight gain of about 3 kg over 3 months and feeling tired.",
            "examination": "Temp 100.4°F. Throat mildly congested. Chest clear. No rash. No lymphadenopathy.",
            "vitals": {"bp": "134/82", "hr": 92, "weight_kg": 78, "temp_f": 100.4},
            "diagnoses": ["Acute viral fever", "Weight gain — under evaluation"],
            "assessment": "Likely viral fever. Weight gain with fatigue: check thyroid; review diabetes control.",
            "plan": "Paracetamol for fever, fluids. HbA1c, kidney function and TSH. Review in 4 weeks with reports.",
            "rx": {
                "items": [("Dolo 650", "1 tab", "TDS", 5, "After food; for fever"), ("Pan 40", "1 tab", "OD", 5, "Before breakfast")],
                "advice": "Plenty of fluids. Return if fever lasts more than 3 more days.",
                "follow_up_days": 28,
            },
        },
    ]
    p.orders = [
        (
            D(2026, 9, 17),
            "HbA1c, KFT and TSH",
            "lab",
            "Diabetes control, kidney function; weight gain and fatigue — rule out hypothyroidism",
            1,
        )
    ]
    p.today = ("10:15", "Stomach pain since 2 days", "expected")
    p.docs = [
        lab(
            p,
            D(2026, 6, 12),
            SANVITA,
            "HbA1c and lipid profile",
            [
                (
                    "Diabetes",
                    [
                        ("HbA1c", "7.6", "%", "4.0 - 5.6", "HPLC"),
                        ("Fasting glucose", "148", "mg/dL", "70 - 99", "Hexokinase"),
                        ("#", "Interpretation (ADA): 5.7-6.4 % prediabetes; 6.5 % or more diabetes; treatment target generally below 7 %."),
                    ],
                ),
                (
                    "Lipid profile",
                    [
                        ("Total cholesterol", "196", "mg/dL", "< 200"),
                        ("Triglycerides", "182", "mg/dL", "< 150"),
                        ("HDL cholesterol", "41", "mg/dL", "> 40"),
                        ("LDL cholesterol", "118", "mg/dL", "< 100"),
                    ],
                ),
                (
                    "Kidney function",
                    [
                        ("Serum Creatinine", "1.28", "mg/dL", "0.70 - 1.30", "Jaffe kinetic"),
                        ("Potassium", "4.6", "mmol/L", "3.5 - 5.1", "ISE"),
                    ],
                ),
            ],
            lab_no="SD/26/061204",
        ),
        lab(
            p,
            D(2026, 9, 22),
            SANVITA,
            "Diabetes, kidney and thyroid panel",
            [
                (
                    "Haematology",
                    [
                        ("Haemoglobin", "12.9", "g/dL", "13.0 - 17.0", "Cyanmethaemoglobin"),
                        ("Total Leucocyte Count", "7.6", "10^3/µL", "4.0 - 11.0"),
                        ("Platelet count", "238", "10^3/µL", "150 - 410"),
                    ],
                ),
                (
                    "Biochemistry",
                    [
                        ("HbA1c", "8.1", "%", "4.0 - 5.6", "HPLC"),
                        ("Fasting glucose", "162", "mg/dL", "70 - 99", "Hexokinase"),
                        ("Serum Creatinine", "1.36", "mg/dL", "0.70 - 1.30", "Jaffe kinetic"),
                        ("Sodium", "138", "mmol/L", "135 - 145", "ISE"),
                        ("Potassium", "4.9", "mmol/L", "3.5 - 5.1", "ISE"),
                        ("SGPT (ALT)", "34", "U/L", "7 - 56", "IFCC"),
                    ],
                ),
                ("Thyroid", [("TSH", "7.2", "µIU/mL", "0.40 - 4.00", "CLIA"), ("Free T4", "0.96", "ng/dL", "0.89 - 1.76", "CLIA")]),
            ],
            lab_no="SD/26/091854",
            notes=[
                "Raised TSH with free T4 in the normal range: suggestive of subclinical hypothyroidism. Repeat in 6-8 weeks with anti-TPO if clinically indicated.",
                "eGFR by CKD-EPI 2021: 55 mL/min/1.73 m².",
            ],
        ),
        prescription(
            p,
            D(2025, 11, 8),
            CLINIC_UROCARE,
            ("Dr. Sameer Joshi", "MS, MCh (Urology)", "Consultant Urologist"),
            vitals="BP 136/80 · Pulse 78/min",
            complaints="Nocturia 3-4 times, poor stream, hesitancy for 6 months",
            findings="P/R: grade II prostatomegaly, smooth, non-tender. PVR 60 mL on USG.",
            diagnosis="Benign prostatic hyperplasia (IPSS 14 — moderate)",
            medicines=[("Tab. Urimax 0.4 mg", "1 cap", "At bedtime (HS)", "3 months, then continue")],
            advice=["Avoid fluids 2 hours before bed", "Get up slowly from bed (dizziness possible)"],
            follow_up="After 3 months with PSA and USG KUB",
            investigations=["Serum PSA", "USG KUB with post-void residue"],
        ),
    ]
    cxr, cxr_img = radiograph(p, D(2026, 2, 14), MEDISIGHT, "cxr_normal_m52", "Chest X-ray PA", extra=["PA ERECT", "kVp 110 mAs 4"])
    p.docs += [
        cxr,
        imaging(
            p,
            D(2026, 2, 14),
            MEDISIGHT,
            "X-ray Chest PA View",
            [
                ("Clinical details", "Cough for 2 weeks, non-smoker. Diabetic."),
                (
                    "Findings",
                    "Both lung fields are clear. No focal consolidation, mass or effusion. Cardiothoracic ratio within normal limits. "
                    "Both costophrenic angles are clear. Hila normal. Bony thorax and soft tissues unremarkable.",
                ),
            ],
            ["No active lung parenchymal lesion.", "Normal cardiac size."],
            accession="MI-XR-26-02148",
            modality="Digital radiography (DR)",
            key_image=cxr_img,
        ),
    ]
    # The scan ordered today — brought back by the patient; the front desk uploads it during the demo.
    p.docs.append(
        imaging(
            p,
            D(2026, 10, 23),
            MEDISIGHT,
            "USG Abdomen and Pelvis",
            [
                ("Clinical details", "Epigastric pain for 2 days. Diabetic, hypertensive. Rule out gallstones / pancreatic pathology."),
                (
                    "Liver",
                    "Normal in size (14.2 cm) with mildly increased echotexture. No focal lesion. Intrahepatic biliary radicles not dilated.",
                ),
                (
                    "Gall bladder",
                    "Well distended. Multiple mobile calculi, the largest 9 mm, with posterior acoustic shadowing. "
                    "Wall thickness 2.6 mm (normal). No pericholecystic fluid. Sonographic Murphy's sign negative.",
                ),
                ("CBD / Pancreas", "CBD 4.5 mm, no calculus seen. Pancreas head and body normal; tail obscured by bowel gas."),
                ("Kidneys", "Right 10.2 cm, left 10.5 cm. Normal corticomedullary differentiation. No calculus or hydronephrosis."),
                ("Prostate", "Enlarged, 38 cc, homogeneous. Post-void residue 55 mL."),
                ("Others", "Spleen 10.1 cm, normal. No free fluid. No significant lymphadenopathy."),
            ],
            [
                "Cholelithiasis — multiple gall bladder calculi without sonographic evidence of acute cholecystitis.",
                "Grade I fatty liver.",
                "Prostatomegaly (38 cc) with insignificant post-void residue.",
            ],
            accession="MI-US-26-10231",
            modality="Ultrasound (Philips EPIQ 5)",
            folder="To upload",
            pending=True,
            hour=16,
        )
    )
    return p


def harish() -> Patient:
    p = Patient(
        2,
        "GMS-10232",
        "Mr.",
        "Harish Chandra",
        "Gupta",
        D(1952, 3, 2),
        "male",
        "+91 98220 47613",
        "B-401, Sai Sparsh, Baner, Pune 411045",
        "O+",
        tags=["cardiac", "anticoagulated", "high-risk"],
        summary="74-year-old with permanent atrial fibrillation and heart failure (EF 35 %); admitted in August with fluid overload. "
        "On apixaban 5 mg twice daily although he weighs 58 kg and his creatinine is 1.6.",
    )
    p.conditions = [
        ("Atrial fibrillation", "I48.21", D(2024, 2, 1)),
        ("Heart failure with reduced ejection fraction", "I50.2", D(2024, 2, 1)),
        ("Essential hypertension", "I10", D(2010, 1, 1)),
        ("Chronic kidney disease, stage 3a", "N18.31", D(2025, 9, 1)),
    ]
    p.allergies = []
    p.outside_meds = [
        ("Eliquis 5", "1 tab", "BD", "Atrial fibrillation — stroke prevention", D(2024, 2, 10)),
        ("Met XL 25", "1 tab", "OD", "Heart failure / rate control", D(2024, 2, 10)),
        ("Lasix 40", "1 tab", "OD", "Heart failure", D(2026, 8, 24)),
        ("Aldactone 25", "1 tab", "OD", "Heart failure", D(2024, 6, 1)),
        ("Telma 20", "1 tab", "OD", "Heart failure / hypertension", D(2024, 6, 1)),
    ]
    p.visits = [
        {
            "date": D(2026, 9, 5),
            "reason": "Post-discharge review — heart failure",
            "history": "Discharged on 24 Aug after admission with breathlessness and leg swelling. Now walks 300 m on level ground. Two-pillow orthopnoea, no PND.",
            "examination": "JVP not raised. Bilateral basal crepts minimal. Trace pedal oedema. Irregularly irregular pulse.",
            "vitals": {"bp": "118/72", "hr": 84, "weight_kg": 58, "spo2": 96},
            "diagnoses": ["Heart failure with reduced ejection fraction", "Atrial fibrillation"],
            "assessment": "Euvolaemic on current diuretics. Rate controlled.",
            "plan": "Continue medicines. Repeat KFT and electrolytes and echo in one month; daily weight chart.",
            "rx": None,
        }
    ]
    p.orders = [
        (D(2026, 9, 5), "2D Echo", "cardiology", "LV function on treatment after HF admission", 0),
        (
            D(2026, 9, 5),
            "KFT with electrolytes and NT-proBNP",
            "lab",
            "On spironolactone, telmisartan and furosemide — potassium and creatinine",
            0,
        ),
    ]
    p.today = ("09:30", "Breathlessness follow-up", "arrived")
    cxr, cxr_img = radiograph(p, D(2026, 8, 20), PANCHAVATI, "cxr_cardiomegaly_m74", "Chest X-ray PA", extra=["PA ERECT"])
    p.docs = [
        discharge(
            p,
            datetime(2026, 8, 20, 22, 40),
            datetime(2026, 8, 24, 12, 0),
            PANCHAVATI,
            ipd_no="IP/26/08/2216",
            consultant="Dr. Nikhil Sonawane, DM (Cardiology)",
            department="Cardiology",
            diagnosis=[
                "Acute decompensated heart failure (HFrEF, LVEF 35 %)",
                "Permanent atrial fibrillation with controlled ventricular rate",
                "Hypertension",
                "Chronic kidney disease stage 3a",
            ],
            sections=[
                (
                    "Presenting complaints",
                    "Breathlessness on minimal exertion for 5 days, orthopnoea and bilateral leg swelling. Reduced urine output.",
                ),
                (
                    "Examination on admission",
                    "Pulse 118/min irregularly irregular, BP 146/88 mmHg, SpO2 89 % on room air, RR 28/min. JVP raised. Bilateral basal crepitations, pitting pedal oedema up to the knees.",
                ),
                (
                    "Course in hospital",
                    "Treated with intravenous furosemide, oxygen and rate control. Diuresed 4.5 L over 72 hours with improvement in breathlessness. "
                    "Creatinine rose from 1.42 to 1.68 mg/dL with diuresis and settled to 1.55 at discharge. Potassium 5.0 mmol/L on spironolactone. "
                    "Apixaban continued. Discharged in stable condition, ambulant, SpO2 96 % on room air.",
                ),
            ],
            investigations=[
                ("Haemoglobin", "11.8", "g/dL", "13.0 - 17.0"),
                ("Serum Creatinine", "1.55", "mg/dL", "0.70 - 1.30"),
                ("Sodium", "134", "mmol/L", "135 - 145"),
                ("Potassium", "5.0", "mmol/L", "3.5 - 5.1"),
                ("NT-proBNP", "6840", "pg/mL", "< 450"),
                ("Troponin I", "18", "ng/L", "< 26"),
            ],
            medicines=[
                ("Tab. Lasix 40 mg", "1 tab", "Morning", "Continue"),
                ("Tab. Aldactone 25 mg", "1 tab", "Morning", "Continue"),
                ("Tab. Met XL 25 mg", "1 tab", "Morning", "Continue"),
                ("Tab. Telma 20 mg", "1 tab", "Night", "Continue"),
                ("Tab. Eliquis 5 mg", "1 tab", "Twice daily", "Continue"),
            ],
            advice=[
                "Fluid restriction 1.5 L/day; salt below 5 g/day",
                "Daily weight — report a gain of more than 2 kg in 3 days",
                "Avoid painkillers such as ibuprofen and diclofenac",
            ],
            follow_up="Cardiology OPD after 2 weeks with KFT and electrolytes.",
            doctors=[("Dr. Nikhil Sonawane", "DM (Cardiology), Consultant Cardiologist"), ("Dr. Pooja Kale", "MD (Medicine), Resident")],
        ),
        cxr,
        imaging(
            p,
            D(2026, 8, 20),
            PANCHAVATI,
            "X-ray Chest PA View",
            [
                ("Clinical details", "Breathlessness, orthopnoea, known AF and LV dysfunction."),
                (
                    "Findings",
                    "Cardiac silhouette is enlarged (CTR about 0.6). Upper lobe blood diversion. Mild prominence of the hila. "
                    "Blunting of the right costophrenic angle — small effusion. No focal consolidation.",
                ),
            ],
            ["Cardiomegaly with features of pulmonary venous hypertension.", "Small right pleural effusion."],
            accession="PC-XR-26-08734",
            modality="Computed radiography (CR)",
            key_image=cxr_img,
        ),
        ecg(
            p, D(2026, 10, 10), "00330_hr", ["Atrial fibrillation", "Otherwise no definite pathology", "Unconfirmed — review by physician"]
        ),
        imaging(
            p,
            D(2026, 10, 10),
            OJAS,
            "2D Echo and Colour Doppler",
            [
                ("Indication", "Follow-up of LV function in HFrEF with atrial fibrillation."),
                ("Measurements", "LVIDd 60 mm, LVIDs 50 mm, IVS 9 mm, PW 9 mm. LA 48 mm (dilated). Aortic root 31 mm. TAPSE 16 mm."),
                (
                    "Findings",
                    "Dilated left ventricle with global hypokinesia. LVEF by biplane Simpson's 35 % (previously 30 %). Grade II diastolic dysfunction cannot be assessed in AF. "
                    "Moderate functional mitral regurgitation. Mild tricuspid regurgitation; RVSP 38 mmHg. IVC 18 mm with more than 50 % collapse. No pericardial effusion, no clot.",
                ),
            ],
            [
                "Dilated cardiomyopathy picture with LVEF 35 % — mild improvement on treatment.",
                "Moderate functional MR; mild pulmonary hypertension (RVSP 38 mmHg).",
                "Severely dilated left atrium; rhythm atrial fibrillation during study.",
            ],
            accession="OH-ECHO-26-1022",
            modality="Echocardiography",
            folder="ECG & cardiology",
            doctors=[("Dr. Aditya Rane", "DM (Cardiology), Consultant Cardiologist")],
        ),
        lab(
            p,
            D(2026, 10, 9),
            SANVITA,
            "KFT, electrolytes and NT-proBNP",
            [
                (
                    "Kidney function",
                    [
                        ("Serum Creatinine", "1.60", "mg/dL", "0.70 - 1.30", "Jaffe kinetic"),
                        ("Blood Urea Nitrogen", "28", "mg/dL", "7 - 20"),
                        ("Uric acid", "8.1", "mg/dL", "3.5 - 7.2"),
                    ],
                ),
                (
                    "Electrolytes",
                    [
                        ("Sodium", "133", "mmol/L", "135 - 145", "ISE"),
                        ("Potassium", "5.3", "mmol/L", "3.5 - 5.1", "ISE"),
                        ("Chloride", "99", "mmol/L", "98 - 107", "ISE"),
                    ],
                ),
                ("Cardiac markers", [("NT-proBNP", "2840", "pg/mL", "< 450", "ECLIA")]),
                ("Haematology", [("Haemoglobin", "12.1", "g/dL", "13.0 - 17.0")]),
            ],
            lab_no="SD/26/100942",
            notes=["eGFR by CKD-EPI 2021: 44 mL/min/1.73 m².", "Mild hyperkalaemia — review potassium-sparing drugs and RAAS blockade."],
        ),
        # Misfiled: another patient's report that ended up in this file (the app's identity check flags it).
        lab(
            p,
            D(2026, 10, 14),
            AROGYAM,
            "Lipid profile",
            [
                (
                    "Lipid profile",
                    [
                        ("Total cholesterol", "238", "mg/dL", "< 200"),
                        ("Triglycerides", "264", "mg/dL", "< 150"),
                        ("HDL cholesterol", "36", "mg/dL", "> 40"),
                        ("LDL cholesterol", "149", "mg/dL", "< 100"),
                    ],
                ),
                ("Diabetes", [("HbA1c", "9.4", "%", "4.0 - 5.6", "HPLC")]),
            ],
            lab_no="AP/2610/44871",
            ref_by="Dr. S. Bharucha",
            printed_for=R.Person("Mr. Hemant Gupta", "52 Y", "Male", "AP-778812"),
        ),
    ]
    return p


def sunita() -> Patient:
    p = Patient(
        3,
        "GMS-10233",
        "Mrs.",
        "Sunita",
        "Deshmukh",
        D(1968, 7, 19),
        "female",
        "+91 94221 88305",
        "Plot 7, Shramik Nagar, Satpur, Nashik 422007",
        "A+",
        tags=["diabetes", "thyroid"],
        summary="58-year-old schoolteacher with diabetes and hypothyroidism, admitted in August with right lower lobe pneumonia. "
        "Penicillin allergy (breathlessness and rash).",
    )
    p.conditions = [
        ("Type 2 diabetes mellitus", "E11.9", D(2015, 5, 1)),
        ("Primary hypothyroidism", "E03.9", D(2019, 2, 1)),
        ("Community-acquired pneumonia, right lower lobe", "J18.1", D(2026, 8, 3), "resolved"),
    ]
    p.allergies = [("Penicillin", "Breathlessness and generalised rash (2012, after amoxicillin)", "severe")]
    p.outside_meds = [
        ("Glycomet 500", "1 tab", "BD", "Type 2 diabetes", D(2015, 6, 1)),
        ("Thyronorm 75", "1 tab", "OD", "Hypothyroidism", D(2019, 3, 1)),
    ]
    p.visits = [
        {
            "date": D(2026, 8, 22),
            "reason": "Post-pneumonia review",
            "history": "Discharged 8 Aug. Cough much better, occasional dry cough. No fever. Appetite returning.",
            "examination": "Chest: few crepts right base. SpO2 98 %.",
            "vitals": {"bp": "126/78", "hr": 82, "weight_kg": 64, "spo2": 98},
            "diagnoses": ["Community-acquired pneumonia — resolving"],
            "assessment": "Clinically improving; inflammatory markers normalised.",
            "plan": "Repeat chest X-ray after 6 weeks. Continue diabetes and thyroid medicines.",
            "rx": None,
        }
    ]
    p.orders = [(D(2026, 8, 22), "Chest X-ray PA (repeat)", "radiology", "Resolution of right lower lobe consolidation", 0)]
    cxr, cxr_img = radiograph(p, D(2026, 8, 3), PANCHAVATI, "cxr_consolidation_f58", "Chest X-ray PA", extra=["PA ERECT"])
    p.docs = [
        cxr,
        imaging(
            p,
            D(2026, 8, 3),
            PANCHAVATI,
            "X-ray Chest PA View",
            [
                ("Clinical details", "Fever with cough and right-sided chest pain for 4 days. Diabetic."),
                (
                    "Findings",
                    "Patchy homogeneous opacity in the right lower zone with air bronchograms, obscuring the right hemidiaphragm medially. "
                    "Left lung clear. Cardiac size normal. Costophrenic angles clear.",
                ),
            ],
            ["Right lower lobe consolidation — likely infective. Follow-up radiograph after treatment advised."],
            accession="PC-XR-26-08035",
            modality="Computed radiography (CR)",
            key_image=cxr_img,
        ),
        lab(
            p,
            D(2026, 8, 3),
            PRAKRUTI,
            "CBC, CRP and procalcitonin",
            [
                (
                    "Haematology",
                    [
                        ("Haemoglobin", "11.6", "g/dL", "12.0 - 15.0"),
                        ("Total Leucocyte Count", "16.8", "10^3/µL", "4.0 - 11.0"),
                        ("Platelet count", "312", "10^3/µL", "150 - 410"),
                        ("ESR", "64", "mm/hr", "0 - 20", "Westergren"),
                    ],
                ),
                ("Inflammation", [("CRP", "96", "mg/L", "< 6", "Turbidimetry")]),
                ("Diabetes", [("HbA1c", "7.4", "%", "4.0 - 5.6", "HPLC"), ("Random blood glucose", "246", "mg/dL", "70 - 140")]),
            ],
            lab_no="PP/0826/1187",
            hour=10,
            notes=["Neutrophilic leucocytosis (neutrophils 86 %) with raised CRP — consistent with bacterial infection."],
        ),
        discharge(
            p,
            datetime(2026, 8, 3, 13, 10),
            datetime(2026, 8, 8, 11, 30),
            PANCHAVATI,
            ipd_no="IP/26/08/0391",
            consultant="Dr. Mahesh Bhamre, MD (Medicine)",
            department="General Medicine",
            diagnosis=[
                "Community-acquired pneumonia, right lower lobe (CURB-65 score 1)",
                "Type 2 diabetes mellitus — uncontrolled during infection",
                "Hypothyroidism",
            ],
            sections=[
                (
                    "Presenting complaints",
                    "Fever with chills, productive cough with rust-coloured sputum and right-sided pleuritic chest pain for 4 days.",
                ),
                (
                    "Examination on admission",
                    "Temp 102°F, pulse 108/min, BP 118/76, RR 24/min, SpO2 92 % on room air. Bronchial breathing and crepitations right infra-axillary and infra-scapular areas.",
                ),
                (
                    "Course in hospital",
                    "Known penicillin allergy (anaphylactoid reaction) — beta-lactams avoided. Treated with intravenous levofloxacin, switched to oral on day 3. "
                    "Insulin sliding scale during admission, back on metformin at discharge. Afebrile from day 2; SpO2 98 % on room air at discharge.",
                ),
            ],
            investigations=[
                ("Total Leucocyte Count", "9.4", "10^3/µL", "4.0 - 11.0"),
                ("CRP", "18", "mg/L", "< 6"),
                ("Serum Creatinine", "0.86", "mg/dL", "0.60 - 1.10"),
                ("Blood culture", "No growth at 48 h", "", ""),
                ("Sputum culture", "Streptococcus pneumoniae", "", ""),
            ],
            medicines=[
                ("Tab. Levoflox 750 mg", "1 tab", "Once daily", "3 more days"),
                ("Tab. Glycomet 500 mg", "1 tab", "Twice daily", "Continue"),
                ("Tab. Thyronorm 75 mcg", "1 tab", "Empty stomach", "Continue"),
                ("Tab. Dolo 650 mg", "1 tab", "SOS for fever", "5 days"),
            ],
            advice=[
                "Complete the antibiotic course",
                "Pneumococcal and annual influenza vaccination after recovery",
                "Monitor sugars twice daily for a week",
            ],
            follow_up="Physician review in 2 weeks; repeat chest X-ray in 6 weeks.",
            doctors=[("Dr. Mahesh Bhamre", "MD (Medicine), Consultant Physician")],
        ),
        lab(
            p,
            D(2026, 8, 20),
            PRAKRUTI,
            "CBC, CRP and TSH",
            [
                (
                    "Haematology",
                    [("Haemoglobin", "11.9", "g/dL", "12.0 - 15.0"), ("Total Leucocyte Count", "7.2", "10^3/µL", "4.0 - 11.0")],
                ),
                ("Inflammation", [("CRP", "4.2", "mg/L", "< 6")]),
                ("Thyroid", [("TSH", "3.1", "µIU/mL", "0.40 - 4.00", "CLIA")]),
            ],
            lab_no="PP/0826/2011",
            hour=9,
        ),
    ]
    return p


def abdul() -> Patient:
    p = Patient(
        4,
        "GMS-10234",
        "Mr.",
        "Abdul Rahman",
        "Shaikh",
        D(1971, 2, 14),
        "male",
        "+91 90110 23457",
        "House 22, Mominpura, Kasba Peth, Pune 411011",
        "B+",
        tags=["tuberculosis", "diabetes"],
        summary="55-year-old tailor on anti-tuberculosis treatment since June for left upper lobe pulmonary TB; diabetes found at diagnosis. "
        "Latest liver tests show ALT more than three times normal.",
    )
    p.conditions = [
        ("Pulmonary tuberculosis (microbiologically confirmed)", "A15.0", D(2026, 6, 6)),
        ("Type 2 diabetes mellitus", "E11.9", D(2026, 6, 6)),
    ]
    p.allergies = []
    p.outside_meds = [
        ("AKT-4 (HRZE fixed-dose combination)", "3 tab", "OD", "Pulmonary tuberculosis — intensive phase", D(2026, 6, 8)),
        ("Pyridoxine 50 mg", "1 tab", "OD", "Prevention of isoniazid neuropathy", D(2026, 6, 8)),
        ("Glycomet 500", "1 tab", "BD", "Type 2 diabetes", D(2026, 6, 20)),
    ]
    p.visits = [
        {
            "date": D(2026, 6, 20),
            "reason": "Diabetes found during TB work-up",
            "history": "Diagnosed with pulmonary TB on 6 June, started on daily HRZE by the NTEP unit. HbA1c 9.2 %. Weight loss 6 kg over 3 months.",
            "examination": "Thin built. Crepts left infraclavicular area.",
            "vitals": {"bp": "122/76", "hr": 94, "weight_kg": 52, "spo2": 96},
            "diagnoses": ["Type 2 diabetes mellitus", "Pulmonary tuberculosis"],
            "assessment": "New diabetes; TB on treatment.",
            "plan": "Metformin; diet advice. LFT monthly during ATT.",
            "rx": {
                "items": [("Glycomet 500", "1 tab", "BD", 60, "After meals")],
                "advice": "Diabetic diet. Do not miss TB tablets.",
                "follow_up_days": 60,
                "chronic": True,
            },
        }
    ]
    p.orders = [(D(2026, 9, 25), "LFT", "lab", "On anti-TB treatment — monitor for drug-induced liver injury", None)]
    p.today = ("12:15", "TB treatment review — nausea and loss of appetite", "expected")
    cxr, cxr_img = radiograph(p, D(2026, 6, 5), MEDISIGHT, "cxr_tuberculosis", "Chest X-ray PA", extra=["PA ERECT"])
    p.docs = [
        cxr,
        imaging(
            p,
            D(2026, 6, 5),
            MEDISIGHT,
            "X-ray Chest PA View",
            [
                ("Clinical details", "Cough for 6 weeks, evening fever, weight loss."),
                (
                    "Findings",
                    "Ill-defined patchy opacities with fibrotic strands in the left upper zone. Small lucency within, suspicious for early cavitation. "
                    "Right lung clear. Cardiac size normal. No pleural effusion.",
                ),
            ],
            ["Left upper zone infiltrates with possible cavitation — features favour pulmonary tuberculosis. Sputum examination advised."],
            accession="MI-XR-26-06051",
            modality="Digital radiography (DR)",
            key_image=cxr_img,
        ),
        lab(
            p,
            D(2026, 6, 6),
            SANVITA,
            "Sputum CBNAAT and baseline tests",
            [
                ("Molecular", [("#", "Sputum CBNAAT (Xpert MTB/RIF Ultra): MTB DETECTED, MEDIUM. Rifampicin resistance NOT DETECTED.")]),
                ("Haematology", [("Haemoglobin", "11.2", "g/dL", "13.0 - 17.0"), ("ESR", "72", "mm/hr", "0 - 15", "Westergren")]),
                (
                    "Liver function (baseline)",
                    [
                        ("SGPT (ALT)", "28", "U/L", "7 - 56", "IFCC"),
                        ("SGOT (AST)", "31", "U/L", "5 - 40", "IFCC"),
                        ("Total Bilirubin", "0.7", "mg/dL", "0.2 - 1.2"),
                    ],
                ),
                ("Diabetes", [("HbA1c", "9.2", "%", "4.0 - 5.6", "HPLC")]),
                ("Serology", [("#", "HIV 1 & 2 antibodies: Non-reactive. HBsAg: Non-reactive.")]),
            ],
            lab_no="SD/26/060613",
            sample="Sputum, Blood",
        ),
        prescription(
            p,
            D(2026, 6, 8),
            CLINIC_NTEP,
            ("Dr. Sunil Kamble", "MBBS, DTCD", "Medical Officer, NTEP"),
            vitals="Weight 52 kg",
            complaints="Cough 6 weeks, fever, weight loss",
            findings="CBNAAT positive, rifampicin sensitive",
            diagnosis="New pulmonary TB (microbiologically confirmed), drug-sensitive. Nikshay ID registered.",
            medicines=[
                ("Tab. 4-FDC (HRZE 75/150/400/275)", "3 tab", "Once daily, empty stomach", "8 weeks (intensive phase)"),
                ("Tab. Pyridoxine 50 mg", "1 tab", "Once daily", "6 months"),
            ],
            advice=[
                "Daily observed doses; do not stop on your own",
                "Cover mouth while coughing; ventilate the room",
                "Report yellow eyes, vomiting or tingling immediately",
            ],
            follow_up="Sputum smear at end of 2 months",
            title="NTEP treatment card",
        ),
        lab(
            p,
            D(2026, 9, 30),
            SANVITA,
            "Liver function test",
            [
                (
                    "Liver function",
                    [
                        ("SGPT (ALT)", "128", "U/L", "7 - 56", "IFCC"),
                        ("SGOT (AST)", "104", "U/L", "5 - 40", "IFCC"),
                        ("Total Bilirubin", "1.4", "mg/dL", "0.2 - 1.2"),
                        ("Alkaline phosphatase", "118", "U/L", "40 - 129"),
                        ("Serum Albumin", "3.6", "g/dL", "3.5 - 5.2"),
                    ],
                ),
            ],
            lab_no="SD/26/093007",
            notes=[
                "Transaminases more than 3 times the upper limit with symptoms meet the definition of drug-induced liver injury on anti-TB treatment. Clinical correlation advised."
            ],
        ),
    ]
    return p


def priyanka() -> Patient:
    p = Patient(
        5,
        "GMS-10235",
        "Mrs.",
        "Priyanka",
        "Nair",
        D(1992, 4, 8),
        "female",
        "+91 99230 61542",
        "C-9, Aditya Garden City, Warje, Pune 411058",
        "O+",
        tags=["pregnancy", "thyroid"],
        summary="34-year-old software engineer, second pregnancy, about 20 weeks; hypothyroid on levothyroxine. Mild anaemia. "
        "Today: cough and cold for 4 days.",
    )
    p.conditions = [
        ("Pregnancy, second trimester (G2P1, LMP 03/06/2026)", "Z34.82", D(2026, 6, 3)),
        ("Primary hypothyroidism", "E03.9", D(2021, 1, 1)),
        ("Anaemia in pregnancy (mild)", "O99.01", D(2026, 6, 20)),
    ]
    p.allergies = []
    p.outside_meds = [
        ("Thyronorm 50", "1 tab", "OD", "Hypothyroidism", D(2021, 2, 1)),
        ("Folvite 5", "1 tab", "OD", "Pregnancy", D(2026, 6, 10)),
        ("Orofer XT", "1 tab", "OD", "Anaemia in pregnancy", D(2026, 6, 25)),
        ("Shelcal 500", "1 tab", "BD", "Pregnancy", D(2026, 8, 1)),
    ]
    p.today = ("11:00", "Cough and cold for 4 days", "expected")
    p.docs = [
        lab(
            p,
            D(2026, 6, 20),
            SANVITA,
            "Antenatal profile",
            [
                (
                    "Haematology",
                    [
                        ("Haemoglobin", "10.4", "g/dL", "11.0 - 15.0"),
                        ("MCV", "74", "fL", "80 - 100"),
                        ("Platelet count", "246", "10^3/µL", "150 - 410"),
                    ],
                ),
                ("Thyroid", [("TSH", "2.8", "µIU/mL", "0.10 - 2.50", "CLIA")]),
                ("Diabetes", [("Fasting glucose", "84", "mg/dL", "70 - 92")]),
                (
                    "Serology",
                    [
                        (
                            "#",
                            "Blood group O, Rh positive. HIV 1 & 2: Non-reactive. HBsAg: Non-reactive. VDRL: Non-reactive. Rubella IgG: Immune.",
                        )
                    ],
                ),
            ],
            lab_no="SD/26/062077",
            notes=["Trimester-specific TSH reference for the first trimester (0.10-2.50 µIU/mL) applied."],
        ),
    ]
    p.docs += [
        still(
            p,
            D(2026, 10, 9),
            "us_fetal_head",
            institution="Medisight Imaging & Diagnostics",
            study="OB - Anomaly scan",
            extra=["GA(LMP) 18w2d", "HC 160.0 mm  18w6d", "Philips Affiniti 70"],
            path="Pregnancy/2026-10-09 Fetal head - anomaly scan image.jpg",
            title="Anomaly scan — fetal head (HC)",
        ),
        imaging(
            p,
            D(2026, 10, 9),
            MEDISIGHT,
            "Obstetric USG - Level II (anomaly) scan",
            [
                ("Clinical details", "G2P1L1, LMP 03/06/2026, GA by LMP 18 weeks 2 days. Hypothyroid on treatment."),
                (
                    "Findings",
                    "Single live intrauterine fetus in cephalic presentation. Cardiac activity present, FHR 148 bpm. "
                    "BPD 41.6 mm, HC 160.0 mm, AC 132 mm, FL 27 mm — composite GA 18 weeks 5 days. EFW 241 g. "
                    "Placenta posterior, upper segment, not low lying. Liquor adequate (deepest pocket 4.8 cm). "
                    "Fetal anatomy survey: intracranial structures, face, spine, four-chamber heart with outflow tracts, stomach, kidneys, bladder and limbs seen and appear normal for gestation.",
                ),
                ("Cervix", "Length 36 mm, internal os closed."),
            ],
            [
                "Single live intrauterine pregnancy of 18 weeks 5 days, corresponding to dates.",
                "No obvious structural anomaly on this scan.",
                "EDD by LMP 10/03/2027.",
            ],
            accession="MI-OB-26-10091",
            modality="Ultrasound",
            folder="Pregnancy",
            doctors=[("Dr. Prasad Gokhale", "MD (Radio-diagnosis), FMF certified")],
        ),
        prescription(
            p,
            D(2026, 10, 9),
            CLINIC_SHRAVANI,
            ("Dr. Neha Gokhale", "MS (Obstetrics & Gynaecology)", "Consultant Obstetrician"),
            vitals="BP 112/70 · Weight 63 kg · Fundal height 19 cm",
            complaints="Routine antenatal visit at 18 weeks. No bleeding or pain.",
            findings="Uterus 18-20 weeks, relaxed. FHS present.",
            diagnosis="G2P1L1, 18 weeks 2 days. Hypothyroid (controlled). Mild anaemia.",
            medicines=[
                ("Tab. Thyronorm 50 mcg", "1 tab", "Empty stomach, 6 am", "Continue"),
                ("Tab. Orofer XT", "1 tab", "After lunch", "Continue"),
                ("Tab. Shelcal 500", "1 tab", "Twice daily", "Continue"),
                ("Tab. Folvite 5 mg", "1 tab", "Once daily", "Continue"),
            ],
            advice=["Take iron and calcium at different times from thyroid tablet", "Report bleeding, leaking or reduced fetal movements"],
            follow_up="After 4 weeks with CBC and TSH",
            investigations=["CBC", "TSH", "OGTT at 24-28 weeks"],
        ),
    ]
    return p


PATIENTS = [rohit, harish, sunita, abdul, priyanka]
