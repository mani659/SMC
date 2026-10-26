# SMC-R3-CR — BOS + OB Economic Methodology Control Review

**Date**: 2026-08-27
**Milestone**: SMC-R3-CR
**Status**: COMPLETE
**Classification**: Control review — no implementation

---

## 1. Executive Summary

SMC-R3-CR audits whether SMC-R3 is genuinely ex-ante, internally coherent, causally valid, and free of hidden researcher degrees of freedom.

**Decision: SMC-R3 VALID WITH CONTROLLED AMENDMENT**

Two issues require correction before SMC-R4 authorization:

1. **Cost/payoff inconsistency** (BLOCKER): The forward return is measured from the next-bar open (the fill price), but 4 points of spread cost are also deducted. This double-counts the spread.
2. **Stop/payoff relationship** (CLARIFICATION): The stop participates in the outcome measurement (Section 9.5) but is described as "not part of the primary payoff." The actual R3 document treats it as part of the primary outcome. This must be made explicit.

Neither issue changes the economic hypothesis. Both are implementation-level corrections that can be frozen before any outcome is examined.

---

## 2. Zero-Degrees-of-Freedom Audit

### Classification Table

| Choice | Value | Classification | Evidence | Risk |
|--------|-------|:---:|----------|------|
| Swing N | 5 | **A** — inherited from R1/R2 | R1 §3.3 defines N=5 for M1; R2 extraction validated | Low |
| MAX_WINDOW (BOS→FVG) | 20 bars | **C** — researcher design choice | NOT in R1 or R2; chosen specifically for R3 | Medium |
| Entry | OB proximal edge | **A** — inherited from R1 | R1 Trigger F: "Limit order at OB proximal edge" | Low |
| Fill | Next-bar open | **C** — researcher design choice | NOT in R1; R1 does not specify fill mechanics | Medium |
| Stop | OB distal edge | **A** — inherited from R1 | R1 Trigger F: "Beyond the OB distal edge" | Low |
| Horizon | 120 bars | **C** — researcher design choice | NOT in R1/R2; no SMC definition of this horizon | Medium |
| Cost | 4.0 points | **C** — researcher design choice | NOT in R1/R2; frozen for R3 | Medium |
| HAC lag | 10 | **C** — researcher design choice | NOT in R1/R2; standard econometric practice | Low |
| OOS split | 2024-12-31 | **C** — researcher design choice | NOT in R1/R2; standard practice | Low |

### Summary

- **A (inherited): 3 choices** — Swing N, entry, stop
- **C (design choice): 6 choices** — MAX_WINDOW, fill, horizon, cost, HAC, OOS split
- **D (ambiguous): 0**

The claim of "zero parameters" is partially misleading. There are zero parameters **estimated from data**, but six methodological choices are **design selections made by the researcher**. These are frozen and legitimate, but they should be classified honestly.

---

## 3. Audit A — 20-Bar BOS→FVG Association

### Origin

The MAX_WINDOW = 20 bars is **NOT** inherited from R1 or R2. R1 defines FVGs and BOS independently but does not specify an association window. R2 extracts both primitives but does not link them.

This is a **new researcher design choice** for R3.

### Justification

The 20-bar window is a structural choice representing: "the displacement FVG should occur during or shortly after the BOS impulse, not minutes/hours later." On M1, 20 bars = 20 minutes, which is a reasonable intraday impulse window.

### Impact Assessment

- A shorter window (e.g., 5 bars) would exclude FVGs that form during slower impulses.
- A longer window (e.g., 50 bars) would include FVGs that may be structurally unrelated to the BOS.
- The 20-bar choice is defensible but should be documented as a design choice, not inherited.

### FVG/OB Uniqueness

Within a single BOS event, the R3 selection rule is deterministic:

1. First qualifying FVG in chronological order
2. If overlapping: largest gap, then earliest
3. One event per BOS

This is **unambiguous**. No blocker.

### Verdict

Not a blocker, but should be classified as **C (design choice)** rather than **A (inherited)**.

---

## 4. Audit B — Entry / Fill Mechanics

### The Issue

R3 §7.3 states:

> "If the next bar open is inside or beyond the limit price, the fill is assumed."

R3 §9.1 defines the forward return as:

> "close at entry + HORIZON_bars"

where "entry" is the OB proximal edge (the limit price).

### The Inconsistency

If the next bar opens ABOVE the OB proximal edge (bullish case):

- **Fill price**: OB.high (the limit order price — limit orders fill at the limit or better)
- **Forward return reference**: next-bar open (which is ABOVE OB.high)

These are **different prices**.

The forward return is measured from the **next-bar open**, not from the **fill price** (OB.high).

This means:
- If price gaps through the OB boundary, the return is measured from a **worse** entry point than the actual fill.
- The economic outcome does not match the actual execution.

### Resolution

Two coherent options:

**Option A**: Measure forward return from the fill price (OB.proximal edge). This is the actual entry price.

**Option B**: Use next-bar open as the fill price. This is a more conservative execution assumption.

**R3 appears to use a混合**: fill at OB.proximal, return from next-bar open. This is internally inconsistent.

### Verdict

**METHODOLOGY BLOCKER — FILL/REFERENCE INCONSISTENCY**

Must be resolved before SMC-R4.

---

## 5. Audit C — Stop vs Primary Payoff

### What R3 Actually Says

§9.5 states explicitly:

> "If price hits the stop before the horizon completes: The outcome is recorded as the stop-loss result... The event is classified as a stop-out and its outcome is the stop-loss result (not the full horizon return)."

This means the stop **does** participate in the primary outcome measurement. Stopped-out events contribute a fixed negative return to the overall mean.

### The Inconsistency

R3 §8.2 says:

> "Note: the actual R-multiple depends on the OB zone width, which varies across events. This is acceptable for the forward-return framework (Section 10)."

But the primary metric (§18) is:

> "Mean net forward return (bps) after 4.0-point transaction costs."

This is a **hybrid outcome**:
- Non-stopped events: forward return at 120 bars
- Stopped events: fixed stop-loss result

This is NOT purely a "forward return." It is a **trade-payoff with stop-loss truncation**.

### Economic Interpretation

The stop functions as:
1. A **sample filter** (stopped events have different outcome structure)
2. An **outcome component** (stopped events contribute a fixed negative return)
3. A **structural invalidation** (STATE_VIOLATED after close beyond stop)

All three roles are simultaneously active. This is coherent but should be stated explicitly.

### Verdict

**CLARIFICATION REQUIRED — not a blocker, but the stop's role must be made explicit in the primary metric definition.**

---

## 6. Audit D — Cost/Payoff Consistency

### The Core Issue

R3 measures forward return from the next-bar open (the fill price), then deducts 4 points of transaction cost.

If the next-bar open IS the fill price:

- The spread is already reflected in the difference between the OB boundary and the next-bar open
- Deducting 4 additional points **double-counts** the spread

If the next-bar open is NOT the fill price (i.e., the fill is at OB.proximal edge):

- The forward return should be measured from OB.proximal, not from next-bar open
- Deducting 4 points would then represent the actual entry cost

### Resolution Options

**Option 1**: Forward return from OB.proximal (fill price), minus 4 points cost.
- Forward return = (P_{t+120} - OB.proximal) / OB.proximal × 10,000
- Net = Forward return - 4.0 / OB.proximal × 10,000

**Option 2**: Forward return from next-bar open (fill price), minus 0 points cost (spread already in price).
- Forward return = (P_{t+120} - next_bar_open) / next_bar_open × 10,000
- Net = Forward return (no additional cost deduction)

**Option 3**: Forward return from OB.proximal, minus 4 points, but classify as a trade payoff rather than a pure forward return.

All three are coherent. R3 currently uses a mixture that is internally inconsistent.

### Verdict

**METHODOLOGY BLOCKER — COST/PAYOFF INCONSISTENCY**

Must be resolved before SMC-R4.

---

## 7. Audit E — 120-Bar Horizon

### Origin

The 120-bar horizon is **NOT** inherited from R1 or R2. No SMC document specifies a 2-hour forward window.

This is a **researcher design choice**.

### Justification

120 bars on M1 = 2 hours. This is a common intraday trade horizon and is long enough for a continuation move to develop while short enough to avoid very stale outcomes.

### Overlapping Observations

Events from different BOS occurrences are independent (different timestamps, different OBs). The 120-bar outcomes do not overlap in the traditional time-series sense because each event has its own entry timestamp.

However, events from the same BOS cluster (e.g., rapid successive BOS during a trend) may have correlated outcomes. The HAC bandwidth of 10 is designed to handle this.

### HAC Adequacy

Events during rapid trends may be spaced 5-20 bars apart. HAC bandwidth=10 captures correlations within a 10-bar window. This is adequate for M1 event spacing.

### Verdict

Not a blocker. The 120-bar choice is a legitimate design decision.

---

## 8. Audit F — HAC Specification

### Origin

HAC bandwidth = 10 is **NOT** inherited from R1 or R2. Standard econometric practice.

### Adequacy

For M1 data, 10 bars = 10 minutes. Most BOS events are spaced further apart than 10 minutes. The HAC is conservative.

If events are more than 10 bars apart (the typical case), the HAC bandwidth has no effect — standard errors are identical to ordinary t-test standard errors.

### Verdict

Not a blocker. Conservative and defensible.

---

## 9. Audit G — One Event Per BOS

### Assessment

The one-event-per-BOS rule is deterministic and prevents sample inflation. The selection among multiple qualifying FVGs is also deterministic (first chronological, then largest gap).

### Concern

The 20-bar window choice (a design decision) determines how many BOS events qualify. A different window would change the sample. But the rule itself is internally consistent.

### Verdict

Not a blocker. Deterministic and defensible.

---

## 10. Audit H — Freshness

### Assessment

The freshness state machine is clearly defined:
- STATE_FRESH: first touch = wick entering zone
- Touch = bar whose low ≤ OB.high AND high ≥ OB.low (bullish case)
- First touch is identified retrospectively from M1 data
- No lookahead: the touch is identified from bars AFTER the OB creation

### Concern

The first-touch bar is identified using the bar's high/low, which are known at bar close. The entry fires at bar close, with limit order on next bar open. This is causally valid.

### Verdict

Not a blocker. Deterministic and causally valid.

---

## 11. Audit I — Causal Timeline

```
Time t:     Confirmed swing (N=5 bars after swing bar)
Time t+1:   BOS close beyond swing
Time t+2..t+22: Qualifying FVGs within MAX_WINDOW=20
Time t+2..t+22: OB = candle preceding first qualifying FVG
Time > t+22:     Price returns to OB zone
Time T:          First-touch bar closes
Time T+1:        Limit order placed at OB.proximal
Time T+1 open:   Fill if price reaches OB.proximal (or not → excluded)
Time T+121:      Forward return measured (or stop hit earlier)
```

### Lookahead Check

| Component | Lookahead? | Evidence |
|-----------|:---:|----------|
| Swing confirmation | No | N=5 bars after swing bar |
| BOS recognition | No | Close must confirm break |
| FVG formation | No | 3-candle pattern requires candle[i+2] close |
| OB identification | No | Candle preceding FVG, known at FVG confirmation |
| BOS→FVG association | No | FVG timestamp ≥ BOS timestamp |
| First-touch detection | No | Bars after OB creation only |
| Entry execution | No | Next bar open after first-touch close |
| Forward return | No | Measured from entry timestamp + 120 bars |
| Stop check | No | Intraday price movement after entry |

**No lookahead issues identified.**

### Verdict

Causal timeline is clean.

---

## 12. Audit J — OOS Split

### Role

The OOS split (2024-12-31) has **no clear role** in a zero-parameter hypothesis test. There is nothing to fit in the discovery period that gets validated in OOS.

### Standard Practice

The split is standard practice and is frozen before testing. It is not data-driven.

### Concern

If the split serves no purpose, it should be documented as such rather than implied to play a validation role.

### Verdict

Not a blocker. Should be documented as "discipline preservation" rather than "OOS validation."

---

## 13. Audit K — Primary Economic Endpoint

### What R3 Claims

> "Mean net forward return (bps) after 4.0-point transaction costs."

### What R3 Actually Computes

A hybrid:
- Non-stopped events: forward return at 120 bars from next-bar open, minus 4 points
- Stopped events: stop-loss result minus 4 points (fixed negative return)

### Assessment

This is coherent as a **trade-payoff metric**. It is NOT purely a "forward return" because stopped events are truncated.

The name should reflect the actual computation.

### Verdict

**CLARIFICATION REQUIRED** — the primary metric name should accurately describe what is computed.

---

## 14. Summary of Findings

| Audit | Finding | Severity | Resolution |
|-------|---------|:---:|------------|
| A — Zero-DoF claim | 6 of 9 choices are design selections (C), not inherited | Medium | Reclassify honestly |
| B — BOS→FVG window | MAX_WINDOW=20 is a new design choice, not inherited | Low | Document as C |
| C — Entry/fill | Fill price ≠ forward return reference price | **BLOCKER** | Choose one consistently |
| D — Stop/payoff | Stop participates in outcome; described as "not part of primary" | Medium | Make explicit |
| E — Cost/payoff | 4-point deduction may double-count spread | **BLOCKER** | Resolve with fill choice |
| F — Horizon | 120 bars is a design choice, not inherited | Low | Document as C |
| G — HAC | Lag=10 is conservative and defensible | Low | No change |
| H — Event identity | One-per-BOS is deterministic and unambiguous | Low | No change |
| I — Freshness | Deterministic, causally valid | Low | No change |
| J — Causal timeline | Clean, no lookahead | Low | No change |
| K — OOS split | Role unclear in zero-parameter context | Low | Document as discipline |
| L — Endpoint naming | "Forward return" does not match actual computation | Medium | Rename accurately |

---

## 15. Decision

**B — SMC-R3 VALID WITH CONTROLLED AMENDMENT**

The economic hypothesis is sound. The methodology is deterministic and causally valid. Two implementation-level issues require correction before SMC-R4.

Both corrections can be frozen before any outcome is examined.

---

## 16. External API calls: 0 | New data acquired: 0 | Spend: $0.00

---

*SMC-R3-CR is a control review milestone. No experiments were run. No backtests were performed. No parameters were changed.*
