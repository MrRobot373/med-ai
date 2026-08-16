# Demo Guide

A 5–10 minute final demonstration script (spec §137's `docs/demo-guide.md`). Every step
below drives the real, running application — no step replays a canned response or a
static screenshot. Run `start-demo.bat` first (see README.md); it seeds the accounts,
patients, and reports this script assumes exist.

## Setup (before the audience arrives)

1. `start-demo.bat` — waits for real health checks to pass and opens the browser once
   the backend is actually responding. If it's been more than a few minutes since it
   ran, models may have been evicted from memory/VRAM by the OS/Ollama's keep-alive
   timeout — the first live query in the walkthrough below will simply take a little
   longer while it warms back up; this is expected, not a hang (see README.md's
   troubleshooting table).
2. Log in as `doctor@gms.local` (credentials in `data/sqlite/.demo_credentials.txt`).

## The walkthrough (~7 minutes of narration + real wait time)

### 1. Overview (30s)

Land on `/overview`. Point out the **System Status** panel — every indicator reflects a
real, live health check (`GET /api/health`), never a hardcoded "Ready." Click **Demo
Scenarios** in the hero section.

### 2. Demo Scenarios page (30s)

`/demo` lists six real scenarios (spec §89). Each card resolves its target patient from
the live `/api/patients` list and deep-links into a real route with real context
pre-filled — nothing here is a canned macro. Walk through two or three of the six below
depending on time; each is independently a complete demonstration.

### 3. Patient Report Comparison (~1 min)

Click **Patient Report Comparison** (Elena Novak). Lands on her Clinical Modules →
Compare Reports tab with her two real seeded metabolic panels available. Select both
and generate — the numeric changes (HbA1c/glucose/LDL down, creatinine up) are
computed by a **100% deterministic** Python engine (`services/clinical_modules.py`),
not the LLM — point this out explicitly, it's a common misconception that every number
an AI app shows came from the model.

### 4. Longitudinal Lab Analysis (~30s)

Click **Longitudinal Lab Analysis** (also Elena Novak). Lands on her Labs tab — a real
two-point trend line for HbA1c/glucose/LDL/creatinine, built from the same two real lab
panels.

### 5. Vision + Guideline RAG (~2 min, includes real wait time)

Click **Vision + Guideline RAG** (Priya Patel). Lands on her Clinical AI tab with a
pre-filled question about her OCT imaging and local AMD guidance, already sent. This is
the most impressive single step: it exercises real Ollama vision analysis (already run
at seed time, visible on her Reports tab if you want to show the structured findings
first), real image-to-RAG retrieval, real local-guideline retrieval, and a real
streamed answer with citations — click a `[V1]`/`[L1]` badge in the answer to jump to
the Evidence panel, then click **Why This Answer?** to open the real retrieval
provenance drawer (spec §80) and show the actual dense/BM25/fused/reranked candidate
counts, not a fabricated confidence score.

### 6. Medication Reconciliation (~1 min)

Click **Medication Reconciliation** (Robert Klein). Lands on his Reports tab. Open his
most recent report and click **Reconcile Medications** — it surfaces Brimonidine as
newly detected (present in the document, not yet in his system medication list) via
fuzzy matching, never silently updating his chart itself. Read-only; a clinician acts
on what's surfaced.

### 7. Current Evidence Research (~2 min, only if `ENABLE_RESEARCH=true` and online)

Click **Current Evidence Research** (Robert Klein). Lands on `/research` with a
pre-filled SLT-vs-topical-therapy question and his patient context selected. Check a
source (PubMed/FDA) and run it — real external API calls, real de-identification
happening before anything leaves the machine (point out the consent banner), a
synthesized answer with real citations linking to real PubMed/FDA URLs. If offline or
Research Mode isn't enabled, the page honestly says so instead of pretending — worth
showing that honest-degradation behavior too (spec §85).

### 8. Clinical Note Generation (~1 min)

Click **Clinical Note Generation** (Thomas Ferreira — the multi-morbidity patient:
glaucoma + cataract + diabetic retinopathy managed concurrently). Lands on his SOAP
tab; generate a note against his most recent encounter. A genuinely complex patient is
a better demonstration than a single-condition one — the draft correctly separates
findings belonging to each of his three conditions.

### 9. Audit & Feedback (~30s)

Navigate to `/audit` (admin account required — log out and back in as
`admin@gms.local` if the audience should see this, or narrate it from the doctor
account without opening it). Show the real audit trail from everything just
demonstrated, and the Feedback tab. Click a thumbs-up on one of the chat answers shown
earlier to show feedback capture live.

## If something goes slowly

Reranking against `medical_knowledge` on CPU-only hardware measured 6–7 minutes live
during development (`docs/architecture.md`'s Phase 08 section) — if this deployment is
running on GPU (see README.md's "GPU acceleration" section), the same call measured
under a second. If a query is visibly slow, say so plainly rather than letting silence
read as a hang: "this is doing real cross-encoder reranking against the full knowledge
base on CPU — on the GPU-enabled build this step alone dropped from minutes to under a
second."

## What NOT to demonstrate live

Don't run `reset-demo.bat` in front of an audience — it's a genuine destructive
operation (spec §87) that takes real time (a full knowledge re-embed can take ~20
minutes on CPU) and requires a typed confirmation. Reset it beforehand instead.
