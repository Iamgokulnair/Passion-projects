# 01 - DeckForge (html-to-ppt)

HTML page in, a real editable `.pptx` out, graded against a consulting-craft standard and a
content-fidelity gate. Seven prompts.

---

### Prompt 1 - The brief

```
I want a Claude Code skill called html-to-ppt. Input: an HTML page, mock or set of HTML
slides. Output: a real, editable .pptx - not screenshots pasted onto slides.

Constraints:
- Portable. No PowerPoint MCP connector, no macOS-only tools. Same code path on macOS
  (Apple Silicon and Intel), Windows and Linux.
- Python only, plus a headless Chromium binary.
- It is not a content dump. It should produce a deck a consulting partner would accept.

Before writing any code, give me the architecture as a stage table (stage, tool, output)
and the list of things that can silently go wrong at each stage.
```

**Check:** you get a Parse -> Map -> Build -> Render -> Score -> Verify table and a failure list.

---

### Prompt 2 - Write the standard first

```
Before any build code, write standards/deck.md: a numbered craft rubric of 12 components
for an MBB-style slide. Each component must be independently checkable on a single slide
(action title that states the answer, one idea per slide, Pyramid Principle, MECE
grouping, consistent layout archetype, and so on). Include a style reference that defines
exactly 5 layout archetypes. The rubric is binary per component - pass or fail, no partial
credit.
```

**Check:** 12 numbered, binary components and 5 archetypes. Push back on any component you can't check by looking at one slide.

---

### Prompt 3 - Parse computed styles, not raw markup

```
Write scripts/parse_html.py. Use Playwright to load the page and read COMPUTED CSS
(resolved cascade, external stylesheets, custom properties) plus element geometry. Output
a flat, ordered JSON manifest of every content-bearing element (headings, text, list
items, table rows, images, background panels), each with a stable id. Run it on
examples/sample.html and show me the manifest.
```

**Check:** every visible text element from the sample appears in the manifest with an id.

---

### Prompt 4 - Build with python-pptx

```
Write scripts/build_pptx.py. Input: the manifest plus a slide_plan.json that groups
manifest ids into slides and names one archetype per slide. If no plan is given, generate
a default one (split on heading boundaries, sort by vertical position) and always write
the plan used to <input>.slide_plan.json so the decision is visible.

Gradients: simple linear gradients become native PowerPoint gradient fills. Radial, conic,
multi-layer or clip-path backgrounds are rasterised to a background image with the text
kept native on top. Log every rasterisation and every simplification to
<deck>.build_report.json. Never simplify silently.
```

**Check:** the `.pptx` opens, text is editable, and `build_report.json` lists any gradient compromises.

---

### Prompt 5 - Render and look at it

```
Write scripts/render_preview.py. Render the deck to PDF with LibreOffice headless. On
Windows, fall back to PowerPoint COM if LibreOffice is missing. If neither exists, run a
geometry-only overflow check and say plainly that no visual render happened. Then look at
every rendered page and grade it against standards/deck.md.
```

**Check:** you get a per-slide score against all 12 components, not a general "looks good".

---

### Prompt 6 - The fidelity gate

```
Write scripts/verify_fidelity.py. Re-open the saved .pptx independently - do not reuse
anything held in memory from the build. Diff every element in the slide plan against what
is actually readable in the file. Three buckets: dropped (hard fail), truncated (hard
fail), reflowed - whitespace or line-break differences only (informational). Page chrome
excluded on purpose in the plan is reported as a decision, not a drop.
```

**Check:** delete a line from a built slide by hand and confirm the gate fails.

---

### Prompt 7 - Package it

```
Wrap it up: scripts/convert.py runs parse -> build -> render -> verify end to end. Add
setup.sh and setup.ps1 that create a .venv, install python-pptx and Playwright Chromium,
and write a capability cache to config/engine.json. Write SKILL.md with the step-by-step
procedure (intake brief, parse and content-map, confirm the standard, build, render,
score, independent QA, report), a README with a known-limitations section, and SETUP.md.
```

**Check:** a fresh clone, setup script and one `convert.py` run gives you a deck and a fidelity report.
