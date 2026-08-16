---
name: product-history
user-invocable: true
description: >-
  Check whether a product's advertised price or discount is actually good, by pulling its real
  price history from multiple independent trackers and auditing the offer for dark patterns
  named in India's CCPA Guidelines for Prevention and Regulation of Dark Patterns, 2023.
  Answers the question a sale banner is designed to stop you asking: is ₹1,499 a genuine floor,
  or the same price this has sat at with an invented MRP stapled on top? Returns the observed
  low / median / high price band, where today sits in that band as a percentile, a BUY / FAIR /
  WAIT / TRAP call with the trigger price that would change it, and named dark-pattern flags.
  Use for "/product-history", "is this a good price", "check the price history", "should I buy
  this now", "is this discount real", "is this sale genuine", "what's the lowest this has been",
  "40% off — is that legit", or any Amazon.in / Flipkart link pasted with buying intent.
  NOT a deal finder and NOT a price-drop alerter — it judges one product at one moment.
metadata:
  version: "1.0"
  author: gokulv
  created: "2026-08-15"
allowed-tools:
  - Bash
  - Read
  - mcp__visualize__read_me
  - mcp__visualize__show_widget
---

# product-history

Paste a product. Get back what it has actually cost over the last year, and whether the
offer in front of you is real.

> **`$SKILL` = the directory this `SKILL.md` file sits in.** Substitute that path when you run
> the command below. Never use a remembered absolute path — this skill is installed to a
> different location on every machine.

```bash
python3 "$SKILL/scripts/ph.py" "<amazon.in URL | flipkart URL | ASIN | product name>"
```

**First run ever?** → `scripts/setup.sh` (macOS/Linux) or `scripts\setup.ps1` (Windows).
There is nothing to install — it is a preflight check. See `SETUP.md`.

---

## The one thing this exists to catch

A banner says **40% off**. The tool asks a different question: *40% off what?*

Discounts are quoted against MRP, and MRP is a number the seller chooses. The only honest
denominator is what the product has actually sold for. When those two diverge by more than
25 percentage points, that gap is the manipulation — and it has a legal name.

---

## Run procedure

### Step 1 — Run the engine

```bash
python3 "$SKILL/scripts/ph.py" "<what the user pasted>"
```

Add `--discount 40` when the user quotes an advertised discount from a banner; it enables the
fake-sale check. Add `--json` when you need the payload for the widget.

Print the terminal table as-is. It is the deliverable and it is designed to stand alone.

### Step 2 — Render the widget

Then call `mcp__visualize__read_me` (module `chart`) followed by `mcp__visualize__show_widget`
to render the band as an interactive card. Build it from the `--json` payload:

- a band track from `band.low` to `band.high`, with a median tick and today's marker at
  `band.percentile`
- a price slider that recomputes the verdict live against `verdict.trigger_price` — this is
  the interactive part that matters, because it turns a verdict into a decision rule
- the `flags[]` list, each with its `ccpa_pattern`
- a footer naming the sources actually used

Keep the numbers identical to the terminal table. The widget is a second view of one
analysis, never a second analysis.

### Step 3 — Say the one-line answer

One sentence, plain: buy it, wait, or don't trust this banner — and at what price that flips.
Do not restate the table in prose.

---

## Reading the output

| Verdict | Means |
|---|---|
| **BUY** | Bottom quartile of the observed price band and within 5% of the all-time low |
| **FAIR** | Between the 25th and 60th percentile — reasonable, not the floor |
| **WAIT** | Above the 60th percentile. This price is worse than typical |
| **TRAP** | A dark pattern fired. Any flag downgrades the verdict one band; a flagged WAIT becomes TRAP |
| **NO-CALL** | Confidence too low. **This is a passing state, not an error** — see below |

| Confidence | Means |
|---|---|
| **HIGH** | 3+ sources agreeing within 5% |
| **MEDIUM** | 2 sources, or 3 with 5–15% spread |
| **LOW** | 1 source, a flat band, or >15% disagreement → **the verdict is withheld** |

**LOW withholds on purpose.** A price call that is confidently wrong is worse than no call,
because it launders a guess into a spending decision. When the tool says *"not enough data
to call it"*, report that plainly — do not fill the gap with your own estimate, and do not
soften it into a recommendation. The band and the flags are still shown; only the buy/wait
call is withheld.

The dark-pattern audit runs **independently of confidence**. A single source is enough to
prove an MRP is fictitious, even when it is not enough to call the price.

---

## Dark patterns detected

Each flag names the pattern from the CCPA Guidelines 2023 and shows the arithmetic that
fired it.

| Flag | CCPA pattern | Fires when |
|---|---|---|
| Fictitious MRP anchor | Bait and switch | Discount claimed off MRP exceeds discount off the real median by >25pp |
| Never-was price | Bait and switch | Claimed MRP is above the highest price ever observed |
| Fake sale | False urgency | An advertised "sale" price is at or above the observed median |
| Recycled discount | False urgency | The same "drop" price recurs 3+ times in 12 months |
| Pre-sale hike | False urgency | Price rose >5% within 30 days before the drop |
| Drip pricing | Drip pricing | Reported as **unverifiable** — cannot be seen before checkout |

Drip pricing is deliberately never asserted. The tool cannot see the checkout page, so it
says so rather than guessing.

---

## How it gets the data

The only network calls this skill makes are to agent-reach's two free, key-less channels —
no other host, no paid API, no browser:

| Lane | agent-reach channel | Called as |
|---|---|---|
| Resolve | `search` → Exa | `mcporter call 'exa.web_search_exa(...)'`, per `agent-reach/references/search.md` |
| Fetch | `web` → Jina Reader | `curl https://r.jina.ai/<url>`, per `agent-reach/references/web.md` |

Four independent trackers are triangulated: `pricehistory.app`, `pricediff.in`,
`pricehistoryapp.com`, `producthistory.in`. No API key, no login, no paid tier.

> **The one fragile detail.** The reader is called with an `x-timeout` header. Without it,
> every one of these sites returns its pre-hydration shell and all price fields come back
> empty. If bands suddenly go blank across all sources at once, check that header first
> (`config/engine.json` → `fetch.headers`).

### The ledger

Every run appends what it saw to `data/ledger.jsonl`, inside this folder. Trackers revise and
lose history; a local append-only file does not. Over time it widens the band beyond what any
site currently admits, and it is the fallback when a source goes dark. Nothing is written
anywhere else on the machine.

---

## Limits — state these, don't paper over them

- **Amazon.in and Flipkart** are well covered. Myntra and Ajio are partial. Croma, Reliance
  Digital and Tata CLiQ are thin across all four sources.
- **Variant-heavy fashion SKUs** (size, colour) have unstable identity across trackers. The
  identity gate drops mismatched variants rather than averaging them, which often means fewer
  sources and a LOW confidence result. That is correct behaviour.
- **Sale days are exactly when trackers lag.** Data older than 72h is stamped stale.
- **New or niche products have no history anywhere.** NO-CALL, and the ledger starts building.
- One product, one moment. Not a deal finder, not an alerter.
