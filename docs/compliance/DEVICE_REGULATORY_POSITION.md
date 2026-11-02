# Is this a medical device? — position paper (DRAFT)

*Review by a regulatory-affairs consultant before any claim is made to a customer or to CDSCO.*

## The question

India regulates software as a medical device under the **Medical Devices Rules, 2017** when it is intended to diagnose,
prevent, monitor, treat or alleviate disease, or to inform clinical decisions in a way that drives treatment. Software that
only stores records is generally outside. This product does both: a records system **and** decision support (prescription
safety alerts, calculators, a diagnosis "second look", an assistant).

## The position taken by the product (to be confirmed)

1. **Intended use statement** (the words everything else must match): *"A clinical decision-support and record system for
   registered medical practitioners. It presents information and alerts for the practitioner's independent review.
   It does not diagnose, prescribe or treat. The practitioner remains responsible for every clinical decision."*
2. **Design choices that support that position**, all already in the product:
   - Every alert shows **what fired and on which patient fact** so the doctor can judge it (`engine.Finding.basis`).
   - Rules **never block**; a critical alert needs a recorded reason, not a barrier.
   - AI output is always a **draft** until a clinician accepts it, labelled as such, and cites its sources or declines.
   - No autonomous action: nothing is sent, ordered or dispensed without a person.
   - Content is **signed by a named doctor and pharmacist** and bound to a fingerprint (`../CLINICAL_GOVERNANCE.md`).
3. **Likely classification**: the regulator, not the vendor, decides. Plan for the possibility that the decision-support
   features are classed as a device (low-to-moderate risk) and prepare the file now, because it doubles as the sales evidence.

## The evidence file to build (and what already exists)

| Item | Exists | Missing |
|---|---|---|
| Intended use and indications / contraindications | Drafted above | Final wording approved |
| Risk management (ISO 14971 style) | `HAZARD_LOG.md` | Clinical review and signatures |
| Software lifecycle documentation (IEC 62304 style) | Architecture docs, 200+ automated tests, migrations, change control for medical content | Formal software requirements ↔ tests trace; release records |
| Clinical evaluation | Clinical test-bank (27+ cases); measured extraction accuracy (`python -m app.cli eval`) | **Validation with the real language model on a GPU; a small prospective evaluation in a partner clinic** |
| Usability evaluation (IEC 62366 style) | Design system, accessible UI | Observed sessions with 5–8 real doctors |
| Cybersecurity | `SECURITY_OPERATIONS.md`, hash-chained audit, encryption | Independent penetration test |
| Post-market surveillance and vigilance | `INCIDENT_RESPONSE.md` | A complaint-handling log and a named person |
| Quality management system | — | ISO 13485 is the usual route if classed as a device; start with a lightweight QMS |

## Recommended order

1. Intended-use statement approved. 2. Ask a regulatory consultant for a **written classification opinion** (days, not months).
3. If a device: licensing route and timeline from that opinion; meanwhile **market as record-keeping with decision *support***
   using the intended-use words above and avoid claims such as "diagnoses", "detects", "prevents errors".
4. Collect real-world evidence in a design-partner clinic under a written agreement.
