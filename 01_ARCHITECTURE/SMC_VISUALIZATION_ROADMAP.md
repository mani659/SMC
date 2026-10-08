# SMC VISUALIZATION ROADMAP (locked 2026-09-20)

**Status:** Governance record — conviction support, NOT an edge-validation track, NOT an MQL5 logic expansion.
**Authority:** Lead Architect instruction 2026-09-20; checklist in `00_LOCKED/POST_V1_ACTIVE_TODO.md` Track V; plan anchor in `POST_V1_PLAN_OF_ACTION.md` §6b.
**Option A preserved:** Python owns all logic at every stage. Any MQL5 chart work is draw-only.

---

## 1. Purpose

Let an operator/researcher SEE which trade or candidate matched which rule: levels → sweep → displacement → POI/pattern → entry or reject reason. Charts support conviction discussions (R3/R4 follow-ons, FLOWCHART_MATCH); they never substitute for identity export or backtest evidence.

## 2. Layered approach (binding order)

1. **V0 — Identity export (COMPLETE 2026-09-20).** `model_tags` + `pillar_path` + `disp_magnitude_atr` on every admitted trade (backtest/paper/live). Prerequisite for everything below. Note: `06_RESEARCH/EXPORT_IDENTITY_PATCH_NOTE.md`.
2. **V1 — Python research visualizer (near-term conviction tool).** Offline charts from backtest/paper logs + R3/R4 artifacts. Python-only, no terminal needed. Reads the V0 identity fields; draws the rule chain per trade/candidate.
3. **V2 — Drawable event schema.** Frozen event shapes for level / sweep / poi / fvg / entry / state-transition, sourced from the same V0 fields, feeding V1 and V3 identically.
4. **V3 — MT5 display-only overlay for the paper terminal (later, paper support only).** Renders V2 events on-chart. Zero strategy logic in MQL5 — hard constraint, not a guideline.
5. **V4 — Clean-chart rules validated.** Shared object prefix; ownership by poi_id/route_id; delete on TESTED/VIOLATED/expiry; layer toggles (Levels / Sweeps / POIs / FVGs / Entries); history cap against clutter.

## 3. Clean-chart rules (binding for any overlay work)

- Every chart object carries the shared prefix and its owning poi_id/route_id.
- Objects die with their thesis: delete on TESTED / VIOLATED / unfilled-order expiry / give-up.
- Layer toggles per family (Levels, Sweeps, POIs, FVGs, Entries); default to the minimal conviction view.
- Bounded history: cap drawn objects (count- or age-based); no unlimited accumulation.
- No mixed messy drawing without lifecycle rules; no strategy code paths that depend on drawn objects.

## 4. Dependency on identity fields

V1/V2/V3 consume exactly: `model_tags`, `pillar_path` (+ first-failure detail), `disp_magnitude_atr`, plus existing `poi_id` / `trigger` / `route_id` / entry / sl / timestamps. If a future visual needs a field the export lacks, the export is extended first (logging-only patch pattern) — visuals never reconstruct rule identity from prices.

## 5. Non-goals

- No MQL5 detection/entry/strategy logic, now or later.
- No overlay-driven decisions (charts don't trade).
- No using overlays as a substitute for identity export or statistical evidence.
- No V3 before V1+V2; no V1 before V0 (cleared).
- No parameter tuning or redesign inside visualization work.
