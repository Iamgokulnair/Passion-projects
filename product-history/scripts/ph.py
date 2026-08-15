#!/usr/bin/env python3
"""product-history — is this actually a good price, or a good-looking banner?

    ph.py "<amazon.in URL | flipkart URL | ASIN | product name>"
    ph.py "B0CQKS8NPQ" --discount 40      # audit an advertised "40% off"
    ph.py "<url>" --json                  # machine-readable, for the widget
    ph.py --preflight                     # is the agent-reach lane up?

All network access goes through agent-reach (Jina Reader + Exa). Nothing is
written outside this skill folder.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import ledger  # noqa: E402
from lib.analyze import analyze  # noqa: E402
from lib.fetch import preflight, read_many  # noqa: E402
from lib.parse import parse  # noqa: E402
from lib.resolve import resolve, same_product  # noqa: E402
from lib.util import load_config, now_iso, ordinal, rupees  # noqa: E402

BAR = "─" * 66


def run(raw: str, advertised_discount: float | None = None) -> dict:
    cfg = load_config()

    target = resolve(raw)
    if not target.urls:
        return {
            "ok": False,
            "error": "no_sources_resolved",
            "message": (
                "Could not find this product on any tracked price-history site. "
                "Try the full product name, or paste the Amazon.in URL."
            ),
            "target": {"key": target.key, "name": target.name, "asin": target.asin},
        }

    urls = list(target.urls.values())
    results = read_many(urls, cfg)

    parsed, failures = [], []
    for r in results:
        if not r.ok:
            failures.append({"url": r.url, "error": r.error})
            continue
        obs = parse(r.url, r.text)
        if obs is None:
            failures.append({"url": r.url, "error": "no parser"})
            continue
        obs.fetched_at = r.fetched_at
        if not obs.usable:
            failures.append({"url": r.url, "error": "no usable band"})
            continue
        parsed.append(obs)

    # Identity gate: a page for a different variant must never enter the band —
    # mixing variants produces a wide, meaningless range. The reference is the
    # name the user gave; when they gave a bare /dp/ASIN URL with no slug, the
    # richest source's own title becomes the reference the others are judged on.
    reference = target.name or next((o.title for o in parsed if o.title), None)

    observations = []
    for obs in parsed:
        ok, why = same_product(reference, obs.title)
        if ok:
            observations.append(obs)
        else:
            failures.append({"url": obs.url, "error": why})

    prior = ledger.summary(target.key)
    result = analyze(observations, cfg, prior, advertised_discount)

    title = next((o.title for o in observations if o.title), target.name)
    rows = ledger.append(target.key, observations, title)

    return {
        "ok": True,
        "generated_at": now_iso(),
        "target": {"key": target.key, "name": target.name,
                   "asin": target.asin, "title": title},
        "band": result["band"],
        "confidence": result["confidence"],
        "flags": result["flags"],
        "verdict": result["verdict"],
        "sources": [o.to_dict() for o in observations],
        "failures": failures,
        "ledger": {**prior, "rows_written": rows},
        "legal_basis": cfg["legal_basis"],
    }


# --------------------------------------------------------------------------
# Terminal rendering — must stand alone without the widget (standards §"Terminal first")
# --------------------------------------------------------------------------
def render(res: dict) -> str:
    if not res.get("ok"):
        return f"\n  NO-CALL — {res.get('message')}\n"

    b, c, v = res["band"], res["confidence"], res["verdict"]
    out = []
    title = (res["target"].get("title") or res["target"].get("name") or "—")
    out.append("")
    out.append(f"  {title[:64]}")
    out.append(BAR)

    # Band BEFORE verdict — evidence first, conclusion second.
    out.append("  12-MONTH BAND")
    out.append(f"    Lowest    {rupees(b['low']):>12}")
    out.append(f"    Median    {rupees(b['median']):>12}")
    out.append(f"    Highest   {rupees(b['high']):>12}")
    out.append(f"    Today     {rupees(b['current']):>12}"
               + (f"   ← {ordinal(b['percentile'])} percentile"
                  if b.get("percentile") is not None else ""))
    bar = band_bar(b)
    if bar:
        out.extend(bar)
    out.append("")

    out.append(f"  VERDICT   {v['verdict']}  —  {v['headline']}")
    out.append(f"            {v['reason']}")
    if v.get("downgraded"):
        out.append(f"            (downgraded from {v['base_verdict']} — dark pattern found)")
    if v.get("trigger_price"):
        out.append(f"            Becomes BUY at {rupees(v['trigger_price'])} or below.")
    out.append("")

    out.append(f"  CONFIDENCE  {c['level']}  ({'; '.join(c['reasons'])})")
    out.append("")

    if res["flags"]:
        out.append("  DARK PATTERNS FOUND")
        for f in res["flags"]:
            out.append(f"    • {f['flag']}  [CCPA 2023: {f['ccpa_pattern']}]")
            for line in _wrap(f["detail"], 58):
                out.append(f"      {line}")
        out.append("")
    else:
        out.append("  DARK PATTERNS   none detected")
        out.append("")

    out.append("  SOURCES")
    for s in res["sources"]:
        extra = f"  [{s['avg_window']} avg]" if s["avg_window"] != "12m" else ""
        out.append(f"    ✓ {s['source']:<22} {rupees(s['current']):>10}"
                   f"  low {rupees(s['low']):>9}  high {rupees(s['high']):>9}{extra}")
    for f in res["failures"]:
        host = f["url"].split("/")[2] if "//" in f["url"] else f["url"]
        out.append(f"    ✗ {host:<22} {f['error']}")

    led = res["ledger"]
    if led.get("observations"):
        out.append("")
        out.append(f"  YOUR LEDGER   {led['observations']} prior observations "
                   f"across {led['distinct_days']} days "
                   f"(own low {rupees(led['own_low'])})")

    out.append(BAR)
    out.append("  Dark-pattern definitions: CCPA Guidelines for Prevention and")
    out.append("  Regulation of Dark Patterns, 2023 (Consumer Protection Act s.18).")
    out.append("")
    return "\n".join(out)


def band_bar(b: dict, width: int = 46) -> list[str]:
    """The range, drawn. Works in any terminal — this is the visual for anyone
    running the CLI outside Claude Code, where the widget is unavailable."""
    low, high = b.get("low"), b.get("high")
    cur, med = b.get("current"), b.get("median")
    if low is None or high is None or high <= low:
        return []

    def at(v):
        if v is None:
            return None
        return max(0, min(width - 1, round((v - low) / (high - low) * (width - 1))))

    track = ["─"] * width
    mi = at(med)
    if mi is not None:
        track[mi] = "┼"
    ci = at(cur)
    if ci is not None:
        track[ci] = "●"

    caret = [" "] * width
    if ci is not None:
        caret[ci] = "▲"

    return [
        "",
        "    low  " + "".join(track) + "  high",
        "         " + "".join(caret).rstrip()
        + ("  today" if ci is not None else ""),
        "         ┼ = 12-month median",
    ]


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def main():
    ap = argparse.ArgumentParser(description="Price-history verdict for a product.")
    ap.add_argument("query", nargs="?", help="URL, ASIN, or product name")
    ap.add_argument("--discount", type=float, default=None,
                    help="advertised discount %% from the banner, to audit")
    ap.add_argument("--json", action="store_true", help="emit JSON only")
    ap.add_argument("--preflight", action="store_true",
                    help="check the agent-reach lane and exit")
    args = ap.parse_args()

    if args.preflight:
        st = preflight()
        print(json.dumps(st, indent=2))
        sys.exit(0 if st["reader"] else 1)

    if not args.query:
        ap.error("a product URL, ASIN, or name is required")

    res = run(args.query, args.discount)

    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(render(res))

    sys.exit(0 if res.get("ok") else 2)


if __name__ == "__main__":
    main()
