# SMC-R3-CR2 — Decision

**Date**: 2026-08-27
**Milestone**: SMC-R3-CR2
**Decision**: A — SMC-R3 METHODOLOGY VALID — SMC-R4 READY

---

## Decision

SMC-R3-CR2 verifies that the SMC-R3-CR amendments define ONE unambiguous economic quantity. The methodology is internally coherent, deterministic, causally valid, and economically interpretable.

**SMC-R4 IS AUTHORIZED.**

---

## What CR2 Verified

1. **Stop-loss mathematics**: Formulas are complete. Gap-through prevented by fill constraint.
2. **Primary endpoint**: Path-dependent trade payoff (Path B), not pure forward return. Consistent.
3. **Cost representation**: Implicit execution cost through fill convention (next-bar open). Conservative and coherent.
4. **Directional symmetry**: Both long and short formulas verified. Sign convention correct.
5. **Entry timing**: Deterministic. Edge cases handled.
6. **FVG association**: Unique. Deterministic selection.
7. **Event identity**: One-per-BOS. No sample inflation.
8. **HAC**: Adequate for amended payoff structure.
9. **Statistical framework**: Complete. One-sided, α=0.05.
10. **Amendment lineage**: Both Amendment A and B change the estimand (honestly classified). Changes make methodology MORE coherent.

---

## Final Economic Quantity

```
E[R] = mean path-dependent trade payoff across all qualifying BOS+OB events

where:
  R = stop_result if stopped, else 120-bar forward return
  fill = next-bar open after first-touch detection
  stop = OB.distal edge (exact level)
  horizon = 120 bars (2 hours)
  costs = implicit (fill convention)
  parameters = 0 data-estimated, 6 frozen design choices
```

---

## SMC-R4 Status

**AUTHORIZED.**

The Control Session has reviewed:
- SMC-R3 (original methodology)
- SMC-R3-CR (first control review — 2 blockers found and resolved)
- SMC-R3-CR2 (amendment verification — all audits pass)

The methodology is ready for empirical execution.

---

*This decision authorizes SMC-R4 execution under the corrected SMC-R3 methodology.*
