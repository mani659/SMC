# SMC-R5 — BOS+OB M4 Module Qualification Methodology

**Date**: 2026-08-27
**Milestone**: SMC-R5
**Status**: COMPLETE
**Classification**: Methodology design — M4 qualification framework

---

## 1. Executive Summary

SMC-R5 designs the M4 qualification framework for BOS+OB. The framework addresses the three material limitations identified in R4-CR:

1. Duplicate BOS entries (sample inflation)
2. Extreme trade frequency (event-level dependence)
3. Incomplete cost model

The methodology freezes a **day-level clustering architecture** with **cluster-robust inference** and **explicit cost sensitivity analysis**.

---

## 2. M4 Objective

Freeze one qualification framework answering:

> Does the BOS+OB economic event remain economically positive after correcting event lineage, accounting for economically meaningful dependence/clustering, enforcing strict chronological OOS validation, and representing execution costs honestly?

M4 is NOT improvement. M4 is validation.

---

## 3. Economic Independence Definition

### The Problem

R4 found 123,386 unique trades with 79 trades/day and up to 14 overlapping. Many trades share the same market context.

### The Resolution

**One economically independent opportunity = one trading day's worth of BOS+OB activity.**

Rationale:

- BOS events within a single trading day arise from the same intraday price structure
- Multiple BOS signals during one day represent repeated exposures to the same market move
- A new independent opportunity begins when the next trading day opens with fresh market structure
- Daily clustering is the natural economic unit for intraday trading on XAUUSD

### Formal Definition

```
ECONOMIC EVENT = all BOS+OB trades within a single UTC trading day

One economic event produces:
  - multiple raw trades (typically 50-120 per day)
  - one aggregated daily return (weighted by trade count)

Independence:
  - different days = independent economic events
  - same day = dependent observations from one opportunity
```

### Why Not Other Clustering Rules?

| Alternative | Problem |
|-------------|---------|
| Same-bar clustering | Too granular; still leaves hundreds of daily events |
| Same-impulse clustering | Requires impulse definition (adds subjectivity) |
| Non-overlapping only | Discards valid information from overlapping trades |
| Hourly blocks | Arbitrary; doesn't match economic structure |

Day-level clustering is the most natural and least discretionary.

---

## 4. Event Aggregation

### Within-Day Aggregation

For each trading day, aggregate all BOS+OB trades into one economic event:

```
Daily return = mean of all directional returns on that day
             = (sum of all trade returns) / (number of trades that day)
```

This is an equal-weighted daily average. Each trade within the day contributes equally to the daily return.

### Why Equal Weight?

- No parameter to estimate (trade-size weighting would require position sizing, which is outside M4 scope)
- Equal weight is the simplest unbiased aggregation
- Trade-level weighting can be explored in M5 (execution validation)

---

## 5. Deduplication

### Mandatory Pre-Processing

Before event extraction, deduplicate the BOS CSV:

```
For each unique (bar_index, dir):
  keep only one row
  if multiple rows with same bar_index and dir:
    keep the first chronologically
    discard duplicates
```

This addresses the R2 extraction issue that caused 32% sample inflation in R4.

### Expected Impact

- Unique BOS events: ~134,310 (down from 196,965)
- Unique trades: ~123,386 (unchanged — duplicates were exact copies)
- Mean R: unchanged (+1.01 bps)
- Daily event count: unchanged (duplicates were within-day)

---

## 6. Dependence Framework

### Primary: Cluster-Robust Inference

Use **cluster-robust standard errors** at the day level.

```
For each day d:
  R_d = mean of all trade returns on day d
  n_d = number of trades on day d

Primary test:
  H0: E[R_d] <= 0
  H1: E[R_d] > 0

Test statistic:
  t = mean(R_d) / SE_cluster
  where SE_cluster uses cluster-robust variance estimator
  with clusters = trading days
```

### Why Cluster-Robust Instead of HAC?

| Method | Handles | Limitation |
|--------|---------|------------|
| HAC (R4) | Serial correlation | Does NOT handle within-day clustering |
| Cluster-robust | Within-cluster dependence | Assumes between-cluster independence |
| Event-level aggregation | Full information loss | Discards trade-level detail |

Cluster-robust is the correct method when:
- Observations are clustered (trades within days)
- Clusters are approximately independent (different days)
- Within-cluster correlation is high (79 trades/day share context)

### Implementation

```
from statsmodels.stats.sandwich_covariance import cov_cluster

# For each day, compute mean return
daily_returns = [mean of trades on day d for each day d]
day_counts = [number of trades on day d for each day d]

# Cluster-robust SE
# Using the day-level aggregated returns with trade-count weighting
```

### Fallback

If cluster-robust implementation is not straightforward, use **block bootstrap** at the day level:

```
1. Resample days with replacement
2. For each resampled day, include ALL trades from that day
3. Compute mean return across resampled days
4. Repeat 10,000 times
5. p-value = fraction of bootstrap samples with mean <= 0
```

---

## 7. Cost Model

### Three-Tier Cost Architecture

SMC-R5 defines three cost levels for honest reporting:

#### Tier 1 — Fill Convention Only (R4 baseline)

```
Entry: next-bar open after first-touch detection
Exit: stop at OB.distal or close at fill+120 bars
No explicit cost deduction
Label: "Gross return under conservative fill convention"
```

This is what R4 reported. It is NOT fully cost-adjusted.

#### Tier 2 — Explicit Spread

```
Entry: next-bar open + spread_cost
  where spread_cost = spread / entry_price * 10,000 bps
  spread = 2.0 points (conservative XAUUSD M1 average)

Exit (non-stop): close at fill+120 - spread_cost
Exit (stop): OB.distal - spread_cost

Label: "Net return after explicit spread"
```

#### Tier 3 — Spread + Slippage

```
Entry: next-bar open + spread_cost + slippage_cost
  where slippage_cost = 1.0 point / entry_price * 10,000 bps

Exit: same as Tier 2

Label: "Net return after spread + slippage"
```

### Cost Parameters (Frozen)

| Parameter | Value | Source |
|-----------|-------|--------|
| Spread | 2.0 points | Conservative XAUUSD M1 ECN average |
| Slippage | 1.0 point | Conservative limit-order slippage |
| Commission | $0 | Embedded in spread assumption |
| Exit spread | Same as entry | Round-trip cost model |

### Reporting Requirement

SMC-R4/SMC-R6 must report ALL THREE tiers:

1. Gross (fill convention only)
2. Net after spread
3. Net after spread + slippage

The primary decision uses **Tier 2 (net after spread)** as the baseline.

### Why Tier 2 as Primary?

- Tier 1 understates costs (implicit only)
- Tier 3 may overstate costs for limit orders
- Tier 2 is the honest middle ground: explicit spread, conservative but not punitive

---

## 8. Entry Convention

### Preserved from R3/CR2

```
Entry = next-bar open after first-touch detection
Fill constraint: next-bar open must reach OB.proximal
```

### Rationale for Preservation

- The fill convention is conservative (biased against trader)
- Changing the entry convention would be an optimization, not validation
- M4 tests the existing hypothesis, not a modified one

### Limitation (Documented)

The next-bar-open fill is NOT identical to a real limit order at OB.proximal. A real limit order would fill at OB.proximal if touched, which is typically better for the trader.

This means M4 results are **conservative relative to real execution**.

---

## 9. Stop Logic

### Preserved from CR2

```
Stop = OB.distal edge
Trigger: wick penetration (bar.low <= distal for long)
Fill: OB.distal (exact level)
```

### No Modification

- No buffer added
- No stop optimization
- No alternative stop definitions

---

## 10. Intrabar Limitation

### Documented as Execution Uncertainty

M1 OHLC cannot determine:
- Exact sequence of prices within a bar
- Whether stop was hit before or after other events
- Gap behavior at bar boundaries

### Treatment

- Stop uses wick-based trigger (most conservative M1 convention)
- This may overstate stop-outs (a wick touch doesn't guarantee fill at the exact level)
- The overstatement is conservative (biased against the trader)

### Label

> "Execution uncertainty due to M1 OHLC resolution. Wick-based stop trigger is the most conservative M1 convention."

---

## 11. Primary Payoff

### Preserved from CR2

```
If stopped: R = (OB.distal - fill) / fill * 10,000 bps
If not stopped: R = (P_exit - fill) / fill * 10,000 bps [long]
```

### Applied at Three Cost Tiers

The payoff is computed for each trade, then:
1. Aggregated to daily level (mean of all trades that day)
2. Tested at day level with cluster-robust inference
3. Reported at all three cost tiers

---

## 12. Chronological Validation

### Architecture: Fixed Split with Yearly Consistency Check

```
Discovery: 2021-04-12 to 2024-12-31 (~3.75 years)
OOS: 2025-01-01 to 2026-04-10 (~1.25 years)
```

### Why Fixed Split?

- BOS+OB has zero estimated parameters
- No fitting occurs in the discovery period
- The split serves as discipline preservation, not parameter validation
- Walk-forward is unnecessary for a zero-parameter structural rule

### Yearly Consistency (Descriptive)

Report mean return for each calendar year. This is descriptive stability evidence, not a formal acceptance criterion.

---

## 13. Parameter Policy

### Zero Parameters Estimated from Data

All quantities are frozen:

| Quantity | Value | Classification |
|----------|-------|:---:|
| Swing N | 5 | Inherited |
| MAX_WINDOW | 20 | Design choice |
| Entry | Next-bar open | Design choice |
| Stop | OB.distal | Inherited |
| Horizon | 120 bars | Design choice |
| Spread | 2.0 points | Frozen assumption |
| Slippage | 1.0 point | Frozen assumption |
| HAC/Cluster | Day-level | Design choice |
| OOS split | 2024-12-31 | Design choice |

**No fitting occurs during M4 execution.**

---

## 14. Qualification Criteria

### M4 Qualification Requires ALL of:

| Criterion | Requirement |
|-----------|-------------|
| 1. Day-level positive expectancy | Mean daily return > 0 after spread costs |
| 2. Statistical significance | Cluster-robust p < 0.05 (one-sided) |
| 3. OOS consistency | OOS mean daily return > 0 |
| 4. Directional consistency | Both long and short daily means > 0 |
| 5. Yearly stability | Positive in at least 4 of 5 years |
| 6. No methodology drift | Implementation matches frozen R3/CR2 |
| 7. Cost robustness | Positive after explicit spread (Tier 2) |

### What M4 Does NOT Require

- Sharpe ratio threshold
- Maximum drawdown limit
- Minimum trade count
- Minimum bps threshold
- Profit factor threshold
- Any parameter optimization

---

## 15. M4 Decision Classes

### A — M4 QUALIFIED

All 7 criteria met.

> BOS+OB becomes a validated M4 economic module.

### B — M4 CONDITIONAL

6 of 7 criteria met. One narrowly defined issue remains.

> M4 requires one controlled amendment before qualification.

### C — M4 NOT QUALIFIED

Fewer than 6 criteria met.

> Standalone BOS+OB hypothesis fails M4 validation.

---

## 16. Forward/Demo Testing Role

### Not Part of M4

M4 is historical validation only.

### Future Role

If M4 qualifies, forward/demo testing may be used for:

> **Execution validation** — confirming that the historical result translates to current market conditions.

It must NOT be used to:

> Wait for a favorable sequence.

---

## 17. Module Role

### Not Formalized in M4

After M4 qualification, BOS+OB may potentially become:

> **Trend-continuation specialist module**

But this role is formalized only after:
1. M4 qualification
2. Module interaction hypothesis (separate milestone)
3. Combined OOS validation (separate milestone)

---

## 18. Negative Result Policy

If M4 fails:

```
BOS+OB
  -> M3 (conditional)
  -> M4 validation
  -> FAIL
```

Response:

> Archive the standalone economic hypothesis.

Do NOT rescue with filters.
Do NOT search combinations.

---

## 19. Comparison of M4 Architectures

### Architecture A — Event-Level (R4 approach)

| Dimension | Score |
|-----------|:---:|
| Economic independence | 2 — violates independence |
| Statistical validity | 3 — HAC insufficient |
| Information preservation | 5 — full detail |
| Reproducibility | 5 — deterministic |
| Simplicity | 5 — straightforward |
| Implementation | 5 — already done |

### Architecture B — Day-Level Clustering (Selected)

| Dimension | Score |
|-----------|:---:|
| Economic independence | 5 — days are independent |
| Statistical validity | 5 — cluster-robust correct |
| Information preservation | 4 — aggregates within day |
| Reproducibility | 5 — deterministic |
| Simplicity | 4 — requires daily aggregation |
| Implementation | 4 — new code needed |

### Architecture C — Non-Overlapping Only

| Dimension | Score |
|-----------|:---:|
| Economic independence | 4 — no overlap |
| Statistical validity | 4 — reduced dependence |
| Information preservation | 2 — discards many trades |
| Reproducibility | 5 — deterministic |
| Simplicity | 4 — straightforward |
| Implementation | 4 — new code needed |

### Architecture D — Hourly Blocks

| Dimension | Score |
|-----------|:---:|
| Economic independence | 3 — arbitrary boundary |
| Statistical validity | 4 — reduced dependence |
| Information preservation | 4 — moderate aggregation |
| Reproducibility | 5 — deterministic |
| Simplicity | 3 — requires hourly alignment |
| Implementation | 3 — complex |

**Selected: Architecture B — Day-Level Clustering**

---

## 20. Required Outputs for SMC-R6

SMC-R6 will need:

```
1. Deduplicated BOS CSV
2. BOS->FVG->OB event extraction (same as R4)
3. Trade simulation (same as R4)
4. Daily aggregation
5. Cluster-robust inference
6. Three-tier cost reporting
7. Qualification checklist evaluation
```

---

## 21. External API calls: 0 | New data acquired: 0 | Spend: $0.00

---

*SMC-R5 is a methodology-design milestone. No experiments were run. No backtests were performed. No parameters were changed.*
