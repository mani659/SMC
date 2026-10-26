# SMC-R8-CR — CHOCH Reversal Methodology Integrity Review

**Milestone**: SMC-R8-CR
**Status**: COMPLETE
**Date**: 2026-08-27
**Decision**: B — R8 VALID WITH CONTROLLED AMENDMENT

---

## 1. Purpose

Determine whether the frozen CHOCH methodology is truly deterministic, causally observable, economically coherent, and free of hidden researcher freedom before the first empirical experiment.

---

## 2. Critical Audit A — Prior Trend Definition

R8 states: "2+ consecutive HH/HL or LH/LL using N=5 swings."

### Audit Findings

| Question | Answer | Status |
|----------|--------|:------:|
| What constitutes the first confirmed swing? | N=5 swing detection (R1 framework) | ✓ Deterministic |
| Are both HH and HL required? | Yes — both must be present | ✓ |
| How many alternating swings? | Minimum 3 swing highs + 3 swing lows | ✓ |
| When does trend officially begin? | When the 3rd HH and 3rd HL are both confirmed | ✓ |
| Can trend remain valid after equal high/low? | No — must be strictly higher/lower | ✓ |
| What ends the prior trend? | CHOCH confirmation | ✓ |
| Can same swing belong to trend and CHOCH? | No — CHOCH swing is the protected level within the trend | ✓ |

### Causal Integrity

The trend state uses only swing highs and swing lows that have been confirmed (close beyond N-bar swing). No future information is required.

**Classification**: DETERMINISTIC — no issues.

---

## 3. Critical Audit B — "Final Extreme of the Trend" ⚠️

R8 states: "The liquidity level is the final extreme of the established trend."

### The Problem

"Final extreme of the trend" is ambiguous. Consider:

```
Trend: HH1=2000, HL1=1950, HH2=2050, HL2=2000, HH3=2100
Sweep: bar wicks above 2100, closes below 2100
Then: price drops, but then rallies to HH4=2150
Then: price drops again, CHOCH confirmed
```

At the time of the sweep, the "last HH" is 2100. But after HH4=2150 forms, the "last HH" becomes 2150. The "final extreme of the trend" is 2150, not 2100.

**If R8 means "the most recent HH at the time of the sweep"**: this is causal. The sweep level is 2100.

**If R8 means "the final HH before the trend ends"**: this requires hindsight. The sweep level would be 2150, but we wouldn't know that until after the CHOCH.

### Resolution Required

R8 must clarify: the liquidity level is **the most recent HH/LL at the time of the sweep**, not the "final extreme of the trend."

This is a wording clarification, not an economic change. The sweep occurs at whichever HH/LL is most recent when the sweep bar forms.

### Classification

> **AMENDMENT REQUIRED** — clarify wording to ensure causal identification.

---

## 4. Critical Audit C — "Last HL/LH in the Trend" ⚠️

R8 states: "The CHOCH swing is the last swing in the trend direction that must be broken."

### The Problem

"Last HL in the uptrend" is ambiguous. After the sweep, new HLs might form before the CHOCH is confirmed.

```
Sweep at HH3=2100
Then: price drops, forms HL3=2050
Then: price rallies, forms HH4=2150
Then: price drops, forms HL4=2100
Then: CHOCH confirmed (close < HL4=2100)
```

At sweep time, the "last HL" is HL2=2000. At CHOCH time, the "last HL" is HL4=2100.

**Which one is the CHOCH swing?**

### Resolution Required

R8 must clarify: the CHOCH swing is **the most recent HL/LH at the time of the sweep**, not the "last HL/LH in the trend" (which could change after the sweep).

This is a wording clarification, not an economic change. The CHOCH swing is fixed at the sweep timestamp.

### Classification

> **AMENDMENT REQUIRED** — clarify wording to ensure causal identification.

---

## 5. Critical Audit D — Liquidity Sweep

R8 defines: "wick pierces + close back inside."

### Audit Findings

| Question | Answer | Status |
|----------|--------|:------:|
| Exact reference level | Most recent HH/LL at sweep time (amended) | ✓ |
| Wick must exceed by any amount? | Yes — wick > level | ✓ |
| Equality handling | Strict inequality (wick > level) | ✓ |
| Intrabar touch | Wick-based; deterministic | ✓ |
| Close-back definition | Close < level (bearish) or close > level (bullish) | ✓ |
| Must occur after trend established? | Yes — sweep is step 2 in event chain | ✓ |
| Multiple sweeps before CHOCH? | First sweep counts; repeated sweeps of same level = one event | ✓ |

### Causal Integrity

The sweep is identified at the bar close that satisfies both conditions. No future information required.

**Classification**: DETERMINISTIC — no issues (after Audit B/C amendments).

---

## 6. Critical Audit E — CHOCH Confirmation

R8 states: "close beyond the CHOCH swing."

### Audit Findings

| Question | Answer | Status |
|----------|--------|:------:|
| Which bar closes? | First bar where close < CHOCH swing (bearish) or close > CHOCH swing (bullish) | ✓ |
| Equality counts? | No — strict inequality | ✓ |
| Timestamp known at? | Bar close | ✓ |
| Sweep and CHOCH on same bar? | Possible but unlikely; sweep requires wick > HH, CHOCH requires close < HL. If both occur on same bar, it's valid | ✓ |
| Sweep must occur before CHOCH? | Yes — by construction (sweep is identified first) | ✓ |
| Maximum sweep→CHOCH interval? | Not specified — intentional | ✓ |

### Causal Integrity

CHOCH confirmation uses only the CHOCH swing (identified at sweep time) and the current bar's close. No future information required.

**Classification**: DETERMINISTIC — no issues.

---

## 7. Critical Audit F — Retest Entry ⚠️

R8 says: "entry on retest of broken CHOCH level."

### Audit Findings

| Question | Answer | Status |
|----------|--------|:------:|
| What constitutes a retest? | Price wick touches CHOCH level | ✓ |
| Does wick touch count? | Yes — same as BOS+OB first-touch convention | ✓ |
| Does price have to close back? | No — wick touch is sufficient | ✓ |
| Can same bar as CHOCH create retest? | If CHOCH bar also touches the CHOCH level, it could be a retest. But CHOCH confirmation requires close beyond the swing, so the bar likely traded through the level. Need to clarify: retest must be AFTER CHOCH confirmation | ⚠️ |
| How many retests allowed? | Only first retest counts | ✓ |
| What if price gaps through? | Fill constraint prevents entry; event excluded | ✓ |
| Timestamp of retest | Bar close that touches CHOCH level | ✓ |

### Resolution Required

R8 must clarify: the retest must occur **after** CHOCH confirmation. The CHOCH confirmation bar itself cannot serve as the retest bar (because the CHOCH bar's close is beyond the swing, meaning the bar likely traded through the level in the confirmation direction, not as a retest).

### Classification

> **AMENDMENT REQUIRED** — clarify retest timing.

---

## 8. Critical Audit G — Entry Price

R8 says: "limit at broken CHOCH level, fill at next-bar open."

### Audit Findings

| Question | Answer | Status |
|----------|--------|:------:|
| Limit is hypothetical? | Yes — order placed at CHOCH level | ✓ |
| Next-bar open is credited fill? | Yes — same as BOS+OB convention | ✓ |
| Fill regardless of price at level? | No — fill constraint enforced | ✓ |
| Gap-through cases? | Handled by fill constraint | ✓ |
| Next-bar open causally after retest? | Yes — retest is detected at bar close, entry is next bar | ✓ |

### Causal Integrity

The entry convention is identical to BOS+OB: next-bar open after retest detection, with fill constraint.

**Classification**: DETERMINISTIC — no issues.

---

## 9. Critical Audit H — Stop

R8 states: "stop beyond sweep extreme."

### Audit Findings

| Question | Answer | Status |
|----------|--------|:------:|
| Exact sweep extreme | Most recent HH (bearish) or LL (bullish) at sweep time | ✓ |
| Wick high/low used? | Yes — bar.high > stop for bearish; bar.low < stop for bullish | ✓ |
| Stop trigger | Wick-based | ✓ |
| Exact stop price | The HH/LL price level | ✓ |
| Zero buffer? | Yes — no buffer | ✓ |
| Long/short mirrored? | Yes | ✓ |

### Causal Integrity

The stop level is fixed at the sweep time. No future information required.

**Classification**: DETERMINISTIC — no issues.

---

## 10. Critical Audit I — Payoff

R8 inherits: "stop or 120-bar horizon."

### Audit Findings

| Question | Answer | Status |
|----------|--------|:------:|
| Stop exits in primary payoff? | Yes — included in mean | ✓ |
| Stop return formula | Directional return from fill to stop level | ✓ |
| 120-bar endpoint formula | Directional return from fill to bar 120 close | ✓ |
| Directional symmetry | Bearish: (fill-exit)/fill×10000; Bullish: (exit-fill)/fill×10000 | ✓ |
| Stop touched on 120th bar? | Stop takes precedence (path-dependent) | ✓ |
| Same-bar ambiguity | Same as BOS+OB — M1 wick-based handling | ✓ |

### Causal Integrity

The payoff is path-dependent and identical to the BOS+OB framework.

**Classification**: DETERMINISTIC — no issues.

---

## 11. Critical Audit J — Cost Model

R8 uses: "2-point round-trip spread assumption."

### Audit Findings

| Question | Answer | Status |
|----------|--------|:------:|
| Inherited from BOS+OB? | Yes — same assumption | ✓ |
| One-way or round-trip? | Round-trip (2× per side) | ✓ |
| Where in payoff? | Subtracted from gross return | ✓ |
| Applied at entry and exit? | Yes — 2× spread_bps | ✓ |
| Interaction with fill convention? | Same as BOS+OB — fill convention is distinct from spread cost | ✓ |
| Classification | RESEARCHER ASSUMPTION | ✓ |

### Note

The cost model is identical to BOS+OB R5/R6. The Control Review notes this but does not object — the spread is a property of the broker/market, not the strategy.

**Classification**: RESEARCHER ASSUMPTION — labeled honestly.

---

## 12. Critical Audit K — Event Identity

R8 uses: "one event per CHOCH confirmation."

### Audit Findings

| Question | Answer | Status |
|----------|--------|:------:|
| One event per sweep? | Yes — one sweep → one CHOCH → one event | ✓ |
| Multiple sweeps? | First sweep counts; repeated sweeps of same level = one event | ✓ |
| One trend, multiple CHOCHs? | After CHOCH, trend is over; new trend required for new event | ✓ |
| Repeated retests? | Only first retest counts | ✓ |
| Opposing CHOCHs in same episode? | After first CHOCH, trend is over; opposing CHOCH requires new trend | ✓ |
| Event expiration | After CHOCH confirmation, event is active until retest or invalidation | ✓ |

### Causal Integrity

Event identity is clean: one complete sequence = one event. No inflation.

**Classification**: DETERMINISTIC — no issues.

---

## 13. Critical Audit L — Event Independence

R8 uses: "event-level HAC."

### Assessment

CHOCH events are expected to be much less frequent than BOS+OB. However, R8 has not empirically verified this. The "5-15 events/week" claim is planning intuition, not evidence.

**Is HAC sufficient?** For sparse, well-separated events, HAC should be adequate. If clustering proves severe, the Control Session may require day-level aggregation.

**Classification**: APPROPRIATE as a starting point — may need adjustment after R9 extraction.

---

## 14. Critical Audit M — Economic Independence

R8 defines: "one event per CHOCH confirmation."

**Can one trend contain multiple CHOCH signals?** After the first CHOCH, the trend is considered over. So no — one trend produces at most one CHOCH event.

**But what about new trends?** A new trend can form after a CHOCH, leading to a new CHOCH event. These are genuinely independent structural episodes.

**Classification**: ECONOMICALLY INDEPENDENT — one event per structural episode.

---

## 15. Critical Audit N — Low Frequency Claim

R8 claims: "estimated 5-15 events/week."

### Assessment

This estimate is **not empirically supported**. It is planning intuition based on the structural requirements (trend → sweep → CHOCH → retest).

**Classification**: PLANNING INTUITION — must be labeled as such. The actual frequency will be measured in R9.

**The frequency estimate must NOT be used as evidence that CHOCH is economically attractive.**

---

## 16. Critical Audit O — M1/M5 Timeframe ⚠️

R8 says: "CHOCH execution is M1/M5."

### The Problem

R8 does not freeze a single execution timeframe. The canonical dataset is M1. If both M1 and M5 are permitted, that creates two models.

### Resolution Required

R8 must freeze: **execution timeframe = M1** (consistent with the canonical dataset).

M5 is mentioned in R1 as a possible execution timeframe, but for this standalone test, we use M1.

### Classification

> **AMENDMENT REQUIRED** — freeze M1 as the execution timeframe.

---

## 17. Critical Audit P — OOS

R8 inherits: "2024-12-31 split."

Same as BOS+OB. Appropriate for a parameter-free structural rule.

**Classification**: CORRECT — no issues.

---

## 18. Critical Audit Q — Primary Endpoint

R8 uses: "mean directional net trade payoff."

Same as BOS+OB. One primary estimand. Stop outcomes included.

**Classification**: CORRECT — no issues.

---

## 19. Critical Audit R — Observable vs Interpretive

R8 separates observable geometry from market-story interpretation. The experiment tests the observable structure, not the institutional explanation.

**Classification**: CORRECT — no issues.

---

## 20. Critical Audit S — Researcher Degrees of Freedom

| Choice | Value | Origin | Classification |
|--------|-------|--------|:--------------:|
| Swing N | 5 | R1/R2 | Inherited |
| Trend length | 2+ swings | R8 | Researcher design |
| Sweep definition | wick + close-back | R1 | Inherited |
| Sweep reference | most recent HH/LL at sweep time | R8 (amended) | Researcher design |
| CHOCH reference | most recent HL/LH at sweep time | R1/R8 (amended) | Researcher design |
| Entry timeframe | M1 | R8 (amended) | Researcher design |
| Entry | broken CHOCH level | R1/R8 | Inherited |
| Fill | next-bar open | R8 | Inherited |
| Stop | sweep extreme | R1/R8 | Inherited |
| Horizon | 120 bars | Inherited | Inherited |
| Cost | 2 points | Assumption | Researcher assumption |
| OOS split | 2024-12-31 | Inherited | Inherited |
| HAC | 10 | Inherited | Inherited |
| Event identity | one per CHOCH | R8 | Researcher design |

**All rows classified. No unresolved items.**

---

## 21. Amendment Summary

| # | Issue | Type | Change Required |
|:-:|-------|------|-----------------|
| A | "Final extreme of the trend" is ambiguous | Wording | Clarify as "most recent HH/LL at the time of the sweep" |
| B | "Last HL/LH in the trend" is ambiguous | Wording | Clarify as "most recent HL/LH at the time of the sweep" |
| C | Timeframe not frozen | Methodology | Freeze as M1 (canonical dataset) |
| D | Retest timing not specified | Methodology | Clarify: retest must be AFTER CHOCH confirmation |
| E | Frequency estimate is planning intuition | Documentation | Label as such; not evidence |

---

## 22. What R8 Gets Right

Despite the amendments needed, R8 is structurally sound:

1. **The event chain is causally identifiable** — each step uses only information available at that timestamp (after amendments).
2. **The hypothesis is genuinely new** — reversal vs continuation tests a different economic mechanism.
3. **No POI requirement** — simplifies the standalone test and reduces degrees of freedom.
4. **Clean event identity** — one event per CHOCH, no clustering issues like BOS+OB.
5. **Observable vs interpretive separation** — correct scientific discipline.

---

*End of SMC-R8-CR Review*
