# Job Matcher — AI-Powered ATS + Recruiter Scoring

This tool scans Google Jobs for **Program Manager / Senior Operations / Business Manager** roles
in **Bangalore (hybrid + remote)** and scores each job against your resume using Claude AI.

Only jobs with **90%+ ATS match** AND **90%+ recruiter confidence** are shown.

---

## What Does It Do?

```
Your Resume  +  Google Jobs Search
        ↓
  Claude AI scores each job:
    - ATS Score:       Does your resume pass keyword filtering? (target 90%+)
    - Recruiter Score: Would a recruiter shortlist you?         (target 90%+)
        ↓
  Filtered Results with:
    - Job title & company
    - Both scores with explanations
    - Keywords you're missing (fix your resume!)
    - Direct apply link
```

---

## One-Time Setup (Do This Once)

### Step 1 — Add Your Resume

You have a PDF or Word doc. Here's how to convert it to plain text:

**Option A (easiest): Google Docs method**
1. Go to [drive.google.com](https://drive.google.com)
2. Drag and drop your PDF into Google Drive
3. Right-click the PDF → **Open with → Google Docs**
4. Google Docs will convert it — wait ~10 seconds
5. Go to **File → Download → Plain Text (.txt)**
6. Open the downloaded file, copy all the text
7. Open `resume.txt` in this folder (use any text editor — Notepad, VS Code, etc.)
8. Delete everything in `resume.txt` and paste your resume text
9. Save the file

**Option B: Copy-paste method**
1. Open your PDF in any PDF viewer (Adobe, Chrome, Preview)
2. Press **Ctrl+A** (select all) then **Ctrl+C** (copy)
3. Open `resume.txt`, delete the template, paste with **Ctrl+V**
4. Save

**Tips for best results:**
- Keep all your skills in a dedicated "SKILLS" section
- Use keywords that match job descriptions (e.g., "stakeholder management", "P&L", "OKRs")
- Include years of experience clearly (e.g., "8+ years in operations")

---

### Step 2 — Get Your Free Anthropic API Key

Anthropic is the company that makes Claude AI (the scoring engine).

1. Go to **[console.anthropic.com](https://console.anthropic.com/)**
2. Click **Sign up** and create a free account
3. Once logged in, go to **API Keys** in the left sidebar
4. Click **Create Key** → give it a name like "job-matcher"
5. Copy the key (it starts with `sk-ant-...`)
6. Keep it safe — you only see it once!

---

### Step 3 — Get Your Free SerpAPI Key

SerpAPI powers the Google Jobs search. Free tier gives 100 searches/month (plenty for weekly use).

1. Go to **[serpapi.com](https://serpapi.com/)**
2. Click **Register** (top right)
3. Sign up with email (no credit card needed for free tier)
4. After signing in, your API key is shown on the **Dashboard**
5. Copy the key

---

### Step 4 — Add Both Keys to config.py

1. Open the file `job-matcher/config.py` in a text editor
2. Find this line:
   ```python
   ANTHROPIC_API_KEY = "sk-ant-PASTE-YOUR-KEY-HERE"
   ```
   Replace `sk-ant-PASTE-YOUR-KEY-HERE` with your actual Anthropic key.

3. Find this line:
   ```python
   SERPAPI_KEY = "PASTE-YOUR-SERPAPI-KEY-HERE"
   ```
   Replace `PASTE-YOUR-SERPAPI-KEY-HERE` with your SerpAPI key.

4. Save `config.py`

---

### Step 5 — Install Python Dependencies

Open a terminal in the `job-matcher/` folder and run:

```bash
pip install -r requirements.txt
```

This installs:
- `anthropic` — the Claude AI library
- `requests` — for calling the job search API
- `python-dotenv` — for managing config

---

## Running the Job Matcher

Once setup is complete, just run:

```bash
python main.py
```

**What you'll see:**

```
============================================================
  JOB MATCHER — AI-Powered Job Search & Scoring
============================================================

[1/4] Loading your resume...
      OK — 542 words loaded from resume.txt

[2/4] Searching for jobs on Google Jobs...
      Job titles: Program Manager, Senior Operations Manager, Business Manager
      Location  : Bangalore, India

  [1/5] Searching: "Program Manager" in Bangalore, India
         Found 5 results, 5 new unique jobs
  [2/5] Searching: "Senior Operations Manager" in Bangalore, India
         Found 5 results, 4 new unique jobs
  ...

[3/4] Scoring 18 jobs with Claude AI...

  [ 1/18] Senior Program Manager at Infosys
           ATS:  94%  |  Recruiter:  91%  |  [MATCH]
  [ 2/18] Operations Lead at Flipkart
           ATS:  76%  |  Recruiter:  72%  |  [skip]
  ...

[4/4] Filtering results...

======================================================================
  MATCH #1
======================================================================
  Role     : Senior Program Manager
  Company  : Infosys
  Location : Bangalore, Karnataka, India (Hybrid)
  Salary   : ₹18,00,000–₹25,00,000 per year

  ATS Score        : [##########] 94%
  Recruiter Score  : [#########-] 91%
  Combined Avg     : 92%
  Summary: Strong alignment in program management experience and technical operations.

  Why your ATS score is strong:
    + Keywords "program management", "stakeholder alignment" found in resume
    + 7+ years experience matches "5+ years" requirement
    + PMP certification listed matches job requirement

  Why a recruiter would shortlist you:
    + Direct experience managing cross-functional programs at scale
    + Leadership of 20+ person teams aligns with role scope

  Keywords to add to your resume before applying:
    ! Agile, JIRA, SAFe, delivery management

  APPLY HERE: https://indeed.com/...
```

---

## Customizing Your Search

All settings are in `config.py`. Key things you can change:

| Setting | Default | What it does |
|---------|---------|-------------|
| `JOB_SEARCH_QUERIES` | 3 role titles | What jobs to search for |
| `SEARCH_LOCATION` | `Bangalore, India` | Where to search |
| `INCLUDE_REMOTE` | `True` | Also search remote roles |
| `MAX_JOBS_PER_QUERY` | `5` | Jobs per search query |
| `ATS_THRESHOLD` | `90` | Minimum ATS score to show |
| `RECRUITER_THRESHOLD` | `90` | Minimum recruiter score |

**If you get zero results:** Lower thresholds to 80 first, check your resume has enough keywords.

**If results seem wrong:** Update `resume.txt` with more specific skills and achievements.

---

## How the Scores Work

| Score | What it measures | What 90%+ means |
|-------|-----------------|-----------------|
| **ATS Score** | Keyword matching, skills, experience level, education | Your resume would pass automated screening |
| **Recruiter Score** | Role fit, domain expertise, leadership signals | A recruiter would shortlist you for interview |

The AI is intentionally **strict** — 90%+ is a genuinely strong match, not an inflated number.

---

## Results File

After every run, results are saved to `job-matcher/results.txt` so you can review them later without re-running.

---

## Common Issues

**"No jobs found"**
- Check your SerpAPI key in config.py
- Try running with a broader query like `"Manager"` instead of `"Senior Operations Manager"`

**"Scoring failed"**
- Check your Anthropic API key in config.py
- Make sure your resume.txt has real content (not the template)

**"ModuleNotFoundError"**
- Run `pip install -r requirements.txt` again
- Make sure you're using Python 3.8 or newer (`python --version`)

---

## Project Structure

```
job-matcher/
├── main.py         ← Run this: python main.py
├── config.py       ← Edit this: your API keys and search settings
├── resume.txt      ← Edit this: paste your resume here
├── searcher.py     ← Searches Google Jobs via SerpAPI
├── scorer.py       ← Scores jobs using Claude AI
├── reporter.py     ← Formats and displays results
├── requirements.txt← Dependencies (pip install -r requirements.txt)
└── results.txt     ← Auto-generated after each run
```
