"""Triangulate sources into one band, grade confidence, audit for dark patterns.

Two rules govern everything here, both from standards/verdict.md:

  1. Never invent a number. Every figure traces to a source or the ledger.
  2. Conflicting sources are SHOWN, never silently averaged. Averaging away a
     disagreement is how a tool launders a guess into a decision.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone

from .util import median, ordinal, pct, spread_pct

# A source's low/high is sanity-checked against the BAND's current price (the
# median across all sources), not that source's own current — a single source
# can be internally self-consistent yet still be a different listing (a
# reseller bundle, a mis-grouped capacity/colour variant) entirely. The band
# current is the more robust reference precisely because it isn't just one
# source vouching for itself.
_MAX_HIGH_MULTIPLE = 3.0
_MIN_LOW_FRACTION = 0.3


def build_band(observations: list, ledger_summary: dict | None = None) -> dict:
    """Reconcile every usable source into one price band.

    Deliberately not called a "12-month band": none of the four tracker
    sources state the time window their low/high/average actually cover in
    the page text, so asserting "12 months" would be a claim the data does
    not support. What IS shown honestly: the observed low/high, an average
    with its window labelled when known, and — for pricediff.in, the one
    source that publishes it — the real number of days it has tracked this
    product.
    """
    usable = [o for o in observations if o.usable]

    # Pass 1 — the band's own current price. Computed first because it is the
    # reference every low/high gets sanity-checked against.
    currents = [o.current for o in usable if o.current is not None]
    band_current = median(currents)

    # Pass 2 — filter low/high against that reference.
    low_pairs, high_pairs, avgs, avg_windows = [], [], [], []
    excluded_notes = []

    for o in usable:
        if o.low is not None:
            if band_current and o.low < band_current * _MIN_LOW_FRACTION:
                excluded_notes.append(
                    f"{o.source}'s low ({_fmt(o.low)}) excluded — implausible "
                    f"vs the current price across sources ({_fmt(band_current)})"
                )
            else:
                low_pairs.append((o.source, o.low))
        if o.high is not None:
            if band_current and o.high > band_current * _MAX_HIGH_MULTIPLE:
                excluded_notes.append(
                    f"{o.source}'s high ({_fmt(o.high)}) excluded — implausible "
                    f"vs the current price across sources ({_fmt(band_current)}); "
                    f"likely a different listing (reseller, bundle, or variant)"
                )
            else:
                high_pairs.append((o.source, o.high))
        if o.avg is not None:
            avgs.append(o.avg)
            avg_windows.append(o.avg_window)

    lows = [v for _, v in low_pairs]
    highs = [v for _, v in high_pairs]

    band = {
        "low": min(lows) if lows else None,
        "high": max(highs) if highs else None,
        "median": median(avgs) if avgs else None,
        "current": band_current,
        "sources_used": len(usable),
        "source_ids": [o.source for o in usable],
        "current_spread_pct": spread_pct(currents),
        "low_spread_pct": spread_pct(lows),
        "high_spread_pct": spread_pct(highs),
        "avg_window_note": _window_note(avg_windows),
        "excluded_notes": excluded_notes,
    }

    depth = _tracking_depth(usable)
    if depth:
        band.update(depth)

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


def _fmt(v):
    return "₹{:,.0f}".format(v)


def _window_note(windows: list[str]):
    known = [w for w in windows if w and w != "unknown"]
    if not windows:
        return None
    if not known:
        return "average's tracked window is not stated by any source — treat as directional"
    if len(set(known)) == 1 and len(known) == len(windows):
        return f"average reflects a {known[0]} window, not a verified 12-month figure"
    return (f"average blends different windows ({', '.join(sorted(set(windows)))}) "
           f"— treat as directional, not a verified 12-month figure")


def _tracking_depth(usable: list):
    """The one genuine history-depth signal available: pricediff.in states
    how long it has tracked a product and how many checkpoints it recorded."""
    candidates = [o for o in usable if o.tracking_since]
    if not candidates:
        return None
    earliest = min(candidates, key=lambda o: o.tracking_since)
    try:
        since = datetime.fromisoformat(earliest.tracking_since).replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - since).days
    except ValueError:
        days = None
    return {
        "tracked_since": earliest.tracking_since,
        "tracked_days": days,
        "checkpoints": sum(o.checkpoints or 0 for o in candidates),
    }


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
                    real = f"only {off_med:.0f}% below the real median of {_r(med)}"
                else:
                    real = (f"actually {abs(off_med):.0f}% ABOVE the real "
                            f"median of {_r(med)}")
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
                f"at or above the observed median of {_r(med)}."
            ),
        })

    # 4 — Recycled discount. Config states this must recur "in 12 months" —
    # enforce that window rather than counting a source's entire history,
    # which can span years and would otherwise flag ordinary long-run price
    # stability as manufactured urgency.
    events = []
    for o in usable:
        events.extend(o.events or [])
    if events:
        cutoff = date.today() - timedelta(days=365)
        recent_events = [e for e in events if _event_date(e) and _event_date(e) >= cutoff]
        counts = Counter(e["to"] for e in recent_events if e.get("to"))
        for price, n in counts.items():
            if n >= dp["recycled_discount"]["min_occurrences"]:
                dates = sorted(e["date"] for e in recent_events if e.get("to") == price)
                flags.append({
                    "flag": "Recycled discount",
                    "ccpa_pattern": dp["recycled_discount"]["ccpa_pattern"],
                    "detail": (
                        f"{_r(price)} has been presented as a price drop {n} times "
                        f"in the last 12 months ({dates[0]} … {dates[-1]}) — a "
                        f"recurring price dressed as an event."
                    ),
                })
                break

    # 5 — Pre-sale hike
    hike = _pre_sale_hike(events, dp["pre_sale_hike"])
    if hike:
        flags.append(hike)

    return flags


def _event_date(e: dict):
    try:
        return date.fromisoformat(e["date"])
    except (KeyError, TypeError, ValueError):
        return None


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

    vs_med = pct(current, med) if (current is not None and med) else None
    if p is not None and vs_med is not None:
        reason = (f"{ordinal(p)} percentile of the price band; "
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


def check_staleness(band: dict, ledger_summary: dict | None, cfg: dict):
    """Every live fetch is, by construction, current — there is no "stale
    tracker page" signal available from these sources' page text. The one
    place staleness genuinely applies: the band was WIDENED using the local
    ledger (a source went dark, or its band was too thin), and that ledger
    data is itself old. Returns hours-old, or None if nothing is stale.
    """
    if not (band.get("low_from_ledger") or band.get("high_from_ledger")):
        return None
    if not ledger_summary or not ledger_summary.get("last_seen"):
        return None
    try:
        seen = datetime.fromisoformat(ledger_summary["last_seen"])
    except ValueError:
        return None
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - seen).total_seconds() / 3600
    threshold = cfg.get("fetch", {}).get("stale_after_hours", 72)
    return round(age_hours, 1) if age_hours > threshold else None


def analyze(observations: list, cfg: dict, ledger_summary: dict | None = None,
            advertised_discount_pct: float | None = None) -> dict:
    band = build_band(observations, ledger_summary)
    confidence = grade_confidence(observations, band, cfg)
    flags = audit_dark_patterns(observations, band, cfg, advertised_discount_pct)
    verdict = decide(band, confidence, flags, cfg)
    stale_hours = check_staleness(band, ledger_summary, cfg)
    if stale_hours is not None:
        confidence["reasons"].append(f"ledger-derived band edge is {stale_hours:.0f}h old")
    return {"band": band, "confidence": confidence,
            "flags": flags, "verdict": verdict, "stale_hours": stale_hours}
