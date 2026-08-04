# Passion-projects

Personal projects, not related to work — just curiosity ones. Two plug-and-play
Claude Code / Cursor skills live here, each self-contained in its own folder.

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

## Using either from Claude Code

Symlink the one(s) you want into `~/.claude/skills/` so `/html-to-ppt`, `/transcript`,
and `/transcript-to-summary` become available as slash commands:

```bash
ln -s "$PWD/html-to-ppt" ~/.claude/skills/html-to-ppt
ln -s "$PWD/transcript" ~/.claude/skills/transcript
ln -s "$PWD/transcript-to-summary" ~/.claude/skills/transcript-to-summary
```

Each skill's own README has the Windows equivalent and full setup/troubleshooting detail.
