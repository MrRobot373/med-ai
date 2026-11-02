# Licence, service and data terms — outline for the commercial lawyer (DRAFT)

*Not a contract. Each heading lists the position the product and operating model support; the lawyer drafts and negotiates.*

## 1. Licence
Non-exclusive, non-transferable right to run the software on **one** installation (identified by its Installation ID) for the
clinic's own use, up to the licensed numbers of doctors, other users and branches (the product enforces these by signed licence
file). Term and renewal; what happens on lapse: **patient care is never interrupted** — only the addition of new users/branches stops.
No reverse engineering; third-party components under their own licences (`THIRD_PARTY_NOTICES.md`).

## 2. Intended use and clinical responsibility
Decision support for registered practitioners (see `DEVICE_REGULATORY_POSITION.md`). The practitioner is responsible for every clinical
decision. The clinic is responsible for reviewing and adopting the medical content, for the accuracy of data entered, and for local law.
**The AI features depend on models the clinic runs; the vendor does not warrant their output.**

## 3. Support and service levels
Hours; response targets by severity (e.g. S1 patient-safety or unable-to-prescribe: acknowledge 1 h, workaround 4 h; S2 degraded: next working day; S3: 5 days);
remote access only on the clinic's request, supervised, logged; no copying of patient data; updates delivered as signed bundles with a rollback path.
Out of scope: the clinic's hardware, network, operating system, AI model server, third-party billing/pharmacy software.

## 4. Data
Data stays on the clinic's server. The vendor does not host or receive it. Backup and key custody are the clinic's duty (the product provides the tools and
reminders). On termination: the clinic keeps everything; the vendor deletes any support copies. Usage reports contain counts only.

## 5. Medical content updates
The vendor supplies reviewed content with each release (named reviewers, registration numbers); the clinic must adopt it by signing before relying on it.
The vendor notifies customers promptly of any safety-relevant correction.

## 6. Warranty, liability, insurance
Warranty limited to conformity with documentation for a defined period. **Limitation of liability** (a multiple of fees paid; no exclusion that the law forbids,
e.g. for death or personal injury caused by negligence — the lawyer must check). Indemnity for IP claims. The vendor carries professional-indemnity and cyber cover
(see `INSURANCE_AND_CERTIFICATION.md`).

## 7. Security
The clinic's duties (disk encryption, keys, patching, access control) are written into the contract with a statement that the vendor's warranty depends on them.

## 8. Governing law, disputes, confidentiality, force majeure, assignment — standard clauses.
