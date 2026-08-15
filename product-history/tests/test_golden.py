#!/usr/bin/env python3
"""Golden-file tests. Run: python3 tests/test_golden.py

Fixtures in tests/fixtures/ are REAL pages captured 2026-08-15 through the
agent-reach reader lane. When a source redesigns its page, these tests fail —
that is the point. Re-capture the fixture, fix the parser, keep the assertions.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from lib.analyze import analyze  # noqa: E402
from lib.parse import parse  # noqa: E402
from lib.resolve import identify, same_product  # noqa: E402
from lib.util import load_config  # noqa: E402

FIX = os.path.join(HERE, "fixtures")
PASS, FAIL = [], []


def check(name, got, want):
    if got == want:
        PASS.append(name)
    else:
        FAIL.append(f"{name}: got {got!r}, want {want!r}")


def check_true(name, cond, detail=""):
    if cond:
        PASS.append(name)
    else:
        FAIL.append(f"{name}: {detail or 'condition false'}")


def load(fn):
    with open(os.path.join(FIX, fn), encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------- parsers
def test_pricehistory_app():
    o = parse("https://pricehistory.app/p/boat-airdopes-141-anc",
              load("pricehistory_app.md"))
    check("pricehistory_app.current", o.current, 1499.0)
    check("pricehistory_app.mrp", o.mrp, 5990.0)
    check("pricehistory_app.low", o.low, 1098.0)
    check("pricehistory_app.avg", o.avg, 1478.0)
    check("pricehistory_app.high", o.high, 1799.0)
    check_true("pricehistory_app.events", len(o.events) >= 10,
               f"only {len(o.events)} events")
    check_true("pricehistory_app.usable", o.usable)
    return o


def test_pricediff_in():
    o = parse("https://pricediff.in/product/b00n143bai-pigeon", load("pricediff_in.md"))
    check("pricediff.current", o.current, 2249.0)
    check("pricediff.low", o.low, 775.0)
    check("pricediff.high", o.high, 3445.0)
    check("pricediff.avg", o.avg, 2013.0)
    check("pricediff.checkpoints", o.checkpoints, 343)
    check("pricediff.tracking_since", o.tracking_since, "2024-12-28")
    check_true("pricediff.site_verdict", "above average" in (o.site_verdict or ""))


def test_pricehistoryapp_com():
    o = parse("https://pricehistoryapp.com/product/boat-airdopes-141-gen-2",
              load("pricehistoryapp_com.md"))
    check("pricehistoryapp.current", o.current, 799.0)
    check("pricehistoryapp.mrp", o.mrp, 3990.0)
    check("pricehistoryapp.low", o.low, 799.0)
    check("pricehistoryapp.high", o.high, 1099.0)
    check("pricehistoryapp.avg_window", o.avg_window, "30d")
    check_true("pricehistoryapp.window_note",
               any("30d" in n for n in o.notes), "missing down-weight note")


def test_producthistory_in():
    o = parse("https://producthistory.in/product/flipkart-boat-lunar",
              load("producthistory_in.md"))
    check("producthistory.current", o.current, 1499.0)
    check("producthistory.low", o.low, 1499.0)
    check_true("producthistory.flat_note",
               any("flat band" in n for n in o.notes), "missing flat-band note")


def test_unknown_source():
    check("unknown_source_returns_none",
          parse("https://example.com/whatever", "irrelevant"), None)


# ---------------------------------------------------------------- analysis
def test_dark_patterns_fire():
    """The boAt case. Advertised 75% off MRP; real median is ₹1,478."""
    cfg = load_config()
    o = test_pricehistory_app()
    res = analyze([o], cfg)

    names = {f["flag"] for f in res["flags"]}
    check_true("flag.fictitious_mrp", "Fictitious MRP anchor" in names,
               f"flags were {names}")
    check_true("flag.never_was", "Never-was price" in names,
               f"flags were {names}")
    check_true("flag.recycled_discount", "Recycled discount" in names,
               f"flags were {names}")

    # Every flag must cite its CCPA pattern and show the arithmetic.
    for f in res["flags"]:
        check_true(f"flag.cited[{f['flag']}]", bool(f.get("ccpa_pattern")))
        check_true(f"flag.detail[{f['flag']}]", len(f.get("detail", "")) > 30)


def test_single_source_withholds():
    """One source must NOT produce a buy/wait call. Refusing is a passing state."""
    cfg = load_config()
    o = test_pricehistory_app()
    res = analyze([o], cfg)
    check("single_source.confidence", res["confidence"]["level"], "LOW")
    check("single_source.verdict", res["verdict"]["verdict"], "NO-CALL")
    check_true("single_source.withholds", res["confidence"]["withholds"])
    # …but the audit still runs. Manipulation detection is independent of the call.
    check_true("single_source.flags_still_fire", len(res["flags"]) > 0)


def test_flat_band_is_low_confidence():
    cfg = load_config()
    o = parse("https://producthistory.in/product/flipkart-boat-lunar",
              load("producthistory_in.md"))
    res = analyze([o], cfg)
    check("flat_band.confidence", res["confidence"]["level"], "LOW")
    check("flat_band.verdict", res["verdict"]["verdict"], "NO-CALL")


def test_no_sources_does_not_crash():
    cfg = load_config()
    res = analyze([], cfg)
    check("empty.verdict", res["verdict"]["verdict"], "NO-CALL")
    check("empty.sources_used", res["band"]["sources_used"], 0)


def test_percentile_and_trigger():
    cfg = load_config()
    o = test_pricehistory_app()
    res = analyze([o], cfg)
    p = res["band"]["percentile"]
    # current 1499 in band 1098..1799 -> (1499-1098)/(1799-1098) = 57.2%
    check("percentile", p, 57.2)
    check_true("trigger_price_present",
               res["verdict"]["trigger_price"] is not None)


def test_same_date_events_do_not_crash():
    """Two drop events on the same date must not raise.

    Regression: _pre_sale_hike sorted (date, dict) tuples with a bare .sort(),
    so equal dates fell through to comparing dicts -> TypeError. Same-date
    drops are common, so this crashed on real products.
    """
    from lib.analyze import _pre_sale_hike

    rule = load_config()["dark_patterns"]["pre_sale_hike"]
    same_day = [
        {"date": "2026-07-08", "from": 1000.0, "to": 900.0},
        {"date": "2026-07-08", "from": 900.0, "to": 1000.0},
        {"date": "2026-07-08", "from": 950.0, "to": 800.0},
    ]
    try:
        _pre_sale_hike(same_day, rule)
        PASS.append("same_date_events.no_crash")
    except TypeError as e:
        FAIL.append(f"same_date_events.no_crash: raised TypeError: {e}")

    # Malformed / missing dates must be skipped, not fatal.
    junk = [{"date": None, "from": 1, "to": 2}, {"date": "not-a-date"},
            {"from": 5}, {"date": "2026-01-01", "from": 100.0, "to": 90.0}]
    try:
        _pre_sale_hike(junk, rule)
        PASS.append("malformed_events.no_crash")
    except Exception as e:  # noqa: BLE001
        FAIL.append(f"malformed_events.no_crash: raised {type(e).__name__}: {e}")


def test_variant_identity_gate():
    """Two variants of the same line must never be averaged into one band."""
    tgt = "boAt Airdopes 141 ANC wireless earbuds"
    keep, _ = same_product(tgt, "boAt Airdopes 141 ANC, Active Noise Cancellation(~32dB)")
    check_true("identity.keeps_exact_variant", keep)

    drop_gen2, why1 = same_product(tgt, "boAt Airdopes 141 Gen 2 Bluetooth Earbuds")
    check_true("identity.drops_gen2", not drop_gen2, why1)

    drop_pro, _ = same_product(tgt, "boAt Airdopes 311 Pro TWS")
    check_true("identity.drops_other_model", not drop_pro)

    drop_unrelated, _ = same_product(tgt, "Pigeon By Stovekraft Super Cooker")
    check_true("identity.drops_unrelated", not drop_unrelated)

    # No reference name (bare /dp/ASIN URL) => unjudgeable, must NOT drop.
    keep_unjudgeable, _ = same_product(None, "anything at all")
    check_true("identity.no_reference_keeps", keep_unjudgeable)


def test_asin_and_name_extraction():
    t = identify("https://www.amazon.in/boAt-Airdopes-141-Wireless-Earbuds/dp/B08ZN9F2Z3")
    check("identify.asin", t.asin, "B08ZN9F2Z3")
    check("identify.key", t.key, "asin:B08ZN9F2Z3")
    check_true("identify.name_from_slug", "Airdopes" in (t.name or ""),
               f"name was {t.name!r}")

    t2 = identify("B0CQKS8NPQ")
    check("identify.bare_asin", t2.asin, "B0CQKS8NPQ")

    t3 = identify("sony wh-1000xm5 headphones")
    check("identify.plain_name_no_asin", t3.asin, None)
    check_true("identify.plain_name_key", t3.key.startswith("name:"))


def main():
    for fn in (test_pricehistory_app, test_pricediff_in, test_pricehistoryapp_com,
               test_producthistory_in, test_unknown_source, test_dark_patterns_fire,
               test_single_source_withholds, test_flat_band_is_low_confidence,
               test_no_sources_does_not_crash, test_percentile_and_trigger,
               test_variant_identity_gate, test_asin_and_name_extraction,
               test_same_date_events_do_not_crash):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            FAIL.append(f"{fn.__name__} raised {type(e).__name__}: {e}")

    print(f"\n  {len(PASS)} passed, {len(FAIL)} failed\n")
    for f in FAIL:
        print(f"  FAIL  {f}")
    if not FAIL:
        print("  All golden assertions hold.\n")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
