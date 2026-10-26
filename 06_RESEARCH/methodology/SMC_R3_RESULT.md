Milestone: SMC-R3
Status: COMPLETE

Research question: Does the BOS + first-mitigated OB continuation event produce positive forward expectancy on XAUUSD after realistic transaction costs?

Candidate model: BOS + OB Continuation (Trigger F, SMC-R1 §7)

Structural chain:
  Swing (N=5) → BOS (close beyond swing) → FVG (3-candle gap within 20 bars) → OB (candle preceding FVG) → price returns to OB → entry

BOS definition:
  Bullish: close > last confirmed swing high
  Bearish: close < last confirmed swing low
  Confirmation: closing price of the breaking bar
  Source: SMC-R1 §3.3, R2 extraction validated

FVG definition:
  Bullish: candle[i+2].low > candle[i].high
  Bearish: candle[i+2].high < candle[i].low
  Confirmation: candle[i+2] close
  Source: SMC-R1 §3.2, R2 extraction validated

OB definition:
  Candle immediately preceding the first candle of the 3-candle FVG pattern
  Color irrelevant (per 07_PROVEN_KNOWLEDGE)
  Zone: [OB.low, OB.high] (full wick, conservative)
  Source: SMC-R1 §3.1, R2 extraction validated

BOS–OB association:
  FVG must occur within MAX_WINDOW=20 bars of BOS
  FVG direction must equal BOS direction
  First qualifying FVG in chronological order selected
  One event per BOS (prevents sample inflation)

POI requirements:
  Zone Refinement: APPLIED (OB+FVG guaranteed by construction)
  Displacement: APPLIED (FVG within 20 bars of BOS)
  Freshness: APPLIED (STATE_FRESH required)
  Premium/Discount: NOT APPLIED (continuation pattern; structurally inappropriate)
  Inducement: NOT APPLIED (most discretionary; future module hypothesis)

Freshness:
  STATE_FRESH: OB created, price has not returned
  STATE_TESTED: Price wick entered zone → entry deactivated
  STATE_VIOLATED: Price closed beyond zone extreme → permanently inactive

Event identity:
  One event per BOS
  Only first valid trigger per POI
  Freshness enforced (STATE_FRESH only)

Entry convention:
  Bullish: limit at OB.high (proximal edge)
  Bearish: limit at OB.low (proximal edge)
  Execution: next bar open after first-touch bar close
  Fill requirement: next bar open must reach or pass limit price
  No chasing: if not filled, event excluded

Stop convention:
  Bullish: stop at OB.low (distal edge)
  Bearish: stop at OB.high (distal edge)
  Buffer: 0 points (structural edge directly)
  Source: SMC-R1 Trigger F specification

Payoff definition:
  Primary: forward return in basis points over 120 bars (2 hours)
  Bullish: (close_at_entry+120 - entry) / entry × 10,000
  Bearish: (entry - close_at_entry+120) / entry × 10,000
  Stop handling: outcome = stop-loss result (not full horizon)
  Entry not filled: event excluded

Transaction-cost model:
  Spread: 3.0 points
  Slippage: 1.0 point
  Total: 4.0 points per trade
  Application: net = gross - total_cost (in bps)
  Frozen, not optimized

Chronological split:
  Discovery: 2021-04-12 to 2024-12-31
  OOS: 2025-01-01 to 2026-04-10
  Primary decision: full dataset (zero free parameters)
  OOS: secondary consistency check

Primary metric:
  Mean net forward return (bps) after 4.0-point costs

Primary null:
  H₀: μ ≤ 0

Primary alternative:
  H₁: μ > 0 (one-sided)

Statistical test:
  One-sample t-test
  Standard errors: Newey-West HAC, bandwidth=10
  Alpha: 0.05

Dependence treatment:
  HAC standard errors (accounts for serial correlation)
  Event independence via freshness + one-per-BOS rules

Rare-event policy:
  No minimum event count
  Evidence assessed by CI width, temporal stability, direction consistency

Secondary descriptors (NOT primary decisions):
  Median forward return
  Win rate
  Mean R-multiple
  Stop-out rate
  MAE
  MFE

Degrees of freedom:
  ZERO — no parameters optimized or estimated
  Swing N=5: fixed
  MAX_WINDOW=20: structural
  Entry: structural (proximal edge)
  Stop: structural (distal edge)
  Horizon: 120 bars (structural)
  Costs: 4.0 points (frozen)
  Alpha: 0.05 (standard)
  HAC bandwidth: 10 (structural)

Remaining ambiguities:
  None — all methodology frozen

Architecture score: 49/50
  Structural fidelity: 5
  Determinism: 5
  Causal integrity: 5
  Economic clarity: 5
  OOS validity: 5
  Cost realism: 4 (frozen but may underestimate)
  Event independence: 5
  Rare-event suitability: 5
  Simplicity: 5
  Scientific information value: 5

Decision: METHODOLOGY FROZEN

Next authorized milestone:
  SMC-R4 — BOS+OB Standalone Event Experiment

Authorization:
  PLANNED — NOT STARTED (requires control session review)

External API calls: 0
New data acquired: 0
Spend: $0.00

Repository files created:
  SMC_RESEARCH/methodology/SMC_R3_BOS_OB_Economic_Methodology.md (NEW)
  SMC_RESEARCH/methodology/SMC_R3_METHODOLOGY_RISK_REGISTER.csv (NEW)
  SMC_RESEARCH/methodology/SMC_R3_RESULT.md (NEW)
