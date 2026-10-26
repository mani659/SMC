# EXPORT ORIGINAL-SL + ZONE GEOMETRY PATCH NOTE (logging-only)

**Status:** COMPLETE 2026-09-20 · no decision, threshold, fill, risk, or trigger logic changed.
**Trigger:** flowchart match notes found exported `sl` is post-BE (corrupts R-multiples) and POI zone bounds are absent (blocks geometry verification).
**Script:** re-ran `06_RESEARCH/scripts/export_patch_verify.py` unchanged — new fields flow with zero script changes.
**Verification:** 2025-10-01..08 window (8280 bars) → 115 trades, **115/115 non-empty** on all four new fields. Suite **596 passed** (591 + 5 new).
**Outputs:** refreshed `06_RESEARCH/results/export_patch_verify/verify_w0/` (trades.csv + report.json with new columns).

---

## 1. Files changed

| File | Change |
|------|--------|
| `smc/backtest/runner.py` | `CandidateEntry` +4 optional fields; `place()`/`open()` call sites pass them |
| `smc/backtest/pipeline_bridge.py` | `candidate_from_route` fills `original_sl` (= placement SL by construction), `zone_low/high` (POI zone, float-guarded), `signal_data_json` (sorted-JSON signal data, empty → None) |
| `smc/backtest/orders.py` | `PendingOrder` +4 fields; `place()` kwargs |
| `smc/backtest/positions.py` | `BacktestPosition` +4 fields; `open()` kwargs; `modify_sl` rebuild copies placement geometry unchanged (the BE-preservation invariant) |
| `smc/backtest/reports.py` | `TradeRecord` +4 fields; `from_closed` maps them |
| `smc/backtest/export.py` | CSV: 4 appended columns; JSON: 4 added keys (nulls stay null) |
| `smc/paper/runner.py` | `_TrackedPending`/`_TrackedPosition` +4 fields; submit-site fill + fill-observe copy |
| `tests/test_identity_patch.py` | +5 tests (placement equality, BE preservation, zone bounds, full-chain record, export columns) |

No adapter/live-loop changes needed — both consume `candidate_from_route` output, so the fields ride the existing seam (live loop feeds nothing new; bridge fills zone/signal automatically).

## 2. Field definitions / schema

| Field | Type | CSV | JSON | Source | Unknown |
|-------|------|-----|------|--------|---------|
| `original_sl` | float \| None | number/`""` | number/null | `signal.stop_reference` at bridge time; never overwritten (modify_sl copies it verbatim — tested) | None |
| `zone_low` / `zone_high` | float \| None | number/`""` | number/null | `route.poi.zone` bottom/top (Zone enforces top ≥ bottom) | None |
| `signal_data_json` | str \| None | string/`""` | string/null | `json.dumps(signal.data, sort_keys=True, default=str)`; empty dict → None | None |

Backward compatible: Optional-with-default everywhere; CSV appended at end (old order kept); JSON additive; determinism unchanged.

## 3. Sample exported rows (verification run, real data)

```text
ticket 1 sl=3866.255 original_sl=3866.255 zone=[3872.698, 3875.295] sig={"bos_index": 155, "ob_index": 155→153}
ticket 2 sl=3866.255 original_sl=3866.255 zone=[3872.698, 3875.295] sig={"bos_index": 155, "ob_index": 153}
ticket 3 sl=3866.255 original_sl=3866.255 zone=[3872.698, 3875.295] sig={"bos_index": 155, "ob_index": 153}
```

(sl == original_sl here: no BE modify fired in this window. The BE case — sl moves, original_sl frozen — is proven by unit test, not this window.)

## 4. What this unlocks / honest limits

- Unlocks: honest R-multiple math (denominator = original_sl), zone-geometry verification on charts (inspector can now draw the rectangle), trigger-geometry audits via signal_data_json (F emits bos/ob indices).
- Limits: BE-contaminated R1/R2/R3 numbers stand as published WITH the contamination note — recomputation against original_sl is the natural next research step, not part of this patch. Paper/live broker fills unexercised (no market session).

## 5. Tests

- New: placement-equality, BE-preservation, zone-bounds, full-chain record, export columns — 5 passed.
- Full suite: **596 passed**, zero regressions.
- No-decision-change: entry/SL/trigger mapping byte-identical with/without new kwargs (prior patch test, still green).

---

*End of note. Next-ready: honest-R recompute and/or stratified inspector work on the instrumented stack (Lead Architect pick).*
