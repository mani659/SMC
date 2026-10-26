# SMC-R5-CR — Decision

**Date**: 2026-08-27
**Milestone**: SMC-R5-CR
**Decision**: B — R5 VALID WITH CONTROLLED AMENDMENT

---

## Decision

R5's day-clustering architecture is economically defensible and addresses the R4-CR dependence limitation. Three amendments are required before R6.

---

## What R5-CR Found

### Confirmed

1. **Day-level clustering is economically defensible** — different days represent fresh market structure
2. **Cluster-robust inference is correct** — handles within-day dependence that HAC cannot
3. **Three-tier cost reporting is honest** — makes cost assumptions explicit
4. **Tier 2 as primary is reasonable** — explicit spread, not too conservative, not too aggressive
5. **Deduplication is mandatory** — addresses R2 sample inflation
6. **No methodology drift** — entry/stop/horizon preserved from R3/CR2

### Amendments Required

#### Amendment 1: Estimand Acknowledgment

R5 changes the estimand from per-trade to per-day. This must be explicitly stated.

#### Amendment 2: Cost Assumption Classification

The 2-point spread is a researcher assumption, not observed data. Classification must be honest.

#### Amendment 3: Qualification Criteria Classification

"Both directions > 0" is new. "≥4/5 years" is post-hoc. Both must be acknowledged.

---

## R5 Methodology After Amendments

The amended R5 methodology:

1. Tests per-day aggregate expectancy (not per-trade)
2. Uses cluster-robust inference at day level
3. Reports three cost tiers with Tier 2 as primary
4. Classifies 2-point spread as researcher assumption
5. Acknowledges "both directions > 0" as new requirement
6. Acknowledges "≥4/5 years" as post-hoc criterion

All other components preserved unchanged.

---

## SMC-R6 Authorization

**CONDITIONAL on amendment acceptance.**

If the control session accepts the three amendments, R6 is authorized.

---

*This decision authorizes SMC-R6 subject to amendment acceptance.*
