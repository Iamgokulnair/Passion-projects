"""Triangulate sources into one band, grade confidence, audit for dark patterns.

Two rules govern everything here, both from standards/verdict.md:

  1. Never invent a number. Every figure traces to a source or the ledger.
  2. Conflicting sources are SHOWN, never silently averaged. Averaging away a
     disagreement is how a tool launders a guess into a decision.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from .util import median, ordinal, pct, spread_pct


# --------------------------------------------------------------------------
# Band
# --------------------------------------------------------------------------
def build_band(observations: list, ledger_summary: dict | None = None) -> dict:
    """Reconcile every usable source into one 12-month band."""
    usable = [o for o in observations if o.usable]

    lows = [o.low for o in usable if o.low is not None]
    highs = [o.high for o in usable if o.high is not None]
    currents = [o.current for o in usable if o.current is not None]
    # Only 12-month averages feed the median. A 30-day average is a different
    # statistic and would quietly bias the band.
    avgs = [o.avg for o in usable if o.avg is not None and o.avg_window == "12m"]

    band = {
        "low": min(lows) if lows else None,
        "high": max(highs) if highs else None,
        "median": median(avgs) if avgs else None,
        "current": median(currents) if currents else None,
        "sources_used": len(usable),
        "source_ids": [o.source for o in usable],
        "current_spread_pct": spread_pct(currents),
        "low_spread_pct": spread_pct(lows),
        "avg_window_note": None,
    }

    if not avgs:
        thirty = [o.avg for o in usable if o.avg is not None]
        if thirty:
            band["median"] = median(thirty)
            band["avg_window_note"] = "median derived from 30-day averages only"

    # The ledger can widen the band beyond what any site currently admits.
    if ledger_summary and ledger_summary.get("observations"):
        ol, oh = ledger_summary.get("own_low"), ledger_summary.get("own_high")
        if ol is not None and (band["low"] is None or ol < band["low"]):
            band["low"] = ol
            band["low_from_ledger"] = True
        if oh is not None and (band["high"] is None or oh > band["high"]):
            band["high"] = oh
            band["high_from_ledger"] = True

    band["percentile"] = _percentile(band["current"], band["low"], band["high"])
    return band


def _percentile(current, low, high):
    """Where today's price sits in the observed band. 0 = all-time low."""
    if current is None or low is None or high is None or high <= low:
        return None
    return round(max(0.0, min(100.0, (current - low) / (high - low) * 100)), 1)


# --------------------------------------------------------------------------
# Confidence — the honest-quality-bar gate
# --------------------------------------------------------------------------
def grade_confidence(observations: list, band: dict, cfg: dict) -> dict:
    usable = [o for o in observations if o.usable]
    n = len(usable)
    spread = band.get("current_spread_pct", 0.0)
    rules = cfg["confidence"]

    if n >= rules["high"]["min_sources"] and spread <= rules["high"]["max_spread_pct"]:
        level = "HIGH"
    elif n >= rules["medium"]["min_sources"] and spread <= rules["medium"]["max_spread_pct"]:
        level = "MEDIUM"
    else:
        level = "LOW"

    reasons = [f"{n} usable source{'s' if n != 1 else ''}",
               f"{spread}% spread on current price"]

    # A flat band is one datapoint wearing a range's clothes.
    if band.get("low") is not None and band.get("low") == band.get("high"):
        level = "LOW"
        reasons.append("band is flat — no real range observed")

    if band.get("median") is None:
        level = "LOW" if level != "LOW" else level
        reasons.append("no 12-month median available")

    outlier = _outlier(usable)
    if outlier:
        reasons.append(f"outlier: {outlier}")

    return {"level": level, "reasons": reasons, "sources": n,
            "spread_pct": spread, "outlier": outlier,
            "withholds": level == "LOW" and rules.get("low_withholds_verdict", True)}


def _outlier(usable: list):
    """Name the source that disagrees most, rather than averaging it away."""
    pts = [(o.source, o.current) for o in usable if o.current is not None]
    if len(pts) < 3:
        return None
    med = median([c for _, c in pts])
    if not med:
        return None
    worst, worst_d = None, 0.0
    for src, c in pts:
        d = abs(c - med) / med * 100
        if d > worst_d:
            worst, worst_d = src, d
    return f"{worst} differs {worst_d:.0f}% from median" if worst_d > 15 else None


# --------------------------------------------------------------------------
# Dark-pattern audit — CCPA Guidelines 2023
# --------------------------------------------------------------------------
def audit_dark_patterns(observations: list, band: dict, cfg: dict,
                        advertised_discount_pct: float | None = None) -> list[dict]:
    flags = []
    dp = cfg["dark_patterns"]
    usable = [o for o in observations if o.usable]

    current = band.get("current")
    med = band.get("median")
    high = band.get("high")

    mrps = [o.mrp for o in usable if o.mrp is not None]
    mrp = max(mrps) if mrps else None

    # 1 — Fictitious MRP anchor
    if mrp and current and med:
        off_mrp = pct(current, mrp)
        off_med = pct(current, med)
        if off_mrp is not None and off_med is not None:
            gap = off_mrp - off_med
            if gap > dp["fictitious_mrp_anchor"]["threshold_pp"]:
                # off_med is negative when today's price sits ABOVE the median;
                # saying "-1% off" would obscure exactly what we are exposing.
                if off_med >= 0:
                    real = f"only {off_med:.0f}% below the real 12-month median of {_r(med)}"
                else:
                    real = (f"actually {abs(off_med):.0f}% ABOVE the real "
                            f"12-month median of {_r(med)}")
                flags.append({
                    "flag": "Fictitious MRP anchor",
                    "ccpa_pattern": dp["fictitious_mrp_anchor"]["ccpa_pattern"],
                    "detail": (
                        f"Advertised {off_mrp:.0f}% off a claimed MRP of "
                        f"{_r(mrp)}, but {real} — a {gap:.0f}pp gap between "
                        f"the discount claimed and the discount real."
                    ),
                })

    # 2 — Never-was price
    if mrp and high and mrp > high:
        flags.append({
            "flag": "Never-was price",
            "ccpa_pattern": dp["never_was_price"]["ccpa_pattern"],
            "detail": (
                f"Claimed MRP {_r(mrp)} exceeds the highest price ever "
                f"observed ({_r(high)}). No source has seen it sold at MRP."
            ),
        })

    # 3 — Fake sale
    if advertised_discount_pct and current and med and current >= med:
        flags.append({
            "flag": "Fake sale",
            "ccpa_pattern": dp["fake_sale"]["ccpa_pattern"],
            "detail": (
                f"A {advertised_discount_pct:.0f}% 'sale' priced at {_r(current)}, "
                f"at or above the 12-month median of {_r(med)}."
            ),
        })

    # 4 — Recycled discount
    events = []
    for o in usable:
        events.extend(o.events or [])
    if events:
        counts = Counter(e["to"] for e in events if e.get("to"))
        for price, n in counts.items():
            if n >= dp["recycled_discount"]["min_occurrences"]:
                dates = sorted(e["date"] for e in events if e.get("to") == price)
                flags.append({
                    "flag": "Recycled discount",
                    "ccpa_pattern": dp["recycled_discount"]["ccpa_pattern"],
                    "detail": (
                        f"{_r(price)} has been presented as a price drop {n} times "
                        f"({dates[0]} … {dates[-1]}) — a recurring price dressed "
                        f"as an event."
                    ),
                })
                break

    # 5 — Pre-sale hike
    hike = _pre_sale_hike(events, dp["pre_sale_hike"])
    if hike:
        flags.append(hike)

    return flags


def _pre_sale_hike(events: list, rule: dict):
    """Did the price climb just before the current 'offer'?"""
    dated = []
    for e in events:
        try:
            dated.append((datetime.fromisoformat(e["date"]).date(), e))
        except (ValueError, KeyError, TypeError):
            continue
    if len(dated) < 2:
        return None
    # Sort on the date ONLY. Two drops sharing a date is common, and a bare
    # .sort() would fall through to comparing the dicts and raise TypeError.
    dated.sort(key=lambda pair: pair[0])
    cutoff = date.today() - timedelta(days=rule["window_days"] * 2)
    recent = [(d, e) for d, e in dated if d >= cutoff]
    for d, e in recent:
        frm, to = e.get("from"), e.get("to")
        if frm and to and frm > to:
            prior = [pe for pd, pe in dated
                     if pd < d and (d - pd).days <= rule["window_days"]]
            for pe in prior:
                pfrm, pto = pe.get("from"), pe.get("to")
                if pfrm and pto and pto > pfrm:
                    rise = (pto - pfrm) / pfrm * 100
                    if rise > rule["threshold_pct"]:
                        return {
                            "flag": "Pre-sale hike",
                            "ccpa_pattern": rule["ccpa_pattern"],
                            "detail": (
                                f"Price rose {rise:.0f}% within "
                                f"{rule['window_days']} days before the "
                                f"{d.isoformat()} drop."
                            ),
                        }
    return None


def _r(v):
    return "₹{:,.0f}".format(v) if v is not None else "—"


# --------------------------------------------------------------------------
# Verdict
# --------------------------------------------------------------------------
def decide(band: dict, confidence: dict, flags: list, cfg: dict) -> dict:
    rules = cfg["verdict"]
    p = band.get("percentile")
    current, low, med = band.get("current"), band.get("low"), band.get("median")

    if confidence["withholds"]:
        return {
            "verdict": "NO-CALL",
            "headline": "Not enough data to call it.",
            "reason": "; ".join(confidence["reasons"]),
            "trigger_price": _trigger(band, cfg),
            "downgraded": False,
        }

    near_low = (
        low is not None and current is not None and low > 0
        and (current - low) / low * 100 <= rules["buy_within_pct_of_low"]
    )

    if p is None:
        base = "FAIR"
    elif p <= rules["buy_max_percentile"] and near_low:
        base = "BUY"
    elif p <= rules["fair_max_percentile"]:
        base = "FAIR"
    else:
        base = "WAIT"

    order = ["BUY", "FAIR", "WAIT"]
    downgraded = False
    verdict = base
    if flags and rules.get("trap_downgrades_one_band", True):
        idx = min(order.index(base) + 1, len(order) - 1)
        verdict = order[idx]
        downgraded = verdict != base
        if base == "WAIT":
            verdict = "TRAP"
            downgraded = True

    if p is not None and med is not None and current is not None:
        vs_med = pct(current, med)
        reason = (f"{ordinal(p)} percentile of the 12-month band; "
                  f"{abs(vs_med):.0f}% {'below' if vs_med > 0 else 'above'} the median")
    else:
        reason = "band incomplete — percentile unavailable"

    return {
        "verdict": verdict,
        "base_verdict": base,
        "headline": _headline(verdict),
        "reason": reason,
        "trigger_price": _trigger(band, cfg),
        "downgraded": downgraded,
    }


def _headline(v):
    return {
        "BUY": "Good price — near the floor.",
        "FAIR": "Reasonable, but not the floor.",
        "WAIT": "Above the typical price. Hold.",
        "TRAP": "Manipulated offer. Do not buy on this banner.",
        "NO-CALL": "Not enough data to call it.",
    }[v]


def _trigger(band: dict, cfg: dict):
    """The counterfactual the standard requires: what price would flip this to BUY."""
    low, high = band.get("low"), band.get("high")
    if low is None or high is None or high <= low:
        return None
    p = cfg["verdict"]["buy_max_percentile"] / 100.0
    within = 1 + cfg["verdict"]["buy_within_pct_of_low"] / 100.0
    return round(min(low + (high - low) * p, low * within), 0)


def analyze(observations: list, cfg: dict, ledger_summary: dict | None = None,
            advertised_discount_pct: float | None = None) -> dict:
    band = build_band(observations, ledger_summary)
    confidence = grade_confidence(observations, band, cfg)
    flags = audit_dark_patterns(observations, band, cfg, advertised_discount_pct)
    verdict = decide(band, confidence, flags, cfg)
    return {"band": band, "confidence": confidence,
            "flags": flags, "verdict": verdict}
