Milestone: SMC-R5-CR
Status: COMPLETE

R5 objective:
  M4 qualification methodology for BOS+OB module

R4 economic estimand:
  E[R per trade] — mean payoff per individual BOS+OB trade

R5 economic estimand:
  E[R_d] — mean of daily average payoffs (deliberate change from R4)

Estimand comparison:
  R4: per-trade expectancy (123K observations, dependence issues)
  R5: per-day expectancy (~1555 observations, dependence addressed)
  Change: DELIBERATE AND DOCUMENTED (Amendment 1)

Economic unit:
  One UTC trading day = one economic event

Day-clustering rationale:
  Different days start with fresh market structure
  Intraday correlation is high (79 trades/day)
  UTC midnight is deterministic but arbitrary

Dependence framework:
  Primary: cluster-robust standard errors at day level
  Correctly handles within-day clustering
  Replaces: HAC (insufficient)

Cost Tier 1:
  Fill convention only (R4 baseline)
  Label: "Gross return under conservative fill"

Cost Tier 2:
  Fill + 2.0-point spread (PRIMARY)
  Label: "Net return after explicit spread"
  Classification: RESEARCHER ASSUMPTION (not observed)

Cost Tier 3:
  Fill + 2.0-point spread + 1.0-point slippage
  Label: "Net return after spread + slippage"

Cost double-counting assessment:
  NOT double-counting
  Next-bar-open gap and spread are different quantities
  But relationship is uncertain

Stop-cost assessment:
  Spread deducted from stop exit (OB.distal - spread)
  Approximate — stop fill at OB.distal is structural, not market price

UTC boundary:
  Deterministic but arbitrary
  Not economically meaningful for XAUUSD
  Acceptable as clustering device

Overlap assessment:
  Day aggregation correctly addresses overlap
  Multiple simultaneous positions = one daily opportunity

Position weighting:
  Equal weighting: each day contributes equally
  Design choice, not economic fact

OOS:
  Fixed split: 2024-12-31
  Appropriate for zero-parameter model

Yearly criterion:
  ≥4/5 years — POST-HOC (created after R4 results)
  Defensible but should be acknowledged

Direction criterion:
  Both long and short > 0 — NEW REQUIREMENT
  Not present in R4
  Justified if mechanism should work both ways

Researcher-degree-of-freedom audit:
  10 choices documented
  2 require explicit acknowledgment (post-hoc, new)
  Neither invalidates R5

Critical limitations:
  1. Estimand change from per-trade to per-day (Amendment 1)
  2. 2-point spread is researcher assumption (Amendment 2)
  3. Two qualification criteria are post-hoc/new (Amendment 3)

Decision: B — R5 VALID WITH CONTROLLED AMENDMENT

Amendments required:
  1. Estimand acknowledgment
  2. Cost assumption classification
  3. Qualification criteria classification

All amendments are clarification/documentation, not methodology changes.

SMC-R6 status:
  CONDITIONAL — requires amendment acceptance

Next authorized milestone:
  SMC-R6 — BOS+OB M4 Qualification Experiment

External API calls: 0
New data acquired: 0
Spend: $0.00

Repository files changed:
  SMC_RESEARCH/validation/SMC_R5_CR_REVIEW.md (NEW)
  SMC_RESEARCH/validation/SMC_R5_CR_DECISION.md (NEW)
  SMC_RESEARCH/validation/SMC_R5_CR_CONTROLLED_AMENDMENT.md (NEW)
  SMC_RESEARCH/validation/SMC_R5_CR_RESULT.md (NEW)
