# Job Sweep — Setup

## One-time install

```bash
pip install -r job_sweep/requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

Add the export to your `~/.zshrc` or `~/.bashrc` so it persists across sessions.

## Running the sweep

From the repo root inside a Claude Code session:

```bash
python job_sweep/job_sweep.py
```

Results render as markdown inline in Claude Code and are also saved to `job_sweep/results/YYYY-MM-DD.md`.

## What the output shows

### Sure Shot card
A single-role deep dive — apply link, score breakdown, HM rationale, and watch-outs.
Only fires if a role scores ≥ 75/100.

### Full Sweep table

| Role | Company | Posted | Score | Verdict | Apply |
|------|---------|--------|-------|---------|-------|
| Head of GCC Operations | Accenture | 4d ago | 84/100 | 🎯 SURE_SHOT | → |
| Director of Delivery | Thoughtworks | 11d ago | 71/100 | ✅ STRONG_MATCH | → |
| VP Operations | Razorpay | 18d ago | 63/100 | ✅ STRONG_MATCH | → |

**Posted** column shows how many days ago the role was listed.
Only roles posted within **21 days** appear — this is the active hiring window
where recruiter and HM engagement is live. Older listings are filtered before scoring.

## Updating the profile

Edit `job_sweep/resume_profile.py`:
- `RESUME_TEXT` — when the resume changes
- `TARGET_QUERIES` — to add/remove role types
- `MAX_DAYS_OLD` — to adjust the freshness window (default: 21)
- `SURE_SHOT_THRESHOLD` — to tighten or loosen the quality gate (default: 75)
