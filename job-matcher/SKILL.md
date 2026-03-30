---
# ============================================================
#  JOB SEARCH SKILL — Claude Code Skill Definition
#  Invoke via: /job-search in Claude Code
# ============================================================

name: job-search
version: "1.0"
author: gokulv
created: 2026-03-30

description: >
  AI-powered job search skill that scans the entire web — LinkedIn, Naukri,
  Glassdoor, Foundit, Wellfound, Monster, TimesJobs, company career pages,
  and any other indexed source — finds roles matching the configured job titles
  and location, scores every posting against the user's resume using a strict
  ATS compatibility rubric and a recruiter shortlisting confidence rubric,
  and surfaces only jobs scoring 90% or above on BOTH dimensions.
  Fully replaces manual job searching.

trigger: /job-search
argument-hint: >
  Optional overrides (all have defaults):
    [job title]         e.g. "Head of Operations"
    [location]          e.g. "Mumbai" or "remote"
    --threshold=N       e.g. --threshold=85  (default: 90)
    --remote-only       Search only remote roles
    --max=N             Max jobs to score e.g. --max=30 (default: 25)
    --save              Save results to timestamped file (always on by default)

allowed-tools:
  - WebSearch       # Multi-platform job discovery across the entire web
  - WebFetch        # Fetch full job descriptions from each posting URL
  - Read            # Load resume.txt and config
  - Write           # Save results to job-matcher/results-YYYY-MM-DD.txt
  - TodoWrite       # Track progress across the 10-step workflow
  - Bash            # Optional: run scorer.py for batch scoring if available

# ── DEFAULT CONFIGURATION ────────────────────────────────────────────────────
# These are the user's defaults. Arguments passed at invocation override them.

resume-path: ~/Passion-projects/job-matcher/resume.txt

target-roles:
  - Program Manager
  - Senior Operations Manager
  - Business Manager

location: Bangalore, India
include-remote: true

ats-threshold: 90        # Minimum ATS keyword match score (0–100)
recruiter-threshold: 90  # Minimum recruiter shortlisting confidence (0–100)

max-jobs-to-score: 25    # Total cap across all queries (cost control)
max-per-query: 5         # Jobs fetched per individual search query

# ── PLATFORM COVERAGE ────────────────────────────────────────────────────────
# Every search run covers all of these. No single portal dependency.
search-platforms:
  - linkedin          # linkedin.com/jobs
  - naukri            # naukri.com (India's largest job board)
  - glassdoor         # glassdoor.com/job-listing
  - foundit           # foundit.in (formerly Monster India)
  - wellfound         # wellfound.com (startups + tech)
  - monster           # monster.com
  - timesjobs         # timesjobs.com
  - iimjobs           # iimjobs.com (management roles)
  - company-careers   # Direct company career page URLs
  - open-web          # Any other indexed posting not covered above

# ── OUTPUT ───────────────────────────────────────────────────────────────────
output:
  terminal: true
  save-to-file: true
  file-path: ~/Passion-projects/job-matcher/results-{date}.txt
  format: detailed-cards   # One card per matched job with all score details
---

# Job Search Skill

## Purpose

This skill is the AI-powered replacement for manually browsing job portals.
When invoked, Claude autonomously:

1. Reads your resume
2. Searches the entire web across 8+ platforms per job title
3. Fetches the full description of every job found
4. Scores each one strictly against your resume
5. Returns only the jobs where **both** your ATS score **and** recruiter
   confidence hit the 90% threshold

The result is a curated shortlist of roles you are genuinely well-suited for,
with the exact keywords you are missing highlighted so you can update your
resume before applying.

---

## How to Invoke

Inside Claude Code, simply type:

```
/job-search
```

With optional overrides:

```
/job-search "Head of Operations" Hyderabad --threshold=85
/job-search --remote-only --max=40
/job-search "Senior Program Manager" Bangalore --threshold=90
```

If no arguments are provided, the skill uses the defaults in this file's
YAML frontmatter (roles, location, threshold).

---

## 10-Step Workflow

Claude follows these steps exactly in sequence. Each step is tracked with
TodoWrite so you can see progress in real time.

---

### Step 1 — Parse Arguments

Read any arguments passed with the invocation:
- If a job title is passed (e.g. `"Head of Operations"`), use it instead of
  the default `target-roles` list
- If a location is passed (e.g. `Mumbai`), override `location`
- If `--threshold=N` is passed, override both `ats-threshold` and
  `recruiter-threshold` with N
- If `--remote-only` is passed, restrict all searches to remote roles
- If `--max=N` is passed, use N as `max-jobs-to-score`
- If no arguments are passed, use all YAML defaults

Log the resolved configuration at the start of the run:
```
Job Search Configuration
─────────────────────────────────
Roles    : Program Manager, Senior Operations Manager, Business Manager
Location : Bangalore, India  |  Remote: Yes
Threshold: ATS ≥ 90%  |  Recruiter ≥ 90%
Max jobs : 25
─────────────────────────────────
```

---

### Step 2 — Load Resume

Read the file at `resume-path` (default: `~/Passion-projects/job-matcher/resume.txt`).

**Validation checks:**
- If the file does not exist → stop and print:
  ```
  ERROR: resume.txt not found at ~/Passion-projects/job-matcher/resume.txt
  Please add your resume. See job-matcher/README.md → Step 1.
  ```
- If the file contains the placeholder text "REPLACE EVERYTHING IN THIS FILE" →
  stop and print:
  ```
  ERROR: resume.txt still contains the template. Replace it with your actual resume.
  ```
- If the file is under 100 words → warn:
  ```
  WARNING: Your resume seems very short (N words). More detail = better scores.
  ```

On success, print:
```
Resume loaded — N words, M sections detected.
```

---

### Step 3 — Build Search Queries

For **each role** in `target-roles`, generate 8 search queries targeting
different platforms and approaches. This ensures no single portal gates
what gets found.

Query template per role (substitute `{ROLE}` and `{LOCATION}`):

```
Q1 [LinkedIn]       : site:linkedin.com/jobs "{ROLE}" "{LOCATION}" 2026
Q2 [Naukri]         : site:naukri.com "{ROLE}" {LOCATION} hiring apply
Q3 [Glassdoor]      : site:glassdoor.com/job-listing "{ROLE}" {LOCATION}
Q4 [Foundit]        : site:foundit.in "{ROLE}" {LOCATION}
Q5 [Wellfound]      : site:wellfound.com/jobs "{ROLE}" India remote
Q6 [TimesJobs]      : site:timesjobs.com "{ROLE}" {LOCATION}
Q7 [Open web]       : "{ROLE}" "{LOCATION}" "apply now" careers 2026
                      -site:linkedin.com -site:naukri.com -site:glassdoor.com
Q8 [Company careers]: "{ROLE}" {LOCATION} "we are hiring" site:*.com/careers
```

If `--remote-only` is set, append `remote` to all queries and drop location.

**Total queries for 3 default roles:** 8 × 3 = 24 searches.
If `--remote-only`, add 4 additional remote-specific queries per role.

---

### Step 4 — Execute Web Searches

Run each query via WebSearch. For each result:
- Collect the URL
- Collect the snippet/title to get a preliminary job title + company name
- Note which platform it came from (for attribution in output)

After all searches, print:
```
Found N job URLs across M searches.
```

---

### Step 5 — Deduplicate

Before fetching full descriptions:
- Remove duplicate URLs (same job listed on multiple platforms)
- Remove URLs that are clearly not job postings (news articles, blog posts, etc.)
- If more than `max-jobs-to-score` URLs remain after deduplication, take the
  top N distributed proportionally across platforms (do not oversample any
  single source)

Print:
```
After deduplication: N unique job postings to evaluate.
```

---

### Step 6 — Fetch Full Job Descriptions

For each unique URL, use WebFetch to load the job page and extract:

| Field        | Description                                      |
|--------------|--------------------------------------------------|
| `title`      | Exact job title from the posting                 |
| `company`    | Company name                                     |
| `location`   | City, state, work mode (hybrid / remote / onsite)|
| `salary`     | If stated (many Indian postings omit this)       |
| `description`| Full job description including requirements      |
| `apply_url`  | The direct "Apply" link on that page             |
| `source`     | Platform name (LinkedIn, Naukri, etc.)           |
| `posted`     | Date posted if visible                           |

If a page fails to load (404, login wall, etc.):
- Skip it silently and reduce the scoring queue
- If more than 30% of URLs fail, print a warning

Print progress:
```
Fetching descriptions... [12/20 done]
```

---

### Step 7 — Score Each Job

For every job fetched, apply the scoring rubric below. This is done inline
by Claude — no external scoring module is required.

#### ATS Score (0–100) — Automated Tracking System Simulation

Simulates whether a company's keyword-filtering software would pass your resume.

**Rubric — be strict, do not inflate:**

| Component | Weight | What to evaluate |
|-----------|--------|-----------------|
| Keyword overlap | 40% | What % of the job's critical terms (required skills, must-haves, tools) are explicitly present in the resume? |
| Skills match | 30% | Does the resume explicitly list the hard and soft skills stated as required in the posting? |
| Experience level | 20% | Does the candidate's stated years of experience and seniority title match the job's requirements? |
| Education / Certs | 10% | Does the candidate meet the stated education or certification requirements? |

**Score guide (be strict — 90+ is rare and means near-perfect):**
- 95–100: Almost every keyword present, ideal seniority match, certs match
- 90–94: Most keywords present, minor gap in one area only
- 80–89: Good match but 3–5 important keywords missing
- 70–79: Partial match, noticeable gaps in skills or experience level
- <70: Poor match — do not show in results

#### Recruiter Score (0–100) — Human Recruiter Shortlisting Confidence

Simulates whether a human recruiter scanning 200 resumes would put yours in
the "interview" pile for this specific role.

**Rubric — be strict, do not inflate:**

| Component | Weight | What to evaluate |
|-----------|--------|-----------------|
| Role relevance | 40% | Does the candidate's past job titles and responsibilities directly map to this role's core function? |
| Domain expertise | 30% | Does the resume show proven depth in the specific functional domain (operations, program management, business management)? |
| Leadership signals | 20% | Is there clear evidence of team management, cross-functional leadership, stakeholder management, or budget ownership? |
| Industry / company fit | 10% | Would this candidate's background logically make sense at this company's size, sector, and culture? |

**Score guide:**
- 95–100: Ideal candidate — would shortlist without hesitation
- 90–94: Strong fit — high confidence shortlist
- 80–89: Decent fit — might shortlist, not a priority
- 70–79: Questionable — unlikely to shortlist
- <70: Not a fit for this role

#### Score Output Format (per job, internal)

After scoring each job, produce a JSON object:
```json
{
  "title": "Senior Program Manager",
  "company": "Infosys",
  "location": "Bangalore, Karnataka (Hybrid)",
  "salary": "₹18L–₹25L/yr",
  "source": "LinkedIn",
  "apply_url": "https://linkedin.com/jobs/view/...",
  "ats_score": 94,
  "recruiter_score": 91,
  "ats_reasons": [
    "Keywords 'program management', 'stakeholder alignment' found in resume",
    "7+ years experience matches '5+ years required'",
    "PMP certification listed matches job requirement"
  ],
  "recruiter_reasons": [
    "Career trajectory shows clear progression to senior PM roles",
    "Cross-domain operations + PM experience is rare and valued here"
  ],
  "missing_keywords": ["Agile", "JIRA", "SAFe", "delivery management"],
  "match_summary": "Strong alignment in program management scope and leadership depth."
}
```

**IMPORTANT SCORING INSTRUCTION:**
- Be strict. Do NOT give benefit of the doubt.
- Only award 90+ when the evidence in the resume is explicit and clear.
- A score of 70 is already above average — 90+ should feel rare and meaningful.
- The `missing_keywords` list must always be populated honestly.

---

### Step 8 — Filter Results

Keep only jobs where **both** of the following are true:
- `ats_score >= ats-threshold` (default 90)
- `recruiter_score >= recruiter-threshold` (default 90)

Sort survivors by `(ats_score + recruiter_score) / 2`, highest first.

If zero jobs pass, print:
```
No jobs matched the 90% threshold on this run.

This is normal — it means the system is working correctly.
What to try:
  1. Add missing keywords to resume.txt (see the scores above for hints)
  2. Lower the threshold: /job-search --threshold=85
  3. Try a broader title: /job-search "Operations Manager"
  4. Run again tomorrow — job listings refresh daily
```

---

### Step 9 — Print Results

For each matched job, print a formatted card:

```
══════════════════════════════════════════════════════════════════════
MATCH #1                                       Source: LinkedIn
══════════════════════════════════════════════════════════════════════
Role     : Senior Program Manager
Company  : Infosys Limited
Location : Bangalore, Karnataka (Hybrid)
Salary   : ₹18L–₹25L per year
Posted   : 2 days ago

ATS Score        : [##########] 94%
Recruiter Score  : [#########-] 91%
Combined Average : 92%

Summary: Strong alignment across program management, cross-functional
leadership, and stakeholder management keywords.

Why your ATS score is strong:
  + "Program management", "stakeholder alignment" found in resume
  + 7+ years experience matches "5+ years" requirement
  + PMP certification matches job requirement

Why a recruiter would shortlist you:
  + Career shows clear senior PM progression
  + Cross-domain operations + PM experience is valued here

Add these keywords to your resume before applying:
  ! Agile, JIRA, SAFe, delivery management, risk mitigation

APPLY HERE: https://linkedin.com/jobs/view/...
══════════════════════════════════════════════════════════════════════
```

After all cards, print a summary line:
```
─────────────────────────────────────────────────────────────────────
Run complete: Evaluated 22 jobs | 4 matched 90%+ | Saved to results-2026-03-30.txt
─────────────────────────────────────────────────────────────────────
```

---

### Step 10 — Save Results to File

Write the full output (all matched job cards + summary) to:
```
~/Passion-projects/job-matcher/results-YYYY-MM-DD.txt
```

File includes a header:
```
JOB SEARCH RESULTS
Run date  : 30 Mar 2026, 10:45 AM
Roles     : Program Manager, Senior Operations Manager, Business Manager
Location  : Bangalore, India  |  Remote: Yes
Threshold : ATS ≥ 90%  |  Recruiter ≥ 90%
Evaluated : 22 jobs  |  Matched : 4
═══════════════════════════════════════════════════════════════════════
[job cards follow]
```

Print confirmation:
```
Results saved to: ~/Passion-projects/job-matcher/results-2026-03-30.txt
```

---

## Configuration Reference

To permanently change defaults (roles, location, threshold), edit the YAML
frontmatter at the top of this file (`job-matcher/SKILL.md`).

| YAML Field | Default | What it controls |
|------------|---------|-----------------|
| `target-roles` | 3 PM/Ops roles | Job titles to search |
| `location` | Bangalore, India | Primary search location |
| `include-remote` | true | Also search remote roles |
| `ats-threshold` | 90 | Minimum ATS score to show |
| `recruiter-threshold` | 90 | Minimum recruiter score |
| `max-jobs-to-score` | 25 | Total jobs scored per run |
| `resume-path` | ~/Passion-projects/job-matcher/resume.txt | Resume location |

---

## Platform Strategy Detail

The 8-query-per-role strategy ensures wide coverage:

| Query Type | Platforms Reached | Why |
|-----------|-------------------|-----|
| `site:linkedin.com/jobs` | LinkedIn only | Largest professional network |
| `site:naukri.com` | Naukri | India's #1 job board by volume |
| `site:glassdoor.com` | Glassdoor | Company reviews + jobs combined |
| `site:foundit.in` | Foundit (Monster India) | Mid-senior roles in India |
| `site:wellfound.com` | Wellfound | Startups, equity-based roles |
| `site:timesjobs.com` | TimesJobs | Indian conglomerate & MNC roles |
| Open web (exclude major boards) | Any other site | Company blogs, career microsites, niche boards |
| `site:*.com/careers` | Company career pages | Direct postings not syndicated |

**Why not use a single job search API?**
Any single API (SerpAPI, Indeed API, LinkedIn API) only indexes a subset of
active postings. Multiple targeted WebSearch queries reach the same Google
index that most people use manually — giving broader coverage than any single
portal's API.

---

## Score Interpretation Guide

| Score Band | ATS Meaning | Recruiter Meaning |
|-----------|-------------|-------------------|
| 95–100 | Near-perfect keyword match | Would shortlist immediately |
| 90–94 | Strong match, minor gaps | High confidence shortlist |
| 85–89 | Good match (use --threshold=85) | Would likely shortlist |
| 80–84 | Decent match, notable gaps | Might shortlist |
| <80 | Filtered out by default | Not shown |

**If you consistently score in the 80–88 range:** add the missing keywords
from the results to your `resume.txt` before the next run.

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Zero matches | Threshold too strict or resume lacks keywords | Lower with `--threshold=85`, add keywords |
| Few jobs fetched | Pages behind login walls | Normal — some portals block scraping |
| Wrong role showing up | Broad queries matched tangential roles | Add more specific title in argument |
| Scores seem low | Resume lacks specific keywords | Review `missing_keywords` fields in output |

---

## Example Runs

```bash
# Default run — uses all YAML defaults
/job-search

# Search for a specific role, different city
/job-search "Head of Operations" Mumbai

# Lower threshold to see more options
/job-search --threshold=85

# Remote only, higher volume
/job-search --remote-only --max=40

# Specific role + location override
/job-search "Senior Business Manager" Hyderabad --threshold=88
```
