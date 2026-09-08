# SMC-R8 — CHOCH Reversal Standalone Economic Methodology

**Milestone**: SMC-R8
**Status**: COMPLETE
**Date**: 2026-08-27
**Decision**: METHODOLOGY FROZEN

---

## 1. Core Research Question

> **Does a confirmed liquidity sweep followed by a causal CHOCH reversal create positive directional expectancy on XAUUSD M1 under a single predefined payoff and realistic execution convention?**

This is a NEW economic hypothesis. It does not inherit the BOS+OB economic result.

---

## 2. Economic Hypothesis

```
If:
    an established trend exists,
    price sweeps the final extreme of the trend,
    and the relevant opposing structure is broken (CHOCH confirmed),

then:
    entering in the reversal direction at the broken CHOCH level
    should produce positive net expectancy.

because:
    the observable geometry may identify exhaustion of the prior directional state
    and a subsequent change in order-flow direction.

Falsification:
    the predefined OOS economic payoff is not positive under the frozen inference rule.
```

---

## 3. Frozen Event Chain

```
Established trend (HH/HL sequence or LH/LL sequence)
    ↓
Final extreme identified (last HH for bearish, last LL for bullish)
    ↓
Liquidity sweep (wick pierces + close back inside)
    ↓
CHOCH swing identified (last HL for bearish, last LH for bullish)
    ↓
CHOCH confirmed (close beyond CHOCH swing)
    ↓
Entry on retest (limit at broken CHOCH level)
    ↓
Path-dependent outcome (stop or 120-bar horizon)
```

Every link is deterministic.

---

## 4. Prior Trend Definition

**Frozen rule:**

```
Bullish trend:
  At least 2 consecutive higher highs AND
  at least 2 consecutive higher lows
  (using N=5 swing detection)

Bearish trend:
  At least 2 consecutive lower highs AND
  at least 2 consecutive lower lows
  (using N=5 swing detection)
```

**Deterministic identification:**

1. Detect all swing highs and swing lows using N=5.
2. For bullish trend: find a sequence of at least 3 swing highs where each is higher than the previous, AND at least 3 swing lows where each is higher than the previous.
3. For bearish trend: find a sequence of at least 3 swing highs where each is lower than the previous, AND at least 3 swing lows where each is lower than the previous.
4. The trend is "established" when this condition is first met.

**Classification:** INHERITED from R1 swing framework + RESEARCHER CHOICE for minimum count (2 consecutive = 3 swings minimum).

---

## 5. Liquidity Level Definition

**Frozen rule:**

```
The liquidity level is the final extreme of the established trend:

  Bearish CHOCH: the last confirmed swing high (HH) in the uptrend
  Bullish CHOCH: the last confirmed swing low (LL) in the downtrend
```

"Last" means most recent in time, not highest/lowest in price.

**Classification:** INHERITED from R1 (trend extreme concept).

---

## 6. Sweep Definition

**Frozen rule:**

```
Liquidity sweep:
  Bearish: price wick > last HH AND candle closes below last HH
  Bullish: price wick < last LL AND candle closes above last LL
```

The sweep is identified at the bar close that satisfies both conditions.

**Deterministic identification:**

1. After the last HH/LL is identified, search forward for a bar where:
   - For bearish: bar.high > last_HH AND bar.close < last_HH
   - For bullish: bar.low < last_LL AND bar.close > last_LL
2. The first such bar is the sweep bar.
3. The sweep timestamp is the close of that bar.

**Classification:** INHERITED from R1 liquidity sweep definition.

---

## 7. CHOCH Swing Definition

**Frozen rule:**

```
The CHOCH swing is the last swing in the trend direction that must be broken:

  Bearish CHOCH: the last confirmed swing low (HL) in the uptrend
  Bullish CHOCH: the last confirmed swing high (LH) in the downtrend
```

This is the structural point whose break confirms the character change.

**Deterministic identification:**

1. After identifying the trend, find the last HL (for bearish) or last LH (for bullish) that was formed before the sweep.
2. This is the CHOCH swing.

**Classification:** INHERITED from R1 CHOCH definition.

---

## 8. CHOCH Confirmation

**Frozen rule:**

```
CHOCH confirmed when:
  Bearish: candle close < CHOCH swing (last HL)
  Bullish: candle close > CHOCH swing (last LH)
```

The confirmation timestamp is the close of the bar that satisfies this condition.

**Classification:** INHERITED from R1 CHOCH definition.

---

## 9. Entry Convention

**Frozen rule:**

```
Entry = limit order at the broken CHOCH level:
  Bearish: entry at last HL price (sell)
  Bullish: entry at last LH price (buy)
```

The entry triggers when price returns to the broken CHOCH level (retest).

**Fill convention:** Next M1 bar open after price touches the CHOCH level.

**Fill constraint:** The next-bar open must be:
- For bearish: ≤ CHOCH level (allowing sell entry)
- For bullish: ≥ CHOCH level (allowing buy entry)

If the fill constraint is violated, the event is excluded (no entry).

**Classification:** INHERITED from R1 Trigger A (limit at broken CHOCH level).

---

## 10. Stop Definition

**Frozen rule:**

```
Stop = beyond the sweep extreme:
  Bearish: stop above last HH (the swept level)
  Bullish: stop below last LL (the swept level)
```

**Stop trigger:** Wick-based (same as BOS+OB):
- For bearish: bar.high > stop_level
- For bullish: bar.low < stop_level

**Stop fill:** At the exact stop_level price.

**Classification:** INHERITED from R1 Trigger A (beyond sweep extreme).

---

## 11. Payoff Definition

**Frozen rule:**

```
Path-dependent stop-or-horizon payoff:

If stop triggered before bar 120:
    R = directional return from fill to stop

If stop NOT triggered by bar 120:
    R = directional return from fill to bar 120 close
```

**Directional return:**
```
Bearish: R = (fill - exit) / fill × 10,000 bps
Bullish: R = (exit - fill) / fill × 10,000 bps
```

**Horizon:** 120 M1 bars (2 hours).

**Justification:** Consistent with the BOS+OB framework for comparability. Reversals may have larger moves, but 120 bars is a reasonable M1 window.

**Classification:** INHERITED from R3/CR2 path-dependent framework.

---

## 12. Transaction Cost Model

**Frozen rule:**

```
Tier 2 (primary): explicit 2.0-point round-trip spread
Tier 1 (descriptive): fill convention only
Tier 3 (stress): 2.0-point spread + 1.0-point slippage
```

**Classification:** RESEARCHER ASSUMPTION (same as BOS+OB R5/R6). Not observed from data.

**Justification:** The spread is a property of the broker/market, not the strategy. The same 2-point assumption applies. Labeled honestly as a researcher assumption.

---

## 13. Event Identity

**Frozen rule:**

```
One CHOCH event = one complete sequence:
  trend → sweep → CHOCH confirmation

One event per CHOCH confirmation.
Repeated touches of the CHOCH level do NOT create new events.
A new event requires a new trend → sweep → CHOCH sequence.
```

**Duplicate prevention:**
- After a CHOCH is confirmed, the trend is considered over.
- Any subsequent price action is in a new structural context.
- A new trend must be established before a new CHOCH event can occur.

**Classification:** NEW RESEARCHER CHOICE (not inherited from BOS+OB, which had different clustering characteristics).

---

## 14. Event Dependence

**Frozen rule:**

```
Event-level observations with HAC standard errors.

CHOCH events are expected to be much less frequent than BOS+OB:
  Estimated 5-15 events per week on M1.
  Events are separated by new trend establishment.
  Clustering is expected to be minimal.
```

**Classification:** RESEARCHER CHOICE. If clustering proves severe, the Control Session may require day-level aggregation (as in BOS+OB R5).

---

## 15. Directional Symmetry

**Frozen rule:**

```
Both bullish and bearish CHOCH reversals are included.
Returns are measured in the trade direction.
Neither direction is required to be positive.
Direction-specific results are descriptive only.
```

**Classification:** INHERITED from R4/R5 framework.

---

## 16. OOS Structure

**Frozen rule:**

```
OOS boundary: 2024-12-31
Discovery: 2021-04-12 to 2024-12-31
OOS: 2025-01-01 to 2026-04-10
```

**Classification:** INHERITED from R3/CR2.

---

## 17. Primary Metric

**Frozen rule:**

```
Primary metric: mean directional net payoff in basis points
  (including stopped events)
```

**Primary null:**
$$H_0: E[R] \leq 0$$

**Primary alternative:**
$$H_1: E[R] > 0$$

**Classification:** INHERITED from R3/CR2.

---

## 18. Statistical Test

**Frozen rule:**

```
One-sided t-test on event-level returns.
Alpha = 0.05.
HAC standard errors (Newey-West) with bandwidth = 10.
```

**Classification:** INHERITED from R3/CR2.

**Note:** If CHOCH events prove to be heavily clustered, the Control Session may require day-level aggregation with cluster-robust inference (as in BOS+OB R5).

---

## 19. Rare-Event Policy

**Frozen rule:**

```
No arbitrary minimum event count.
Report:
  - total events;
  - independent events;
  - calendar coverage;
  - OOS exposure;
  - confidence interval width;
  - chronological stability.
```

**Classification:** INHERITED from R3/CR2.

---

## 20. POI Requirement

**Frozen rule:**

```
NO separate POI requirement for the standalone test.

The CHOCH level itself serves as the structural reference.
The standalone hypothesis tests the pure CHOCH reversal phenomenon.
```

**Justification:**
- More objective (no POI validation ambiguity)
- More testable (fewer degrees of freedom)
- Focused on the core CHOCH phenomenon
- If positive, a future hypothesis could add POI validation

**Classification:** NEW RESEARCHER CHOICE (R1 Trigger A requires a POI, but the standalone test simplifies this).

---

## 21. Observable vs Interpretive

**Observable (tested):**
- Trend state (HH/HL or LH/LL sequence)
- Liquidity sweep (wick + close-back)
- CHOCH confirmation (close beyond swing)
- Entry at broken level
- Stop at sweep extreme
- Forward payoff

**Interpretive (not tested):**
- Institutional stop hunt
- Absorption at liquidity level
- Trapped traders providing liquidity
- Smart money reversal

---

## 22. Methodology Freeze Checklist

- [x] Prior trend definition frozen
- [x] Liquidity level definition frozen
- [x] Sweep definition frozen
- [x] Close-back rule frozen
- [x] CHOCH swing definition frozen
- [x] Confirmation timestamp frozen
- [x] POI requirement frozen (NONE)
- [x] Entry convention frozen
- [x] Stop frozen
- [x] Payoff frozen
- [x] Cost architecture frozen
- [x] Event identity frozen
- [x] Dependence treatment frozen
- [x] OOS split frozen
- [x] Primary statistical test frozen
- [x] Alpha frozen
- [x] Rare-event policy frozen
- [x] No outcome-derived choices

**All boxes checked. METHODOLOGY FROZEN.**

---

## 23. Comparison with BOS+OB

| Property | BOS+OB (R3) | CHOCH (R8) |
|----------|:-----------:|:----------:|
| Signal type | Continuation | Reversal |
| Prior trend required | No | Yes |
| Liquidity sweep required | No | Yes |
| Entry mechanism | First touch of OB | Retest of broken CHOCH level |
| Stop reference | OB distal edge | Sweep extreme |
| Event frequency | ~79/day (M1) | ~5-15/week (estimated) |
| POI requirement | OB+FVG | None (CHOCH level is the reference) |
| Payoff | Path-dependent 120-bar | Path-dependent 120-bar |
| Cost | 2-pt spread (researcher assumption) | 2-pt spread (researcher assumption) |

---

## 24. Expected Event Frequency

CHOCH events are expected to be much less frequent than BOS+OB:

- A trend must be established (2+ consecutive HH/HL or LH/LL)
- The trend must be swept
- The CHOCH must be confirmed
- Price must return for retest

Estimated frequency: **5-15 events per week on M1** (vs 79/day for BOS+OB).

This directly addresses the frequency-cost bottleneck that killed BOS+OB.

---

## 25. Risk Register

| Risk | Severity | Mitigation |
|------|:--------:|------------|
| Trend definition ambiguity | Medium | Frozen as 2+ consecutive swings; deterministic |
| Multiple sweeps of same level | Low | One event per sweep; new trend required for new event |
| CHOCH confirmation timing | Low | Defined as bar close; deterministic |
| Entry retest may not occur | Medium | Excluded events; no outcome bias |
| Low event count | Medium | Rare-event policy; CI-based evidence |
| Cost assumption may be wrong | Medium | Labeled as researcher assumption; not observed |

---

## 26. Architecture Score

| Dimension | Score | Rationale |
|-----------|:-----:|-----------|
| Structural fidelity | 5 | Faithful to R1 CHOCH definition |
| Determinism | 5 | All components are deterministic |
| Causal integrity | 5 | No lookahead; events identified at confirmation |
| Economic clarity | 5 | Payoff is explicit; path-dependent |
| OOS validity | 5 | Chronological split frozen |
| Cost realism | 4 | Researcher assumption; labeled honestly |
| Event independence | 5 | One event per CHOCH; no inflation |
| Rare-event suitability | 5 | Low frequency; CI-based evidence |
| Simplicity | 5 | Minimal degrees of freedom; no POI requirement |
| Scientific information value | 5 | Tests reversal vs continuation; different economic mechanism |

**Architecture score: 4.9 / 5**

---

*End of SMC-R8 CHOCH Economic Methodology*
