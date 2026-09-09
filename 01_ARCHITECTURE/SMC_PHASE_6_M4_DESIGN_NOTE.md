# Phase 6 — Milestone 4 Design Note: Full PipelineEngine Integration

Status: COMPLETE — full suite **467 passed** (458 pre-existing + 9 new M4 integration tests), deterministic on repeated runs, MT5-free.

Scope: real detection → validation → trigger routing → risk-gated pending limits inside the M3 backtest runner. Reporting (M5) and paper trading (M6) remain out of scope.

---

## 1. New / modified files

| File | Change |
| --- | --- |
| `04_SRC/smc/backtest/pipeline_bridge.py` | NEW — pure mapping: `TriggerRoute` → `CandidateEntry` (identity + prices + §15 score + `route_id`), and `fvg_context_for_route` (honest FVG derivation) |
| `04_SRC/smc/backtest/pipeline_adapter.py` | NEW — `PipelineAdapter`: drives the engine per bar inside the runner's entry step; owns the §11 one-shot workflow lifecycle |
| `04_SRC/smc/backtest/runner.py` | MODIFIED — `CandidateEntry.fvg_provider` + `fvg_context()` (frozen-safe), `cancel_pending_for_poi()`, sweep-level plumbing through `_sweep_by_order` → `_sweep_level_by_ticket` → `record_failed_sweep`, FVG context plumbing through `_fvg_by_order` → `_fvg_by_ticket`, adapter hook in the entry step |
| `04_SRC/smc/orchestration/engine.py` | MODIFIED — `scan_route(..., to_bar=)` no-lookahead cap, `tracked_pois()` arm-order registry, `arm_at`/`episode` bookkeeping (`_PoiEpisode.arm_bar`) |
| `04_SRC/tests/test_backtest_pipeline_integration.py` | NEW — 9 integration tests (bridge, adapter, runner path, blocked retry, FVG, determinism) |

---

## 2. How PipelineEngine is invoked in the bar loop

The locked M3 per-bar order is unchanged and still authoritative:

1. `reset_day` on UTC date change
2. `evaluate_friday_close` (portfolio-level, once)
3. `hard_cancel_pending`
4. risk exits (FVG invalidation + PureRunner BE)
5. M2 fills: pending limits, then physical SL/TP (same-bar SL first)
6. **entries last** — and inside the entry step: `adapter.generate_candidates(bar, bar_index, now)` runs BEFORE `_process_entries`, which risk-gates whatever the adapter queued

## 1a. Audit fixes (post-freeze, Phase 6 audit accepted)

* **C1 — §23/§24 unfilled-order expiry is now wired into the bar loop.**
  `BacktestRunner.on_bar` runs a dedicated expiry step (3c, before fills):
  `PendingOrderBook.expired_by_section23(timeframe)` (M5 = 12 / M1 = 30
  bars) then `expired_by_give_up` (the 20-bar §24 backstop for timeframes
  without a §23 rule). Cancelled orders' per-order context maps are
  cleaned, and each affected POI is driven to TESTED through the engine's
  state machine via `PipelineAdapter.notify_order_expired` (the frozen
  `expire_unfilled` path when a §23 rule exists, else a FRESH → TESTED
  transition). An order reaching expiry on a bar is cancelled BEFORE that
  bar's fills are evaluated, so it can never fill after its window.
* **I1 — ATR and spread are fed per bar.** The adapter exposes
  `current_atr(bar_index)` — `latest_atr` over the honest candle prefix
  `[: bar_index + 1]` (no lookahead, same contract as the trigger scan);
  the runner feeds it to `set_atr` each bar before exit management. The
  spread input comes from `RunnerConfig.spread_price` (PRICE units; a
  caller enabling the §28.5 spread gate must configure it — no longer a
  silent default). The paper runner computes the same ATR from its own
  growing series, so backtest and paper gate on the same inputs.
* **I5 (ruling) — fill-before-entry is the V1 rule.** The runner evaluates
  fills (step 5) BEFORE the entry step (step 6): a limit placed on bar N
  can only fill from bar N+1 — a just-placed limit never fills on its own
  bar's range, even if that bar traded through the price.
* **I3 (ruling) — hard-cancel does not consume the workflow.** After a §11
  hard-cancel the adapter's workflow survives; a new limit may be placed
  only after the blackout clears, and only while the workflow is still
  alive (§24 `signal_expired` drops it, a POI VIOLATION drops it and
  cancels resting limits). The §5 machine is never re-armed — a TESTED /
  VIOLATED POI never routes again.

---

Per bar, per tracked POI (arm order — deterministic), the adapter runs:

1. **Trigger scan** — `PipelineEngine.scan_route(poi, prefix, detect_swings(prefix, tf), to_bar=bar_index)`. The scan universe is the candle prefix `[: bar_index + 1]` (never a future bar — no lookahead). §19 swings are recomputed on the same prefix rather than trusting caller-supplied full-history swing lists (V1 honesty note: those lists are not assumed prefix-safe; recomputing keeps the backtest strictly causal). The scan is bounded by the §24 give-up window anchored at the POI's arm bar (engine bookkeeping).
2. **Workflow drive** — the first winning route creates the POI's one-shot workflow whose candidate is submitted for this bar's risk verdict; the workflow is re-submitted each bar until consumed/expired (see §3).
3. **§5 freshness feed** — `PipelineEngine.feed_bar(poi, bar)` LAST: the engine stays the sole §5 authority. VIOLATED → the workflow is dropped and the POI's resting limit cancelled (`runner.cancel_pending_for_poi`). TESTED → recorded; the in-flight workflow lives on.

### Why scan-before-feed (the §5 "first touch OK" subtlety)

Trigger D's engulfing bar overlaps the POI zone by definition (`_overlaps_zone` is a frozen trigger condition), and §5's touch is wick-enters-zone: the SAME bar is simultaneously the pattern's second leg and the POI's first touch. Feeding first would flip the POI to TESTED before the scan on that bar, making every in-zone trigger unreachable forever. The adapter therefore scans before feeding and bounds post-touch routing to the touch bar itself plus one bar (`_may_route`: FRESH always; TESTED only while `bar_index <= tested_bar + 1` — exactly Trigger D's entry bar). After that a touched POI is never routed again (1-touch rule). The state machine itself is never bypassed; only the *order of queries* changes.

---

## 3. How routes become pending orders

One-shot semantics (R1 §11: one validated POI + one LTF trigger + one execution), implemented as a per-POI **workflow** in the adapter:

* The FIRST winning route for a POI mints ONE candidate (pure bridge mapping) and records it as that POI's single workflow (`_workflows[poi.id]`). `_routed` guarantees no POI is ever scanned into a second route even after its workflow ends — one §11 event per POI lifetime.
* Every bar, the active workflow's candidate is re-submitted to the runner's risk-gated path (`RiskEngine.evaluate_entry` → on ENTER, a policy-sized pending limit in the M2 `PendingOrderBook`):
  * **ENTER (accepted)** → limit placed; the runner calls `adapter.on_candidate_accepted(candidate)` → the workflow is consumed. This is the ONLY consumption point.
  * **HOLD (blocked: news / session / breaker / same-level / sweep / spread / min-lots)** → nothing placed, **nothing consumed** — the same candidate object is re-submitted on the next bar (mirrors `PipelineEngine.execute_route`'s I2 blocked semantics). The integration test proves via a submit spy that the SAME candidate object is retried.
  * **§24 signal expiry** (`signal_expired(completion_index, expiry_bars, current_bar)`) → the workflow is dropped without an execution.
  * **POI VIOLATED** → workflow dropped AND any resting limit for that POI is cancelled — a violated zone is a dead thesis; no ghost order may fill later.
* Identity preservation on the whole chain: `CandidateEntry` carries `poi_id`, `trigger` (the `TriggerType`), `route_id` (`"{poi.id}:{trigger.value}@{completion_index}"` — same format as the engine's live limit-request comment) and the §15 score. `orders.place(...)` stores `poi_id`/`trigger`/`comment` on the `PendingOrder`; `positions.open(...)` carries `poi_id`/`trigger` onto the open position; `ClosedPosition` inherits them. Per-model / per-trigger reporting (M5) can therefore group by identity without any backfill.
* Sizing stays single-path: the runner passes `risk_fraction` into `evaluate_entry`, which sizes through the §28.7 policy (`sized_lots` — band clamp + `LOT_MAX_SAFETY` cap). No second sizing path exists.

---

## 4. FVG context capture (fill-time mapping)

Frozen-constraint mapping (no geometry is ever invented):

* The bridge binds `fvg_provider` onto the candidate AT CONSTRUCTION (the dataclass is frozen — no post-hoc mutation): `lambda route=route: fvg_context_for_route(route)`.
* `fvg_context_for_route(route)` is honest-or-nothing:
  * Trigger F (`F_BOS_OB`) may emit its displacement-leg FVG in `signal.data["fvg"]` (the v25 `g_activeFVGCtx` snapshot semantics) → mapped to `FvgContext(valid=True, low, high, direction=signal.direction)` after validating `high > low` (degenerate geometry → `None`, never repaired).
  * Every other trigger (and any F signal without a usable FVG) → `None`.
* At placement, the runner calls `candidate.fvg_context()` and stores a non-None context on `_fvg_by_order[order.ticket]`; at fill, `_apply_fills` moves it to `_fvg_by_ticket[position.ticket]`; `evaluate_exit` then runs FVG invalidation with it.
* When the context is ABSENT, `_fvg_by_ticket` simply has no entry → `evaluate_exit` receives `fvg_context=None` → FVG invalidation is skipped for that trade. The test asserts exactly this for a real Trigger D fill.

---

## 5. Sweep-level plumbing (available today)

No trigger in the frozen Phase 4 set exposes a sweep level on its signal (`data` carries pattern references only — checked across `smc/triggers/`). The plumbing is therefore complete but usually dormant:

* `CandidateEntry.sweep_level` → `_sweep_by_order[order.ticket]` at placement → `_sweep_level_by_ticket[position.ticket]` at fill → on a LOSING close, `risk.record_failed_sweep(sweep_level, bar_index, is_long)` feeds the §28.6 sweep guard.
* No level → nothing recorded (never fabricated). The runner's TODO comment documents where a future signal field would plug in.

---

## 6. Live-vs-backtest execution split

* `PipelineEngine.execute_route` (live: builds `OrderRequest`, calls the live `OrderManager`, applies §11/§2 gates, caches the fired outcome) is **deliberately never called** by the adapter — it assumes a live connector. The adapter uses the engine only in its backtest-safe role: `merge / validate / arm_at / feed_bar / scan_route / tracked_pois`.
* Backtest placement goes through the SAME risk-gated path as the M3 seam (`submit_entry` → `evaluate_entry` → `PendingOrderBook.place`). There is no second orchestrator and no parallel order path; the pipeline finds/validates/routes, the RiskEngine gates/sizes/manages, the backtest stores apply fills and closes.
* Consequence: news/session gating in backtest comes from `RunnerConfig.news_events` / `allowed_sessions` via `evaluate_entry` (verified: the blocked test shows `blocked_by == "session"`). The engine's own `execute_route` gates remain the live-path equivalent.
* Multi-TF: `PipelineAdapter` is parameterized by `timeframe` (default M5) and the engine API (`scan_route`, `feed_bar`) is per-POI-timeframe, so HTF/M8 zones arm through the same path (M1 `MultiTimeframeFeed` shape) — the design is not painted into single-TF.

---

## 7. Determinism

Injected bar + clock only; plain dicts/sets keyed by POI id; arm-order iteration; monotone ticket sequence; no wall clock, no randomness, no MT5 imports anywhere in the backtest core (existing guard test still green). The repeated-run test compares orders/positions/closes mechanics (POI UUIDs are per-run values, so identity strings are excluded from the equality comparison) — identical across runs.

---

## 8. Blocking open questions

None blocking M4. Two notes for M5 (reporting):

1. `route_id` embeds the completion bar; pending orders keep it in `comment` — decide whether M5 reports prefer parsing it or a dedicated column.
2. Sweep plumbing is dormant until a trigger exposes `signal.data["sweep_level"]`; if M5 wants failed-sweep stats on Trigger C routes specifically, that signal field is the place to add it (Phase 4 freeze notwithstanding — it is additive).
