Milestone: SMC-R9
Status: COMPLETE

Research question:
  Does the standalone CHOCH reversal event produce positive mean
  directional net payoff on XAUUSD M1 under the frozen methodology?

Canonical dataset: XAUUSD M1, 2021-04-12 11:00:00 to 2026-04-10 20:59:00, 1768123 bars

Total qualifying events: 7483
Discovery events: 5417
OOS events: 2066

Events per week: 28.7
Events per month: 123.1
Events per year: 1497.4

Long events: 3766
Short events: 3717
Stopped events: 4672 (62.4%)
Non-stopped events: 2811

Mean gross payoff: 0.8936 bps
Mean net payoff: -17.0286 bps
OOS mean net payoff: -9.6414 bps
Discovery mean net payoff: -19.8460 bps
Median net payoff: -23.9143 bps
Std net payoff: 26.0641 bps

Positive-event fraction: 0.1487

Long mean net: -16.8714 bps
Short mean net: -17.1879 bps

Primary HAC statistic: t = -31.3003
HAC SE: 0.5440
Primary p-value: 0.500000
95% CI lower bound: -17.9236 bps

Gate 1 -- Positive mean net payoff: FAIL (-17.0286)
Gate 2 -- Primary p < 0.05: FAIL (0.500000)
Gate 3 -- Positive OOS mean: FAIL (-9.6414)
Gate 4 -- No methodology drift: PASS

Primary M3 decision: M3 FAILED

What R9 establishes:
  CHOCH reversal does not demonstrate positive standalone expectancy under the frozen methodology.

What R9 does NOT establish:
  That CHOCH is a profitable live strategy.
  That the edge will persist in future markets.
  That the assumed 2-point spread is the actual execution cost.

M3 status: M3 FAILED
M4 status: NOT STARTED

Major limitations:
  1. 2-point spread is researcher assumption (not observed)
  2. HAC bandwidth=10 may not fully capture event clustering
  3. Frequency measurement is first empirical estimate

External API calls: 0
New data acquired: 0
Spend: $0.00
