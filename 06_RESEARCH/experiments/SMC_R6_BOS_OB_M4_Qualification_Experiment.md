# SMC-R6 — BOS+OB M4 Economic Module Qualification Experiment

**Date**: 2026-08-27
**Milestone**: SMC-R6
**Status**: COMPLETE
**Classification**: M4 qualification experiment

---

## 1. Executive Summary

SMC-R6 tests whether BOS+OB qualifies as an M4 validated economic module under the frozen daily-aggregate methodology with Tier 2 cost assumptions.

**Decision: C — M4 FAILED**

The frozen BOS+OB candidate fails the qualification test. The raw per-trade edge (+1 bps) is overwhelmed by the assumed 2-point round-trip spread cost when aggregated across 79 daily trades.

---

## 2. Frozen Methodology

| Component | Value |
|-----------|-------|
| BOS definition | Close beyond confirmed swing (N=5) |
| FVG definition | 3-candle gap, same direction |
| MAX_WINDOW | 20 bars |
| OB definition | Candle preceding first qualifying FVG |
| Entry | Next-bar open after first-touch |
| Stop | OB.distal edge |
| Horizon | 120 bars |
| Tier 2 spread | 2.0 points (round-trip) |
| Daily aggregation | SUM of trade returns per day |
| OOS split | 2024-12-31 |
| Alpha | 0.05 |

---

## 3. Sample Lineage

| Stage | Count |
|-------|------:|
| Raw BOS rows | 196,965 |
| Unique BOS rows | 134,310 |
| Duplicates removed | 62,655 (31.8%) |
| Qualifying BOS+OB events | 126,308 |
| Valid trades | 123,386 |
| Eligible UTC days | 1,555 |
| Discovery days | 1,158 |
| OOS days | 397 |

---

## 4. Primary Results

### Full Dataset

| Metric | Tier 1 (Gross) | Tier 2 (Spread) | Tier 3 (Spread+Slip) |
|--------|:--------------:|:---------------:|:---------------------:|
| Mean daily return (bps) | **+79.83** | **-1,347.31** | **-2,060.88** |
| Positive days | 3.2% | 3.2% | 3.2% |

### OOS

| Metric | Tier 2 |
|--------|-------:|
| Mean daily return (bps) | -751.34 |
| t-statistic | -25.57 |
| p-value | 0.500000 |

### Per-Trade Basis (Tier 2)

| Metric | Value |
|--------|------:|
| Mean per-trade return (Tier 2) | -17.0 bps |
| Mean per-trade cost (round-trip 2pt spread) | -20.0 bps |
| Gross per-trade edge (Tier 1) | +1.0 bps |
| Net per-trade after Tier 2 cost | -17.0 bps |

---

## 5. Why M4 Failed

The economic arithmetic is straightforward:

```
Per-trade gross edge:     +1.0 bps
Per-trade Tier 2 cost:   -20.0 bps  (2 points round-trip at ~2000 XAUUSD)
Per-trade net:           -19.0 bps

Trades per day:           ~79
Daily Tier 2 payoff:     ~79 x (-19) = ~-1,500 bps
```

The 2-point spread cost per trade (20 bps round-trip) overwhelms the 1 bps gross edge by a factor of 20.

**The raw edge exists but is not economically viable under the frozen cost model.**

---

## 6. Gate Evaluation

| Gate | Requirement | Result | Verdict |
|:----:|-------------|--------|:-------:|
| 1 | Mean daily Tier 2 > 0 | -1,347.31 | **FAIL** |
| 2 | p < 0.05 | 0.500000 | **FAIL** |
| 3 | OOS mean > 0 | -751.34 | **FAIL** |
| 4 | No methodology drift | No issues | **PASS** |

**Gates passed: 1/4**

---

## 7. Descriptive Diagnostics

### Yearly Results (Tier 2)

| Year | Days | Mean daily T2 (bps) | Positive % |
|:----:|:----:|--------------------:|:----------:|
| 2021 | 226 | -1,706 | 0.9% |
| 2022 | 310 | -1,735 | 0.6% |
| 2023 | 309 | -1,547 | 0.6% |
| 2024 | 313 | -1,264 | 1.0% |
| 2025 | 312 | -831 | 5.4% |
| 2026 | 85 | -459 | 27.1% |

### Trade Characteristics

| Metric | Value |
|--------|------:|
| Stopped trades | 80.1% |
| Non-stopped trades | 19.9% |
| Mean events/day | 79.3 |
| Median events/day | 92 |
| Max events/day | 117 |

### Direction (Descriptive)

Both long and short are negative after Tier 2 costs. The gross edge is positive in both directions, but costs overwhelm it.

---

## 8. Interpretation

### What M4 Establishes

> The frozen BOS+OB structural event has a small gross positive edge (+1 bps per trade) that is NOT economically viable under the assumed 2-point round-trip spread cost. The module does NOT qualify for M4.

### What M4 Does NOT Establish

- That BOS+OB has no economic value whatsoever (the gross edge exists)
- That a different cost model would produce the same result
- That the structural event is scientifically invalid
- That no future economic mechanism could monetize the information

### Economic Reality

With 79 trades per day and 20 bps cost per trade, the daily cost burden is ~1,580 bps. The gross daily edge is ~80 bps. The net is ~-1,500 bps per day.

For BOS+OB to be economically viable, either:
1. The per-trade edge must be much larger than +1 bps, OR
2. The trade frequency must be much lower, OR
3. The execution cost must be much lower than 2 points round-trip

None of these can be achieved within the frozen methodology without optimization (which is forbidden).

---

## 9. M4 Status

> **M4 NOT QUALIFIED**

BOS+OB fails the frozen M4 qualification test.

Per the negative-result policy:
> Archive the standalone economic hypothesis unless the Control Session authorizes a genuinely new module hypothesis.

Do NOT:
- Add filters to reduce trade frequency
- Add RSI/volume/session to improve edge
- Optimize the cost model
- Rescue with combinations

---

## 10. External API calls: 0 | New data acquired: 0 | Spend: $0.00

---

*SMC-R6 is an M4 qualification experiment. The frozen BOS+OB candidate failed the qualification test under the frozen Tier-2 cost model.*
