# SMC-R5 Controlled Amendment

**Date**: 2026-08-27
**Origin**: SMC-R5-CR identified three issues requiring clarification
**Status**: FROZEN — applies to SMC-R6 and beyond

---

## Amendment 1: Estimand Acknowledgment

### Original R5

R5 did not explicitly acknowledge that day aggregation changes the estimand from R4.

### Amended R5

Add to §3:

> **Important**: R5 tests the per-day aggregate expectancy, which is a different quantity than R4's per-trade expectancy. The per-day estimand is more relevant for portfolio-level decision-making and correctly accounts for within-day dependence. This is a deliberate methodological improvement, not a hidden change.

### Effect

The economic question changes from:
- R4: "Is each BOS+OB trade positive on average?"
- R5: "Is each trading day's BOS+OB activity positive on average?"

Both are valid economic questions. R5's is more appropriate for portfolio evaluation.

---

## Amendment 2: Cost Assumption Classification

### Original R5

> "spread = 2.0 points (conservative XAUUSD M1 ECN average)"

### Amended R5

> "spread = 2.0 points — **Researcher assumption**, frozen before R6 execution. Not directly observed from canonical dataset. Reasonable estimate for XAUUSD M1 ECN but should be treated as an assumption, not a fact."

### Effect

The cost model is honest about what is observed vs assumed. The 2-point spread is a frozen assumption, not empirical data.

---

## Amendment 3: Qualification Criteria Classification

### Original R5

Criteria 4 and 5 were presented as standard qualification gates.

### Amended R5

> **Criterion 4** (both long and short daily means > 0): This is a **new requirement** not present in R4. R4 tested whether the overall mean was positive. R5 requires both directions to be positive. This is justified if the economic mechanism should work in both directions, but it is a new scientific condition.

> **Criterion 5** (positive in ≥4 of 5 years): This criterion was **defined after R4 results** showed positive in all 6 years. It is a post-hoc addition. While defensible as a stability check, it should be acknowledged as created after seeing the results.

### Effect

Both criteria are preserved but classified honestly. The control session can evaluate whether they are appropriate given their origins.

---

## Unchanged Components

All other R5 components are unchanged:
- Day-level clustering
- Cluster-robust inference
- Three-tier cost reporting
- Tier 2 as primary
- Deduplication
- Entry/stop/horizon conventions
- Zero-parameter principle
- OOS split

---

*This amendment resolves three SMC-R5-CR findings. The corrected methodology is now internally coherent and ready for SMC-R6.*
