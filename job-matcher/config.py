# ============================================================
#  JOB MATCHER — CONFIGURATION
#  Edit the values below before running `python main.py`
# ============================================================

# -- API KEY 1: ANTHROPIC (for AI scoring) -------------------
# Powers the ATS + Recruiter scoring engine.
# Get your free key at: https://console.anthropic.com/
ANTHROPIC_API_KEY = "sk-ant-PASTE-YOUR-KEY-HERE"

# -- API KEY 2: SERPAPI (for job searching) -------------------
# Powers the Google Jobs search. Free tier = 100 searches/month.
# Get your free key at: https://serpapi.com/ (click "Register")
SERPAPI_KEY = "PASTE-YOUR-SERPAPI-KEY-HERE"

# -- WHAT JOB ARE YOU LOOKING FOR? ---------------------------
# You can add multiple job titles. The system searches all of them.
JOB_SEARCH_QUERIES = [
    "Program Manager",
    "Senior Operations Manager",
    "Business Manager",
]

# -- WHERE ARE YOU LOOKING? ----------------------------------
SEARCH_LOCATION = "Bangalore, India"   # Full city + country
COUNTRY_CODE    = "in"                 # Lowercase country code for Google Jobs

# Also search for remote roles? (True = yes, False = no)
INCLUDE_REMOTE  = True

# -- HOW MANY JOBS TO SCAN PER SEARCH QUERY? -----------------
# 5 jobs per query is a good starting point.
# With 3 queries + remote, that's up to 20 jobs total.
MAX_JOBS_PER_QUERY = 5

# -- SCORING THRESHOLDS (0 to 100) ---------------------------
# A job must score AT OR ABOVE BOTH thresholds to appear in results.
# Start at 90. If you get no results, try lowering to 80.
ATS_THRESHOLD        = 90
RECRUITER_THRESHOLD  = 90

# -- CLAUDE MODEL (don't change unless you know why) ---------
CLAUDE_MODEL = "claude-sonnet-4-6"
