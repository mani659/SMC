# EXPORT / IDENTITY PATCH NOTE (logging-only instrumentation)

**Status:** COMPLETE 2026-09-20 · no decision, threshold, fill, risk, or trigger logic changed.
**Script:** `06_RESEARCH/scripts/export_patch_verify.py` (mirrors phase_b wiring + the new seam).
**Verification:** 2025-10-01..08 window (8280 bars) → 115 closed trades, **115/115 non-empty** on all three new fields. Suite **591 passed** (582 + 9 new).
**Outputs:** `06_RESEARCH/results/export_patch_verify/verify_w0/` (trades.csv + report.json with new columns).

---

## 1. Files changed (11 production + 1 test + 1 script)

| File | Change |
|------|--------|
| `smc/backtest/runner.py` | `CandidateEntry` +3 optional fields; `BlockedEntry` + poi/trigger/route; `place()`/`open()` call sites pass them through |
| `smc/backtest/pipeline_bridge.py` | `candidate_from_route(route, *, displacement=None, pillar_path=None)`; new `pillar_path_summary()` (duck-typed PASS/FAIL formatter); `model_tags` always from `route.poi.models`, unknown (`None`) never invented |
| `smc/backtest/pipeline_adapter.py` | `note_route_context()` retention + consumption at workflow creation (pop-on-route) |
| `smc/backtest/orders.py` | `PendingOrder` +3 fields; `place()` kwargs |
| `smc/backtest/positions.py` | `BacktestPosition` +3 fields; `open()` kwargs; `modify_sl` rebuild copies them (BE modifies keep identity) |
| `smc/backtest/reports.py` | `TradeRecord` +3 fields; `from_closed` maps them |
| `smc/backtest/export.py` | CSV: 3 appended columns (`model_tags,pillar_path,disp_magnitude_atr`; old order kept); JSON: 3 added keys (`model_tags` as list, nulls stay null) |
| `smc/paper/runner.py` | `_TrackedPending`/`_TrackedPosition` +3 fields; submit-site fill + fill-observe copy |
| `smc/live/loop.py` | `_arm_new_pois` feeds `note_route_context` from driver results + `attribute_displacement` (guarded; identity never blocks arming) |
| `tests/test_identity_patch.py` | 9 focused tests (flow, defaults, export, no-decision-change) |
| `06_RESEARCH/scripts/export_patch_verify.py` | Short-window proof run (new file, research only) |

## 2. Field definitions / schema

| Field | Type (store) | CSV | JSON | Source | Unknown encoding |
|-------|--------------|-----|------|--------|------------------|
| `model_tags` | `tuple[str,...] \| None` | `M1+M5` joined, `""` if None | list or null | `route.poi.models` names at bridge time (always present in practice) | `None` → empty/null |
| `pillar_path` | `str \| None` | string or `""` | string or null | `pillar_path_summary(validation_result)` via `note_route_context` | `None` |
| `disp_magnitude_atr` | `float \| None` | number or `""` | number or null | `DisplacementResult.magnitude_atr` via `note_route_context` | `None` |

- `pillar_path` format: `PASS:1+2+3+4+5;inducement=1.0` for admitted trades; `FAIL@<pillar>:<name>:<status>:<detail>` where a failed validation is ever summarized.
- Backward compatibility: all dataclass fields Optional-with-default (positional construction unaffected); CSV columns appended at end; JSON readers using `.get` unaffected; determinism unchanged (fixed column/key order).
- What is NOT persisted (honest gaps): per-POI pillar paths for POIs that never route (validation records still live only in-memory `DriverResult.results`); armed-never-traded registry (no such store exists); FVG contexts beyond the existing Trigger-F path.

## 3. Sample exported rows (verification run, real data)

```text
row ticket=1 trigger=F models=M1 pillar=PASS:1+2+3+4+5;inducement=1.0 disp_atr=2.1731978801020726 pnl=-0.09300000000002911
row ticket=2 trigger=F models=M1 pillar=PASS:1+2+3+4+5;inducement=1.0 disp_atr=2.1731978801020726 pnl=-0.09300000000002911
row ticket=3 trigger=F models=M1 pillar=PASS:1+2+3+4+5;inducement=1.0 disp_atr=2.1731978801020726 pnl=-0.09300000000002911
```

(CSV header now ends `...,route_id,model_tags,pillar_path,disp_magnitude_atr`.)

## 4. Method notes / caveats

- The verify run over-trades vs Phase B methodology (115 vs ~10 expected): it mirrors the LIVE loop (episode check only) and omits the research-side `ZoneRegistry` geometric dedup, so same-zone POIs re-arm per bar under fresh uuids. Counts differ; field-flow proof is unaffected (every candidate carries identity regardless of dedup).
- Route ids vary run-to-run (uuid4 POI ids, pre-existing behavior — Phase C used deterministic-id injection for byte-identity; not needed here).
- Backtest/paper/live share `CandidateEntry`, so all three paths are structurally wired; the live loop additionally feeds context per newly-armed POI. Paper/live broker fills were not exercised in this patch (no market session) — structural wiring only, covered by unit tests + backtest proof run.

## 5. Test result

- New: `tests/test_identity_patch.py` — 9 passed (bridge flow incl. empty-models-unknown, displacement/pillar propagation, PASS/FAIL/None summary, modify_sl preservation, old-construction compat, CSV append + empty-cell + JSON keys, entry/SL/trigger byte-identical with/without kwargs).
- Full suite: **591 passed** (582 pre-existing + 9 new), zero regressions.

---

*End of note. Next-ready: FLOWCHART_MATCH study and/or SHORT_WINDOW_SELECTIVITY re-runs on the instrumented stack (Lead Architect pick). Phase D ops unaffected.*
