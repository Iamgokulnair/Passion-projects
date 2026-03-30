"""
searcher.py — Fetches job listings from Google Jobs via SerpAPI.

How it works:
1. Loads your resume from resume.txt
2. Searches Google Jobs (via SerpAPI) for each query in config.py
3. Fetches the full job description for each result
4. Returns a clean list of jobs ready for scoring
"""

import os
import sys
import time

import requests


SERPAPI_JOBS_URL = "https://serpapi.com/search"


def load_resume(path: str = "resume.txt") -> str:
    """
    Read resume.txt and return its contents as a string.
    Shows a clear error message if the file is missing or not updated.
    """
    resume_path = os.path.join(os.path.dirname(__file__), path)

    if not os.path.exists(resume_path):
        print(f"\nERROR: Could not find '{path}'")
        print("  Please make sure resume.txt is in the job-matcher/ folder.")
        print("  See README.md -> Step 1 for instructions.\n")
        sys.exit(1)

    with open(resume_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    if "REPLACE EVERYTHING IN THIS FILE" in content:
        print("\nWARNING: You haven't updated resume.txt yet!")
        print("  Open resume.txt and replace the template with your actual resume.")
        print("  See README.md -> Step 1 for instructions.\n")
        sys.exit(1)

    return content


def _search_google_jobs(query: str, location: str, country: str, api_key: str, num: int = 10) -> list:
    """
    Search Google Jobs via SerpAPI and return a list of job result dicts.

    Returns list of dicts with: title, company, location, via,
    description (snippet), job_id (encoded), apply_url, salary.
    """
    params = {
        "engine": "google_jobs",
        "q": query,
        "location": location,
        "gl": country,
        "hl": "en",
        "num": num,
        "api_key": api_key,
    }

    try:
        response = requests.get(SERPAPI_JOBS_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.ConnectionError:
        print("    ERROR: Could not connect to SerpAPI. Check your internet connection.")
        return []
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            print("    ERROR: Invalid SerpAPI key. Check SERPAPI_KEY in config.py.")
        else:
            print(f"    ERROR: SerpAPI returned {response.status_code}: {e}")
        return []
    except Exception as e:
        print(f"    ERROR: Unexpected error searching jobs: {e}")
        return []

    jobs_results = data.get("jobs_results", [])
    jobs = []

    for result in jobs_results:
        # Extract the best available apply link
        apply_options = result.get("apply_options", [])
        apply_url = apply_options[0].get("link", "") if apply_options else ""

        # Salary: may be in detected_extensions or directly on result
        extensions = result.get("detected_extensions", {})
        salary = extensions.get("salary", result.get("salary", "Not specified"))
        schedule = extensions.get("schedule_type", "")

        # Build a unique ID from the job listing token or title+company
        job_token = result.get("job_id") or result.get("token") or ""

        jobs.append({
            "job_id": job_token or f"{result.get('title', '')}_{result.get('company_name', '')}",
            "title": result.get("title", ""),
            "company": result.get("company_name", ""),
            "location": result.get("location", ""),
            "salary": f"{salary} ({schedule})".strip(" ()") if schedule else salary,
            "description": result.get("description", ""),
            "apply_url": apply_url,
            "via": result.get("via", ""),
        })

    return jobs


def fetch_jobs(config, verbose: bool = True) -> list:
    """
    Fetch jobs for all configured search queries.

    Args:
        config: The config module with SERPAPI_KEY, JOB_SEARCH_QUERIES, etc.
        verbose: Print progress messages

    Returns:
        Deduplicated list of job dicts ready for scoring.
    """
    if not config.SERPAPI_KEY or config.SERPAPI_KEY.startswith("PASTE"):
        print("\nERROR: You haven't set your SerpAPI key!")
        print("  1. Go to https://serpapi.com/ and create a free account")
        print("  2. Copy your API key")
        print("  3. Open config.py and paste it as SERPAPI_KEY")
        sys.exit(1)

    all_jobs = {}  # Keyed by job_id to deduplicate across queries

    queries = list(config.JOB_SEARCH_QUERIES)

    # Add remote variants if requested
    if config.INCLUDE_REMOTE:
        remote_q = [f"{q} remote" for q in config.JOB_SEARCH_QUERIES[:2]]
        queries = queries + remote_q

    for i, query in enumerate(queries):
        if verbose:
            print(f"  [{i+1}/{len(queries)}] Searching: \"{query}\" in {config.SEARCH_LOCATION}")

        results = _search_google_jobs(
            query=query,
            location=config.SEARCH_LOCATION,
            country=config.COUNTRY_CODE,
            api_key=config.SERPAPI_KEY,
            num=config.MAX_JOBS_PER_QUERY,
        )

        new_count = 0
        for job in results:
            jid = job["job_id"]
            if jid and jid not in all_jobs:
                all_jobs[jid] = job
                new_count += 1

        if verbose:
            print(f"       Found {len(results)} results, {new_count} new unique jobs")

        # Be polite to the API — small delay between requests
        if i < len(queries) - 1:
            time.sleep(0.5)

    jobs = list(all_jobs.values())

    if verbose:
        print(f"\n  Total unique jobs found: {len(jobs)}")

    return jobs
