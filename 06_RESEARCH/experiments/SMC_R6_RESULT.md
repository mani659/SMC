Milestone: SMC-R6
Status: COMPLETE

M4 object: BOS+OB creates positive daily aggregate expectancy under Tier 2

Canonical dataset: XAUUSD M1, 2021-04-12 to 2026-04-10, 1768123 bars

Raw BOS rows: 196965
Unique BOS rows: 134310
Duplicates removed: 62655 (31.8%)

Qualifying BOS+OB events: 126308
Valid trade events: 123386
Eligible UTC days: 1555
Discovery days: 1158
OOS days: 397

Mean daily Tier-2 payoff: -1347.3118 bps
OOS mean daily Tier-2 payoff: -751.3378 bps
Discovery mean daily Tier-2 payoff: -1551.6310 bps

Primary inference statistic: t = -67.2021
Primary p-value: 0.500000
95% CI lower bound: -1380.2918 bps

Tier 1 descriptive mean: 79.8307 bps
Tier 3 descriptive mean: -2060.8831 bps

Stopped percentage: 80.1%
Mean events/day: 79.3
Median events/day: 92
Max events/day: 117

Gate 1 -- Mean daily payoff > 0: FAIL (-1347.3118)
Gate 2 -- p < 0.05: FAIL (0.500000)
Gate 3 -- OOS mean > 0: FAIL (-751.3378)
Gate 4 -- No methodology drift: PASS

Primary M4 decision: M4 FAILED

Economic interpretation:
  BOS+OB does not have positive daily aggregate expectancy under the frozen Tier-2 cost model.

Statistical interpretation:
  The mean daily Tier-2 payoff is not statistically significant (p = 0.500000).

Cost interpretation:
  Result is net after assumed 2-point spread (RESEARCHER ASSUMPTION, not observed).

Event-independence limitation:
  123386 trades aggregated into 1555 daily observations.
  Days are approximately independent; within-day trades are dependent.

What M4 establishes:
  BOS+OB does not qualify for M4 under the frozen methodology.

What M4 does NOT establish:
  That BOS+OB is a profitable live strategy.
  That the edge will persist in future markets.
  That the assumed 2-point spread is the actual execution cost.

M5 status: NOT STARTED (requires control session review of R6)

External API calls: 0
New data acquired: 0
Spend: $0.00
