# POOL CONSOLE WIRE NOTE — ACTIVE POOL LEVELS + RECENT SWEEP HITS

Status: **PASS** (display/glue only) · Date: 2026-11-11 · Authority: Lead Architect
WIRE-LIGHT directive · `LOGIC_CHANGED: DISPLAY ONLY`

Read-only observability of the accepted P2a pool and P2b attribution on the
operator structure console. **Not a trading gate.** No detection math,
trigger, pillar, risk, fill or TP/SL change; ranking is still unfrozen; EQH/EQL
is never constructed or rendered (R-EQH-C).

---

## 1. Files touched

| File | Change |
| --- | --- |
| `04_SRC/smc/live/pool_board.py` | NEW. Pure read-only board builder: candles → P2a builders → `LiquidityPool` → active levels; P2b `attribute_sweeps` → recent hits grouped per bar. |
| `04_SRC/smc/live/structure_console.py` | `ACTIVE POOL` + `POOL SWEEPS` sections; `pool active: N` header line. The pre-existing POI-displacement `SWEEPS` section is untouched. |
| `04_SRC/smc/live/run_operator.py` | Thin glue: attaches the board on every structure refresh (`_pool_board_for`), cached by the last execution bar, failure degrades to an explicit note. |
| `04_SRC/tests/test_pool_console.py` | NEW, 8 tests (fake snapshots + synthetic candles, no MT5). |
| `00_LOCKED/SESSION_HANDOFF.md`, `00_LOCKED/POST_V1_ACTIVE_TODO.md`, `00_LOCKED/CHANGELOG.md` | Governance records. |

Untouched (verified empty diff): `04_SRC/smc/config/locked_constants.py`,
`04_SRC/smc/detection/**`, `04_SRC/smc/trigger/**`, `04_SRC/smc/risk/**`,
`04_SRC/smc/liquidity/**`.

---

## 2. Survey findings (cited, required by the directive)

* **Console module:** `04_SRC/smc/live/structure_console.py`. Existing sections:
  `STRUCTURE SCAN` (candidates, NOT armed) → `ARMED POI` → `SWEEPS`
  (POI-linked displacement, `SWEEPS: none`) → `SEEKING` → `PLAN`. The existing
  `SWEEPS` section is **POI-displacement only**, so it was kept verbatim and
  `POOL SWEEPS` was added as a **distinct** section (semantics stay honest).
* **Refresh cadence / rebuild triggers:** `run_operator.OperatorSession._maybe_refresh_structure`
  — a batch change (`batch_changed`) rebuilds immediately, new-bar refreshes are
  rate-limited to `config.console_refresh_s`; a pure timer poll rebuilds nothing.
  The pool board rides the same refresh (no second cadence).
* **Series available at refresh time:** `PipelineAdapter._candles` — the
  execution series the loop already holds (M5, `window_bars=200` on the loop,
  adapter keeps its own longer list). No new broker endpoint, no extra fetch.
* **Stage-0 sweeps per batch:** the runtime's batch report carries POI sweep
  *links* (consumed by the legacy `SWEEPS` section); pool sweeps are **derived
  on the held slice** by `attribute_sweeps`, which is cheap on the ~300-bar
  window (full rebuild per changed bar, cached by last bar timestamp).

---

## 3. Board layout (sample, synthetic data)

```
========================================================================
 STRUCTURE CONSOLE  |  2026-03-03T12:00:00+00:00 UTC   (read-only snapshot; armed 0)   pool active: 4
========================================================================
 pool active: 4
 STRUCTURE SCAN  (candidates - NOT armed)
   Locked POI definition NOT applied - not tradeable / not seeking
   (none) - no merged geometry in the last batch
------------------------------------------------------------------------
 ARMED POI  (locked definition only)
   W1 : (none)
   D1 : (none)
   H4 : (none)
   H1 : (none)
   (no armed POIs)
------------------------------------------------------------------------
 ACTIVE POOL  (read-only; display order only - NOT a trade priority)
   PWH/PWL: (none)
   PDH/PDL: (none)
   SESSION BSL    105.00  2026-03-02_ASIA      tf=M5
   SESSION SSL     99.00  2026-03-02_ASIA      tf=M5
   SESSION BSL    106.50  2026-03-02_LONDON    tf=M5
   SESSION SSL     99.00  2026-03-02_LONDON    tf=M5
   STRUCT : (none)
------------------------------------------------------------------------
 SWEEPS
   SWEEPS: none
------------------------------------------------------------------------
 POOL SWEEPS  (enter_at-safe; recent)
   POOL SWEEPS: (none)
------------------------------------------------------------------------
 SEEKING
   SEEKING: none
------------------------------------------------------------------------
 PLAN
   PLAN: none
========================================================================
```

Notes on the layout:

* Display order inside `ACTIVE POOL` is the **R3 soft order for readability
  only** (PWH/PWL → PDH/PDL → SESSION → STRUCT). It is never consulted by
  attribution, routing or risk.
* `SESSION` rows print `tf=M5`, satisfying R1 (session levels computed on M5).
* An empty family prints `(none)`; an empty pool prints
  `(none) - no active pool levels`; absence of a pool snapshot prints
  `(none) - pool snapshot unavailable`. The board never silently blanks.
* Attribution that cannot run prints `POOL SWEEPS: n/a (<reason>)`; a render
  never raises.
* Multi-hit bars render one line with every level listed and no winner:
  `03-03 12:00  n=2  session/BSL 2400.00  previous_day/BSL 2400.00`.

---

## 4. Data path

```
adapter._candles (M5 execution series, already held)
        │
        ├── detect_session_levels(candles, M5) ──► from_session(source_tf=M5)
        ├── detect_periodic_levels(candles, M5) ─► from_pdh_pdl / from_pwh_pwl
        └── detect_swings(HTF only) ─────────────► from_structural
                        │
                 LiquidityPool.add(level)   (sorted by enter_at)
                        │
        pool.inventory(last_bar_ts)  ────────────► ACTIVE POOL rows
                        │
        attribute_sweeps(pool, candles, levels=tf_levels)
          start_index = resolve_start_index(series, enter_at)
                        │
        group hits by sweep bar, last 8 bars ─────► POOL SWEEPS rows
```

`formed_at` is never forwarded as the scan start (that would leak
pre-publication bars); every hit is bounded by the level's `enter_at`.

---

## 5. Confirmation: not a trade gate

* `pool_board.build_live_pool_board` only READS candles and returns dicts.
* The console snapshot is built after the loop's decisions and is consumed only
  by the renderer / structure-draw publisher (viz only).
* Nothing in `smc/detection`, `smc/trigger`, `smc/risk`, `smc/orchestration` or
  `smc/paper` imports `pool_board` or `smc.liquidity` on a decision path.
* `dry_run` display parity: the board is built from candles and pool state, not
  from order permission, so a dry-run session shows identical pool/hit rows.

Tests pin: grouped/ordered render, explicit `(none)` for empty and absent pool,
`n/a (reason)` for failed attribution, multi-hit bars listing every level, no
EQH family ever built or rendered, and every hit at or after its `enter_at`.

---

## 6. Verification

* Suite: **1471 passed, 7 skipped** (`cd 04_SRC && PYTHONPATH=. python -m pytest -q`).
* `locked_constants.py` diff: **empty**.
* `smc/detection`, `smc/trigger`, `smc/risk`, `smc/liquidity` diffs: **empty**.
* `DRY_RUN_PROVEN: SKIPPED` — no terminal available in this session, so no live
  board was captured. The board is built only from already-held candles, and the
  unit tests exercise the same builder path the operator uses.

---

## 7. Residuals (explicit)

* **Family coverage in live V1:** the operator's ~300-bar M5 window can support
  session levels and, when it spans a completed prior day, PDH/PDL. PWH/PWL
  needs a completed prior week and STRUCT needs H4/H1 detection series, so both
  render `(none)` until the caller supplies those series. No fabrication.
* **Broken structural exit** remains deferred (supersession-only lifecycle).
* **Ranking still not frozen** (measurement-first); the R3 sort lives only in
  the console render and `inventory_sort_key`, never in a decision.
* **No seek handoff** — pool levels are not routed to the menu or any seek path.
* No expectancy/edge claim is made or implied by this board.
