# SMC-R3 Controlled Amendment — Cost/Payoff and Stop/Payoff Resolution

**Date**: 2026-08-27
**Origin**: SMC-R3-CR identified two methodology issues requiring correction
**Status**: FROZEN — applies to SMC-R4 and beyond
**Authority**: SMC-R3-CR control review

---

## 1. Amendment A — Primary Economic Endpoint (RESOLVES BLOCKER)

### Problem

R3 measured forward return from the next-bar open (the fill price) but also deducted 4 points of spread cost. If the next-bar open IS the fill price, the spread is already embedded in the price. Deducting it again double-counts.

### Resolution

**Choose Option 2: Forward return from next-bar open, no additional cost deduction.**

The next-bar open is the fill price for the limit order. The spread is already reflected in the gap between the OB proximal edge and the next-bar open. No additional cost is deducted.

### Frozen Primary Metric

```
For bullish entry:
  Net forward return = (P_{T+120} - P_{T+1}) / P_{T+1} × 10,000 (bps)

For bearish entry:
  Net forward return = (P_{T+1} - P_{T+120}) / P_{T+1} × 10,000 (bps)

where:
  T+1 = the next bar after first-touch (the fill bar)
  P_{T+1} = open of the fill bar (the assumed fill price)
  P_{T+120} = close of the bar 120 bars after the fill bar
```

**No additional cost deduction.** The spread is embedded in the fill price.

### What This Means Economically

The test measures: "On average, does buying at the next-bar open after first touch produce positive forward return over 2 hours?"

This is a clean, interpretable economic question. The fill price already incorporates the spread.

### Stopped Events

If the stop is hit before T+120:

```
Net forward return = (OB.distal - P_{T+1}) / P_{T+1} × 10,000 (bps, negative)
```

The stop result replaces the full horizon return. No additional cost is applied to the stop result.

### Renamed Metric

The primary metric is now called:

> **Mean net forward return (bps)**

where "net" means "after accounting for the fill price" (not "after deducting explicit costs").

The name accurately describes what is computed.

---

## 2. Amendment B — Stop Role Clarification (RESOLVES CLARIFICATION)

### Problem

R3 described the stop as "not part of the primary payoff" (§8.2 note) but also explicitly used it to determine outcomes (§9.5). The stop simultaneously functions as:

1. A sample filter (stopped events have different outcomes)
2. An outcome component (stopped events contribute a fixed negative return)
3. A structural invalidation marker (STATE_VIOLATED)

### Resolution

**The stop IS part of the primary outcome measurement.**

The primary economic quantity is:

> Mean net forward return across ALL qualifying events, where stopped events contribute their stop-loss result and non-stopped events contribute their 120-bar forward return.

This is a **trade-payoff metric with structural stop**, not a pure forward return.

### Why This Is Coherent

The OB distal edge represents structural invalidation. If price closes beyond the OB, the continuation hypothesis is falsified for that event. The stop result is the economic consequence of that falsification.

Including stopped events in the mean is economically honest: it measures the average outcome of ALL BOS+OB signals, including failures.

### Removed Language

The following sentence from R3 §8.2 is **superseded** by this amendment:

> "Note: the actual R-multiple depends on the OB zone width, which varies across events. This is acceptable for the forward-return framework (Section 10)."

The forward-return framework is now defined by Amendment A. The stop is explicitly part of it.

---

## 3. Amendment C — Classification of Design Choices

### Problem

R3 classified all choices as "zero parameters" without distinguishing inherited definitions from new design selections.

### Resolution

The following reclassification applies:

| Choice | Original Classification | Corrected Classification |
|--------|:---:|:---:|
| Swing N = 5 | Inherited | **A — inherited** (correct) |
| MAX_WINDOW = 20 | "structural" | **C — researcher design choice** |
| Entry = OB proximal | Inherited | **A — inherited** (correct) |
| Fill = next-bar open | "structural" | **C — researcher design choice** |
| Stop = OB distal | Inherited | **A — inherited** (correct) |
| Horizon = 120 bars | "structural" | **C — researcher design choice** |
| Cost = 0 points (amended) | "frozen" | **N/A — removed by Amendment A** |
| HAC lag = 10 | "structural" | **C — researcher design choice** |
| OOS split = 2024-12-31 | "frozen" | **C — researcher design choice** |

### Corrected Statement

R3 §20 should read:

> The hypothesis has zero parameters **estimated from data**. However, six methodological choices (MAX_WINDOW, fill convention, horizon, HAC bandwidth, OOS split, and event association) are researcher design selections frozen before testing. These are legitimate but should be classified as design choices, not structural necessities.

---

## 4. Amendment D — OOS Split Role Clarification

### Problem

R3 implied the OOS split serves a validation role. In a zero-parameter hypothesis, there is nothing to fit in the discovery period.

### Resolution

The OOS split serves as **discipline preservation**, not OOS validation. Its purpose is:

1. To demonstrate that the hypothesis was frozen before any outcome examination.
2. To enable a secondary consistency check: if the effect exists, it should appear in both subperiods.
3. To establish the practice of chronological separation for future parameterized models.

The primary economic decision still uses the full dataset (zero parameters → no fitting → no need for separate OOS test).

---

## 5. Unchanged Components

The following R3 components are NOT amended:

- BOS definition (§4.2) ✓
- FVG definition (§4.3) ✓
- OB definition (§4.4) ✓
- Freshness state machine (§6) ✓
- One-event-per-BOS rule (§5.3) ✓
- Entry price = OB proximal edge (§7.1) ✓
- Stop = OB distal edge (§8.1) ✓
- Chronological split date (§14) ✓
- Alpha = 0.05 (§16.2) ✓
- Statistical test: one-sided t-test (§16.1) ✓
- HAC bandwidth = 10 (§15.5) ✓
- Dealing-range treatment (§11) ✓
- Inducement treatment (§12) ✓
- POI validation pillars (§13) ✓

---

## 6. Net Effect on SMC-R4

SMC-R4 will compute:

```
For each qualifying BOS+OB event:
  1. Identify first-touch bar
  2. Fill price = next bar open
  3. Forward return = (P_{fill+120} - fill_price) / fill_price × 10,000 bps
     OR if stop hit first:
     Forward return = (OB.distal - fill_price) / fill_price × 10,000 bps
  4. Primary metric: mean of all forward returns
  5. Statistical test: one-sided t-test, HAC bandwidth=10, alpha=0.05
```

No cost deduction. No additional parameters. No alternative horizons.

---

## 7. External API calls: 0 | New data acquired: 0 | Spend: $0.00

---

*This amendment resolves two SMC-R3-CR blockers. The corrected methodology is now internally coherent and ready for SMC-R4.*
