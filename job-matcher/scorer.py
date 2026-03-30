"""
scorer.py — Scores each job against your resume using Claude AI.

Two scores are calculated for every job:

  ATS Score (0-100):
    How well your resume would pass the Applicant Tracking System.
    Based on keyword overlap, required skills, experience level, education.

  Recruiter Score (0-100):
    Confidence that a human recruiter would shortlist you for an interview.
    Based on role relevance, domain expertise, leadership signals, company fit.

Only jobs scoring 90+ on BOTH are shown in results.
"""

import json
import re

import anthropic


SCORING_PROMPT = """You are a strict and experienced ATS system combined with a senior recruiter.
Your job is to evaluate how well a candidate's resume matches a specific job posting.

You must return a JSON object with EXACTLY these fields (no extra text before or after):

{
  "ats_score": <integer from 0 to 100>,
  "recruiter_score": <integer from 0 to 100>,
  "ats_reasons": [<2-4 short strings explaining the ATS score>],
  "recruiter_reasons": [<2-4 short strings explaining the recruiter score>],
  "missing_keywords": [<keywords in the job that are NOT in the resume>],
  "match_summary": "<one sentence describing the overall match>"
}

=== ATS SCORE RUBRIC (be strict — 90+ means near-perfect match) ===
Weight 40% — Keyword overlap: What % of the job's key terms appear in the resume?
Weight 30% — Skills match: Does the resume list the required technical and soft skills?
Weight 20% — Experience level: Does years of experience and seniority match?
Weight 10% — Education/Certifications: Does the candidate meet stated requirements?

Score guide:
  95-100: Almost every keyword matches, ideal experience level
  90-94:  Most keywords match, minor gaps only
  80-89:  Good match but several important keywords missing
  70-79:  Partial match, significant gaps in skills or experience
  <70:    Poor match

=== RECRUITER SCORE RUBRIC (be strict — 90+ means strong shortlist) ===
Weight 40% — Role relevance: Does the candidate's career history directly fit this role?
Weight 30% — Domain expertise: Do they have proven experience in this functional area?
Weight 20% — Leadership signals: Evidence of team management, stakeholder engagement?
Weight 10% — Industry/company fit: Would this background make sense at this company?

Score guide:
  95-100: Ideal candidate, would shortlist immediately
  90-94:  Strong fit, would shortlist with high confidence
  80-89:  Decent fit, might shortlist but not a priority
  70-79:  Questionable fit, unlikely to shortlist
  <70:    Not a strong match for this role

IMPORTANT: Be strict. Do NOT inflate scores. A 90+ score should mean this is genuinely
one of the best matches you would ever see. A 70 is already above average.
"""


def score_job(
    client: anthropic.Anthropic,
    resume: str,
    job: dict,
    model: str = "claude-sonnet-4-6",
) -> dict:
    """
    Score a single job against the candidate's resume.

    Args:
        client: Anthropic API client
        resume: Plain text resume content
        job: Dict with job details (title, company, description, etc.)
        model: Claude model to use

    Returns:
        The job dict enriched with: ats_score, recruiter_score,
        ats_reasons, recruiter_reasons, missing_keywords, match_summary
    """
    job_description = _format_job_for_scoring(job)

    user_message = f"""=== CANDIDATE RESUME ===
{resume}

=== JOB POSTING ===
{job_description}

Evaluate this match and return ONLY the JSON object as specified."""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SCORING_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        text = response.content[0].text.strip()
        scores = _parse_json_response(text)

        # Merge scores into the job dict
        return {**job, **scores, "scoring_error": None}

    except Exception as e:
        # If scoring fails, return zeros so the job is filtered out
        return {
            **job,
            "ats_score": 0,
            "recruiter_score": 0,
            "ats_reasons": [],
            "recruiter_reasons": [],
            "missing_keywords": [],
            "match_summary": f"Scoring failed: {str(e)}",
            "scoring_error": str(e),
        }


def _format_job_for_scoring(job: dict) -> str:
    """Format a job dict into a readable string for the scoring prompt."""
    parts = []
    if job.get("title"):
        parts.append(f"Title: {job['title']}")
    if job.get("company"):
        parts.append(f"Company: {job['company']}")
    if job.get("location"):
        parts.append(f"Location: {job['location']}")
    if job.get("salary"):
        parts.append(f"Salary: {job['salary']}")
    if job.get("description"):
        parts.append(f"\nJob Description:\n{job['description']}")
    return "\n".join(parts)


def _parse_json_response(text: str) -> dict:
    """
    Extract and parse JSON from Claude's response.
    Handles cases where Claude wraps JSON in markdown code blocks.
    """
    # Remove markdown code blocks if present
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    text = text.rstrip("`").strip()

    # Find JSON object boundaries
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in response")

    data = json.loads(text[start:end])

    # Validate required fields with defaults
    return {
        "ats_score": int(data.get("ats_score", 0)),
        "recruiter_score": int(data.get("recruiter_score", 0)),
        "ats_reasons": data.get("ats_reasons", []),
        "recruiter_reasons": data.get("recruiter_reasons", []),
        "missing_keywords": data.get("missing_keywords", []),
        "match_summary": data.get("match_summary", ""),
    }


def filter_jobs(
    scored_jobs: list,
    ats_threshold: int = 90,
    recruiter_threshold: int = 90,
) -> list:
    """
    Filter jobs to only those meeting both score thresholds.
    Returns results sorted by combined score (highest first).
    """
    matched = [
        job for job in scored_jobs
        if job.get("ats_score", 0) >= ats_threshold
        and job.get("recruiter_score", 0) >= recruiter_threshold
    ]

    # Sort by average of both scores, descending
    matched.sort(
        key=lambda j: (j["ats_score"] + j["recruiter_score"]) / 2,
        reverse=True,
    )

    return matched
