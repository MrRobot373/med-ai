# Doctor's guide — a consultation in GMS Clinical AI

*Two pages. Print it and keep it at the desk.*

## Your day
1. **Sign in** (password, then the 6-digit code from your authenticator app). Your first screen is **Today's patients** — who is waiting, who has new results.
2. Click a patient. The **header** always shows name, age, sex and MRN — check it matches the person in front of you.
3. **Overview** shows allergies (red), active problems, current medicines, latest results with trends, and what changed since the last visit.
4. The **Inbox** (top right) lists what needs you: abnormal new results, reports that did not match their patient, drafts waiting.

## A consultation
1. Patient → **Consultation → Start consultation**. Type the history and examination; vitals go in the boxes.
2. Add the **diagnosis**. *Diagnosis second look* (optional) suggests what else to consider — it is a draft for your judgement.
3. **Write prescription**. Type the medicine as you would write it (brand or generic: *Pan 40, Septran DS, Glycomet-GP 2*). Each line is checked **as you type** against **this patient**: allergies, kidney function (eGFR), pregnancy, age, liver, interactions, duplicates, maximum doses.
   - **Red / "Stop & check"**: a serious problem. You may still prescribe, but you must type your reason (it is recorded).
   - **Amber**: be aware. **Grey**: information.
   - The alert says *what fired and on which fact* (for example "eGFR 28, calculated") so you can judge it. **You decide; the system never blocks.**
4. **Speed**: **Templates** (your own, or the clinic's), **★** next to a medicine saves it with your usual dose, **Quick add** chips show your most-used medicines, **Same as last visit** copies the previous prescription (every line is checked again).
5. Add advice and a follow-up date (1 wk / 2 wk / 1 mo buttons).
6. **Complete consultation**: the prescription is finalised, medicines enter the chart, a follow-up appears on the day list.
7. **Print** opens a PDF on your letterhead with your registration number and a QR code. A pharmacy can scan it to confirm it is genuine.

## Letters (patient → Letters → New letter)
**Medical certificate**, **fitness certificate**, **referral letter** (pre-filled from the chart: problems, medicines, allergies) and **visit summary** (plain language for the patient). Edit, **Issue** (it gets a number like MC-2026-0007 and can no longer be changed), **Print**. A mistake is **voided with a reason** and rewritten — never edited.

## Reports and results
Reports uploaded by the front desk are read automatically. New values appear in **Results** with a flag and the source page. **Always glance at the source** for a result that will change a decision. A report that does not match the patient's name/DOB is **quarantined** and shows in your Inbox.

## Ask the chart (Assistant)
Ask in plain words: "How has her kidney function changed?" The answer cites its sources ([R] = the structured record, [P1] = a document page). If the material does not answer the question, it says so rather than guessing. **It is decision support: verify before acting.**

## Your profile (Settings → Profile)
Add your **registration number**, council and qualifications (printed on every prescription — required before you can finalise one), a photo of your **signature**, and **two-step verification**.

## If something looks wrong
Open the prescription or letter → note the time → tell your administrator. A suspected wrong or missing alert is a **patient-safety report**: the same day, to the vendor's support contact (see `compliance/INCIDENT_RESPONSE.md`).
