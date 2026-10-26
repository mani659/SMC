# SMC-R10 — Economic Qualification Framework

**Milestone**: SMC-R10
**Status**: COMPLETE
**Date**: 2026-08-27
**Purpose**: Correct governance gap between "positive expectancy" and "deployment readiness"

---

## 1. Why R10 Was Required

SMC-R4 and SMC-R9 both found tiny gross positive effects (+1.01 and +0.89 bps) that failed to survive transaction costs. The programme correctly rejected both as M3/M4 candidates. But this created a governance question:

> Should the programme define "economic viability" as merely "large enough to trade," or should it first establish "strictly positive net expectancy" as the minimum scientific threshold?

R10 establishes the answer: **positive net expectancy is the minimum threshold for Level 2 (Economic Candidate).** Deployment suitability is a separate, later gate.

---

## 2. The Four-Level Qualification Hierarchy

```
Level 1: Scientific Effect
    "Does the event contain predictive information?"
    ↓
Level 2: Economic Candidate
    "Does it produce positive expected net payoff after realistic costs?"
    ↓
Level 3: Validated Economic Module
    "Does the positive expectancy survive stronger validation?"
    ↓
Level 4: Deployment Candidate
    "Is it sufficiently attractive for actual bot deployment?"
```

These are NOT the same thing. Collapsing them creates governance failures.

---

## 3. Level 1 — Scientific Effect

**Question**: Is there evidence that the event contains predictive information?

**Evidence types**:
- Positive gross expectancy
- Conditional distributional difference
- Predictive relationship

**Threshold**: Any credible evidence of information content.

**Current SMC findings**:
- BOS+OB: Level 1 PASS (gross +1.01 bps)
- CHOCH: Level 1 PASS (gross +0.89 bps)

**Do NOT reject at Level 1 merely because the effect is small.**

---

## 4. Level 2 — Economic Candidate (M3)

**Question**: Does the event produce positive expected payoff AFTER realistic costs?

**Minimum threshold**:

$$E[R_{net}] > 0$$

with appropriate uncertainty quantification.

**Requirements**:
- Frozen methodology
- Realistic cost model
- Chronological OOS validation
- Independence-aware inference
- No hidden researcher degrees of freedom

**This is the minimum M3 gate.**

**Current SMC findings**:
- BOS+OB: Level 2 FAIL (net < 0 after costs)
- CHOCH: Level 2 FAIL (net < 0 after costs)

**Do NOT create arbitrary universal thresholds** (e.g., +5 bps, +$10, 10% annual). These are instrument-, capital-, and execution-dependent.

---

## 5. Level 3 — Validated Economic Module (M4)

**Question**: Does the positive net expectancy survive stronger validation?

**Additional requirements beyond Level 2**:
- Strict chronological OOS
- Dependence-aware inference
- Realistic execution assumptions
- No methodology drift
- Temporal stability
- Event-independence treatment

**This is the M4 gate.**

**Current SMC findings**: No modules have reached Level 3.

---

## 6. Level 4 — Deployment Candidate

**Question**: Is the validated module suitable for actual bot deployment?

**Deployment dimensions** (NOT requirements for proving positive expectancy):
- Capital efficiency
- Maximum drawdown
- Expected drawdown
- Variance / tail risk
- Turnover
- Capacity
- Execution burden
- Opportunity frequency
- Position overlap
- Time-in-market

**This is the production gate.** It is separate from Levels 1-3.

**Do NOT collapse Level 2 and Level 4.**

---

## 7. Minimum Economic Threshold

The minimum threshold for an economic candidate (Level 2) is:

$$E[R_{net}] > 0$$

after realistic, frozen transaction costs.

That is ALL. No additional universal minimum applies.

**Specifically**:
- No minimum bps threshold
- No minimum dollar threshold
- No minimum annual return
- No minimum trade count (separate from evidence sufficiency)

These are deployment-layer considerations, not scientific thresholds.

---

## 8. Evidence Sufficiency vs Event Frequency

These are separate dimensions:

| Dimension | What It Measures |
|-----------|-----------------|
| Event frequency | How often the signal occurs |
| Evidence sufficiency | Whether enough independent observations exist to estimate expectancy credibly |
| Economic attractiveness | Whether the resulting expectancy justifies deployment |

A module may be rare and still qualify if:
- Net expectancy is positive
- Evidence is sufficient (CI is tight enough)
- Events are independently identified
- OOS evidence supports it
- Costs are included

**Do NOT impose arbitrary minimum event counts.**

---

## 9. Expectancy vs Total Profit

Positive expectancy per independent event does NOT imply high total annual PnL.

Example A:
- +$0.10 expected net payoff
- 20 independent events/year
- Total: +$2.00/year
- **Scientifically valid, economically low-scale**

Example B:
- +$100 net/event
- 2 events/year
- Total: +$200/year
- **Scientifically valid, economically concentrated**

Do not reject either solely on scale. The deployment layer handles scale.

---

## 10. Small Positive Expectancy

**Small positive expectancy is still positive expectancy.**

Do NOT invent a universal minimum economic edge.

However, deployment should separately ask:

> Is the magnitude large enough after considering capital, execution, risk, and opportunity frequency?

This creates:

```
Economically positive ≠ Economically scalable
```

A rare module can have positive expectancy but very low aggregate annual contribution. This should not invalidate its scientific/economic status.

---

## 11. Rare Event Evidence Framework

Future studies should report:

- Mean net expectancy
- Confidence interval
- Number of independent events
- Calendar exposure
- OOS observations
- Dependence treatment

Do NOT assume p < 0.05 alone is sufficient.

Do NOT require enormous sample sizes when the event is intrinsically rare.

The framework should balance:

> effect magnitude + uncertainty + independent evidence

---

## 12. Failed Artifact Treatment

When a standalone experiment fails (net < 0):

**Classify as**:
- Scientifically informative (gross effect exists)
- Economically non-viable under tested architecture
- NOT automatically a filter, confirmation, or regime label

**Preserve as**:
- Background knowledge for genuinely new future hypotheses
- NOT as a rescue component for the failed model

**Example**:
- BOS+OB gross effect: scientifically informative
- BOS+OB as a "trend filter" for CHOCH: NOT permitted without independent hypothesis

---

## 13. Future Research Gate

Any NEW SMC research direction must answer:

1. What new scientific/economic question is being asked?
2. Why is it distinct from closed paths?
3. What economic mechanism is hypothesized?
4. What is the minimum evidence needed?
5. What constitutes positive economics?
6. What constitutes deployment readiness?

**No automatic new experiment.**

---

*End of SMC-R10 Economic Qualification Framework*
