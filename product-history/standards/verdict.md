# Craft standard — what a trustworthy price verdict must contain

Bound at Cycle 0, before any build lane ran. This is the **craft axis**: not "did we fetch
data" (that's intent) but "is this verdict as good as the best version of this thing".

The failure mode this standard exists to prevent: **a confident-looking verdict built on one
thin source.** A price call that is wrong is worse than no price call, because it launders a
guess into a decision.

---

## The 10 components (each independently checkable, each located)

| # | Component | Passing bar |
|---|---|---|
| 1 | **Band before verdict** | The 12-month low / median / high appear *above* the recommendation. The reader sees the evidence before the conclusion, never after |
| 2 | **Percentile, not adjectives** | "68th percentile of the 12-month band" — never "quite high", "a decent price" |
| 3 | **Confidence is first-class** | Every verdict carries HIGH / MEDIUM / LOW and the source count that produced it. Never printed without it |
| 4 | **LOW withholds** | At LOW confidence the tool prints *"not enough data to call it"* and the raw band. It does **not** print BUY/WAIT. Refusing to answer is a passing state |
| 5 | **Every number is attributed** | Each figure carries its source domain and fetch timestamp. An unattributed number is a defect |
| 6 | **Disagreement is shown, not averaged away** | When sources conflict >15%, show the spread and name the outlier. Silently averaging conflicting sources is the single worst thing this tool could do |
| 7 | **Dark-pattern flags are named and cited** | Each flag names the CCPA 2023 pattern it maps to and states the arithmetic that fired it. No flag without its trigger shown |
| 8 | **MRP is treated as a claim, never a fact** | MRP is always rendered as "claimed MRP". The tool never computes "you save X" off MRP without also giving the saving off the real median |
| 9 | **Staleness is surfaced** | If the newest datapoint is >72h old, the verdict is stamped STALE. Sale-day data is exactly when trackers lag |
| 10 | **The counterfactual is stated** | Every verdict says what would change it: "at ₹1,180 this becomes BUY" — so the reader gets a trigger price, not just a mood |

**Threshold: 10/10 binary.** Nine is a fail. Each one of these is the difference between a
tool you can trust with money and a tool that reads well.

---

## Style reference for the output surface

- **Terminal first.** The verdict must be fully legible with the widget stripped out — the
  widget is an enhancement, never the carrier of a number that isn't also in the table.
- **Verdict word in the first line.** BUY / FAIR / WAIT / TRAP / NO-CALL.
- **Currency always ₹ with thousands separators.** Never bare integers.
- **No emoji as data.** A flag is a named string, not a 🚩 the reader must decode.
- **Max one screen.** If it doesn't fit in a terminal without scrolling, it's over-built.

---

## Anti-patterns (automatic fail)

| Anti-pattern | Why it fails |
|---|---|
| Inventing a median from a single datapoint | A band needs a range; one point is not a range |
| Reporting "% off" using only MRP | That is the manipulation being audited, reproduced by the auditor |
| Filling a gap with a model guess | The ledger and the sources are the only permitted origins of a number |
| A verdict with no trigger price | Leaves the reader with a mood, not a decision rule |
| Hiding which sources failed | A silent 403 looks identical to agreement |
