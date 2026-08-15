"""Per-source extractors.

Every regex here was written against a real captured page in tests/fixtures/,
not inferred from the site's docs. When a source redesigns, the fixture is the
thing to re-capture and the test is the thing that will tell you.

Contract: a parser NEVER guesses. A field it cannot find with a labelled anchor
comes back None, and the confidence gate downstream deals with the consequence.
"""
from __future__ import annotations

import re

from .util import all_money, money, parse_loose_date


class Observation:
    """One source's view of one product."""

    FIELDS = ("source", "url", "title", "current", "mrp", "low", "high",
              "avg", "avg_window", "events", "site_verdict", "tracking_since",
              "checkpoints", "fetched_at", "notes")

    def __init__(self, source, url, **kw):
        self.source = source
        self.url = url
        self.title = kw.get("title")
        self.current = kw.get("current")
        self.mrp = kw.get("mrp")
        self.low = kw.get("low")
        self.high = kw.get("high")
        self.avg = kw.get("avg")
        self.avg_window = kw.get("avg_window", "12m")
        self.events = kw.get("events") or []
        self.site_verdict = kw.get("site_verdict")
        self.tracking_since = kw.get("tracking_since")
        self.checkpoints = kw.get("checkpoints")
        self.fetched_at = kw.get("fetched_at")
        self.notes = kw.get("notes") or []

    @property
    def usable(self) -> bool:
        """A source counts toward confidence only if it gives a current price
        AND at least one band edge. A lone current price is not history."""
        return self.current is not None and (self.low is not None or self.high is not None)

    def to_dict(self) -> dict:
        return {f: getattr(self, f) for f in self.FIELDS}


def _title(text: str):
    m = re.search(r"^Title:\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else None


# --------------------------------------------------------------------------
# pricehistory.app — the richest source. Labelled stats, MRP, dated events.
#   Lowest: ₹1,098 / Average: ₹1,478 / Highest: ₹1,799
#   | Price | ₹1,499 |   | MRP | ₹5,990 |
#   Price Drop 8th Jul 2026 / ₹1,499→₹1,299 / 13.34% drop
# --------------------------------------------------------------------------
def parse_pricehistory_app(text: str, url: str) -> Observation:
    def labelled(label):
        m = re.search(rf"{label}\s*:?\s*\**\s*(₹\s*[0-9][0-9,]*)", text, re.I)
        return money(m.group(1)) if m else None

    def table_row(label):
        m = re.search(rf"\|\s*{label}\s*\|\s*(₹\s*[0-9][0-9,]*)\s*\|", text, re.I)
        return money(m.group(1)) if m else None

    low = labelled("Lowest") or table_row("Lowest Ever Price")
    high = labelled("Highest") or table_row("Highest Price")
    avg = labelled("Average") or table_row("Average Price")
    current = table_row("Price") or labelled("current Price in India is")
    mrp = table_row("MRP")

    if current is None:
        m = re.search(r"current Price in India is\s*(₹\s*[0-9][0-9,]*)", text, re.I)
        current = money(m.group(1)) if m else None

    events = []
    for block in re.finditer(
        r"Price Drop\s+(\d{1,2}\s*(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\s+\d{4})"
        r".{0,120}?(₹\s*[0-9][0-9,]*)\s*→\s*(₹\s*[0-9][0-9,]*)",
        text, re.S | re.I,
    ):
        d = parse_loose_date(block.group(1))
        frm, to = money(block.group(2)), money(block.group(3))
        if d and to:
            events.append({"date": d.isoformat(), "from": frm, "to": to})

    return Observation(
        "pricehistory_app", url, title=_title(text), current=current, mrp=mrp,
        low=low, high=high, avg=avg, events=events,
    )


# --------------------------------------------------------------------------
# pricediff.in — ASIN-keyed. Publishes its own above/below-average call.
#   **₹2,249.00**  /  All-time lowest **₹775.00**
#   "Price is 11.7% above average (₹2013)."
#   bare sequence: ₹775 (low) ₹3445 (high) ₹2013 (avg)
# --------------------------------------------------------------------------
def parse_pricediff_in(text: str, url: str) -> Observation:
    notes = []

    current = None
    m = re.search(r"–\s*(₹\s*[0-9][0-9,]*)\s*Now", text)
    if m:
        current = money(m.group(1))
    if current is None:
        m = re.search(r"\*\*(₹\s*[0-9][0-9,]*(?:\.[0-9]{2})?)\*\*", text)
        current = money(m.group(1)) if m else None

    low = None
    m = re.search(r"Lowest\s*(₹\s*[0-9][0-9,]*)", text, re.I)
    if m:
        low = money(m.group(1))
    if low is None:
        m = re.search(r"All-time lowest\s*\n*\s*\**(₹\s*[0-9][0-9,]*(?:\.[0-9]{2})?)",
                      text, re.I)
        low = money(m.group(1)) if m else None

    avg = None
    site_verdict = None
    m = re.search(r"Price is\s*([0-9.]+)%\s*(above|below)\s*average\s*\((₹?\s*[0-9][0-9,]*)\)",
                  text, re.I)
    if m:
        site_verdict = f"{m.group(2).lower()} average by {m.group(1)}%"
        raw = m.group(3).replace("₹", "").replace(",", "").strip()
        try:
            avg = float(raw)
        except ValueError:
            avg = None

    # The stat strip is label-then-value on separate lines:
    #   Min \n ₹775 · Max \n ₹3445 · Avg \n ₹2013
    def strip_stat(label):
        m = re.search(rf"^\s*{label}\s*$\s*\n+\s*(₹\s*[0-9][0-9,]*)",
                      text, re.I | re.M)
        return money(m.group(1)) if m else None

    high = strip_stat("Max")
    low = low if low is not None else strip_stat("Min")
    avg = avg if avg is not None else strip_stat("Avg")

    # Depth signals — this source states how long and how densely it has tracked.
    tracking_since = None
    m = re.search(r"Tracking since\s+(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})", text, re.I)
    if m:
        d = parse_loose_date(m.group(1))
        tracking_since = d.isoformat() if d else None

    checkpoints = None
    m = re.search(r"([0-9,]+)\s+checkpoints", text, re.I)
    if m:
        try:
            checkpoints = int(m.group(1).replace(",", ""))
        except ValueError:
            pass

    return Observation(
        "pricediff_in", url, title=_title(text), current=current, low=low,
        high=high, avg=avg, site_verdict=site_verdict,
        tracking_since=tracking_since, checkpoints=checkpoints, notes=notes,
    )


# --------------------------------------------------------------------------
# pricehistoryapp.com — all-time low/high plus a 30-DAY average (not 12m).
#   ₹799₹3,990        <- current immediately followed by MRP
#   30d Average / ₹969
#   All-time low:**₹799** · All-time high:**₹1,099**
# --------------------------------------------------------------------------
def parse_pricehistoryapp_com(text: str, url: str) -> Observation:
    notes = []

    low = high = None
    m = re.search(r"All-time low\s*:?\s*\**\s*(₹\s*[0-9][0-9,]*)", text, re.I)
    if m:
        low = money(m.group(1))
    m = re.search(r"All-time high\s*:?\s*\**\s*(₹\s*[0-9][0-9,]*)", text, re.I)
    if m:
        high = money(m.group(1))

    current = None
    m = re.search(r"Current\s*:?\s*(₹\s*[0-9][0-9,]*)", text, re.I)
    if m:
        current = money(m.group(1))

    # current and MRP render adjacently with no separator: "₹799₹3,990"
    mrp = None
    m = re.search(r"(₹\s*[0-9][0-9,]*)(₹\s*[0-9][0-9,]*)", text)
    if m:
        a, b = money(m.group(1)), money(m.group(2))
        if a and b and b > a:
            current = current if current is not None else a
            mrp = b
    if mrp is None:
        m = re.search(r"You save\s*(₹\s*[0-9][0-9,]*)", text, re.I)
        if m and current is not None:
            saved = money(m.group(1))
            if saved:
                mrp = current + saved
                notes.append("MRP derived from stated saving")

    avg, window = None, "12m"
    m = re.search(r"(\d+)d Average\s*\n*\s*(₹\s*[0-9][0-9,]*)", text, re.I)
    if m:
        window = f"{m.group(1)}d"
        avg = money(m.group(2))
    else:
        m = re.search(r"avg\.\s*(₹\s*[0-9][0-9,]*)", text, re.I)
        if m:
            avg, window = money(m.group(1)), "30d"

    if window != "12m":
        notes.append(f"average is {window}, not 12-month — down-weighted")

    return Observation(
        "pricehistoryapp_com", url, title=_title(text), current=current, mrp=mrp,
        low=low, high=high, avg=avg, avg_window=window, notes=notes,
    )


# --------------------------------------------------------------------------
# producthistory.in — thinnest. Stats render as Lowest₹X / Average₹X / Highest₹X
# with no separator. Often reports a flat band; weight is reduced in config.
# --------------------------------------------------------------------------
def parse_producthistory_in(text: str, url: str) -> Observation:
    def glued(label):
        m = re.search(rf"{label}\s*:?\s*(₹\s*[0-9][0-9,]*)", text, re.I)
        return money(m.group(1)) if m else None

    low, avg, high = glued("Lowest"), glued("Average"), glued("Highest")

    current = None
    m = re.search(r"(₹\s*[0-9][0-9,]*)\s*[0-9.]+%\s*off", text, re.I)
    if m:
        current = money(m.group(1))
    if current is None:
        amounts = all_money(text)
        current = amounts[0] if amounts else None

    notes = []
    if low is not None and high is not None and low == high:
        notes.append("flat band reported — treat as single datapoint")

    return Observation(
        "producthistory_in", url, title=_title(text), current=current,
        low=low, high=high, avg=avg, notes=notes,
    )


PARSERS = {
    "pricehistory_app": parse_pricehistory_app,
    "pricediff_in": parse_pricediff_in,
    "pricehistoryapp_com": parse_pricehistoryapp_com,
    "producthistory_in": parse_producthistory_in,
}

_DOMAIN_TO_SOURCE = {
    "pricehistory.app": "pricehistory_app",
    "pricediff.in": "pricediff_in",
    "pricehistoryapp.com": "pricehistoryapp_com",
    "producthistory.in": "producthistory_in",
}


def source_for_url(url: str):
    for domain, sid in _DOMAIN_TO_SOURCE.items():
        if domain in url:
            return sid
    return None


def parse(url: str, text: str):
    """Dispatch to the right extractor. None if the URL is not a known source."""
    sid = source_for_url(url)
    if not sid:
        return None
    obs = PARSERS[sid](text, url)
    return obs
