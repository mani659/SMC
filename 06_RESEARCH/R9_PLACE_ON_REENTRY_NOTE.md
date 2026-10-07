# R9 — PLACE-ON-REENTRY INTENT (implementation + smoke, 2026-09-22)

**Status:** implemented per Lead Architect ruling; design locked BEFORE code (`00_LOCKED/R9_PLACE_ON_REENTRY_DESIGN.md`).
**Extends:** R7 (place guard) + R8 (HTF resting) — both remain; R9 replaces the R7 silent drop with a deferred placement. `GATE_WIDENED = NO`; `ZONE_REFINEMENT_ATR` unchanged (test-asserted).

---

## 1. Rule (as ruled, with the four design-locked semantics)

A risk-accepted candidate that fails R7's band check arms a **PlaceIntent** — the FULL accepted placement frozen at signal time (FR-3.1 zone-anchored limit, FR-2 SL/TP, policy lots). Each later bar: if the market re-enters the zone band (existing R7 geometry on the bar close) **or** touches the limit (locked fill-model touch rule), the pending order places with the **remaining** R8 bars. Clock ends → `intent_expired_no_reentry`, no order.

Design-locked derivations (all from frozen conventions, none tuned):

1. **Clock convention (§23 parity):** armed on bar N, alive while `age = bar − N < rest_bars`; dead from `N + rest_bars`. The arming bar never places (its close failed the band check by construction).
2. **DOA boundary (the "minimum 1 bar" clause):** an order placed with `remaining` bars has exactly `remaining − 2` fill-eligible bars under the book's frozen `bars_open` convention (expiry cancels pre-fill on `N + rest − 1`). So `remaining ≥ 3` places; `remaining < 3` never fabricates a born-expired order — the intent runs to natural expiry.
3. **Dedupe:** one intent per route identity per run (`route_id`, fallback `poi_id|trigger`); first intent wins, clock NEVER refreshed; terminal status blocks re-arming.
4. **Bar order (no double-order, no lookahead):** Friday-EOD/news drops → pendings §23/§24 expiry → **intent expiry** → position exits → fills → **candidate entries** (immediate place supersedes → `REPLACED`) → **intent re-entry placements** last. Candidates before intents is load-bearing: a same-bar in-band re-proposal must place ONE order, not two (my first wiring ordered intents first and my own test caught the double order — fixed before any run). A bar-B placement cannot fill on B (fills already ran).

One-shot: arm consumes nothing; place consumes (a real accepted placement — both engines call `on_candidate_accepted` exactly once at intent placement). Dead thesis (`cancel_pending_for_poi`) and portfolio events drop alive intents. Paper mirrors everything, including dry-run (record, never send, intent stays armed).

## 2. Modules

- `smc/backtest/intents.py` — `PlaceIntent` + `IntentBook` (insertion-ordered, deterministic; lifecycle ARMED→PLACED|EXPIRED|REPLACED|DROPPED_POI|DROPPED_PORTFOLIO; machine-readable event log + counters).
- `smc/risk/fill_regime_policy.py` — `market_reentered_zone` (band via existing `zone_place_allowed`; touch mirrors `fill_model.limit_filled`, cross-checked by test so the two never drift); `INTENT_EXPIRED_NO_REENTRY` constant.
- `smc/backtest/runner.py` — arm-on-skip in `_process_entries`; shared single placement path `_place_accepted` (immediate + intent placements byte-identical); `_place_due_intents` step; drops wired to Friday/news/POI-violation.
- `smc/paper/runner.py` — same IntentBook; `_expire_intents` (KPI records) + `_place_due_intents` (broker path; dry-run honest); same drops.
- Tests: `04_SRC/tests/test_r9_place_on_reentry.py` — 23 tests (immediate place / arm-not-place / band re-entry with inherited life / touch-only re-entry / natural expiry / DOA boundary / dedupe + clock immutability / REPLACED + one-shot burn exactly once / R8 table + `ZONE_REFINEMENT_ATR` unchanged / fill-model cross-check / paper mirrors incl. dry-run + expiry-before-reentry same-bar).

## 3. Smoke — frozen FR-4b window (isolated out-root, pair untouched)

Window `2025-09-01 → 2025-11-30` (1-month warm-up), stack = FR-3.1 + R7 + R8 + R9, script `06_RESEARCH/scripts/r9_place_on_reentry_smoke.py` (logging-only capturing runner, restored in `finally`).

```text
funnel:    identical to FR-4b (27,266 detected → 709 passed → 21 armed/15 M8 → 6 routes)
intents:   armed 5  placed 1  expired_no_reentry 4  replaced 0  dropped 0
places:    1 (intent re-entry)      fills: 1      trades: 1 (M8)
```

Per-intent ledger (all M8-tagged candidates carry R8=48; H1 = 36):

| intent | POI | tf | signal bar | rest | expire | outcome |
|---|---|---|---|---|---|---|
| 1 | poi-000067 (M8) | H1 | 38 | 48 | 86 | expired (no re-entry) |
| 2 | poi-000069 | H1 | 38 | 36 | 74 | expired |
| 3 | poi-000671 | H4 | 441 | 48 | 489 | expired |
| 4 | poi-011779 (M8) | H4 | 7765 | 48 | 7813 | expired |
| 5 | **poi-014750 (M8)** | H4 | 9657 | 48 | 9705 | **PLACED bar 9694 → filled → closed** |

**The completed chain (first under frozen rules):** intent 5 armed when F completed with the market 14.65 units beyond the zone (the R7-skip class); the market re-entered band/touch at bar 9694 (37 bars into the 48-bar clock) → order placed with inherited rest_bars 11 → **filled at the on-zone limit 4247.355** (bar 9699) → PureRunner BE moved the stop → closed by stop at **+0.07** (positive BE scratch) after 52 bars. Exit kind `stop_loss` (BE-modified). TP was on the order (FR-2 structural).

The 4 expiries are the September trend-runaway class (market never returned within the R8 clock) — recorded, not tuned.

## 4. Residual / next

- The chain arm→reentry→fill→manage→close now exists on frozen rules; n=1 — measurement windows may grow it, but per standing bans: no parameter search, no F-timing labels, no gate widening.
- The 4 September expiries restate the forensic finding: trend-runaway POIs never re-enter; R9 converts those silent skips into visible, counted waits.
- F-survivor research: a non-empty filled sample of 1 exists (M8, BE-scratch) — still below any meaningful analysis bar; stays PAUSED per R6 unless the Architect rules otherwise.

## 5. Artifacts

- Design lock: `00_LOCKED/R9_PLACE_ON_REENTRY_DESIGN.md`
- Smoke: `results/r9_smoke/run1/` (`r9_smoke_summary.json` incl. per-intent rows, `trades.csv`, `report.json`)
- Suite: **681 passed** (658 + 23)
