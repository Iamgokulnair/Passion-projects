"""
Claude-based job scoring from a hiring manager / recruiter perspective.
Each JD is evaluated against Gokul's profile to produce a structured score.
"""

import json
import time
import anthropic
from resume_profile import RESUME_TEXT

# Use Haiku for cost efficiency on daily runs; swap to Sonnet for higher precision
SCORING_MODEL = "claude-haiku-4-5-20251001"

SCORING_PROMPT = """You are a senior recruiter and hiring manager at a top-tier GCC, MNC, or high-growth technology company in Bengaluru, India. You have just received a candidate profile for the open role below.

Your job: decide whether this candidate would make your shortlist (top 3 candidates you'd call). Be rigorous and realistic. Not every strong candidate fits every role.

---
## OPEN ROLE
**Title:** {job_title}
**Company:** {company}
**Location:** {location}

### Job Description:
{job_description}

---
## CANDIDATE PROFILE
{resume_text}

---
## SCORING RUBRIC

Score the candidate on 5 dimensions:

1. **Level Fit** (0–25): Does their seniority, scope, and years of experience match what this role demands? (Director/Head-level = 8 yrs experience managing 10+ people)
2. **Domain Match** (0–25): Do their specific functions (operations, people leadership, GCC, strategy) map directly to the core JD requirements?
3. **Scale & Complexity** (0–20): Does the scale of their work (team size, FTEs built, cross-functional governance, P&L adjacency) match what this role needs?
4. **Differentiator Fit** (0–15): Does the candidate bring something the HM would find distinctive and hard to replace? (McKinsey pedigree, zero-to-one GCC build, LLM automation at scale)
5. **Location & Practical Fit** (0–15): Is there any location, visa, or practical barrier? Candidate is based in Bengaluru — deduct points only if role is explicitly outside BLR or requires relocation.

---
## OUTPUT FORMAT

Return ONLY a valid JSON object. No markdown fences, no explanation outside the JSON:

{{
  "total_score": <int 0-100>,
  "level_fit": <int 0-25>,
  "domain_match": <int 0-25>,
  "scale_complexity": <int 0-20>,
  "differentiator_fit": <int 0-15>,
  "location_fit": <int 0-15>,
  "shortlist_verdict": "<SURE_SHOT | STRONG_MATCH | WEAK_MATCH | NO_FIT>",
  "top_reasons_for": ["<concise reason 1>", "<concise reason 2>", "<concise reason 3>"],
  "top_reasons_against": ["<concise reason 1>", "<concise reason 2>"],
  "hm_one_liner": "<One sharp sentence a hiring manager would say about this candidate for THIS role>"
}}

Verdict thresholds: SURE_SHOT ≥ 75 | STRONG_MATCH 60–74 | WEAK_MATCH 40–59 | NO_FIT < 40
"""


def score_job_match(job_title: str, company: str, location: str, job_description: str) -> dict:
    """
    Score a job against Gokul's profile from a hiring manager perspective.
    Returns a dict with score breakdown and verdict.
    """
    client = anthropic.Anthropic()

    prompt = SCORING_PROMPT.format(
        job_title=job_title,
        company=company,
        location=location,
        job_description=job_description[:4000],  # cap to avoid large prompts
        resume_text=RESUME_TEXT,
    )

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=SCORING_MODEL,
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()

            # Strip markdown fences if model adds them
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            result = json.loads(raw)

            # Validate required keys
            required = ["total_score", "shortlist_verdict", "hm_one_liner",
                        "top_reasons_for", "top_reasons_against"]
            for key in required:
                if key not in result:
                    raise ValueError(f"Missing key: {key}")

            # Clamp total_score to 0–100
            result["total_score"] = max(0, min(100, int(result["total_score"])))
            return result

        except (json.JSONDecodeError, ValueError) as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            # Return a safe fallback on persistent failure
            return {
                "total_score": 0,
                "level_fit": 0,
                "domain_match": 0,
                "scale_complexity": 0,
                "differentiator_fit": 0,
                "location_fit": 0,
                "shortlist_verdict": "NO_FIT",
                "top_reasons_for": [],
                "top_reasons_against": [f"Scoring failed: {e}"],
                "hm_one_liner": "Could not evaluate — JD may be too short or malformed.",
            }
        except anthropic.RateLimitError:
            time.sleep(60)
            continue
        except Exception as e:
            return {
                "total_score": 0,
                "shortlist_verdict": "NO_FIT",
                "top_reasons_for": [],
                "top_reasons_against": [f"API error: {e}"],
                "hm_one_liner": "Scoring unavailable.",
            }
