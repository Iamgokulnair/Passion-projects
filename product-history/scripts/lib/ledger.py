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


_ROW_FIELDS = ("current", "mrp", "low", "high", "avg", "avg_window")


def _last_row_for(key: str, source: str, existing: list[dict]):
    for row in reversed(existing):
        if row.get("key") == key and row.get("source") == source:
            return row
    return None


def append(key: str, observations: list, title: str | None = None) -> int:
    """Record this run's observations. Returns rows actually written.

    Skips a source when its last recorded row for this product already has
    identical price fields — otherwise running the tool twice in a minute
    logs the same observation twice, and the ledger's "N prior observations"
    count reads as N independent datapoints when it is really one repeated."""
    _ensure()
    existing = history(key)
    ts = now_iso()
    rows = 0
    with open(LEDGER_PATH, "a", encoding="utf-8") as fh:
        for o in observations:
            if not o.usable:
                continue
            new_row = {f: getattr(o, f) for f in _ROW_FIELDS}
            prior = _last_row_for(key, o.source, existing)
            if prior and all(prior.get(f) == new_row[f] for f in _ROW_FIELDS):
                continue
            fh.write(json.dumps({
                "ts": ts,
                "key": key,
                "title": title or o.title,
                "source": o.source,
                "url": o.url,
                **new_row,
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
    """What our OWN records say — independent of what the sites claim today.

    A row missing an expected field (a hand-edited ledger, a future format
    change) must degrade gracefully, matching the "corrupt line never takes
    the tool down" contract in history() above — .get(), not [].
    """
    rows = history(key)
    if not rows:
        return {"observations": 0, "first_seen": None, "last_seen": None,
                "own_low": None, "own_high": None, "distinct_days": 0}

    currents = [r["current"] for r in rows if r.get("current")]
    timestamps = [r["ts"] for r in rows if r.get("ts")]
    days = {t[:10] for t in timestamps}
    return {
        "observations": len(rows),
        "first_seen": timestamps[0] if timestamps else None,
        "last_seen": timestamps[-1] if timestamps else None,
        "own_low": min(currents) if currents else None,
        "own_high": max(currents) if currents else None,
        "distinct_days": len(days),
    }
