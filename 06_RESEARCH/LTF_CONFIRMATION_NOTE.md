# LTF CONFIRMATION NOTE (identification only — no trading decisions)

**Status:** COMPLETE · suite **762 passed** (754 pre-existing + 8 new), zero regressions, `locked_constants` diff empty.
**Scope bans honored:** no locked_constants / pillar / trigger / risk / TP-SL edits; no new selection thresholds or quality filters; no PnL / expectancy / win-rate / edge claims; no F-timing / Monte Carlo; identification-only; survey-first (below).

---

## 1. Survey findings (what the LTF pack had to reuse)

- **HTF source:** accepted packs as-is — `events_h4_poi.csv` (658 raw rows, post-F1F2 collapse, dual=0) + optional D1 subset ≤10 from `events_d1_poi_post_f1f2.csv`. No re-emission, no re-thresholding.
- **LTF stage-0:** `DetectionDriver.stage0` over resampled M15 (17,788) and M5 (53,358) series — the same detection layer the product runs, no thresholds added. `resample_ohlcv` is generic (M15/M5 identical path to H4/D1).
- **Router observation:** per-bar replay mirroring `PipelineAdapter.generate_candidates` — one `SeriesState(timeframe, atr_period)` extended per M5 bar; `engine.arm_at(poi, arm_bar)`; `engine.feed_bar`; `_may_route` mirror (FRESH→yes; TESTED→`bar ≤ tested_bar+1`); `engine.scan_route(..., scan_from=cursor, evaluation_candles=state.candles, evaluation_swings=state.swings, hints=state)`. Pillars/execution intentionally not run (`route_would_form` = pre-pillar router signal, disclosed everywhere).
- **Eligibility check (verified, not assumed):** `eligible_types` for M8 POIs = all six triggers A–F (`matrix.eligible_triggers`), so a `{F}`-only mix is an observation, not a filter artifact. `trigger_router.evaluate_at` was read end-to-end: `None` returns mean genuinely no signal — **no exception is swallowed** (no try/except in the evaluate/best-route path).
- **Product cross-ref:** `structure_identification_ledger.py` `route_ltf` rows (10 in the accepted 6-month ledger) cross-referenced into `notes` as `actual_product_route=...` (structure-level fact, window-independent).
- **Charts:** `render_d1_chart` (H4/D1 context panels) + a new `render_ltf_panel` in the pack script (M15/M5 panels: zone band, linked-event markers, arrow at structure close, same canvas constants/colors as the pack family).
- **Determinism:** `install_deterministic_poi_ids()` (patches `smc.core.poi.uuid4` → `poi-%07d` counter, same trick as the ledger script); structure ids geometry-derived (never `POI.id` = run-random uuid4 — lesson from the H4 pack).

## 2. What was built

- Script: `06_RESEARCH/scripts/ltf_confirmation_pack.py`.
- Outputs: `06_RESEARCH/results/ltf_confirmation/` — `events_ltf_confirmation.csv` (15,352 rows, exact 15-column schema), `summary.json`, `charts/` (39 PNGs, stale PNGs cleared each run), plus this report + note at `06_RESEARCH/`.
- Tests: `04_SRC/tests/test_ltf_confirmation_pack.py` (8): sample-selection caps + interleaving stability + full-panel-set rule; plain-tag contract (TF-suffixed, no module paths, explicit `NONE` rows); look-ahead consistency (`LA_M5_BARS == poi_give_up_bars() == TRIGGER_A_EXPIRY == 20`, `LA_M15_BARS == 7`, identical window rule every structure, disclosed series-end clamp); pinned strategy constants (a locked-constant change fails loudly).

## 3. Four defects found and fixed (script-local)

1. **Cross-pack dual tie (first run: GATE FAIL, dual=1).** H4 geometry `3683.365–3691.895` (`evt-6a8455eea149`) equals D1-subset geometry (`evt-bbf35c6dc170`). Both packs individually proved dual=0 — a cross-TF geometric coincidence is not a dual emission. Fix: dual/conflict gates computed **per source pack** (H4 among H4, D1 among D1); disclosed in report §4.
2. **Self-linking sub-bars (first run: active=668, silent=0).** Windows were anchored at the origin bar's OPEN, so a structure's own forming sub-bars linked to their own candle and every ambient in-zone event counted. Sensitivity probe: orig/any=658 active, after-close/zone-interaction=616/42. Fix: anchor at origin bar **CLOSE** (H4 +4h, D1 +24h) for both router arm and link windows, clamped to series **and** exec end; activity = zone-interacting link (`retest`/`inside`) or own trigger. Post-fix: **624 active / 44 silent**.
3. **0 routes (first run).** Verified genuine: probe on a touched structure ran all six eligible triggers through `evaluate_at` with no exceptions; product itself forms only 10 routes in 6 months; spec allows `TRIGGER_MIX: {}`. After the close-anchor fix (correct arm semantics) the honest count became **2** (both F).
4. **Sample skew (silent group empty → selection degenerate).** Fix: deterministic **interleaved** selection (active, silent, active, silent…) under the panel cap instead of all-actives-first. Post-fix sample: 7 active + 6 silent, 39 panels ≤ 40, active ≤12, silent ≤8.
   Also widened panel windows for close-anchored markers (M5 half 60→90 bars, marker at close+100 min sits inside ±7.5h; M15 half 24 covers ±6h; D1 structures anchor M15/M5 panels at close so ±windows hold for +24h origins too).

## 4. Disclosures (also in report §1)

- **Look-ahead:** M5=20 bars = `poi_give_up_bars()` = TRIGGER_A_EXPIRY (LOCKED §24, existing constant); M15=7 bars = `ceil(20×5/15)` (derived, covers ≥105 min ≥ 100 min). Same rule for every structure; only clamp = series end / exec end (disclosed, tested).
- **Anchor rule:** look-ahead and arm start at origin bar close; forming bar excluded (prevents self-linking).
- **Activity rule:** zone-interaction based; `above`/`below` links recorded but not counted — classification, not a filter; no tunable threshold introduced.
- **Pre-pillar:** `route_would_form` = router signal before pillars — approximation, not a product fill; no product execution semantics implied.
- **Replay vs product:** 0 timestamp overlap between this replay's 2 routes and the product's 10 `route_ltf` rows; different arm/scan context; neither declared correct (human gates open).
- **Subtitle fix (render-only):** `generate_d1_poi_pack.py:171` had `detection_tf: D1 | chart_tf: D1` hardcoded — wrong for every H4/D1 chart after the H4 pack reused it. Fix reads `row.get("detection_tf")/row.get("chart_tf")` with D1 fallback. Justification: presentation only; H4 pack re-run produced charts with correct per-row TFs and the CSV stayed **byte-identical** (script edit cannot touch data). LTF panels pass detection_tf/chart_tf explicitly (M15/M5).
- **Determinism:** double-run → CSV byte-identical, summary.json identical.

## 5. Residuals (human step)

- Human CORRECT/PARTIAL scoring of the 39 sampled panels (role/direction/label) — pack surfaces, does not score.
- Open armed-quality gates on original H4/D1 armed charts (not blocked here).
- Reviewer may disagree with the zone-interaction activity rule (624/44) — it is a disclosed classification, not a quality filter, and cannot be tuned in this pack.

## 6. Explicit non-claims

- No expectancy, PF, or edge claims (identification only).
- No timing analysis, no survivor logic, no Monte Carlo (bans honored).
- `LOGIC_CHANGED: NO` — no production (`04_SRC/smc/**`) edit this engagement; only research-script changes (new pack script + the render-only subtitle fix above).
