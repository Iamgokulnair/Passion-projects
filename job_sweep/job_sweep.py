"""
Job Sweep — V Gokul
Searches LinkedIn + Indeed + Glassdoor for Director/Head Operations roles in Bengaluru,
scores each JD against the resume from a hiring manager's perspective,
and surfaces the single best Sure Shot pick of the sweep.

Usage (from repo root):
    python job_sweep/job_sweep.py

Designed to run inside a Claude Code session — output renders as markdown inline.
"""

import sys
import os
from datetime import date, datetime, timedelta
from pathlib import Path

_dir = Path(__file__).parent
sys.path.insert(0, str(_dir))

from resume_profile import TARGET_QUERIES, SURE_SHOT_THRESHOLD, STRONG_MATCH_THRESHOLD
from scorer import score_job_match

try:
    from jobspy import scrape_jobs
    import pandas as pd
except ImportError:
    print("Missing packages. Run:  pip install -r job_sweep/requirements.txt")
    sys.exit(1)


# ── Config ────────────────────────────────────────────────────────────────────

LOCATION        = "Bengaluru, Karnataka"
COUNTRY_INDEED  = "IN"
MAX_DAYS_OLD    = 21        # 3-week active hiring window
HOURS_OLD       = MAX_DAYS_OLD * 24
MAX_PER_QUERY   = 15
RESULTS_DIR     = _dir / "results"
RESULTS_DIR.mkdir(exist_ok=True)

BLR_TERMS = {"bengaluru", "bangalore", "blr", "karnataka"}

VERDICT_EMOJI = {
    "SURE_SHOT":    "🎯",
    "STRONG_MATCH": "✅",
    "WEAK_MATCH":   "⚠️",
    "NO_FIT":       "❌",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _posted_label(raw) -> tuple[str, int]:
    """
    Return ('X days ago', days_int) from a date/datetime/string/NaT/None.
    Returns ('Unknown', 999) if unparseable so unknown dates don't block display.
    """
    if raw is None or (hasattr(raw, '__class__') and raw.__class__.__name__ == 'NaTType'):
        return "Unknown", 999

    today = date.today()

    if isinstance(raw, datetime):
        delta = today - raw.date()
    elif isinstance(raw, date):
        delta = today - raw
    else:
        try:
            parsed = datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
            delta = today - parsed
        except (ValueError, TypeError):
            return "Unknown", 999

    days = delta.days
    if days == 0:
        return "Today", 0
    elif days == 1:
        return "Yesterday", 1
    else:
        return f"{days}d ago", days


def _apply_url(job: dict) -> str:
    return job.get("job_url_direct") or job.get("job_url") or "#"


# ── Search ────────────────────────────────────────────────────────────────────

def search_all_queries() -> list[dict]:
    all_jobs: list[dict] = []
    seen_ids: set[str] = set()

    for query in TARGET_QUERIES:
        print(f"  ↳ {query}", flush=True)
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
            print(f"      ⚠ Skipped: {e}", flush=True)
            continue

        if df is None or df.empty:
            continue

        added = 0
        for _, row in df.iterrows():
            job = row.to_dict()
            uid = str(
                job.get("id") or f"{job.get('company','')}|{job.get('title','')}"
            ).lower().strip()
            if uid in seen_ids:
                continue
            seen_ids.add(uid)
            all_jobs.append(job)
            added += 1

        if added:
            print(f"      +{added} jobs", flush=True)

    return all_jobs


def filter_blr_and_fresh(jobs: list[dict]) -> list[dict]:
    """
    Keep jobs that are:
      1. Located in Bengaluru (or location unknown — let scorer decide)
      2. Posted within the 21-day active hiring window
    """
    filtered = []
    dropped_location = 0
    dropped_stale = 0

    for job in jobs:
        # Location filter
        loc = str(job.get("location") or "").lower()
        if loc and not any(t in loc for t in BLR_TERMS):
            dropped_location += 1
            continue

        # Freshness filter
        _, days = _posted_label(job.get("date_posted"))
        if days > MAX_DAYS_OLD:
            dropped_stale += 1
            continue

        filtered.append(job)

    print(f"  Dropped {dropped_location} non-BLR, {dropped_stale} stale (>{MAX_DAYS_OLD}d)", flush=True)
    return filtered


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_all(jobs: list[dict]) -> list[dict]:
    scored = []
    total = len(jobs)

    for i, job in enumerate(jobs, 1):
        title    = str(job.get("title")    or "Unknown Role")
        company  = str(job.get("company")  or "Unknown Company")
        location = str(job.get("location") or LOCATION)
        jd       = str(job.get("description") or "")

        if len(jd) < 80:
            print(f"  [{i}/{total}] Skip (no JD): {title} @ {company}", flush=True)
            continue

        print(f"  [{i}/{total}] Scoring: {title} @ {company}", flush=True)
        scoring = score_job_match(
            job_title=title,
            company=company,
            location=location,
            job_description=jd,
        )
        job["scoring"] = scoring
        scored.append(job)

    return scored


# ── Report ────────────────────────────────────────────────────────────────────

def generate_report(scored_jobs: list[dict], sweep_date: str) -> str:
    sure_shots = [j for j in scored_jobs if j["scoring"]["shortlist_verdict"] == "SURE_SHOT"]
    strong     = [j for j in scored_jobs if j["scoring"]["shortlist_verdict"] == "STRONG_MATCH"]

    top_pick = (
        max(sure_shots, key=lambda x: x["scoring"]["total_score"]) if sure_shots
        else max(strong, key=lambda x: x["scoring"]["total_score"]) if strong
        else None
    )

    by_score = sorted(scored_jobs, key=lambda x: x["scoring"]["total_score"], reverse=True)

    lines = [
        f"# Job Sweep — {sweep_date}",
        "",
        f"*BLR · {len(scored_jobs)} roles scored · "
        f"{len(sure_shots)} sure shot(s) · {len(strong)} strong match(es) · "
        f"≤{MAX_DAYS_OLD}-day freshness window*",
        "",
        "---",
        "",
    ]

    # ── Sure Shot card ──────────────────────────────────────────────
    lines.append("## 🎯 Sure Shot Pick")
    lines.append("")

    if top_pick:
        s   = top_pick["scoring"]
        url = _apply_url(top_pick)
        posted_label, _ = _posted_label(top_pick.get("date_posted"))
        verdict_label = "SURE SHOT" if s["shortlist_verdict"] == "SURE_SHOT" else "BEST AVAILABLE"

        lines += [
            "| Field | Detail |",
            "|-------|--------|",
            f"| **Role** | [{top_pick.get('title','—')}]({url}) |",
            f"| **Company** | {top_pick.get('company','—')} |",
            f"| **Location** | {top_pick.get('location', LOCATION)} |",
            f"| **Posted** | {posted_label} |",
            f"| **Match Score** | **{s['total_score']}/100** — {verdict_label} |",
            f"| **Apply** | [Open listing →]({url}) |",
            "",
            f"> {s['hm_one_liner']}",
            "",
            "**Why you'd get the call:**",
        ]
        for r in s.get("top_reasons_for", []):
            lines.append(f"- {r}")

        if s.get("top_reasons_against"):
            lines += ["", "**Watch-outs:**"]
            for r in s["top_reasons_against"]:
                lines.append(f"- {r}")

        lines += [
            "",
            "**Score breakdown:**",
            "",
            "| Dimension | Score | Max |",
            "|-----------|------:|----:|",
            f"| Level Fit | {s.get('level_fit','—')} | 25 |",
            f"| Domain Match | {s.get('domain_match','—')} | 25 |",
            f"| Scale & Complexity | {s.get('scale_complexity','—')} | 20 |",
            f"| Differentiator Fit | {s.get('differentiator_fit','—')} | 15 |",
            f"| Location Fit | {s.get('location_fit','—')} | 15 |",
            f"| **Total** | **{s['total_score']}** | **100** |",
        ]
    else:
        lines += [
            "> **No Sure Shot today.** Nothing cleared the 75-point threshold.",
            "> Quality gate held. Next sweep may surface a stronger match.",
        ]

    # ── Full sweep table ────────────────────────────────────────────
    lines += [
        "",
        "---",
        "",
        "## Full Sweep",
        "",
        "| Role | Company | Posted | Score | Verdict | Apply |",
        "|------|---------|--------|------:|---------|-------|",
    ]

    for job in by_score:
        s            = job["scoring"]
        url          = _apply_url(job)
        emoji        = VERDICT_EMOJI.get(s["shortlist_verdict"], "")
        posted_label, _ = _posted_label(job.get("date_posted"))

        lines.append(
            f"| [{job.get('title','—')}]({url}) "
            f"| {job.get('company','—')} "
            f"| {posted_label} "
            f"| {s['total_score']}/100 "
            f"| {emoji} {s['shortlist_verdict']} "
            f"| [→]({url}) |"
        )

    lines += [
        "",
        "---",
        "",
        f"*Sweep complete — {sweep_date}. "
        f"Freshness window: ≤{MAX_DAYS_OLD} days (active hiring zone). "
        "Sure Shot ≥ 75 · Strong Match 60–74 · Weak Match 40–59 · No Fit < 40.*",
    ]

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    sweep_date = date.today().isoformat()

    print(f"\n{'─'*58}")
    print(f"  JOB SWEEP  ·  {sweep_date}  ·  BLR  ·  ≤{MAX_DAYS_OLD}d window")
    print(f"{'─'*58}\n")

    print("[1/3] Searching job boards...")
    raw_jobs = search_all_queries()
    print(f"\n  {len(raw_jobs)} unique jobs found across all queries")

    print(f"\n[2/3] Filtering (BLR + ≤{MAX_DAYS_OLD}-day freshness)...")
    fresh_blr = filter_blr_and_fresh(raw_jobs)
    print(f"  {len(fresh_blr)} jobs in the active hiring window\n")

    if not fresh_blr:
        print("  Nothing to score — no fresh BLR results today.")
        return

    print("[3/3] Scoring against resume (hiring manager lens)...")
    scored = score_all(fresh_blr)
    print(f"\n  {len(scored)} jobs scored\n")

    if not scored:
        print("  All listings had no description — nothing to report.")
        return

    report = generate_report(scored, sweep_date)

    out = RESULTS_DIR / f"{sweep_date}.md"
    out.write_text(report, encoding="utf-8")

    # Print report to stdout so Claude Code renders it inline
    print(f"\n{'─'*58}")
    print(report)
    print(f"{'─'*58}")
    print(f"\nSaved → {out}")


if __name__ == "__main__":
    main()
