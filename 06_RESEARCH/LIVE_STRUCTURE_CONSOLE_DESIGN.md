# LIVE STRUCTURE CONSOLE — DESIGN (Milestone L1)

**Directive:** Lead Architect, 2026-10-06 (two-sequence engagement: W → L1)
**Status:** IMPLEMENTED — see `06_RESEARCH/LIVE_STRUCTURE_CONSOLE_NOTE.md`

## 1. Purpose

Operator command-prompt view of the LIVE structure state for human
second-validation: Weekly / Daily / H4 armed POIs at a glance, the sweep
linked to each, what the engine is currently seeking, and the plan only
when a candidate/route actually exists. **Read-only snapshot + render** —
no decision logic reads it, nothing is written to MT5 (never chart objects).

## 2. Sections and columns

```
========================================================================
 STRUCTURE CONSOLE  |  2026-10-06T12:00:00+00:00 UTC   (read-only snapshot)
========================================================================
 POIS
   W1 : LONG  ob             2340.10-2355.50   armed=yes  state=FRESH  id=ab12cd34
   D1 : (none)
   H4 : SHORT demand_supply  2310.00-2318.40   armed=yes  state=FRESH  id=9988ccdd
   H1 : (none)
 ------------------------------------------------------------------------
 SWEEPS
   W1  side=LONG  1.42x ATR   -> poi ab12cd34
 ------------------------------------------------------------------------
 SEEKING
   ab12cd34  W1  state=FRESH   posture=CLEAN_ARM     trigger=-
 ------------------------------------------------------------------------
 PLAN
   PLAN: none
 ========================================================================
```

| Section | Columns | Source |
|---------|---------|--------|
| POIS | TF (W1, D1, H4, H1 order) · direction · kind (`m8_kind` or model tags) · `zone_low-zone_high` · armed yes/no · §5 state · short id (8 chars) | `engine.tracked_pois()` + `engine.episode()` + `engine.state_machine.current()` |
| SWEEPS | TF · side (`LONG`/`SHORT`) · magnitude (×ATR) · linked short id | loop's cumulative sweep links (batch `disp_map`) ∩ current armed book |
| SEEKING | short id · TF · state · arm posture (`SeekPosture`) · targeted trigger letter (`TriggerType.value`, `-` when no route yet) | same POI rows + adapter `active_workflows()` |
| PLAN | direction · entry · SL · TP · `tp_source` (`structural_swing`/`atr_fallback`) · trigger letter · POI id | adapter `active_workflows()` candidates only |

Honest empties are a hard rule: a timeframe with zero armed POIs prints
`(none)`, no sweeps prints `SWEEPS: none`, no armed POIs prints
`SEEKING: none`, no candidate prints `PLAN: none`. Missing fields degrade
to `n/a` (operator-console convention) — nothing is ever invented.

## 3. Data flow (read-only)

```
LiveLoop.batch report.displacements  ──merge──▶  LiveLoop.sweep_links (cumulative)
PipelineEngine (tracked/episode/§5)  ─┐
PipelineAdapter.active_workflows()    ─┼─▶ build_structure_snapshot() ─▶ snapshot dict
LiveLoop.sweep_links                  ─┘           │ (pure)
                                                   ▼
OperatorSession.state["structure"]  ─▶  render_structure_console() ─▶ board text
```

* `MultiTFBatchReport.displacements` (NEW, additive field): POI id →
  `{"side", "magnitude_atr", "passed"}` for every passed POI whose
  displacement context paired it with a liquidity sweep. Display only.
* `LiveLoop.sweep_links` (NEW, additive): cumulative merge across batches
  so weekly links survive between H1-cadence batches.
* `PipelineAdapter.active_workflows()` (NEW, additive): public COPY of the
  §11 one-shot workflow map (POI id → `CandidateEntry`) so the console
  never touches private bookkeeping.

## 4. Refresh cadence

* **Trigger:** a new execution (M5) bar and/or an HTF batch advance
  (`htf_batches` changed).
* **Rate limit:** the board cadence — at most one rebuild per
  `console_refresh_s` (min 1 s). The operator reads a stable board, not a
  flickering one.
* **Publish:** the structure board is appended under the existing status
  board on every `_publish_console()` and mirrored to
  `console_mirror.log`.

## 5. Non-goals / guarantees

* Not an MT5 chart dashboard — text only, ASCII only (Windows code page).
* The snapshot builder and renderer are pure functions of their inputs —
  unit-testable without a terminal (tests use a REAL engine + synthetic
  POIs; no MT5 anywhere).
* Weekly rows are LIVE data: the tests pin that a W1 row carries the
  actual synthetic zone numbers, never hardcoded demo rows.
* Zero decision impact: no detection re-derivation, no thresholds, no
  SL/TP/risk values consumed or changed; `locked_constants.py` untouched.
