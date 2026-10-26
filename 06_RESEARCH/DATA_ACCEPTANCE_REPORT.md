# POST-V1 PHASE A — DATA ACCEPTANCE REPORT

**Status:** PASS — CLOSED 2026-09-09 (A5 ruled option (a): volume-less dataset accepted; Phase B/C baselines run WITHOUT Trigger D)
**Date:** 2026-09-09
**Active plan:** `00_LOCKED/POST_V1_PLAN_OF_ACTION.md` §3 (Phase A)
**Tool:** `06_RESEARCH/scripts/phase_a_data_acceptance.py` (read-only; no trading logic touched)

---

## 1. Inventory

| File | Size | Format | Classification |
|---|---|---|---|
| `XAUUSD_M1.parquet` | 34 MB | parquet | **CANONICAL — primary M1 execution series** |
| `XAUUSD_M1.csv` | 100 MB | CSV | Derived twin of the parquet (identical schema/content) — provenance duplicate |
| `XAUUSD_mt5_ticks.csv` | 12.9 GB | CSV (MT5 export) | Tick source series — **Phase D+ only** (bid/ask spread reconstruction) |

Tick schema: `date,time,bid,ask,last,volume` (281,514,283 rows, 2021-04-12 11:00:00 → 2026-04-10 20:59:59 — exactly matches the M1 window).

No README/schema notes present in `07_DATA/`.

## 2. Git protection (A0 — mandatory first)

`.gitignore` now carries a dedicated local-data block: `07_DATA/`, `*.parquet`, `*.tick`, `*.ticks`, `*.csv` under data patterns — **all three files verified ignored** via `git check-ignore -v`. Nothing under `07_DATA/` was ever tracked; nothing staged. **No large data files can enter git history.** Related fix (2026-09-09): the pre-existing bare `data/` ignore pattern had silently excluded the entire `04_SRC/smc/data/` package from version control — patterns were root-anchored (`/data/`, `/datasets/`) so source code stays tracked while dataset directories remain ignored.

## 3. Validation results (plan A1–A6)

| Check | Result | Evidence |
|---|---|---|
| **A1 schema vs Candle** | PASS | Columns `timestamp,open,high,low,close,volume`; float64 OHLC; int64 volume. Round-trip: 10,000 `Candle` objects built via UTC-attaching adapter (`to_candles` in the acceptance script) |
| **A2 timestamps** | PASS | tz-NAIVE source → adapter attaches UTC explicitly; strictly ascending; **0 duplicates**; all stamps minute-aligned; range 2021-04-12 11:00 → 2026-04-10 20:59 |
| **A3 gaps** | PASS | 1,766,443 continuous minutes; 1,377 intraday holes (≤2 h); 302 weekend/holiday closures; **0 unexplained gaps > 1 week**; max gap 3.04 days (weekend). Bar-count expiry (§23/§24) is unaffected by calendar gaps — documented in the plan |
| **A4 OHLC integrity** | PASS | 0 rows with high<max(o,c) / low>min(o,c); 0 NaN/inf cells; price floor pass (min 1614.710) |
| **A4 pathological spikes** | PASS | **0 error-bars** (isolated runs ≤3 bars >50% off the 50-bar median). NOTE: max price 5596.805 exceeds 5000 — verified GENUINE: a 7-week sustained repricing regime (38,400 rows, smooth 4549→5596→5280→5418→4857 progression), not a data error. A static price ceiling was the wrong check and was replaced |
| **A5 volume** | **RULED — option (a), 2026-09-09** | **0 nonzero-volume rows of 1,768,123.** Trigger D's frozen rule (`engulfer.volume < engulfed.volume`) can never be true → Trigger D is structurally unfireable on this dataset. The 12.9 GB tick file's volume column is also all-zero (MT5 exports tick volume as 0 for XAUUSD) — **tick data does not rescue this**. **RULING (plan §3): the dataset is accepted as volume-less; the Phase B/C baselines run WITHOUT Trigger D as a tradeable path (per-trigger breakdowns will show 0). Triggers A/B/C unaffected; vendor re-sourcing deferred until Phase C fidelity justifies it.** |
| **A6 provenance** | PASS | SHA-256 recorded below |
| **Spread** | INFO | No spread column in M1. Tick file **has bid/ask** → spread series reconstructable for Phase C sensitivity (or configure `spread_price` externally per plan §5) |

**SHA-256:**
```
e5d730eae5af8348ac38f46f31e9ee6e1a481cbeaaa57cda342b9e56fd17fee9  XAUUSD_M1.parquet
54cf61559673adc7f6917f086bd4ef8d71808c3834f2faa82cd9323ee119311c  XAUUSD_M1.csv
637087df5cbe13a3c5c270c32b115691e7c7e53a4f9a92ac51fb78b35bfbd82e  XAUUSD_mt5_ticks.csv
```

## 4. Coverage

- **Bars:** 1,768,123 M1 bars
- **Window:** 2021-04-12 11:00 UTC → 2026-04-10 20:59 UTC (≈ 5.0 years, 1824.4 days)
- **Density:** 67.3% of a continuous 24/7 series — the deficit is weekends/holidays, consistent with a genuine broker M1 feed
- **Sessions:** full 24 h coverage around the clock on trading days

## 5. Loader path for Phase B

Existing `smc.data.csv_loader.load_ohlcv` handles CSV only. The acceptance script demonstrates the minimal adapter (pandas `read_parquet` → attach UTC → construct `Candle`). Phase B needs a **tiny parquet loader** (≤20 lines: `load_ohlcv_parquet(path)`) — no new data stack. Do not build more until Phase B requires it.

## 6. CANONICAL SERIES DECISION

```text
CANONICAL_SERIES = XAUUSD M1 (parquet)
PATH             = 07_DATA/XAUUSD_M1.parquet
TF               = M1
ROWS             = 1,768,123
FROM             = 2021-04-12 11:00:00 UTC
TO               = 2026-04-10 20:59:00 UTC
SHA256           = e5d730eae5af8348ac38f46f31e9ee6e1a481cbeaaa57cda342b9e56fd17fee9
NOTES            = tz-naive source, adapter attaches UTC; volume all-zero (A5 ruled option (a) 2026-09-09 — baseline without Trigger D);
                   spread absent in M1 — tick bid/ask available for Phase C
```

**Phase B usage:** short fidelity backtest window (1–3 months) cut from the canonical parquet. Recommendation: pick a window containing both trending and ranging regimes.

**Tick data:** NOT needed for Phase B or C entry/fill logic. Needed only in Phase C (spread reconstruction) and Phase D+ (paper-vs-backtest fill forensics). Do not process the 12.9 GB file until then.

## 7. Blockers / risks

| # | Item | Severity | Disposition |
|---|---|---|---|
| 1 | **A5 — Trigger D unfireable** (all-zero volume, both M1 and tick) | **CLOSED** | **RULED (a) 2026-09-09 (plan §3): run the baseline WITHOUT Trigger D** (documented limitation; triggers A/B/C unaffected). *Deriving volume from the existing tick file was impossible — its volume column is all-zero too.* Vendor re-sourcing deferred until Phase C fidelity justifies it. No code change. |
| 2 | tz-naive timestamps | Low | Solved by convention: loader attaches UTC (script + plan document it). Phase B loader must do the same — a unit test pins this |
| 3 | No spread column | Low | Phase C: reconstruct from tick bid/ask or configure `spread_price`. Documented in plan §5 |
| 4 | Price regime > 5000 (to 5596.805) | None | Verified genuine 2026 market; risk/sizing uses ATR-relative math, no absolute price ceilings in the pipeline |

## 8. Verdict

**PHASE A: PASS.** All exit criteria met:
1. `07_DATA/` git-ignored ✅ 2. canonical M1 series identified ✅ 3. schema/timestamps/OHLC acceptable ✅ 4. coverage understood ✅ 5. limitations documented (A5, spread, tz) ✅ 6. Phase B can start without guessing the input file ✅

The A5 ruling is recorded (`POST_V1_PLAN_OF_ACTION.md` §3, option (a)) — **Phase A is CLOSED; Phase B — Short Fidelity Backtest is ACTIVE.**
