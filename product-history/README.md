# product-history

**Is that 40% off real?** Paste a product link. Get back what it has actually cost over the
last year, and whether the offer in front of you is a genuine floor or a manufactured one.

Runs entirely on free, public sources. No API key, no login, no paid tier, no account.
Pure Python standard library — nothing to install.

---

## The problem

A discount is a fraction, and the seller picks the denominator.

Here is a real result from this tool, on a real listing:

```
  boAt Airdopes 141 ANC
  ──────────────────────────────────────────────────────────────
  12-MONTH BAND
    Lowest          ₹1,098
    Median          ₹1,478
    Highest         ₹1,799
    Today           ₹1,499   ← 57th percentile

    low  ──────────────────┼────────●─────────────────  high
                                    ▲  today
         ┼ = 12-month median

  DARK PATTERNS FOUND
    • Fictitious MRP anchor  [CCPA 2023: Bait and switch]
      Advertised 75% off a claimed MRP of ₹5,990, but actually
      1% ABOVE the real 12-month median of ₹1,478 — a 76pp gap
      between the discount claimed and the discount real.

    • Never-was price  [CCPA 2023: Bait and switch]
      Claimed MRP ₹5,990 exceeds the highest price ever observed
      (₹1,799). No source has seen it sold at MRP.

    • Recycled discount  [CCPA 2023: False urgency]
      ₹1,299 has been presented as a price drop 8 times
      (2024-08-06 … 2026-07-08) — a recurring price dressed as
      an event.
```

The listing advertises **75% off**. Measured against what the product has actually sold for,
today's price is **1% above** the median. The ₹5,990 MRP has never been observed anywhere —
it is an anchor, not a price. And the "drop" to ₹1,299 has been staged eight times in two
years.

Nothing here is an accusation of illegality; it is arithmetic. But the patterns have names,
and India's Central Consumer Protection Authority gave them those names in the
**Guidelines for Prevention and Regulation of Dark Patterns, 2023** — thirteen specified
patterns, issued under Section 18 of the Consumer Protection Act, 2019.

---

## Usage

```bash
python3 scripts/ph.py "https://www.amazon.in/dp/B0CQKS8NPQ"
python3 scripts/ph.py "sony wh-1000xm5"
python3 scripts/ph.py "B0CQKS8NPQ" --discount 40    # audit a banner's claim
python3 scripts/ph.py "<product>" --json            # machine-readable
python3 scripts/ph.py --preflight                   # is the fetch lane up?
```

Accepts an Amazon.in URL, a Flipkart URL, a bare ASIN, or a plain product name.

---

## What you get

| Verdict | Means |
|---|---|
| `BUY` | Bottom quartile of the band, within 5% of the all-time low |
| `FAIR` | 25th–60th percentile — reasonable, not the floor |
| `WAIT` | Above the 60th percentile. Worse than typical |
| `TRAP` | A dark pattern fired. Any flag downgrades the verdict one band |
| `NO-CALL` | Confidence too low — the call is withheld on purpose |

Every verdict carries a **trigger price**: the number that would flip it to BUY. You get a
decision rule, not a mood.

The band is drawn in the terminal, so the range is visible at a glance without any extra
tooling. Run from Claude Code, the same analysis also renders as an interactive card with a
price slider that recomputes the verdict live.

### NO-CALL is a feature

Free sources vary in quality, and some products are barely tracked. When fewer than two
sources agree, or the band is flat, or sources disagree by more than 15%, the tool prints the
band and the flags and then **refuses to make a buy call**.

A price verdict that is confidently wrong is worse than no verdict, because it launders a
guess into a spending decision. Refusing is a passing state here, not a failure.

The dark-pattern audit runs regardless. One source is enough to prove an MRP is fictitious,
even when it is not enough to judge the price.

---

## How it works

```
  input (URL / ASIN / name)
        │
        ▼
  resolve ──── agent-reach: Exa search ───→ the product's page on each tracker
        │
        ▼
  fetch ────── agent-reach: Jina Reader ──→ 4 pages, in parallel
        │
        ▼
  parse ────── one extractor per source, written against captured fixtures
        │
        ▼
  identity gate ─→ drop variant mismatches (141 ANC ≠ 141 Gen 2)
        │
        ▼
  triangulate ─→ band + percentile + confidence grade
        │
        ├─→ dark-pattern audit (CCPA 2023)
        ├─→ append to local ledger
        ▼
  verdict + trigger price
```

**Sources triangulated:** [pricehistory.app](https://pricehistory.app),
[pricediff.in](https://pricediff.in), [pricehistoryapp.com](https://pricehistoryapp.com),
[producthistory.in](https://producthistory.in).

**Disagreement is shown, never averaged away.** When sources conflict, the spread is printed
and the outlier is named. Quietly averaging two conflicting sources is the single most
dishonest thing a tool like this could do.

### The ledger

Every run appends what it saw to `data/ledger.jsonl` (gitignored, inside this folder).
Trackers revise and lose history; a local append-only file does not. After a few months it
widens the band beyond what any site currently admits, and it keeps working when a source
goes dark.

---

## Limits

Stated plainly, because a price tool that hides its blind spots is the problem it claims to solve.

- **Coverage:** Amazon.in and Flipkart are well covered. Myntra and Ajio partial. Croma,
  Reliance Digital and Tata CLiQ are thin across all four sources.
- **Fashion variants** (size, colour) have unstable identity across trackers. The identity
  gate drops mismatches rather than averaging them — usually meaning fewer sources and a
  NO-CALL. That is the correct trade.
- **Sale days are when trackers lag most.** Data older than 72h is stamped stale.
- **Single upstream dependency:** the Jina Reader endpoint. If it rate-limits, the ledger and
  any reachable source carry the run; if it is down entirely, so is the fetch lane.
- **Not a deal finder, not an alerter.** One product, one moment, one decision.

---

## Requirements

- Python 3.9+ (standard library only — no pip, no venv, no lockfile)
- [`agent-reach`](https://github.com/Panniantong/Agent-Reach) with its `web` and `search`
  channels healthy (`agent-reach doctor --json`)
- `mcporter` on PATH, for Exa search

```bash
./scripts/setup.sh      # macOS/Linux — preflight + golden tests
.\scripts\setup.ps1     # Windows (untested)
```

---

## Tests

```bash
python3 tests/test_golden.py
```

75 assertions against **real captured pages** in `tests/fixtures/`. When a source redesigns,
these fail — that is their job. Re-capture the fixture, fix the extractor, keep the assertions.

---

## Licence

MIT — see [LICENSE](LICENSE).

This tool reads public pages through a public reader service, at the volume of one person
making one purchase decision. It is not a monitoring service and not a resale product.
Nothing in its output is legal advice; the CCPA references identify pattern definitions, not
findings of violation.
