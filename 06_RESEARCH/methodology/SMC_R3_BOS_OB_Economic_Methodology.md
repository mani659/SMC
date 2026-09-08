# SMC-R3 — BOS + Order Block Continuation Economic Methodology

**Date**: 2026-08-27
**Milestone**: SMC-R3
**Status**: COMPLETE
**Classification**: Methodology freeze — no implementation

---

## 1. Executive Summary

SMC-R3 freezes one standalone economic hypothesis: **does the precisely defined BOS + fresh OB/FVG continuation event produce positive forward expectancy on XAUUSD after realistic transaction costs?**

The methodology is fully deterministic, parameter-free at the hypothesis level, and frozen before any empirical testing.

**Decision: METHODOLOGY FROZEN — READY FOR SMC-R4 EMPIRICAL EXECUTION**

---

## 2. Research Question

Freeze:

> **Does the BOS + first-mitigated OB continuation event produce positive mean forward return (in basis points) on XAUUSD M1 after realistic transaction costs?**

The null hypothesis is:

> H₀: μ ≤ 0 (mean forward return ≤ 0)

The alternative is:

> H₁: μ > 0 (mean forward return > 0)

The test is one-sided because the economic hypothesis predicts directional continuation.

---

## 3. Event Chain Definition

The complete, deterministic event chain is:

```
Step 1:  Confirmed swing (N=5 confirmation)
Step 2:  BOS — close beyond confirmed swing (directional break)
Step 3:  Displacement — strong move away from break
Step 4:  FVG — 3-candle imbalance gap within the displacement
Step 5:  OB — candle immediately preceding the FVG (color irrelevant)
Step 6:  Price returns and touches the OB zone
Step 7:  Entry at the OB proximal edge (direction = BOS direction)
Step 8:  Forward return measured over fixed horizon
Step 9:  Outcome classified
```

Every step is deterministic and causally identified.

---

## 4. Structural Definitions (Frozen)

### 4.1 Swing Definition

```
Swing High: candle whose high > both N candles before and N candles after
Swing Low:  candle whose low  < both N candles before and N candles after
N = 5 (M1 detection parameter)
```

**Confirmation**: a swing is confirmed only when N bars after it have been observed.
A swing cannot be used before its confirmation timestamp.

### 4.2 BOS Definition

```
Bullish BOS: candle close > last confirmed swing high
Bearish BOS: candle close < last confirmed swing low
```

**Timestamp**: the bar close that confirms the break.
BOS is NOT recognized until the closing price confirms the structural break.
No future information used.

### 4.3 FVG Definition

```
Bullish FVG: candle[i+2].low > candle[i].high
  Gap upper = candle[i+2].low
  Gap lower = candle[i].high
  Direction: bullish (price moved up through the gap)

Bearish FVG: candle[i+2].high < candle[i].low
  Gap upper = candle[i].high
  Gap lower = candle[i+2].low
  Direction: bullish (price moved down through the gap)
```

**Confirmation**: candle[i+2] close.

### 4.4 OB Definition

```
OB = candle at index (fvg_bar_index - 3) for the selected FVG
  i.e., the candle immediately preceding the FIRST candle of the 3-candle FVG pattern

Zone:
  Full wick:  [OB.low, OB.high]
  Body only:  [min(OB.open, OB.close), max(OB.open, OB.close)]

Direction: inherited from FVG
Color: irrelevant (per 07_PROVEN_KNOWLEDGE)
```

**Default zone**: full wick [OB.low, OB.high] (conservative test).
The body-only zone is a secondary descriptor only.

### 4.5 Displacement Qualification

A FVG is considered displacement if it is **associated with a BOS event**.

The association rule is:

```
FVG displacement qualifying:
  1. FVG direction = BOS direction (same direction)
  2. FVG creation timestamp ≥ BOS timestamp (FVG occurs during or after BOS)
  3. FVG creation timestamp ≤ BOS timestamp + MAX_WINDOW bars
```

**MAX_WINDOW = 20 bars** (M1).

This means: the displacement FVG must occur within 20 bars of the BOS event.
FVGs further than 20 bars from the BOS are NOT associated displacement — they are independent structural events.

---

## 5. BOS–OB Association (Critical)

### 5.1 Selection Rule

For a given BOS event, there may be multiple qualifying displacement FVGs within MAX_WINDOW.

**Frozen selection rule**: Use the **first qualifying FVG** in chronological order after the BOS.

The OB associated with that first FVG is the POI for this event.

### 5.2 Overlapping FVGs

If multiple FVGs occur simultaneously (overlapping boundaries), use the one with the **largest gap size**. If gap sizes are identical, use the one created first.

### 5.3 One Event Per BOS

Each BOS generates at most ONE event.

If a BOS has no qualifying FVG within MAX_WINDOW, the BOS is excluded.
If a BOS has qualifying FVGs, only the first FVG's OB is used.

This prevents sample inflation from multiple OBs per BOS.

---

## 6. Freshness / First-Touch State Machine

```
STATE_FRESH:
  OB created, price has NOT returned to [OB.low, OB.high]
  → VALID FOR ENTRY

STATE_TESTED:
  Price wick has entered [OB.low, OB.high]
  → ENTRY DEACTIVATED

STATE_VIOLATED:
  Price has closed beyond OB extreme
  → PERMANENTLY INACTIVE
```

**First touch**: the first bar (after OB creation) whose low ≤ OB.high AND high ≥ OB.low (for bullish OB).
This represents a wick entering the zone.

**Entry timing**: the entry signal fires at the **close of the first-touch bar**.

The entry is then placed as a **limit order at the OB proximal edge** on the **next bar open**.

---

## 7. Entry Convention

### 7.1 Entry Price

```
Bullish OB: entry = OB.high (proximal edge — the top of the zone)
Bearish OB: entry = OB.low  (proximal edge — the bottom of the zone)
```

**Execution assumption**: the limit order is placed at the OB proximal edge and filled at the next bar open after the first-touch bar closes.

### 7.2 Why proximal edge?

- Conservative: requires price to enter the zone before entry.
- Matches R1 definition: "Limit order at OB proximal edge."
- Avoids assuming price touches the exact distal edge.

### 7.3 Fill assumption

If the next bar open is **inside or beyond** the limit price (i.e., the bar opens at or past the limit level), the fill is assumed.

If the next bar open does not reach the limit level, the entry does NOT trigger (event excluded from outcome measurement).

This is a **limit order with no chasing**.

---

## 8. Stop-Loss Definition

### 8.1 Structural Stop

```
Bullish OB: stop = OB.low  (distal edge — bottom of zone)
Bearish OB: stop = OB.high (distal edge — top of zone)
```

**Buffer**: None. The stop is exactly at the OB distal edge.

### 8.2 Rationale

The OB zone is [OB.low, OB.high]. If price closes beyond the zone, the structural premise is invalidated (STATE_VIOLATED).

A fixed buffer would introduce a parameter. The clean first test uses the structural edge directly.

**Note**: the actual R-multiple depends on the OB zone width, which varies across events. This is acceptable for the forward-return framework (Section 10).

---

## 9. Exit / Outcome Definition

### 9.1 Primary Framework: Fixed Time-Horizon Return

The primary economic outcome is:

```
Forward return = (price at entry + HORIZON - entry price) / entry price × 10,000 (basis points)
```

For a **bullish** entry:

```
Forward return = (close at entry + HORIZON_bars - entry) / entry × 10,000 bps
```

For a **bearish** entry:

```
Forward return = (entry - close at entry + HORIZON_bars) / entry × 10,000 bps
```

**HORIZON = 120 bars** (M1) = 2 hours.

### 9.2 Why time-horizon rather than R-target?

- No RR parameter to optimize.
- Preserves the full distribution of outcomes.
- Allows calculation of mean, median, skewness, tail risk.
- Honest about the time-value of the trade.
- Can be computed for every event (no target never reached).

### 9.3 Why 120 bars (2 hours)?

- Long enough for the continuation move to develop.
- Short enough to avoid extremely stale outcomes.
- The M1 timeframe gives 120 independent observations.
- No optimization — this is a structural choice (comparable to typical intraday trade horizons).

### 9.4 Alternative endpoint (secondary)

As a secondary descriptor only (not primary):

```
R-multiple = forward return / (|OB.high - OB.low| / entry × 10,000)
```

This normalizes by the OB zone width and is reported for interpretability only.

### 9.5 Stop-hit handling

If price hits the stop before the horizon completes:

```
The outcome is recorded as the stop-loss result:
  Bullish: stop_result = (OB.low - entry) / entry × 10,000 bps (negative)
  Bearish: stop_result = (entry - OB.high) / entry × 10,000 bps (negative)
```

The event is classified as a **stop-out** and its outcome is the stop-loss result (not the full horizon return).

**If price hits stop AND later recovers within the horizon**: the stop-out result still counts. The trade was stopped.

**If price hits stop and the bar close is beyond the stop level**: STATE_VIOLATED.

### 9.6 Expiry

If neither the stop is hit nor the entry triggers within the horizon window:

```
If the entry was triggered: outcome = forward return at HORIZON bars
If the entry was never triggered (limit not filled): event EXCLUDED from outcome measurement
```

---

## 10. Transaction-Cost Model

### 10.1 Assumptions

```
Spread:    3.0 points (30 pips) — conservative XAUUSD M1 average
Commission: $0 per lot (already embedded in spread assumption)
Slippage:   1.0 point (10 pips) — additional slippage on limit fill
Total:     4.0 points per trade (40 pips round-trip)
```

### 10.2 Application

```
Gross outcome (bps):  forward return in basis points
Cost (bps):           spread_cost + slippage_cost
  spread_cost  = 3.0 / entry × 10,000 bps
  slippage_cost = 1.0 / entry × 10,000 bps
  total_cost   = 4.0 / entry × 10,000 bps

Net outcome = gross outcome - total_cost
```

### 10.3 Rationale

- 3-point spread is conservative for XAUUSD M1 (typical ECN spread 1–4 points).
- 1-point slippage is conservative for limit orders on M1.
- No commission modeled separately.
- These are NOT optimized. They are frozen before testing.

---

## 11. Dealing-Range / Premium-Discount Treatment

### 11.1 Decision: NO premium/discount filter for SMC-R3

The BOS+OB continuation model is a **trend continuation** pattern, not a reversal pattern.

Applying the reversal-oriented premium/discount filter (buy only in discount, sell only in premium) to a continuation pattern would be structurally inappropriate for this hypothesis.

**SMC-R3 does NOT apply premium/discount filtering.**

### 11.2 Rationale

- BOS+OB continuation naturally occurs during an established trend.
- The premium/discount filter is designed for POI reversal models (Models 2–7).
- The first test must isolate the BOS+OB structural geometry without adding a context filter.

### 11.3 Future consideration

Premium/discount filtering may be tested as a separate module hypothesis in SMC-R4/SMC-R5.

---

## 12. Inducement Treatment

### 12.1 Decision: NO inducement filter for SMC-R3

Inducement (IDM) validation is Pillar 5 of the POI validation framework and was scored as "not automatic rejection" in R1.

**SMC-R3 does NOT apply inducement filtering.**

### 12.2 Rationale

- Inducement is the most discretionary of the 5 pillars.
- Its economic contribution is unknown.
- The first test should use only the core structural primitives.

---

## 13. POI Validation Treatment

### 13.1 Mandatory pillars (applied)

| Pillar | Status | Rule |
|--------|--------|------|
| Zone Refinement | **APPLIED** | OB must be associated with a displacement FVG (already guaranteed by construction) |
| Displacement | **APPLIED** | FVG must be within MAX_WINDOW=20 of BOS (already guaranteed by construction) |
| Freshness | **APPLIED** | OB must be STATE_FRESH at time of first touch |

### 13.2 Optional pillars (NOT applied)

| Pillar | Status | Reason |
|--------|--------|--------|
| Premium/Discount | NOT APPLIED | Continuation pattern; structurally inappropriate |
| Inducement | NOT APPLIED | Most discretionary; future module hypothesis |

---

## 14. Chronological Split

### 14.1 Discovery Period

```
Start: 2021-04-12 (dataset beginning)
End:   2024-12-31
```

### 14.2 OOS Validation Period

```
Start: 2025-01-01
End:   2026-04-10 (dataset end)
```

### 14.3 Rationale

- Discovery = ~3.75 years
- OOS = ~1.25 years
- Chronological split prevents look-ahead bias.
- The split date is frozen BEFORE testing.
- No parameter estimation is required (zero degrees of freedom), but the split preserves the validation discipline.
- OOS period is sufficient for ~15,000+ M1 bars per month × 16 months.

### 14.4 Primary Decision

The **primary economic decision** uses the **full dataset** (discovery + OOS combined) because:

- The hypothesis has zero free parameters.
- The OOS split is for future model validation, not for this zero-parameter test.
- A zero-parameter structural test either works or it doesn't across the full period.

**OOS validation** is performed as a secondary consistency check: if the effect is robust, it should appear in both subperiods.

---

## 15. Event Independence

### 15.1 One Event Per BOS

Each qualifying BOS produces at most one OB event.

### 15.2 Freshness Enforcement

Only STATE_FRESH OBs generate entries. Once an OB is tested (STATE_TESTED), it is deactivated.

### 15.3 Temporal Separation

Events must be separated by at least **1 bar** to avoid overlapping outcomes.

### 15.4 Overlapping POI Handling

If two BOS events produce OBs that overlap in price:

```
Both events are tracked independently.
Each has its own freshness state.
Each is counted separately IF it produces an independent entry.
```

### 15.5 Serial Dependence

Multiple BOS events may occur in rapid succession during strong trends.

**Dependence treatment**: use Newey-West heteroskedasticity-and-autocorrelation-consistent (HAC) standard errors with a lag bandwidth of 10 bars (10 minutes).

This accounts for serial correlation without requiring event de-duplication.

---

## 16. Statistical Inference

### 16.1 Primary Test

```
One-sample t-test of mean net forward return (bps)
H₀: μ ≤ 0
H₁: μ > 0
One-sided
```

Standard errors computed using Newey-West HAC with bandwidth = 10.

### 16.2 Alpha

```
α = 0.05
```

### 16.3 Secondary Descriptors (not primary decisions)

| Descriptor | Purpose |
|------------|---------|
| Median forward return | Robustness to outliers |
| Win rate | Descriptive only |
| Mean R-multiple | Risk-normalized interpretation |
| Stop-out rate | Descriptive only |
| Max adverse excursion | Descriptive only |
| Max favorable excursion | Descriptive only |

These do NOT drive the primary decision.

### 16.4 Confidence Interval

```
95% one-sided lower confidence bound for mean forward return.
```

---

## 17. OOS Consistency Check

### 17.1 Procedure

Split results into:

```
Discovery: 2021-04-12 to 2024-12-31
OOS:       2025-01-01 to 2026-04-10
```

### 17.2 Consistency Criterion

If the full-dataset result is significant, check:

- Discovery period: direction of mean (should be positive)
- OOS period: direction of mean (should be positive)
- OOS mean should not be dramatically different from discovery mean

### 17.3 OOS Decision Rule

```
If full-dataset significant AND both subperiods positive → ROBUST
If full-dataset significant BUT OOS negative → FRAGILE (flag for control review)
If full-dataset not significant → FAIL
```

---

## 18. Primary Economic Metric

### 18.1 Primary

**Mean net forward return (bps)** after 4.0-point transaction costs.

### 18.2 Why this metric?

- Directly measures economic value.
- Accounts for costs.
- Preserves full outcome distribution.
- No parameter freedom.
- Unambiguous interpretation: "on average, each BOS+OB event earns X basis points."

---

## 19. Rare-Event Policy

### 19.1 Event Count

No minimum event count is imposed. The event count will be whatever the frozen extraction produces.

### 19.2 Evidence Sufficiency

Evidence sufficiency is assessed by:

- Confidence interval width
- Temporal stability across subperiods
- Consistency of direction across chronological quarters

### 19.3 Calendar Exposure

The dataset spans ~5 years of M1 data. Even sparse events will accumulate meaningful calendar exposure.

---

## 20. Degrees of Freedom

```
BOS+OB has ZERO free parameters:
  - Swing detection: N=5 (fixed, not optimized)
  - MAX_WINDOW: 20 (structural, not optimized)
  - Entry: OB proximal edge (structural)
  - Stop: OB distal edge (structural)
  - Horizon: 120 bars (structural, not optimized)
  - Costs: 4.0 points (frozen, not optimized)
  - Alpha: 0.05 (standard)
  - HAC bandwidth: 10 (structural)
```

**There is no parameter search. The test has zero degrees of freedom.**

---

## 21. Methodology Freeze Checklist

- [x] BOS definition frozen (§4.2)
- [x] FVG definition frozen (§4.3)
- [x] OB definition frozen (§4.4)
- [x] POI validation requirements frozen (§13)
- [x] Freshness frozen (§6)
- [x] Event identity frozen (§15)
- [x] Entry price frozen (§7)
- [x] Stop reference frozen (§8)
- [x] Payoff frozen (§9)
- [x] Transaction costs frozen (§10)
- [x] OOS split frozen (§14)
- [x] Primary metric frozen (§18)
- [x] Primary statistical test frozen (§16)
- [x] Alpha frozen (§16.2)
- [x] Dependence treatment frozen (§15.5)
- [x] Rare-event evidence policy frozen (§19)
- [x] No outcome-based choices remain

**All boxes checked. METHODOLOGY IS FROZEN.**

---

## 22. What SMC-R3 Establishes

1. The complete deterministic BOS+OB event chain
2. The exact association rule (BOS → FVG → OB)
3. The entry convention (proximal edge, limit order)
4. The stop convention (distal edge, structural)
5. The outcome framework (time-horizon return, 120 bars)
6. The cost model (4.0 points)
7. The statistical test (one-sided t-test, HAC)
8. The chronological split (2024-12-31)
9. The zero-parameter character of the hypothesis
10. The primary and secondary metrics

---

## 23. What SMC-R3 Does NOT Establish

1. That BOS+OB has positive expectancy
2. Optimal RR or target
3. Any filter additions
4. Module interaction
5. Any EA code
6. Any parameter values
7. That the model should be traded

---

## 24. Risk Register

| Risk | Description | Mitigation |
|------|-------------|------------|
| Sample inflation | Multiple OBs per BOS | One event per BOS (§5.3) |
| Stale POIs | OBs from distant past | Freshness state machine (§6) |
| Serial dependence | Multiple events in trend | HAC standard errors (§15.5) |
| Entry non-fill | Limit order not reached | Excluded from measurement (§7.3) |
| Cost underestimation | Spread/slippage larger than modeled | Conservative 4.0-point frozen assumption (§10) |
| Survivorship bias | Only showing filled entries | All qualifying events tracked (§9.6) |
| Parameter freedom | Hidden degrees of freedom | Zero parameters identified (§20) |
| Outcome-driven choices | Adjusting horizon/metric after testing | All frozen before testing (§21) |
| Structural ambiguity | BOS/OB definitions unclear | Deterministic, R2-validated (§4) |
| Lookahead | Future data used in classification | R2 lookahead audit: PASS (§4) |

---

## 25. Required Inputs for SMC-R4

SMC-R4 will need:

```
SMC_R2_bos.csv  — 196,965 BOS events
SMC_R2_fvgs.csv — 471,475 FVGs with OB linkage
SMC_R2_obs.csv  — 471,475 OBs
SMC_R2_swings.csv — 208,621 swings
m1_clean.csv    — 1,768,123 M1 bars (for forward returns)
```

---

## 26. External API calls: 0 | New data acquired: 0 | Spend: $0.00

---

*SMC-R3 is a methodology-design milestone. No experiments were run. No backtests were performed. No parameters were optimized. No EA code was written.*
