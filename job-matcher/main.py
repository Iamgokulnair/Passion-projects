"""
main.py — Job Matcher Entry Point

HOW TO RUN:
    python main.py

BEFORE RUNNING (one-time setup):
  1. Add your resume to resume.txt      (see README.md -> Step 1)
  2. Get a free Anthropic API key       (see README.md -> Step 2)
  3. Get a free SerpAPI key             (see README.md -> Step 3)
  4. Paste both keys into config.py     (see README.md -> Step 4)
"""

import sys
import os

# Ensure imports work regardless of where you run the script from
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import anthropic

import config
from searcher import load_resume, fetch_jobs
from scorer import score_job, filter_jobs
from reporter import print_results, save_results_to_file


def validate_setup() -> None:
    """Check that the user has completed the one-time setup."""
    errors = []

    if not config.ANTHROPIC_API_KEY or "PASTE" in config.ANTHROPIC_API_KEY:
        errors.append(
            "  - ANTHROPIC_API_KEY not set in config.py\n"
            "    Get your free key at: https://console.anthropic.com/"
        )

    if not config.SERPAPI_KEY or "PASTE" in config.SERPAPI_KEY:
        errors.append(
            "  - SERPAPI_KEY not set in config.py\n"
            "    Get your free key at: https://serpapi.com/ (free tier: 100 searches/month)"
        )

    if errors:
        print("\n" + "=" * 60)
        print("  SETUP REQUIRED — Please fix these issues first:")
        print("=" * 60)
        for error in errors:
            print(f"\n{error}")
        print("\n  See README.md for step-by-step instructions.\n")
        sys.exit(1)


def main() -> None:
    print("\n" + "=" * 60)
    print("  JOB MATCHER — AI-Powered Job Search & Scoring")
    print("  ATS Match + Recruiter Confidence Scoring")
    print("=" * 60)

    # Check setup is complete
    validate_setup()

    # Step 1: Load resume
    print("\n[1/4] Loading your resume...")
    resume = load_resume()
    word_count = len(resume.split())
    print(f"      OK — {word_count} words loaded from resume.txt")

    # Step 2: Search for jobs
    print(f"\n[2/4] Searching for jobs on Google Jobs...")
    print(f"      Job titles: {', '.join(config.JOB_SEARCH_QUERIES)}")
    print(f"      Location  : {config.SEARCH_LOCATION}")
    print(f"      Remote    : {'Yes' if config.INCLUDE_REMOTE else 'No'}")
    print()

    jobs = fetch_jobs(config, verbose=True)

    if not jobs:
        print("\n  No jobs found. Try:")
        print("  - Broadening your search queries in config.py")
        print("  - Checking your SerpAPI key is correct")
        sys.exit(0)

    # Step 3: Score each job with Claude AI
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    print(f"\n[3/4] Scoring {len(jobs)} jobs with Claude AI...")
    print(f"      Threshold: ATS >= {config.ATS_THRESHOLD}%  |  Recruiter >= {config.RECRUITER_THRESHOLD}%")
    print()

    scored_jobs = []
    for i, job in enumerate(jobs, 1):
        title = job.get("title", "Unknown Role")
        company = job.get("company", "Unknown Company")
        print(f"  [{i:2d}/{len(jobs)}] {title} at {company}")

        scored = score_job(client, resume, job, model=config.CLAUDE_MODEL)
        scored_jobs.append(scored)

        ats = scored["ats_score"]
        rec = scored["recruiter_score"]
        passed = ats >= config.ATS_THRESHOLD and rec >= config.RECRUITER_THRESHOLD
        status = "MATCH" if passed else "skip"
        print(f"         ATS: {ats:3d}%  |  Recruiter: {rec:3d}%  |  [{status}]")

    # Step 4: Filter and display results
    print(f"\n[4/4] Filtering results...")
    matched = filter_jobs(scored_jobs, config.ATS_THRESHOLD, config.RECRUITER_THRESHOLD)

    print_results(matched, config.ATS_THRESHOLD, config.RECRUITER_THRESHOLD)

    results_file = save_results_to_file(
        matched,
        all_jobs_count=len(jobs),
        ats_threshold=config.ATS_THRESHOLD,
        recruiter_threshold=config.RECRUITER_THRESHOLD,
    )
    print(f"  Full results saved to: {results_file}\n")


if __name__ == "__main__":
    main()
