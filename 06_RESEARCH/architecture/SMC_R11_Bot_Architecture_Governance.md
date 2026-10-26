# SMC-R11 — Bot Architecture Governance

**Milestone**: SMC-R11
**Status**: COMPLETE
**Date**: 2026-08-27

---

## 1. Architecture A — Killer Strategy

One independently validated strategy with:
- Positive net expectancy
- Strong OOS evidence
- Realistic execution
- Sufficient risk-adjusted economics

It enters the bot alone. No need to manufacture modules if one strategy is sufficient.

---

## 2. Architecture B — Specialist Modules

A small number of validated modules:

```
Market State Router
        │
   ┌────┼────┐
   ↓    ↓    ↓
 TREND RANGE REVERSAL
   │    │    │
   └────┴────┘
        ↓
   Execution layer
```

**The router itself must not be invented solely to make weak modules profitable.** Every component has a separate research burden.

---

## 3. Conflicting Modules

If two modules produce opposing signals simultaneously, an ex-ante arbitration mechanism is required.

Possible future mechanisms:
- Mutually exclusive regime states
- Priority hierarchy
- Independent capital sleeves
- Simultaneous execution where economically justified

Do NOT choose one now. The framework only requires that the mechanism be defined before combined testing.

---

## 4. Module Combination Governance

### Forbidden

```
A + B + C
    →
historical backtest
    →
best result selected
```

### Allowed

```
A independently validated (M4)
B independently validated (M4)
        ↓
explicit economic interaction
        ↓
frozen combined hypothesis
        ↓
combined OOS
```

The interaction is a new scientific/economic experiment.

---

## 5. Failed Artifact Reuse

A failed standalone artifact MAY survive as background knowledge.

It does NOT automatically become:
- Filter
- Regime detector
- Confirmation
- Risk modifier

To reuse it economically, define a NEW hypothesis.

### Not Acceptable

> "BOS+OB failed, but adding CHOCH improved it."

### Potentially Acceptable Future Question

> "A validated reversal-state classifier changes the expected payoff distribution of an independently validated continuation module."

But only after both underlying economic roles exist independently.

---

## 6. Future SMC Research Gate

Any future SMC candidate must start from:

> new scientific/economic hypothesis

Not:
- Another combination
- Another timeframe
- Another filter

The candidate must explain:
1. What market condition it detects
2. What economic payoff it should create
3. Why that payoff is different from closed mechanisms
4. How it will be falsified

---

## 7. Dual Architecture Pursuit

Architecture A and Architecture B can be pursued simultaneously IF:
- Each has its own independent research thread
- Neither is justified by the other's results
- No cross-contamination of evidence
- Separate Control Session authorization for each

The programme should not force one architecture over the other. The evidence determines which is appropriate.

---

## 8. Current SMC Application

### Architecture A Status
No candidate. Both tested models (BOS+OB, CHOCH) failed Level 2.

### Architecture B Status
No validated modules. Both tested models failed Level 2.

### What Would Restart the Programme

A genuinely new hypothesis answering:
1. What new scientific/economic question?
2. Why distinct from closed paths?
3. What economic mechanism?
4. Minimum evidence needed?
5. What constitutes positive economics?
6. What constitutes deployment readiness?

---

*End of SMC-R11 Bot Architecture Governance*
