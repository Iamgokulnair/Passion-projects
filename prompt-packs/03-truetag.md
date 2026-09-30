# 03 - TrueTag (product-history)

Paste a product link, learn whether the discount is real. Six prompts.

---

### Prompt 1 - Frame the question the banner hides

```
Build a Claude Code skill called product-history for Indian e-commerce (Amazon.in,
Flipkart). Input: a product URL, ASIN or name. The question it answers: is this price a
genuine floor, or an invented MRP stapled on top?

Hard rules:
- Free, public sources only. No API key, no login, no paid tier.
- Pure Python standard library. Nothing to install.
- A confidently wrong verdict is worse than none. When evidence is thin, refuse to call it.

It is not a deal finder and not a price-drop alerter. It judges one product at one moment.
```

---

### Prompt 2 - The standard before the build

```
Write standards/verdict.md: 10 binary components a trustworthy price verdict must meet.
Include: price band shown before the verdict; percentile, never adjectives; confidence on
every verdict with the source count; LOW confidence withholds the call; every number
attributed to a source and timestamp; disagreement shown, never averaged away; each dark
pattern named and its arithmetic shown; MRP always treated as a claim; stale data stamped;
and a trigger price that would change the verdict. 10 of 10 or it fails.
```

**Check:** read each component and ask whether you could test it against one output. If not, rewrite it.

---

### Prompt 3 - Fetch from several trackers

```
Write scripts/lib/fetch.py and resolve.py. Resolve a product name or link to candidate
price-tracker pages using a free web-search channel, then read each page as text. Keep
each tracker as a separate source - never merge them before analysis. Record source domain
and fetch time for every figure.
```

**Check:** one product returns figures from more than one tracker, each tagged with its source.

---

### Prompt 4 - Band, confidence, verdict

```
Write scripts/lib/analyze.py. Compute low / median / high and today's percentile.
Confidence: HIGH = 3+ sources within 5%; MEDIUM = 2 sources, or 3 with 5-15% spread;
LOW = 1 source, a flat band, or >15% disagreement. Verdicts: BUY (bottom quartile and
within 5% of the low), FAIR (25th-60th), WAIT (above 60th), NO-CALL at LOW confidence.
Always state the trigger price that flips the verdict.
```

---

### Prompt 5 - Dark-pattern audit, named in law

```
Add the dark-pattern audit, mapped to India's CCPA Guidelines for Prevention and
Regulation of Dark Patterns, 2023. Flags: fictitious MRP anchor (claimed discount beats the
real discount by >25pp), never-was price (MRP above the highest observed), fake sale,
recycled discount (same drop 3+ times in 12 months), pre-sale hike (>5% rise in the 30
days before the drop). Any flag downgrades the verdict one band; a flagged WAIT becomes
TRAP. Drip pricing is always reported as unverifiable, because we can't see checkout.
The audit runs even at LOW confidence.
```

**Check:** feed a listing with an inflated MRP and confirm the flag fires with its arithmetic shown.

---

### Prompt 6 - Golden tests and the output

```
Write tests/test_golden.py with saved fixtures so the verdict logic is tested offline.
Make scripts/ph.py print a single-screen terminal table: verdict word on the first line,
rupees with thousands separators, no emoji as data. Add --discount to enable the fake-sale
check and --json for a widget payload. Write SKILL.md, README (with a real, unedited
example output, including the lines that don't flatter it) and SETUP.md.
```

**Check:** tests pass offline, and a one-source product returns NO-CALL instead of a guess.
