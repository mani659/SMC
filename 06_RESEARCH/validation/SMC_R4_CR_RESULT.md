Milestone: SMC-R4-CR
Status: COMPLETE

R4 reported result:
  Total trade rows: 181,676
  Unique valid trades: 123,386
  Duplicate rows: 58,290 (32.1%)
  OOS trade rows: 47,132
  Unique OOS trades: ~31,645

Sample lineage:
  BOS CSV rows: 196,965
  Unique BOS bar_index: 134,310
  Duplicate BOS rows: 62,655 (31.8%)
  Cause: R2 extraction produced duplicate BOS entries
  Impact: Reported N inflated by 32%; mean R unchanged

Trade-frequency assessment:
  Mean trades/day: 79.3
  Max trades/day: 117
  Min gap: 0 seconds
  Entry timestamps with multiple trades: 11,927
  Max trades at same entry time: 5
  Assessment: HIGH FREQUENCY — many trades share same market context

Overlap assessment:
  Max simultaneously open trades: 14
  Assessment: MATERIAL LIMITATION — not economically independent

Stop-payoff audit:
  Stop implementation: CORRECT per CR2
  Stop trigger: wick-based (bar.low <= distal for long)
  Stop fill: OB.distal (exact level)
  Non-stop exit: close at fill+120 bars
  Verification: correct for both directions

Intrabar audit:
  M1 OHLC cannot determine exact intra-bar sequence
  Stop uses wick-based trigger (conservative)
  Classification: STANDARD LIMITATION (not blocking)

Fill convention:
  Entry: next-bar open after first-touch detection
  Fill constraint: must reach OB.proximal
  Classification: CONSERVATIVE APPROXIMATION

Cost representation:
  No explicit cost deduction
  Implicit cost through fill convention
  Classification: NOT FULLY COST-ADJUSTED

Directional symmetry:
  Long: n=62,895, mean=+1.31 bps
  Short: n=60,491, mean=+0.69 bps
  Both positive, formulas correct
  Classification: CORRECT

OOS architecture:
  Split: 2024-12-31 (frozen)
  Discovery: n=91,741, mean=+0.80 bps
  OOS: n=31,645, mean=+1.62 bps
  Classification: APPROPRIATE

Robustness terminology:
  R4 reported "ROBUST"
  Corrected: "positive in both periods and each calendar year"
  Classification: TERMINOLOGY OVERSTATEMENT

Statistical vs economic magnitude:
  Statistical: p < 0.000001 (overwhelming)
  Economic: +1.01 bps per trade (small)
  Classification: POSITIVE EXPECTANCY ONLY

Event-level dependence:
  79 trades/day, up to 5 per bar, 14 overlapping
  Many trades represent same market move
  Effective sample size much smaller than 123K
  Classification: MATERIAL LIMITATION

Data exclusions:
  4,510 events excluded (data-boundary only)
  Classification: VALID

Lookahead:
  0 issues
  Classification: CLEAN

Methodology drift:
  One deviation: duplicate BOS entries (originated in R2)
  All other components match R3/CR2
  Classification: DEVIATION (originated in R2)

Primary economic quantity:
  Mean net forward return (bps) under conservative fill convention
  NOT fully cost-adjusted

M3 classification:
  M3 CONDITIONAL
  Valid economic candidate with material limitations

Major limitations:
  1. Duplicate BOS entries inflated N by 32%
  2. Extreme trade frequency (79/day) suggests repeated exposures
  3. Up to 14 overlapping trades (not independent)
  4. Not fully cost-adjusted
  5. Effective sample size overstated

Decision: B — R4 VALID WITH MATERIAL LIMITATIONS

Next authorized milestone:
  SMC-R5 — BOS+OB M4 Module Qualification Methodology
  (subject to deduplication and limitation documentation)

External API calls: 0
New data acquired: 0
Spend: $0.00

Repository files changed:
  SMC_RESEARCH/validation/SMC_R4_CR_REVIEW.md (NEW)
  SMC_RESEARCH/validation/SMC_R4_CR_DECISION.md (NEW)
  SMC_RESEARCH/validation/SMC_R4_CR_RESULT.md (NEW)
