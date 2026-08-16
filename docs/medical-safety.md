# Medical Safety Behavior

What this application actually does — and refuses to do — to avoid presenting
fabricated, overconfident, or unverifiable clinical information as fact. Every claim
below points at real code, not aspirational policy; `docs/architecture.md`'s per-phase
sections have the live-verification evidence for each one.

## The core rule: never invent, never guess, never overclaim

Spec §2's "never invent/never distort" is the single rule every other mechanism on this
page exists to enforce. It shows up as many small, separate decisions rather than one
central filter:

- Lab reference ranges are shown **exactly as the source document stated them**, or
  "Not stated in source" — never a hardcoded "normal" threshold (`models/observation.py`).
  Real reference intervals vary by lab/sex/age/method; baking one in would itself be an
  invented fact.
- An empty allergy/medication list renders as "None documented" — explicitly **not**
  "no known allergies" (`chat/patient_context.py`). Silence is never treated as a
  confirmed negative.
- Medications are append-only (`models/medication.py`): stopping one sets
  `active=False` + `stop_date`, it never deletes or rewrites the original prescribing
  details. History is preserved, not overwritten to look cleaner.
- The deterministic "What Changed?" / report-comparison engines
  (`services/change_engine.py`, `services/clinical_modules.py`'s
  `_compute_numeric_changes`) report `increased`/`decreased`/`unchanged` — deliberately
  **not** `worsened`/`improved`. Whether a rising value is good or bad is clinical
  judgment this code has no basis to assert.
- Medication reconciliation (`services/reconciliation.py`) words an absence as "not
  mentioned in this document," never "discontinued" — those are different claims, and
  only one of them is actually supported by what a single document not mentioning a
  drug can tell you.

## Retrieval grounding: an answer must trace to real evidence

Every citable claim in a Clinical AI answer traces back through a real pipeline stage,
not a post-hoc gloss — see `docs/rag-design.md` for the mechanism. Three enforcement
points specifically exist to stop an answer from claiming support it doesn't have:

1. **Citation validation** (`chat/citation_validator.py`): a `[P9]`-style label the
   model emits that wasn't actually offered as evidence is stripped from the answer
   before it's shown — spec §52, verified live in `evaluation/citation_eval.py`
   (both a synthetic fabricated-label test and a real end-to-end precision check).
2. **Grounding validation** (`chat/grounding_validator.py`): a second real LLM pass
   classifies each claim in the model's own answer as
   `supported`/`partially_supported`/`unsupported` against its cited passages — spec
   §52/§53, scored live in `evaluation/groundedness_eval.py`.
3. **Evidence quality labeling** (`chat/evidence_quality.py`): a deterministic
   `strong`/`moderate`/`limited`/`insufficient` category from transparent factors
   (distinct source count, the reranker's own logit sign, citation coverage) — spec
   §54's explicit "never `AI Confidence: 93%` unless a scientifically calibrated model
   supports that measure." There isn't one here, so there's no percentage.

## Abstention: two real layers (see `docs/rag-design.md` for the mechanism)

A hard pre-generation gate stops the LLM from being called at all when there's truly
nothing to answer from; a system-prompt instruction to use `ABSTENTION_TEXT` verbatim
handles the case where *some* structured context exists but doesn't answer the
specific question asked. Both are live-verified in
`evaluation/hallucination_eval.py` — including the real finding that checking only the
first layer would have misreported a correctly-honest answer as a failure.

## Vision: observable findings, never autonomous diagnosis

`vision/prompts.py`'s system prompt states the rule directly, more than once: describe
what is visible, never present a diagnosis as settled fact, never claim certainty a
careful human reviewer wouldn't have. The structured output schema itself enforces this
shape — `observations` (what's visible), `measurements_visible` (only numbers actually
printed/drawn on the image, never one the model calculated itself),
`quality_limitations`, and `uncertainties` are separate fields, not folded into one
freeform "impression." Live-verified in Phase 09: a synthetic schematic eye diagram was
correctly described as "a stylized schematic, not a clinical photograph" rather than
the model pretending it was a real fundus photo.

## Prompt injection resistance

Retrieved document content is data, never instructions — stated explicitly in
`chat/prompts.py`'s system prompt, and tested for real: `klein_injection_test_note.pdf`
(seeded by `scripts/seed_demo_reports.py`) embeds spec §98's exact "Ignore all previous
instructions" phrase inside otherwise-real clinical content.
`evaluation/hallucination_eval.py`'s prompt-injection check confirms live that (a) the
chunk is genuinely retrieved — RAG doesn't pre-filter adversarial content, the boundary
holds at generation time, not by hiding the attack — and (b) the model's real answer
both accurately describes what the note contains *and* explicitly declines to follow
it, rather than complying.

## Patient isolation

Spec §16's mandatory guarantee: `dense_search()`/`sparse_search()` raise if a
patient-scoped collection is queried without a `patient_id` — enforced in code at the
one place every retrieval call passes through. `evaluation/patient_isolation_eval.py`
verifies this live across every seeded patient pair, through the full real pipeline,
attacked with each patient's own real clinical content scoped to every other patient.

## Research Mode: de-identification before anything leaves the machine

`research/deidentify.py` strips the current patient's own known identifiers
(name/MRN/phone/email) plus generic identifier-shaped patterns (email, phone, MRN,
street address) from a query **before** any external provider (PubMed, openFDA,
ClinicalTrials.gov, or SearXNG) ever sees it — spec §66, no bypass. Deliberately narrow
rather than general name-detection: a broader NER pass risks false positives on
ordinary clinical terminology (a dedicated test confirms "Marcus Gunn pupil" survives
untouched) — spec §2's "never invent/distort" argues against an overreaching filter
just as much as it argues against an under-reaching one.

## Provenance over confidence

Spec §80's "Why This Answer?" drawer and spec §125's "no hidden chain-of-thought" are
the same underlying principle from two directions: the app shows *real, observed*
pipeline mechanics (dense/BM25/fused/reranked candidate counts, which model generated
the answer) — never the model's internal reasoning, and never a fabricated confidence
number. `Message.structured_payload` only ever stores the specific fields spec §125
calls "acceptable provenance" (task classification, retrieval query, evidence
selected, grounding classification) — chain-of-thought is neither requested from the
model (`"think": false` on every call) nor stored anywhere.

## Audit and feedback: a real trail, not a black box

Every meaningful account/clinical action is recorded (`app/audit/service.py`) with who,
what, when, and outcome — never full clinical free text, per spec §82's own "avoid
unnecessary PHI in logs" rule. Every AI-generated answer (chat message or clinical
module draft) can be rated Helpful/Not Helpful/Incorrect/Missing Evidence/Outdated
Evidence/Wrong Patient Context (spec §81), stored for real evaluation, not discarded.

## Draft discipline

Every one of the six Clinical Modules (summary, SOAP, entity extraction, differential
support, guideline Q&A, report comparison) plus Research Mode writes an explicit,
timestamped **draft** row (`ClinicalModuleRun`) — spec §63's "never automatically saved
as finalized clinical record." Nothing generated by the AI ever writes directly to
`Condition`/`Medication`/`Encounter`; a clinician acts on what's surfaced, the system
never acts on its own behalf.
