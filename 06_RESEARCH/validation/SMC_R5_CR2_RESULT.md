Milestone: SMC-R5-CR2
Status: COMPLETE

R5 economic unit: One UTC trading day = one economic observation
R4 economic unit: One BOS+OB trade = one observation

Estimand comparison:
  R4: E[R per trade] — per-BOS-event expectancy
  R5: E[R per day] — per-day aggregate expectancy
  Change: deliberate, documented, economically justified for module qualification

Chosen M4 object:
  BOS+OB creates positive daily aggregate expectancy for a portfolio operating the signal continuously

Economic independence: Different trading days (fresh market structure)

Dependence framework: Day-level aggregation + ordinary inference on daily means

Day aggregation: Equal-weighted daily average of all trade returns

Overlap treatment: Aggregate concurrent positions into daily return

Cost Tier 1: Fill convention only (descriptive)
Cost Tier 2: Fill + 2.0-point spread (PRIMARY acceptance criterion)
Cost Tier 3: Fill + 2.0-point spread + 1.0-point slippage (stress test)

Cost classification: RESEARCHER ASSUMPTION (not observed, frozen before R6)

Cost/payoff consistency: VERIFIED — spread applied symmetrically, no double-counting

Direction criterion: REMOVED from formal acceptance (post-hoc)
  Moved to: descriptive diagnostic only

Yearly criterion: REMOVED from formal acceptance (post-hoc)
  Moved to: descriptive diagnostic only

OOS: Fixed chronological split 2024-12-31 (appropriate for zero-parameter model)

Primary acceptance criteria (4 gates):
  1. Positive mean daily return under Tier 2
  2. Cluster-robust p < 0.05 (one-sided)
  3. Positive OOS mean daily return
  4. No methodology drift

Secondary diagnostics (reported, not gates):
  5. Long vs short breakdown
  6. Yearly breakdown
  7. Tier 1 and Tier 3 results
  8. Event count and cluster count
  9. Stopped vs non-stopped breakdown

Post-hoc criteria removed:
  - Both directions > 0 (was criterion 4)
  - Positive in >=4/5 years (was criterion 5)

M3 to M4 boundary:
  M3 = positive standalone event ESTABLISHED (R4)
  M4 = sufficiently reliable daily module PENDING (R6)

Major limitations:
  1. Day aggregation changes estimand from per-trade to per-day (deliberate)
  2. 2-point spread is researcher assumption (not observed)
  3. UTC day boundary is deterministic but arbitrary
  4. Equal day weighting is a design choice

Decision: A — M4 VALID — R6 READY

SMC-R6 status: AUTHORIZED

Next authorized milestone: SMC-R6 — BOS+OB M4 Qualification Experiment

External API calls: 0
New data acquired: 0
Spend: $0.00

Repository files changed:
  SMC_RESEARCH/validation/SMC_R5_CR2_REVIEW.md (NEW)
  SMC_RESEARCH/validation/SMC_R5_CR2_DECISION.md (NEW)
  SMC_RESEARCH/validation/SMC_R5_CR2_RESULT.md (NEW)
