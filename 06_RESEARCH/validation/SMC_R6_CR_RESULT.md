Milestone: SMC-R6-CR
Status: COMPLETE

R6 reported result:
  M4 FAILED — 1/4 gates passed
  Mean daily Tier 2: -1,347.31 bps
  OOS mean Tier 2: -751.34 bps

Raw BOS rows: 196,965
Unique BOS rows: 134,310
Duplicates removed: 62,655 (31.8%)

Valid trades: 123,386
Eligible UTC days: 1,555
OOS days: 397

Point/bps conversion:
  Formula: spread_bps = 2.0 / fill * 10000
  At mean fill (2,451.55): 8.16 bps per side
  Round-trip: 16.32 bps
  Per-trade computation: 8.98 bps/side, 17.95 bps round-trip
  VERIFICATION: CORRECT — no unit conversion error

Tier-2 spread application:
  Formula: ret_t2 = ret_t1 - 2 * spread_bps
  One spread per side, applied to entry and exit
  VERIFICATION: CORRECT — not double-counted

Fill/spread interaction:
  Next-bar-open = fill convention (execution price assumption)
  2-point spread = explicit transaction cost (broker spread)
  These are DISTINCT economic quantities
  VERIFICATION: NOT DOUBLE-COUNTED

Stop-cost treatment:
  Stopped trades also incur 2× round-trip spread
  Classification: CONSERVATIVE APPROXIMATION
  Impact: Removing spread from stops would not change M4 conclusion

Daily aggregation:
  R_d = sum of Tier-2 returns for all trades on day d
  VERIFICATION: CORRECT per R5 specification

Sample lineage:
  196,965 raw BOS -> 134,310 unique -> 126,308 qualifying -> 123,386 valid -> 1,555 days
  All exclusions deterministic and outcome-blind

OOS:
  Boundary: 2024-12-31
  Discovery: 1,158 days (mean -1,551.63 bps)
  OOS: 397 days (mean -751.34 bps)
  VERIFICATION: CORRECT

Primary inference:
  Standard one-sided t-test on daily Tier 2 returns
  t = -67.20, SE = 20.05, p = 0.50 (one-sided > 0)
  VERIFICATION: APPROPRIATE

Event-level vs daily interpretation:
  Event-level: +1.01 bps gross per trade (positive, confirmed)
  Daily: -1,347 bps per day (strongly negative after costs)
  NOT contradictory — frequency overwhelms edge

Economic magnitude:
  Gross edge: +1.01 bps per trade
  Spread cost: ~18 bps per trade (round-trip)
  Net per trade: ~-17 bps
  Daily: ~79 trades x -17 bps = ~-1,343 bps
  Cost overwhelm ratio: 18x

Cost interpretation:
  Result is "net after assumed 2-point spread"
  2-point spread is RESEARCHER ASSUMPTION (not observed)
  Even with zero explicit cost (Tier 1), daily edge is only +80 bps
  Any realistic cost makes daily result negative at 79 trades/day

Overlap:
  Up to 14 simultaneous positions
  Correctly aggregated into daily returns
  Classification: faithfully represented

M4 gate verification:
  Gate 1 (mean_t2 > 0): FAIL (-1,347.31)
  Gate 2 (p < 0.05): FAIL (p = 0.50)
  Gate 3 (OOS > 0): FAIL (-751.34)
  Gate 4 (no drift): PASS
  1/4 gates passed

What R6 proves:
  1. BOS+OB has a small gross positive edge (+1.01 bps/trade)
  2. The edge is overwhelmed by transaction costs at 79 trades/day
  3. M4 qualification fails under frozen Tier 2 cost model
  4. Cost model is mathematically correct (no errors found)

What R6 does NOT prove:
  1. That BOS+OB structural phenomenon is false
  2. That no lower-frequency variant could work
  3. That actual broker spreads are exactly 2 points
  4. That all SMC hypotheses are unprofitable

Decision: A — R6 FAILURE VALID

M4 status: NOT QUALIFIED — CONFIRMED

Next authorized milestone:
  CONTROL SESSION to determine programme direction
  (BOS+OB standalone archived; new hypotheses require separate authorization)

External API calls: 0
New data acquired: 0
Spend: $0.00

Repository files changed:
  SMC_RESEARCH/validation/SMC_R6_CR_REVIEW.md (NEW)
  SMC_RESEARCH/validation/SMC_R6_CR_DECISION.md (NEW)
  SMC_RESEARCH/validation/SMC_R6_CR_RESULT.md (NEW)
