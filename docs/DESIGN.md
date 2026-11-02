# GMS Clinical AI — Design System

This is the complete visual and interaction language of GMS Clinical AI, written so that a designer
(in Figma, Penpot or any tool) or a developer can create new screens that look and behave exactly
like the existing product. Every value below is taken from the code:

- Colours, radii, shadows, motion: `frontend/src/styles/index.css`, `frontend/tailwind.config.ts`
- Accent maths: `frontend/src/lib/color.ts`
- Components: `frontend/src/components/ui/*`, `frontend/src/components/clinical/*`
- App shell and navigation: `frontend/src/components/layout/*`

If this document and the code ever disagree, the code wins; update this file.

---

## Contents

1. [Design principles](#1-design-principles)
2. [Brand](#2-brand)
3. [Colour](#3-colour)
4. [Typography](#4-typography)
5. [Spacing, density and grid](#5-spacing-density-and-grid)
6. [Shape: corner radius](#6-shape-corner-radius)
7. [Elevation, glass and backgrounds](#7-elevation-glass-and-backgrounds)
8. [Iconography](#8-iconography)
9. [Layout: the app shell](#9-layout-the-app-shell)
10. [Page templates](#10-page-templates)
11. [Core components](#11-core-components)
12. [Clinical components](#12-clinical-components)
13. [AI surfaces](#13-ai-surfaces)
14. [Data visualisation](#14-data-visualisation)
15. [Motion](#15-motion)
16. [States: empty, loading, error, disabled](#16-states-empty-loading-error-disabled)
17. [Writing (UX copy)](#17-writing-ux-copy)
18. [Accessibility](#18-accessibility)
19. [Dark mode](#19-dark-mode)
20. [Responsive behaviour](#20-responsive-behaviour)
21. [Print](#21-print)
22. [Do and don't](#22-do-and-dont)
23. [Setting it up in Figma](#23-setting-it-up-in-figma)
24. [New-screen checklist](#24-new-screen-checklist)

---

## 1. Design principles

GMS Clinical AI is a doctor's co-pilot. Every decision in this system follows from five rules:

1. **The patient first, the software second.** The patient's name, age, allergies and active problems are always
   visible at the top of any patient screen. The chrome is quiet so the clinical content is loud.
2. **Evidence on screen.** A number is never shown without where it came from: the report, the page, the date,
   the reference range *as stated by the source*. AI statements carry citation chips.
3. **Calm until it matters.** The base palette is soft blue-grey and white. Colour is reserved for meaning:
   red = stop, amber = caution, blue/teal = information, green = in range / done. If everything is coloured,
   nothing is urgent.
4. **AI is a draft.** Every AI output is labelled as a draft for the doctor to verify, shows the model and time,
   and can be regenerated. It never looks like a final, signed fact.
5. **One glance, then one click.** Summaries first (score, trend, "what changed"), the original document one
   click away. The doctor should be able to decide from the summary and verify from the source.

---

## 2. Brand

| Element | Value |
|---|---|
| Product name | **GMS Clinical AI** |
| Tagline | *Clinical intelligence, grounded in evidence* |
| Mark | `frontend/public/brand-mark.webp` — the red striped **GMS** logotype with "THE TECHNOLOGY COMPANY" (766 × 326 px, transparent) |
| Wordmark | "GMS Clinical AI" in Inter Semibold, ink colour; in marketing, "Clinical **AI**" with *AI* in the accent blue |
| Organisation line | Under the product name in the header and sign-in page, e.g. *Life Care Medico* (muted, 0.7 rem) |
| White-label | Name, logo, tagline, default accent, default theme, disclaimer and sign-in message are editable in **Settings → Branding**. Design every screen so it still works with a different logo and accent. |

**Logo rules**

- In the header (`BrandMark`) the mark is a 36 px rounded-xl white tile (2 px padding, `shadow-xs`, 1 px black/5 % ring) next to the product name (1.05 rem / 600) and organisation (0.7 rem muted). On the sign-in hero it is a 40 px tile.
- Clear space: at least the height of the "G" on all sides.
- Always on white: the mark lives on its own white rounded tile in every theme, including the navy sign-in panel and dark mode.
- Never recolour the red stripes, never put the mark on the accent blue, never stretch it.

---

## 3. Colour

All colours are **CSS variables holding an HSL triplet** (e.g. `--primary: 221 98% 57%`), used as
`hsl(var(--primary))` or with alpha `hsl(var(--primary) / 0.2)`. This is what makes the accent colour,
light/dark theme and high-contrast mode switchable at runtime. In design files, create one colour style per
token below, for both themes.

### 3.1 Neutrals and surfaces

| Token | Light | Dark | Use |
|---|---|---|---|
| `background` | `#EBEFF5` | `#0C0F18` | App canvas behind everything |
| `foreground` | `#16233B` | `#EBEFF5` | Primary text ("ink") |
| `card` | `#FFFFFF` | `#141924` | Cards, panels (used through the glass surface, §7) |
| `card-foreground` | `#16233B` | `#EBEFF5` | Text on cards |
| `popover` | `#FFFFFF` | `#161B27` | Menus, popovers, dialogs |
| `muted` | `#EBEFF4` | `#202532` | Hover fills, segmented-control track, chips, skeletons |
| `muted-foreground` | `#637188` | `#95A0B1` | Secondary text, labels, captions, icons at rest |
| `subtle` | `#F5F7FA` | `#11151F` | Table headers, dialog footers, empty-state icon tiles |
| `border` | `#DCE2EA` | `#272C3A` | Hairlines, card dividers, table rules |
| `input` | `#D0D8E1` | `#343B4B` | Input borders |
| `sidebar` | `#FFFFFF` | `#141924` | Mobile navigation sheet |
| `sidebar-foreground` | `#435270` | `#B6BFCE` | Text in the navigation sheet |
| `sidebar-active` | `#EBEFF4` | `#222735` | Hovered item in the navigation sheet |

### 3.2 Accent (brand colour)

The accent is chosen per organisation (Settings → Branding) and per user (Settings → Appearance). Default:
**Clinical blue `#246BFD`**. From one hex value the app derives a whole family (`lib/color.ts → accentVars`):

| Token | Light (from `#246BFD`) | Dark | Use |
|---|---|---|---|
| `primary` | `#266AFD` | lightness lifted to ≥ 55 % | Links, focus ring, primary buttons, active chart line, selected thumbnail |
| `primary-foreground` | `#FFFFFF` | — | Text on `primary`. Switches to dark ink `#0F172A` automatically if white would fall below 3 : 1 contrast (e.g. yellow accents) |
| `primary-soft` | `#E7EEFE` | `#192643` | Soft buttons, card-header icon circles, AI panels, "primary" badges |
| `primary-soft-foreground` | `#154CC1` | `#88ACFC` | Text/icons on `primary-soft` |
| `ring` | = `primary` | = `primary` | Focus outline |
| `strong` | `#1D3463` (deep navy, same hue) | `#4C80F0` | **Key actions and active navigation**: "Start consultation", "Finalise prescription", active nav pill, active tab |
| `strong-foreground` | `#FFFFFF` | `#0C111D` | Text on `strong` |

**Accent presets** offered to users: Clinical blue `#246BFD` · Ocean `#0E7490` · Teal `#0D9488` ·
Emerald `#059669` · Indigo `#4F46E5` · Violet `#7C3AED` · Rose `#E11D48` · Amber `#D97706` ·
Graphite `#475569`.

> Design every screen in Clinical blue first, then check it in **Rose** and **Amber**: the accent must
> never be confused with the danger/warning colours. That is why critical findings use the `danger`
> *soft* fill + icon + words, never accent alone.

**`primary` vs `strong`.** `primary` (bright blue) is for interactive emphasis on light content: links, focus,
the selected item. `strong` (deep navy) is for *the* action of a screen and for "you are here" in navigation.
Use at most one `strong` button per card.

### 3.3 Semantic (status) colours

Each status has three tokens: a solid colour (icons, dots, bars), a **soft** fill (backgrounds of badges and
finding rows) and a **foreground** (text on the soft fill).

| Status | Solid (L / D) | Soft (L / D) | Foreground (L / D) | Clinical meaning |
|---|---|---|---|---|
| `danger` | `#E13333` / `#EC5151` | `#FDEAEA` / `#3B1616` | `#AD1F1F` / `#F98B8B` | Stop & check, allergy, critical interaction, value far out of range, wrong-patient document, "Unsafe" |
| `warning` | `#EB8D0A` / `#F6A823` | `#FFF4DB` / `#362712` | `#974D0C` / `#F7C96E` | Caution (age, Beers, renal dose), follow-up overdue, "Allergies not documented", result back waiting for review |
| `info` | `#0D9CDE` / `#2BB0EE` | `#E2F5FD` / `#132D39` | `#106793` / `#81D3F8` | Informational dosing notes, neutral system messages |
| `success` | `#249E65` / `#2EB877` | `#E3F7ED` / `#153225` | `#147145` / `#85E0B3` | In range, identity verified, reviewed, connection successful, "Routine" |

Rules:

- **Never rely on colour alone.** Every status also has an icon (⚠ `AlertTriangle`, ⓘ `Info`, ⊘ `AlertCircle`,
  ✓ `Check`) and a word ("Stop & check", "Caution", "High", "Reviewed").
- **Severity order on screen:** critical (danger) before caution (warning) before info. Within a prescription
  line, the worst finding sets the row's outline colour.
- Lab flags use words in the status foreground colour: `high` / `low` in danger/info text, never just arrows.

### 3.4 Clinical range gradients

Used only by the range bar under a lab value (§12.3). Colours are fixed, not themed:

| Name | Stops |
|---|---|
| `range-gradient` (two-sided range) | `#F59E0B` 0 % → `#FBBF24` 14 % → `#34D399` 30 % → `#10B981` 50 % → `#34D399` 70 % → `#FB923C` 86 % → `#EF4444` 100 % |
| `range-gradient-high` (only an upper limit, e.g. "< 100") | `#10B981` → `#34D399` 45 % → `#FBBF24` 62 % → `#FB923C` 80 % → `#EF4444` |
| `range-gradient-low` (only a lower limit, e.g. "> 40") | `#EF4444` → `#FB923C` 20 % → `#FBBF24` 38 % → `#34D399` 55 % → `#10B981` |

### 3.5 Avatar tones

Patient and staff avatars are initials on a pastel circle, chosen by a hash of the name so a person always has
the same colour: sky, violet, emerald, amber, rose, cyan (Tailwind `-100` fill with `-700` text in light;
`-500/15` fill with `-300` text in dark).

---

## 4. Typography

**Typeface:** [Inter](https://rsms.me/inter/) (variable; `@fontsource-variable/inter`), with OpenType features
`cv11` (single-storey a) and `ss01` (open digits) switched on globally. Users can switch to the system font in
Appearance; designs must still work in Segoe UI / SF Pro.

**Base size:** the root font size is **15 px** (user options: 14 / 15 / 16.5 px), so `1rem = 15 px`.
All sizes below scale with it.

**Numbers:** any number a doctor compares (lab values, doses, counts, times) uses **tabular figures**
(`.num` → `font-variant-numeric: tabular-nums`) so columns line up.

### Type scale

| Role | Size (rem → px at 15) | Weight | Tracking | Example |
|---|---|---|---|---|
| Display — hero (sign-in, marketing) | 2.1rem → 31.5 | 600 | −0.025em | "Clinical intelligence, grounded in evidence" |
| Big number (stat tiles) | 1.875–2.25rem → 28–34 | 600 | tight | "162 mg/dL", "8.1 %" |
| Page title (`PageHeader`) | 1.45rem → 22 | 600 | tight | "Clinical dashboard" |
| Patient name (workspace header) | 1.5rem → 22.5 | 600 | tight | "Rohit Verma" |
| Card title (`CardHeader`) | 0.95rem → 14.3 | 600 | tight | "Before you see the patient" |
| Section title | 0.875rem → 13 | 600 | normal | "Results since then" |
| Body | 0.875rem → 13 | 400 | normal | Form values, table cells |
| Body — reading (AI answers, `prose-clinical`) | 0.95rem → 14.3, line-height 1.625 | 400 | normal | Assistant answers, summaries |
| Secondary / description | 0.8rem → 12 | 400 | normal | Card descriptions, hints |
| Small | 0.75rem → 11.3 | 400–500 | normal | Metadata ("22 Sep 2026"), table sub-lines |
| Badge | 0.7rem → 10.5 | 500 | normal | "Waiting", "Caution" |
| Label / eyebrow (`.text-label`) | 0.72rem → 10.8, **UPPERCASE** | 600 | +0.06em | "LAST TIME", "RESULTS SINCE THEN", table headers |
| Micro (range ticks, counters) | 0.65rem → 9.75 | 500–600 | normal | Range-bar limits, nav counters |
| Code / citations | `ui-monospace`, 0.68–0.85em | 600 | normal | Citation chips `P1`, `K2`, `R` |

Rules:

- Two weights do almost everything: **400** for reading, **600** for anything you scan. 500 for badges and
  buttons. Never 700+ inside the app (marketing only).
- Headings are sentence case ("Before you see the patient"), never Title Case, never all caps except `.text-label`.
- Line length for reading text: max ~80 characters (`max-w-2xl`).

---

## 5. Spacing, density and grid

**Base unit: 4 px** (Tailwind scale, `1 = 0.25rem`). Common steps: 4, 6, 8, 12, 16, 20, 24, 32.

Three density variables drive every card and table, so the whole app compacts at once:

| Variable | Comfortable (default) | Compact | Used for |
|---|---|---|---|
| `--card-pad` | 1.25rem (≈ 19 px) | 0.9rem (≈ 13.5 px) | Inner padding of every card |
| `--row-y` | 0.75rem | 0.45rem | Vertical padding of table rows and list rows |
| `--gap` | 1rem | 0.85rem | Gap between cards in grids |

Layout grid:

- **Content width:** max **1680 px**, centred, 24 px side padding on desktop (`md:px-6`), 12 px on phones.
- **Gaps:** 16 px between cards (`gap-4`), 12 px inside card sections, 6–8 px between chips and buttons.
- **Columns:** pages use 12-column CSS grids. Typical splits: dashboard **7 / 5**, patient overview
  **report viewer 7 / insights 5**, consultation **notes 1 : prescription 1**, settings **nav 3 / form 9**.
- Vertical rhythm: page header bottom padding 24 px (`pb-6`); 16 px between stacked cards.

---

## 6. Shape: corner radius

One variable, `--radius`, sets every corner. User setting: **Sharp 0.4rem / Default 0.875rem / Round 1.2rem**.

| Token | Default value | Used on |
|---|---|---|
| `rounded-sm` | radius − 4 px ≈ 9 px | Small chips, citation chips (`rounded`) |
| `rounded-md` | radius − 2 px ≈ 11 px | Buttons, menu items |
| `rounded-lg` | radius ≈ 13 px | Inputs, selects, dialogs content blocks |
| `rounded-xl` | radius + 4 px ≈ 17 px | Icon buttons in the header, finding rows, stat tiles |
| `rounded-2xl` | radius + 8 px ≈ 21 px | **Cards**, dialogs, the AI insight overlay |
| `rounded-3xl` | 24 px (fixed) | The report viewer stage |
| `rounded-full` | pill | Badges, navigation pills, segmented controls, tab bars, primary page actions, avatars |

Rule of thumb: **containers are generously rounded, controls inside them slightly less** (a 21 px card holds
13 px inputs and 11 px buttons). Pills are used for navigation, filters and status — not for form fields.

---

## 7. Elevation, glass and backgrounds

### Shadows

Shadow colour is the variable `--shadow` (`30 50 90`, a navy, in light; pure black in dark), so shadows are
tinted, never grey.

| Token | Value | Use |
|---|---|---|
| `shadow-xs` | `0 1px 2px rgb(shadow / .05)` | Buttons, inputs, small tiles |
| `shadow-card` | `0 1px 2px rgb(shadow / .04), 0 8px 24px -12px rgb(shadow / .12)` | **All cards**, nav pill, header buttons |
| `shadow-pop` | `0 10px 38px -10px rgb(shadow / .25), 0 10px 20px -15px rgb(shadow / .2)` | Menus, popovers, autocomplete |
| `shadow-float` | `0 18px 50px -20px rgb(shadow / .35), 0 2px 6px rgb(shadow / .06)` | Dialogs, floating overlays, documents in the viewer |
| `shadow-ring` | `0 0 0 3px hsl(ring / .25)` | Focus halo on custom controls |

### Glass surface

Cards, the centre navigation pill, header icon buttons and the left rail are **frosted glass**:

```css
.glass { background: hsl(var(--glass) / var(--glass-alpha));      /* white at 78 % (dark: #161B27 at 72 %) */
         backdrop-filter: blur(18px) saturate(1.4); }
/* plus */ border: 1px solid rgb(255 255 255 / .7);  /* dark: rgb(255 255 255 / .06) */
           box-shadow: var(shadow-card);  border-radius: rounded-2xl;
```

The white 70 % border is what gives cards their crisp "lit edge" on the blue-grey canvas. Keep it.

### Page background

The canvas is `background` plus two very soft radial glows fixed to the viewport:

```css
radial-gradient(1200px 600px at 85% -10%, hsl(var(--primary) / .09), transparent 60%),   /* accent glow, top right */
radial-gradient(900px 500px at -10% 110%, hsl(var(--strong) / .07), transparent 60%);    /* navy glow, bottom left */
```

They follow the accent colour automatically. Don't add other gradients, images or patterns to the canvas.

### Layers (z-order)

1. Canvas → 2. Cards (glass) → 3. Sticky header (`background/70` + `backdrop-blur-md`, z 30) →
4. Popovers/menus (z 40–50) → 5. Dialog overlay (`slate-950 / 40 %`, 2 px blur, z 50) → 6. Toasts.

---

## 8. Iconography

- **Library:** [Lucide](https://lucide.dev) (`lucide-react`), outline style. Navigation icons use stroke width
  **1.9**; everything else the default 2.
- **Sizes:** 16 px (`size-4`) default in buttons, inputs and lists; 14 px (`size-3.5`) in compact buttons and
  mobile nav; 12 px (`size-3`) inside badges; 18–20 px in dialog and empty-state tiles.
- **Icon containers:** a card header icon sits in a **32 px circle** with `primary-soft` fill, `primary-soft-
  foreground` icon and a 1 px `primary / 10 %` ring. Dialog headers use a 36 px rounded-lg tile. Empty states
  use a 44 px rounded-xl tile on `subtle` with a border.
- Common icons and their meaning (keep them consistent):

| Meaning | Icon |
|---|---|
| Dashboard / Patients / Assistant / Inbox | `Home` / `Users` / `MessagesSquare` / `Inbox` |
| Clinical tools / Library / Audit / Settings | `Stethoscope` / `BookOpenText` / `ScrollText` / `Settings` |
| AI (anything generated) | `Sparkles` |
| Consultation | `Stethoscope` / `ClipboardPen` (notes) |
| Prescription / medicine | `FileSignature`-style pen / `Pill` |
| Investigations / lab | `Microscope` / `FlaskConical` |
| Imaging / DICOM | `ScanLine` |
| Document / report | `FileText` |
| Critical / caution / info | `AlertCircle` / `AlertTriangle` / `Info` |
| Done / verified | `Check` / `ShieldCheck` |

---

## 9. Layout: the app shell

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ [GMS] GMS Clinical AI          ( Dashboard | Patients | Assistant | Inbox 93 )   [⌕][☾][✉ 93][+ New][AR] │  ← sticky header
│       Life Care Medico                   centre glass pill, active = strong                         │
├────┬─────────────────────────────────────────────────────────────────────────────────────────┤
│ ⚕  │  PAGE CONTENT (max 1680 px)                                                              │
│ 📖 │                                                                                          │
│ ⚙  │                                                                                          │
│ ●  │  ← status dot (service health)                                                           │
│    │                                                                                          │
└────┴─────────────────────────────────────────────────────────────────────────────────────────┘
 left rail: glass pill, icon-only, tooltips
```

**Header** (sticky, `background/70` + blur, 16 px vertical padding):

- Left: `BrandMark` — logo tile + product name (600, 1 rem) + organisation line (muted, 0.7 rem).
- Centre: **primary navigation pill** — glass, `rounded-full`, 4 px inner padding. Each item: icon + label,
  `rounded-full`, 14 px horizontal padding. Active item: `strong` fill with `strong-foreground` text; inactive:
  muted text, `muted` fill on hover. The Inbox item carries a red count bubble (`danger`, white, 0.65 rem).
- Right: 40 px glass **icon buttons** (`rounded-xl`): search (⌘K), theme toggle, inbox with count; then the
  `strong` **+ New** button (40 px high, `rounded-xl`) and the user avatar.

**Left rail:** a vertical glass pill (sticky 88 px from top) with icon-only buttons for tools and administration
(Clinical tools, Knowledge library, Audit log, Settings) and a health dot at the bottom (green / amber / red).
Tooltips give the labels.

**Footer line** at the bottom of every page: the disclaimer in muted 0.75 rem —
*"Clinical decision support — AI output must be reviewed by the treating clinician."*

Role-based navigation: items are hidden (not disabled) for roles that can't use them. The front desk never sees
Assistant, Inbox, tools or clinical tabs.

---

## 10. Page templates

### 10.1 Standard page

```
EYEBROW (optional .text-label)
Page title (1.45rem/600)                                [secondary action] [primary action]
Description (0.875rem, muted, max ~80 ch)
──────────────────────────────────────────────── 24 px
[ Card ] [ Card ]          ← 12-col grid, 16 px gaps
```

### 10.2 Clinical dashboard (doctor's home)

- Left 7 columns: **report viewer** card with the review queue (documents to review across patients).
- Right 5 columns: greeting card ("Good morning, Dr. Rao" + date + open items + a 4-segment *workload* bar),
  **Today's patients** (time · avatar · name · age/sex · status badge · reason · problem chips · "N result back"
  / "N abnormal" badges · Open/Continue button), then *Abnormal results* and *Most urgent* tiles,
  then *Patients needing attention*.

### 10.3 Patient workspace (every patient screen)

```
[<] (RV) Rohit Verma                    [⚠ Sulfa drugs · moderate] [BPH] [Dyslipidaemia] [+2]   [Ask about patient] [Consultation] [⋯]
    LCM-10231 · 69 y · Male · DOB 10 May 1957 · Blood B+
( Overview | Consultation | Timeline | Reports & imaging 5 | Results | Orders | Prescriptions | … )   ← glass tab pill
──────────────────────────────────────────────────────────────────────────────
tab content
```

- The **identity header is never scrolled away** from the patient's context; allergies are the first chips and
  are always `danger` badges with the alert icon. No allergies recorded → a `warning` badge
  "Allergies not documented" (never silence).
- Tabs are a horizontal glass pill; the active tab uses `strong`. Counts sit in a small muted bubble.
- **Overview:** report viewer (7 col) + right column of insight cards: score card with level bar ("Glycaemic
  control · 8.1 % · Well above general target", pager 1/2), *now vs previous* comparison, a sentence card
  ("Fasting glucose has **risen by 14 mg/dL** since 12 Jun 2026") with *View full report*, *Key areas of concern*
  (three range-bar tiles), *Care overview* tabs (Action plan / Medications / Scores / Problems).

### 10.4 Consultation

Two equal columns:

- **Left:** *Before you see the patient* (last time, results since then, reports & tests, AI pre-visit brief) →
  *Consultation notes* (chief complaint, history, vitals strip of 5 boxed inputs with unit suffixes,
  examination, diagnosis chips, assessment, plan) → *Diagnosis — second look*.
- **Right:** *Prescription* (checked-against chips, diagnosis, medicine lines with live findings, advice,
  follow-up, clinical review, **Finalise prescription** in `strong`) → *Investigations*.
- A consultation status bar on top: icon tile, "Consultation · In progress", start time, and
  **Complete consultation** (`strong`, pill).

### 10.5 Assistant (chat)

Three columns: conversation list (left, ~260 px) · conversation (centre, max 760 px reading width, composer
pinned to the bottom, `rounded-full` send button) · evidence panel (right, ~360 px, tabs *Sources* / *Why this
answer*).

### 10.6 Settings

Left: grouped vertical nav (Profile, Appearance, … ; admin groups below). Right: stacked cards, one per topic,
each with title, description, fields and a footer with **Test** (secondary) and **Save** (primary).

### 10.7 Sign-in

Split card centred on the canvas: left half a deep navy panel (`strong`) with the logo, the hero line, three
feature rows (icon in a white/10 circle + title + one line) and the disclaimer; right half white with
"Sign in", the organisation's message, Email, Password (show/hide toggle) and a full-width `strong` pill
**Continue →**.

---

## 11. Core components

All live in `frontend/src/components/ui`. Build them as components with variants in Figma.

### 11.1 Button

Base: Inter 500, 13 px, `rounded-md`, 8 px icon–label gap, 16 px icons, 150 ms transitions, **pressed = scale
0.98**, disabled = 50 % opacity, focus = 2 px `ring/40` ring with 1 px offset. A loading button shows a spinner
before the label and is disabled.

| Variant | Fill / text | Use |
|---|---|---|
| `strong` | navy `strong` / white | The one key action: Start consultation, Finalise, Continue, + New |
| `primary` | accent / white | Primary action where navy would be too heavy (forms, dialogs) |
| `secondary` | white 90 % with border / ink | Second action: Order test, Print, Test connection |
| `soft` | `primary-soft` / `primary-soft-foreground` | AI actions: Prepare brief, Check diagnosis, Review with clinical AI, Read report against the question |
| `ghost` | transparent / muted → `muted` fill on hover | Tertiary: Hide, Regenerate, Close |
| `danger` | `danger` / white | Destructive confirm (Delete, Proceed despite critical) |
| `danger-ghost` | transparent / danger text | Remove a line, cancel an order |
| `link` | accent text, underline on hover | Inline links |

| Size | Height | Horizontal padding | Text |
|---|---|---|---|
| `xs` | 28 px | 8 px | 12 px, 14 px icon |
| `sm` | 32 px | 12 px | 12 px |
| `md` (default) | 36 px | 16 px | 13 px |
| `lg` | 40 px | 20 px | 13 px |
| `icon` / `icon-sm` / `icon-xs` | 36 / 32 / 28 px square | — | — |

Prominent page and card actions are **pills** (`rounded-full`); buttons inside forms keep `rounded-md`.

### 11.2 Badge and dot

`rounded-full`, 1 px border (transparent except `outline`), 8 px × 2 px padding, 10.5 px / 500, 12 px icon.
Tones: `neutral` (muted), `primary`, `success`, `warning`, `danger`, `info`, `outline`. A `square` variant uses
`rounded-md`. **Dot:** 8 px circle in the solid status colour; `pulse` adds a ping ring for live states.

### 11.3 Card

`glass` + `rounded-2xl` + white/70 border + `shadow-card`. **CardHeader**: 32 px icon circle (optional) · title
(0.95 rem / 600, truncates) · description (0.8 rem muted) · right-aligned actions (6 px gap). Padding:
`--card-pad` on all sides. Body content uses the same padding. Inner sub-panels inside a card use
`rounded-xl`, 1 px `border/60`, `card/70` fill and 12 px padding (e.g. *Last time*, stat tiles).

### 11.4 Inputs

- **Input:** 36 px high, `rounded-lg`, 1 px `input` border, `card/90` fill, 12 px side padding, 13 px text,
  placeholder muted at 70 %. Focus: border `primary/60` + 3 px `ring/15` halo. Invalid: `danger` border.
  Optional leading icon (16 px, 12 px in) and trailing slot (e.g. show/hide password, unit suffix).
- **Textarea:** same, min-height 84 px, relaxed line-height.
- **Field:** label (0.8 rem / 500) · optional action at the right of the label · control · hint (0.75 rem muted)
  or error (0.75 rem danger). Required = red asterisk. 6 px vertical gaps.
- **Vitals box:** a bordered tile with the uppercase micro label (BP, PULSE…) top-left, value input, unit
  suffix right (mmHg, /min, °F, %, kg).
- **Select, Checkbox, Switch, Slider:** Radix primitives styled to the same input border, radius and focus ring.
  `SwitchRow` = label + description on the left, switch on the right, for settings.

### 11.5 Segmented control and tabs

- **Segmented** (filters such as *All / Reports / Imaging*, *Open / All*): `rounded-full` track in `muted/80`
  with a `border/60` border and 2 px padding; the selected segment is a white (`card`) pill with `shadow-xs`;
  others are muted text.
- **Tabs** (patient workspace, care overview): `rounded-full` glass/`muted` track with 4 px padding; the active
  tab is a `strong` pill (navigation) or a white pill (in-card tabs).

### 11.6 Table

Full width, 13 px. Header row: `subtle/70` fill, 36 px high, `.text-label` style (uppercase, 0.72 rem, muted).
Rows: bottom border, `--row-y` vertical padding, 16 px side padding; clickable rows get `muted/50` hover.
Numeric columns right-aligned and tabular. Source columns show a link ("Report, page 1") over a monospace excerpt.

### 11.7 Overlays

- **Dialog:** `slate-950/40` backdrop with 2 px blur; panel `popover`, `rounded-2xl`, `shadow-float`, max width
  per use (sm 28 rem ≈ 420 px / md 32 rem ≈ 480 px / lg 42 rem ≈ 630 px / xl 56 rem ≈ 840 px at the 15 px root). Header: 36 px icon tile + title (1 rem / 600) + description, close ✕;
  body scrolls; footer on `subtle` with right-aligned buttons.
- **Sheet:** side panel sliding from the right (250 ms), used for document details and mobile navigation.
- **Dropdown menu / Popover:** `popover`, `rounded-xl`, `shadow-pop`, 4 px padding; items 32 px high,
  `rounded-md`, muted hover. Destructive items in danger text.
- **Tooltip:** inverted — `foreground` background with `background`-coloured 0.75 rem text, `rounded-md`, 8 × 4 px padding, `shadow-pop`, max width 20 rem, 6 px from the trigger, 150 ms fade.
- **Toast** (Sonner): bottom-right, rich colours, close button, Inter.
- **Command palette** (⌘K / Ctrl K): centred dialog with search input and grouped results.

### 11.8 Misc

- **Avatar:** initials, pastel tone (§3.5); sizes xs 24 · sm 28 · md 36 · lg 44 · xl 56 px. Initials skip
  titles ("Dr. Ananya Rao" → AR) and use first + last name.
- **Kbd:** small rounded key cap for shortcuts (`G H`, `⌘K`).
- **KeyValue:** label left (muted), value right, 6 px vertical padding — for detail panels.
- **Skeleton:** `muted` rounded block with a 1.4 s shimmer sweep.
- **Spinner:** `Loader2` rotating, 16 px.

---

## 12. Clinical components

These are what make the product feel clinical. Keep them visually identical everywhere they appear.

### 12.1 Report viewer

The centre of every patient dashboard and of *Reports & imaging*.

- Stage: `rounded-3xl`, min-height 420 px. Light documents sit on a soft accent-tinted gradient
  (`radial accent/10 % top-left` over `subtle → muted`); **imaging (X-ray, CT, MRI, ECG) switches the stage to a
  dark radial `#1E293B → #020617`** so images read like on a radiology monitor.
- Top bar: icon circle (FileText in accent / ScanLine on white/10), title, "Kind · date · page x of y",
  and round 36 px buttons on the right (details ⓘ, open original ↗).
- Thumbnail strip: a glass pill under the title; each thumbnail 44 × 56 px, `rounded-lg`, 2 px border;
  the active one has a `primary` border + `primary/30` ring; hover lifts 2 px. Tooltip = title · date.
- The page/image itself: white page with `rounded-md` + `shadow-float` (documents) or a drop shadow (images).
- Bottom-right floating round buttons: zoom in (+), zoom out (−), full screen.
- A wrong-patient document shows a `danger-soft` banner across the top of the stage.

### 12.2 Lab value tile ("Key areas of concern")

```
Creatinine                                   ›
1.36 mg/dL                     ↗ Above range        ← value 1.6rem/600 tabular · unit muted · status in danger text
[▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬|▬▬▬▬▬▬▌▬▬▬]                       ← range bar
      0.7          1.3                               ← limits as stated by the source
```

### 12.3 Range bar

10 px tall pill filled with the range gradient (§3.4). White 1 px ticks at the source's low/high limits; the
patient's value is a 4 × 18 px dark (`foreground`) marker with a 2 px `card` ring, positioned on the scale.
Tick labels in 0.65 rem tabular muted below. If the source gave no range, the bar is plain `muted` — **never
invent a range**.

### 12.4 Level bar and stack meter

- **Level bar** (scores): N equal 6 px segments with 4 px gaps; filled segments go green → amber → orange → red
  by position; unfilled are `muted`. Used for Glycaemic control, CKD stage, CHA₂DS₂-VASc, workload.
- **Stack meter** (now vs previous): six 5 px stacked bars; filled = `danger/80` when worse, `strong/70` otherwise.

### 12.5 Now vs previous

Two big numbers side by side: "Now" (danger stack if worse) › "Previous · 12 Jun 26" (navy stack), each with
unit in small muted text. Next to it, a sentence card in plain language with the change highlighted in the
status colour: *"Fasting glucose has **risen by 14 mg/dL** since 12 Jun 2026 — currently **above range**."*
and a `strong` pill **View full report ↗**.

### 12.6 Safety finding rows (prescription checks)

Each medicine line is a bordered `rounded-xl` row (outline colour = worst finding: danger / warning / none)
containing the medicine input, dose, frequency select, days, remove ✕, instructions, the resolved composition
("Pantoprazole 40 mg + Domperidone 30 mg · 40 mg/day + 30 mg/day") and a status tag right-aligned
(**⊘ Stop & check** in danger, **⚠ Caution** in warning).

Findings are stacked soft rows, `rounded-lg`, 8 × 12 px padding:

```
⊘  Allergy: Sulfa drugs — Sulfamethoxazole — documented Sulfa drugs allergy (reaction: Itchy rash (2019)).   ← danger-soft
⚠  Dicyclomine: Benign prostatic hyperplasia — Risk of urinary retention.                                    ← warning-soft
ⓘ  Pantoprazole: Age 69 — Beers 2023: avoid scheduled PPI use beyond 8 weeks without a clear indication.     ← info-soft
```

Bold lead ("Allergy: Sulfa drugs") in the status foreground, explanation in normal weight. A critical finding
adds a danger-bordered input: *"Reason to proceed anyway (required to finalise)"*. Above the lines, the
**Checked against** chips: `69 y · older adult`, `78 kg`, `eGFR 55` (warning if reduced), `Allergy: Sulfa drugs`
(danger), `5 current medicines`. Card header summary chip: "1 critical · 1 caution".

### 12.7 Patient row (today's list)

Time (tabular, muted) · avatar · **name** · "69 y · Male" · status badge (Waiting = `primary-soft`, Expected =
`muted`, Seen = `success-soft`, Cancelled = muted with strike-through) · reason (muted) · up to two problem chips (truncate) · "⚗ N result back" (warning) ·
"N abnormal" (danger) · "✦ Brief ready" (primary) · right: **Open ›** (secondary pill) or **Continue**
(`strong` pill when a consultation is in progress).

### 12.8 Order card (investigations)

Icon tile · test name (600) · status badge (*Ordered* neutral → *Result back — review* warning → *Reviewed*
success) · "Ordered 23 Oct 2026 · result 23 Oct 2026 · reason" · linked report with FileText icon · AI reading
panel (§13) · note input + **Mark reviewed** (`strong`, small pill). A result-back card has a soft warning outline.

### 12.9 Inbox item

Status icon tile (left, tinted by type) · title ("Result back: TMT", "CRP high: 58 mg/L") · patient name + MRN ·
detail · relative time · right: **Acknowledge** (secondary) and **Open** (ghost). Urgent items get a `danger`
"Urgent" badge and sort first. Filter by a segmented control with counts (All 164 · Urgent 1 · Abnormal labs 78…).

### 12.10 Allergy and problem chips

Allergy: `danger` badge with ⚠ — "Sulfa drugs · moderate". Problems: `neutral` badges, max-width 14 rem,
truncated, overflow as "+N". Allergies always come first.

---

## 13. AI surfaces

AI output must always be recognisable as AI and as a draft.

- **Trigger buttons:** `soft` variant with the `Sparkles` icon ("✦ Prepare brief", "✦ Check diagnosis",
  "✦ Review with clinical AI", "✦ Read report against the question").
- **Empty AI card:** dashed `primary/30` border, `primary-soft/40` fill, Sparkles icon, one-line explanation of
  what the AI will read, and the trigger button.
- **AI result panel:** `rounded-xl`, 1 px `primary/20` border, `primary-soft/30` fill, 14 px padding. Top line =
  **run meta** in 0.7 rem muted: `✦ med-ai · just now · 2.4 s` · an `outline` badge **"Draft · verify before
  acting"** · **Regenerate** (ghost). Then the content.
- **Verdict tags** inside AI panels: *Routine* (success), *Partly consistent* (warning), *Unsafe* (danger),
  *Agree with the rule check* (sparkle line in muted).
- **Structured sections** use `.text-label` headings: ASK ABOUT, SINCE LAST VISIT, WATCH OUT TODAY, KEY
  FINDINGS, NEXT STEPS TO CONSIDER, RED FLAGS (on `danger-soft`), TESTS THAT WOULD HELP. Numbered questions use
  18 px navy circles with white numbers.
- **Citation chips:** inline monospace chips, 18 px high, `rounded`, 0.68 rem / 600, tinted by source:
  `P1, P2…` patient documents (`info` soft/foreground), `K1…` knowledge library (`primary-soft`), `W…` web
  sources (`warning` soft), `R` structured record (`success` soft).
  Hover/active = 1 px ring in the chip colour. Clicking opens the source in the evidence panel.
- **Evidence panel:** list of source cards — label chip + title, "Patient document · page 1 · 12 Oct 2026",
  the quoted excerpt (0.78 rem muted, 5 lines), retrieval scores in micro text, **Open document**.
- **Streaming:** text appears progressively with a blinking caret (`blink` 1 s); a status line shows the stage
  ("Searching records and knowledge").
- **Patient-facing text** (e.g. "For the patient: …") sits in a white inset box with a bold lead-in.

---

## 14. Data visualisation

Library: Recharts. Charts must be readable in both themes and printable.

- **Trend line:** 2.25 px monotone line in `primary`, points as 9 px dots with a 2 px `card`-coloured ring;
  **flagged points (high / low / abnormal) in `danger`**. The source's reference range is a `success` band at 8 %
  opacity with a `success` edge. Light horizontal grid lines in
  `border`; axis labels 0.75 rem muted, tabular. Dates on the x-axis as "15 Oct 25".
- **Sparklines** (results list): 90 × 32 px area line, red tint when the latest value is flagged, blue otherwise,
  next to "1.62 mg/dL ↗ +0.17".
- **Workload bar:** 4 segments green / amber / orange / red under the greeting.
- One chart, one message: title states the test and "3 measurements · reference 0.5 – 1.1 mg/dL (as stated by
  the source)". No legends unless there are two series.

---

## 15. Motion

Motion is short and functional; it confirms that something happened. Nothing loops except loading indicators.

| Name | Duration | Easing | Use |
|---|---|---|---|
| `fade-in` | 150 ms | ease-out | Overlays, dialog backdrop |
| `slide-up` | 200 ms | `cubic-bezier(0.16, 1, 0.3, 1)` (expo-out) | New cards, toasts, AI results appearing (6 px rise) |
| `scale-in` | 150 ms | expo-out | Dialogs, popovers (from 97 %) |
| `slide-in-right` | 250 ms | expo-out | Side sheets |
| Hover / colour | 150 ms | default | Buttons, rows, chips |
| Press | instant | — | Buttons scale to 98 % |
| `shimmer` | 1.4 s loop | linear | Skeletons only |
| `blink` | 1 s step | — | Streaming caret only |

**Reduce motion** (Settings → Appearance, also respects the OS): all animations and transitions drop to ~0 ms.
Never encode meaning only in motion.

---

## 16. States: empty, loading, error, disabled

- **Empty:** centred `EmptyState` — 44 px icon tile, title (13 px / 600), one-line description that says
  *what will appear here and how*, optional action. E.g. "No tests ordered in this consultation".
- **Loading:** skeleton shapes that match the final layout (never a full-page spinner). Buttons that started
  work show their own spinner. Documents in processing show "⟳ Processing document…" in the viewer.
- **Error:** inline, close to where it happened, in danger text with what to do next. Toasts only for
  background failures ("Could not save the prescription").
- **Disabled:** 50–60 % opacity, no pointer; explain *why* nearby when it isn't obvious ("Add a reason to
  proceed to finalise").
- **Saving:** a quiet "Saving… / Saved" indicator in the card header, never a modal.

---

## 17. Writing (UX copy)

- **Plain clinical English.** Short sentences, sentence case, no exclamation marks, no jargon the doctor
  wouldn't use. Indian clinical conventions: brand names as written on the strip (Dolo 650, Pan-D), OD / BD /
  TDS / HS, mg/dL, "follow-up".
- **Say what the thing does for the doctor**, not how it works: "Reads the full record — previous complaints,
  results, reports and medicines — and suggests what to ask today."
- **Findings** follow *what — why — what to do*: "Dicyclomine: Benign prostatic hyperplasia — Risk of urinary
  retention."
- **Never overstate AI.** Use "suggests", "consider", "draft". Every AI panel says *verify before acting*.
- **Numbers:** always with unit and date; ranges "as stated by the source"; trends with direction and amount
  ("risen by 14 mg/dL since 12 Jun 2026").
- **Buttons are verbs:** Start consultation, Write prescription, Order test, Mark reviewed, Finalise
  prescription. Avoid "OK", "Submit".
- **Dates:** "23 Oct 2026" in the UI; "Fri, 23 October 2026" in greetings; relative ("2 minutes ago") only for
  activity, never for clinical dates.

---

## 18. Accessibility

- Contrast: body text ≥ 4.5 : 1, large text and UI components ≥ 3 : 1 in both themes. The accent foreground
  is computed to stay ≥ 3 : 1 (§3.2).
- **High-contrast mode** (Settings → Appearance) strengthens `muted-foreground` (`#3C495D` light / `#C8CFDA` dark),
  `border` and `input`. Check new screens in it.
- **Focus:** every interactive element shows a 2 px `ring` outline with 2 px offset on keyboard focus.
- Hit targets: ≥ 32 px (36 px default) for controls; icon-only buttons have `aria-label` and a tooltip.
- Keyboard: ⌘K / Ctrl K palette, `G` + letter navigation, Enter to add diagnoses and pick suggestions, Esc to close.
- **Text size** user setting (14 / 15 / 16.5 px root): layouts must reflow, never clip.
- Status = icon + word + colour (§3.3). Charts mark out-of-range points by colour *and* by the table below.

---

## 19. Dark mode

Dark mode is a first-class theme (user choice: Light / Dark / System; organisation default in Branding).

- Canvas `#0C0F18`, cards `#141924` glass at 72 %, borders `#272C3A`, card edges `white / 6 %`.
- Shadows lose their navy tint (pure black) and matter less; separation comes from the slightly lighter cards.
- `strong` flips to a **bright blue** (`#4C80F0`) with near-black text, so key actions still stand out.
- Status soft fills become deep tints (`danger-soft #3B1616`) with light foregrounds (`#F98B8B`).
- The report viewer's imaging stage is dark in both themes; light documents stay white pages.
- Test every new screen in both themes before handing off.

---

## 20. Responsive behaviour

Breakpoints (Tailwind): `sm` 640 · `md` 768 · `lg` 1024 · `xl` 1280 · `2xl` 1536 px. Designed first for
**1440–1920 px desktops**, then laptop 1280, tablet 1024/768, phone 390.

- **< 768 px:** the centre nav pill becomes a horizontally scrolling row of small pills under the header; the
  left rail moves into a hamburger sheet; header icon buttons shrink to search + inbox + avatar.
- Two-column layouts (dashboard, overview, consultation) stack: viewer/notes first, insights/prescription second.
- Patient header chips wrap; tabs scroll horizontally.
- Tables scroll horizontally inside their card; never shrink text below 0.72 rem.
- Minimum supported width: 360 px with a 12 px side gutter, no horizontal page scroll.

---

## 21. Print

The printed prescription (`/print/prescription/:id`) is A4, white, black text, no app chrome (`.no-print`):
organisation header (logo, organisation name, tagline) with the doctor's name and contact on the right, the date,
patient line (name, age/sex, MRN, phone), vitals, complaint and diagnosis, a serif italic **℞** mark, a numbered
table (medicine with generic composition beneath, dose, when — e.g. "OD · Once a day" — days, instructions),
advice, follow-up, prescription ID and a signature line. Use the same type scale at 1 : 1 and no colour except the logo.

---

## 22. Do and don't

| Do | Don't |
|---|---|
| Keep the canvas blue-grey and the cards white glass | Put cards on pure white or add busy backgrounds |
| Use `strong` (navy) for the one key action per area | Use several navy buttons side by side |
| Show the source, date and range with every value | Show a number without unit, date or provenance |
| Use danger/warning only for clinical meaning | Use red or amber for decoration or branding |
| Pair every status colour with an icon and a word | Rely on colour alone |
| Mark AI output as a draft with model and time | Present AI text as final or unattributed |
| Use pills for navigation, filters and status | Use pills for text inputs |
| Sentence case, verbs on buttons | Title Case, "Submit", "OK" |
| Tabular numbers for anything compared | Proportional digits in tables and vitals |
| Test with Rose/Amber accents, dark mode, compact density, 16.5 px text | Design only for the default blue, light, comfortable |

---

## 23. Setting it up in Figma

1. **Variables → Collections:** create `Theme` with modes **Light** and **Dark**; add every colour token from §3.1–3.3
   with the hex values above. Create `Accent` with modes for each preset (§3.2) holding `primary`,
   `primary-soft`, `primary-soft-foreground`, `strong`, `strong-foreground`.
2. **Number variables:** `radius` (9 / 11 / 13 / 17 / 21 / 24 / 999), `space` (4 / 6 / 8 / 12 / 16 / 20 / 24 / 32),
   `card-pad` (19 / 13.5), `row-y` (11 / 7) with modes **Comfortable** and **Compact**.
3. **Text styles:** one per row of the type scale (§4), Inter, with tabular figures on the numeric styles.
4. **Effect styles:** `shadow/xs`, `shadow/card`, `shadow/pop`, `shadow/float` using colour `#1E325A` at the
   given opacities (light) and black (dark); `glass` = white 78 % fill + background blur 18.
5. **Components with variants:** Button (variant × size × state), Badge (tone × icon), Input/Textarea/Field
   (state), Segmented, Tabs, Card + CardHeader, Dialog, Menu, Table row, Avatar (size), and the clinical set:
   Range bar, Level bar, Lab value tile, Now-vs-previous, Finding row (danger/warning/info), Medicine line,
   Patient row, Order card, AI panel, Citation chip (P/K/R), Report viewer (document/imaging).
6. **Frames:** desktop 1440 × 900 and 1920 × 1080, laptop 1280 × 800, phone 390 × 844. Use a 12-column
   layout grid, 24 px margins, 16 px gutters, max content 1680 px.
7. **Icons:** install the Lucide Figma plugin; 16 px default, stroke 2 (1.9 in navigation).
8. **Reference screens:** run the app with the demo data (`docs/DEPLOY_LOCAL.md`) and screenshot each page in
   light and dark; the product film (`video/`) shows the main flows in motion.

---

## 24. New-screen checklist

Before a new screen is ready to build:

- [ ] Uses only tokens from this document (no new hex values, radii or shadows).
- [ ] Patient screens keep the identity header (name, age/sex, MRN, allergies first).
- [ ] One `strong` action per area; secondary actions are `secondary`/`ghost`; AI actions are `soft` + ✦.
- [ ] Every clinical number has unit, date and source; ranges only as stated by the source.
- [ ] Every status has icon + word + colour; critical before caution before info.
- [ ] AI output shows model, time, "Draft · verify before acting" and citations where it uses evidence.
- [ ] Empty, loading, error, disabled and saving states are designed.
- [ ] Works in Light and Dark, Comfortable and Compact, with the Rose and Amber accents, at 14 and 16.5 px text.
- [ ] Keyboard focus visible on every control; icon-only buttons have labels/tooltips.
- [ ] Reflows at 1280, 1024, 768 and 390 px without horizontal scrolling.
- [ ] Copy is sentence case, verbs on buttons, plain clinical English.
