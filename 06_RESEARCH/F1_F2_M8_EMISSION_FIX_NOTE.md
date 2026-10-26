# F1/F2 M8 EMISSION FIX NOTE (identification only — no trading decisions)

**Status:** COMPLETE · suite **750 passed** (737 pre-existing + 13 new), zero regressions.
**Scope bans honored:** no pillar/trigger/RiskEngine/TP-SL/lot/spread/threshold edits; no new models or tags; no expectancy claims; survey-first (below).

---

## 1. Survey findings (pre-fix emission mechanics)

- **M8 emission path:** `M8HtfDemandSupply._zones(series, tf)` yields `(kind, direction, start_index, zone)`; kinds `ob` (candle before first FVG candle, R1 §3.1), `fvg` (gap zone), `demand_supply` (single last opposing candle before ≥1×ATR impulse, §22). `zone_for_candle` = full wick range of ONE candle (no buffer) — ob/ds zones were ALWAYS single-candle.
- **Dual emission confirmed live in audit output:** evt-98a04a (ob SHORT) + evt-30783c (demand_supply SHORT), identical bounds 3343.448–3384.495 — same origin candle qualifying under both facets. Direction conflicts also present (3 exact-bounds groups, audit 007/008 etc.).
- **Ledger hook wraps `_zones`** (`structure_identification_ledger.m8_zones_wrapper`): per-kind rows = the audit's dual source. D1 pack reads ledger rows (not `detect()` POIs).
- **Downstream:** `merge_overlapping` reconstructs POI (drops unknown fields — patched to propagate); `ZoneDedup` is direction-aware (opposite-direction duplicates arm twice — F1 collapse required); arm path registers episodes. `M8.detect()` keeps latest-per-(direction,kind) (≤6/TF).
- **Existing tests:** `test_poi_models.py` M8 block (acceptance/ignore/overlap/empty); `test_confluence_scorer.py` M8 bonus. All green post-fix, unweakened.
- **Width measurement (D1 Mar–Dec 2025, pre-fix _zones):** 231 yields — demand_supply p50 52.9/max 193.0, ob p50 49.3/max 127.7, fvg p50 21.7/max 85.2. The widest "demand" rows ARE single giant D1 candles (verified: 193.0pt row == origin candle range exactly). 27 exact-bounds multi-yield groups, 3 with direction conflicts.

## 2. F1 collapse policy + episode key

- **Rule:** one geometric episode → one POI. Never LONG+SHORT on one bounds; never two kinds differing only by facet on one bounds+direction.
- **Episode key:** `(round(bottom,3), round(top,3))` — direction deliberately EXCLUDED (conflicts must collide); origin-bar excluded (series-relative indices shift across windows; bounds ARE the identity). Float rounding is belt-and-braces on 3-decimal vendor data.
- **Winner:** kind priority ob(0) > demand_supply(1) > fvg(2) [per Architect; fvg residual documented as tie-break order, not tuned] → direction name ascending (LONG-first, arbitrary-but-deterministic, disclosed) → earliest origin (episode seniority).
- **Location:** inside `_zones` (buffered collect → collapse → chronological yield), so the ledger hook, `detect()`, and every consumer see one POI. Implemented as module-level `collapse_episodes()` (pure, unit-tested) + `M8_KIND_PRIORITY` export.
- **Facet visibility:** new `POI.m8_kind` (winner kind; logging/identity only, never a trading input); merge propagates via sorted `+` join; models stays `[M8]` (no new tags — enum ban honored).
- **Alternative rejected:** collapse only in chart export (product path would still see duals — explicitly forbidden by prompt).

## 3. F2 zone rule chosen + measurement basis

- **Verdict: Option A VERIFIED ALREADY TRUE — no construction change.** Measurement proves ob/demand_supply zones equal their origin candle's exact range (bit-stable across runs; origin-tight violations on re-sample: **0**). A 193-pt "demand on a top" IS one 193-pt bearish D1 candle — wide by October-2025 volatility, not by envelope construction. Shrinking it would violate §22's full-range rule.
- **FVG gaps** are multi-candle by definition (R1 §3.1 imbalance); redefining them is out of scope (ripples into Pillar 1/trigger geometry).
- **Width cap REJECTED with rationale:** any K invents selection criteria (prompt-forbidden random shrinking); usability of giant-candle zones belongs to human re-score, which now has tight-geometry charts to judge. NO new constant → `LOCKED_CONSTANTS_DIFF: empty`.
- Regression guard added instead: origin-candle invariant tests (ob/ds == origin range exactly; FVG == definitional gap; huge-candle case; bit-stability).

## 4. Mechanical gate results (D1 re-sample, exec 2025-06-01 → 2025-11-30)

- Script: `06_RESEARCH/scripts/d1_f1f2_resample.py` (same warm-up 2025-03-01, same `render_d1_chart` visual language, same CSV schema + kind column).
- `events_d1_poi_post_f1f2.csv`: **137 raw rows** (ob 43 / demand_supply 50 / fvg 44), 2 merged, 0 armed.
- **dual_exact_bounds_count = 0. direction_conflict_count = 0. origin_tight_violations = 0.**
- Charts: 20 (0 armed + 10 ob + 5 demand + 5 supply = full demand_supply spread of 10 across directions).
- **Armed = 0 explained (not hidden):** rolling 60-bar batch validation rejects everything on this window (Pillar 1 zone_refinement, same as the product probe) — batch re-validation of aged zones cannot reproduce the audit's M5-loop formation-time arming. Armed-quality re-score therefore proceeds on the AUDIT's original 6 armed charts (files untouched), not on new rows. No thresholds were touched to force arming.
- Width stats by kind recorded in `summary.json` (fvg p50 20.6/max 84.7; ds p50 49.4/max 193.0; ob p50 49.4/max 114.0).

## 5. Residuals (what human re-score must still judge)

- Whether collapsed winners (ob-priority) match expert zone choice per chart (mechanical gates prove uniqueness, not correctness).
- Armed quality (051-style LONG-into-top cases): no new armed rows produced — original 6 stand for re-score.
- Whether giant-candle zones (100+ pt) are usable POIs (selection judgment, explicitly not decided here).
- Merged-row ts uses origin ts (no M5-loop arm times in re-sample — documented approximation).
- FVG-vs-ob exact-bound coincidences (kind rank decides silently; count in re-sample: report in summary if nonzero — check output).

## 6. Explicit non-claims

- No expectancy, PF, or edge claims (identification only).
- No human CORRECT rates (re-score remains Architect/user step).
- No claim that collapse improves trading — only that emission is now unique and bounded.
- Phase C book untouched; no baseline comparisons offered.
