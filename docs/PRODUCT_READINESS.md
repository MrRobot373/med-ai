# GMS Clinical AI — Product readiness for the market

This assesses GMS Clinical AI as **a product to be sold**, not as a demo or a pilot. The bar is: a clinic that
is not us installs it, pays for it, depends on it daily, and holds us accountable when it is wrong.

It replaces the "pilot-grade" framing used in the first version of the pending lists. Details live in
[PENDING_TECHNICAL.md](PENDING_TECHNICAL.md) and [PENDING_MANAGEMENT.md](PENDING_MANAGEMENT.md); what exists is in
[FEATURES.md](FEATURES.md).

---

## 1. Verdict

**GMS Clinical AI has a strong, differentiated core and is not yet a sellable product.**

- **The core is real and well built:** a doctor's AI co-pilot over the patient's *own* documents, with
  citations, a deterministic India-specific prescription safety engine, automatic matching of results to orders,
  wrong-patient quarantine, role separation, on-premise operation and white-labelling. About 11,000 lines of
  backend and 8,000 of frontend, 110 automated tests, a design system, a deployment guide.
- **Around the core, almost everything a customer pays for beyond the demo is missing:** validated medical
  content, proof the AI works on real models, security and privacy assurance, regulatory standing, a way to
  install, license, update and support it at other people's sites, and the everyday workflow features doctors
  expect from clinic software.

Rough shape of the distance to a first sale: **core ≈ built; product ≈ 40–60 engineer-weeks of further
engineering, plus clinical-content work, regulatory work and a customer-validation phase running in parallel.**
(An estimate with stated assumptions in §8, not a promise.)

A design-partner phase with real clinics is **part of getting to market** — it is how a clinical product is
validated before general sale — not an alternative to it.

---

## 2. Scorecard

🟢 sellable today · 🟡 present but incomplete · 🔴 missing or unproven

| # | Dimension | Status | Why |
|---|---|---|---|
| 1 | Core clinical value (AI chart review, co-pilot, citations) | 🟡 | Built end to end; **never run on a real model** |
| 2 | Medical content and safety (formulary, guidelines, scores) | 🔴 | 114 generics, 10 placeholder notes, no clinical sign-off |
| 3 | Doctor's daily workflow (speed, templates, letters, patient copy) | 🔴 | No prescription templates/favourites, no certificates/referrals, no patient copy |
| 4 | Clinic operations (multi-doctor, multi-site, import) | 🟡 | Multiple users and roles ✔; no multi-site, no import from existing systems, no patient-merge |
| 5 | Security and privacy engineering | 🔴 | No MFA, lockout, headers, encryption at rest; default secrets accepted |
| 6 | Reliability, scale, operations | 🔴 | SQLite/single process, no job recovery, no backups built in, no monitoring |
| 7 | Installability and updates | 🔴 | Docker/CLI only; no installer, no update mechanism, no health reporting |
| 8 | Commercial platform (licences, seats, billing for us, support tooling) | 🔴 | None |
| 9 | Interoperability (FHIR, ABDM, LIS, PACS, e-prescription sharing) | 🔴 | None |
| 10 | Regulatory and legal standing | 🔴 | No classification, privacy documents, contracts, insurance or certifications |
| 11 | Quality engineering (CI, coverage, load, accessibility, cross-browser) | 🟡 | 110 tests pass; no pipeline, no load or accessibility testing |
| 12 | Documentation, training, support material | 🟡 | Deployment guide, design system, film; no user manuals or runbooks |
| 13 | UX and design | 🟢 | Consistent design system, themes, role-aware screens; tablet/phone barely verified |
| 14 | Brand and sales assets | 🟡 | Film exists; needs disclaimers and credits, collateral, pricing |

Five reds in the engineering rows (2, 5, 6, 7, 8) plus the regulatory red (10) are the real gate.

---

## 3. The biggest strategic risk: deployment model and unit economics

This decides what you must build, so it must be settled before anything else.

The clinical model the product is designed around (MedGemma 27B) needs about **17 GB of GPU memory at 4-bit**
(a 24 GB GPU class machine); smaller models run on 8 GB at lower quality. A typical single-doctor clinic will not
buy and maintain a GPU server.

| Model | What it means | Consequences |
|---|---|---|
| **A. On-premise at the clinic** (today's design) | Strongest privacy story: "your data never leaves your building" | Hardware cost and support per site; only viable for hospitals, chains, polyclinics, or with a small model on modest hardware; installer, remote support and update tooling become essential |
| **B. Hosted by you (SaaS)** | Cheap to adopt, quick to onboard, one place to update | You become the **data processor** for every patient record (DPDP duties, DPAs, breach liability, security certifications); AI inference cost is yours; **multi-tenant architecture does not exist** — today's design is one database for one clinic (large rework) |
| **C. Hybrid**: records at the clinic, AI inference in your Indian cloud with de-identified or minimal context | Middle path | Needs a clear de-identification boundary, consent wording, and an audit of what is sent; more engineering, simpler hardware |

**Recommendation:** decide the primary model and first customer segment (D2, D4 in the management file), then
sequence work accordingly. A reasonable v1: **model A for hospitals/polyclinics/chains** (matches the privacy
promise and the existing architecture), with model C designed in so small clinics can follow.

---

## 4. What actually differentiates the product — and what does not

Be clear where to invest.

| Strong, hard to copy | Easy to copy |
|---|---|
| A **validated, India-specific safety knowledge base** (formulary, interactions, local brands) once it has real coverage and clinical sign-off | Generic chat over documents with citations — any competitor can wire this up |
| **Workflow glue**: results matched to the question the doctor asked; identity quarantine; pre-visit brief from the chart | Prompts and screen layouts |
| **Trust**: measured accuracy, published evaluation, clinical advisory board, regulatory standing | The film and design |
| **On-premise / offline** operation | |

Implication: the product's **moat is content and trust, not code.** Medical content (T-03, T-04) and
measured, published validation (T-01, T-02) are the most valuable engineering-adjacent investments.

Benchmark against the software your target doctors use today (examples in India include Practo, Eka Care,
HealthPlix, Bahmni and many local clinic systems — **their current features are not verified here**). Those
products typically include appointments with reminders, billing, patient communication, templates and
multi-language support, so doctors will treat those as expected.

---

## 5. Gaps a buyer will notice in the first hour

Verified absent in the code. Grouped by who notices.

### The doctor
| Gap | Why it matters |
|---|---|
| **No prescription templates, favourites or protocol sets** | Doctors write the same 20 prescriptions daily. Without one-click reuse the product is *slower* than paper. The single most important adoption feature. |
| No **medical certificate / fitness / referral letters**, **no patient-friendly visit summary** | Daily outputs of any clinic. |
| No way to **send the prescription to the patient** (PDF, WhatsApp, SMS, email) | Patients expect it; today it can only be printed. |
| Prescription print lacks the doctor's **registration number and qualifications** (legal requirement) | See management file §5. |
| No voice dictation, no regional languages | Heavy daily-use expectation in India. |
| Paediatric weight-based dosing exists for 44 of 114 medicines only; "no known allergies" cannot be recorded | Safety-feature completeness. |

### The front desk and clinic owner
| Gap | Why it matters |
|---|---|
| **No billing, receipts or pharmacy** (a deliberate choice — "co-pilot, not a management tool") | Most buyers run billing in another system. Decide to integrate (export, API, partner) or accept being an add-on. |
| No **patient merge / duplicate-patient detection** at registration | Duplicate charts are a daily real-world problem. |
| **No import** from the clinic's existing system or spreadsheets | Almost every sale starts with "can you bring my data?" |
| **Single clinic per install**; no multiple branches, doctors' calendars or per-site reporting | Chains and polyclinics need it. |
| No reminders (SMS/WhatsApp), no recall lists | Expected by clinic managers. |
| No letterhead/template customisation | Every clinic wants its own look on prints. |

### The IT buyer / hospital procurement
| Gap | Why it matters |
|---|---|
| No MFA, SSO (OIDC/LDAP), lockout, security headers, encryption at rest | Standard questionnaire items (T-06, T-23). |
| No certifications, penetration-test report, SBOM, DPA, SLA | Procurement blockers. |
| No backup/restore tooling or monitoring | Asked on day one. |
| No **installer or appliance image**, no **update mechanism**, no remote health reporting | Customer IT cannot be expected to run Docker commands; you cannot support what you cannot update. |
| No FHIR/ABDM, LIS, PACS integration | Hospitals integrate everything. |

### The patient
No patient-facing channel at all: no copy of prescription or reports, no reminders, no portal or app.

---

## 6. What a sellable v1.0 must contain

A focused scope beats a long list. Proposed **v1.0 "General Availability"** wedge:

> *AI-assisted chart review and prescription safety for Indian outpatient clinics and hospitals, run privately
> on the customer's own infrastructure.*

### v1.0 must have
1. **Trust:** measured results on real models (T-01), published evaluation (T-02), formulary and knowledge
   coverage with named clinical sign-off (T-03, T-04), hazard log and validation records (management §2, §4).
2. **Security and privacy baseline:** T-06, T-07, T-08, T-05 resolved; penetration test passed; DPDP-aligned
   documents; encrypted storage.
3. **Doctor speed:** prescription templates and favourites, repeat last prescription, certificates and referral
   letters, patient copy by PDF/WhatsApp/SMS/email, registration number on prints (new T-31, T-32, T-35, T-13).
4. **Clinic fit:** import from CSV/other systems, duplicate-patient detection and merge, letterhead
   customisation, two-language support at minimum (English + Hindi or Marathi) (new T-33, T-34, T-19).
5. **Deliverability:** one-command or guided installer, signed releases, update and rollback mechanism, backup
   and restore built in, health and version reporting, an admin "support bundle" export (new T-36, T-37, T-07).
6. **Commercial platform:** licence/activation with seats and expiry, offline-tolerant, usage metering you can
   invoice from, and a support process (new T-38, management §10).
7. **Legal and regulatory:** classification opinion and the path it implies, contracts (EULA, DPA, SLA), insurance,
   trademark (management §1, §3, §7, §8).
8. **Quality gates:** CI with security scanning, coverage targets, load and accessibility testing, cross-browser
   and tablet verification (T-09–T-12, T-24).

### Defer to v1.1+ (do not let these delay the first sale)
Voice consultation (T-17), FHIR/ABDM (T-14) unless a named customer requires it, multi-site (T-39) unless the
first customers are chains, billing, full multi-language beyond two languages, order sets, enterprise SSO
(unless demanded by the first hospital), the patient app.

### Re-think before building
Billing and pharmacy: either integrate through an export/API with the leading local systems, or decide the
product is deliberately an **add-on** that sits beside the clinic's existing system. This affects pricing and
the sales pitch more than any single feature.

---

## 7. GA exit criteria (the definition of "we can sell this")

All must be true:

| Area | Criterion |
|---|---|
| AI quality | Each AI feature meets written thresholds on the supported models (valid output ≥ target, citation validity ≥ target, hallucination ≤ target, abstains when evidence is missing); report published internally |
| Safety content | Formulary and knowledge coverage targets met; every rule set versioned, reviewed and signed; rule test-bank passes in CI |
| Security | Penetration test with no open high/critical findings; MFA, lockout, headers, encryption at rest; secrets cannot be defaults in production |
| Reliability | Tested backup and restore; documented recovery targets; job recovery after restart; load test at the target clinic size within agreed latency |
| Deliverability | A customer's IT can install, update, roll back and back up without engineering help, using documentation |
| Workflow | A doctor can complete a typical visit faster than on paper with templates; usability test (5–8 doctors) meets an agreed score |
| Commercial | Licences enforceable; contracts, SLA, DPA, insurance in place; support process staffed |
| Regulatory | Written classification and, if required, the licence/registration obtained |
| Privacy | DPDP-aligned notices, consent wording, retention and erasure procedures, breach plan |
| Evidence | At least one real-world validation (design-partner) with measured outcomes |

---

## 8. Effort and team (rough, with assumptions)

Assumptions: one product owner, a small senior team, existing code reused, content and regulatory work run by
specialists in parallel. Sizes use the scale in PENDING_TECHNICAL (S ≤ 1 wk, M ≈ 2–5 days → counted as 1,
L ≈ 2 weeks, XL ≈ 4+ weeks). These are **order-of-magnitude** figures.

| Workstream | Engineer-weeks (approx.) |
|---|---|
| Trust: real-model validation, evaluation suite, prompt hardening (T-01, T-02, T-25) | 4–6 |
| Security, privacy engineering, backups, reliability, observability (T-06–T-09, T-12) | 8–12 |
| CI/CD, test depth, accessibility, cross-browser (T-10, T-11, T-24) | 4–6 |
| PDF library replacement (T-05) | 1–2 |
| Doctor-speed features: templates/favourites, letters, patient copy, registration data, print customisation (T-13, new T-31–T-35) | 6–9 |
| Clinic fit: import, merge, two languages (T-19, new T-33, T-34) | 5–8 |
| Deliverability: installer, updates, support bundle, licensing and metering, onboarding (new T-36–T-38, T-40) | 7–11 |
| Imaging and chart completeness (T-15, T-16, T-20) | 5–7 |
| **Core product engineering total** | **≈ 40–62** |
| Interoperability: FHIR/ABDM/LIS (T-14) — if required | +6–12 |
| Multi-site / multi-tenant (new T-39) — if required | +8–16 |
| Formulary and knowledge content (T-03, T-04) | specialist effort: pharmacist and clinical reviewers, plus content licences — typically the longest lead time |
| Regulatory, legal, certifications | external consultants; duration depends on classification (can be the longest path) |
| Design-partner validation | 8–12 weeks of calendar time, overlapping the above |

**Team to sustain it:** product owner, 3–4 engineers (backend/AI, frontend, DevOps/security, QA), a part-time
clinical lead, a clinical pharmacist, a regulatory/quality person, a support/implementation lead.

---

## 9. Recommended order

1. **Decide** the deployment model, first segment and the regulatory path (management Step 0). Appoint the
   clinical lead.
2. **Trust and safety foundation** in parallel: real-model validation and evaluation (T-01, T-02) while the
   pharmacist and clinical reviewer start the formulary and knowledge work (T-03, T-04); resolve the PDF
   licence (T-05).
3. **Hardening and deliverability**: T-06–T-08, installer, updates, backups, CI (T-10), licensing.
4. **Doctor speed and clinic fit**: templates, letters, patient copy, import, merge, languages.
5. **Design partners** (2–3 clinics) on release candidates: measure, fix, repeat.
6. **Assurance**: penetration test, regulatory outcome, contracts, insurance, support readiness.
7. **GA** against the exit criteria in §7, then the v1.1 list.

What I can start immediately is listed in PENDING_TECHNICAL ("What I can do next"); the new commercial items below
extend that list.
