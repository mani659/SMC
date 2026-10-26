# C1 NOTE — ONE MULTI-TF PRODUCT RUNTIME (live = paper = research)

**Date:** 2026-09-23 · **Authority:** Lead Architect Phase 0 + Phase 1 (C1) ruling
**Contract (Phase 0):** `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md`
**Evidence before:** `06_RESEARCH/AS_CODED_ARCHITECTURE_FLOWCHART.md` (as-coded extraction — research chain = multi-TF, live/paper = single-TF)
**Strategy changes:** none (no threshold, pillar, trigger, R7/R8/R9, or zone-band edit)

---

## 1. Before / after call graph (live)

**Before (as-coded):**

```
run_operator._build_stack
  → LiveLoop(driver=DetectionDriver(M5))            # single TF
      → run_once()  per new M5 bar
          → _arm_new_pois()
              → driver.validate_window(_window, engine)   # M5-only detection;
                                                          # M8 unfed, no H4/H1
          → runner.run_one_cycle(bar)
```

**After (C1):**

```
run_operator._build_stack
  → MultiTFProductRuntime(execution=M5, detection=(H4,H1),
                          allow_single_tf_degraded=cfg flag)      # ONE runtime
  → PaperRunner(..., runtime=runtime)      # paper seam available too
  → LiveLoop(runtime=runtime)
      → start()
          → connector.connect()
          → HTF probe (product mode): missing H1/H4 ⇒ REFUSE to start (loud)
      → run_once()  per new M5 bar
          → _detect_and_arm(bar)
              → _fetch_htf_series()        # connector.copy_rates per TF (H4/H1/+D1)
              → new H1 close?  no  → return 0 (cadence honoured)
                               yes → runner.arm_multi_tf(series, as_of, arm_bar,
                                                         execution_candles)
                                       → MultiTFProductRuntime.run_batch(...)
                                           → MultiTFDetectionDriver.validate_multi
                                           → ZoneDedup (geometry episode dedup)
                                           → engine.arm_at(newly passed only)
                                           → adapter.note_route_context (logging)
              → MissingHtfSeriesError ⇒ arm_errors++, logged, NOTHING arms
          → runner.run_one_cycle(bar)
```

**Research parity:** `06_RESEARCH/scripts/c1_multi_tf_parity_smoke.py` drives the same
`MultiTFProductRuntime.run_batch` on the canonical dataset (and asserts the paper entry point
produces identical per-TF counts). The heavy FR-4b evidence scripts stay frozen.

## 2. Public API (the one-driver rule)

| Symbol | Role |
|---|---|
| `smc.orchestration.multi_tf_runtime.MultiTFProductRuntime` | product facade (batch state, dedup, counters) |
| `MultiTFProductRuntime.run_batch(...)` | detect → dedup → arm one batch; returns `MultiTFBatchReport` |
| `MultiTFProductRuntime.build_htf_prefixes(series_by_tf, as_of)` | honest prefixes (`timestamp <= as_of`) |
| `MultiTFProductRuntime.missing_series(series_by_tf)` | loud-fail predicate |
| `smc.orchestration.multi_tf_runtime.ZoneDedup` | shared geometry dedup (research rule, now shared) |
| `smc.orchestration.multi_tf_runtime.MissingHtfSeriesError` | the loud-fail exception |
| `smc.paper.runner.PaperRunner.arm_multi_tf(series, *, as_of, arm_bar, execution_candles)` | paper-side seam entry |
| `smc.live.loop.LiveLoop(runtime=..., htf_window_bars=..., htf_fetch=...)` | live dispatch + cadence + HTF provisioning |

`MultiTFDetectionDriver.validate_multi` remains the single detection implementation — the runtime
forwards to it; no second stack, no copied thresholds.

## 3. How HTF series are obtained

| Path | Source | Depth |
|---|---|---|
| Live/paper (operator) | `connector.copy_rates(symbol, TF, 0, htf_window_bars)` per TF (H4, H1, D1) | 300 bars/TF (`DEFAULT_HTF_WINDOW_BARS`) |
| Live tests | injected `LiveLoop(htf_fetch=...)` callable | caller-defined |
| Research smoke | `resample_multi(M1) → H1/H4/D1` prefixes by timestamp | full prefix from the load window |
| Historical research (FR-4b etc.) | unchanged (frozen scripts) | — |

M8 input: the runtime forwards **D1 + H4** into the driver's `htf_candles` when the caller supplies
them (`supply_d1_to_m8=True`, default). The frozen research chain relied on `validate_multi`'s
auto-share (H4 only); the product seam is a **superset** (contract §1: "D1 supplied when
available") — declared here, not a threshold change.

## 4. Loud-fail behaviour (contract §3)

* `run_batch` raises `MissingHtfSeriesError` naming missing TFs when `allow_single_tf_degraded=False`.
* `LiveLoop.start()` refuses (returns False, logs) when the HTF probe yields no usable H1/H4.
* Mid-session: the batch refuses, `arm_errors++`, `last_arm_error` recorded, nothing arms — no fallback.
* `allow_single_tf_degraded=True` (tests only) runs the legacy single-TF path, stamped
  `degraded=True` + reason; operator config default is `false`.
* Operator config rejects `detection_timeframes` that collapse onto the execution TF unless degraded.

## 5. Smoke on real data (`results/c1_multi_tf_parity/run1/summary.json`)

Window: exec 2025-10-01 → 2025-10-15 (2,761 M5 bars), HTF warm-up from 2025-08-17, canonical
`07_DATA/XAUUSD_M1.parquet`. Runtime: 27.0 s total.

| Measure | Value |
|---|---|
| H1 cadence batches | 231 |
| Detected raw (H4 / H1, summed) | 3,272 / 3,503 |
| Passed (H4 / H1, summed) | 8 / 49 |
| **Armed (new POIs)** | **5** |
| **Duplicates skipped by shared dedup** | **52** (run1 == run2) |
| Already-tracked skips | 0 |
| Batch errors | 0 |

**Parity (batch 0):** live-path per-TF counts == paper-path per-TF counts (`per_tf_equal: true`,
armed equal), paper used its own `MultiTFProductRuntime` instance (shared class, not shared state).

**Loud-fail probe (real series, H4 withheld):** `raised: true`, missing = ["H4"], message
"…refusing to fall back to single-TF detection…".

**Degraded probe:** `degraded: true`, reason records the explicit opt-in and the missing TFs,
per-TF map shows the M5 single-TF run.

**LiveLoop dispatch smoke (no terminal):** `started: true`, `htf_batches: 1` across 60 M5 bars,
`arm_errors: 0` — the H1 cadence gate holds (one batch, not 60).

> The 52 duplicate skips are the double-arm storm the audit warned about: POI ids are `uuid4`, so
> without the shared geometry dedup every later HTF batch would re-arm the same zone as a new POI.

**Determinism pair:** the smoke was run twice (`run1/`, `run2/`) — `bars_processed`, `htf_batches`,
`funnel`, `parity`, `loud_fail`, `degraded` and the LiveLoop dispatch block are **IDENTICAL**
across runs (26.7 s vs 27.0 s wall clock only).

## 6. Test map (`04_SRC/tests/test_multi_tf_product_path.py`, 17 tests)

| Test | Contract item |
|---|---|
| `test_run_batch_raises_when_required_htf_missing` | §3.1 loud-fail, nothing arms |
| `test_degraded_requires_execution_series` | §3.3 degraded needs the exec series |
| `test_degraded_single_tf_report_is_stamped` | §3.3 explicit degraded + reason |
| `test_build_htf_prefixes_cutoff_semantics` / `..._rejects_disorder` | honest prefixes / poisoned input |
| `test_zone_dedup_matches_research_rule` | shared dedup rule (same dir + overlap) |
| `test_run_batch_structure_on_synthetic_htf` | §5.3 structure + arming into a real engine |
| `test_run_batch_arms_new_pois_and_skips_duplicate_zone` | §5.4 newly passed armed once, duplicates skipped |
| `test_d1_is_forwarded_to_m8_only_when_supplied` | M8 D1/H4 provisioning |
| `test_live_loop_runs_one_batch_per_new_h1_close` | §5.5 cadence (1 batch per H1 bar) |
| `test_live_loop_product_mode_refuses_to_start_without_htf` | §5.6 start gate |
| `test_live_loop_degraded_mode_starts_and_reports_degraded` | §5.6 degraded start |
| `test_paper_arm_multi_tf_delegates_to_shared_runtime` / `...requires_real_engine` | §5.7 paper seam |
| `test_operator_config_defaults_and_c1_flags` / `...rejects_single_tf_detect_exec` / `...rejects_unknown_or_malformed_detection_tfs` | §5.8 config validation |

Suite: **698 passed** (681 baseline + 17 new), zero regressions. No locked constant changed
(`ZONE_REFINEMENT_ATR`, R7/R8/R9 untouched — existing assertions still green).

## 7. Residuals (honest)

1. **R9 paper parity** — `PaperRunner` already shares the `IntentBook` implementation; this task did
   not extend intent semantics. Residual unchanged from R9.
2. **HTF depth** — 300 bars/TF; deep-history warm-up (e.g. 200+ D1 bars) is not provisioned in V1.
3. **Cold start** — live still anchors to the latest bar and does not replay history (unchanged).
4. **Legacy mode** — `LiveLoop` without a runtime keeps the pre-C1 single-TF path for the Phase 7
   tests; it logs a warning and is NOT the product composition (run_operator always passes a runtime).
5. **Research scripts** — FR-4b evidence scripts remain frozen (not switched to the seam);
   the parity smoke is the bridge. Consequently the frozen chain's M8 map (H4-only auto-share)
   differs from the product seam's D1+H4 provisioning as declared in §3.
6. **Pillar-2 attribution in the product path** — unchanged: the adapter's honest sweep-displacement
   map (or caller injection) applies exactly as before.
7. **Phase D operator runs** — the EXNESS session path now builds the runtime; a live ops session
   should confirm the HTF probe against the real terminal (broker-side H4/H1 availability).
