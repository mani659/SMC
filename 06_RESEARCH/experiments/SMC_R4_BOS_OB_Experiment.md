# SMC-R4 -- BOS + Order Block Continuation Standalone Economic Experiment

**Date**: 2026-08-27
**Milestone**: SMC-R4
**Status**: COMPLETE

---

## Frozen Methodology

| Component | Value |
|-----------|-------|
| BOS definition | Close beyond confirmed swing (N=5) |
| FVG definition | 3-candle gap, same direction as BOS |
| Association window | MAX_WINDOW = 20 bars |
| FVG selection | First chronological qualifying FVG |
| OB definition | Candle preceding selected FVG |
| Entry | Next-bar open (if reaches OB.proximal) |
| Stop | OB.distal edge |
| Horizon | 120 bars (2 hours) |
| Costs | Implicit (fill convention) |
| OOS split | 2024-12-31 |
| HAC bandwidth | 10 |
| Alpha | 0.05 |

---

## Results

### Full Dataset

| Metric | Value |
|--------|-------|
| Total trades | 181676 |
| Mean R (bps) | 1.0104 |
| Median R (bps) | -3.2664 |
| Std R (bps) | 18.9559 |
| Positive fraction | 0.1921 |
| HAC SE | 0.0878 |
| t-statistic | 11.5040 |
| p-value (one-sided) | 0.000000 |
| 95% CI lower bound | 0.8659 bps |

### Discovery Period

| Metric | Value |
|--------|-------|
| Trades | 134544 |
| Mean R (bps) | 0.8027 |
| HAC SE | 0.0823 |
| t-statistic | 9.7506 |
| p-value | 0.000000 |

### OOS Period

| Metric | Value |
|--------|-------|
| Trades | 47132 |
| Mean R (bps) | 1.6036 |
| HAC SE | 0.2435 |
| t-statistic | 6.5852 |
| p-value | 0.000000 |
| 95% CI lower bound | 1.2030 bps |

---

## Direction Split

| Direction | Count | Mean R (bps) |
|-----------|:-----:|:------------:|
| Long | 92772 | 1.3606 |
| Short | 88904 | 0.6451 |

---

## Stop Analysis

| Category | Count | Mean R (bps) |
|----------|:-----:|:------------:|
| Stopped | 145122 | -5.2831 |
| Non-stopped | 36554 | 25.9962 |

---

## Primary Decision

**POSITIVE EXPECTANCY ESTABLISHED**

---

## Lookahead Audit

Issues: 0

---

*SMC-R4 is the first empirical SMC economic experiment.*
