# SMC-R5-CR2 — Final M4 Qualification Adjudication

**Date**: 2026-08-27
**Milestone**: SMC-R5-CR2
**Status**: COMPLETE
**Classification**: Final control review before R6

---

## 1. Executive Summary

SMC-R5-CR2 determines whether R5 can be frozen as a legitimate M4 qualification framework without converting post-R4 observations into retroactive acceptance criteria.

**Decision: A — M4 VALID — R6 READY**

After removing two post-hoc criteria from formal acceptance, the amended R5 framework is scientifically legitimate. R6 can execute a clean, predeclared M4 qualification test.

---

## 2. The Central Problem

R5 introduced two qualification criteria AFTER observing R4 results:

| Criterion | Origin | Problem |
|-----------|--------|---------|
| Both directions > 0 | Post-R4 | Not ex-ante |
| Positive in ≥4/5 years | Post-R4 | Not ex-ante |

These must be removed from formal acceptance gates. They can remain as descriptive diagnostics.

---

## 3. Critical Issue A — R4 vs R5 Estimand

### R4 Estimand

$$E[R_{trade}] = \text{mean payoff per individual BOS+OB trade}$$

### R5 Estimand

$$E[R_{day}] = E\left[\frac{1}{n_d}\sum_{i=1}^{n_d} R_{trade,i}\right] = \text{mean of daily average payoffs}$$

### Assessment

These ARE different quantities. R5 does not merely "correct" R4's inference — it changes what is being tested.

**However, the change is economically justified for M4 module qualification:**

- M4 qualifies a MODULE for possible future bot architecture
- A module operates in the context of a portfolio, not as individual trades
- The relevant question for a module is: "Does running this daily produce positive expected value?"
- Day aggregation answers this directly

**M4 should qualify the per-day estimand, not the per-trade estimand.**

The per-trade estimand (R4) established that the BOS+OB event has positive economic value. The per-day estimand (R5) establishes whether that value survives realistic portfolio-level aggregation with proper dependence treatment.

---

## 4. Critical Issue B — Economic Unit

### The Chosen Unit

**One UTC trading day = one economic observation.**

### Rationale

- Different days start with fresh market structure (overnight gaps)
- Intraday correlation is high (79 trades/day share context)
- A module running daily cares about daily outcomes, not individual trades
- Day boundaries are deterministic and reproducible

### Limitation

UTC midnight is not economically meaningful for XAUUSD. But as a clustering device, the exact boundary doesn't matter for statistical validity.

---

## 5. Critical Issue C — Post-Hoc Direction Criterion

### Original R5

> Criterion 4: Both long and short daily means > 0 (mandatory gate)

### Finding

This was introduced AFTER observing that R4's long (+1.31 bps) and short (+0.69 bps) were both positive. It is NOT ex-ante.

### Resolution

**Remove from formal acceptance. Move to descriptive diagnostics.**

The primary hypothesis is:
> "BOS+OB continuation produces positive mean daily return overall."

Directional consistency is useful interpretive information but should NOT be a formal acceptance gate for this experiment.

If directional asymmetry is important, it should be tested in a separate, ex-ante methodology.

### Classification

> **POST-HOC — REMOVED FROM FORMAL ACCEPTANCE**

---

## 6. Critical Issue D — Post-Hoc Yearly Criterion

### Original R5

> Criterion 5: Positive in at least 4 of 5 years (mandatory gate)

### Finding

This was defined AFTER R4 showed positive in all 6 years. It is NOT ex-ante.

### Resolution

**Remove from formal acceptance. Move to descriptive diagnostics.**

Yearly consistency is valuable descriptive evidence. But a criterion defined after seeing the results cannot serve as a formal acceptance gate for the same experiment.

If temporal stability is important, it should be tested in a separate, ex-ante methodology.

### Classification

> **POST-HOC — REMOVED FROM FORMAL ACCEPTANCE**

---

## 7. Critical Issue E — What Should M4 Qualify?

### Selected Definition

> **M4 qualifies: BOS+OB is a sufficiently reliable economic module whose daily aggregate payoff is positive under the frozen methodology.**

This is Definition 2 from the prompt:
> "BOS+OB creates positive expectancy for a portfolio operating the signal continuously."

### Why Definition 2?

- M4 qualifies a MODULE for possible bot architecture
- A bot operates continuously, not trade-by-trade
- Daily aggregate payoff is the relevant quantity for portfolio evaluation
- This aligns with the day-aggregation architecture

### What M4 Does NOT Qualify

- Individual trade profitability (that's R4)
- Directional consistency (that's descriptive)
- Yearly stability (that's descriptive)
- Strategy optimization (that's forbidden)

---

## 8. Critical Issue F — Cost Assumption

### Classification

> **2.0-point spread = RESEARCHER ASSUMPTION**

Not observed in the canonical dataset. Reasonable for XAUUSD M1 ECN, but an assumption.

### Treatment

- Frozen before R6 execution
- Used as the primary cost tier (Tier 2)
- Labeled honestly in all reports
- Does NOT constitute "observed transaction costs"
- The result is "cost-validated under assumed spread," not "fully cost-adjusted"

### Permissible for M4?

**Yes.** M4 can use frozen assumptions for qualification. The assumption must be labeled honestly and the result interpreted accordingly.

---

## 9. Critical Issue G — Three Cost Tiers

### Formal Role

| Tier | Role |
|:----:|------|
| 1 | Descriptive (R4 baseline) |
| **2** | **PRIMARY acceptance criterion** |
| 3 | Stress test / sensitivity |

### Rule

**Only Tier 2 determines M4 qualification.**

Tier 1 and Tier 3 are reported for interpretation but cannot override the Tier 2 decision.

The future R6 report must NOT allow the reader to choose the favorable tier. The decision is Tier 2, period.

---

## 10. Critical Issue H — Cost/Payoff Consistency

### Tier 2 Formula

```
Entry: next-bar open + spread_cost
  spread_cost = 2.0 / entry_price * 10,000 bps

Exit (non-stop): close at fill+120 - spread_cost
Exit (stop): OB.distal - spread_cost
```

### Verification

- Spread applied symmetrically to entry and exit ✓
- No double-counting (next-bar-open gap ≠ spread) ✓
- Stop exit includes cost deduction ✓
- Formula is internally consistent ✓

### Classification

> **COST/PAYOFF CONSISTENT**

---

## 11. Critical Issue I — Dependence

### Selected Architecture

**Day-level aggregation + ordinary inference on daily means.**

### Rationale

- Simpler than event-level + cluster-robust
- Equally valid for the module qualification question
- Directly answers: "Does running BOS+OB daily produce positive value?"
- Day means are approximately independent (different days = fresh structure)

### Alternative Considered

Event-level observations + day-clustered inference would preserve more information. But it requires cluster-robust SE, which is more complex and not necessary for this zero-parameter qualification.

---

## 12. Critical Issue J — Information Loss

### Assessment

Day aggregation gives equal weight to a 1-trade day and a 100-trade day.

### Justification

- Each day is one independent opportunity for the module
- Trade count is endogenous (more BOS events ≠ more opportunities)
- Equal weighting avoids parameterizing the trade-count relationship
- For module qualification, the question is "does the daily portfolio make money?" not "does each individual trade make money?"

### Classification

> **EQUAL WEIGHTING IS APPROPRIATE for module qualification**

---

## 13. Critical Issue K — Overlapping Positions

### Treatment

Aggregate all concurrent positions into the daily return. This is consistent with the day-aggregation architecture.

Multiple simultaneous positions are ONE exposure to the same market move, counted once in the daily return.

---

## 14. Critical Issue L — OOS

### Architecture

Fixed chronological split: 2024-12-31.

### Justification

- Zero parameters estimated from data
- No fitting occurs
- Walk-forward is unnecessary
- Fixed split demonstrates temporal persistence

---

## 15. Critical Issue M — Acceptance Criteria

### Final Primary Criteria (4 gates)

| # | Criterion | Type |
|:-:|-----------|:----:|
| 1 | Positive mean daily return under Tier 2 | Primary |
| 2 | Cluster-robust p < 0.05 (one-sided) | Primary |
| 3 | Positive OOS mean daily return | Primary |
| 4 | No methodology drift (matches R3/CR2) | Primary |

### Secondary Descriptive (reported, not gates)

| # | Diagnostic |
|:-:|-----------|
| 5 | Long vs short breakdown |
| 6 | Yearly breakdown |
| 7 | Tier 1 and Tier 3 results |
| 8 | Event count and cluster count |
| 9 | Stopped vs non-stopped breakdown |

### Removed from Formal Acceptance

| # | Criterion | Reason |
|:-:|-----------|--------|
| ~~4~~ | ~~Both directions > 0~~ | Post-hoc |
| ~~5~~ | ~~Positive in ≥4/5 years~~ | Post-hoc |

---

## 16. M3 → M4 Boundary

| Level | Definition | Status |
|:-----:|-----------|:------:|
| M3 | Positive standalone event expectancy | ESTABLISHED (R4) |
| M4 | Sufficiently reliable daily module | PENDING (R6) |

M4 does NOT require:
- Optimization
- Filters
- Directional consistency
- Yearly stability
- Sharpe threshold
- Drawdown limit

M4 requires ONLY:
- Positive daily expectancy under Tier 2
- Appropriate inference
- Temporal persistence
- No methodology drift

---

## 17. R6 Execution Framework

R6 will:

1. Deduplicate BOS entries
2. Extract BOS→FVG→OB events (same as R4)
3. Simulate trades (same as R4)
4. Aggregate to daily returns
5. Compute mean daily return under Tier 2
6. Compute cluster-robust SE
7. Compute p-value
8. Compute OOS mean daily return
9. Report all three cost tiers
10. Evaluate 4 primary criteria

R6 will NOT:
- Add filters
- Optimize
- Test alternate clustering
- Test alternate costs
- Test alternate horizons
- Combine modules
- Build EA

---

## 18. External API calls: 0 | New data acquired: 0 | Spend: $0.00

---

*SMC-R5-CR2 is a final control review. No experiments were run. No backtests were performed. No parameters were changed.*
