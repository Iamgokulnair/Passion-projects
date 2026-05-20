# Job Sweep Setup

## One-time setup (2 minutes)

### 1. Add your Anthropic API key to GitHub Secrets

Go to: **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**

- Name: `ANTHROPIC_API_KEY`
- Value: your key from console.anthropic.com

### 2. That's it. The workflow runs daily at 05:00 IST automatically.

---

## How to run manually

```bash
pip install -r job_sweep/requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python job_sweep/job_sweep.py
```

Results are saved to `job_sweep/results/YYYY-MM-DD.md`.

---

## How to trigger a manual sweep from GitHub

Go to: **Actions tab → "Daily Job Sweep — BLR (5am IST)" → Run workflow**

---

## What it does

1. Searches LinkedIn, Indeed, and Glassdoor for 10 target role types in Bengaluru
2. Deduplicates across boards
3. Filters to BLR-only listings
4. Scores each JD against your resume using Claude — from a hiring manager's perspective
5. Picks the single best **Sure Shot** (score ≥ 75/100)
6. Saves a clean markdown table with apply links to `job_sweep/results/`
7. Commits and pushes the result to the repo

---

## Scoring rubric (what Claude evaluates)

| Dimension | Max | What it checks |
|-----------|-----|----------------|
| Level Fit | 25 | Does seniority match Director/Head mandate? |
| Domain Match | 25 | Operations, people leadership, GCC, strategy? |
| Scale & Complexity | 20 | Team size, FTEs built, P&L adjacency? |
| Differentiator Fit | 15 | McKinsey pedigree, GCC zero-to-one, LLM automation? |
| Location Fit | 15 | Confirmed Bengaluru? |
| **Total** | **100** | |

**Verdicts:** Sure Shot ≥ 75 · Strong Match 60–74 · Weak Match 40–59 · No Fit < 40

---

## Updating the resume profile

Edit `job_sweep/resume_profile.py` — the `RESUME_TEXT` block and `TARGET_QUERIES` list.
