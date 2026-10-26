# SMC-R6-CR — Decision

**Milestone**: SMC-R6-CR
**Status**: COMPLETE
**Date**: 2026-08-27

---

## Decision

### A — R6 FAILURE VALID

The M4 failure is correctly attributable to the frozen cost/aggregation methodology. No implementation errors exist.

---

## Summary of Findings

| Audit Area | Finding | Status |
|------------|---------|:------:|
| Point/bps conversion | 2.0 pts / fill × 10,000 = correct bps | ✓ |
| Spread application | Round-trip (2×), correct | ✓ |
| Fill/spread interaction | Not double-counted | ✓ |
| Stop-cost treatment | Conservative approximation | ✓ |
| Daily aggregation | Matches R5 frozen spec | ✓ |
| Sample lineage | 196,965 → 134,310 → 123,386 → 1,555 | ✓ |
| OOS architecture | Frozen split, correct | ✓ |
| Statistical inference | Standard t-test on daily obs, valid | ✓ |
| Event independence | High intraday clustering, correctly aggregated | ✓ |
| Cost unit correctness | No error found | ✓ |

---

## Corrected Per-Trade Economics

| Metric | R4-CR Estimate | Verified Value | Source |
|--------|:--------------:|:--------------:|--------|
| Mean fill price | ~2,000 (assumed) | 2,451.55 | R4 ledger |
| Spread per side | 10.0 bps | 8.98 bps | Per-trade computation |
| Round-trip cost | 20.0 bps | 17.95 bps | Per-trade computation |
| Per-trade net | −19.0 bps | **−16.94 bps** | R4 ledger |
| Daily net (79 trades) | −1,505 bps | **−1,347 bps** | R6 output |

**The M4 failure margin is slightly smaller than R4-CR reported (17 bps per trade instead of 19), but the conclusion is identical: the gross edge (+1 bps) is overwhelmed by costs (~18 bps per trade × 79 trades/day).**

---

## Economic Arithmetic — Final Verification

```
Gross per-trade edge:     +1.01 bps
Spread cost per trade:    -17.95 bps (verified at mean fill 2,452)
Net per-trade:            -16.94 bps
Trades per day:           79.3
Daily Tier 2:             ~-1,343 bps ✓ (matches R6 report of -1,347)
Cost overwhelm ratio:     18x (spread cost / gross edge)
```

Even under the MOST favorable cost assumption (Tier 1: zero explicit cost, fill convention only):
```
Daily Tier 1:  +79.83 bps (positive but small)
```
This represents the raw structural edge at daily frequency. It IS positive, but the moment any realistic transaction cost is applied, the daily result becomes strongly negative because of the extreme trade frequency.

---

## Key Insight

The R6 failure is NOT about the cost assumption being too aggressive. It is about the **frequency-cost interaction**:

- The BOS+OB signal fires ~79 times per day
- Each firing costs ~18 bps in round-trip spread
- Total daily cost: ~1,400 bps
- Total daily gross edge: ~80 bps
- Net daily result: ~-1,320 bps

The edge is real (+1 bps per trade) but too small relative to the cost of expressing it at the observed frequency.

---

## M4 Status

> **M4 NOT QUALIFIED — CONFIRMED**

The frozen BOS+OB standalone hypothesis fails M4 qualification. This is a valid economic finding, not an implementation error.

---

## Implications

1. **BOS+OB structural edge exists** — this is a genuine scientific finding from the SMC programme.
2. **The edge is not economically deployable** at M1 frequency under realistic costs.
3. **Lower-frequency BOS+OB variants** (e.g., H4, D1) could potentially have fewer signals with larger per-trade edges, but this would require a new methodology and hypothesis.
4. **Module-level rescue** (adding filters, combining with other signals) is forbidden by the negative-result policy.

---

*End of SMC-R6-CR Decision*
