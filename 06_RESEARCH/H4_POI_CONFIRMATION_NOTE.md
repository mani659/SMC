# H4 POI CONFIRMATION NOTE (identification only — no trading decisions)

**Status:** COMPLETE · suite **754 passed** (750 pre-existing + 4 new), zero regressions.
**Scope bans honored:** no pillar/trigger/RiskEngine/TP-SL/lot/spread/threshold edits; no new models or tags; no expectancy/PF claims; identification-only; survey-first (below).

---

## 1. Survey findings (what the H4 pack had to reuse)

- **Emission path:** identical to the D1 pack — `M8HtfDemandSupply._zones(h4, H4)` yields
  `(kind, direction, start, zone)` post-F1F2 collapse (one row per geometric episode;
  `m8_kind` winner propagated). No product code changed for this pack.
- **Product seam:** `DetectionDriver.validate_window` on H4 with `htf_candles={H4: h4}` +
  `ZoneDedup` for the armed approximation — same layers as `d1_f1f2_resample.py`
  (raw → merged → armed), minus the M5 exec loop (documented approximation).
- **Chart language:** reuses `render_d1_chart` from `generate_d1_poi_pack.py` (same visual style,
  plain-label overlays); H4 series passed as the candle context.
- **Data/window:** `07_DATA/XAUUSD_M1.parquet` → `resample_multi(..., [H4])` → 1203 H4 bars
  (warm-up load 2025-03-01, exec 2025-06-01 → 2025-11-30 UTC).

## 2. What was built

- Script: `06_RESEARCH/scripts/h4_poi_confirmation.py`.
- Outputs: `06_RESEARCH/results/h4_poi_confirmation/` — `events_h4_poi.csv` (661 rows),
  `summary.json`, `H4_POI_CONFIRMATION_REPORT.md`, `charts/` (55 PNGs).
- Tests: `04_SRC/tests/test_h4_poi_pack.py` (4 tests): H4 synthetic emission origin-tight + no duals;
  plain-tag contract has no D1 leakage; merged ids geometry-stable (with the uuid4 rationale pinned);
  exec-window endpoint filter behavior.

## 3. Two defects found and fixed (script-local)

1. **First-seen anchoring vs exec filter (merged layer emptied).** Validating windows whose end
   predates EXEC_START anchored deduped geometries to pre-exec timestamps; the exec-range filter
   then dropped the same geometry when it re-appeared in-window (first-seen wins → all dropped).
   Live check: pre-fix merged=0 despite dozens of live M8-tagged validation results.
   Fix: only windows with `end_ts ≥ EXEC_START` (mirrors the D1 script's convention).
   Post-fix merged=3.
2. **Run-random merged ids.** `POI.id = uuid4()` → merged `event_id`s differed byte-wise across
   runs while raw rows/summary matched. Fix: geometry-derived `_eid("merged", direction, bounds, ts)`.
   Verified: double-run → CSV **byte-identical**, summary identical.

## 4. Gate + count record (exec window)

- raw **658** (ob 177 / demand_supply 304 / fvg 177) · merged **3** · armed **0** · charts **55**.
- **dual_exact_bounds_count = 0 · direction_conflict_count = 0 · origin_tight_violations = 0.**
- All 3 merged rows failed Pillar 1 `zone_refinement` (naked level) → armed=0 follows; **no
  threshold was relaxed to force arming** (same documented batch-vs-live-loop limitation as D1).
- Width stats in `summary.json` (H4 p50: ob 16.2 / ds 21.2 / fvg 6.8 — much tighter than D1 p50 ~49–52).
- Determinism: byte-identical across two consecutive full runs (after fix 2).

## 5. Residuals (human step)

- Armed-quality judgment: no new armed rows — audit's original armed charts stand for re-score.
- Correctness of collapsed winners per chart (gates prove uniqueness, not expert agreement) —
  human CORRECT scoring not run in this pack.
- Usability of giant-candle H4 zones (100+ pt): selection judgment, explicitly not decided here.

## 6. Explicit non-claims

- No expectancy, PF, or edge claims (identification only).
- No claim that H4 zones arm or trade — only that H4 emission is unique, origin-tight, and reproducible.
- Locked constants untouched; V1.1 runtime baseline remains frozen.
