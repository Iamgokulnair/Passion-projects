# Setup -- one time

**macOS / Linux:**

```bash
cd html-to-ppt
./scripts/setup.sh
```

**Windows (PowerShell):**

```powershell
cd html-to-ppt
.\scripts\setup.ps1
```

Creates a self-contained `.venv` (Python 3.12) inside the skill. Installs `python-pptx`,
`beautifulsoup4` + `tinycss2` (fallback parser), `Pillow`, and `playwright` (+ downloads a
headless Chromium binary, ~150-300MB, one time). Nothing installed system-wide; Homebrew is
not required. Idempotent -- safe to re-run.

If Windows blocks `setup.ps1` from running ("this file came from another computer"), the
repo was downloaded as a ZIP rather than `git clone`d -- run
`Unblock-File .\scripts\setup.ps1` first.

Check state at any time without changing anything:

```bash
./scripts/setup.sh --check      # macOS/Linux
.\scripts\setup.ps1 -Check      # Windows
```

---

## LibreOffice -- optional, strongly recommended

Powers the visual Perceive Gate (Step 4 of `SKILL.md`): converting the built `.pptx` to a
PDF that gets actually looked at, page by page, before the deck is called done.

```bash
brew install --cask libreoffice                    # macOS
winget install TheDocumentFoundation.LibreOffice    # Windows
```

**This is optional.** Without it, `scripts/render_preview.py` falls back to geometry-only
checks -- it can still catch overlapping or off-slide shapes numerically, but it cannot see
contrast failures, chart-integrity problems, or whether a rasterized gradient background
actually looks right. The pipeline still produces a real `.pptx` either way; only the QA
coverage differs, and every report says explicitly which tier ran.

---

## Verify end to end

```bash
# macOS/Linux
./scripts/setup.sh --check
.venv/bin/python scripts/convert.py examples/sample.html
```

```powershell
# Windows
.\scripts\setup.ps1 -Check
.venv\Scripts\python.exe scripts\convert.py examples\sample.html
```

`examples/sample.html` has a linear gradient, a radial gradient, a table, and an embedded
image -- enough to exercise every stage. Expect a `deck.pptx` next to it, plus
`.manifest.json`, `.slide_plan.json`, `.build_report.json`, `.render_report.json`, and
`.fidelity_report.json` -- and a printed fidelity verdict.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `playwright install chromium` fails (corporate proxy/firewall) | `parse_html.py` falls back to BeautifulSoup4-only parsing automatically -- inline/`<style>`-block styles only, no CSS cascade resolution. It prints a loud warning, doesn't fail silently. |
| `render_preview.py` reports tier `geometry-only` | LibreOffice (and, on Windows, PowerPoint COM) weren't found. Install LibreOffice above, or accept the reduced QA coverage -- the report says exactly what was skipped. |
| Font looks different from the source page when opened in PowerPoint | Expected -- see README's Known limitations. Check `<deck>.build_report.json`'s `font_substitutions` list for what was swapped. |
| A gradient's middle color looks slightly off after opening in PowerPoint | The source had 3+ gradient stops; `python-pptx`'s stable API only exposes the stop count baked into the preset fill, so mid-stops are simplified to first/last. Check `gradient_notes` in the build report. Rasterize (automatic for radial/conic) is the exact-fidelity path. |
| `verify_fidelity.py` reports FAIL | Read `<deck>.fidelity_report.json` -- it lists exactly which element(s) were dropped or truncated and on which slide. This should not happen in normal operation; if it does, it's the pipeline's own bug, not expected behavior. |
| `setup.ps1` won't run: "from another computer" | ZIP download, not `git clone` -- run `Unblock-File .\scripts\setup.ps1` |
| `Activate.ps1 cannot be loaded` | Don't activate the venv -- invoke `.venv\Scripts\python.exe` directly, as shown above |
| Remote (`http://`/`https://`) image in the source HTML doesn't appear | Check network access; `build_pptx.py` fetches it at build time and logs a failure note rather than silently skipping (see the build report). `data:` and `file://` images never need network access. |
