---
name: html-to-ppt
user-invocable: true
description: >-
  Convert an HTML page, mock, or set of HTML slides into a real, industry-grade PowerPoint
  deck (.pptx) -- entirely portable, zero MCP-connector dependency, works identically in
  Claude Code and Cursor on macOS (Apple Silicon or Intel) and Windows. Not a mechanical
  content dump: the deck is built via a bundled Python engine (Playwright + python-pptx),
  rendered, and scored against a named MBB-style craft standard before being called done.
  Use for "turn this HTML into a PowerPoint", "convert this page to a deck", "make a .pptx
  from this mock", "export this HTML as slides", "build a presentation from this webpage".
  Do NOT use for a from-scratch deck with no HTML source. Do NOT use for an interactive/live
  deck meant to stay a webpage -- this skill's output is always a static, real `.pptx` file.
metadata:
  version: "1.0"
  author: gokulv
  created: "2026-08-04"
---

# html-to-ppt

HTML source in -> a real, editable `.pptx` out, checked against a named craft standard and
a content-fidelity gate before it's handed back. Runs entirely from the scripts bundled in
this folder -- no PowerPoint MCP, no macOS-only tools. First run ever? See `SETUP.md`.

> **`$SKILL` = the directory this `SKILL.md` file sits in.** Substitute that path when you run
> the commands below. Never use a remembered absolute path — this skill is installed to a
> different location on every machine.

```bash
"$SKILL/.venv/bin/python" "$SKILL/scripts/convert.py" <input.html>        # macOS/Linux
```
```powershell
& "$SKILL\.venv\Scripts\python.exe" "$SKILL\scripts\convert.py" <input.html>   # Windows
```

`convert.py` alone runs the deterministic backbone (parse -> build -> render -> fidelity
check) with a default heuristic content-mapping. The steps below are what turns that into
an actually-good deck: they add the judgment layer (content clustering, craft scoring, an
independent QA pass) on top.

## Step 0 -- Intake

Read the source HTML (content and structure: headings, bullets, images, tables). Lock a
lightweight brief before building anything:

- **Audience / occasion** -- who's in the room, how formal.
- **Target length** -- rough slide count, or "let the content decide." For a long
  single-page HTML document, force a decision here (content-driven vs. a hard slide cap) --
  otherwise Step 1 has no stopping rule.
- **Look** -- preserve the source page's visual design, or redesign to deck-native
  conventions (see `standards/deck.md` -> Style reference)? Default to deck-native unless
  asked to preserve -- a webpage's layout rarely survives translation to a slide well.

Skip asking if the request already answers these.

## Step 1 -- Parse and content-map

Run the parser first, then reason over its output -- don't re-read raw HTML for mapping
decisions, so every mapping choice is traceable back to a manifest element id:

```bash
.venv/bin/python scripts/parse_html.py <input.html> --out /tmp/manifest.json
```

This produces a flat, ordered JSON manifest of every content-bearing element (headings,
text, list items, table rows, images, background panels) with computed styles and
geometry. Cluster its elements into one-idea-per-slide units using the Pyramid Principle
(answer first, support after) and a MECE check -- both are inlined in
`standards/deck.md`'s checklist. Pick a layout archetype per slide from the Style
reference there -- never invent a new layout per slide.

Write your grouping as a `slide_plan.json` (schema: see `default_plan()` in
`scripts/build_pptx.py` for the exact shape it produces automatically -- match that shape).
**Excluding page chrome is a legitimate decision here** (nav bars, cookie banners, repeated
boilerplate) -- note what you excluded and why in your Step 7 report; that is not the same
as accidentally dropping content that should have been included.

If the request is simple enough that the default heuristic grouping (heading-boundary
splits, sorted by vertical position) is good enough, you can skip authoring a plan and let
`build_pptx.py` generate one -- it always writes whatever plan it used to
`<input>.slide_plan.json`, so the decision is visible either way.

## Step 2 -- Confirm the craft standard

Read `standards/deck.md` in this skill folder. It is self-contained -- no external skill or
path dependency -- and frozen for this run; don't edit it to make a slide easier to pass.
A different named exemplar can be applied for a specific run without overwriting the file.

## Step 3 -- Build

```bash
.venv/bin/python scripts/build_pptx.py <input>.manifest.json --plan <input>.slide_plan.json --out deck.pptx
```

Applies the Style reference's type scale/palette and the gradient decision rule from
`standards/deck.md` automatically (native linear-fill vs. rasterized background). Produces
`deck.pptx`, `deck.build_report.json` (font substitutions, gradient notes, and the
element-id -> written-text index the fidelity gate needs), and, if no `--plan` was given,
`<input>.slide_plan.json`.

**Gate:** every content unit from Step 1 has a slide; the build script exits 0.

## Step 4 -- Perceive Gate

Actually look at the rendered deck -- don't assume it's clean because the build step didn't
error.

```bash
.venv/bin/python scripts/render_preview.py deck.pptx
```

Runs the fallback chain from `standards/deck.md` (LibreOffice -> optional Windows COM ->
geometry-only) and writes `deck.render_report.json` stating which tier actually ran. If
LibreOffice produced a PDF, `Read(<pdf>, pages="1-N")` for every slide. If it fell back to
geometry-only, read the JSON findings instead and say so plainly in the final report --
that tier cannot see contrast, chart integrity, or rasterized-gradient legibility.

## Step 5 -- Content-fidelity check

```bash
.venv/bin/python scripts/verify_fidelity.py deck.pptx deck.build_report.json
```

Independently re-opens the saved file (not the in-memory build objects) and diffs every
planned element's text against what's actually in the deck. Writes
`deck.fidelity_report.json` with dropped/truncated/reflowed-ok counts. **Zero dropped and
zero truncated is required to proceed** -- reflow (whitespace-only difference from
autofit wrapping) is expected and not a failure.

## Step 6 -- Independent QA pass (blind review)

Before reporting the deck as done, review it as if you had not built it: reload only
`standards/deck.md`, the Step 4 render output, and the Step 5 fidelity report -- do not
carry over reasoning from the build steps above.

- **If your host environment can spawn an independent subagent/task** (e.g. Claude Code's
  Task tool), spawn one now with exactly those three inputs and nothing else, and have it
  score the deck.
- **If it can't** (e.g. Cursor's agent mode has no equivalent primitive), perform the same
  review yourself as a distinct, explicitly-labeled pass -- announce "Independent QA pass
  (blind review)" before starting, and deliberately don't reference your own build-step
  reasoning, only the rendered artifact and the standard.

Either way, state in the final report which mode actually ran.

Score every slide against `standards/deck.md`'s 12 craft components, and separately
spot-check a sample of the Step 5 fidelity diff against the rendered pages directly (a
second, independent check in case `verify_fidelity.py` itself has a bug):

- **PASS** requires >=8.0/10 weighted **and** zero binary-critical failures (overlap,
  clipping, contrast, missing source line on a data slide, leftover placeholders) **and**
  the Step 5 fidelity check already passed.
- **FAIL** -- list each defect by slide number.

## Step 7 -- Bounded fix loop

On FAIL, fix only the specific flagged slide(s) -- the smallest edit that resolves the
located defect. Re-render and re-check only the affected pages, don't re-score the whole
deck from scratch. Cap at 3 laps; if still failing after that, stop and report the
remaining defects rather than looping indefinitely -- some fixes (e.g. "the source content
genuinely has two ideas crammed onto one slide") need a human call.

## Step 8 -- Report

State: file path, final weighted score, which components passed, the fidelity-check
counts, which Perceive Gate tier actually rendered it, which mode the independent QA pass
ran in, and any font-substitution or gradient-rasterization notes from the build report.
Don't just say "done" -- say what was actually checked.
