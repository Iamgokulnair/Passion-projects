"""
reporter.py — Formats and displays the job matching results.

Prints a clean summary to the terminal and saves a text file you can
refer back to later (results.txt in the job-matcher/ folder).
"""

import os
from datetime import datetime


def _score_bar(score: int, width: int = 10) -> str:
    """Create a simple text progress bar for a score."""
    filled = round((score / 100) * width)
    bar = "#" * filled + "-" * (width - filled)
    return f"[{bar}] {score}%"


def _truncate(text: str, max_len: int = 80) -> str:
    """Truncate long text with ellipsis."""
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def format_job(job: dict, index: int) -> str:
    """Format a single matched job as a readable block of text."""
    separator = "=" * 70
    thin_sep = "-" * 70

    lines = [
        "",
        separator,
        f"  MATCH #{index}",
        separator,
        f"  Role     : {job.get('title', 'N/A')}",
        f"  Company  : {job.get('company', 'N/A')}",
        f"  Location : {job.get('location', 'N/A')}",
    ]

    if job.get("salary"):
        lines.append(f"  Salary   : {job['salary']}")

    lines += [
        thin_sep,
        f"  ATS Score        : {_score_bar(job.get('ats_score', 0))}",
        f"  Recruiter Score  : {_score_bar(job.get('recruiter_score', 0))}",
        f"  Combined Avg     : {(job.get('ats_score', 0) + job.get('recruiter_score', 0)) // 2}%",
        thin_sep,
        f"  Summary: {_truncate(job.get('match_summary', ''), 65)}",
    ]

    # ATS reasons
    ats_reasons = job.get("ats_reasons", [])
    if ats_reasons:
        lines.append("")
        lines.append("  Why your ATS score is strong:")
        for r in ats_reasons:
            lines.append(f"    + {_truncate(r, 64)}")

    # Recruiter reasons
    rec_reasons = job.get("recruiter_reasons", [])
    if rec_reasons:
        lines.append("")
        lines.append("  Why a recruiter would shortlist you:")
        for r in rec_reasons:
            lines.append(f"    + {_truncate(r, 64)}")

    # Missing keywords (actionable advice)
    missing = job.get("missing_keywords", [])
    if missing:
        lines.append("")
        lines.append("  Keywords to add to your resume before applying:")
        missing_str = ", ".join(missing[:8])
        if len(missing) > 8:
            missing_str += f" (+{len(missing) - 8} more)"
        lines.append(f"    ! {missing_str}")

    # Apply link
    apply_url = job.get("apply_url", "")
    if apply_url:
        lines += [
            "",
            f"  APPLY HERE: {apply_url}",
        ]

    lines.append(separator)
    return "\n".join(lines)


def print_results(matched_jobs: list, ats_threshold: int = 90, recruiter_threshold: int = 90) -> None:
    """Print all matched jobs to the terminal."""
    header = f"""
{'=' * 70}
  JOB MATCHER RESULTS
  Filters: ATS >= {ats_threshold}%  |  Recruiter Confidence >= {recruiter_threshold}%
  Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}
{'=' * 70}"""

    print(header)

    if not matched_jobs:
        print("""
  No jobs found matching your 90%+ threshold.

  This is actually normal — it means the system is working correctly
  and being strict. Here's what you can try:

  1. Update your resume.txt to add more keywords from job descriptions
  2. Lower the thresholds slightly in config.py (e.g., ATS_THRESHOLD = 85)
  3. Broaden your search queries in config.py
  4. Run the tool again — job results change daily
""")
        return

    print(f"\n  Found {len(matched_jobs)} job(s) matching your criteria!\n")

    for i, job in enumerate(matched_jobs, 1):
        print(format_job(job, i))

    print(f"\n  Total matches: {len(matched_jobs)}\n")


def save_results_to_file(
    matched_jobs: list,
    all_jobs_count: int,
    ats_threshold: int = 90,
    recruiter_threshold: int = 90,
    filename: str = "results.txt",
) -> str:
    """Save results to a text file. Returns the file path."""
    output_path = os.path.join(os.path.dirname(__file__), filename)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"JOB MATCHER RESULTS\n")
        f.write(f"Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n")
        f.write(f"Jobs scanned: {all_jobs_count} | Matches found: {len(matched_jobs)}\n")
        f.write(f"Thresholds: ATS >= {ats_threshold}%  Recruiter >= {recruiter_threshold}%\n")
        f.write("=" * 70 + "\n")

        if not matched_jobs:
            f.write("\nNo jobs matched the criteria.\n")
        else:
            for i, job in enumerate(matched_jobs, 1):
                f.write(format_job(job, i))
                f.write("\n")

    return output_path
