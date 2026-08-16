# Setup

There is nothing to install.

This skill is pure Python standard library by design — no `pip`, no virtualenv, no lockfile,
no build step. A price tool that needs a 400 MB dependency tree to divide two numbers has
lost the plot.

```bash
./scripts/setup.sh          # macOS / Linux
.\scripts\setup.ps1         # Windows (untested — see below)
```

Setup is a **preflight check**, not an installer. It verifies the four things this actually
depends on and then runs the golden tests.

---

## What it checks

| Check | Why it matters | If it fails |
|---|---|---|
| `python3` 3.9+ | The whole engine | Install Python 3.9 or newer |
| Jina Reader reachable | The fetch lane — every page read goes through it | See *Fetch lane down* below |
| `mcporter` on PATH | Exa search, which resolves a product name to tracker URLs | `npm i -g mcporter`; without it, only direct URLs work |
| `agent-reach doctor` → `exa_search: ok` | Confirms the search channel is live | Run `agent-reach doctor --json` and fix the reported channel |
| Golden tests pass | Proves the extractors still match the live sites | See *A source redesigned* below |

Expected output:

```
  python3                            OK — 3.13
  agent-reach web (Jina Reader)      OK — reachable
  mcporter                           OK — /usr/local/bin/mcporter
  agent-reach search (Exa)           OK — ok

  running golden tests…
  75 passed, 0 failed
```

---

## Troubleshooting

### Every band comes back empty, across all sources at once

**Check the `x-timeout` header first.** This is the single most fragile detail in the skill.

These tracker sites inject their price figures after page hydration. Called without a wait
header, the reader returns the pre-hydration shell — a valid HTTP 200, real page text, and
zero price fields. It looks like the sites removed their data. They did not.

Measured on `producthistory.in`, 2026-08-15:

| Call | Response | Price fields |
|---|---|---|
| no header | 2,256 bytes | **0** |
| `x-timeout: 25` | 4,135 bytes | Lowest, Average, Highest all present |

The header lives in `config/engine.json` → `fetch.headers`. Verify by hand:

```bash
curl -sS -H "x-timeout: 25" "https://r.jina.ai/https://pricehistory.app/p/<slug>" | grep -i lowest
```

### Fetch lane down

```bash
python3 scripts/ph.py --preflight
```

If `reader: false`, the Jina endpoint is unreachable or rate-limiting. It is a free public
service with no key, so throttling under heavy use is normal. Wait, then retry — the engine
already retries twice with backoff. Prior ledger entries still work while it is down.

### A source redesigned (golden tests fail)

Expected, eventually. The fixtures in `tests/fixtures/` are real pages captured on
2026-08-15; when a site changes its markup, the matching assertions fail. That failure is the
feature — it tells you the extractor is stale before a wrong number reaches a verdict.

To repair:

```bash
curl -sS -H "x-timeout: 25" "https://r.jina.ai/<the product URL>" \
  > tests/fixtures/<source>.md
```

Then update that source's extractor in `scripts/lib/parse.py` and the expected values in
`tests/test_golden.py`. Keep the assertions — do not delete a failing test to make it green.

### "Could not find this product on any tracked price-history site"

Either the product is genuinely untracked (new, niche, or a marketplace outside scope), or
Exa did not surface it. Try:

1. the exact Amazon.in URL rather than a product name
2. the bare ASIN
3. a shorter name — long names with many qualifiers search poorly

If it is genuinely untracked, NO-CALL is the correct answer, and the run still seeds the
ledger for next time.

### Only one source resolves

Normal for variant-heavy products. The identity gate deliberately drops pages for a different
variant (`141 ANC` is not `141 Gen 2`) rather than averaging two products into one meaningless
band. Fewer sources means LOW confidence and a withheld verdict — working as designed.

---

## Windows

`scripts/setup.ps1` is **untested** — no Windows machine was available when this shipped, and
saying so is more useful than implying coverage that was never verified. The macOS/Linux path
is the verified one.

The engine itself is plain stdlib Python and has no platform-specific code. Every check in the
PowerShell script can be run by hand if it misbehaves.

---

## Where files go

| Path | What | Committed? |
|---|---|---|
| `data/ledger.jsonl` | Your accumulated price observations | No — gitignored |
| `tests/fixtures/*.md` | Captured real pages for the golden tests | Yes |
| `config/engine.json` | Sources, thresholds, flag rules | Yes |

Nothing is written outside this folder.
