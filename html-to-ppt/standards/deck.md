# Benchmark Standard — deck

> Self-contained craft rubric for this skill. Adapted from a private consulting-grade deck
> standard (McKinsey/Bain/BCG house-style **mechanics**, not their branding) — this copy has
> no external dependency on any other skill or file outside this repo, so it works for anyone
> who clones this repo, not just the original author.
> Freshness: reviewed 2026-08-04. If your organization has its own house-style rubric, replace
> the checklist and Style reference below with it — the pipeline mechanics (bind → build →
> render → score → fix) stay the same regardless of which rubric is bound.

## Output class
`deck` — a presentation intended to be shown to an audience (`.pptx`, or a PDF exported as
slides).

## Named exemplar
Consulting-grade strategy slides. If a different named exemplar applies for a given run (a
client's own brand deck, a specific competitor's deck style), that one wins for that run — don't
overwrite this cached file from a one-off request.

## Where this checklist comes from
Every row below is inlined directly (not referenced from another skill) so this file stands
alone:

- **Pyramid Principle** (row 6): state the answer/conclusion first, support it after — never
  build up to a reveal. Named after Barbara Minto's structure for consulting writing.
- **MECE** (row 7): groupings should be Mutually Exclusive, Collectively Exhaustive — no bucket
  overlaps another, no obvious gap between them.
- **The "So What?" test** (row 8): for every fact or chart on a slide, ask "so what does this
  mean for the reader" — if the slide doesn't answer that itself, it fails.
- **The 3-second test** (rows 4-5 combined): a reader should get the slide's one point within
  3 seconds of looking at it — one idea, one action title, no hunting for the message.
- **Anti-slop pass** (row 4, copy tone): action titles state a *finding* ("Margins fell 4pts on
  mix"), not a *topic* ("Margins"). No adjectives standing in for evidence. No em-dash-laden or
  triplet-heavy AI-tell phrasing in slide copy.

## The checklist — 12 components, all locatable

| # | Component | How it is checked (where to look) | Scale | Weight |
|---|---|---|---|---|
| 1 | **No overlapping elements** | Every rendered page: any two shapes/text boxes intersecting | binary | critical |
| 2 | **No clipped or overflowing text** | Every page: text extending past its box or the slide edge | binary | critical |
| 3 | **Readable contrast** | Every page: body text vs. its background, WCAG AA or better | binary | critical |
| 4 | **Action titles** | Every page's title: states the *message* ("Margins fell 4pts on mix"), not the *topic* ("Margins") | 1–5 | 0.15 |
| 5 | **One idea per slide** | Each page: can its point be said in one sentence? Two arguments on a page = fail | 1–5 | 0.15 |
| 6 | **Answer first / pyramid** | Deck order: conclusion up front, support after — not a build-up to a reveal | 1–5 | 0.10 |
| 7 | **MECE structure** | Section and bullet groupings: no overlap between buckets, no obvious gap | 1–5 | 0.10 |
| 8 | **So-What present** | Each data page: the implication is stated, not left to the reader | 1–5 | 0.15 |
| 9 | **Chart integrity** | Every chart: axes labelled with units, baseline not truncated, no chartjunk, legend legible | 1–5 | 0.10 |
| 10 | **Source line on every data page** | Footer of each page carrying data | binary | 0.05 |
| 11 | **Consistent grid & margins** | Across pages: title baseline, body block, and page-number positions align; ≥0.5in margins | 1–5 | 0.10 |
| 12 | **Type discipline & no placeholders** | ≤2 typefaces, consistent size ladder; zero "Click to add title"/lorem/template leftovers | binary | 0.10 |

**Craft threshold:** ≥ 8.0/10 weighted **AND** zero failures on binary-critical components.

**Binary-critical (any single failure = FAIL regardless of weighted score):**
#1 overlap · #2 clipping · #3 contrast · #10 missing source on a data page · #12 placeholders.

Rationale: overlaps and leftover placeholders are the exact tells that make a deck read as
machine-made. They are not tradeable against a good score elsewhere.

## Content-fidelity gate (in addition to the 12 craft components)

This is a 13th, separate, binary-critical gate specific to HTML→PPT conversion — the craft
checklist above governs *how the deck looks*, this governs *whether the source content survived
intact*:

| Bucket | Meaning | Verdict |
|---|---|---|
| **Dropped** | Text present in the source HTML manifest, absent from every slide shape | hard fail |
| **Truncated / altered** | Text present but shortened (autofit "shrink to fit" silently cutting content) or characters mangled by font substitution | hard fail |
| **Reflowed** | Text present in full, only whitespace/line-break position differs (expected text-box wrapping) | informational only, not a failure |

**PASS requires zero dropped and zero truncated/altered entries.** Reflow is expected and does
not block PASS. Report exact counts in every run — never just "content preserved."

## Style reference (rides in every build step)
- **Layout archetypes — pick from these, never invent per slide:** (a) title + single chart +
  so-what bar; (b) title + 2–3 column comparison; (c) title + framework diagram; (d) title +
  quantified bullet stack (max 5); (e) section divider.
- **Type scale:** title 28–32pt, body 14–18pt, source 9–10pt. Two typefaces maximum. Prefer a
  cross-platform-safe font (Arial/Helvetica, Calibri, Georgia, Times New Roman) unless the
  target machine is confirmed to have the source's web font installed — see the Known limits
  section below.
- **Palette:** one neutral base + one accent that leads the eye. Neutral by default.
- **Copy tone:** action titles; no adjectives doing the work of evidence; numbers carry units.
- **Visual identity:** NEUTRAL by default. Apply a specific brand identity only on explicit
  request — never by default, never on third-party work.

## How this artifact gets perceived (the Perceive Gate)

Ordered fallback chain, evaluated automatically by `scripts/render_preview.py` — best fidelity
first, most-portable last, so the same command degrades gracefully on any machine:

1. **Preferred, cross-platform: LibreOffice headless.**
   `soffice --headless --convert-to pdf --outdir <dir> <file>.pptx`, then read the resulting PDF
   page-by-page. Free, installs the same way in spirit on macOS and Windows (see this repo's
   `SETUP.md`) — this is the primary path for this skill, not a fallback.
2. **Optional, Windows-only enhancement:** PowerPoint COM automation (`pywin32`), if PowerPoint
   is actually installed and licensed on the machine. Higher-fidelity than LibreOffice for
   PowerPoint-specific rendering quirks, but never the primary path — a skill that only works
   with a paid, Windows-only app installed isn't portable.
3. **Last resort, no visual render: `python-pptx` geometry checks.** Computes each shape's
   bounding rectangle in EMUs and checks pairwise intersection (catches #1 overlap) and
   text-frame overflow (catches #2 clipping) numerically. **Cannot** check #3 contrast, #9 chart
   integrity, or whether a rasterized-gradient background is actually legible — any run using
   this tier must say so explicitly in its report, not imply full coverage.

If none of these produce a usable result, report which tool was missing and FAIL. Never assume
the deck is clean.

## Known limits of this standard
- **Fonts:** PowerPoint/`.pptx` reference fonts by name only — there is no reliable way to embed
  the source HTML's actual web font file into the output. A font not installed on the machine
  that later opens the file will silently substitute. Mitigated by mapping to the safe-font list
  above and logging every substitution, not eliminated.
- **Gradients:** simple linear gradients (any stop count) render as native, editable `.pptx`
  gradient fills. Radial, conic, multi-layered, or clip-path-based backgrounds are rasterized to
  a background image instead — editable text stays native on top, but the background itself
  will not rescale as a gradient if the shape is resized afterward in PowerPoint. This is stated
  in every build report where it applies, not left implicit.
- **Animations, transitions, hover states, and JS-driven interactivity** are invisible to a
  static computed-style snapshot and are not represented in the output.
- **Complex CSS layouts** (grid/flexbox dashboards, absolute-positioned overlapping panels) are
  best-effort mapped to the fixed layout archetypes above — this is a structural translation,
  not a pixel-exact clone, by design.
- This standard governs craft mechanics and content fidelity, not the correctness of the
  underlying content — a factually wrong but well-laid-out, fully-preserved slide can still pass
  this standard; that's on the source HTML's author, not this skill.
