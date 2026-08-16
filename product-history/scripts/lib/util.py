"""Shared primitives: config loading, money parsing, date parsing.

Pure stdlib. No third-party dependency anywhere in this skill.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(ROOT, "config", "engine.json")
DATA_DIR = os.path.join(ROOT, "data")

_MONEY = re.compile(r"₹\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)")

_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun",
         "jul", "aug", "sep", "oct", "nov", "dec"]
    )
}


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def money(text: str):
    """First rupee amount in `text`, as a float. None if absent.

    Handles ₹1,499 · ₹2,249.00 · ₹ 799. Deliberately strict about the ₹ sign:
    a bare integer on a price page is more often a rating or a review count.
    """
    if not text:
        return None
    m = _MONEY.search(text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def all_money(text: str) -> list[float]:
    out = []
    for raw in _MONEY.findall(text or ""):
        try:
            out.append(float(raw.replace(",", "")))
        except ValueError:
            pass
    return out


def parse_loose_date(text: str):
    """'8th Jul 2026' / '23rd Nov 2025' -> date. None if unparseable.

    Tracker pages write dates in ordinal English, not ISO.
    """
    if not text:
        return None
    m = re.search(
        r"(\d{1,2})\s*(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?\s+(\d{4})", text
    )
    if not m:
        return None
    day, mon_raw, year = m.groups()
    mon = _MONTHS.get(mon_raw[:3].lower())
    if not mon:
        return None
    try:
        return datetime(int(year), mon, int(day), tzinfo=timezone.utc).date()
    except ValueError:
        return None


def pct(part: float, whole: float):
    """Percent difference of `part` below `whole`. None on bad input."""
    if not whole or whole <= 0 or part is None:
        return None
    return round((whole - part) / whole * 100, 1)


def rupees(v) -> str:
    """Format for display: 1499.0 -> '₹1,499'. Always separators, per standard."""
    if v is None:
        return "—"
    return "₹{:,.0f}".format(v)


def ordinal(n) -> str:
    """1 -> 1st, 71 -> 71st, 13 -> 13th."""
    n = int(round(n))
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def spread_pct(values: list[float]):
    """Relative spread across source estimates: (max-min)/median * 100."""
    vals = [v for v in values if v is not None and v > 0]
    if len(vals) < 2:
        return 0.0
    vals.sort()
    mid = vals[len(vals) // 2]
    if not mid:
        return 0.0
    return round((vals[-1] - vals[0]) / mid * 100, 1)


def median(values: list[float]):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    n = len(vals)
    if n % 2:
        return vals[n // 2]
    return (vals[n // 2 - 1] + vals[n // 2]) / 2
