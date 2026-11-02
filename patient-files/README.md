# Patient files

Fifteen patient folders as a clinic would receive them: laboratory reports, imaging reports with the images (X-ray, ultrasound, CT and MRI — some as DICOM), ECG printouts, hospital discharge summaries and other doctors' prescriptions. `python -m app.seed demo` loads every folder into the application. Files under `To upload/` are left out so they can be uploaded during a walkthrough (for example by the front desk).

All people, organisations and reports are fictional. The medical images are real, de-identified images from openly licensed datasets; each folder's `IMAGE_SOURCES.md` lists the dataset, licence and citation. Rebuild with `backend/.venv/bin/python scripts/patient_files/build.py`.

| Folder | Patient | Documents |
|---|---|---|
| 01 - Rohit Verma (LCM-10231) | 69-year-old retired bank officer with diabetes, hypertension and BPH; sulfa allergy. Seen in September for fever and weight gain; thyroid and sugar tests since. Today: stomach pain for 2 days. | 6 |
| 02 - Harish Chandra Gupta (LCM-10232) | 74-year-old with permanent atrial fibrillation and heart failure (EF 35 %); admitted in August with fluid overload. On apixaban 5 mg twice daily although he weighs 58 kg and his creatinine is 1.6. | 7 |
| 03 - Sunita Deshmukh (LCM-10233) | 58-year-old schoolteacher with diabetes and hypothyroidism, admitted in August with right lower lobe pneumonia. Penicillin allergy (breathlessness and rash). | 5 |
| 04 - Abdul Rahman Shaikh (LCM-10234) | 55-year-old tailor on anti-tuberculosis treatment since June for left upper lobe pulmonary TB; diabetes found at diagnosis. Latest liver tests show ALT more than three times normal. | 5 |
| 05 - Priyanka Nair (LCM-10235) | 34-year-old software engineer, second pregnancy, about 20 weeks; hypothyroid on levothyroxine. Mild anaemia. Today: cough and cold for 4 days. | 4 |
| 06 - Aarav Kulkarni (LCM-10236) | 4-year-old (16 kg) treated for right-sided pneumonia this week by his paediatrician; brought by father for a second opinion on fever that is settling. | 4 |
| 07 - Meenakshi Iyer (LCM-10237) | 46-year-old bank manager with hypertension who found a lump in the left breast; ultrasound BI-RADS 3. Referred to a breast surgeon. | 4 |
| 08 - Kavita Joshi (LCM-10238) | 61-year-old with long-standing diabetes and diabetic kidney disease. eGFR has fallen from 46 to 36 over a year; still on metformin 1 g twice daily. Today: diabetes and kidney review. | 5 |
| 09 - Imran Qureshi (LCM-10239) | 29-year-old delivery rider with a distal forearm fracture after a two-wheeler fall; in a below-elbow cast. Allergic to ibuprofen (facial swelling). | 3 |
| 10 - Lakshmi Venkatesh (LCM-10240) | 66-year-old retired teacher whose headaches and a single seizure led to an MRI showing a right frontal convexity meningioma. On levetiracetam; awaiting elective surgery. | 6 |
| 11 - Gurpreet Singh Bains (LCM-10241) | 53-year-old transport business owner and smoker with exertional chest tightness. ECG shows lateral T-wave changes and the treadmill test was positive; angiography planned. On clopidogrel together with omeprazole. | 6 |
| 12 - Ananya Bose (LCM-10242) | 26-year-old UX designer with moderate persistent asthma and allergic rhinitis. Aspirin causes wheeze. | 5 |
| 13 - Ramesh Patil (LCM-10243) | 57-year-old farmer recovering from COVID-19 viral pneumonia (CT severity 12/25) treated in September; diabetic and hypertensive; tapering prednisolone. Still breathless on exertion. | 5 |
| 14 - Fatima Sayyed (LCM-10244) | 39-year-old homemaker with heavy periods from an intramural fibroid causing iron-deficiency anaemia (Hb 8.9 → 10.6 on iron). Hypothyroid. | 4 |
| 15 - Suresh Babu Reddy (LCM-10245) | 67-year-old retired engineer who had a right MCA ischaemic stroke in August with left-sided weakness, now walking with a stick. Diabetic and hypertensive; on clopidogrel and high-dose atorvastatin. | 5 |
