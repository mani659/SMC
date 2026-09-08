Milestone: SMC-R3-CR2
Status: COMPLETE

Final amended hypothesis:
  BOS → FVG within 20 bars → OB → first touch → next-bar open fill → 120-bar path-dependent payoff with structural stop

Stop-loss definition:
  Long stop: OB.low (distal edge)
  Short stop: OB.high (distal edge)
  Stop trigger: wick penetration (bar range enters distal level)
  Stop fill price: OB.distal (exact level assumed)
  Gap-through prevention: fill constraint excludes events where next-bar open is past OB.proximal
  After stop: remaining bars ignored; event contributes stop result to sample mean

Primary payoff:
  Path-dependent trade payoff (Path B)
  If stopped: R = (OB.distal - P_fill) / P_fill × 10,000 bps [long]
  If not stopped: R = (P_{fill+120} - P_fill) / P_fill × 10,000 bps [long]
  Short formulas: sign-reversed
  Primary metric: E[R] across all events (including stopped)

Entry price:
  OB.proximal edge (limit order)

Entry timing:
  First-touch bar closes → limit placed → next bar open fill (if price reaches limit)
  Fill constraint: next-bar open must reach OB.proximal
  If not filled: event excluded

Cost representation:
  Implicit execution cost through fill convention (next-bar open is typically worse than OB.proximal)
  No explicit cost deduction
  Classification: CONSERVATIVE APPROXIMATION

Directional symmetry:
  Long: return = (exit - entry) / entry × 10,000
  Short: return = (entry - exit) / entry × 10,000
  Both directions produce returns in the trade direction
  Verified for both stopped and non-stopped cases

FVG association:
  MAX_WINDOW = 20 bars (design choice)
  Selection: first chronological qualifying FVG
  Overlapping: largest gap, then earliest
  One BOS → one FVG → one OB → one event
  DETERMINISTIC

Event identity:
  One event per BOS
  Freshness: STATE_FRESH only
  First touch: wick enters zone boundary
  Temporal separation: ≥1 bar
  No sample inflation

Freshness:
  STATE_FRESH → first touch → STATE_TESTED
  Touch = bar whose range enters [OB.low, OB.high]
  Causally valid: identified from bars after OB creation
  No lookahead

OOS:
  Split: 2024-12-31 (frozen before testing)
  Role: discipline preservation
  Primary decision: full dataset (zero data-estimated parameters)
  Secondary: consistency check across subperiods

HAC:
  Bandwidth = 10 bars
  Adequate for amended payoff structure
  Conservative

Primary null:
  H₀: E[R] ≤ 0
  H₁: E[R] > 0
  One-sided, α = 0.05
  95% one-sided lower confidence bound

Rare-event policy:
  No minimum event count
  Evidence: CI width, temporal stability, direction consistency

Amendment lineage:
  A: Cost removal (estimand changed: explicit → implicit)
  B: Stop inclusion (estimand changed: forward return → trade payoff)
  C: Design choice classification (no estimand change)
  D: OOS role clarification (no estimand change)

Estimand changes:
  Both A and B change the economic estimand
  Both changes make methodology MORE coherent
  Both changes frozen before any outcome examination

Unresolved issues:
  None — all audits pass

Decision: A — SMC-R3 METHODOLOGY VALID — SMC-R4 READY

SMC-R4 status:
  AUTHORIZED
  The Control Session has reviewed R3, CR, and CR2
  The methodology defines one unambiguous economic quantity

Next authorized milestone:
  SMC-R4 — BOS+OB Standalone Event Experiment

External API calls: 0
New data acquired: 0
Spend: $0.00

Repository files created:
  SMC_RESEARCH/methodology/SMC_R3_CR2_REVIEW.md (NEW)
  SMC_RESEARCH/methodology/SMC_R3_CR2_DECISION.md (NEW)
  SMC_RESEARCH/methodology/SMC_R3_CR2_RESULT.md (NEW)
