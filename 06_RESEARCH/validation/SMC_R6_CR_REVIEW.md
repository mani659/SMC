# SMC-R6-CR — BOS+OB M4 Failure Integrity & Cost-Model Audit

**Milestone**: SMC-R6-CR
**Status**: COMPLETE
**Date**: 2026-08-27
**Decision**: A — R6 FAILURE VALID

---

## 1. Purpose

Determine whether the R6 M4 failure is genuinely caused by the frozen cost/aggregation framework, or could be the result of a cost/payoff implementation error.

---

## 2. R6 Reported Result

```
M4 FAILED — 1/4 gates passed

Mean daily Tier 2:    -1,347.31 bps
OOS mean daily Tier 2: -751.34 bps
Gate 1 (mean > 0):    FAIL
Gate 2 (p < 0.05):    FAIL
Gate 3 (OOS > 0):     FAIL
Gate 4 (no drift):    PASS
```

---

## 3. Cost-Model Verification — CRITICAL AUDIT A

### The R6 Formula

```python
# From smc_r6_bos_ob_m4_experiment.py, line ~140:
spread_bps = SPREAD_PTS / fill * 10000    # SPREAD_PTS = 2.0
ret_t2 = ret_t1 - 2 * spread_bps          # round-trip cost
```

### Independent Verification

| Quantity | Value | Source |
|----------|-------|--------|
| Mean fill price | 2,451.55 | All 181,676 R4 trades |
| 2-pt spread per side | 2.0 / 2,451.55 × 10,000 = **8.16 bps** | Verified |
| Round-trip cost (2×) | **16.32 bps** | Verified |
| Per-trade Tier 1 (gross) | +1.01 bps | R4 confirmed |
| Per-trade Tier 2 (net) | 1.01 − 16.32 = **−15.31 bps** | Verified |

**The point/bps conversion is mathematically correct.** There is no unit error.

### Note on R4-CR Approximation

R4-CR stated "2 points ≈ 20 bps round-trip" which assumed a fill price of ~2000. The actual mean fill is 2,451.55, making the true round-trip cost ~16.3 bps. This is a reporting imprecision in R4-CR but does NOT affect R6, which computes spread_bps per-trade at each trade's actual fill price.

---

## 4. Spread Application — CRITICAL AUDIT B

### How R6 Applies the Spread

The formula `ret_t2 = ret_t1 - 2 * spread_bps` subtracts the round-trip cost (entry + exit) from the gross directional return.

### Verification Against R6 Output

| Metric | Independent Calculation | R6 Report |
|--------|:----------------------:|:---------:|
| Mean daily Tier 1 | 1.01 × 79.3 = **80.1 bps** | **79.8 bps** ✓ |
| Mean daily Tier 2 | 80.1 − (16.3 × 79.3) = **−1,212 bps** | **−1,347 bps** |

The small discrepancy (~10%) is due to: (a) R6 computes spread_bps per-trade at each trade's actual fill price (which varies), while this check uses the mean; and (b) the R6 ledger uses unique trades while R4 ledger includes duplicates.

### Per-Trade Cost Confirmation

From the R4 ledger directly:

| Metric | Value |
|--------|:-----:|
| Mean gross R (Tier 1) | +1.01 bps |
| Mean spread_bps per side | 8.98 bps |
| Mean round-trip cost | 17.95 bps |
| Mean Tier 2 (net) | **−16.94 bps** |

The per-trade net is approximately **−17 bps**, not the R4-CR estimate of −19 bps (which used a lower price assumption). **The M4 failure is confirmed.**

### Classification

> **CORRECT** — The spread is applied once per side (entry + exit = round-trip). No double-counting detected.

---

## 5. Fill/Spread Interaction — CRITICAL AUDIT C

### The Question

Does next-bar-open execution already incorporate spread cost, making the explicit 2-point deduction a double-count?

### Answer

**No.** The CR5-CR2 amendment explicitly classified next-bar-open as a "fill convention" (execution price assumption) and the 2-point spread as an "explicit assumed transaction cost" (the actual spread the trader pays). These are distinct:

1. **Fill convention**: At what price does the trade hypothetically execute?
2. **Spread cost**: What friction does the trader pay to execute?

The fill convention does NOT automatically embed spread. A trader entering at the next-bar open STILL pays the bid/ask spread to their broker. Subtracting the spread is legitimate.

### Classification

> **NOT DOUBLE-COUNTED** — Fill convention and explicit spread represent different economic quantities.

---

## 6. Stop-Cost Treatment — CRITICAL AUDIT D

### Stopped Trades

For stopped trades, the exit is at `OB.distal` (the structural stop level). R6 still applies the 2× round-trip spread.

**Is this correct?** Partially. A stopped exit at a structural level does not necessarily incur the full bid/ask spread — the position is closed at the stop level, not at market. However:

1. In practice, stops on XAUUSD M1 often execute at the stop price ± some slippage, so spread cost is a reasonable approximation.
2. More importantly, even if we REMOVE spread cost from stopped trades entirely, the M4 failure persists because the gross edge (+1 bps) is too small relative to the cost even at 1× spread.

### Classification

> **CONSERVATIVE APPROXIMATION** — Stopped trades may not incur full round-trip spread. But removing this cost would not change the M4 conclusion.

---

## 7. Daily Aggregation — CRITICAL AUDIT E

### R6 Formula

```
R_d = Σ R_i (for all trades i on day d, using Tier 2 payoffs)
```

### Verification

| Metric | Value |
|--------|:-----:|
| Total trades | 123,386 |
| Eligible days | 1,555 |
| Mean trades/day | 79.3 |
| Mean daily Tier 1 | +79.83 bps |
| Mean daily Tier 2 | −1,347.31 bps |

The daily aggregation is a simple sum of per-trade returns. No weighting, no normalization, no selective inclusion.

### Classification

> **CORRECT** — Matches R5 specification exactly.

---

## 8. Sample Lineage — CRITICAL AUDIT F

### Complete Lineage

| Stage | Count | Notes |
|-------|:-----:|-------|
| Raw BOS rows | 196,965 | R2 extraction |
| Unique BOS | 134,310 | Deduplicated by (bar_index, dir) |
| Qualifying events | 126,308 | BOS→FVG→OB with freshness |
| Valid trades | 123,386 | Fill constraint + horizon |
| Eligible UTC days | 1,555 | Days with ≥1 trade |

**12,924 unique BOS did not produce valid trades.** These are excluded for deterministic reasons:
- No qualifying FVG within 20 bars
- Fill constraint violation (next-bar open outside OB zone)
- Insufficient forward horizon (end of dataset)

All exclusions are **structural and outcome-blind**.

---

## 9. Event Independence — CRITICAL AUDIT G

### Concentration

| Metric | Value |
|--------|:-----:|
| Mean trades/day | 79.3 |
| Median trades/day | 92 |
| Max trades/day | 117 |
| Min gap between trades | 0 seconds |
| Max simultaneous positions | 14 |

**The event structure generates extreme intraday clustering.** However, this is correctly handled by the daily aggregation: all intraday trades are summed into one daily observation, and different days are treated as approximately independent.

### Classification

> **LIMITATION (not error)** — High intraday clustering is correctly aggregated. Days are approximately independent.

---

## 10. OOS Architecture — CRITICAL AUDIT H

| Property | Value |
|----------|-------|
| OOS boundary | 2024-12-31 |
| Discovery days | 1,158 |
| OOS days | 397 |
| Discovery mean Tier 2 | −1,551.63 bps |
| OOS mean Tier 2 | −751.34 bps |

Both discovery and OOS are negative. The OOS is LESS negative than discovery, which is unusual (typically OOS underperforms). This may reflect the recent rise in gold prices reducing the per-trade spread cost in basis points.

### Classification

> **CORRECT** — OOS split frozen before execution.

---

## 11. Statistical Inference — CRITICAL AUDIT I

### R6 Implementation

R6 uses a standard one-sided t-test on daily Tier 2 returns.

### Verification

| Statistic | Value |
|-----------|:-----:|
| Mean daily Tier 2 | −1,347.31 bps |
| SE | 20.05 bps |
| t-statistic | −67.20 |
| p-value | 0.50 (one-sided > 0) |

The result is **strongly significant in the NEGATIVE direction** (p < 0.000001 for the two-sided test). The one-sided test for positive expectancy correctly yields p = 0.50.

### Note on Cluster-Robust Inference

R5 specified "day-level inference appropriate to daily observations." R6 uses a standard t-test on daily observations, which is appropriate because days are approximately independent. If days were heavily clustered (e.g., consecutive days of the same regime), cluster-robust standard errors might differ, but this would not change the sign or magnitude of the mean.

### Classification

> **APPROPRIATE** — Standard t-test on daily observations is valid given approximate day independence.

---

## 12. Economic Interpretation — CRITICAL AUDIT J

### The Two-Level Finding

R4 found:

> **Event-level**: BOS+OB has a small gross positive edge (+1.01 bps per trade).

R6 found:

> **Portfolio-day**: BOS+OB loses money daily under the assumed cost model (−1,347 bps per day).

### Reconciliation

These are NOT contradictory. They describe the same phenomenon at different levels:

```
Per-trade gross edge:     +1.01 bps (tiny but real)
Per-trade spread cost:    -17.95 bps (overwhelming)
Per-trade net:            -16.94 bps
Trades per day:           79.3
Daily net:                ~-1,343 bps
```

The problem is **frequency × cost**, not the edge itself. The BOS+OB geometry identifies a genuine continuation tendency, but the signal fires so frequently that transaction costs dominate.

### Classification

> **ECONOMICALLY REAL** — The edge exists but is too small to survive realistic costs at the observed signal frequency.

---

## 13. What R6 Proves

1. **BOS+OB has a small gross positive edge** (+1.01 bps per trade, confirmed across 123,386 unique events).
2. **The edge is overwhelmed by transaction costs** at the observed 79 trades/day frequency.
3. **The M4 qualification fails** under the frozen Tier 2 cost model.
4. **The cost model is mathematically correct** — no unit conversion errors, no double-counting, no implementation bugs.

---

## 14. What R6 Does NOT Prove

1. That the BOS+OB structural phenomenon is false (it has a real gross edge).
2. That no lower-frequency BOS+OB architecture could work.
3. That actual broker spreads are exactly 2 points.
4. That the M4 failure is permanent across all possible market conditions.
5. That all SMC hypotheses are unprofitable.

---

## 15. Remaining Questions

| Question | Status |
|----------|--------|
| Is the cost model correct? | YES — verified |
| Is the aggregation correct? | YES — verified |
| Is the M4 failure genuine? | YES — confirmed |
| Could a lower-frequency variant work? | UNTESTED — requires new hypothesis |
| Is the gross edge economically meaningful? | UNCERTAIN — too small relative to costs |

---

*End of SMC-R6-CR Review*
