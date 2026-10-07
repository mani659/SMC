# WEEKLY (W1) PROVISIONING NOTE

**Milestone:** W — Weekly provisioning (Lead Architect directive 2026-10-06)
**Status:** PASS — suite 838 passed, `locked_constants.py` diff empty
**Result:** W1 is a first-class above-daily HTF **context** timeframe across all
product seams. Execution remains M5 (unchanged). No thresholds, triggers,
SL/TP, risk, or §5a seek/scan semantics were touched.

---

## 1. W1 role (contract statement)

Weekly is **HTF context POI only**: weekly zones are detected, armed, and
displayed exactly like D1/H4 context zones, but they never serve as an
execution timeframe and they change no decision logic. Triggers, SL/TP
routing, and risk stay entirely on the frozen M5 execution path.

## 2. What was wired (5 seams, all additive)

| # | Seam | File | Change |
|---|------|------|--------|
| 1 | Enum | `04_SRC/smc/config/timeframe.py` | `W1 = 32769` (MT5 `TIMEFRAME_W1`), `minutes=10080`, `is_htf()` includes W1 (shares the §27 N=5 class; `N_BAR_HTF` unchanged). |
| 2 | Resample | `04_SRC/smc/data/resample.py` | `_week_open()` bins to UTC **Monday 00:00** of the ISO week; weekly bypass of the 1440-modulo guard; weekly branch in bin-key selection. Deliberate exception: epoch-multiples of 10080 min align to Thursdays (Unix epoch = Thursday) — wrong for MT5/TV weekly bars. |
| 3 | M8 scan | `04_SRC/smc/poi/models/m8_htf_demand_supply.py` | `HTF_TIMEFRAMES = (W1, D1, H4)` — a supplied weekly series is scanned by the same frozen scanner. **Overlap pairing stays D1×H4 (frozen §26)** — W1 deliberately NOT added so quality scores are untouched. |
| 4 | M8 map sharing | `04_SRC/smc/orchestration/multi_tf.py` | `M8_HTF_TIMEFRAMES = (W1, D1, H4)` — a supplied W1 series is auto-shared into M8's map (missing W1 stays optional). |
| 5 | Runtime + live fetch | `04_SRC/smc/orchestration/multi_tf_runtime.py`, `04_SRC/smc/live/loop.py` | `OPTIONAL_W1_TIMEFRAME = W1`; default `optional_timeframes=(W1, D1)`; `LiveLoop` now provisions `runtime.optional_timeframes` in its HTF fetch list (D1 still governed by `include_d1`/`supply_d1_to_m8`). |

Zero-change seams (verified in survey): `mt5_connector.copy_rates` casts
`int(tf)` directly → `PERIOD_W1` works with no mapping table;
`operator_config.py` validates against `Timeframe.__members__` → W1 is
accepted in operator `detection_timeframes` config automatically.

## 3. Enum values

```
W1 = 32769            # MT5 TIMEFRAME_W1 (0x8001) — identical int, mapping-table-free.
                      # CORRECTED 2026-10-06 (dry run): originally written as 32768,
                      # which copy_rates_from_pos rejects with "Invalid params"; the
                      # MetaTrader5 package's TIMEFRAME_W1 is 32769. Enum + pin fixed.
W1.minutes = 10080    # 7 × 1440 (one trading week)
W1.is_htf() = True    # §27 HTF class, N=5 confirmation (unchanged constant)
```

## 4. Default detection timeframes after change

- **Required (unchanged):** `detection_timeframes = (H4, H1)` — missing
  series still raises `MissingHtfSeriesError` (loud, contract §3).
- **Optional context (now):** `optional_timeframes = (W1, D1)` — fetched in
  product mode, fed to M8 when present, tolerated-missing.
- Operator config may promote W1 to required via `detection_timeframes`
  (e.g. `["W1", "H4", "H1"]`); the loud-fail then applies to W1 too.

## 5. Live/paper fetch

`LiveLoop.htf_timeframes` = detection set + optional set = `(H4, H1, W1, D1)`
in product mode. Fetch depth = `DEFAULT_HTF_WINDOW_BARS = 300` per TF →
300 weekly bars ≈ 5.8 years of weekly history — no depth change needed.
Batch **cadence is unchanged**: one multi-TF batch per new H1 close; W1 is
fetched/scanned but never gates the rhythm and never executes.

## 6. Test coverage (`04_SRC/tests/test_weekly_provisioning.py`)

1. W1 resample: Monday-00:00 bin alignment, honest OHLCV aggregation,
   no invented weekend bars, determinism + guard bypass + `resample_multi`.
2. M8 on W1: deterministic weekly impulse fixture emits ≥1 W1 zone through
   the frozen scanner (DISPLACEMENT_MIN_ATR=1.0, N=3 — nothing tuned);
   silent when no W1 series supplied.
3. Runtime: W1 as REQUIRED detection TF → full batch, `per_tf["W1"]` counts;
   W1 as OPTIONAL → reaches M8's map when supplied, tolerated when absent.
4. Live loop: product fetch list `(H4, H1, W1, D1)`, W1 fetched on probe +
   batch, cadence still one batch per new H1 close; legacy mode unchanged.
5. Enum pins updated (E1 convention — strengthened): members list, MT5
   value 32768, minutes 10080, W1 in the §27 HTF class.

## 7. Residuals / known limits

- **Sparse W1 bars:** weekly series are short (300 bars ≈ 6 y). M8's
  displacement scanner needs a warm-up for ATR; very young symbols may emit
  zero weekly POIs — honest (zero POIs, no crash), never fabricated.
- **Cold-start depth:** the bounded 300-bar fetch is the pre-existing
  provisioning bound; deep-history warm-up remains out of scope (documented
  LiveLoop V1 limitation, unchanged).
- **Weekly forming bar:** like every TF, the current forming weekly bar is
  included via prefix semantics (`build_htf_prefixes`) and re-detected next
  batch; geometry dedup (`ZoneDedup`) prevents double-arming.
- **Weekend gap honesty:** weekly bins aggregate present bars only; no bar
  is invented for weekends/holidays (pinned by test).
