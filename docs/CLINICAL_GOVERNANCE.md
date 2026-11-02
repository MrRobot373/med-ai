# Clinical governance — who signs off the medical content, and how

*Draft for the owner's decision. Where it names regulations, confirm the current text with a lawyer before relying on it.*

## The answer in one paragraph

Appoint **two named people, both independent of the sales side of the company, on a written retainer**:

1. **Clinical Lead** — a practising **physician in Internal Medicine or Family Medicine** (MD / DNB), ten or more years
   in outpatient practice, registered with a State Medical Council or the NMC, who still sees patients. Not a surgeon
   or sub-specialist: the product is an outpatient general-practice tool, and the person must recognise what a
   *routine* clinic prescription looks like.
2. **Pharmacist** — a **clinical or hospital pharmacist** (Pharm.D, or M.Pharm in Pharmacy Practice / Clinical
   Pharmacy), five or more years in a hospital or clinical-pharmacy role, registered with a State Pharmacy Council,
   experienced in drug-interaction and renal-dosing review.

They sign **every release that changes medical content**. A third person — a **nephrologist or geriatrician** on call
for half a day per release — reviews the renal and elderly rules, because that is where dosing errors do most harm.
Each customer clinic's own senior doctor then **adopts** the content for that clinic (see "Two layers" below).

Why these two: the rules engine is, in effect, a pharmacology reference plus a set of clinical judgements. A doctor
alone tends to accept the output that looks plausible; a pharmacist alone lacks the sense of what a busy clinic
actually does. Two different professions looking at the same cases catch different errors, and "signed by a doctor
and a pharmacist, with registration numbers" is the sentence a buyer, an insurer and a regulator all want to read.

**Do not** make the founder, a developer, or a doctor employed on commission the signatory. The signature is only
worth something if the signer is free to say no.

## What they are signing

The product has three areas of medical content. Each has a fingerprint (SHA-256) of exactly what ships; a signature
is bound to that fingerprint, and lapses automatically when anything in the area changes.

| Area | What it is | Signed by |
|---|---|---|
| Prescription safety rules and drug database | 114 generics, brands, doses, allergy groups, interactions, the rules that raise alerts, and the 27 clinical test cases | Clinical Lead **and** Pharmacist (different people) |
| Clinical scores and calculators | The formulas and thresholds | Clinical Lead |
| Reference library | The documents the assistant quotes | Clinical Lead |

The product enforces: a password check at signing, the signer's registration number on file, two different people for
the rules, and **no signature while any clinical test fails**. Settings → *Clinical content* shows who signed what and when.

## The review, step by step (per release that touches medical content)

1. **Release notes list every medical-content change** (a rule added, a threshold moved, a drug added, a document replaced). Engineering prepares them; a change that is not listed is a defect.
2. Reviewers run `python -m app.cli clinical-selftest` and read the 27+ cases in `backend/app/clinical/testbank.json`.
   Each case states the patient, the prescription, what must be reported, what must *not* be, and why.
3. **Pharmacist** reviews: dose limits, units, brand → generic mapping, interactions (severity and wording),
   renal/hepatic/paediatric/elderly rules, allergy and cross-allergy groups, duplicate-therapy classes.
4. **Clinical Lead** reviews: whether alerts are *proportionate* (too many alerts are ignored — alert fatigue is a
   safety problem, so every "clean" test case that must stay quiet matters as much as the ones that must fire),
   the calculators, and the reference library against current Indian guidelines.
5. Each reviewer adds cases for anything that surprised them. The bank only ever grows.
6. They sign in the product. The signature record is exported with the release and filed (see below).

Time: first full review about **3–4 working days each**; later releases **½–1 day** because only changes are read.

## Two layers of responsibility

- **The vendor's reviewers** sign the *shipped* content, so that every customer starts from a reviewed version. Their
  signed record travels with each release (Settings → Clinical content can be exported to PDF for the file).
- **Each clinic's senior doctor** signs in *their own installation* that they have reviewed and adopt the content for
  their patients. This is the clinic's own clinical governance and it is what makes the clinic, not the vendor, the
  owner of its prescribing decisions. A clinic's pharmacist (or the vendor's, by arrangement) signs the second role.

The software is a decision aid: **the prescriber is always the decision-maker and every alert can be overridden with
a recorded reason.** The product does not change that and the documentation must never say otherwise.

## Change control

| Change | Needs |
|---|---|
| Bug fix in code that does not touch rules, data, calculators or the library | Engineering review only |
| Any edit to the formulary data, rule code, calculators or the library | Both reviewers' fresh signatures (the product shows "changed since reviewed" until then) |
| New clinical test case added | Reviewer who added it initials the case; no re-signing needed unless a rule changed |
| A reported patient-safety incident | Immediate review by both reviewers; hotfix path with same-day sign-off |

## Retainer and independence (suggested terms)

- Written consultancy agreement; fee fixed per release, not per number of installations.
- Right to refuse to sign, and a duty to say so in writing.
- Conflict-of-interest declaration (no holding in competing products; no pharmaceutical sponsorship).
- Professional indemnity cover of their own for advisory work; the company's cover should also name them.
- Named deputy for each, so a release is never blocked by one person's leave.

## Where to find them

Ask a **teaching hospital's Department of General Medicine and Department of Pharmacology / Clinical Pharmacy** for a
senior faculty member or a clinical pharmacist willing to consult. Medical-college faculty are used to this role, are
registered, and are used to being independent. Indian Association of Clinical Pharmacology & Therapeutics members are
another route for the pharmacist.

## Records to keep (the audit file for each release)

Release number and content fingerprints · the release notes · test-bank results · both signatures with registration
numbers · any cases added · the incident log. Keep at least as long as the longest warranty or limitation period that
applies — ask the company's lawyer; assume **eight years**.
