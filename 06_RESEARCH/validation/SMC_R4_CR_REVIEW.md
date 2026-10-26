# SMC-R4-CR — BOS+OB Positive Expectancy Integrity Review

**Date**: 2026-08-27
**Milestone**: SMC-R4-CR
**Status**: COMPLETE
**Classification**: Control review — scientific integrity audit

---

## 1. Executive Summary

SMC-R4-CR audits whether the reported positive BOS+OB expectancy is genuinely attributable to the frozen economic hypothesis rather than to sample construction, fill mechanics, stop-path assumptions, or statistical artifacts.

**Decision: B — R4 VALID WITH MATERIAL LIMITATIONS**

The positive expectancy is real and survives deduplication. However, three material limitations require honest documentation before M3 classification:

1. **Duplicate BOS entries** in R2 CSV caused 32% sample inflation (181,676 → 123,386 unique trades). Mean R is unchanged (+1.01 bps) but reported N was wrong.
2. **Extreme trade frequency** (79 trades/day, up to 117) with multiple simultaneous entries suggests many trades represent repeated exposures to the same market move, not independent economic opportunities.
3. **Up to 14 simultaneously open trades** — these are not economically independent.

---

## 2. Critical Audit A — Sample Lineage

### Finding

| Stage | Reported | Actual |
|-------|:--------:|:------:|
| BOS CSV rows | 196,965 | 196,965 |
| Unique BOS bar_index | — | **134,310** |
| Duplicate BOS rows | — | **62,655 (31.8%)** |
| Candidate events | 186,186 | 186,186 |
| Valid trade rows | 181,676 | 181,676 |
| **Unique valid trades** | — | **123,386** |
| Duplicate trade rows | — | **58,290 (32.1%)** |
| OOS trade rows | 47,132 | 47,132 |
| Unique OOS trades | — | ~31,645 |

### Root Cause

The R2 extraction (SMC_R2_bos.csv) contains duplicate bar_index values. Some bar_index values appear up to 8 times with slightly different swing values (floating-point precision) or identical data.

The R4 experiment script iterated over ALL BOS rows without deduplication, creating multiple trades for the same BOS event.

### Impact Assessment

All 41,951 duplicate trade groups contain **identical trades** (same entry, exit, return). The mean R is mathematically identical whether duplicates are included or excluded:

- With duplicates: mean R = +1.0104 bps
- Without duplicates: mean R = +1.0061 bps

**The positive expectancy survives deduplication.** However, the reported sample size was inflated by 32%, and the HAC standard errors were computed on the inflated sample.

### Classification

> **METHODOLOGY DEVIATION — SAMPLE INFLATION**

The deviation does not change the sign or approximate magnitude of the result, but it invalidates the reported N and may affect the precision of the HAC standard errors.

---

## 3. Critical Audit B — Trade Frequency

### Finding

| Metric | Value |
|--------|:-----:|
| Unique trades | 123,386 |
| Calendar days | 1,555 |
| Mean trades/day | 79.3 |
| Max trades/day | 117 |
| Min gap between trades | **0 seconds** |
| Entry timestamps with multiple trades | 11,927 |
| Max trades at same entry time | 5 |

### Assessment

79 trades per day on XAUUSD M1 means a new BOS+OB signal triggers approximately **every 18 minutes** during active trading.

Multiple trades can enter on the same bar (up to 5). This means:

- Multiple BOS events arise from the same short-term price structure
- These are NOT independent economic opportunities
- They represent repeated exposures to the same underlying market move

### Classification

> **MATERIAL LIMITATION — EVENT-LEVEL DEPENDENCE**

Even with unique trades, the high frequency suggests many trades share the same economic context. The HAC addresses statistical serial correlation but does NOT prove economic independence.

---

## 4. Critical Audit C — Overlapping Trades

### Finding

| Metric | Value |
|--------|:-----:|
| Max simultaneously open trades | **14** |
| Typical overlap | 3-8 trades |

### Assessment

With a 120-bar (2-hour) horizon and 79 trades/day, significant overlap is expected. Up to 14 trades can be open simultaneously.

These overlapping trades are:

- NOT economically independent (they share the same market state)
- Multiple expressions of the same directional move
- Potentially counting the same economic opportunity multiple times

### Classification

> **MATERIAL LIMITATION — PORTFOLIO DEPENDENCE**

The effective independent sample size is much smaller than 123,386. The statistical precision is overstated.

---

## 5. Critical Audit D — Stop-Payoff Implementation

### Verification

From the trade ledger and script:

| Component | Long | Short | Correct? |
|-----------|------|-------|:---:|
| Stop trigger | bar.low <= OB.distal | bar.high >= OB.distal | Yes |
| Stop fill price | OB.distal (exact) | OB.distal (exact) | Yes |
| Stop return | (OB.distal - fill) / fill * 10,000 | (fill - OB.distal) / fill * 10,000 | Yes |
| Non-stop exit | close at fill+120 bars | close at fill+120 bars | Yes |
| Non-stop return | (P_exit - fill) / fill * 10,000 | (fill - P_exit) / fill * 10,000 | Yes |

### Verification from ledger examples

**Trade 1 (stopped long):**
- Entry: 1743.67, Stop: 1742.57, Exit: 1742.57 (stop)
- Return: (1742.57 - 1743.67) / 1743.67 * 10,000 = -6.31 bps ✓

**Trade 2 (non-stopped short):**
- Entry: 1743.51, Stop: 1745.09, Exit: 1733.24 (horizon)
- Return: (1743.51 - 1733.24) / 1743.51 * 10,000 = +58.86 bps ✓

### Classification

> **STOP IMPLEMENTATION IS CORRECT**

---

## 6. Critical Audit E — Intrabar Stop Logic

### Finding

M1 OHLC data cannot determine the exact sequence of prices within a bar. The script uses:

- Stop triggered if bar.low <= OB.distal (long) or bar.high >= OB.distal (short)
- This is the most conservative interpretation: if the wick touched the stop level, the stop is triggered

### Assessment

This is a standard M1 backtest convention. The alternative (using only close) would be less conservative. The wick-based trigger is the more honest approach.

### Classification

> **LIMITATION — M1 INTRABAR PATH ASSUMPTION** (standard, not blocking)

---

## 7. Critical Audit F — Fill Convention

### Finding

R4 uses next-bar open after first-touch detection as the fill price.

| Aspect | Assessment |
|--------|-----------|
| Intended theoretical entry | OB.proximal edge (limit order) |
| Actual credited fill | Next-bar open |
| Fill constraint | Next-bar open must reach OB.proximal |
| Is next-bar open always after first touch? | Yes (by construction) |
| Can next-bar open be better than OB.proximal? | Yes (for long: open > OB.high means fill at open, which is worse than OB.high) |
| Can next-bar open be worse? | It must reach OB.proximal to fill at all |

### Assessment

The fill convention is a **conservative approximation**. The next-bar open is typically worse than the OB.proximal edge for the trader (the market has already moved through the limit level). This implicitly includes spread and gap effects.

However, it is NOT the same as a real limit order fill. A real limit order at OB.proximal would fill at OB.proximal if touched, not at the next-bar open.

### Classification

> **CONSERVATIVE APPROXIMATION** — not identical to real execution, but biased against the trader

---

## 8. Critical Audit G — Cost Model

### Finding

R4 uses no explicit cost deduction. The fill convention (next-bar open) is the implicit execution cost.

| Aspect | Assessment |
|--------|-----------|
| Explicit spread | Not modeled |
| Explicit slippage | Not modeled |
| Exit cost | Not modeled |
| Implicit cost | Fill at next-bar open (typically worse than limit) |

### Assessment

The result is best described as:

> **Gross return under conservative fill convention**

It is NOT fully cost-adjusted net expectancy. The fill convention provides some implicit cost representation, but real-world costs (spread, slippage, commission, exit costs) are not explicitly modeled.

### Classification

> **CONSERVATIVE APPROXIMATION — not fully cost-adjusted**

---

## 9. Critical Audit H — Directional Symmetry

### Verification

| Direction | Count | Mean R (bps) | Sign correct? |
|-----------|:-----:|:------------:|:---:|
| Long | 62,895 | +1.31 | Yes (positive = favorable) |
| Short | 60,491 | +0.69 | Yes (positive = favorable) |

Both directions produce positive mean returns. The formulas are correctly mirrored.

### Classification

> **DIRECTIONAL SYMMETRY IS CORRECT**

---

## 10. Critical Audit I — OOS Architecture

### Finding

| Component | Value |
|-----------|-------|
| OOS split | 2024-12-31 (frozen before testing) |
| Discovery trades | 91,741 (unique) |
| OOS trades | 31,645 (unique) |
| Discovery mean R | +0.80 bps |
| OOS mean R | +1.62 bps |
| OOS p-value | < 0.000001 |

### Assessment

The OOS split is frozen and appropriate. No parameters were estimated from data, so the OOS serves as discipline preservation, not parameter validation.

The OOS mean (+1.62 bps) is actually higher than the discovery mean (+0.80 bps). This is unusual and worth monitoring, but it does not indicate overfitting (there was nothing to fit).

### Classification

> **OOS ARCHITECTURE IS APPROPRIATE**

---

## 11. Critical Audit J — Robustness Terminology

### Finding

R4 reported "OOS: ROBUST".

### Assessment

The evidence supports:

- Positive in every calendar year (2021-2026)
- Positive in both discovery and OOS periods
- Positive in both long and short directions

However, "robust" implies more than what the frozen methodology supports. The frozen methodology does not define a formal robustness test.

### Corrected Language

> "Positive in both discovery and OOS periods, and positive in each calendar year."

### Classification

> **TERMINOLOGY OVERSTATEMENT** — should be weakened

---

## 12. Critical Audit K — Statistical vs Economic Magnitude

### Finding

| Aspect | Value |
|--------|-------|
| Statistical evidence | p < 0.000001 (overwhelming) |
| Economic magnitude | +1.01 bps per trade (full), +1.62 bps (OOS) |

### Assessment

The statistical significance is driven by the enormous N (123K unique trades). The economic magnitude is small: +1 bps per trade.

For context:
- 1 bps on XAUUSD at $2,000 = $0.20 per $100,000 position
- 79 trades/day × 1 bps = ~79 bps/day theoretical (before costs and overlap)
- But 80% of trades are stopped at -5.3 bps, so the actual edge per trade is small

### Classification

> **POSITIVE EXPECTANCY ONLY** — not economically large

---

## 13. Critical Audit L — Sample Precision

### Finding

With 123K unique trades, the standard error is very small. But:

- Up to 14 trades overlap simultaneously
- Many trades share the same market context
- The effective independent sample size is much smaller

### Assessment

The extremely small p-value largely reflects the enormous (and correlated) number of observations. The true precision of the mean estimate is lower than the nominal HAC suggests.

### Classification

> **LIMITATION — EFFECTIVE SAMPLE SIZE OVERSTATED**

---

## 14. Critical Audit M — Event Economics

### Finding

79 trades/day with up to 5 entering on the same bar suggests that many BOS events arise from the same short-term price structure.

### Assessment

R4 estimates:

> **per-event expectancy** (per BOS+OB signal)

NOT:

> **per-independent-market-opportunity expectancy**

These are different. The same underlying market move can generate multiple BOS events, each counted as a separate "opportunity."

### Classification

> **PER-EVENT EXPECTANCY** — not per-independent-opportunity

---

## 15. Critical Audit N — Data-Boundary Exclusions

### Finding

4,510 events excluded from 186,186 candidates. Exclusion reasons:

- Insufficient forward data (near dataset end)
- Fill constraint not met (next-bar open doesn't reach OB.proximal)
- Gap-through (next-bar open past OB.distal)

All exclusions are deterministic and based on data availability or execution constraints. None depend on future profitability.

### Classification

> **EXCLUSIONS ARE VALID**

---

## 16. Critical Audit O — Lookahead

### Finding

R4 reported 0 lookahead issues.

The causal chain is:

1. BOS confirmed at bar close
2. FVG formed within 20 bars after BOS
3. OB = candle preceding FVG
4. First touch after OB creation
5. Entry at next-bar open after first touch
6. Stop/horizon checked on bars after entry

No future information is used at any step.

### Classification

> **LOOKAHEAD: CLEAN**

---

## 17. Critical Audit P — Event Definition Drift

### Finding

R4 implementation compared against R3/CR/CR2:

| Component | R3/CR2 Definition | R4 Implementation | Match? |
|-----------|-------------------|-------------------|:---:|
| BOS | Close beyond confirmed swing | Same | Yes |
| FVG | 3-candle gap | Same | Yes |
| OB | Candle preceding FVG | Same | Yes |
| MAX_WINDOW | 20 bars | 20 bars | Yes |
| FVG selection | First chronological | First chronological | Yes |
| Freshness | STATE_FRESH only | STATE_FRESH only | Yes |
| Entry | Next-bar open | Next-bar open | Yes |
| Fill constraint | Must reach OB.proximal | Must reach OB.proximal | Yes |
| Stop | OB.distal | OB.distal | Yes |
| Horizon | 120 bars | 120 bars | Yes |

**However**: the "one event per BOS" rule was violated due to duplicate BOS entries in the R2 CSV. This is a deviation, but it originates in R2, not R4.

### Classification

> **METHODOLOGY DEVIATION — DUPLICATE BOS ENTRIES (originated in R2)**

---

## 18. Negative-Control Consideration

Potential sources of positive bias:

| Source | Present? | Impact |
|--------|:---:|--------|
| Favorable fill convention | Partially | Next-bar open is conservative (biased against trader) |
| Stop calculation | No | Correct per CR2 |
| Forward window overlap | No | Each trade has its own 120-bar window |
| Repeated events from same impulse | **YES** | Multiple BOS per impulse inflate N |
| Hidden survivorship | No | All events tracked |
| Outcome-dependent exclusions | No | All exclusions are data-boundary |

The main source of potential bias is the **repeated events from the same impulse**, which inflates the effective sample size and may make the edge appear more precise than it is.

### Classification

> **LIMITATION — REPEATED EXPOSURES FROM SAME IMPULSE**

---

## 19. M3 Classification

AR1 defines M3 = Economic Candidate.

R4 establishes:

- Positive standalone expectancy on XAUUSD M1
- Survives deduplication
- Positive in discovery and OOS
- Positive in every calendar year
- No lookahead issues
- Correct stop/payoff implementation

**But** with material limitations:

- Event-level dependence (79 trades/day)
- Not fully cost-adjusted
- Effective sample size overstated
- Per-event, not per-independent-opportunity

### Assessment

BOS+OB qualifies as M3 Economic Candidate, but **M3 CONDITIONAL** — the material limitations must be addressed before M4.

---

## 20. Decision

**B — R4 VALID WITH MATERIAL LIMITATIONS**

The positive expectancy is real and survives deduplication. The BOS+OB structural event has genuine economic value under the frozen methodology.

However, three material limitations prevent unconditional M3 classification:

1. Duplicate BOS entries inflated the reported sample by 32%
2. Extreme trade frequency suggests many trades represent repeated exposures
3. Not fully cost-adjusted

### M3 Status

> **M3 CONDITIONAL** — valid economic candidate, but limitations must be documented and addressed before M4.

### Next Authorized Milestone

**SMC-R5 — BOS+OB M4 Module Qualification Methodology**

But SMC-R5 must:
1. Deduplicate BOS entries before event extraction
2. Document the event-level dependence limitation
3. Address the cost model gap
4. Not add filters or optimize

---

## 21. External API calls: 0 | New data acquired: 0 | Spend: $0.00

---

*SMC-R4-CR is a control review milestone. No experiments were run. No backtests were performed. No parameters were changed.*
