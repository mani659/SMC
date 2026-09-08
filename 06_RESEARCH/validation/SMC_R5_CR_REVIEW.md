# SMC-R5-CR — M4 Qualification Methodology Control Review

**Date**: 2026-08-27
**Milestone**: SMC-R5-CR
**Status**: COMPLETE
**Classification**: Control review — methodology integrity audit

---

## 1. Executive Summary

SMC-R5-CR audits whether R5 genuinely validates the same BOS+OB economic candidate or has unintentionally changed the economic estimand.

**Decision: B — R5 VALID WITH CONTROLLED AMENDMENT**

The day-clustering idea is economically defensible and addresses the R4-CR dependence limitation. However, R5 makes three changes that require explicit acknowledgment:

1. **Estimand change**: from per-trade to per-day expectancy
2. **New cost assumption**: 2-point spread is a researcher assumption, not observed
3. **New qualification criteria**: "both directions > 0" and "≥4/5 years" are new requirements

None of these invalidate R5, but they must be honestly classified before R6 execution.

---

## 2. Critical Audit A — Estimand Change

### R4 Estimand

$$E[R_{trade}] = \text{mean payoff per individual BOS+OB trade}$$

### R5 Estimand

$$E[R_d] = E\left[\frac{1}{n_d}\sum_{i=1}^{n_d} R_{trade,i}\right] = \text{mean of daily average payoffs}$$

### Comparison

| Property | R4 | R5 |
|----------|:---:|:---:|
| Unit of observation | Individual trade | Trading day |
| N (approximate) | 123,386 | ~1,555 |
| Handles within-day dependence | No (HAC insufficient) | Yes (cluster-robust) |
| Tests | "Is each trade positive on average?" | "Is each day positive on average?" |
| Economic question | Per-trade edge | Per-day portfolio edge |

### Assessment

**R5 changes the estimand.** This is a meaningful change, not merely a statistical correction.

However, the change is **economically defensible**:

- R4-CR established that many trades within a day are NOT independent economic opportunities
- The per-day estimand is more relevant for portfolio-level decision-making
- A trader cares about whether their account makes money each day

### Classification

> **ESTIMAND CHANGE — DELIBERATE AND DOCUMENTED**

R5 explicitly declares this redefinition in §3. It is not hidden. But it must be acknowledged that R5 tests a different quantity than R4.

---

## 3. Critical Audit B — Day Aggregation Rationale

### R5 Claim

> "One UTC trading day = one economic event."

### Assessment

**Partially justified, partially arbitrary.**

**Justified aspects:**
- Different days start with fresh market structure (overnight gaps)
- Intraday correlation is high (79 trades/day share context)
- Day boundaries create natural independence breaks

**Arbitrary aspects:**
- UTC midnight is NOT economically meaningful for XAUUSD
- London session spans midnight UTC
- A day with 1 trade and a day with 100 trades are not equivalent opportunities
- The exact boundary doesn't matter for statistical validity, but it does affect which trades cluster together

### Classification

> **DETERMINISTIC BUT PARTIALLY ARBITRARY — acceptable as clustering device**

---

## 4. Critical Audit C — Cluster-Robust vs HAC

### R5 Claim

> "HAC is insufficient; cluster-robust day inference is required."

### Assessment

**Correct.** HAC with bandwidth=10 only captures 10-bar serial correlation. Trades within a day can be highly correlated across the full day (e.g., 79 trades sharing the same intraday trend). Cluster-robust standard errors correctly account for ALL within-day correlation.

### Alternative Considered

Event-level data + cluster-robust SE (without aggregation) would preserve the original R4 estimand while fixing the inference. This is statistically valid but was not selected.

### Classification

> **CLUSTER-ROBUST IS CORRECT for the day-level estimand**

---

## 5. Critical Audit D — 2-Point Spread

### R5 Claim

> "spread = 2.0 points (conservative XAUUSD M1 ECN average)"

### Origin

The 2-point spread is a **RESEARCHER ASSUMPTION**. It is:
- NOT observed in the canonical dataset (m1_clean.csv has no bid/ask)
- NOT inherited from R1/R2/R3
- NOT empirically verified from the user's broker data
- A reasonable estimate for XAUUSD M1 ECN, but an assumption nonetheless

### Assessment

The spread assumption is reasonable but should be classified honestly:

| Classification | Description |
|:---:|-------------|
| NOT observed | No bid/ask in dataset |
| NOT inherited | Not from R1/R2/R3 |
| RESEARCHER ASSUMPTION | Frozen before R6 execution |
| REASONABLE | Consistent with typical XAUUSD M1 ECN spreads |

### Classification

> **RESEARCHER ASSUMPTION — frozen, reasonable, but not observed**

---

## 6. Critical Audit E — Cost Tier Reporting

### R5 Architecture

| Tier | Description | Role |
|:----:|-------------|------|
| 1 | Fill convention only | Descriptive (R4 baseline) |
| **2** | **+ 2-point spread** | **PRIMARY decision criterion** |
| 3 | + 2-point spread + 1-point slippage | Stress test |

### Assessment

The three-tier architecture is honest and transparent. The primary decision uses Tier 2, which is a reasonable middle ground.

**Risk**: The existence of three tiers creates a researcher degree of freedom to choose the favorable tier. R5 specifies Tier 2 as primary, which mitigates this risk.

### Classification

> **COST TIERS ARE COHERENT — Tier 2 as primary is defensible**

---

## 7. Critical Audit F — Cost Double-Counting

### The Issue

R4 uses next-bar-open as the fill price. R5 adds 2 points of explicit spread. Is the spread already in the next-bar-open gap?

### Analysis

The gap between OB.proximal and next-bar open includes:
1. Bid/ask spread (part of the gap)
2. Market movement between first-touch bar close and next-bar open
3. Any gap at the bar boundary

The spread is ONLY PART of the gap. Adding 2 points of explicit spread is NOT double-counting — it's adding a specific cost component that may or may not already be in the gap.

However, we don't know how much of the gap IS the spread. The 2-point assumption may overstate or understate the actual additional cost.

### Classification

> **NOT DOUBLE-COUNTING — but the relationship between fill-convention gap and explicit spread is uncertain**

---

## 8. Critical Audit G — Stop Costs

### R5 Specification

```
Exit (stop): OB.distal - spread_cost
```

### Assessment

Stop exits DO have a cost deduction. But the stop fill is at OB.distal (a structural level), not at a market price. Deducting spread from OB.distal assumes the stop would fill at OB.distal minus spread, which may not be accurate.

For a stop triggered by wick penetration, the actual fill could be:
- At OB.distal (if the wick exactly touches)
- Worse than OB.distal (if the market gaps through)
- Better than OB.distal (if the wick reverses)

The spread deduction is a reasonable approximation but not precise.

### Classification

> **APPROXIMATE — stop cost treatment is reasonable but not exact**

---

## 9. Critical Audit H — UTC Day Boundary

### Assessment

UTC midnight is:
- **Deterministic**: reproducible, no ambiguity
- **Arbitrary**: not aligned with XAUUSD market sessions
- **Acceptable**: as a clustering device, the exact boundary doesn't matter for statistical validity
- **Not economically justified**: London session spans midnight UTC

### Classification

> **DETERMINISTIC AND ARBITRARY — acceptable as clustering device, not economically meaningful**

---

## 10. Critical Audit I — Overlapping Positions

### Assessment

R4-CR found up to 14 simultaneous positions. R5 aggregates by day.

Within a day, simultaneous positions are:
- NOT separate economic bets (they share the same market context)
- Repeated expressions of the same directional move
- Correctly treated as dependent observations

Day aggregation correctly handles this by treating all within-day trades as one opportunity.

### Classification

> **DAY AGGREGATION CORRECTLY ADDRESSES OVERLAP**

---

## 11. Critical Audit J — Position Weighting

### R5 Approach

Equal weighting: each day contributes equally regardless of trade count.

### Assessment

A day with 1 trade and a day with 100 trades receive equal statistical weight.

**Arguments for equal weighting:**
- Each day is one independent opportunity
- Trade count is endogenous (more BOS events ≠ more opportunities)
- No parameter to estimate

**Arguments against:**
- A day with 100 trades may contain more economic information
- Equal weighting underweights high-activity days

### Classification

> **EQUAL WEIGHTING IS A DESIGN CHOICE — defensible but not the only option**

---

## 12. Critical Audit K — Qualification Criteria

### Criterion 4: "Both long and short daily means > 0"

**This is a NEW requirement not present in R4.** R4 tested whether the OVERALL mean was positive. R5 requires both directions to be positive.

This changes the hypothesis from:
> "BOS+OB continuation is positive overall"

to:
> "BOS+OB continuation is positive in both directions"

### Classification

> **NEW RESEARCHER REQUIREMENT — justified if economic mechanism should work both ways, but a new condition**

### Criterion 5: "Positive in at least 4 of 5 years"

**This was created AFTER seeing R4 results** (which showed positive in all 6 years). This is a POST-HOC criterion.

However, it's not unreasonable — yearly stability is a common robustness check. The issue is timing: it was defined after seeing the results.

### Classification

> **POST-HOC CRITERION — defensible but should be acknowledged as created after R4**

---

## 13. Critical Audit L — OOS Architecture

### Assessment

R5 retains the fixed 2024-12-31 split. For a zero-parameter model, this is sufficient. Walk-forward is unnecessary.

The OOS serves as discipline preservation and temporal stability evidence.

### Classification

> **OOS ARCHITECTURE IS APPROPRIATE**

---

## 14. Critical Audit M — M3 → M4 Definition

### Assessment

R5 tests whether the BOS+OB economic module survives stricter qualification. It does NOT turn BOS+OB into a different strategy.

The estimand changes from per-trade to per-day, but the underlying economic mechanism (BOS → FVG → OB → first touch → continuation) is preserved.

### Classification

> **M4 QUALIFIES THE SAME ECONOMIC MODULE — estimand change is a statistical correction, not an economic redefinition**

---

## 15. Critical Audit N — Researcher Degrees of Freedom

| Choice | Value | Classification |
|--------|-------|:---:|
| Day aggregation | UTC day | Design choice (deterministic, partially arbitrary) |
| Cluster-robust | Day-level | Necessary structural consequence |
| 2-point spread | 2.0 pts | Researcher assumption (frozen, reasonable) |
| 1-point slippage | 1.0 pt | Researcher assumption (frozen, reasonable) |
| ≥4/5 years | 4 of 5 | Post-hoc (created after R4 results) |
| Both directions > 0 | Yes | New researcher requirement |
| OOS split | 2024-12-31 | Inherited from R3 |
| Tier 2 primary | Spread only | Deliberate qualification design |
| Equal day weighting | Yes | Design choice |
| No parameters | Zero | Inherited from R3 |

### Assessment

Two items require explicit acknowledgment:
1. "≥4/5 years" is post-hoc
2. "Both directions > 0" is new

Neither invalidates R5, but both should be classified honestly.

### Classification

> **TWO POST-HOC/NEW CRITERIA — should be acknowledged but do not block R6**

---

## 16. Decision

**B — R5 VALID WITH CONTROLLED AMENDMENT**

The day-clustering architecture is economically defensible and addresses the R4-CR dependence limitation. However, three amendments are required:

### Amendment 1: Estimand Acknowledgment

Add explicit statement:

> "R5 tests the per-day aggregate expectancy, which is a different quantity than R4's per-trade expectancy. The per-day estimand is more relevant for portfolio-level decision-making but represents a deliberate change from R4."

### Amendment 2: Cost Assumption Classification

Change spread classification from "Conservative XAUUSD M1 ECN average" to:

> "Researcher assumption: 2.0 points. Frozen before R6 execution. Not directly observed from canonical dataset."

### Amendment 3: Qualification Criteria Classification

Add explicit statement:

> "Criterion 4 (both directions > 0) is a new requirement not present in R4. Criterion 5 (≥4/5 years) was defined after R4 results. Both are defensible but should be acknowledged as additions to the original hypothesis."

---

## 17. What Does NOT Change

- Day-level clustering architecture: PRESERVED
- Cluster-robust inference: PRESERVED
- Three-tier cost reporting: PRESERVED
- Tier 2 as primary: PRESERVED
- Deduplication requirement: PRESERVED
- Entry/stop/horizon conventions: PRESERVED
- Zero-parameter principle: PRESERVED
- OOS split: PRESERVED

---

## 18. External API calls: 0 | New data acquired: 0 | Spend: $0.00

---

*SMC-R5-CR is a control review milestone. No experiments were run. No backtests were performed. No parameters were changed.*
