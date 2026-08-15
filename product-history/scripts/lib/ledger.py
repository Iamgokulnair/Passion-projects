"""The compounding asset.

Trackers can revise, thin out, or lose their history. A local append-only file
cannot. Every run writes what it saw; every later run reads it back. After a
few months this is first-party truth no seller can edit — and it is the reason
a source going dark degrades the tool instead of blinding it.

Lives at product-history/data/ledger.jsonl, INSIDE the skill folder and
gitignored. Nothing is written anywhere else on the machine.
"""
from __future__ import annotations

import json
import os

from .util import DATA_DIR, now_iso

LEDGER_PATH = os.path.join(DATA_DIR, "ledger.jsonl")


def _ensure():
    os.makedirs(DATA_DIR, exist_ok=True)


def append(key: str, observations: list, title: str | None = None) -> int:
    """Record this run's observations. Returns rows written."""
    _ensure()
    ts = now_iso()
    rows = 0
    with open(LEDGER_PATH, "a", encoding="utf-8") as fh:
        for o in observations:
            if not o.usable:
                continue
            fh.write(json.dumps({
                "ts": ts,
                "key": key,
                "title": title or o.title,
                "source": o.source,
                "url": o.url,
                "current": o.current,
                "mrp": o.mrp,
                "low": o.low,
                "high": o.high,
                "avg": o.avg,
                "avg_window": o.avg_window,
            }, ensure_ascii=False) + "\n")
            rows += 1
    return rows


def history(key: str) -> list[dict]:
    """Every prior row for this product, oldest first."""
    if not os.path.exists(LEDGER_PATH):
        return []
    out = []
    with open(LEDGER_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue  # a corrupt line must never take the tool down
            if row.get("key") == key:
                out.append(row)
    return out


def summary(key: str) -> dict:
    """What our OWN records say — independent of what the sites claim today."""
    rows = history(key)
    if not rows:
        return {"observations": 0, "first_seen": None, "last_seen": None,
                "own_low": None, "own_high": None, "distinct_days": 0}

    currents = [r["current"] for r in rows if r.get("current")]
    days = {r["ts"][:10] for r in rows}
    return {
        "observations": len(rows),
        "first_seen": rows[0]["ts"],
        "last_seen": rows[-1]["ts"],
        "own_low": min(currents) if currents else None,
        "own_high": max(currents) if currents else None,
        "distinct_days": len(days),
    }
