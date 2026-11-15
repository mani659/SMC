# CONSOLE V2 — MTF BOARD + STRUCTURE SCAN vs LOCKED ARMED POI

**Date:** 2026-11-02
**Authority:** Lead Architect — "CONSOLE V2 — MTF BOARD + STRUCTURE SCAN vs LOCKED ARMED POI" (GO)
**Scope:** display / telemetry only. `LOGIC_CHANGED: NO`.

---

## 0. Why

Operators reported the console showing `armed 0` while the chart still had
visible structure. The status board also described the multi-TF path only as
one flat `H4 23/11/3  H1 21/8/0` line, so the configured detection set, the
degraded flag and any failed fetch were not readable.

Console V2 splits the two questions that were previously conflated:

| Question | Answer now lives in |
|---|---|
| "What geometry do the detectors see right now?" | **STRUCTURE SCAN** (candidates) |
| "What has the locked definition armed / is seeking?" | **ARMED POI** + SEEKING + PLAN |
| "What is this session actually configured to detect?" | **MTF block** on the status board |

---

## 1. Contract table — SCAN vs ARMED

| Aspect | STRUCTURE SCAN (Section A) | ARMED POI (Section B) |
|---|---|---|
| Meaning | merged detector geometry, **before** the locked pillar definition | the product book: POIs the engine actually armed |
| Data source | `MultiTFBatchReport.scan` — read-only rows built from the batch's own merged `ValidationResult`s (capped `SCAN_ROWS_PER_TF = 6` per TF, newest first) | `PipelineEngine.tracked_pois()` + `engine.episode(poi)` (unchanged L1 source) |
| TFs | any detection TF present in the last batch (W1/D1/H4/H1 first, then others) | `SECTION_ORDER` W1/D1/H4/H1 (+ any other TF shown honestly) |
| Fields | direction, kind (`ob`/`demand_supply`/`fvg`/model tags), `[low,high]`, zone time | direction, kind, `[low,high]`, `armed=yes`, §5 state, short id |
| Counts | `N candidate(s)` + per-kind breakdown per TF | board header `armed N)` + the rows themselves |
| Empty state | `(none) - no merged geometry in the last batch` | `TF : (none)` per timeframe |
| Drives any decision | **no** | yes (unchanged, engine-owned) |
| Allowed words | candidate, structure, zone, scan | armed, POI, state, posture, trigger |
| Banned words | armed, POI, POI ready, entry, signal, take trade | — |

`SCAN` rows never carry `armed=yes`, never carry `entry=`, and never appear in
SEEKING or PLAN — those sections reference armed workflows only.

---

## 2. Status-board MTF block

New lines on the operator status board (rendered by
`smc/live/operator_console.render_status_board`):

```text
 terminal : C:\Program Files\MetaTrader 5 EXNESS - Copy  id: MetaTrader 5 EXNESS - Copy  server: Exness-MT5Trial15
 detect   : htf batches 4  armed 1  arm-errors 0
            H4 23/11/3  H1 21/8/0
 mtf      : exec M5  detect H4,H1  optional W1,D1  degraded NO
            per-TF raw/merged/passed/armed: H4 23/11/3/1  H1 21/8/0/0
            scan: 3 candidate row(s)  (NOT armed - see STRUCTURE SCAN)
```

* `detect H4,H1` — the **configured** detection set from the runtime
  (`runtime.detection_timeframes`), not a remembered default.
* `optional W1,D1` — provisioned context tiers (`runtime.optional_timeframes`).
* `degraded YES/NO` — the report's own degraded flag.
* `per-TF raw/merged/passed/armed` — batch counts plus the armed-POI count per
  TF read from the structure snapshot (`armed_by_tf`).
* A configured TF with no counts prints `H4 FAILED` (loud, never a silent 0),
  and a failed fetch also prints `MISSING SERIES: H4 (configured, fetch failed)`.
* `degraded_opt_in` (config `allow_single_tf_degraded`) stamps
  `DEGRADED OPT-IN ACTIVE - single-TF fallback is NOT product mode`.

---

## 3. Example board (rendered from fakes, ASCII only)

```text
========================================================================
 STRUCTURE CONSOLE  |  2026-11-02T09:30:00+00:00 UTC   (read-only snapshot; armed 1)
========================================================================
 STRUCTURE SCAN  (candidates - NOT armed)
   Locked POI definition NOT applied - not tradeable / not seeking
   D1 : 1 candidate(s)  demand_supply 1
      SHORT demand_supply  4060.00-4085.00     t=2026-11-02T00:00
   H4 : 1 candidate(s)  fvg 1
      LONG  fvg            3995.00-4002.00     t=2026-11-02T04:00
   H1 : 1 candidate(s)  ob 1
      LONG  ob             4001.00-4006.00     t=2026-11-02T08:00
------------------------------------------------------------------------
 ARMED POI  (locked definition only)
   W1 : (none)
   D1 : (none)
   H4 : LONG  ob             3998.00-4010.50     armed=yes  state=FRESH  id=c493ac99
   H1 : (none)
------------------------------------------------------------------------
 SWEEPS
   H4  side=LONG  1.20x ATR    -> poi c493ac99
------------------------------------------------------------------------
 SEEKING
   c493ac99  H4  state=FRESH    posture=CLEAN_ARM        trigger=-
------------------------------------------------------------------------
 PLAN
   PLAN: none
========================================================================
```

Empty-scan case (successful batch, nothing merged):

```text
 STRUCTURE SCAN  (candidates - NOT armed)
   Locked POI definition NOT applied - not tradeable / not seeking
   (none) - no merged geometry in the last batch
```

---

## 4. Refresh semantics

* **Batch change → immediate rebuild** (the 2026-10-06 armed-visibility rule is
  preserved). The same rebuild now also refreshes SCAN and `armed_by_tf`.
* New execution bars stay rate-limited by `console_refresh_s`.
* Idle polls still do nothing.
* SCAN rides the **same** snapshot as the structure board: one snapshot, one
  cadence, no second timer and no per-poll detection.
* Every count is a **clone** of numbers the batch already produced; the console
  path never re-derives detection, never re-validates, never arms.

---

## 5. Read-only proof

`build_structure_snapshot` only calls `engine.tracked_pois()`,
`engine.episode(poi)`, `engine.state_machine.current(poi)` and
`adapter.active_workflows()`. `MultiTFProductRuntime` builds `report.scan`
from `result.details` **before** arming and never touches a POI.

Pinned by `04_SRC/tests/test_console_v2_scan.py`:

1. SCAN non-empty while ARMED empty (the original operator complaint).
2. ARMED lists rows and the header `armed N)` equals the row count.
3. Strict read-only engine fake: `arm_at` / `place` / `set_pipeline_adapter`
   raise if the console ever calls them; renderer is pure (two renders equal).
4. Runtime proof: a merged-but-rejected geometry yields `report.scan == 1`
   with `report.armed == []` and `engine.tracked_pois() == []`.
5. Scan rows capped per TF (`SCAN_ROWS_PER_TF`), newest first.
6. Status board shows the configured detection set, per-TF
   raw/merged/passed/armed, `degraded NO/YES`, missing-series naming and the
   degraded opt-in stamp.
7. `OperatorSession` seam: `report.scan` reaches the snapshot; `armed_by_tf`
   and `scan_total` are published for the board.

Suite after the change: **1374 passed** (was 1361; +13 in the new file).

---

## 6. Bans honoured

* No pillar / trigger / threshold / `locked_constants` change — diff empty.
* No new arming rule; SCAN never calls `arm`, `place` or risk entry.
* Candidates are never labelled POI, armed, signal, entry or tradeable.
* No `OrderSend` from any console path (Python console only; MQL5 untouched).
* No coupled-vs-Mode-A switch in this task: the existing opt-in strategy_mode
  path is unchanged.

---

## 7. Known limits

* SCAN shows the **last batch's** merged geometry per detection TF; it is a
  batch snapshot, not a live per-tick inventory.
* Rows are capped at `SCAN_ROWS_PER_TF` (6) per TF; the per-kind counts in the
  TF header describe what is shown, not the whole merged set.
* The standalone judgement board (`judgement_console`, design lock
  `00_LOCKED/MODE_T_CONSOLE_MARKER_DESIGN.md` §3) is unchanged: its block list
  is frozen, so SCAN appears on the structure/status boards, not there.
