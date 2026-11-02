# Patient-safety hazard log (DRAFT — for Clinical Lead and Pharmacist review)

Severity S (1 minor … 5 death) · Likelihood L (1 rare … 5 frequent) before and after the controls built in. Residual risk
must be accepted in writing by the Clinical Lead. This is the first pass; reviewers add hazards they think of.

| # | Hazard | Possible harm | Controls in the product | Residual | Remaining action |
|---|---|---|---|---|---|
| H1 | Wrong patient's chart opened or written to | Wrong prescription, missed allergy | Name + MRN + age shown in the chart header and on every print; identity check of uploaded reports (name/MRN/DOB mismatch quarantines the file); duplicate warning and audited merge | Low | Usability test of header prominence |
| H2 | Allergy not on file, or not matched | Allergic reaction | Allergy groups and cross-reactivity; critical alert needs a recorded reason; "unknown drug" is reported, not silent | Medium | Pharmacist review of groups; train staff to record allergies |
| H3 | Renal/hepatic/paediatric/elderly dose wrongly judged | Overdose, toxicity | eGFR from the latest result or calculated (labelled "calculated"); weight-based and age rules; missing facts are shown as "unknown" | Medium | Nephrology/geriatric review; validate against local labs |
| H4 | **Alert fatigue**: too many alerts, real one ignored | Missed critical alert | Severity tiers; "clean" test cases that must stay quiet; duplicate suppression | Medium | Measure alert override rates in the pilot clinic |
| H5 | Alert wrongly absent (false negative) | Unsafe prescription issued | 27+ clinical test cases; signed rules; update → re-sign | Medium | Grow the test bank from every reported miss |
| H6 | Drug name misread (look-alike brands) | Wrong medicine | Brand → generic resolved and shown on the prescription; formulary shows description | Medium | Pharmacist review of brand table |
| H7 | AI states something unsupported | Wrong decision | Answers must cite provided evidence or decline; invented citations stripped; AI output is a draft; measured abstention rate | Medium | **Validate with the real model** (`python -m app.cli eval`) |
| H8 | Lab value mis-extracted from a report | Wrong trend, wrong dose | Source excerpt and page kept with every value; flags recomputed; measured 99% recall / 96% precision on 21 reports | Medium | Human review step for uploaded results is mandatory in the workflow |
| H9 | Prescription altered after printing / forged | Fraud, wrong dispensing | Signed QR verification; issued prescriptions are immutable (void and reissue) | Low | — |
| H10 | Certificate issued in error or misused | Legal / welfare harm | Numbered, immutable, voidable with reason, verifiable | Low | — |
| H11 | System unavailable at the point of care | Delay | Offline-capable local server (no internet needed); backups; restore tested | Low | Written downtime procedure (paper prescriptions) at each clinic |
| H12 | Data loss | Loss of history | Daily encrypted backups, integrity check, off-site script, crash recovery | Low | Monthly restore test |
| H13 | Unauthorised access to records | Privacy harm | MFA, roles, lockout, audit chain, encryption | Low | Penetration test |
| H14 | Update breaks something | Wrong behaviour | Backup before update; automatic rollback; medical content re-sign | Low | Staging copy for large clinics |
| H15 | Clock or time zone wrong | Wrong dates on prescriptions | Time zone setting; installer checks clock sync | Low | — |
