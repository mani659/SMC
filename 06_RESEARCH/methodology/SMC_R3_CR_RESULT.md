Milestone: SMC-R3-CR
Status: COMPLETE

R3 hypothesis:
  BOS → displacement FVG → OB → first touch → limit at OB proximal → forward return

Zero-degree-of-freedom audit:
  Data-estimated parameters: 0
  Researcher design choices: 6 (MAX_WINDOW, fill, horizon, HAC, OOS split, event association)
  Inherited from R1/R2: 3 (Swing N, entry price, stop reference)
  Classification: C — design choices frozen before testing (legitimate)

BOS→FVG association:
  MAX_WINDOW = 20 bars (design choice, not inherited)
  Selection: first qualifying FVG chronologically
  Overlapping: largest gap, then earliest
  One event per BOS: DETERMINISTIC

FVG/OB uniqueness:
  Within a BOS: one OB selected (deterministic)
  Across BOS events: independent (each has own freshness state)
  No ambiguity

Entry/fill mechanics:
  ENTRY: OB proximal edge (limit order)
  FILL: next bar open after first-touch bar close
  FILL CONSTRAINT: next bar open must reach OB.proximal
  If not filled: event EXCLUDED from measurement
  CAUSAL: valid (next-bar open is known before outcome)

Stop/payoff relationship:
  STOP: OB.distal edge (structural invalidation)
  STOP ROLE: part of primary outcome measurement
  Stopped events contribute stop-loss result to mean
  Non-stopped events contribute 120-bar forward return
  Primary metric: mean across ALL events (including stopped)

Forward horizon:
  120 bars = 2 hours (design choice, not inherited)
  Overlapping: events from different BOS are independent
  HAC handles serial correlation between nearby events

Cost/payoff consistency:
  BLOCKER IDENTIFIED: 4-point cost double-counts spread
  AMENDMENT: forward return from fill price, no additional cost deduction
  Spread already embedded in next-bar open vs OB.proximal gap
  Corrected primary metric: (P_{T+120} - P_{fill}) / P_{fill} × 10,000 bps

HAC specification:
  Bandwidth = 10 bars (design choice)
  Conservative for typical event spacing (>10 bars)
  Adequate for M1 serial correlation

Event identity:
  One event per BOS: deterministic
  Freshness enforced: STATE_FRESH only
  First touch: wick enters zone boundary
  Temporal separation: ≥1 bar
  No sample inflation

Freshness:
  STATE_FRESH → first touch → STATE_TESTED
  Touch = bar whose range enters [OB.low, OB.high]
  Causally valid: identified from bars after OB creation
  No lookahead

Causal timeline:
  Confirmed swing → BOS close → FVG formation → OB creation → freshness period → first touch → entry → outcome
  No future information used at any step
  LOOKAHEAD: NONE

OOS split:
  2024-12-31 (design choice)
  Role: discipline preservation (not parameter validation)
  Primary decision: full dataset (zero parameters)
  Secondary: consistency check across subperiods

Primary economic endpoint:
  Mean net forward return (bps)
  = mean of [(P_{fill+120} - P_{fill}) / P_{fill} × 10,000] across all events
  Stopped events: replaced with stop-loss result
  No additional cost deduction (Amendment A)

Standalone vs module:
  STANDALONE economic hypothesis
  No regime filters, no indicators, no modules

Rare-event evidence:
  No minimum event count
  Evidence assessed by CI width, temporal stability, direction consistency

Critical ambiguities:
  RESOLVED by controlled amendment:
  1. Cost/payoff double-counting → Amendment A
  2. Stop/payoff role → Amendment B
  3. Design choice classification → Amendment C
  4. OOS split role → Amendment D

Remaining ambiguities:
  None — all resolved by controlled amendment

Decision: B — SMC-R3 VALID WITH CONTROLLED AMENDMENT

SMC-R4 status:
  NOT YET AUTHORIZED
  Requires control session review of SMC-R3-CR and acceptance of amendments

Next authorized milestone:
  SMC-R4 — BOS+OB Standalone Event Experiment
  (after amendment acceptance)

External API calls: 0
New data acquired: 0
Spend: $0.00

Repository files created:
  SMC_RESEARCH/methodology/SMC_R3_CR_REVIEW.md (NEW)
  SMC_RESEARCH/methodology/SMC_R3_CR_DECISION.md (NEW)
  SMC_RESEARCH/methodology/SMC_R3_CONTROLLED_AMENDMENT.md (NEW)
  SMC_RESEARCH/methodology/SMC_R3_CR_RESULT.md (NEW)
