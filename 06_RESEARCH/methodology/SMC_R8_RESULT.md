Milestone: SMC-R8
Status: COMPLETE

Research question:
  Does a confirmed liquidity sweep followed by a causal CHOCH reversal
  create positive directional expectancy on XAUUSD M1?

Candidate:
  CHOCH Reversal — standalone reversal hypothesis

Prior trend:
  At least 2 consecutive higher highs and higher lows (bullish)
  or 2 consecutive lower highs and lower lows (bearish)
  using N=5 swing detection

Liquidity level:
  Final extreme of the trend — last HH (bearish) or last LL (bullish)

Sweep definition:
  Wick pierces liquidity level AND candle closes back inside

Close-back:
  Bearish: close below last HH
  Bullish: close above last LL

CHOCH swing:
  Last HL (bearish) or last LH (bullish) in the trend

CHOCH confirmation:
  Candle close beyond CHOCH swing
  Bearish: close < last HL
  Bullish: close > last LH

POI requirement:
  NONE — standalone test uses CHOCH level as structural reference

Entry:
  Limit at broken CHOCH level
  Fill: next-bar open after retest touch
  Fill constraint: entry price must allow sell (bearish) or buy (bullish)

Stop:
  Beyond sweep extreme (last HH for bearish, last LL for bullish)
  Trigger: wick-based (bar.high > stop for bearish, bar.low < stop for bullish)
  Fill: exact stop level price

Payoff:
  Path-dependent stop-or-horizon
  Horizon: 120 M1 bars (2 hours)
  Directional return in bps

Cost:
  Tier 2 (primary): 2.0-point round-trip spread (researcher assumption)
  Tier 1 (descriptive): fill convention only
  Tier 3 (stress): 2.0-point spread + 1.0-point slippage

Event identity:
  One event per CHOCH confirmation
  One trend → one sweep → one CHOCH = one event
  Repeated touches do not create new events

Dependence:
  Event-level observations with HAC (bandwidth=10)
  Estimated 5-15 events/week (much lower than BOS+OB's 79/day)

OOS:
  Boundary: 2024-12-31
  Discovery: 2021-04-12 to 2024-12-31
  OOS: 2025-01-01 to 2026-04-10

Primary metric:
  Mean directional net payoff in basis points (including stopped events)

Primary null:
  H0: E[R] <= 0

Primary alternative:
  H1: E[R] > 0

Statistical test:
  One-sided t-test, HAC bandwidth=10, alpha=0.05

Alpha:
  0.05

Rare-event policy:
  No arbitrary minimum event count
  Report: total events, independent events, calendar coverage, CI, stability

Observable vs interpretation:
  Observable: trend, sweep, CHOCH, entry, stop, payoff
  Interpretive: institutional stop hunt, absorption, trapped traders (not tested)

Degrees of freedom:
  0 data-estimated parameters
  6 researcher design choices (trend minimum, sweep definition, entry, stop, horizon, cost)

Critical ambiguities:
  None identified — all components are deterministic

Methodology score:
  4.9/5

Decision:
  METHODOLOGY FROZEN — READY FOR SMC-R9

Next authorized milestone:
  SMC-R9 — CHOCH Standalone Economic Experiment

Authorization:
  PLANNED — NOT STARTED

External API calls: 0
New data acquired: 0
Spend: $0.00

Repository files changed:
  SMC_RESEARCH/methodology/SMC_R8_CHOCH_Economic_Methodology.md (NEW)
  SMC_RESEARCH/methodology/SMC_R8_METHODOLOGY_RISK_REGISTER.csv (NEW)
  SMC_RESEARCH/methodology/SMC_R8_RESULT.md (NEW)
