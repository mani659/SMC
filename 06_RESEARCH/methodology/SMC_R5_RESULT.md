Milestone: SMC-R5
Status: COMPLETE

M3 status: M3 CONDITIONAL (from R4-CR)

M4 objective:
  Does BOS+OB survive stricter qualification after correcting event lineage,
  accounting for dependence, and representing execution costs honestly?

Economic independence definition:
  One trading day = one economic event
  All BOS+OB trades within a single UTC day are one opportunity
  Different days = independent events

Dependence framework:
  Primary: cluster-robust standard errors at day level
  Fallback: block bootstrap at day level
  Replaces: HAC (insufficient for within-day clustering)

Event clustering:
  Day-level aggregation
  Daily return = mean of all trade returns on that day
  Equal-weighted within day

Cost model:
  Three-tier architecture:
    Tier 1: Fill convention only (R4 baseline)
    Tier 2: Net after explicit spread (2.0 points) — PRIMARY
    Tier 3: Net after spread + slippage (1.0 point)
  All three tiers reported

Entry convention:
  Preserved: next-bar open after first-touch detection
  Fill constraint: must reach OB.proximal
  Limitation: conservative (biased against trader)

Stop logic:
  Preserved: OB.distal edge
  Trigger: wick penetration
  No buffer, no optimization

Intrabar limitation:
  Documented as execution uncertainty
  Wick-based trigger is most conservative M1 convention

Primary payoff:
  Directional return (bps) at three cost tiers
  Aggregated to daily level
  Tested with cluster-robust inference

Chronological validation:
  Fixed split: 2021-04-12 to 2024-12-31 (discovery)
               2025-01-01 to 2026-04-10 (OOS)
  Yearly consistency: descriptive stability check

Parameter policy:
  Zero parameters estimated from data
  All quantities frozen before execution

Economic magnitude framework:
  Report effect size, CI width, cost burden, clustering impact
  No arbitrary bps threshold

Rare-event policy:
  Distinguish raw events from independent opportunities
  Report both counts
  No arbitrary minimum

Direction handling:
  Both long and short required
  No directional filtering
  Directional consistency is a qualification criterion

Qualification criteria (7 required):
  1. Day-level positive expectancy after spread
  2. Cluster-robust p < 0.05
  3. OOS mean daily return > 0
  4. Both long and short daily means > 0
  5. Positive in at least 4 of 5 years
  6. No methodology drift
  7. Positive after explicit spread (Tier 2)

Forward/demo role:
  Not part of M4
  Future: execution validation only

Standalone/module status:
  Standalone trend-continuation candidate
  Module role not formalized until after M4

Candidate M4 architecture comparison:
  A: Event-level (R4) — rejected (violates independence)
  B: Day-level clustering — SELECTED
  C: Non-overlapping — rejected (discards information)
  D: Hourly blocks — rejected (arbitrary boundary)

Selected architecture:
  Day-level clustering with cluster-robust inference

Major limitations:
  1. Day-level aggregation reduces effective N from 123K to ~1555
  2. Edge is small (+1 bps) and may not survive realistic costs
  3. M1 intrabar limitation remains
  4. Fill convention is conservative approximation

Decision: A — M4 METHODOLOGY FROZEN — READY FOR QUALIFICATION

Next authorized milestone:
  SMC-R6 — BOS+OB M4 Qualification Experiment

Authorization:
  PLANNED — NOT STARTED

External API calls: 0
New data acquired: 0
Spend: $0.00

Repository files created:
  SMC_RESEARCH/methodology/SMC_R5_BOS_OB_M4_Qualification_Methodology.md (NEW)
  SMC_RESEARCH/methodology/SMC_R5_M4_RISK_REGISTER.csv (NEW)
  SMC_RESEARCH/methodology/SMC_R5_RESULT.md (NEW)
