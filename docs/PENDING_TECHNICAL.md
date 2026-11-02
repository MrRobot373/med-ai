# GMS Clinical AI 3.0 — Engineering status and what remains

**Where it stands.** The commercial-product gaps found in the readiness assessment are built, tested and packaged for
**on-premise delivery in a Docker container** (`scripts/make-bundle.sh`). The remaining work is not more code: it is
**running the AI on a real model, medical review by named professionals, an independent security test, and a pilot
clinic** — see [What remains](#what-remains). The business side is in [PENDING_MANAGEMENT.md](PENDING_MANAGEMENT.md) and the
[compliance pack](compliance/README.md).

Tests at this version: **200+ backend**, 8 front-end unit, 6 browser end-to-end; lint and type checks clean.

## What was closed in this release

| Gap in the assessment | Now | Where |
|---|---|---|
| Prescription templates, favourites, repeat-last | Per-doctor and clinic-shared templates; ★ favourite medicines with their usual dose; most-used medicines; "same as last visit". They only fill the form — every line is still safety-checked | Prescription screen · `api/rxlib.py` |
| Medical certificate, fitness, referral letter, patient copy | Numbered (gap-free per year), immutable once issued, void with reason, QR-verifiable, on the clinic letterhead; referral pre-filled from the record; plain-language visit summary for the patient | Patient → Letters · `services/letters.py` |
| Doctor registration number on prescriptions | Profile fields (number, council, qualifications, signature image); printed on every prescription; **required to finalise in production** | Profile · `services/printing.py` |
| Custom letterhead and print | Paper size, text size, accent, logo, contact details, footer, what appears; **live server-rendered preview**; real PDFs (not browser print) | Settings → Letterhead & print |
| Branches | One install, several sites: per-branch letterhead data, day list, staff access, switcher; shared patient index | Settings → Branches |
| Patient import and duplicates | CSV/Excel wizard with mapping and per-row validation (nothing saved until confirmed); duplicate warning at registration; duplicate review; audited merge that moves records **and search vectors** | Patients → Import / Duplicates |
| Installer, updates, rollback | `install.sh` with preflight and key generation; `update.sh` (stop → verified backup → swap → health check → **automatic rollback**); `rollback.sh` | `deploy/` |
| Licensing and seat control | Ed25519-signed offline licence bound to the installation; seat/branch limits; never blocks patient care; usage report (counts only); vendor tool to issue licences | `tools/licence.py` · Settings → Licence |
| MFA, headers, encryption, lockout | TOTP + recovery codes, lockout, password policy, CSRF, CSP/HSTS, AES-256-GCM uploads and backups, hash-chained audit, ClamAV (fail-closed), production start-up guards | `SECURITY_OPERATIONS.md` |
| Backup tooling | Daily encrypted backups, retention, integrity **check**, CLI restore proven end-to-end, off-site script, crash recovery of half-processed documents | Settings → Backups |
| PyMuPDF (AGPL) | Replaced by pypdfium2 + reportlab (permissive); output verified identical on 57 real PDFs | `ingestion/pdf.py` |
| Billing and pharmacy | **Integrate, don't build**: scoped API keys, partner API, "dispensed" callback, signed webhooks, spreadsheet exports — see [BILLING_AND_PHARMACY.md](BILLING_AND_PHARMACY.md) | Settings → Integrations |
| Clinical sign-off | Fingerprint-bound approval by a named clinical lead and a different pharmacist, password-confirmed, blocked while a clinical test fails — see [CLINICAL_GOVERNANCE.md](CLINICAL_GOVERNANCE.md) | Settings → Clinical content |
| Rule test-bank and evaluation harness | 27 reviewable clinical cases (including "must stay quiet" cases); `python -m app.cli eval` measures extraction (**99.2 % recall / 96.3 % precision** on 21 real reports, 130 values), retrieval, abstention and grounding | `clinical/testbank.json` · `evals/` |

Found and fixed while measuring: three lab analytes that were not recognised (random blood glucose, absolute eosinophil count,
total IgE) and D-dimer; a path-handling hole in the backup-verify endpoint (admin-only, now names only).

## What remains

### Needs a GPU and a real model — **do this first** (T-01)
Everything that calls a language model was built and tested against the bundled test model. Run the full measurement on the
intended models and read the numbers:
`docker compose exec app python -m app.seed knowledge` then `docker compose exec app python -m app.cli eval`
(retrieval, abstention and grounding suites measure the configured models). Decide the supported model list and minimum
hardware per clinic size; add a repair path for malformed model JSON if the measured failure rate warrants it.
*Done when*: a written validation report with pass thresholds per feature.

### Needs people (no code can substitute) — see `CLINICAL_GOVERNANCE.md`
- A named **clinical lead** and **pharmacist** read and sign the rules and the reference library (3–4 days each, first time).
- **Formulary scale**: 114 generics / 32 interactions is a credible start for general outpatient practice, not complete.
  Grow it from the clinical reviewers' own most-prescribed list; every addition needs a test case.
- **Reference library**: 10 short notes today. Needs licensed or owned, clinically reviewed content.

### Needs a third party
- **Independent penetration test** (installer, update channel, partner API, the web app).
- **Design-partner clinic**: 4–8 weeks of real use, with usability observation and measured alert-override rates.

### Engineering work worth doing next (none blocks a pilot)
| Item | Size | Note |
|---|---|---|
| CI pipeline (tests, lint, type check, image build, a smoke test of install → update → rollback) | M | Build the bundle on every tag |
| Windows-native installer (`install.ps1`) | S–M | The Linux installer needs Docker; Windows clinics can use Docker Desktop manually today |
| Observability: metrics endpoint and a one-page health dashboard | M | Logs and `status`/`doctor` exist |
| Load test for the largest planned clinic (e.g. 30 concurrent users, 100 k patients) | M | SQLite in WAL mode is comfortable for a small clinic; measure before promising more, and keep PostgreSQL as the option for large groups |
| Appointment reminders (SMS/WhatsApp) | M | Needs a gateway and consent handling; a per-clinic decision |
| ABDM / ABHA linkage | L | Integration pattern already exists (scoped, audited, optional) |
| Drawn signature pad, digital signature certificate on PDFs | S–M | Signature image upload exists |
| Hindi / Marathi / Tamil UI and patient-copy languages | L | The visit summary is the highest-value first translation |
| E-prescription in HL7 FHIR for pharmacy partners | M | Data is structured; add a view to the partner API |

## Decided differently (not pending)

| Spec item | What happened |
|---|---|
| Web research (PubMed/FDA/SearXNG, research UI) | **Removed entirely** at the owner's request; the product works fully offline. |
| "Attached screenshots are the visual source of truth" | Replaced by the owner's later direction; the design is documented in `DESIGN.md`. |
| Multi-tenant SaaS | **Not built**: delivery is on-premise only, one clinic (or one group) per installation; branches cover multi-site. |
| Billing / pharmacy stock | **Integrate rather than build** — `BILLING_AND_PHARMACY.md`. |
| Demo accounts and "synthetic" labels | Removed; the demonstration build carries 15 realistic named patients ("Life Care Medico"). |
