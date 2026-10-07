# LIVE STRUCTURE CONSOLE — NOTE (Milestone L1)

**Directive:** Lead Architect, 2026-10-06 — Milestone L1 (after Milestone W PASS)
**Status:** PASS — suite 849 passed, `locked_constants.py` diff empty
**Design doc:** `06_RESEARCH/LIVE_STRUCTURE_CONSOLE_DESIGN.md`
**Correction (2026-10-06 dry run):** W1 enum value fixed 32768 → **32769**
(the MetaTrader5 package's `TIMEFRAME_W1`; 32768 is rejected live by
`copy_rates_from_pos` with "Invalid params"). Weekly rows on the console
are unaffected — they render from the engine book either way.

## 1. What was built

A read-only live structure console for the operator command prompt with
four sections — **POIS / SWEEPS / SEEKING / PLAN** — following the existing
pure-renderer pattern (`operator_console.py`):

- `04_SRC/smc/live/structure_console.py` (NEW):
  `build_structure_snapshot()` (read-only snapshot from engine/adapter/loop
  state) + `render_structure_console()` (pure ASCII renderer).
- `04_SRC/smc/live/run_operator.py` (WIRED): snapshot rebuilt on a new M5
  bar and/or HTF batch advance, rate-limited to `console_refresh_s` (min
  1 s); board printed + mirrored under the status board.

## 2. Data sources (all live, nothing hardcoded)

| Section | Source |
|---------|--------|
| POIS | `engine.tracked_pois()` / `engine.episode()` / `engine.state_machine.current()` — armed POIs grouped W1 → D1 → H4 → H1 with direction, kind, zone bounds, armed, state, short id |
| SWEEPS | new cumulative `LiveLoop.sweep_links` (fed from the new additive `MultiTFBatchReport.displacements` field) ∩ current armed book — POI + TF + side (+ magnitude ×ATR), or `SWEEPS: none` |
| SEEKING | armed POIs with §5 state + `SeekPosture` + targeted trigger letter (`TriggerType.value`) from `PipelineAdapter.active_workflows()`, `-` when no route yet |
| PLAN | routed candidates only: direction, entry, SL, TP, `tp_source`, trigger, POI id — else `PLAN: none` |

**Weekly rows are LIVE:** W1 rows come from the same engine book as every
other TF (provisioned by Milestone W) — the tests pin that a rendered W1
row carries the actual zone numbers, not demo values.

## 3. Additive seams (no behavior change, no second detection stack)

1. `MultiTFBatchReport.displacements` — POI id → `{"side", "magnitude_atr",
   "passed"}` per passed POI with a paired displacement. Display only.
2. `LiveLoop.sweep_links` — cumulative merge of report displacements.
3. `PipelineAdapter.active_workflows()` — public read-only COPY of the §11
   workflow map.
4. `OperatorSession` — `state["structure"]` + `_maybe_refresh_structure()`
   + board publish. Any snapshot failure is logged, never fatal.

## 4. Tests (`04_SRC/tests/test_structure_console.py`, 11 tests)

- POIS grouping (W1/D1/H4/H1 order), live W1 zone numbers on the board,
  honest `(none)` sections, fully-empty board renders all four honest
  empties.
- SWEEPS linked rows (untracked links dropped) and `SWEEPS: none`.
- SEEKING state/posture/trigger letter; `-` without an adapter.
- PLAN full candidate line (`entry=… sl=… tp=… src=… trig=… poi=…`) and
  `PLAN: none` without workflows.
- ASCII-only board check.
- `active_workflows()` returns a copy (no aliasing of §11 state).
- Runtime report collects sweep links (fabricated disp_map); LiveLoop
  merges them into `sweep_links` (fake runner, no MT5).

## 5. Cadence & limits

- Refresh trigger: new M5 bar and/or `htf_batches` advance; rate-limited to
  `console_refresh_s`. Unarmed/undetected structure (e.g. zero weekly zones
  on a young symbol) renders honestly as `(none)` — never fabricated.
- Console is read-only: no MT5 chart objects, no order actions, no decision
  reads it. Trading logic unchanged; `locked_constants.py` diff remains
  empty.
- Known residual: sweep links exist only for POIs whose detection batch
  paired a displacement (M8 zone-only POIs legitimately show none — the
  §3 displacement pairing is the source of truth, nothing is inferred).
