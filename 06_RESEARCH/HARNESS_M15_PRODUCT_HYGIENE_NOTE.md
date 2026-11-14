# HARNESS M15 PRODUCT-DIAGNOSTIC HYGIENE

**Date:** 2026-11-14 · **Status:** PASS · **`LOGIC_CHANGED: NO`** (scripts/docs only)
**Authority:** `LOCKED_DECISIONS` §0 / §4b (POI inventory includes M15),
`PRODUCT_RUNTIME_CONTRACT` §1 (`(D1,H4,H1,M15)`), `POST_C2_DIAGNOSTIC_REPORT.md`
(the empty-funnel finding).

---

## 1. Problem

The product runtime requires the POI inventory set `(D1, H4, H1, M15)`. Harnesses
that supplied only H1/H4/D1 made **every** `run_batch` fail loudly
(`MissingHtfSeriesError`) and still wrote a funnel summary — `htf_batches=0,
batch_errors=2979` on the 6-month window — which reads as "no setups" instead of
"harness incomplete".

---

## 2. Shared helper (one place, no copy-paste)

`06_RESEARCH/scripts/lib/product_htf_series.py`

| Symbol | Contract |
|---|---|
| `PRODUCT_DETECTION_TIMEFRAMES` | `(D1, H4, H1, M15)` — the contract set. |
| `MissingProductHtfSeries(ValueError)` | Loud failure naming every missing TF. |
| `ensure_product_detection_frames(frames, *, source, require_d1=True)` | Keeps supplied series; derives each missing product TF from a finer `source` (M1/M5) by resample; **drops the trailing bucket unless it closed by the source's last close** (no lookahead); validates strictly ascending, tz-aware UTC; raises if anything is still missing. |
| `assert_product_detection_complete(frames)` | Raises naming absent/empty required TFs. |

Closed-bar rule: a derived bar is kept only when
`bar.timestamp + tf.minutes <= source_last.timestamp + source_tf.minutes`.
D1 is derived the same way, so a slice shorter than one day fails loud rather than
inventing a partial daily bar (`require_d1=False` is available for deliberately
D1-less probes).

---

## 3. Survey — every product-path harness under `06_RESEARCH/scripts/`

| Harness | Before | Action |
|---|---|---|
| `phase3_structure_funnel.py` (shared composition) | **H1/H4/D1 only → all batches failed** | **Fixed**: helper + M15 prefix per bar |
| `frozen_funnel_6m_new_contract.py`, `frozen_funnel_6m_post_tp.py`, `frozen_funnel_new_contract.py` | delegate to `phase3.run` | inherit the fix (no edit) |
| `phase4_unified_backtest.py` (`arm_multi_tf` dry check) | H1/H4/D1 → `MissingHtfSeriesError` swallowed as `skip` | **Fixed**: helper + M15 |
| `c1_multi_tf_parity_smoke.py` | H1/H4/D1 → every batch loud-failed | **Fixed**: helper + M15 (full M5 load prefix) |
| `post_c2_diagnostic.py` | ad-hoc `run_batch` probe injecting M15 | **Simplified**: probe removed; inherits phase3's helper |
| `menu_trade_funnel.py`, `menu_confirm_stream_smoke.py`, `menu_funnel_debug.py`, `opt4_menu_rejoin.py`, `opt_b_confirm_measure.py` | already resample M15 (`DETECTION_TFS`) | unchanged (already correct) |
| `fr1_multi_tf_smoke.py`, `fr4_fidelity_baseline.py`, `fr4_armed_poi_fate.py` | `MultiTFDetectionDriver.validate_multi` (legacy detection driver, not the product seam) | **unchanged, documented as non-product** |
| `d1_f1f2_resample.py`, `h4_poi_confirmation.py`, `l1_h4_stage0a_enriched.py`, `phase2_contract_population_snapshot.py` | model-level probes (M8 direct / single TF) | unchanged, non-product |

No harness claims "product funnel" while running a degraded single-TF set; the
existing degraded-mode opt-in is untouched.

---

## 4. Verification

Dry run of the fixed shared composition (exec 2025-10-01 → 2025-10-03, load
2025-08-01):

| Metric | Before (same harness) | After |
|---|---|---|
| `htf_batches` | 0 | **66** |
| `batch_errors` | 2979 (6-month run) | **1** (cold-start prefix only) |
| detected | none | **H4 1007 · H1 992 · D1 924 · M15 997** |
| armed | 0 | **12** |

A product-mode call with an incomplete map and no source now raises
`MissingProductHtfSeries` naming the missing TFs — no silent zero-batch success.

---

## 5. Tests

`04_SRC/tests/test_harness_m15_hygiene.py` (4, helper imported by path):

- **T1** missing M15 → derived from M5, non-empty, map asserted complete.
- **T2** missing H4 → `ensure_*`/`assert_*` raise naming `H4`.
- **T3** derived M15 bars are closed-bar only (last bucket never extends past
  the source's last close).
- **T4** `post_c2_diagnostic.py` imports and `main` is callable.

**Suite:** 1504 passed / 7 skipped (1500 + 4). No skips added.

---

## 6. Non-edits

- No `04_SRC/smc/**` strategy/runtime change (`git diff` empty).
- `locked_constants.py` untouched.
- No C3/R3/D-S/threshold change, no boundary-sweep emitter.
- Degraded mode kept; only mislabeled product runs are prevented.
- No PnL/performance claim (the October diagnostic remains non-performance).

---

## 7. Return block

```text
HARNESS_M15_STATUS: PASS
HELPER_PATH: 06_RESEARCH/scripts/lib/product_htf_series.py
HARNESSES_UPDATED: phase3_structure_funnel.py, phase4_unified_backtest.py, c1_multi_tf_parity_smoke.py, post_c2_diagnostic.py
PRODUCT_MODE_WITHOUT_M15: AUTO_INJECT (FAIL_LOUD when no finer source)
TESTS_ADDED: 4
SUITE: 1504/0
NOTE_PATH: 06_RESEARCH/HARNESS_M15_PRODUCT_HYGIENE_NOTE.md
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
SRC_STRATEGY_DIFF: empty
HANDOFF_UPDATED: YES
NEXT_READY: Open-decisions research agenda (O1–O5) | Architect pick
```
