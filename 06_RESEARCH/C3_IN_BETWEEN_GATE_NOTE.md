# C3 — SHARED IN-BETWEEN CONTAINMENT GATE

**Date:** 2026-11-12 · **Status:** PASS · **Scope:** C3 only
**Authority:** master card §3.4 (in-between binary), amendment list (entry validity),
gap plan row G05 (TOP_BLOCKER). Prerequisite C2a PASS (not reopened).
**`LOGIC_CHANGED: YES`** — entry validity gate only; no threshold, geometry, SL/TP or risk change.

---

## 1. Completion-price definition (frozen)

**`COMPLETION_PRICE = close`** — the CLOSE of the completion bar
(`signal.completion_index`) on the confirmation/execution series.

One definition everywhere: the adapter and the menu both read
`candles[signal.completion_index].close` and hand it to the gate. The limit
entry price (`signal.entry_price`) is **not** used for validity — it is the
resting order and may legitimately sit inside the zone while the bar closed
outside it (that completion is now invalid). No wick/high/low variant exists
on either path.

---

## 2. Helper (single geometry, no new numbers)

`04_SRC/smc/triggers/in_between.py`

| Symbol | Contract |
|---|---|
| `price_inside_zone(price, zone_low, zone_high)` | Inclusive `low <= price <= high`; inverted bounds, NaN and unparseable inputs → `False` (fail closed). |
| `trigger_in_between(*, zone_low, zone_high, completion_price)` | Master card §3.4 gate; thin wrapper over the containment predicate. |
| `NOT_IN_BETWEEN` | `"not_in_between"` — the machine-readable reject token. |

No ATR tolerance, no median gate, no `locked_constants` value. The median of
the zone remains a placement detail only and is untouched.

---

## 3. Where the gate lives (one choke point)

`candidate_from_route` (`04_SRC/smc/backtest/pipeline_bridge.py`) gained
`completion_price: float | None = None` and returns **`None`** when the close
is outside the POI body. Every placement candidate in the product is built by
this one function, so no path can bypass the gate while still producing a
`CandidateEntry`.

| Call site | Before | After |
|---|---|---|
| `smc/backtest/pipeline_adapter.py` — `generate_candidates` route→workflow | Any route became a workflow/candidate | Passes the completion bar's close; `None` ⇒ no workflow, no `_routed` mark, scan cursor resumes at the next bar (a later in-between completion can still win). |
| `smc/orchestration/product_menu_mtf.py` — `_candidate` | Any route became a candidate | Passes the close; `None` ⇒ `_win` appends `rejected_<TF>_not_in_between`, episode stays `ACTIVE`/unconsumed, scan continues on later bars. |
| `smc/orchestration/product_menu_mtf.py` — `_win` / batch loop | Always consumed and appended a winner | Skips rejected completions; no winner appended (`_win` returns `None`). |
| `smc/backtest/pipeline_bridge.py` — `fvg_context_for_route` | — | Unchanged; runs only for candidates that passed. |
| `smc/backtest/pipeline_adapter.py` — `queue_menu_candidate` | Defensive `None` guard | Unchanged (receives already-gated candidates; live loop inherits). |
| `smc/dumb/mtf_paper_adapter.py` | Research DUMB path builds `CandidateEntry` directly from `DumbMtfRoute` (no `TriggerRoute`, no trigger signal) | **Not gated** — documented as research-only, outside the product entry contract. |
| `smc/orchestration/engine.py` — `scan_route`/`evaluate_at` | Produces `TriggerRoute` only, no candidate | Unchanged by design: routing geometry stays as-is, validity is applied where placement intent exists. |

Tests that call `candidate_from_route` without `completion_price` (pure
mapping/identity checks) keep their pre-C3 behaviour; every placement caller
passes the close, so the product contract is enforced.

---

## 4. Interaction with existing geometry (no double invention)

- **FR-3 gate** (`entry_within_zone`, ±0.5×ATR band) and **FR-3.1**
  (`zone_anchored_entry`) are untouched: the limit may still sit within the
  refinement band; the completion must additionally close inside the **body**.
  The C3 check applies zero tolerance by design.
- **R7 / fill regime** untouched.
- **§5 seek/scan/posture** untouched: no routing, give-up or state rule moved.
- **C2a** untouched: Rule 3 still cannot route (`is_live_choch`).
- No tolerance widening (`ZONE_REFINEMENT_ATR`, FR-3 band unchanged), no
  constants edited.

---

## 5. Tests

New `04_SRC/tests/test_c3_in_between_gate.py` (8):
- **T1** `price_inside_zone`: inside / inclusive edges / below / above /
  inverted / unparseable; `trigger_in_between` parity; token value.
- **T2** in-between completion → candidate built (zone bounds carried).
- **T3** completion above the zone → `None`; completion below → `None`.
- **T4** menu `_candidate` builds nothing for an out-of-zone completion and
  still builds for an in-between one.
- **T5** C2a regression smoke: Rule 3 not live, Rules 1/2 live.

Fixtures updated (no assertions weakened) where a synthetic completion
legitimately fell outside its zone:
- `test_backtest_pipeline_integration.py` (`CALM_SIGNAL` close 100.5 → 100.2)
- `test_paper_runner.py`, `test_backtest_reports.py` (same signal bar)
- `test_adapter_scan_semantics.py` (fire bar closes on the zone top, 100.2)
- `test_confirm_vs_zone_opt1.py` (out-of-zone distance now verified on
  `_completion_metrics` directly — C3 makes such a completion non-winning;
  the report-only metric is unchanged)

**Suite:** 1493 passed / 7 skipped (1485 + 8 new). No skips added.

---

## 6. Explicitly NOT done

- No boundary-sweep fallback product emitter (G06 — design later).
- No color-free Demand/Supply (C2b).
- No D0/C1 detection-TF contract work.
- No TP/SL/risk/fill-regime/R7/R9 change; no constant edits.
- No LOCKED_DECISIONS/ESSENCE body rewrite; no expectancy claim.
- No drive-by refactors.

---

## 7. Return block

```text
C3_STATUS: PASS
COMPLETION_PRICE: close
HELPER_PATH: smc/triggers/in_between.py:trigger_in_between
ADAPTER_GATED: YES
MENU_GATED: YES
REJECT_REASON_TOKEN: not_in_between
TESTS_ADDED_OR_UPDATED: 8
SUITE: 1493/0
NOTE_PATH: 06_RESEARCH/C3_IN_BETWEEN_GATE_NOTE.md
LOGIC_CHANGED: YES
LOCKED_CONSTANTS_DIFF: empty
HANDOFF_UPDATED: YES
NEXT_READY: C2b color-free Demand/Supply | Architect pick
```
