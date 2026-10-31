# GMS Clinical AI — Pending management, regulatory and business work

The items here cannot be solved by writing code. They are decisions, approvals, certifications, legal
documents, clinical governance and operations that must exist before the product is used on real patients
or sold to clinics and hospitals. Engineering items are in [PENDING_TECHNICAL.md](PENDING_TECHNICAL.md); what is
built is in [FEATURES.md](FEATURES.md).

> **Important.** This is a planning checklist prepared from engineering knowledge, **not legal or regulatory
> advice**. Laws, rules and notified dates change. Every item marked **(verify)** must be confirmed with a
> qualified regulatory consultant or lawyer before you rely on it. The most valuable first step is a single
> meeting with a medical-device regulatory consultant and a healthcare lawyer (see [Step 0](#step-0--decisions-only-you-can-make)).

**Where the product stands.** Pilot-grade software, never used with real patients, never run against a real
clinical AI model, with no regulatory classification, no privacy documentation, no clinical validation, and no
certifications. The demo is safe to show because every patient in it is fictional.

---

## Contents

0. [Decisions only you can make](#step-0--decisions-only-you-can-make)
1. [Regulatory status of the software](#1-regulatory-status-of-the-software)
2. [Quality management and safety standards](#2-quality-management-and-safety-standards)
3. [Privacy and data protection](#3-privacy-and-data-protection)
4. [Clinical governance and validation](#4-clinical-governance-and-validation)
5. [Healthcare-specific rules](#5-healthcare-specific-rules)
6. [Information-security assurance](#6-information-security-assurance)
7. [Legal, licensing and intellectual property](#7-legal-licensing-and-intellectual-property)
8. [Insurance and liability](#8-insurance-and-liability)
9. [Public release of the film and marketing](#9-public-release-of-the-film-and-marketing)
10. [Operations: support, training, incident response](#10-operations-support-training-incident-response)
11. [Pilot plan](#11-pilot-plan)
12. [Business readiness](#12-business-readiness)
13. [Indicative sequence and owners](#13-indicative-sequence-and-owners)

Owner key: **Founder** · **Clinical lead** (a practising doctor who signs off medical content) ·
**Pharmacist** · **Regulatory** (consultant) · **Legal** · **Security** · **Engineering** · **Ops**.

---

## Step 0 — Decisions only you can make

Almost every item below depends on these answers. Write them down first.

| # | Decision | Why it matters |
|---|---|---|
| D1 | **Intended use statement** — one paragraph: who uses it, for what, what it does *not* do. | Decides whether the software is a regulated medical device (§1). |
| D2 | **Who runs it?** The clinic runs it on its own server, or you host it for clinics. | Decides who is "data fiduciary" and who is "processor" (§3), insurance (§8), security obligations (§6). |
| D3 | **Which markets?** India only, or also elsewhere. | Different rules (e.g. EU MDR, US FDA, GDPR/HIPAA). The formulary is India-only today. |
| D4 | **Business model and first customers** — single clinics, hospitals, chains. | Hospitals ask for far more assurance (§6, §12). |
| D5 | **Which AI models and under which licences** — MedGemma and others. | Their licence terms flow into your contracts (§7). |
| D6 | **PDF library** — buy the PyMuPDF commercial licence or replace it. | AGPL conflict (§7). Engineering item T-05. |
| D7 | **Who is the clinical lead?** A named, registered doctor accountable for medical content. | Required by almost every clinical-governance step (§4). |
| D8 | **Is "Life Care Medico" a real organisation?** Yours, a partner's, or invented? | The film and demo use the name publicly (§9). |

---

## 1. Regulatory status of the software

**Question to answer:** is GMS Clinical AI a *medical device* (software as a medical device, SaMD), or an
administrative/records tool outside device regulation?

**Why it is not obvious.** The product organises records (not regulated on its own) but also *checks
prescriptions for allergy, dose, kidney and interaction problems*, *suggests diagnoses to consider and red flags*,
*reads investigation reports against a clinical question* and *computes clinical scores* (CKD stage,
CHA₂DS₂-VASc, anticoagulant dose criteria). Software that provides information used to make or inform clinical
decisions can fall under device rules depending on its intended use and the claims made. The doctor is always
in the loop, which weighs in your favour but does not decide the question. **(verify)**

| Task | Owner | Output |
|---|---|---|
| Write the intended-use statement and a list of *claims you will and will not make* (D1) | Founder + Clinical lead | One-page document |
| Obtain a **written regulatory opinion**: is it a device under the **Medical Devices Rules, 2017** (CDSCO), and if so which risk class? Use the IMDRF SaMD risk framework as the reference | Regulatory | Opinion letter |
| Decide strategy: (a) keep features within a non-device scope; (b) register as a device; (c) split the product (records/AI assistant vs. dose/score checking) | Founder + Regulatory | Strategy memo |
| If a device: CDSCO registration/licensing route, classification, technical file, labelling, instructions for use | Regulatory | Licence/registration (months — get a quote and timeline) |
| If targeting other markets: CE marking under EU MDR (software Rule 11), FDA clinical decision support guidance | Regulatory | Per-market plan |

Until this is answered, **do not market any feature as diagnosing, treating or preventing disease**, and keep
the on-screen disclaimer ("Clinical decision support — AI output must be reviewed by the treating clinician").

---

## 2. Quality management and safety standards

If the software is a device — or if hospital customers ask for evidence of safe development — these are the
standards normally applied. Several can be adopted gradually even if registration is not required.

| Standard | What it covers | What you would need |
|---|---|---|
| **ISO 13485** | Quality management system for medical devices | Documented QMS: design controls, document control, supplier control, CAPA, internal audits; certification audit |
| **IEC 62304** | Software lifecycle; safety class A/B/C | Development plan, requirements, architecture, verification, release and maintenance records; a software bill of materials |
| **ISO 14971** | Risk management | **Hazard log** (e.g. wrong dose not flagged, wrong-patient document accepted, AI hallucinated citation, missed critical result), controls, residual-risk acceptance |
| **IEC 62366-1** | Usability engineering | Use-error analysis; **summative usability test** with real doctors and front-desk staff |
| **IEC 82304-1** | Health software product safety | Product-level requirements and validation |
| **IEC 81001-5-1** | Security in the health-software lifecycle | Threat model, security requirements, patch process |
| **ISO/IEC 27001** | Information security management | See §6 |

**Already helpful, but not sufficient:** automated tests, an audit log, a deterministic rules engine, source
citations, patient isolation, and the design principles in DESIGN.md. None of this is yet written up as
controlled documents.

| Task | Owner |
|---|---|
| Start a **hazard log** now (cheap; useful even if not regulated) | Clinical lead + Engineering |
| Write a software development and release procedure; keep records per release | Engineering |
| Plan and run a usability test with 5–8 real users | Clinical lead + Engineering |
| Decide whether to pursue ISO 13485 / IEC 62304 certification (depends on §1) | Founder |

---

## 3. Privacy and data protection

Patient records are sensitive personal data. Treat privacy as a pre-condition for any pilot.

| Item | Detail | Owner |
|---|---|---|
| **Digital Personal Data Protection Act, 2023 and its Rules** | Notice and consent, purpose limitation, data-principal rights (access, correction, erasure, grievance), duties on data fiduciaries, breach notification to the Board and affected persons, children's data (verifiable parental consent), possible Significant Data Fiduciary obligations. The Rules were notified in late 2025 with phased commencement — **confirm the dates and requirements that apply to you (verify)** | Legal |
| **Roles** | If the clinic runs it on its own server: the clinic is the data fiduciary and you are a supplier. If *you* host it: you are a data processor and need a **Data Processing Agreement** per customer | Legal |
| **IT Act 2000 (s.43A) and SPDI Rules 2011** | Reasonable security practices for sensitive personal data; check how they interact with the DPDP regime **(verify)** | Legal |
| **Data Protection Impact Assessment** | Describe data flows (what is stored, where, who sees it, what leaves the clinic — note that a non-local AI endpoint receives patient context), risks and mitigations | Security + Legal |
| **Consent** | Patient notice and consent for digital records and AI-assisted processing. *The product has no consent capture today* (technical item) — decide the legal basis and the wording first | Legal + Clinical lead |
| **Privacy policy and notices** | For clinics' patients and for staff users | Legal |
| **Retention and erasure** | A retention schedule (medical-record retention rules apply — the older Indian Medical Council regulations require patient records to be kept for at least 3 years; check current NMC and state rules **(verify)**); a documented erasure procedure (today deletion is permanent and immediate) | Legal + Clinical lead |
| **Cross-border data** | Keep data in India unless a lawful basis exists; know where any cloud AI endpoint runs | Legal + Security |
| **Breach response** | A written plan with who decides, who is notified and within what time; link to CERT-In reporting (§6) | Security |
| **Grievance officer** | Named contact for data-principal complaints | Founder |
| **Aadhaar / ABHA** | If these identifiers are ever collected, additional restrictions apply | Legal |

---

## 4. Clinical governance and validation

The safety of this product depends on the medical content and on how doctors use it. Someone qualified must own both.

| Item | Detail | Owner |
|---|---|---|
| **Clinical lead (D7)** | A named registered doctor accountable for medical content, with authority to stop a release | Founder |
| **Formulary sign-off** | The rule data (doses, kidney/liver thresholds, Beers, interactions, allergy groups) must be reviewed and signed by a clinical pharmacologist/pharmacist, with a version and review date; a **test bank** of prescriptions with expected findings (technical item T-03) | Pharmacist |
| **Knowledge-library sign-off** | Every guideline added has a reviewer, source, version and review date | Clinical lead |
| **Score validation** | Independent check of CKD, CHA₂DS₂-VASc, glycaemic, metformin and apixaban logic against the source criteria | Clinical lead |
| **AI validation protocol** | Written acceptance thresholds for each AI feature on the chosen model (valid output rate, citation accuracy, hallucination rate, abstention); results reviewed by the clinical lead (technical items T-01, T-02) | Clinical lead + Engineering |
| **Model and prompt change control** | Any change of model, prompt or formulary version re-runs the validation set and is approved before release | Engineering + Clinical lead |
| **Clinical evaluation / pilot study** | Structured pilot with predefined measures (§11). If it is run as research on patient data, **ethics committee approval** and informed consent are required; follow the **ICMR *Ethical Guidelines for Application of AI in Biomedical Research and Healthcare* (2023)** **(verify)** | Clinical lead |
| **Acceptable-use policy for doctors** | "The AI is a draft; you are responsible; verify against the cited source"; what to do when it is wrong; no entry of data outside the system | Clinical lead |
| **Incident and near-miss reporting** | A log and a review meeting; severe events trigger a stop-and-investigate rule | Clinical lead + Ops |
| **Clinical advisory board** | 2–3 independent clinicians who review the product quarterly | Founder |

---

## 5. Healthcare-specific rules

| Area | What to check | Owner |
|---|---|---|
| **Prescription content** | Registered medical practitioner's name, qualifications and **registration number**; patient details; date; generic names; legibility — the prescription print does not yet carry the registration number (technical item T-13). Check current **NMC** regulations on prescribing **(verify)** | Legal + Clinical lead |
| **Controlled and scheduled drugs** | Drugs and Cosmetics Rules (Schedules H, H1, X) and the NDPS Act: decide whether the system may prescribe them, and what extra controls apply **(verify)** | Legal + Pharmacist |
| **Electronic prescriptions and signatures** | Legal validity of an electronic prescription and of any digital signature under the IT Act | Legal |
| **Telemedicine** | The product is designed for in-clinic use. If remote consultation is added, the **Telemedicine Practice Guidelines (2020)** apply **(verify)** | Legal |
| **Clinical Establishments Act and state rules** | These apply to the clinics that use the software (record-keeping, registration); your customers will ask how you help them comply | Legal |
| **NABH and hospital accreditation** | Accredited hospitals will ask how the system supports their documentation and information-management requirements | Founder + Clinical lead |
| **ABDM (Ayushman Bharat Digital Mission)** | Optional but strategically important in India: ABHA linking, becoming a health-information provider/user, the sandbox and milestone certifications run by the National Health Authority (technical item T-14) | Founder |

---

## 6. Information-security assurance

Hospitals and larger clinics will send a security questionnaire. Be ready to answer it truthfully; today several
answers would be "not yet" (see technical item T-06).

| Item | Detail | Owner |
|---|---|---|
| **Vulnerability assessment and penetration test (VAPT)** | By an independent firm, ideally **CERT-In empanelled**; fix findings; keep the report | Security |
| **ISO/IEC 27001 certification** | Information security management system; common requirement from hospitals and enterprises | Security |
| **SOC 2** | Sometimes asked by international or enterprise customers; less common in India | Security |
| **CERT-In Directions (2022)** | Incident reporting within 6 hours of noticing; log retention for 180 days; time synchronisation **(verify)** | Security |
| **Hosting** | If you host: Indian data centre, tenant isolation, encrypted storage and backups, access control, monitoring; for any public-sector customers, check cloud empanelment rules **(verify)** | Security + Ops |
| **Policies** | Access control, password and MFA, acceptable use, change management, supplier management, secure development, logging, backup, business continuity | Security |
| **Staff** | Background checks and confidentiality agreements for anyone with data access; security training | Founder |
| **Supplier management** | Which sub-processors see patient data (cloud, AI endpoints, support tools) | Security + Legal |

---

## 7. Legal, licensing and intellectual property

| Item | Detail | Owner |
|---|---|---|
| **Company and contracts** | Terms of service / end-user licence; master services agreement; SLA; data processing agreement; limitation of liability and indemnities; support terms; warranty disclaimers (clinical decisions remain the doctor's) | Legal |
| **Trademark** | Search and register **"GMS Clinical AI"** and the logo (software and healthcare classes). Confirm you own the red striped **GMS** logo artwork | Legal |
| **"Life Care Medico" (D8)** | Confirm it is yours or obtain written permission; check for confusingly similar real clinics before using it publicly | Legal |
| **PyMuPDF — AGPL-3.0 (D6)** | The PDF library is AGPL. Offering the product to others (including as a hosted service) without releasing your source under AGPL needs the **Artifex commercial licence**, or replacing the library (technical item T-05) | Founder + Legal |
| **AI model licences (D5)** | **MedGemma** is released under Google's *Health AI Developer Foundations* terms: confirm commercial use, redistribution, prohibited uses (including any restriction on use as a regulated medical device), and attribution **(verify)**. **Qwen** and other models: confirm the licence for the specific size you ship. If you point customers at hosted AI endpoints, their terms and data handling apply | Legal |
| **Dataset licences** | The 15 demo patients use real, de-identified images from open datasets: NIH ChestX-ray14, Kermany pneumonia (CC BY 4.0), BUSI (CC BY 4.0), HC18 (CC BY 4.0), FracAtlas (CC BY 4.0), Shenzhen (US NLM), TEKNOFEST 2021 CT (Apache 2.0 mirror), COVID-19 CT (CC BY 4.0), PTB-XL ECG (CC BY 4.0), Brain Tumor MRI (CC0). **CC BY requires credit to the authors and a licence link wherever the images are shown or published**; credits are in each folder's `IMAGE_SOURCES.md` | Founder |
| **Reference photos of medicines** | If the optional Wikimedia Commons lookup is enabled, each photo has its own licence and author credit; keep it off for commercial deployments unless attribution is displayed | Legal |
| **Fonts, icons, sounds** | Inter and Liberation Sans (SIL OFL), Lucide icons (ISC), Pixabay sound effects (Pixabay licence) — all permit commercial use; keep `THIRD_PARTY_NOTICES.md` current and generate a full software bill of materials | Engineering |
| **Voice and music for the film** | The ElevenLabs plan used must permit **commercial use** of the voice and any generated music; keep the licence/plan record | Founder |
| **Drug and guideline content** | Commercial drug databases and guideline PDFs are copyrighted; licences must cover embedding into a product and (if hosted) redistribution | Legal |
| **Open-source compliance** | Review every dependency licence once (the notices file lists them); check nothing else is copyleft | Engineering |

---

## 8. Insurance and liability

| Cover | Why |
|---|---|
| **Professional indemnity / errors and omissions** (technology) | Claims that the software gave wrong output |
| **Product liability** | If treated as a medical device or if harm is alleged |
| **Cyber liability** | Data breach costs, notification, regulatory response |
| **General commercial liability** | Standard |
| **Clinicians' own cover** | Doctors using decision support should confirm their professional indemnity covers it |

Ask a broker specifically about **AI and clinical-software exclusions** before buying.

---

## 9. Public release of the film and marketing

You said the video is going out to the world. Before it is published:

| Check | Detail | Status |
|---|---|---|
| **"Fictional patients" notice** | Every patient, doctor and clinic shown is fictional (the images are real de-identified dataset images). Say so on screen or in the description | **Not in the current film** — fix (technical item T-28) |
| **Image credits** | Credit the dataset authors with licence links (CC BY 4.0) in the video description or end credits | **Not yet** |
| **Claims** | The film says "Every report, read. Every decision, yours." — keep claims factual; avoid "never misses", "reduces errors", "improves outcomes", "diagnoses" until you have evidence and a regulatory position (§1). Advertising of health products and services is subject to advertising-standards codes (ASCI) **(verify)** | Review before publishing |
| **AI output** | The AI text shown comes from a test AI that assembles text from reports; it is not a clinical model. Do not describe the film as showing clinical AI reasoning. Add "interface demonstration" wording | Decide wording |
| **Real clinic and real doctors** | If "Life Care Medico" or "Dr. Ananya Rao" resemble real people or organisations, confirm there is no conflict (D8). Doctors endorsing products are restricted by medical-council ethics — do not imply a real doctor's endorsement | Check |
| **Voice and music** | Licences as in §7 | Pending recording |
| **Logo and brand** | Confirm trademark position (§7) | Pending |

---

## 10. Operations: support, training, incident response

| Item | Detail | Owner |
|---|---|---|
| **Support model** | Channels, hours, severity levels, response and resolution targets, escalation path, who is on call | Ops |
| **Release management** | Version numbers, release notes, change approval, maintenance windows, rollback plan, customer notice for updates | Engineering + Ops |
| **Business continuity** | Recovery point and recovery time targets, tested backup restore (technical item T-07), what clinics do during downtime (paper fall-back) | Ops |
| **Incident response plan** | Roles, severity levels, communication templates, evidence handling, post-incident review; links to §3 and §6 | Security + Ops |
| **Training** | Role-specific training: doctors (how to read AI drafts critically, override reasons), front desk (registration, uploads, identity quarantine), admins (users, models, backups); slides, short videos, quick-reference cards | Clinical lead + Ops |
| **User manuals** | One per role; the product film can be the first training asset | Engineering + Clinical lead |
| **Implementation checklist per clinic** | Hardware, network, server install, data migration from existing records, user accounts, go-live support, sign-off | Ops |
| **Hardware specification** | Server and GPU guidance per clinic size, from the model validation (technical item T-01) | Engineering |
| **Customer success and feedback loop** | Regular check-ins; the in-product feedback data reviewed monthly | Ops |

---

## 11. Pilot plan

A small, supervised pilot is the safest next step and produces the evidence for everything above.

| Element | Suggestion |
|---|---|
| Scope | 1 clinic, 2–3 doctors, 1 front-desk user, 8–12 weeks, existing records kept in parallel |
| Preconditions | §3 privacy basics and consent wording; §4 clinical lead and formulary/knowledge sign-off; technical P0 items T-01, T-05, T-06, T-07; ethics approval if run as a study; staff trained (§10) |
| Measures decided in advance | Time to review a chart; time to write a prescription; number and type of safety findings raised and how often the doctor agreed; wrong-patient documents caught; AI draft accept/reject rates; usability score (e.g. SUS); adoption; incidents and near-misses |
| Governance | Weekly review with the clinical lead; incident log; a stop rule (what finding ends the pilot) |
| Exit | Written report, go / no-go criteria, plan for data return or deletion |

---

## 12. Business readiness

| Item | Detail | Owner |
|---|---|---|
| **Target customer and problem statement** | Which clinics, which pain, what they use now (D4) | Founder |
| **Pricing and packaging** | Per doctor / per clinic / per month; what hardware and AI hosting cost; implementation fee | Founder |
| **Evidence for value** | Pilot results (time saved, safety catches) — required before you claim ROI | Founder + Clinical lead |
| **Competitive landscape** | Existing Indian clinic software and AI scribes; positioning | Founder |
| **Sales collateral** | The film, a short deck, a one-page security and privacy summary, a feature sheet (FEATURES.md can seed it) | Founder |
| **Procurement documents** | Company registration, GST, bank, standard quotation and contract templates, security questionnaire answers | Founder + Legal |
| **Roadmap and ownership** | Who maintains clinical content, models and infrastructure after launch; budget | Founder |

---

## 13. Indicative sequence and owners

Durations depend heavily on the regulatory outcome; treat this as order, not a schedule.

| Phase | What | Owners |
|---|---|---|
| **0 · Decide** | D1–D8; engage a regulatory consultant and a healthcare lawyer; appoint the clinical lead | Founder |
| **1 · Foundations** | Regulatory opinion; privacy documents (DPIA, notices, consent wording, DPA); start hazard log and development procedure; resolve PyMuPDF licence; trademark search; model licence review | Regulatory, Legal, Engineering |
| **2 · Make it safe to pilot** | Engineering hardening (T-06, T-07, T-08, T-05); real-model validation and evaluation suite (T-01, T-02); formulary and knowledge sign-off (T-03, T-04); insurance quote; support and incident procedures | Engineering, Pharmacist, Clinical lead, Ops |
| **3 · Pilot** | Ethics approval if needed; training; 8–12 week supervised pilot; collect measures | Clinical lead, Ops |
| **4 · Assurance** | VAPT; ISO 27001 / 13485 / 62304 as decided in §1–2; usability study; corrective actions | Security, Regulatory |
| **5 · Launch** | Device registration if required; contracts and SLAs; public marketing with the film (after §9 fixes); ABDM work if chosen | Founder, Legal |

**Do not skip Phase 1 and 2 before putting the product in front of real patients.** The demo can be shown at any time.
