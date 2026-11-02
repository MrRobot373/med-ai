# Digital Personal Data Protection Act, 2023 — readiness mapping (DRAFT)

*Review by a data-protection lawyer. The Act's Rules were being phased in when this was written; confirm current dates and text.*

## Roles

On an **on-premise** installation the **clinic is the Data Fiduciary**: it decides why and how patient data is processed,
and the data never leaves its server. The vendor is **not** a processor for day-to-day operation (it does not host or
access the data). The vendor *becomes* a processor only when its staff access an installation for support — covered by the
terms in `TERMS_DRAFT.md` (access only on the clinic's request, supervised, logged, no copying of patient data).
Health data is sensitive in practice; treat all of it with the highest care even where the Act does not distinguish.

## Obligations → what the product does → what the clinic does

| Obligation | Product | Clinic |
|---|---|---|
| Lawful purpose; consent or legitimate use for care | Registration form records only care-related data; notice text below | Display the notice at reception; record consent where the clinic's counsel requires it |
| Notice (what, why, rights, contact) | — | Use the text below on a poster / the registration form |
| Data minimisation / purpose limitation | Optional fields; roles limit who sees what (front desk cannot read clinical content); branch-scoped worklists | Give each person the lowest role that works |
| Accuracy; correction | Charts are editable with an audit trail; letters/prescriptions are corrected by voiding and reissuing, never silently edited | Handle correction requests (below) |
| Retention limit and erasure | Admin-only permanent deletion of a patient; merge of duplicates; backups are retained by the clinic's policy | Set a retention period (see below) and follow it, **including backups** |
| Security safeguards | Encryption (files, backups, in transit), MFA, audit chain, lockout, headers, scan, role separation — `SECURITY_OPERATIONS.md` | Disk encryption, key custody, patching, physical security, staff discipline |
| Breach notification | Audit log + `audit-verify` for scoping; incident procedure | Notify the Board and affected people as required; CERT-In — `INCIDENT_RESPONSE.md` |
| Rights of the person (access, correction, erasure, grievance, nominee) | Patient summary export (*Export* on the chart); visit summary PDF; admin erasure | Name a grievance contact; answer within the legal time |
| Children's data | Patient age is recorded | Obtain a parent/guardian's consent for under-18s |
| Cross-border transfer | **None by default**: nothing leaves the server. AI models run on the clinic's own machine | Do not point the product at a cloud AI service without a documented decision |
| Significant Data Fiduciary duties (if designated) | Audit trail and reports help | Data Protection Officer, audits, impact assessment |

## Suggested patient notice (poster / form) — plain English

> **How we use your information.** *[Clinic name]* keeps a record of your health and contact details to look after you:
> to diagnose and treat you, to prescribe, to send you reminders, and to keep legally required medical records.
> Your record is stored on our own computer in this clinic and is seen only by staff who need it. We do not sell it or
> share it, except with a doctor, laboratory or pharmacy you ask us to, or where the law requires.
> You may ask to see your record, to correct it, or to have it erased where the law permits, and you may complain to us.
> Contact: *[name, phone, email]*. We keep records for *[period]*.

## Requests from patients (procedure)

1. Log it (date, who, what). 2. Verify identity (photo ID against the chart). 3. **Access**: print the chart *Export* and the
visit summaries. 4. **Correction**: correct the chart; for an issued letter/prescription void it with a reason and reissue.
5. **Erasure**: only if no legal duty to keep the record applies; Settings is admin-only; remember backups age out by retention. 6. Reply in writing.

## Retention (to be set with the clinic's lawyer)

Indian medical-council conduct rules have required outpatient records to be kept for **at least three years** (longer for
inpatient/medico-legal cases and for children until they reach majority plus a margin). Confirm the current requirement,
choose a period, and apply it to **both** the live data and the off-site backups (the product keeps the 14 newest
automatically; the off-site script keeps 30 — set deliberately).
