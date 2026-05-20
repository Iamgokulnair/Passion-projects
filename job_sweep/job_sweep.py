"""
Daily Job Sweep — V Gokul
Searches LinkedIn + Indeed for Director/Head Operations roles in Bengaluru,
scores each JD against the resume from a hiring manager's perspective,
and surfaces the single best "Sure Shot" pick of the day.

Run manually:     python job_sweep/job_sweep.py
Scheduled:        GitHub Actions cron (05:00 IST = 23:30 UTC)
"""

import sys
import json
import os
from datetime import date
from pathlib import Path

# Ensure imports work from both repo root and job_sweep dir
_dir = Path(__file__).parent
sys.path.insert(0, str(_dir))

from resume_profile import TARGET_QUERIES, SURE_SHOT_THRESHOLD, STRONG_MATCH_THRESHOLD
from scorer import score_job_match

try:
    from jobspy import scrape_jobs
    import pandas as pd
except ImportError:
    print("ERROR: Run  pip install -r job_sweep/requirements.txt  first.")
    sys.exit(1)


# ── Config ────────────────────────────────────────────────────────────────────

LOCATION = "Bengaluru, Karnataka"
COUNTRY_INDEED = "IN"
HOURS_OLD = 168          # look back 7 days to ensure enough volume
MAX_PER_QUERY = 10       # jobs per search query per board
RESULTS_DIR = _dir / "results"
RESULTS_DIR.mkdir(exist_ok=True)

BLR_TERMS = {"bengaluru", "bangalore", "blr", "karnataka"}


# ── Search ────────────────────────────────────────────────────────────────────

def search_all_queries() -> list[dict]:
    all_jobs: list[dict] = []
    seen_ids: set[str] = set()

    for query in TARGET_QUERIES:
        print(f"  Searching: {query}")
        try:
            df = scrape_jobs(
                site_name=["linkedin", "indeed", "glassdoor"],
                search_term=query,
                location=LOCATION,
                results_wanted=MAX_PER_QUERY,
                hours_old=HOURS_OLD,
                country_indeed=COUNTRY_INDEED,
                linkedin_fetch_description=True,
            )
        except Exception as e:
            print(f"    ⚠ Skipped '{query}': {e}")
            continue

        if df is None or df.empty:
            print(f"    → 0 results")
            continue

        added = 0
        for _, row in df.iterrows():
            job = row.to_dict()
            uid = str(job.get("id") or f"{job.get('company','')}|{job.get('title','')}").lower()
            if uid in seen_ids:
                continue
            seen_ids.add(uid)
            all_jobs.append(job)
            added += 1

        print(f"    → {added} new jobs")

    return all_jobs


def filter_blr(jobs: list[dict]) -> list[dict]:
    """Keep jobs explicitly in Bengaluru or with no location (let scorer decide)."""
    filtered = []
    for job in jobs:
        loc = str(job.get("location") or "").lower()
        if not loc or any(t in loc for t in BLR_TERMS):
            filtered.append(job)
    return filtered


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_all(jobs: list[dict]) -> list[dict]:
    scored = []
    total = len(jobs)
    for i, job in enumerate(jobs, 1):
        title = str(job.get("title") or "Unknown Role")
        company = str(job.get("company") or "Unknown Company")
        location = str(job.get("location") or LOCATION)
        jd = str(job.get("description") or "")

        if len(jd) < 80:
            print(f"  [{i}/{total}] Skipping {title} @ {company} — description too short")
            continue

        print(f"  [{i}/{total}] Scoring: {title} @ {company}")
        result = score_job_match(
            job_title=title,
            company=company,
            location=location,
            job_description=jd,
        )
        job["scoring"] = result
        scored.append(job)

    return scored


# ── Report ────────────────────────────────────────────────────────────────────

VERDICT_EMOJI = {
    "SURE_SHOT":     "🎯",
    "STRONG_MATCH":  "✅",
    "WEAK_MATCH":    "⚠️",
    "NO_FIT":        "❌",
}


def _apply_url(job: dict) -> str:
    return (
        job.get("job_url_direct")
        or job.get("job_url")
        or "#"
    )


def generate_report(scored_jobs: list[dict], sweep_date: str) -> str:
    sure_shots    = [j for j in scored_jobs if j["scoring"]["shortlist_verdict"] == "SURE_SHOT"]
    strong        = [j for j in scored_jobs if j["scoring"]["shortlist_verdict"] == "STRONG_MATCH"]
    all_qualified = sure_shots + strong

    top_pick = (
        max(sure_shots, key=lambda x: x["scoring"]["total_score"]) if sure_shots
        else max(strong,     key=lambda x: x["scoring"]["total_score"]) if strong
        else None
    )

    sorted_jobs = sorted(scored_jobs, key=lambda x: x["scoring"]["total_score"], reverse=True)

    lines = [
        f"# Job Sweep — {sweep_date}",
        f"",
        f"*05:00 IST sweep · {len(scored_jobs)} roles evaluated · "
        f"{len(sure_shots)} sure shot(s) · {len(strong)} strong match(es)*",
        "",
        "---",
        "",
    ]

    # ── Sure Shot Pick ──────────────────────────────────────────────
    lines.append("## 🎯 Today's Sure Shot Pick")
    lines.append("")

    if top_pick:
        s = top_pick["scoring"]
        url = _apply_url(top_pick)
        verdict_label = "SURE SHOT" if s["shortlist_verdict"] == "SURE_SHOT" else "BEST AVAILABLE"

        lines += [
            f"| Field | Detail |",
            f"|-------|--------|",
            f"| **Role** | [{top_pick['title']}]({url}) |",
            f"| **Company** | {top_pick.get('company', '—')} |",
            f"| **Location** | {top_pick.get('location', LOCATION)} |",
            f"| **Match Score** | **{s['total_score']}/100** ({verdict_label}) |",
            f"| **Apply** | [Open listing →]({url}) |",
            "",
            f"> {s['hm_one_liner']}",
            "",
            "**Why you'd get the call:**",
        ]
        for r in s.get("top_reasons_for", []):
            lines.append(f"- {r}")

        if s.get("top_reasons_against"):
            lines.append("")
            lines.append("**Watch-outs:**")
            for r in s["top_reasons_against"]:
                lines.append(f"- {r}")

        # Score breakdown
        lines += [
            "",
            "**Score breakdown:**",
            "",
            "| Dimension | Score | Max |",
            "|-----------|-------|-----|",
            f"| Level Fit | {s.get('level_fit', '—')} | 25 |",
            f"| Domain Match | {s.get('domain_match', '—')} | 25 |",
            f"| Scale & Complexity | {s.get('scale_complexity', '—')} | 20 |",
            f"| Differentiator Fit | {s.get('differentiator_fit', '—')} | 15 |",
            f"| Location Fit | {s.get('location_fit', '—')} | 15 |",
            f"| **Total** | **{s['total_score']}** | **100** |",
        ]
    else:
        lines += [
            "> **No Sure Shot today.** No role cleared the 75-point threshold.",
            "> Quality gate held — next sweep may surface a stronger match.",
        ]

    # ── Full Sweep Table ────────────────────────────────────────────
    lines += [
        "",
        "---",
        "",
        "## Full Sweep Results",
        "",
        "| Role | Company | Location | Score | Verdict | Apply |",
        "|------|---------|----------|-------|---------|-------|",
    ]

    for job in sorted_jobs:
        s = job["scoring"]
        url = _apply_url(job)
        emoji = VERDICT_EMOJI.get(s["shortlist_verdict"], "")
        lines.append(
            f"| [{job.get('title','—')}]({url}) "
            f"| {job.get('company','—')} "
            f"| {job.get('location', LOCATION)} "
            f"| {s['total_score']}/100 "
            f"| {emoji} {s['shortlist_verdict']} "
            f"| [→]({url}) |"
        )

    lines += [
        "",
        "---",
        "",
        f"*Generated by job_sweep.py on {sweep_date}. "
        "Scores reflect hiring-manager likelihood of shortlisting. "
        "Sure Shot = 75+, Strong Match = 60–74.*",
    ]

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    sweep_date = date.today().isoformat()
    print(f"\n{'='*60}")
    print(f"  JOB SWEEP  —  {sweep_date}  —  BLR")
    print(f"{'='*60}\n")

    # 1. Search
    print("[1/3] Searching job boards...")
    raw_jobs = search_all_queries()
    print(f"\n  → {len(raw_jobs)} total unique jobs found")

    # 2. Filter BLR
    blr_jobs = filter_blr(raw_jobs)
    print(f"  → {len(blr_jobs)} after Bengaluru filter\n")

    if not blr_jobs:
        print("  No BLR jobs found. Exiting without output.")
        return

    # 3. Score
    print("[2/3] Scoring against resume (hiring manager lens)...")
    scored_jobs = score_all(blr_jobs)
    print(f"\n  → {len(scored_jobs)} jobs scored\n")

    if not scored_jobs:
        print("  All jobs lacked descriptions. Exiting without output.")
        return

    # 4. Report
    print("[3/3] Generating report...")
    report = generate_report(scored_jobs, sweep_date)

    output_path = RESULTS_DIR / f"{sweep_date}.md"
    output_path.write_text(report, encoding="utf-8")
    print(f"\n  ✓ Saved: {output_path}\n")

    print("=" * 60)
    print(report)
    print("=" * 60)


if __name__ == "__main__":
    main()
