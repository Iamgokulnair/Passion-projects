"""
fetch_jobs.py — scrapes job boards and saves raw results for Claude to score.
Runs automatically via the SessionStart hook. No AI/API key required.
"""

import sys
import json
from datetime import date, datetime, timedelta
from pathlib import Path

_dir = Path(__file__).parent
sys.path.insert(0, str(_dir))

try:
    from jobspy import scrape_jobs
except ImportError:
    print("jobspy not installed — hook may still be installing deps")
    sys.exit(0)

LOCATION       = "Bengaluru, Karnataka"
COUNTRY        = "india"
MAX_DAYS_OLD   = 21
HOURS_OLD      = MAX_DAYS_OLD * 24
MAX_PER_QUERY  = 15
BLR_TERMS      = {"bengaluru", "bangalore", "blr", "karnataka"}

QUERIES = [
    "Director of Operations",
    "Head of Operations",
    "Head of GCC Operations",
    "Director People Operations",
    "VP Operations",
    "Head Strategy Operations",
    "Senior Manager Operations GCC",
]

OUT = _dir / "results" / "latest_raw.json"
OUT.parent.mkdir(exist_ok=True)


def days_old(raw) -> int:
    if raw is None or str(raw) in ("NaT", "None", "nan", ""):
        return 0
    today = date.today()
    try:
        if isinstance(raw, (datetime,)):
            return (today - raw.date()).days
        if isinstance(raw, date):
            return (today - raw).days
        return (today - datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()).days
    except Exception:
        return 0


def main():
    today = date.today().isoformat()
    print(f"[fetch_jobs] {today} — scraping BLR roles (≤{MAX_DAYS_OLD}d window)")

    all_jobs, seen = [], set()

    for q in QUERIES:
        print(f"  ↳ {q}", flush=True)
        try:
            df = scrape_jobs(
                site_name=["linkedin", "indeed", "glassdoor"],
                search_term=q,
                location=LOCATION,
                results_wanted=MAX_PER_QUERY,
                hours_old=HOURS_OLD,
                country_indeed=COUNTRY,
                linkedin_fetch_description=True,
            )
        except Exception as e:
            print(f"      ⚠ {e}", flush=True)
            continue

        if df is None or df.empty:
            continue

        for _, row in df.iterrows():
            job = row.to_dict()
            uid = str(job.get("id") or f"{job.get('company','')}|{job.get('title','')}").lower()
            if uid in seen:
                continue

            loc = str(job.get("location") or "").lower()
            if loc and not any(t in loc for t in BLR_TERMS):
                continue

            age = days_old(job.get("date_posted"))
            if age > MAX_DAYS_OLD:
                continue

            seen.add(uid)
            all_jobs.append({
                "title":       str(job.get("title") or ""),
                "company":     str(job.get("company") or ""),
                "location":    str(job.get("location") or LOCATION),
                "days_ago":    age,
                "posted_label": "Today" if age == 0 else ("Yesterday" if age == 1 else f"{age}d ago"),
                "description": str(job.get("description") or "")[:4000],
                "apply_url":   str(job.get("job_url_direct") or job.get("job_url") or ""),
            })

    payload = {"fetched_date": today, "total": len(all_jobs), "jobs": all_jobs}
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[fetch_jobs] saved {len(all_jobs)} jobs → {OUT}")


if __name__ == "__main__":
    main()
