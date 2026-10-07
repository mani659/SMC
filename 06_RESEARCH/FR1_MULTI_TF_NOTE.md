# FR-1 MULTI-TF CASCADE NOTE (implementation + limits)

**Status:** COMPLETE 2026-09-21 · library path + wired smoke run. No thresholds, no trigger geometry, no risk logic touched.
**Scripts:** `06_RESEARCH/scripts/fr1_multi_tf_smoke.py` (real-data wired path).
**Tests:** `04_SRC/tests/test_multi_tf_cascade.py` (11 tests). Suite **607 passed** (596 + 11), zero regressions.
**Artifacts:** `06_RESEARCH/results/fr1_smoke/fr1_summary.json`.

---

## 1. Current behavior pre-FR-1 (survey finding)

- Detection TF today: whatever single candle list the caller passes — M1 in every backtest/fidelity script (`adapter.set_candles(M1)`), M5 rolling window in the live loop. One `DetectionDriver` instance = one TF.
- `htf_candles` (the M8 map): empty (`{}`) on every production path — passed never, defaulted always.
- M8 therefore **cannot emit** outside unit tests: `M8HtfDemandSupply.detect` iterates `(D1, H4)` map keys and skips absent series silently.
- Phase C / fidelity scripts (`phase_b/c_*`) construct the runner + adapter on M1 only — frozen evidence runners, intentionally untouched; they remain single-TF by design and are flagged as such (see §4).

## 2. What changed (modules)

| File | Change |
|------|--------|
| `smc/data/resample.py` (new) | Deterministic M1 → M5/H1/H4/D1 OHLCV aggregation (UTC-aligned bins, present-bars-only gaps, disorder raises loud, order-preserving determinism) |
| `smc/orchestration/multi_tf.py` (new) | `MultiTFDetectionDriver`: per-TF frozen `DetectionDriver` runs (H4+H1 default), shared D1/H4 map into M8 (detection series double as M8 input — silence impossible when data present), optional per-TF arming, per-TF counts, `single_tf_detect_exec` compliance flag, loud missing-series failure (explicit `missing_ok` degraded opt-in) |
| `tests/test_multi_tf_cascade.py` (new) | 11 tests: resample exactness/determinism/disorder, feed FR-1 shape + alignment, spy-proven non-M1 detection, M8 emission through the wired driver, loud-missing + degraded opt-in, single-TF flag both ways, arm-bars wiring |
| `06_RESEARCH/scripts/fr1_multi_tf_smoke.py` (new) | Real-data path: accepted M1 loader → resample → `MultiTimeframeFeed` validation → multi-TF batch → M8 loud-fail gate → JSON artifacts |

No edits to detection models, triggers, risk, runner, adapter, constants, or fidelity scripts.

## 3. How to run multi-TF

```text
python 06_RESEARCH/scripts/fr1_multi_tf_smoke.py [--from YYYY-MM-DD] [--to YYYY-MM-DD]
```
Default window 2025-09-20..10-31. Exit nonzero when M8 emits nothing. Library use: `MultiTFDetectionDriver(detection_timeframes=(H4, H1), execution_timeframe=M5).validate_multi({H4: [...], H1: [...]})` → `result.counts_by_tf()`, `result.single_tf_detect_exec`.

## 4. Smoke result (2025-09-20..10-31, 41,399 M1 bars)

M5 8280 / H1 690 / H4 186 / D1 36 bars; feed validated; H4: 9 raw → 4 merged → 0 passed; H1: 10 → 4 → 0 passed (this window's candidates all failed validation — counts are the deliverable, not entries); **M8 emitted 12 POIs**; `single_tf_detect_exec=false`; PASS.

## 5. Residual limits (honest, not hidden)

- Per-bar backtest/paper loop integration is NOT in FR-1: the loop still walks a single execution-TF series; multi-TF runs are batch-window. Wiring per-bar HTF detection into `BacktestRunner`/`PaperRunner` cycles is follow-on work (FR-4 territory).
- No cross-TF POI merge (streams stay per-TF; confluence across TFs is an open research question).
- Phase B/C fidelity scripts remain single-TF by design (frozen baselines — must not be re-run as multi-TF evidence).
- D1 detection is provisioned (resample + map support it) but R2 requires only H4+H1; D1 stays optional per ruling.

---

*End of note. Exit criteria: detection consumes H4+H1 ✓ · M1-only not the sole wired path ✓ · M8 emits with fixtures ✓ (unit + wired + smoke) · per-TF counts ✓ · suite 607 ✓ · no constant edits ✓.*
