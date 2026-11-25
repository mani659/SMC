# F TARGET-REPRESENTATION DIAGNOSIS (READ-ONLY)
**Post-R1 Year F Book — Take-Profit Fallback Forensic Audit**

**Date:** 2026-11-24  
**Authority:** Lead Architect directive (P4)  
**Mode:** READ-ONLY code-path & historical replay audit — `LOGIC_CHANGED: NO`  
**Artifacts Generated:**  
- Deliverable: `06_RESEARCH/F_TP_REPRESENTATION_DIAGNOSIS.md`  
- Dataset: `06_RESEARCH/results/f_tp_representation/fallback_inventory.csv`  
- Summary: `06_RESEARCH/results/f_tp_representation/summary.json`  

---

## 1. Executive Summary & Verdict

For the post-R1 full-year Book F backtest (admitted set F, B, C, E, A across 12 calendar segments, 351 total fills), exactly **129 out of 351 fills (36.75%)** resolved `tp_source = "atr_fallback"`.

At confirmation / placement time:
- **Was a structural swing target unavailable in the frozen feed?** **NO (0 / 129, 0.0%)**.
- **Was a structural swing target available but suppressed by policy/code?** **YES (129 / 129, 100.0%)**.
- **Dominant cause:** **`SUPPRESSED_AGE_CAP_GT_20_BARS` (129 / 129, 100.0%)**. In every single instance, an opposing §19-confirmed structural swing of the correct polarity was present on the place-time prefix and on the favorable side of entry (passing the `0.25 × ATR` noise guard), but was excluded solely because its base candle index was older than the 20-bar bound (`placement_bar - candle_index > 20`).

| Metric | Result |
|---|---|
| **Book F Total Fills** | **351** |
| **Structural Swing TP Fills** | 222 (63.25%) |
| **ATR Fallback TP Fills (`FALLBACK_N`)** | **129 / 351 (36.75%)** |
| **Diagnosed Sample Size** | **129 / 129 (100.0% census)** |
| **Verdict Bucket** | **`SUPPRESSED_POLICY`** |
| **Dominant Bucket Share** | **100.0%** (>60% threshold met; unambiguous) |
| **Dominant Specific Cause** | **`SUPPRESSED_AGE_CAP_GT_20_BARS` (100.0%)** |
| **Feed Unavailability (`UNAVAILABLE_FEED`)** | **0 / 129 (0.0%)** |

---

## 2. Pre-Registered Classification Rules

Before tabulating results across the 129 fills, the following mutually exclusive diagnostic taxonomy was formally registered:

```
[All 129 F Fallback Fills at Place Time]
  │
  ├── BUCKET 1: UNAVAILABLE_FEED (No qualifying opposing structure in price history)
  │     ├── NO_OPPOSING_SWINGS_ON_PREFIX: Zero §19-confirmed opposing swings exist in prefix history
  │     └── ALL_SWINGS_ADVERSE_WRONG_SIDED: Swings exist, but 100% are on the adverse side of entry
  │           (e.g., for LONG, all swing highs are <= entry; for SHORT, all swing lows are >= entry)
  │
  └── BUCKET 2: SUPPRESSED_POLICY (Valid favorable opposing swing existed, but was suppressed by code)
        ├── SUPPRESSED_AGE_CAP_GT_20_BARS: At least one favorable opposing swing passed the
        │     0.25×ATR noise guard, but was rejected solely because age > 20 bars
        ├── SUPPRESSED_NOISE_GUARD_LT_0P25_ATR: Favorable opposing swings existed within 20 bars,
        │     but were closer than 0.25×ATR to entry
        └── SUPPRESSED_AGE_AND_NOISE: Favorable swings within 20 bars failed noise guard,
              and swings beyond 20 bars passed noise guard
```

### Kill Criterion
If no single bucket accounts for `> 60.0%` of fallback fills, the verdict is declared **`MIXED`** and investigation stops without proposing rules.

---

## 3. Code Path Architecture & The 20-Bar Suppression Seam

### 3.1 Design Origin of the Bound
In `06_RESEARCH/STRUCTURAL_TP_FEED_DESIGN.md` §3b (accepted 2026-10-05) and its Architect Addendum:
> *"Reuse of `poi_give_up_bars()` as pre-arm swing tolerance — Accepted ONLY as an optional search bound (CPU/age cap), not a new market meaning. Primary rule remains: all §19-confirmed swings with `confirmed_index < placement_bar` on the place-time prefix; the `poi_give_up_bars()`-before-arm cap is a documented bound, never 'give-up semantics'."*

### 3.2 As-Coded Implementation
In `04_SRC/smc/backtest/pipeline_bridge.py` (`structural_tp_target`):
```python
# Optional age bound (CPU/age cap — NOT give-up semantics).
if (placement_bar is not None and max_age_bars is not None
        and swing.candle_index < placement_bar - max_age_bars):
    continue
```
In `04_SRC/smc/triggers/trigger_expiry.py`:
```python
def poi_give_up_bars() -> int:
    return TRIGGER_A_EXPIRY  # = 20
```
In `04_SRC/smc/orchestration/product_menu_mtf.py` (`_candidate`):
```python
structural_target = structural_tp_target(
    self._swings_for(tf),
    route.signal.entry_price,
    route.signal.direction,
    atr,
    placement_bar=(index if isinstance(index, int) and index >= 0 else None),
    max_age_bars=poi_give_up_bars(),  # Hardcoded 20 bars across all confirmation TFs
)
```

### 3.3 The Time-Scale Mismatch
When `poi_give_up_bars()` (frozen at 20 M5 bars, i.e., 100 minutes) is passed as `max_age_bars` to `structural_tp_target`:
- On **M1** confirmation (which accounts for 95 / 129 fallback fills, 73.6%), 20 bars corresponds to **20 minutes**.
- On **M5** confirmation (23 / 129 fallback fills, 17.8%), 20 bars corresponds to **100 minutes**.
- Under §18/§19 structural swing rules (`N_BAR_LTF = 3`), forming and confirming an opposing swing requires at minimum 7–10 bars (3 bars before peak, base candle, 3 bars after peak, plus a break candle). 
- Consequently, if the confirmation sequence or setup interaction takes 25–60 minutes, any opposing liquidity shelf formed in earlier price action has `age > 20` and is completely invisible to the selector.

---

## 4. Reconstructed Place-Time Swing Availability (Full Census N = 129)

Every one of the 129 fills was re-simulated on its exact place-time prefix series across all 12 monthly segments (`nov24` through `oct25`), with full lookahead protection (`confirmed_index < placement_bar` strictly enforced).

### 4.1 Master Scoreboard

```text
TOTAL_FALLBACK_FILLS: 129
SUPPRESSED_POLICY:    129  (100.0%)
UNAVAILABLE_FEED:       0  (  0.0%)
DOMINANT_CAUSE:       SUPPRESSED_AGE_CAP_GT_20_BARS (129 / 129, 100.0%)
```

### 4.2 Breakdown by Confirmation Timeframe

| Confirmation TF | Total Fallback Fills | `SUPPRESSED_AGE_CAP` | `UNAVAILABLE_FEED` | Share of Fallbacks | Median Age of Best Swing | Min Age | Max Age |
|---|---:|---:|---:|---:|---:|---:|---:|
| **M1** | 95 | 95 (100.0%) | 0 (0.0%) | 73.6% | 45.0 bars (45 min) | 21 bars | 12,501 bars |
| **M5** | 23 | 23 (100.0%) | 0 (0.0%) | 17.8% | 52.0 bars (260 min) | 21 bars | 509 bars |
| **H1** | 8 | 8 (100.0%) | 0 (0.0%) | 6.2% | 38.0 bars (38 h) | 22 bars | 84 bars |
| **M15** | 3 | 3 (100.0%) | 0 (0.0%) | 2.3% | 47.0 bars (705 min) | 32 bars | 87 bars |
| **Total / Overall** | **129** | **129 (100.0%)** | **0 (0.0%)** | **100.0%** | **47.0 bars** | **21 bars** | **12,501 bars** |

### 4.3 Age Distribution of Suppressed Valid Swings
When evaluating the nearest §19-confirmed, favorable, noise-guard-passing opposing swing on the prefix:
- **Minimum age observed:** **21 bars** (literally 1 bar past the 20-bar cutoff).
- **25th percentile (Q1):** **31 bars**.
- **Median (Q2):** **47 bars**.
- **75th percentile (Q3):** **173 bars**.
- In **0%** of cases was the feed missing an opposing swing.
- In **0%** of cases was the opposing swing rejected by the `0.25 × ATR` noise guard.
- In **100%** of cases, when `max_age_bars` is unbounded (`max_age_bars = None`), `structural_tp_target` returned a valid, finite, correctly sided structural target.

---

## 5. Segment-by-Segment Distribution

The 129 fallback fills are distributed across all 12 monthly replay segments with 100% uniformity in root cause:

| Segment | Replay Window | Fallback Fills | `SUPPRESSED_AGE_CAP` | `UNAVAILABLE_FEED` |
|---|---|---:|---:|---:|
| `nov24` | 2024-11-01 .. 2024-11-30 | 15 | 15 (100%) | 0 (0%) |
| `dec24` | 2024-12-01 .. 2024-12-31 | 8 | 8 (100%) | 0 (0%) |
| `jan25` | 2025-01-01 .. 2025-01-31 | 10 | 10 (100%) | 0 (0%) |
| `feb25` | 2025-02-01 .. 2025-02-28 | 10 | 10 (100%) | 0 (0%) |
| `mar25` | 2025-03-01 .. 2025-03-31 | 8 | 8 (100%) | 0 (0%) |
| `apr25` | 2025-04-01 .. 2025-04-30 | 11 | 11 (100%) | 0 (0%) |
| `may25` | 2025-05-01 .. 2025-05-31 | 11 | 11 (100%) | 0 (0%) |
| `jun25` | 2025-06-01 .. 2025-06-30 | 9 | 9 (100%) | 0 (0%) |
| `jul25` | 2025-07-01 .. 2025-07-31 | 13 | 13 (100%) | 0 (0%) |
| `aug25` | 2025-08-01 .. 2025-08-31 | 12 | 12 (100%) | 0 (0%) |
| `sep25` | 2025-09-01 .. 2025-09-30 | 8 | 8 (100%) | 0 (0%) |
| `oct25` | 2025-10-01 .. 2025-10-31 | 14 | 14 (100%) | 0 (0%) |
| **All 12 Months** | **Full Year** | **129** | **129 (100.0%)** | **0 (0.0%)** |

---

## 6. Answers to Mandated Questions

1. **Was a structural swing target unavailable in the frozen feed?**  
   **No.** Structural swings opposing the entry were consistently present in the series prefix.
2. **Was a structural swing target available but suppressed by policy/code?**  
   **Yes.** 100% of the 129 fallback fills had an available, §19-confirmed, noise-passing opposing swing that was suppressed by the `max_age_bars = 20` policy cap.
3. **Is the population mixed?**  
   **No.** There is zero dispersion in high-level cause. The dominant cause is `SUPPRESSED_AGE_CAP_GT_20_BARS` at `100.0%`, well exceeding the 60% kill threshold.

---

## 7. Governance, Disclaimers & Non-Interference

- **Bans strictly observed:**
  - NO new TP selector implemented.
  - NO changes to `KEEP_DUAL_TP` or the 4×ATR fallback policy.
  - NO minimum R or threshold tuning proposed.
  - NO expectancy language or PnL claims made.
  - Book-scoped strictly to Year F (P0).
- **Codebase integrity:**
  - `LOGIC_CHANGED: NO`.
  - `locked_constants.py` diff: empty.
  - Test suite verified: 27/27 structural TP unit tests passing.
