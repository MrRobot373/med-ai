# Incident response (DRAFT — lawyer and security lead to review)

Two kinds: **A. data/security incident**, **B. patient-safety incident** (the software contributed to, or nearly caused, harm).

## Roles
Clinic: *Incident lead* (the administrator), *Clinical lead* (senior doctor), *Contact for patients*. Vendor: *Support lead*, *Security lead*, *Product Clinical Lead + Pharmacist*. Phone numbers are filled in at installation.

## A. Data or security incident

| Time | Do |
|---|---|
| 0–1 h | **Contain**: disconnect the server from the network (keep it powered); change admin passwords from another device; revoke API keys. Tell the incident lead. **Preserve**: `docker compose logs app > logs.txt`; copy the latest backup; `python -m app.cli audit-verify` and save the output |
| 1–6 h | Decide whether it is a reportable cyber incident. **CERT-In expects reports of listed incident types within six hours** of noticing — call the lawyer now. Inform the insurer (policies usually require immediate notice) |
| 6–72 h | Scope with the audit log: accounts, patients, exports, API keys. Rebuild from a pre-incident backup if integrity is in doubt; rotate every key |
| As the law requires | Notify the Data Protection Board and affected people with what happened, what data, what to do, and a contact |
| After | Written report; root cause; fix; update the hazard log; brief staff |

## B. Patient-safety incident
1. Make the patient safe first (clinical action). 2. Record exactly what the screen showed (screenshot, prescription ID, time).
3. Report to the vendor's Support lead **the same day**; the vendor's Clinical Lead and Pharmacist review within 24 hours.
4. If a rule or content is at fault: add a failing test case, fix, release with fresh signatures, notify every customer that
   could be affected. 5. File the record (kept at least eight years). 6. If the regulator's vigilance rules apply, report as required.

## Practice
Run a tabletop exercise once a year: "the server was stolen", "a pharmacist reports a wrong-dose prescription".
