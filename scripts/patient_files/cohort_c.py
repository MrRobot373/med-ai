"""Patients 11-15."""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
from common import (
    AROGYAM,
    ASSETS,
    CLINIC_AASHA,
    CLINIC_BREATHE,
    MANIFEST,
    MEDISIGHT,
    OJAS,
    PANCHAVATI,
    PRAKRUTI,
    SAHYOG,
    SANVITA,
    VEDANT,
    Patient,
    clinic_letter,
    dicom,
    discharge,
    ecg,
    gray,
    imaging,
    lab,
    prescription,
    radiograph,
)

D = date


def gurpreet() -> Patient:
    p = Patient(
        11,
        "GMS-10241",
        "Mr.",
        "Gurpreet Singh",
        "Bains",
        D(1972, 12, 1),
        "male",
        "+91 98811 66024",
        "Bungalow 14, Ekta Colony, Aundh, Pune 411007",
        "A+",
        tags=["cardiac", "smoker"],
        summary="53-year-old transport business owner and smoker with exertional chest tightness. ECG shows lateral T-wave changes and "
        "the treadmill test was positive; angiography planned. On clopidogrel together with omeprazole.",
    )
    p.conditions = [
        ("Stable angina", "I20.8", D(2026, 10, 5)),
        ("Dyslipidaemia", "E78.5", D(2026, 10, 5)),
        ("Tobacco smoking", "F17.210", D(1995, 1, 1)),
    ]
    p.allergies = []
    p.outside_meds = [
        ("Ecosprin 75", "1 tab", "OD", "Angina", D(2026, 10, 7)),
        ("Clopilet 75", "1 tab", "OD", "Angina", D(2026, 10, 7)),
        ("Omez 20", "1 cap", "OD", "Gastric protection", D(2026, 10, 7)),
        ("Atorva 40", "1 tab", "HS", "Dyslipidaemia", D(2026, 10, 7)),
        ("Metolar 25", "1 tab", "BD", "Angina", D(2026, 10, 7)),
    ]
    p.visits = [
        {
            "date": D(2026, 10, 5),
            "reason": "Chest tightness on climbing stairs",
            "history": "Central chest tightness on climbing 2 flights for 3 weeks, relieved by rest in 5 minutes. Smokes 15 cigarettes a day for 30 years. Father had MI at 58.",
            "examination": "BMI 29. Heart sounds normal, no murmur. Chest clear.",
            "vitals": {"bp": "148/92", "hr": 86, "weight_kg": 86},
            "diagnoses": ["Stable angina — suspected", "Dyslipidaemia"],
            "assessment": "Typical exertional angina with multiple risk factors.",
            "plan": "ECG, lipid profile, chest X-ray today; cardiology referral for TMT.",
            "rx": None,
        }
    ]
    p.orders = [
        (D(2026, 10, 5), "TMT (treadmill stress test)", "cardiology", "Exertional chest tightness — inducible ischaemia?", 0),
        (D(2026, 10, 5), "Lipid profile and HbA1c", "lab", "Cardiovascular risk assessment", 0),
    ]
    cxr, cxr_img = radiograph(p, D(2026, 10, 5), MEDISIGHT, "cxr_normal_m52", "Chest X-ray PA", extra=["PA ERECT"])
    p.docs = [
        ecg(
            p,
            D(2026, 10, 5),
            "00167_hr",
            ["Sinus rhythm", "T-wave changes as in high lateral ischaemia", "Unconfirmed — review by physician"],
        ),
        cxr,
        imaging(
            p,
            D(2026, 10, 5),
            MEDISIGHT,
            "X-ray Chest PA View",
            [
                ("Clinical details", "Exertional chest discomfort. Smoker."),
                (
                    "Findings",
                    "Lungs are clear. No consolidation or effusion. Cardiac size normal. Aortic knuckle normal. Bony thorax normal.",
                ),
            ],
            ["No significant abnormality."],
            accession="MI-XR-26-10053",
            modality="Digital radiography (DR)",
            key_image=cxr_img,
        ),
        lab(
            p,
            D(2026, 10, 5),
            SANVITA,
            "Lipid profile and HbA1c",
            [
                (
                    "Lipid profile",
                    [
                        ("Total cholesterol", "246", "mg/dL", "< 200"),
                        ("Triglycerides", "212", "mg/dL", "< 150"),
                        ("HDL cholesterol", "34", "mg/dL", "> 40"),
                        ("LDL cholesterol", "168", "mg/dL", "< 100"),
                    ],
                ),
                ("Diabetes", [("HbA1c", "6.1", "%", "4.0 - 5.6", "HPLC"), ("Fasting glucose", "108", "mg/dL", "70 - 99")]),
                ("Kidney function", [("Serum Creatinine", "1.04", "mg/dL", "0.70 - 1.30")]),
            ],
            lab_no="SD/26/100544",
            notes=["Interpretation: HbA1c in the prediabetes range (5.7-6.4 %)."],
        ),
        imaging(
            p,
            D(2026, 10, 7),
            OJAS,
            "Treadmill Test (Bruce protocol)",
            [
                ("Indication", "Exertional chest tightness; risk factors — smoking, dyslipidaemia, family history."),
                (
                    "Protocol",
                    "Bruce protocol. Resting HR 82/min, BP 140/90. Exercised for 6 min 10 s (stage II, 7.4 METs), reaching 158/min (95 % of target).",
                ),
                (
                    "Findings",
                    "Exercise limited by chest tightness at 5 min 40 s. 2.0 mm horizontal ST depression in II, III, aVF and V4-V6 at peak exercise, "
                    "persisting 4 minutes into recovery. BP response normal. No arrhythmia.",
                ),
            ],
            ["TMT strongly positive for inducible myocardial ischaemia at moderate workload.", "Coronary angiography recommended."],
            accession="OH-TMT-26-1007",
            modality="Exercise ECG",
            folder="ECG & cardiology",
            doctors=[("Dr. Aditya Rane", "DM (Cardiology), Consultant Cardiologist")],
        ),
        clinic_letter(
            p,
            D(2026, 10, 7),
            OJAS,
            "Cardiology consultation",
            [
                ("Assessment", "Stable angina with strongly positive TMT. Smoker, LDL 168 mg/dL."),
                (
                    "Plan",
                    "Coronary angiography on 28 October. Started aspirin, clopidogrel, high-intensity statin and metoprolol; "
                    "omeprazole for gastric protection. Smoking cessation counselled.",
                ),
            ],
            ["Chronic coronary syndrome — angiography planned.", "Dual antiplatelet therapy started pending angiography."],
            [("Dr. Aditya Rane", "DM (Cardiology), Consultant Cardiologist")],
        ),
    ]
    return p


def ananya() -> Patient:
    p = Patient(
        12,
        "GMS-10242",
        "Ms.",
        "Ananya",
        "Bose",
        D(2000, 2, 17),
        "female",
        "+91 88050 31977",
        "Room 4, Krishna PG, Viman Nagar, Pune 411014",
        "O+",
        tags=["asthma"],
        summary="26-year-old UX designer with moderate persistent asthma and allergic rhinitis. Aspirin causes wheeze.",
    )
    p.conditions = [("Asthma, moderate persistent", "J45.40", D(2014, 1, 1)), ("Allergic rhinitis", "J30.9", D(2012, 1, 1))]
    p.allergies = [("Aspirin", "Wheezing and nasal blockage within 30 minutes (aspirin-exacerbated)", "severe")]
    p.outside_meds = [
        ("Foracort 200 Rotacap (formoterol + budesonide)", "1 inhalation", "BD", "Asthma", D(2026, 7, 14)),
        ("Montair-LC", "1 tab", "HS", "Allergic rhinitis / asthma", D(2026, 7, 14)),
    ]
    cxr, cxr_img = radiograph(p, D(2026, 7, 14), MEDISIGHT, "cxr_normal_f26", "Chest X-ray PA", extra=["PA ERECT"])
    p.docs = [
        cxr,
        imaging(
            p,
            D(2026, 7, 14),
            MEDISIGHT,
            "X-ray Chest PA View",
            [
                ("Clinical details", "Recurrent wheeze, worse at night."),
                ("Findings", "Lungs well expanded and clear. No hyperinflation. Heart, hila and diaphragm normal."),
            ],
            ["Normal chest radiograph."],
            accession="MI-XR-26-07143",
            modality="Digital radiography (DR)",
            key_image=cxr_img,
            ref_by="Dr. Farhan Ali",
        ),
        imaging(
            p,
            D(2026, 7, 14),
            CLINIC_BREATHE,
            "Spirometry with bronchodilator reversibility",
            [
                (
                    "Technique",
                    "ATS/ERS acceptable manoeuvres; 3 reproducible efforts. Salbutamol 400 mcg via spacer, repeat after 15 minutes.",
                ),
                ("Results (pre)", "FEV1 2.06 L (72 % predicted), FVC 3.18 L (93 %), FEV1/FVC 0.65. PEF 5.1 L/s (68 %)."),
                ("Results (post)", "FEV1 2.41 L (+17 %, +350 mL), FVC 3.30 L, FEV1/FVC 0.73."),
            ],
            ["Moderate obstructive ventilatory defect with significant bronchodilator reversibility — consistent with asthma."],
            accession="BE-PFT-26-0714",
            modality="Spirometry",
            folder="Lab reports",
            doctors=[("Dr. Farhan Ali", "MD (Pulmonary Medicine), Consultant Chest Physician")],
        ),
        lab(
            p,
            D(2026, 7, 14),
            AROGYAM,
            "CBC with absolute eosinophil count and IgE",
            [
                (
                    "Haematology",
                    [
                        ("Haemoglobin", "12.4", "g/dL", "12.0 - 15.0"),
                        ("Total Leucocyte Count", "8.1", "10^3/µL", "4.0 - 11.0"),
                        ("Absolute eosinophil count", "640", "cells/µL", "40 - 440"),
                    ],
                ),
                ("Immunology", [("Total IgE", "486", "IU/mL", "< 100", "CLIA")]),
            ],
            lab_no="AP/2607/30144",
            ref_by="Dr. Farhan Ali",
            notes=["Eosinophilia with raised total IgE — atopic phenotype."],
        ),
        prescription(
            p,
            D(2026, 7, 14),
            CLINIC_BREATHE,
            ("Dr. Farhan Ali", "MD (Pulmonary Medicine)", "Consultant Chest Physician"),
            vitals="SpO2 98 % · PEF 310 L/min",
            complaints="Night-time cough and wheeze 3-4 nights a week, sneezing in the mornings",
            findings="Scattered expiratory wheeze. Pale, boggy nasal mucosa.",
            diagnosis="Asthma, moderate persistent (not controlled). Allergic rhinitis. Aspirin sensitivity.",
            medicines=[
                ("Foracort 200 Rotacap", "1 inhalation", "Twice daily, rinse mouth after", "3 months"),
                ("Asthalin inhaler 100 mcg", "2 puffs", "When breathless (SOS)", "As needed"),
                ("Tab. Montair-LC", "1 tab", "At night", "1 month"),
            ],
            advice=[
                "Avoid aspirin and other painkillers like ibuprofen; use paracetamol",
                "Dust-mite precautions",
                "Inhaler technique demonstrated",
            ],
            follow_up="After 6 weeks with PEF diary",
        ),
    ]
    return p


def ramesh() -> Patient:
    p = Patient(
        13,
        "GMS-10243",
        "Mr.",
        "Ramesh",
        "Patil",
        D(1969, 9, 9),
        "male",
        "+91 94220 81356",
        "At post Ozar, Tal. Niphad, Dist. Nashik 422206",
        "B+",
        tags=["diabetes", "post-viral"],
        summary="57-year-old farmer recovering from COVID-19 viral pneumonia (CT severity 12/25) treated in September; diabetic and hypertensive; "
        "tapering prednisolone. Still breathless on exertion.",
    )
    p.conditions = [
        ("COVID-19 viral pneumonia, moderate", "U07.1", D(2026, 9, 21), "resolved"),
        ("Type 2 diabetes mellitus", "E11.9", D(2017, 1, 1)),
        ("Essential hypertension", "I10", D(2019, 1, 1)),
    ]
    p.allergies = []
    p.outside_meds = [
        ("Glycomet 500", "1 tab", "BD", "Type 2 diabetes", D(2017, 2, 1)),
        ("Amlong 5", "1 tab", "OD", "Hypertension", D(2019, 2, 1)),
        ("Wysolone 10", "1 tab", "OD", "Post-viral lung inflammation — tapering", D(2026, 9, 28)),
    ]
    ct = np.load(ASSETS / MANIFEST["ct_chest_covid_slices"]["file"])["hu"]
    when = D(2026, 9, 22)
    p.docs = [
        dicom(
            p,
            when,
            ct[0],
            source="ct_chest_covid_slices",
            modality="CT",
            study="HRCT CHEST",
            series="AXIAL LUNG 1.5 MM",
            body_part="CHEST",
            window=(-600, 1500),
            org=SAHYOG,
            spacing=(0.736, 0.736),
            thickness=1.5,
            accession="SS-CT-26-09224",
            label="HRCT chest - axial (upper)",
        ),
        dicom(
            p,
            when,
            ct[2],
            source="ct_chest_covid_slices",
            modality="CT",
            study="HRCT CHEST",
            series="AXIAL LUNG 1.5 MM",
            body_part="CHEST",
            window=(-600, 1500),
            org=SAHYOG,
            spacing=(0.736, 0.736),
            thickness=1.5,
            accession="SS-CT-26-09224",
            label="HRCT chest - axial (lower)",
        ),
        imaging(
            p,
            when,
            SAHYOG,
            "HRCT Chest (plain)",
            [
                ("Clinical details", "Fever and cough for 7 days, breathlessness, SpO2 91 %. RT-PCR positive for SARS-CoV-2."),
                (
                    "Findings",
                    "Multifocal peripheral and posterior ground-glass opacities with areas of consolidation and interlobular septal thickening "
                    "(crazy-paving) in both lungs, predominantly in the lower lobes. No pleural effusion. No mediastinal lymphadenopathy. "
                    "CT severity score: right upper 1, right middle 2, right lower 3, left upper 2, left lower 4 = 12/25.",
                ),
            ],
            [
                "Bilateral peripheral ground-glass opacities with consolidation — typical of COVID-19 viral pneumonia (CO-RADS 6).",
                "CT severity score 12/25 (moderate).",
            ],
            accession="SS-CT-26-09224",
            modality="CT (128-slice)",
            ref_by="Dr. Mahesh Bhamre",
        ),
        discharge(
            p,
            datetime(2026, 9, 21, 19, 30),
            datetime(2026, 9, 28, 12, 0),
            PANCHAVATI,
            ipd_no="IP/26/09/1774",
            consultant="Dr. Mahesh Bhamre, MD (Medicine)",
            department="General Medicine",
            diagnosis=[
                "COVID-19 viral pneumonia, moderate (CT severity 12/25)",
                "Type 2 diabetes mellitus with steroid-induced hyperglycaemia",
                "Hypertension",
            ],
            sections=[
                (
                    "Course in hospital",
                    "Required oxygen 2-4 L/min for 4 days. Treated with dexamethasone 6 mg daily for 7 days, enoxaparin prophylaxis "
                    "and insulin for steroid-induced hyperglycaemia. Weaned off oxygen on day 6. SpO2 95 % on room air at rest, 92 % after a 6-minute walk.",
                )
            ],
            investigations=[
                ("CRP", "84", "mg/L", "< 6"),
                ("Ferritin", "812", "ng/mL", "30 - 400"),
                ("D-dimer", "0.9", "µg/mL FEU", "< 0.5"),
                ("Total Leucocyte Count", "6.2", "10^3/µL", "4.0 - 11.0"),
                ("HbA1c", "8.3", "%", "4.0 - 5.6"),
            ],
            medicines=[
                ("Tab. Wysolone 10 mg", "1 tab", "Morning after breakfast", "Taper: 10 mg x 7 days, 5 mg x 7 days, stop"),
                ("Tab. Glycomet 500 mg", "1 tab", "Twice daily", "Continue"),
                ("Tab. Amlong 5 mg", "1 tab", "Morning", "Continue"),
                ("Tab. Pan 40 mg", "1 tab", "Before breakfast", "While on steroid"),
            ],
            advice=[
                "Check sugar twice daily while on steroid",
                "Breathing exercises and gradual walking",
                "Seek care if SpO2 falls below 93 %",
            ],
            follow_up="Physician review after 2 weeks; repeat chest imaging after 3 months if still breathless.",
            doctors=[("Dr. Mahesh Bhamre", "MD (Medicine), Consultant Physician")],
        ),
        lab(
            p,
            D(2026, 10, 12),
            PRAKRUTI,
            "Post-COVID follow-up profile",
            [
                (
                    "Inflammation",
                    [("CRP", "7.8", "mg/L", "< 6"), ("Ferritin", "356", "ng/mL", "30 - 400"), ("D-dimer", "0.42", "µg/mL FEU", "< 0.50")],
                ),
                ("Diabetes", [("Fasting glucose", "186", "mg/dL", "70 - 99")]),
                ("Kidney function", [("Serum Creatinine", "0.98", "mg/dL", "0.70 - 1.30"), ("Potassium", "4.3", "mmol/L", "3.5 - 5.1")]),
            ],
            lab_no="PP/1026/0912",
            ref_by="Dr. Mahesh Bhamre",
            hour=9,
        ),
    ]
    return p


def fatima() -> Patient:
    p = Patient(
        14,
        "GMS-10244",
        "Mrs.",
        "Fatima",
        "Sayyed",
        D(1987, 3, 3),
        "female",
        "+91 90490 77215",
        "Flat 9, Al-Huda Residency, Kondhwa, Pune 411048",
        "A-",
        tags=["anaemia", "gynaecology"],
        summary="39-year-old homemaker with heavy periods from an intramural fibroid causing iron-deficiency anaemia (Hb 8.9 → 10.6 on iron). Hypothyroid.",
    )
    p.conditions = [
        ("Iron deficiency anaemia", "D50.0", D(2026, 8, 11)),
        ("Uterine leiomyoma (intramural fibroid)", "D25.1", D(2026, 8, 14)),
        ("Heavy menstrual bleeding", "N92.0", D(2025, 12, 1)),
        ("Primary hypothyroidism", "E03.9", D(2020, 6, 1)),
    ]
    p.allergies = []
    p.outside_meds = [
        ("Orofer XT", "1 tab", "OD", "Iron deficiency anaemia", D(2026, 8, 14)),
        ("Thyronorm 25", "1 tab", "OD", "Hypothyroidism", D(2020, 7, 1)),
        ("Tranexamic acid 500 mg", "1 tab", "TDS", "Heavy periods — first 3 days of cycle", D(2026, 8, 14)),
    ]
    p.docs = [
        lab(
            p,
            D(2026, 8, 11),
            SANVITA,
            "CBC and iron studies",
            [
                (
                    "Haematology",
                    [
                        ("Haemoglobin", "8.9", "g/dL", "12.0 - 15.0"),
                        ("MCV", "68", "fL", "80 - 100"),
                        ("Platelet count", "412", "10^3/µL", "150 - 410"),
                        ("#", "Peripheral smear: microcytic hypochromic red cells with pencil cells and anisopoikilocytosis."),
                    ],
                ),
                ("Iron studies", [("Ferritin", "6", "ng/mL", "15 - 150", "CLIA"), ("Vitamin B12", "312", "pg/mL", "211 - 911")]),
                ("Thyroid", [("TSH", "3.4", "µIU/mL", "0.40 - 4.00")]),
            ],
            lab_no="SD/26/081133",
            ref_by="Dr. Rupa Shah",
        ),
        imaging(
            p,
            D(2026, 8, 14),
            MEDISIGHT,
            "USG Pelvis (transabdominal and transvaginal)",
            [
                ("Clinical details", "Heavy menstrual bleeding for 8 months, anaemia."),
                (
                    "Uterus",
                    "Anteverted, bulky (10.2 x 6.4 x 5.8 cm). A well-defined hypoechoic intramural fibroid in the posterior wall measuring 3.2 x 2.9 cm, "
                    "abutting but not distorting the endometrium (FIGO type 4). Endometrial thickness 9 mm, homogeneous.",
                ),
                ("Ovaries", "Both ovaries normal in size and echotexture. No adnexal mass. No free fluid."),
            ],
            ["Bulky uterus with a 3.2 cm posterior wall intramural fibroid (FIGO 4).", "Normal endometrium and ovaries."],
            accession="MI-US-26-08144",
            modality="Ultrasound",
            ref_by="Dr. Rupa Shah",
        ),
        prescription(
            p,
            D(2026, 8, 14),
            CLINIC_AASHA,
            ("Dr. Rupa Shah", "MD, DGO", "Consultant Gynaecologist"),
            vitals="BP 110/70 · Pulse 96/min · Weight 58 kg",
            complaints="Heavy periods with clots for 8 months, tiredness, breathlessness on stairs",
            findings="Pallor ++. P/A soft. P/V: uterus bulky, ~10 weeks size.",
            diagnosis="AUB-L (intramural fibroid) with iron-deficiency anaemia",
            medicines=[
                ("Tab. Orofer XT", "1 tab", "After lunch", "3 months"),
                ("Tab. Tranexamic acid 500 mg", "1 tab", "Three times daily during periods", "First 3 days of each cycle"),
                ("Tab. Thyronorm 25 mcg", "1 tab", "Empty stomach", "Continue"),
            ],
            advice=["Iron-rich diet; take iron 4 hours apart from the thyroid tablet", "Menstrual chart"],
            follow_up="After 2 months with CBC; discuss options for the fibroid",
        ),
        lab(
            p,
            D(2026, 10, 10),
            SANVITA,
            "CBC (follow-up)",
            [
                (
                    "Haematology",
                    [
                        ("Haemoglobin", "10.6", "g/dL", "12.0 - 15.0"),
                        ("MCV", "75", "fL", "80 - 100"),
                        ("Platelet count", "338", "10^3/µL", "150 - 410"),
                    ],
                ),
                ("Iron studies", [("Ferritin", "19", "ng/mL", "15 - 150")]),
            ],
            lab_no="SD/26/101017",
            ref_by="Dr. Rupa Shah",
            notes=["Improving haemoglobin and ferritin on oral iron."],
        ),
    ]
    return p


def suresh() -> Patient:
    p = Patient(
        15,
        "GMS-10245",
        "Mr.",
        "Suresh Babu",
        "Reddy",
        D(1958, 11, 19),
        "male",
        "+91 98490 22370",
        "Plot 31, Sector 27, Pradhikaran, Nigdi, Pune 411044",
        "O+",
        tags=["stroke", "diabetes", "hypertension"],
        summary="67-year-old retired engineer who had a right MCA ischaemic stroke in August with left-sided weakness, now walking with a stick. "
        "Diabetic and hypertensive; on clopidogrel and high-dose atorvastatin.",
    )
    p.conditions = [
        ("Ischaemic stroke, right MCA territory", "I63.511", D(2026, 8, 2)),
        ("Left hemiparesis (residual)", "I69.354", D(2026, 8, 2)),
        ("Essential hypertension", "I10", D(2009, 1, 1)),
        ("Type 2 diabetes mellitus", "E11.9", D(2012, 1, 1)),
        ("Dyslipidaemia", "E78.5", D(2026, 8, 2)),
    ]
    p.allergies = []
    p.outside_meds = [
        ("Clopilet 75", "1 tab", "OD", "Secondary stroke prevention", D(2026, 8, 24)),
        ("Atorva 80", "1 tab", "HS", "Secondary stroke prevention", D(2026, 8, 3)),
        ("Telma 40", "1 tab", "OD", "Hypertension", D(2010, 1, 1)),
        ("Glycomet 500", "1 tab", "BD", "Type 2 diabetes", D(2012, 2, 1)),
    ]
    when = D(2026, 8, 2)
    p.docs = [
        dicom(
            p,
            when,
            gray("ct_brain_ischaemic"),
            source="ct_brain_ischaemic",
            modality="CT",
            study="CT BRAIN PLAIN",
            series="AXIAL 5 MM BRAIN",
            body_part="HEAD",
            window=(128, 256),
            org=VEDANT,
            spacing=(0.45, 0.45),
            thickness=5,
            accession="VH-CT-26-08021",
            label="CT brain - axial",
        ),
        imaging(
            p,
            when,
            VEDANT,
            "CT Brain (plain)",
            [
                ("Clinical details", "Sudden left-sided weakness and slurred speech, onset about 9 hours before arrival."),
                (
                    "Findings",
                    "Ill-defined hypodensity with loss of grey-white differentiation in the right fronto-temporal region and insular cortex, "
                    "in the right middle cerebral artery territory, with mild effacement of adjacent sulci. No haemorrhage. "
                    "No midline shift. Ventricles and basal cisterns normal. Age-related small-vessel changes in the periventricular white matter.",
                ),
            ],
            [
                "Acute-to-subacute infarct in the right MCA territory. No haemorrhagic transformation.",
                "Chronic small-vessel ischaemic changes.",
            ],
            accession="VH-CT-26-08021",
            modality="CT (64-slice)",
            ref_by="Emergency department",
        ),
        imaging(
            p,
            D(2026, 8, 5),
            VEDANT,
            "Carotid Doppler",
            [
                (
                    "Findings",
                    "Right ICA: hypoechoic plaque at the origin causing about 40 % luminal narrowing (PSV 118 cm/s). "
                    "Left ICA: calcified plaque, less than 30 % narrowing. Both vertebral arteries show antegrade flow. CIMT 1.1 mm bilaterally.",
                )
            ],
            ["Right ICA plaque with ~40 % stenosis (not haemodynamically significant).", "Diffuse carotid atherosclerosis."],
            accession="VH-US-26-08052",
            modality="Duplex ultrasound",
        ),
        discharge(
            p,
            datetime(2026, 8, 2, 4, 50),
            datetime(2026, 8, 9, 13, 0),
            VEDANT,
            ipd_no="IP/26/08/0211",
            consultant="Dr. Nandini Iyer, DM (Neurology)",
            department="Neurosciences",
            diagnosis=[
                "Acute ischaemic stroke, right MCA territory (NIHSS 7 on admission, 3 at discharge)",
                "Hypertension",
                "Type 2 diabetes mellitus",
                "Dyslipidaemia",
            ],
            sections=[
                (
                    "Presenting complaints",
                    "Woke up with weakness of the left arm and leg and slurred speech; last seen well 9 hours earlier — outside the thrombolysis window.",
                ),
                (
                    "Course in hospital",
                    "Aspirin and clopidogrel (dual antiplatelet for 21 days) and atorvastatin 80 mg started. "
                    "Swallow assessment passed on day 2. Physiotherapy from day 2; walking with a stick and one-person support at discharge. "
                    "Echocardiography normal, no thrombus. 24-hour Holter: sinus rhythm, no atrial fibrillation.",
                ),
            ],
            investigations=[
                ("LDL cholesterol", "142", "mg/dL", "< 70"),
                ("HbA1c", "7.8", "%", "4.0 - 5.6"),
                ("Serum Creatinine", "1.08", "mg/dL", "0.70 - 1.30"),
                ("Haemoglobin", "13.6", "g/dL", "13.0 - 17.0"),
            ],
            medicines=[
                ("Tab. Ecosprin 75 mg", "1 tab", "After lunch", "21 days, then stop"),
                ("Tab. Clopilet 75 mg", "1 tab", "After breakfast", "Continue"),
                ("Tab. Atorva 80 mg", "1 tab", "At night", "Continue"),
                ("Tab. Telma 40 mg", "1 tab", "Morning", "Continue"),
                ("Tab. Glycomet 500 mg", "1 tab", "Twice daily", "Continue"),
            ],
            advice=[
                "Daily physiotherapy as taught",
                "BP target below 130/80; sugar monitoring",
                "Report new weakness, speech or vision problems immediately — call 108",
            ],
            follow_up="Neurology OPD after 3 weeks with lipid profile.",
            doctors=[("Dr. Nandini Iyer", "DM (Neurology), Consultant Neurologist")],
        ),
        lab(
            p,
            D(2026, 9, 25),
            SANVITA,
            "Lipid profile and HbA1c",
            [
                (
                    "Lipid profile",
                    [
                        ("Total cholesterol", "142", "mg/dL", "< 200"),
                        ("Triglycerides", "128", "mg/dL", "< 150"),
                        ("HDL cholesterol", "42", "mg/dL", "> 40"),
                        ("LDL cholesterol", "74", "mg/dL", "< 70"),
                    ],
                ),
                ("Diabetes", [("HbA1c", "7.1", "%", "4.0 - 5.6", "HPLC")]),
                ("Liver function", [("SGPT (ALT)", "38", "U/L", "7 - 56")]),
            ],
            lab_no="SD/26/092533",
            ref_by="Dr. Nandini Iyer",
        ),
    ]
    return p


PATIENTS = [gurpreet, ananya, ramesh, fatima, suresh]
