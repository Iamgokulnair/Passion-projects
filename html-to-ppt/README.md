# html-to-ppt

Point it at an HTML page or mock and get back a real, editable `.pptx` -- checked against
a named MBB-style craft standard and a content-fidelity gate before it's called done.
Entirely portable: no PowerPoint MCP connector, no macOS-only tools, works the same in
Claude Code and Cursor on any platform below.

## Platform support

| Platform | Parser | Build | Visual QA renderer |
|---|---|---|---|
| **macOS** (Apple Silicon or Intel) | Playwright (Chromium) | `python-pptx` | LibreOffice (optional, recommended) |
| **Windows** | Playwright (Chromium) | `python-pptx` | LibreOffice (optional, recommended), or PowerPoint COM if installed |
| **Linux** | Playwright (Chromium) | `python-pptx` | LibreOffice (optional, recommended) |

Every stage is pure Python + a headless Chromium binary -- identical code path on every
OS. The only thing that varies by platform is which visual-QA renderer gets found; the
pipeline runs and produces a real `.pptx` either way (see [Known limitations](#known-limitations)).

## What it does

| Stage | Detail |
|---|---|
| Parse | Playwright loads the HTML and reads *computed* CSS (resolved cascade, external stylesheets, custom properties) -- not just raw markup, which static parsers can't do |
| Map | Content clustered into one-idea-per-slide units (Pyramid Principle + MECE), one of 5 layout archetypes per slide |
| Build | `python-pptx` writes a real, editable `.pptx`. Gradients: native linear-fill where possible, rasterized background image for radial/conic/complex cases -- see [Gradient handling](#gradient-handling) |
| Render | LibreOffice headless -> PDF (or Windows PowerPoint COM, or a geometry-only fallback with no visual render) -- actually looked at, not assumed clean |
| Score | Every slide graded against a 12-component MBB-mechanics rubric in `standards/deck.md` |
| Verify | The saved file is re-opened independently and every planned text element is diffed against what's actually in it -- catches silent drops or truncation |

## Gradient handling

CSS gradients don't map 1:1 onto what `.pptx` can natively express. The decision rule:

- **Simple linear gradients** (any number of color stops) -> native, editable PowerPoint
  gradient fill. Stays resizable/editable afterward.
- **Radial, conic, multi-layered, or clip-path-based backgrounds** -> rasterized to a
  background image at build time (foreground text stays native and editable on top). This
  is a real limitation, stated plainly: resizing that shape's background afterward in
  PowerPoint will not rescale the gradient, because it's now a flattened image.

Every rasterization and every gradient simplification (e.g. a 5-stop gradient reduced to
its first/last stop because `python-pptx`'s stable gradient API doesn't support arbitrary
stop counts) is logged in `<deck>.build_report.json`, not applied silently.

## Content fidelity

The output is verified, not assumed. `scripts/verify_fidelity.py` re-opens the saved
`.pptx` independently and diffs every element the slide plan included against what's
actually readable in the file, in three buckets: **dropped** (hard fail), **truncated**
(hard fail), **reflowed** -- whitespace/line-break differences from normal text-box
wrapping (informational, not a failure). Deliberately excluding page chrome (nav bars,
cookie banners) during content-mapping is a legitimate editorial decision, surfaced in the
report -- not the same thing as silent data loss, which this gate exists to catch.

## Install

1. **Install Claude Code or Cursor**, if you don't already have one.
2. **Clone this repo** (not a ZIP download -- see the Windows note below):
   ```
   git clone https://github.com/Iamgokulnair/Passion-projects.git
   cd Passion-projects
   ```
3. **Run setup** for your platform:
   ```bash
   # macOS / Linux
   cd html-to-ppt && ./scripts/setup.sh
   ```
   ```powershell
   # Windows
   cd html-to-ppt; .\scripts\setup.ps1
   ```
   Creates a self-contained `.venv` inside the folder (nothing installed system-wide) and
   downloads a headless Chromium binary for Playwright (~150-300MB, one time).
4. **Optional, strongly recommended -- install LibreOffice** for the full visual QA gate:
   ```
   brew install --cask libreoffice        # macOS
   winget install TheDocumentFoundation.LibreOffice   # Windows
   ```
   Without it, the pipeline still produces a real `.pptx`, just with a reduced,
   geometry-only QA pass (no rendered visual check) -- see [Known limitations](#known-limitations).
5. **Symlink into Claude Code** so `/html-to-ppt` becomes available (or copy the folder
   into Cursor's own rules/skills location per its docs):
   ```bash
   # macOS / Linux
   ln -s "$PWD/../html-to-ppt" ~/.claude/skills/html-to-ppt
   ```
   ```powershell
   # Windows -- needs admin or Developer Mode enabled; otherwise copy the folder into
   # %USERPROFILE%\.claude\skills\ instead
   New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills\html-to-ppt" -Target "$PWD\..\html-to-ppt"
   ```
6. **Use it** -- inside a Claude Code or Cursor session:
   ```
   /html-to-ppt path/to/page.html
   ```

If Windows blocks `setup.ps1` ("this file came from another computer"), the repo was
downloaded as a ZIP rather than `git clone`d -- run `Unblock-File .\scripts\setup.ps1`
first.

## Security notes

- **No cloud API calls for the conversion itself.** Parsing, building, and rendering are
  all local. The one exception is an `http(s)://` image `src` in the source HTML, which
  `build_pptx.py` will fetch to embed -- `data:` URIs and local `file://` images never
  touch the network.
- **Review `setup.sh`/`setup.ps1` before running them** -- standard hygiene for any script
  from a public repo. Both are plain `pip`/`uv` installs into a local virtual environment;
  no `curl | bash`, no `sudo`, no admin rights required (except the optional Windows
  symlink step, which has a copy-folder fallback).
- **Never commit `.venv`** -- covered by this folder's `.gitignore`.

## Known limitations

- **Fonts:** `.pptx` references fonts by name only -- there's no reliable way to embed the
  source HTML's actual web font file. A font not installed on the machine that later opens
  the file silently substitutes. Mitigated by mapping to a cross-platform-safe font list
  and logging every substitution, not eliminated.
- **Complex CSS layouts** (grid/flexbox dashboards, absolute-positioned overlapping
  panels) get best-effort mapped onto one of 5 fixed slide archetypes -- a structural
  translation, not a pixel-exact clone, by design.
- **Animations, transitions, hover states, and JS-driven interactivity** are invisible to
  a static computed-style snapshot and are not represented in the output.
- **Without LibreOffice installed**, the visual QA gate degrades to geometry-only checks
  (overlap/overflow via shape math) -- it cannot catch contrast failures, chart-integrity
  problems, or an illegible rasterized gradient. The final report says this plainly when
  it happens; it does not imply full coverage regardless.
- **The Windows path is new and not yet run end-to-end on real Windows hardware by the
  author.** The macOS path is the proven one -- Windows ships as a genuine first release,
  not a fully field-tested equivalent.

Full setup detail and a troubleshooting table: [`SETUP.md`](SETUP.md).
