# SMC-R11 — Rare-Event Economic Discovery & Specialist-Module Framework

**Milestone**: SMC-R11
**Status**: COMPLETE
**Date**: 2026-08-27
**Purpose**: Create governance framework for rare high-expectancy specialist modules

---

## 1. Why R11 Was Required

R10 established the four-level qualification hierarchy. But the programme needed an explicit framework for:

1. How to discover and qualify rare events that fire infrequently
2. How to distinguish "rare but valuable" from "rare and weak"
3. How to combine specialist modules without combination mining
4. How to pursue Architecture B (specialist modules) responsibly

R11 creates this framework.

---

## 2. Core Distinctions

The framework must explicitly maintain:

```
rare ≠ weak
frequent ≠ good
positive expectancy ≠ scalable
validated module ≠ production bot
```

These distinctions prevent two failure modes:

### False Rejection
Rare event discarded because N is small.

### False Acceptance
Rare event accepted because a tiny sample happens to have positive mean.

---

## 3. Five Dimensions of Module Quality

| Dimension | What It Measures |
|-----------|-----------------|
| Frequency | How often the event occurs |
| Evidence sufficiency | Whether enough independent observations exist to estimate expectancy |
| Economic magnitude | Expected net payoff per opportunity |
| Aggregate contribution | Expected total contribution across available opportunities |
| Scalability | How much capital can actually be deployed |

These are separate. A module can rank high on some and low on others.

---

## 4. Minimum Economic Threshold

Preserved from R10:

$$E[R_{net}] > 0$$

after realistic, frozen costs. Nothing else required at Level 2.

No universal minimum bps, dollars, annual return, or event count.

---

## 5. Evidence Sufficiency Framework

### What Must Be Reported

Future studies must report:

- Independent event count
- Calendar duration
- Confidence interval width
- Chronological split (discovery/OOS)
- Effect magnitude (mean net payoff)
- Cost burden (assumed vs observed)
- Dependence structure
- Execution uncertainty

### Classification

Choose exactly one:

| Classification | Meaning |
|:--------------:|---------|
| **INSUFFICIENT** | Not enough evidence to decide. Continue observation. |
| **POSITIVE CANDIDATE** | Positive net expectancy with adequate evidence. |
| **NEGATIVE** | Net expectancy ≤ 0 with adequate evidence. |
| **INCONCLUSIVE** | Evidence ambiguous. Cannot classify. |

### Do NOT Set Universal N Thresholds

The Control Session decides whether evidence is sufficient for the specific phenomenon. A rare event with N=30 and tight CI may have more evidence than a frequent event with N=500 and wide CI.

---

## 6. Rare-Event Inconclusive State

This is critical. Define:

> `INCONCLUSIVE — EVIDENCE INSUFFICIENT`

This prevents:
- False rejection of genuinely rare phenomena
- False acceptance of tiny-sample noise

When evidence is insufficient, the correct action is:
- Continue observation
- Do NOT declare the hypothesis dead
- Do NOT promote it to M3
- Return to evidence accumulation

---

## 7. Module Economic Roles

### A — Trade Generator

Produces its own positive expectancy. Active when its events occur.

### B — Regime Specialist

Produces positive expectancy only within a clearly defined market state.

### C — Risk/Exposure Modifier

Changes exposure according to a validated economic relationship.

### D — Trade Suppressor

Avoids situations where a base module's expectancy is demonstrably worse.

**Critical rule**: Roles C and D cannot be validated merely by improving another strategy's backtest. They require their own defensible economic hypothesis.

---

## 8. Standalone Module

```
Module event
    ↓
net payoff > 0
    ↓
M3 (Economic Candidate)
    ↓
independent validation
    ↓
M4 (Validated Module)
```

The module may be rare. It does not need to fire continuously.

---

## 9. Specialist Module

A specialist module is active only under a predefined state.

Example:
```
Trend State → Trend module active
Range State → Range module active
```

**The regime definition must be frozen independently of module outcomes.**

Forbidden:
```
test 20 regime definitions → choose the one where the module performs best
```

This is regime mining, identical to timeframe mining.

---

## 10. Conditioning Module

If Module B conditions Module A:

Hypothesis: $E[R_A | B] > E[R_A]$

Requirements:
- Ex-ante specified
- Economically motivated
- Independently validated
- NOT justified by "B improved A's historical PnL"

---

## 11. Module Independence

Three dimensions:

| Dimension | What It Means |
|-----------|---------------|
| Scientific independence | Information source is not a duplicate of the same structural event |
| Economic independence | Module has a distinct payoff mechanism |
| Sampling independence | Validation evidence is not entirely dependent on the same small set of events |

Do NOT require statistical zero correlation. The question is:

> Does Module B contain genuinely separate information or merely repackage Module A?

---

## 12. Module Complementarity

A complementary module should have a distinct domain:

```
TREND MODULE — strong in directional continuation
RANGE MODULE — strong in mean-reversion
REVERSAL MODULE — strong near structural exhaustion
```

Before combined testing:
- Both modules independently qualify (M4)
- Economic roles are explicit
- Activation overlap is defined
- Conflict resolution is frozen
- Capital allocation is frozen
- Combined hypothesis is predeclared

---

## 13. Module Silence

A specialist module is allowed to be inactive for long periods.

Its value is NOT measured by number of trades.

Instead by:
- Conditional expectancy
- Evidence sufficiency
- Opportunity quality
- Economic contribution
- Execution feasibility

---

## 14. Capital Contribution vs Positive Expectancy

A module with $E[R] > 0$ may have very low expected annual contribution.

That is not a scientific failure.

```
Economically positive ≠ Economically scalable
```

The deployment layer assesses:
- Expected annual contribution
- Capital allocation
- Drawdown
- Capacity
- Turnover
- Opportunity frequency

Do NOT calculate these at the module validation stage.

---

## 15. Module Evidence Ladder

| Level | Name | Meaning |
|:-----:|------|---------|
| M0 | Phenomenon | Observable pattern exists |
| M1 | Scientific Primitive | Pattern is deterministic and reproducible |
| M2 | Predictive Primitive | Pattern contains predictive information |
| M3 | Economic Candidate | Positive net expectancy after costs |
| M4 | Validated Module | Survives stronger validation |
| M5 | Deployment Candidate | Suitable for bot inclusion |

Current SMC status:
- BOS+OB: M2 PASS, M3 FAIL
- CHOCH: M2 PASS, M3 FAIL

---

*End of SMC-R11 Rare-Event Module Framework*
