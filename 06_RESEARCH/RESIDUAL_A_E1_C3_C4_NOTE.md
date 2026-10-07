# Residual Track A — E1 entry_anchor export, C3 structural TP, C4 silent policies

Track A residual engineering after Choice-1 completion (as-coded Part 2 gaps C1–C4; C1 closed by the
product-runtime unification). This note is the design record required BEFORE any C3 code.
Suite baseline at start: **726 passed**. Date: 2026-09-24.

---

## §E1 — entry_anchor end-to-end export (DONE)

### Gap (Phase 3/4 sample audit)
Phase 3/4 sample audit showed `entry_anchor = n/a:not_exported`: Trigger F (FR-3.1
`zone_anchored_entry`) sets `signal.data["entry_anchor"]` (`"zone_edge_reanchor"` / `"ob_proximal"`),
but it only survived as a JSON-string fragment inside `signal_data_json` — no first-class field on
the trade record, and the Phase 4 audit script treated it as not-exported.

### Path surveyed (as-coded)
`trigger_f_bos_ob.py` (sets `signal.data["entry_anchor"]`)
→ `pipeline_bridge.candidate_from_route` (whole `signal.data` → `signal_data_json`)
→ `CandidateEntry` → `PendingOrder.place` → `BacktestPosition.open` →
`PositionStore.modify_sl` (rebuild) → `TradeRecord.from_closed` → `export.to_csv` / `to_json`.
Paper side: `PaperRunner` `_TrackedPending` → `_TrackedPosition` mirrors the same chain.

### Implemented (logging/audit only — zero decision change)
* `CandidateEntry.entry_anchor: str | None` — extracted in `candidate_from_route` from
  `signal.data["entry_anchor"]` ONLY when it is a non-empty string (never coerced, never invented).
  The anchor also remains inside `signal_data_json` (inspector ease — both surfaces).
* `PendingOrder.entry_anchor`, `BacktestPosition.entry_anchor` — carried verbatim;
  `PositionStore.modify_sl` copies it unchanged while moving `sl` (same placement-geometry
  invariant as `original_sl`; enforced by test).
* `TradeRecord.entry_anchor` + `from_closed` mapping.
* `export.to_csv` appends an `entry_anchor` column AFTER the existing columns (backward
  compatible: old column order untouched; `None` → empty cell). `to_json` adds the
  `entry_anchor` key per trade. Paper `_TrackedPending`/`_TrackedPosition` carry it pending → position.
* `smc/paper/runner.py`, `smc/backtest/{runner,orders,positions,reports,pipeline_bridge,export}.py`
  touched — identity/export plumbing only. `locked_constants.py` untouched.

### Tests (11 new, `04_SRC/tests/test_residual_a_e1_entry_anchor.py`)
Bridge extraction (first-class + inside signal_data_json; absent → None; non-string → None;
decision-identity invariance), order → position flow, `modify_sl` preservation (vs `original_sl`
pattern), `from_closed` carry, CSV appended column, JSON key. Two assertions in
`test_identity_patch.py` updated for the appended CSV column (append-only contract, not a regression).

**E1 verdict: DONE** — suite 726 → 737, all green.

---

## §C3 — structural TP: DESIGNED / UNFED (write-before-code record)

### FR-2 as-coded today
`pipeline_bridge.resolve_take_profit(entry_price, direction, atr, structural_target=None)`:
a caller-supplied structural target wins when it is finite and strictly favorable
(LONG above entry / SHORT below); anything else falls back to entry ± 4×ATR
(`FR2_TP_ATR_MULTIPLE = 4.0`, frozen). Missing/non-positive ATR → `None` (never an invented level).
The structural branch is fully wired and unit-tested — it is just never fed a real value,
because no trigger emits a structural target.

### Survey: does a real structural source exist on the route?
* `TriggerSignal.data` (as-coded, all triggers): `fvg`, `bos_index`, `ob_index`,
  `entry_anchor`, `wave5_index` (B/C), `rsi_*` (E) — **no target price field anywhere**.
* `TriggerRoute` = POI + signal + bar; the POI carries zone bounds + model tags — no target.
* Liquidity levels / sweeps exist upstream in the detection run but are NOT attached to the
  route; the engine's `scan_route` never passes them to the trigger layer.
* `candidate_from_route(structural_target=...)` accepts a caller-supplied target, but the only
  callers (adapter, research scripts) pass nothing — inventing a selector there (e.g. "nearest
  opposing liquidity", "next H1 swing") would be NEW target-selection logic, not a feed.

### V1 design ruling (locked answers)
1. **What counts as a valid structural TP in V1** — a price value that satisfies ALL of:
   (a) emitted by a trigger in `signal.data` under an explicit, frozen key (a trigger-level
   definition, not a bridge-side selector); (b) finite and strictly favorable
   (LONG: > entry; SHORT: < entry); (c) derivable from objects the route already carries —
   the trigger's own pattern geometry (e.g. Trigger A's swept-liquidity extreme, a diagonal's
   origin) — never from a cross-object search over levels/swings the route does not hold.
2. **If none available on route → 4×ATR only** (unchanged policy; FR-2 R4 stands).
3. **No new constants.** If a buffer/selector were ever required it would be UNFROZEN and is
   NOT invented here — the implementation stays on the frozen FR-2 multiple already in code.

### Verdict
**C3_STRUCTURAL_TP: UNFED_DESIGN_ONLY.** No trigger emits a structural target today; feeding one
would require inventing target-selection logic (banned: fixed-R search, Phase-C book tuning,
Fib engines). The `resolve_take_profit` structural branch stays as-is (wired, tested, dormant).
Phase A PASS does not depend on C3 being fed — it requires the honest disposition, recorded here
and mirrored in the product contract's C4/silent table as "structural TP: designed, unfed (V1)".

---

## §C4 — news / spread / sweep-guard: formal dispositions

| Gate | Disposition | Evidence (as-coded) |
|------|-------------|---------------------|
| News §11 | **DEFERRED** | EntryRequest carries `news_block`; product configs ship `news_events=[]` and there is NO news-calendar ingestion in `04_SRC` (no synthetic calendar per hard ban). Needs an external, operator-supplied calendar feed before the gate can be proven live. |
| Spread §28.5 | **WIRED (operator config input)** | `spread_price` is a real, threaded input: `LiveConfig`/`RunnerConfig.spread_price` → `EntryRequest.current_spread_price` → `effective_max_spread(score, atr)` ATR-relative grading in `risk_engine` — plus the R7-style operator whitelist (`operator_config.py`). It is wired end-to-end; only the VALUE is operator-supplied (0.0 = gate off in shipped research configs). |
| Sweep guard | **DEFERRED** | Guard + plumbing fully implemented (`sweep_guard.is_blocked`, `note_sweep`, runner/paper `sweep_level` threading) but NO trigger emits a sweep level today — the plumbing is dormant by design. Threading it would require a trigger emitting a real sweep level; inventing sweep attribution is banned. |

### Required statement
Shipped research configs run with `news_events=[]` and `spread_price=0.0` — these remain
**diagnostic**, not "gates proven live". The spread gate's WIRING is proven (tests, §28.5
grading path); its LIVE protection depends on the operator supplying a real spread series.
News and sweep-guard remain formally SILENT in V1 product runs until real feeds exist.

---

## Governance
* Suite: 726 → **737 passed** (`cd 04_SRC && python -m pytest tests -q`).
* `04_SRC/smc/config/locked_constants.py` diff: empty (verify at close).
* Handoff / ACTIVE_TODO / CHANGELOG updated for Track A; contract gets the silent/deferred table.
