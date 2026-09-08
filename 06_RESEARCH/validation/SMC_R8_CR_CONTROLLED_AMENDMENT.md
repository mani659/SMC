# SMC-R8-CR Controlled Amendment

**Date**: 2026-08-27
**Origin**: SMC-R8-CR identified four issues requiring clarification
**Status**: FROZEN — applies to SMC-R9 and beyond

---

## Amendment A: Final Extreme Causal Identification

### Original R8

> "The liquidity level is the final extreme of the established trend."

### Problem

"Final extreme of the trend" could be interpreted as requiring hindsight — the final extreme is only known after the trend ends (at CHOCH confirmation).

### Amended R8

> "The liquidity level is **the most recent confirmed swing high (HH) or swing low (LL) at the time of the sweep bar**."

### Effect

The sweep level is fixed at the sweep timestamp. If new HH/LL pairs form after the sweep, they become potential sweep levels for future events — but the current event's sweep level remains unchanged.

### Causal Integrity

The sweep level is identifiable at the bar close of the sweep. No future information required.

---

## Amendment B: CHOCH Swing Causal Identification

### Original R8

> "The CHOCH swing is the last swing in the trend direction that must be broken."

### Problem

"Last swing in the trend direction" could change after the sweep if new HL/LH pairs form before CHOCH confirmation.

### Amended R8

> "The CHOCH swing is **the most recent confirmed swing low (HL) or swing high (LH) at the time of the sweep bar**."

### Effect

The CHOCH swing is fixed at the sweep timestamp. If new HL/LH pairs form after the sweep, they do not change the CHOCH swing for the current event.

### Causal Integrity

The CHOCH swing is identifiable at the bar close of the sweep. No future information required.

---

## Amendment C: Execution Timeframe Frozen

### Original R8

> "CHOCH execution is M1/M5."

### Problem

Both M1 and M5 are permitted, creating two models. The canonical dataset is M1.

### Amended R8

> "CHOCH execution is **M1** (consistent with the canonical dataset)."

### Effect

Only M1 data is used. No M5 execution.

### Note

A future hypothesis could test M5 execution as a separate research question. For this standalone test, M1 is frozen.

---

## Amendment D: Retest Timing Clarified

### Original R8

> "Entry on retest of broken CHOCH level."

### Problem

R8 does not specify whether the CHOCH confirmation bar itself can serve as the retest bar.

### Amended R8

> "The retest must occur **after** CHOCH confirmation. The CHOCH confirmation bar cannot serve as the retest bar."

### Effect

The retest is a price return to the CHOCH level after the confirmation has occurred. This prevents using the same bar for both confirmation and retest.

### Causal Integrity

The retest is detected at a bar close after the CHOCH confirmation timestamp. No future information required.

---

## Amendment E: Frequency Estimate Documentation

### Original R8

> "Estimated 5-15 events per week on M1."

### Problem

This estimate is planning intuition, not empirical evidence. It must not be used as evidence that CHOCH is economically attractive.

### Amended R8

> "Estimated frequency: **5-15 events per week on M1** (PLANNING INTUITION — not empirically verified. Actual frequency will be measured in SMC-R9.)"

### Effect

The estimate is labeled honestly. It cannot be used as a selection argument.

---

## Unchanged Components

All other R8 components are unchanged:
- Prior trend definition (2+ consecutive swings)
- Sweep definition (wick + close-back)
- CHOCH confirmation (close beyond swing)
- Entry convention (limit at broken level, next-bar fill)
- Stop (sweep extreme, wick-based)
- Payoff (path-dependent, 120 bars)
- Cost (2-point spread, researcher assumption)
- Event identity (one per CHOCH)
- OOS split (2024-12-31)
- Statistical test (one-sided t-test, HAC, alpha=0.05)
- POI requirement (NONE)

---

*This amendment resolves four SMC-R8-CR findings. The corrected methodology is now internally coherent and causally valid.*
