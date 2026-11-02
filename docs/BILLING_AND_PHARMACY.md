# Billing and pharmacy — what to do, what was built, what was deliberately not

*Recommendation for an on-premise product sold to Indian clinics.*

## Recommendation

**Do not build billing, GST, insurance claims or a pharmacy stock system inside this product. Connect to them.**

| Reason | |
|---|---|
| Clinics already have billing or pharmacy software they are tied to (Marg, Tally, Busy, GoFrugal, Practo Ray, hospital HIS, a neighbouring chemist's system), and switching it is a bigger decision than switching the clinical tool | Selling "replace everything" slows every sale |
| Billing means GST invoicing, e-invoicing thresholds, TDS, insurance/TPA formats, receipts, refunds, audit by a chartered accountant — all of which change with the law | A permanent maintenance and liability burden unrelated to the product's strength |
| Pharmacy stock means batch/expiry tracking, schedule H/H1/X registers, purchase and returns, drug-licence compliance | Regulated, specialist, and the chemist is often not even the clinic |
| The product's value is **the clinical decision and the record**, and a clean, trustworthy hand-off to those systems is worth more than a mediocre copy of them | |

If a customer later insists on a basic in-clinic bill (consultation fee + procedure + receipt), add a thin
**fee schedule and receipt** module then, behind a feature flag. Do not start with it.

## What was built (version 3.0)

**For billing staff**
- *Completed visits feed*: each visit with date, patient MRN and name, doctor, branch, diagnoses and the **services given**
  (consultation, investigations ordered, prescription issued, letters issued). **No prices** — prices live in their software.
- *Spreadsheet export* (Settings → Integrations): visits and prescriptions for a date range, opens directly in Excel, with
  protection against spreadsheet-formula injection from patient-entered text.
- *API and webhooks* so their software can pull or be told automatically.

**For pharmacy**
- *Printed QR code on every prescription*: scanning it opens a page that confirms it is genuine, issued by whom, when,
  and that it has not been altered — revealing nothing about the patient.
- *Partner API*: a pharmacy (or the clinic's own pharmacy software) with a scoped key can read issued prescriptions and
  **mark one as dispensed** (once; a second attempt is refused). The doctor sees "Dispensed · City Pharmacy" on the
  prescription.
- *Webhook* `prescription.finalized` so a pharmacy that is connected hears about a new prescription within seconds.

**Safety of the connection**
- Keys are random, stored only as a hash, shown once, scoped, can expire, and can be revoked at any time; every use is recorded.
- Webhook messages are signed (HMAC-SHA256 with a per-webhook secret), queued with the event so none is lost, and
  retried with increasing delays for about two days. The default message contains **IDs only**; the partner fetches
  detail with its key. Addresses on the clinic's network are allowed; loopback and cloud-metadata addresses are refused.

## What a customer's technician does

1. Settings → Integrations → **New key**, tick only what the partner needs (`prescriptions:read` and `prescriptions:dispense` for a pharmacy; `visits:read` for billing).
2. Give the partner the key (shown once) and the address of this server.
3. Optional: **New webhook** pointing at the partner's server; press **Test**; read the log if it does not turn green.
4. The partner developer's guide is `docs/PARTNER_API.md`.

## When this recommendation changes

- A chain of clinics asks for **one billing system across branches** → build the fee schedule and receipt module.
- A large customer wants **ABDM / ABHA** linkage → build it as a separate integration (it is the same pattern: scoped, audited, optional).
- A pharmacy partner wants **e-prescription in a standard format** → add an HL7 FHIR `MedicationRequest` view to the partner API; the data is already structured.
