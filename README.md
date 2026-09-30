# Passion-projects

Personal projects built in my own time, not related to my employer or my day job - just
curiosity ones. Three plug-and-play Claude Code / Cursor skills live here, each
self-contained in its own folder, plus the prompt packs that rebuild them and an open case
study on AI adoption.

Clone the repo, run one setup script per skill you want, and go:

```bash
git clone https://github.com/Iamgokulnair/Passion-projects.git
cd Passion-projects
```

## [`html-to-ppt/`](html-to-ppt/)

HTML page or mock in, a real, editable `.pptx` out — checked against a named MBB-style
craft standard and a content-fidelity gate before it's called done. Entirely portable:
no PowerPoint MCP connector, no macOS-only tools, works the same on macOS (Apple Silicon
or Intel) and Windows.

```bash
cd html-to-ppt && ./scripts/setup.sh      # macOS/Linux
cd html-to-ppt; .\scripts\setup.ps1       # Windows
```

Full detail: [`html-to-ppt/README.md`](html-to-ppt/README.md).

## [`transcript/`](transcript/) + [`transcript-to-summary/`](transcript-to-summary/)

Point it at a recording with no captions — a meeting, a lecture, an interview, a call —
and get back a full, timestamped, speaker-labelled transcript. Entirely local: audio
never leaves the machine. Pair it with `transcript-to-summary` and the same pipeline
goes all the way to structured meeting notes (key points, decisions, action items).

```bash
cd transcript && ./scripts/setup.sh       # macOS/Linux
cd transcript; .\scripts\setup.ps1        # Windows
```

Full detail: [`transcript/README.md`](transcript/README.md).

## [`product-history/`](product-history/)

Paste a product link, find out whether the discount is real. Pulls the product's actual
12-month price history from four independent trackers, shows where today's price sits in
that band, and flags dark patterns by their names in India's CCPA Guidelines for Prevention
and Regulation of Dark Patterns, 2023 — fictitious MRP anchors, recycled discounts,
never-was prices. Nothing to install: pure Python standard library, no API key, no login.

When the sources disagree or only one has the product, it refuses to make a call rather
than guessing. A confidently wrong price verdict is worse than none.

```bash
cd product-history && ./scripts/setup.sh   # macOS/Linux — preflight, no install
python3 scripts/ph.py "https://www.amazon.in/dp/B0CQKS8NPQ"
```

Full detail: [`product-history/README.md`](product-history/README.md).

## [`prompt-packs/`](prompt-packs/)

The build conversations behind each skill, reverse-engineered into ordered prompts with a
check after every step, so anyone can rebuild them in Claude Code without writing code by
hand. Also includes a colleague starter pack: role-based prompts, a one-page safe-use
guide and a "ready to send?" job aid for teams new to an AI assistant.

## [`case-studies/`](case-studies/)

[`copilot-adoption-partners-framework.md`](case-studies/copilot-adoption-partners-framework.md) -
a self-authored framework for rolling out Copilot to internal teams through a volunteer
Adoption Partners network: role charters, cohorts, a ship-publish-respond loop and
honest measurement, mapped to ADKAR.

## Using any of these from Claude Code

Symlink the one(s) you want into `~/.claude/skills/` so `/html-to-ppt`, `/transcript`,
`/transcript-to-summary`, and `/product-history` become available as slash commands:

```bash
ln -s "$PWD/html-to-ppt" ~/.claude/skills/html-to-ppt
ln -s "$PWD/transcript" ~/.claude/skills/transcript
ln -s "$PWD/transcript-to-summary" ~/.claude/skills/transcript-to-summary
ln -s "$PWD/product-history" ~/.claude/skills/product-history
```

Each skill's own README has the Windows equivalent and full setup/troubleshooting detail.

## Licence

MIT — see [LICENSE](LICENSE).
