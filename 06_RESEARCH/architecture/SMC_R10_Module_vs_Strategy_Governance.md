# SMC-R10 — Module vs Strategy Governance

**Milestone**: SMC-R10
**Status**: COMPLETE
**Date**: 2026-08-27

---

## 1. Standalone Strategy vs Specialist Module

### Standalone Strategy

A complete trade-generating system with its own economic expectancy. Active continuously. Produces signals independently.

### Specialist Module

A component with:
- A specific economic role
- A clearly defined activation condition
- Independently validated value
- A restricted operating domain

**A module does NOT have to be active continuously.** Silence outside the activation domain is acceptable and expected.

Example:
```
TREND MODULE
  active only in validated trend conditions
  silent in ranges ✓

RANGE MODULE
  active only in validated range conditions
  silent in trends ✓

REVERSAL MODULE
  active only after validated reversal conditions
  silent during continuation ✓
```

---

## 2. Critical Module Rule

A module may NOT become valid merely because:

```
Base Strategy + Filter Module → better historical PnL
```

Instead:

> The module itself must have an independently defensible economic role.

### Acceptable

> Module A has positive conditional expectancy specifically in regime X.

This is a testable hypothesis about Module A's independent economic contribution.

### Unacceptable

> Adding Module A improved backtest PnL.

This is combination mining.

---

## 3. Two Bot Architectures

### Architecture A — Killer Strategy

```
ONE M4/M5 STRATEGY
```

A single independently validated economic engine. Simple, robust, self-contained.

### Architecture B — Specialist Modules

```
                ┌── TREND MODULE (M4 validated)
                │
MARKET STATE ───┼── RANGE MODULE (M4 validated)
                │
                └── REVERSAL MODULE (M4 validated)
```

Each module must qualify independently (M4). The interaction must be specified before combined OOS testing.

**Both architectures are valid.** The programme should not force one over the other.

---

## 4. Module Interaction Rule

Before combination:

1. Module A independently validated (M4)
2. Module B independently validated (M4)
3. Economic roles are complementary
4. Interaction mechanism is defined ex ante
5. Activation overlap is explicitly specified
6. Combined test is treated as a NEW hypothesis
7. Combined OOS test is untouched

### Forbidden

```
A, B, C, D, E
    →
test every combination
    →
pick best equity curve
```

This is the anti-combination-mining rule.

---

## 5. Conditioning Module

A conditioning module has validated evidence that it changes the economic behavior of another independently validated generator.

Example:
```
Base module expectancy: E[R]
Conditioning hypothesis: E[R | state X] > E[R]
```

### Requirements

- The conditioning module itself must have an independently defensible role
- The conditional hypothesis must be frozen before testing
- The improvement must be statistically and economically significant
- The combined test must use fresh OOS data

### Prohibition

A conditioning module cannot be justified merely by improving historical results.

---

## 6. Module Independence

Each module must be independently validated before combination. The validation must demonstrate:

- Positive net expectancy (Level 2)
- Survival under stronger validation (Level 3)
- Defined economic role
- Frozen methodology
- No dependence on other modules for its own validity

A module that only works when combined with another is NOT independently validated.

---

## 7. Bot Inclusion Standard

A module can be admitted into the eventual bot only when:

```
Scientific foundation (Level 1)
    +
Positive net expectancy (Level 2)
    +
Independent validation (Level 3)
    +
Defined economic role
    +
Realistic execution
    +
Known risk characteristics
    +
Combined OOS validation (if multi-module)
    +
Execution validation
```

The final bot still requires combined OOS validation and execution validation.

---

## 8. Economic Generator vs Conditioning Module

### Economic Generator

Creates positive payoff itself. Has standalone positive expectancy. Can be active independently.

### Conditioning Module

Has validated evidence that it changes the economic behavior of another independently validated generator. Cannot be justified merely by improving historical results.

A conditioning module requires:
- Independent economic role definition
- Frozen conditional hypothesis
- Separate OOS validation of the conditional effect
- No reliance on the base module's PnL for justification

---

## 9. Failed Module Reuse

When a standalone experiment fails (net < 0):

**It CANNOT automatically become**:
- A filter for another module
- A confirmation signal
- A regime label
- A risk modifier

**It MAY be preserved as**:
- Background knowledge for genuinely new hypotheses
- Scientific reference for structural geometry
- Starting point for a new, independently justified hypothesis

**Any reuse requires**:
- A new, independently testable economic hypothesis
- New methodology design (R3-level)
- New control review
- No reliance on the failed experiment's results for justification

---

## 10. Current SMC Architecture Status

### Level 1 (Scientific Effect): Both PASS
- BOS+OB: gross +1.01 bps ✓
- CHOCH: gross +0.89 bps ✓

### Level 2 (Economic Candidate): Both FAIL
- BOS+OB: net < 0 ✗
- CHOCH: net < 0 ✗

### Level 3 (Validated Module): None
- No modules have reached M4

### Level 4 (Deployment): Not applicable
- No validated modules exist

### Bot Architecture Status
- Architecture A (Killer Strategy): No candidate
- Architecture B (Specialist Modules): No validated modules

---

*End of SMC-R10 Module vs Strategy Governance*
