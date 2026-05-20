# Claude Code — Project Instructions

## Job Sweep Routine

Run the job sweep at any time from inside this Claude Code session:

```bash
python job_sweep/job_sweep.py
```

**What it does:**
- Searches LinkedIn, Indeed, Glassdoor for Director/Head Operations roles in Bengaluru
- Filters to jobs posted within the **21-day active hiring window** only
- Scores each JD against Gokul's resume using Claude (hiring manager perspective)
- Surfaces 1 **Sure Shot** pick (score ≥ 75/100) with a full breakdown table
- Saves the result to `job_sweep/results/YYYY-MM-DD.md`
- Output renders as markdown inline in this session

**First-time setup (one-off):**
```bash
pip install -r job_sweep/requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # add to your shell profile to persist
```

**To update the resume or target queries:** edit `job_sweep/resume_profile.py`

**Results are saved here:** `job_sweep/results/`

---

## Scoring rubric (what "hiring manager lens" means)

| Dimension | Max | Signal |
|-----------|-----|--------|
| Level Fit | 25 | Director/Head seniority match for 8 yrs experience |
| Domain Match | 25 | Ops, people leadership, GCC, strategy alignment |
| Scale & Complexity | 20 | Team size, FTEs built, cross-functional scope |
| Differentiator Fit | 15 | McKinsey pedigree, GCC zero-to-one, LLM automation |
| Location Fit | 15 | Confirmed Bengaluru |
| **Total** | **100** | |

Sure Shot ≥ 75 · Strong Match 60–74 · Weak Match 40–59 · No Fit < 40
