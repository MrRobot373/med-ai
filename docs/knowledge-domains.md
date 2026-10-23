# Knowledge domains — what to put in the library

Each library document has a **domain** (specialty). Domains let clinicians scope Guideline
Q&A, keep the library navigable, and make it obvious where coverage is thin. The UI offers
the taxonomy below; any custom domain can be added at upload time.

## Suggested taxonomy

| Group | Domains | High-value content to add |
|---|---|---|
| **Medicine** | General / Internal Medicine | Chronic disease follow-up protocols, preventive care schedules, discharge criteria |
| | Cardiology | Hypertension, heart failure (GDMT), AF anticoagulation, ACS pathways, lipid targets |
| | Endocrinology & Diabetes | Type 1/2 diabetes, insulin titration, thyroid disorders, adrenal, osteoporosis |
| | Nephrology | CKD staging/management, AKI, electrolytes (K⁺, Na⁺), dialysis, renal drug dosing |
| | Pulmonology & Respiratory | Asthma (GINA), COPD (GOLD), pneumonia, PE, oxygen therapy |
| | Gastroenterology & Hepatology | GI bleed, IBD, liver disease, NAFLD, H. pylori |
| | Infectious Disease | Antibiotic stewardship / local antibiogram, sepsis bundles, TB, HIV, vaccination |
| | Hematology | Anaemias, anticoagulation reversal, transfusion thresholds, VTE |
| | Oncology | Regimen references, neutropenic fever, screening guidelines |
| | Rheumatology | RA, gout, lupus, steroid tapering |
| | Neurology | Stroke pathways, epilepsy, headache, dementia |
| | Psychiatry & Mental Health | Depression, anxiety, suicide-risk assessment, antipsychotic monitoring |
| | Dermatology | Eczema, psoriasis, skin lesion triage |
| | Geriatrics | Falls, polypharmacy / deprescribing (Beers, STOPP/START), delirium |
| **Surgical & specialty** | Ophthalmology | Glaucoma, diabetic retinopathy, cataract, AMD (starter pack included) |
| | ENT / Otolaryngology | Sinusitis, hearing loss, airway |
| | General Surgery | Peri-operative protocols, surgical prophylaxis, ERAS |
| | Orthopedics | Fracture management, joint replacement pathways |
| | Urology | BPH, stones, UTI |
| | Obstetrics & Gynecology | Antenatal care, gestational diabetes, pre-eclampsia, contraception |
| | Pediatrics & Neonatology | Weight-based dosing, growth, immunisation schedules, fever |
| **Acute care** | Emergency & Critical Care | Triage, resuscitation, toxicology, sepsis, ICU protocols |
| | Anesthesiology & Pain | Pre-op assessment, analgesic ladders, opioid conversion |
| **Diagnostics** | Radiology & Imaging | Reporting standards, contrast safety, incidental-finding guidance |
| | Pathology & Laboratory Medicine | **Your lab's reference ranges**, critical-value lists, specimen requirements |
| **Cross-cutting** | Pharmacology & Drug Reference | Formulary, interactions, renal/hepatic dose adjustment, high-alert drugs |
| | Nursing & Care Protocols | Early-warning scores, wound care, line care |
| | Nutrition & Dietetics | Renal/diabetic diets, enteral feeding |
| | Public Health & Preventive Care | Screening programmes, vaccination policy |
| | Hospital Policies & SOPs | Consent, escalation, infection control, documentation standards |

## Recommendations

1. **Start where your patients are.** Seed the 3–5 domains your clinicians use daily, plus
   *Pharmacology* and *Pathology & Laboratory Medicine* (local reference ranges and critical
   values make lab answers far more precise).
2. **Prefer your institution's approved documents** over generic summaries. Record the
   publisher in *Source* and the edition in *Version*; deactivate superseded versions
   instead of deleting them, so the audit trail stays intact.
3. **Format matters.** Text PDFs, DOCX and Markdown with clear headings chunk best. Scanned
   PDFs work (read by the vision model) but are slower. Structured data can be a JSON list
   of records (one section per record — see `knowledge-packs/ophthalmology/eye_conditions.json`).
4. **Check coverage** with the Retrieval playground: ask the questions clinicians ask and
   confirm the right passages come back before relying on them.

To ship a pack with the code, add files under `knowledge-packs/<domain-folder>/` and run
`python -m app.seed knowledge`.
