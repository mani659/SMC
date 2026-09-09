# CHANGELOG

**Last Updated:** 2026-09-09
**Rules:** Every change to the project is recorded here. Format: date, session title, what was added/changed/fixed.

---

## [Unreleased]

_No pending changes._

---

## [2026-09-09] — Phase 7 Complete: Live Readiness + MQL5 Safety Watchdog (V1)

### Added
- **`smc/live/` — Python live package (Option A: Python owns the brain):**
  - `config.py` — `LiveConfig` (symbol/timeframe/magic, demo-first flags, risk inputs on the single §28.7 sizing path, heartbeat/watchdog timing, detection window) + `live_config_from_dict` (timeframe coercion).
  - `heartbeat.py` — plain-text heartbeat file (`<unix_secs> <sequence>` + `state=`), atomic temp+rename writes, `HeartbeatPublisher` (interval-bounded, injected clock), `read_heartbeat`/`is_stale` (fail-closed: missing/garbage == stale), and `evaluate_watchdog` — the pure-Python decision the EA mirrors (healthy → no action; stale/unreadable → emergency). Defaults: 1 s interval, 5 s stale timeout (documented UNFROZEN operational timing, not trading thresholds).
  - `loop.py` — `LiveLoop`: connect (refuse on failure) → poll new closed bars → rolling 200-bar window → `DetectionDriver.validate_window` → arm ONLY newly-passed POIs (never re-arm; §24 anchor + §11 one-shot preserved) → `PaperRunner.run_one_cycle` over the REAL adapter/engine/risk stack → interval-bounded heartbeat. Cold start anchors history without replay; `run_once()` is the deterministic test seam; `stop()` writes a `shutdown` heartbeat (watchdog treats it like death — fail-closed).
- **`05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` — MQL5 Safety Watchdog EA only.**
  - MAY: monitor heartbeat (1 s timer, 5 s timeout vs `TimeGMT()`), emergency close ALL scoped positions + delete ALL scoped pendings on stale/unreadable heartbeat, log/alert.
  - MUST NOT: any strategy logic — no POI detection, validation, entries, PureRunner/FVG management, session/news/risk policy, sizing. Healthy heartbeat → no trading actions.
- **`smc/orchestration/detection_driver.py`** — `validate_window` extracted (Stage 0/1 → detect → merge → validate WITHOUT arming); `run` delegates and arms.
- **Tests** — `tests/test_live_phase7.py` (9): heartbeat roundtrip/freshness, fail-closed garbage/missing, sequence + clean-shutdown marker, publisher interval, watchdog decision (healthy/stale/missing), live loop over a fake connector (history anchor → new-bar cycle → heartbeat fresh → shutdown marker), start refusal, no re-arming of existing POIs, config coercion.
- Design note: `01_ARCHITECTURE/SMC_PHASE_7_DESIGN_NOTE.md` (transport + timeouts + loop structure + exact EA responsibilities + clean shutdown + manual EA validation checklist + residual risks).
- Suite: **510 → 519 passed**.

### Fixed / integrated
- The pre-Phase-7 coherence patch (CR1 detection driver, I1 single §5 state machine, I2 running equity, CR2 paper close guards, I4 retention — 510 passed) is folded into this freeze; see `SMC_PHASE_7_PREP_COHERENCE_PATCH.md`.

---

## [2026-09-09] — Phase 6 Audit Fixes (independent audit accepted)

### Fixed
- **C1 — §23/§24 unfilled-order expiry wired into the integrated loop.**
  `BacktestRunner` runs an expiry step (3c, before fills) calling
  `expired_by_section23(timeframe)` + `expired_by_give_up`; affected
  POIs are driven TESTED through the state machine via
  `PipelineAdapter.notify_order_expired`; paper cancels GTC pendings by
  age (M5 12 / M1 30 bars, §24 backstop). Resting limits can no longer
  fill past their frozen window.
- **C2 — paper fill matching by order identity linkage, not ticket
  equality.** `PositionSnapshot` now surfaces `magic`/`comment`;
  `PaperRunner._observe_fills` matches a fill to a pending on
  (symbol, magic, comment) — the fields real MT5 carries from the order
  to the position record (`POSITION_MAGIC`/`POSITION_COMMENT`); the
  position ticket is keyed separately. The false "position id equals
  order ticket" claim is retracted in the M6 note + SESSION_HANDOFF.
- **I1 — ATR/spread fed per bar in the integrated backtest path**
  (`PipelineAdapter.current_atr` on the honest prefix; spread from
  `RunnerConfig.spread_price`) so BE/spread/same-level gates are not
  silently disabled; parity with the paper runner.
- **I2 — the real `PipelineAdapter` is auto-attached by `PaperRunner`**
  (`init`), with a real-adapter composition test; POI provisioning for
  demo use documented in the M6 note.
- **I3/I5 rulings recorded** in the M4/M6 design notes (hard-cancel
  workflow survival + re-placement bounds; fill-before-entry is the V1
  rule).
- Suite: **496 → 501 passed** (2 backtest expiry tests + 3 paper tests:
  linkage fill, age expiry, real-adapter composition).

---

## [2026-09-09] — Phase 6 Complete: Backtesting & Paper Trading (V1)

### Added
- **`smc/backtest/`** — deterministic, MT5-free backtest stack (M1–M5):
  - `data_feed.py` — `CandleSeries` (single- and multi-TF feed shape,
    exact-timestamp indexing contract).
  - `clock.py` — `BarClock`: the injected `now` (strictly advancing;
    reading before the first bar raises; zero wall-clock reads).
  - `bar_loop.py` — `BarLoop` + `BarHandler` seam: ONE loop, two
    backends (backtest + later live), deterministic bar order and
    `LoopStats`.
  - `orders.py` — `PendingOrderBook`: insertion-ordered pending LIMIT
    book, deterministic tickets, §23/§24 unfilled-order expiry.
  - `fill_model.py` — limit fills AT THE LIMIT PRICE; physical SL/TP
    with the same-bar SL-FIRST rule; `CloseKind` taxonomy.
  - `positions.py` — `PositionStore`: open/close/modify with POI/trigger
    identity on every position; `ClosedPosition` trade-log records.
  - `runner.py` — `BacktestRunner`: the LOCKED per-bar order —
    `reset_day` on UTC date change → `evaluate_friday_close` once →
    `hard_cancel_pending` (§11) → per-position risk exits (FVG
    invalidation + PureRunner BE; `on_be_applied` only after a
    successful modify) → pending-limit fills + physical SL/TP → new
    entries LAST. Blocked risk verdicts place nothing. `submit_entry`
    seam (M3) + `set_pipeline_adapter` (M4) + `result()` snapshot (M5).
  - `pipeline_bridge.py` — `TriggerRoute` → `CandidateEntry` pure
    mapping: direction / limit entry / SL, §15 confluence score,
    `poi_id` + `trigger` + `route_id` ("{poi}:{trigger}@{bar}" §11
    event identity), and the bound FVG provider (Trigger F's signal FVG
    only — geometry never invented).
  - `pipeline_adapter.py` — per-bar engine drive: scan-before-feed (§5
    first-touch OK window covers the touch bar + one bar so an in-zone
    Trigger D pattern stays routable), §11 one-shot workflows (BLOCKED
    verdicts re-submit the SAME candidate without consuming; §24 expiry
    or POI VIOLATED retires the workflow and cancels the resting limit),
    no-lookahead prefix scans.
  - `reports.py` / `export.py` — `build_report(RunnerResult)`: trade
    list, win rate, gross/net P/L, profit factor (zero-loss case →
    explicit `None`, never inf), max drawdown on the closed-trade equity
    curve, per-trigger + per-POI breakdowns (`unattributed` when
    identity is absent), blocked-entry counts by reason, empty-run
    defined zeros; deterministic CSV + JSON export (`sort_keys`).
- **`smc/paper/`** — paper trading over the live execution layer (M6):
  - `runner.py` — `PaperRunner`: the same locked bar order applied
    bar-close driven; implements the M4 adapter seam directly
    (`submit_entry` / `on_candidate_accepted` /
    `cancel_pending_for_poi`) so the identical `PipelineAdapter` drives
    backtest AND paper; broker-truth observation (fill = pending ticket
    appears as a position; close = tracked position disappears);
    `on_trade_opened` on fill; `on_be_applied` ONLY on a confirmed
    modify; dry-run flag; refuses to start when
    `connector.initialize()` fails.
  - `broker_adapter.py` — thin `OrderManager`/`PositionManager`
    boundary: place-limit (§10 limits only), close (opposite DEAL),
    cancel; SL modify re-sends the untouched TP (post-audit rule at the
    execution layer); raises nothing — returns success/latency outcomes
    measured with the injected `perf` source.
  - `kpi_logger.py` — append-only structured KPI records (decision,
    order_ack, management, fill, trade_closed, missed_bar, hard_cancel,
    friday_close) with INJECTED timestamps only; derived `counters()`;
    deterministic JSON/JSONL/CSV exports. NO pass/fail threshold engine
    (Future Flexibility Clause thresholds are not frozen — metrics
    logged only).
- **Design notes** — `01_ARCHITECTURE/SMC_PHASE_6_M4_DESIGN_NOTE.md`,
  `SMC_PHASE_6_M5_DESIGN_NOTE.md`, `SMC_PHASE_6_M6_DESIGN_NOTE.md`
  (alongside the phase-level `SMC_PHASE_6_DESIGN.md`).
- **Tests** — M1–M6 suites including pipeline-integration (9), reports
  (14) and paper (15) files — **496 tests total passing**
  (`python -m pytest tests` from `04_SRC/`); suite progression 458 (M3
  accepted) → 467 (M4) → 481 (M5) → **496 (M6)**.

### Binding decisions honored (Phase 6 constraints)
- Fill AT THE LIMIT PRICE; same-bar SL-first on physical closes.
- Injected `now` only — bar clock in backtest, bar timestamps + injected
  `perf` monotonic source in paper; no wall-clock reads.
- Pure `RiskEngine` (decisions only); `PipelineEngine` finds/validates/
  routes; runners/stores apply.
- A blocked risk verdict places nothing and consumes nothing — the POI
  one-shot survives (I2 parity across engine, adapter and paper runner).
- Single sizing path (§28.7 policy band + `LOT_MAX_SAFETY` cap) in both
  runners; no second sizing implementation.
- FVG context attached at trade open ONLY when the signal can supply a
  real one (Trigger F); otherwise absent and invalidation skipped —
  geometry never fabricated.

### Changed
- `smc/orchestration/engine.py` — `scan_route(..., to_bar=)` no-lookahead
  cap + `tracked_pois()` arm-order registry (M4 integration seams; no
  trading-logic change).
- `README.md` — Phase 6 milestones + test counts updated to 496.

### Deferred to V1.1 (recorded, not built)
- Walk-forward analysis; Monte Carlo; Future Flexibility KPI pass/fail
  thresholds; slippage simulator; Redis/event-bus abstraction (V1
  in-memory stores documented as the seam).

---

## [2026-09-08] — Phase 0–5 Audit Fixes (Lead Architect approved)

### Fixed
- **PositionManager SL/TP clobber (C1)** — `modify_sl` / `modify_tp` no
  longer send `0.0` for the untouched protective field. Both fetch the
  current position snapshot and RE-SEND the current opposite price (the
  cab_watcher `_modify_sl` pattern); an unknown ticket raises instead of
  sending a clobbering request. Regression tests: modifying SL preserves
  TP and vice versa; unknown ticket sends nothing.
- **Single sizing policy path (C2)** — `PipelineEngine.compute_risk_lots`
  now routes through the Phase 5 policy layer
  (`smc.risk.lot_sizing.sized_lots`: RISK_PCT band clamp + `LOT_MAX_SAFETY`
  cap) instead of the raw `risk_lots` formula. No public helper sizes
  outside `RISK_PCT_MIN`/`RISK_PCT_MAX` or above `LOT_MAX_SAFETY`.
- **Blocked routes no longer burn the POI one-shot (I2)** —
  `PipelineEngine.execute_route` marks the POI fired ONLY on an accepted
  execution attempt; news/session blocks return `blocked` outcomes without
  consuming the §11 event identity, so the route can be re-attempted once
  the gate clears.
- **Same-bar tie-break pinned A-first (I3)** — on equal bar + equal §15
  grade the EARLIER trigger letter wins (A before F).
  `TriggerRouter.evaluate_at` (negated-grade ascending key) and
  `CompatibilityMatrix.eligible_triggers` (letter-ascending within grade)
  are aligned; regression test drives F before A in the trigger list and
  asserts A wins.
- **§7 inducement literals (I4)** — `pillar_5_inducement.py` and
  `validation_pipeline.py` import and use `INDUCEMENT_WITH_SCORE` /
  `INDUCEMENT_WITHOUT_SCORE` from `locked_constants`; no bare 1.0/0.7 or
  `!= 1.0` comparisons remain.
- **Injected clock (I5)** — `PipelineEngine.execute_route(..., now=...)`
  requires the caller to inject `now` (required keyword; no
  `datetime.now()` default) for backtest determinism; omitting it fails
  loudly with `TypeError`.

### Changed
- Governance docs (SESSION_HANDOFF / CHANGELOG / TODO) now describe the
  post-audit RiskEngine API: portfolio-level `evaluate_friday_close`,
  `on_trade_opened` / `on_be_applied` lifecycle hooks,
  `hard_cancel_pending`, `EntryRequest.current_spread_price` (price units,
  not MT5 points) and the closed-bar FVG contract
  (`PositionState.closed_close` only). The old "Friday inside
  `evaluate_exit`" description is removed — Friday EOD is evaluated ONCE
  per bar BEFORE per-position exits.
- Tests: C1/C2/I2/I3 regression tests added; engine tests inject `now`;
  inducement tests assert against the frozen constants. **Suite 353 → 363
  passing** (`python -m pytest tests` from `04_SRC/`).

### Notes / design decisions
- `modify_sl`/`modify_tp` fail fast (`ValueError`) when the ticket is not
  open — never send a protective-field-clobbering request blindly.
- The §28.7 clamp direction is confirmed: sub-band risk fractions are
  clamped UP to `RISK_PCT_MIN` (the caller chooses within the band; the
  policy guarantees the band). LOT_MAX_SAFETY caps the final size.

---

## [2026-09-07] — Phase 5 Complete: Risk Layer (v25_DIAG Port)

### Added
- **§28 Risk constants lock (2026-09-07, Lead Architect approval)** — 17 risk thresholds formally frozen in `locked_constants.py` (new §28 group) and mirrored in `LOCKED_DECISIONS.md` §28.1–28.9: `PURE_RUNNER_BE_ATR` 1.0, `PURE_RUNNER_BE_BUFFER_ATR` 0.10, `CIRCUIT_BREAKER_LOSS_COUNT` 3, `CIRCUIT_BREAKER_PAUSE_HOURS` 4, `SAME_LEVEL_GUARD_ATR` **0.15** (running v25 default; supersedes the outdated 0.1 header comment), `SAME_LEVEL_GUARD_COOLDOWN_BARS` 4, `FRIDAY_EOD_CLOSE_HOUR_UTC` 20, `SPREAD_MAX_ATR` 0.15, `SPREAD_GRADE_MULTIPLIERS` (A+ 1.5 / A 1.0 / B 0.7 / C 0.5), `SPREAD_GRADE_SCORE_THRESHOLDS` (A+ ≥8 / A ≥5 / B ≥3 / C <3), `SWEEP_GUARD_ZONE_ATR` 0.5, `SWEEP_GUARD_COOLDOWN_BARS` 4, `RISK_PCT_MIN` 0.5 / `RISK_PCT_MAX` 1.0 (band kept; caller chooses within), `LOT_MAX_SAFETY` 0.10, plus optional gates `ADX_MIN_ENTRY` 25.0 and `ATR_FLOOR_MIN_SL` 1.0. Explicitly deferred: Immediate Trail, fixed-dollar risk mode, fixed-lot fallback, dynamic SL buffers, PureRunner TP RR. **Primary exit model: PureRunner (BE at 1.0× ATR + buffer) + FVG Invalidation.**
- **`smc/risk/`** — Stage 5 ported from v25_DIAG, all thresholds imported from §28 (zero hardcoding), no MT5 calls (pure decisions + injectable state):
  - `lot_sizing.py` — re-exports the Phase 4 `risk_lots` pure formula (single sizing path, no parallel implementation) + policy layer: `clamp_risk_fraction` enforces the frozen RISK_PCT band, `sized_lots` applies the `LOT_MAX_SAFETY` cap.
  - `circuit_breaker.py` — `CircuitBreaker` + injectable `CircuitBreakerState`: pause after `CIRCUIT_BREAKER_LOSS_COUNT` consecutive losses for `CIRCUIT_BREAKER_PAUSE_HOURS`; resets on WIN or new day (v25 `TradeAllowed` semantics).
  - `same_level_guard.py` — blocks re-entry while the new SL sits within `SAME_LEVEL_GUARD_ATR` × ATR of the last closed SL and fewer than `SAME_LEVEL_GUARD_COOLDOWN_BARS` bars have elapsed (v25 `g_lastSLLevel` block semantics).
  - `friday_eod.py` — once-per-Friday force-close decision at `FRIDAY_EOD_CLOSE_HOUR_UTC` with latch + reset (v25 `g_fridayClosed`); pure decision — the caller performs closes/cancels.
  - `sweep_guard.py` — per-direction failed-sweep re-entry block (`SWEEP_GUARD_ZONE_ATR` zone, `SWEEP_GUARD_COOLDOWN_BARS`; v25 `IsFailedSweepBlocked` semantics, daily reset).
  - `spread_grading.py` — score-tier grading (`grade_for_score` over `SPREAD_GRADE_SCORE_THRESHOLDS`) + `effective_max_spread` = multiplier × `SPREAD_MAX_ATR` × ATR.
  - `pure_runner.py` — one-shot BE: fires at `PURE_RUNNER_BE_ATR` × ATR profit from entry, new SL = entry + dir × `PURE_RUNNER_BE_BUFFER_ATR` × ATR, only when it improves the current SL; no partials in V1.
  - `fvg_invalidation.py` — `FvgContext` frozen dataclass (valid/low/high/direction) + `is_invalidated` closed-candle structural-failure check with machine-readable exit reasons.
  - `risk_engine.py` — the orchestrator: `RiskEngine` composes all components (dependency-injected, §28 defaults). `evaluate_entry(EntryRequest) -> EntryDecision` gates in v25 pipeline order (news → session → circuit breaker → same-level → sweep → spread → risk-band clamp + sizing; first block wins, machine-readable `blocked_by`). Per-position `evaluate_exit(PositionState, *, now, fvg_context) -> ExitDecision`: FVG invalidation → PureRunner BE (`MOVE_SL` carries `new_sl`); Friday EOD is portfolio-level via `evaluate_friday_close(now)` called once per bar BEFORE per-position exits. Lifecycle hooks `on_trade_opened()` (re-arm BE latch) / `on_be_applied()` (set latch only after broker acceptance); §11 `hard_cancel_pending(now, news_events)`; `EntryRequest.current_spread_price` in PRICE units; FVG invalidation consumes only the closed-bar `PositionState.closed_close`. State pass-throughs: `record_result`, `record_sl_close`, `record_failed_sweep`, `reset_day`. Typed contracts: `RiskAction` (HOLD/ENTER/MOVE_SL/EXIT), `EntryRequest`/`EntryDecision`, `PositionState`/`ExitDecision`.
  - `__init__.py` — public re-exports of all risk components + decision types.
- **Tests** — 10 Phase 5 test files (90 tests: `test_locked_constants` §28 assertions + `test_risk_lot_sizing`, `test_circuit_breaker`, `test_same_level_guard`, `test_friday_eod`, `test_sweep_guard`, `test_spread_grading`, `test_pure_runner`, `test_fvg_invalidation`, `test_risk_engine`) — **340 total passing** (36 Phase 0 + 56 Phase 1 + 42 Phase 2 + 40 Phase 3 + 76 Phase 4 + 90 Phase 5).

### Changed
- `locked_constants.py` — old "v25_DIAG risk thresholds deliberately excluded" notice replaced by the §28 lock notice (only the deferred set remains excluded); `__all__` extended with the 17 §28 names.
- `00_LOCKED/TODO.md` — Phase 5 fully checked off; phase table row 5 → ✅ COMPLETE; current phase → 6 (Backtesting & Paper Trading); Kalman/ADX-gate/ATR-floor marked NOT ported (constants locked as conditional gates only).
- `SESSION_HANDOFF.md` — Phase 5 marked ✅ BUILT; current/next phase → Phase 6; Phase 5 implementation notes (RiskEngine API + Phase 6 open questions) added.
- `smc/execution/lot_sizing.py` — unchanged; now re-exported (not duplicated) by `smc/risk/lot_sizing.py`.

### Notes / design decisions
- **No parallel sizing path** — `PipelineEngine.compute_risk_lots` still consumes `smc.execution.lot_sizing.risk_lots`; the risk layer adds policy (band clamp + cap) on top of the same formula.
- **Pure decisions, no broker calls** — every risk component and the engine return typed decisions; Phase 6/7 runners apply them.
- **Gate order mirrors v25's entry pipeline** (environment → breaker → re-entry guards → spread quality → size); exit priority mirrors v25 on-tick management (Friday close outranks per-position exits).
- **Open questions for Phase 6:** FVG context capture at trade open (trigger layer doesn't persist FVG boundaries yet), exit evaluation cadence (closed bars vs ticks), daily `reset_day()` clock edge ownership, whether ADX/ATR-floor gates get ported, slippage policy (v25 `InpSlippage` deferred).

---

## [2026-09-07] — Phase 4 Complete: LTF Triggers (A–F) + Python Execution

### Added
- **`smc/triggers/`** — Stage 3 per LOCKED_DECISIONS §10/§12/§15/§22–§24 and R1 §7/§11:
  - `base_trigger.py` — `Trigger` ABC + `TriggerContext`/`TriggerSignal` (entry limit + stop reference, `completion_index`, `expiry_bars`, `detail`, and `data: dict = field(default_factory=dict)` — never None).
  - `trigger_a_choch.py` … `trigger_f_bos_ob.py` — the six triggers: A CHOCH Reversal, B Leading Diagonal (5-wave initiation), C Ending Diagonal (throw-under reclaim), D Two-Bar Reversal (frozen 50% engulfing-body limit, §10), E RSI Divergence, F BOS + OB continuation. Every trigger is a LIMIT entry — none emits a market order.
  - `wave_structure.py` — deterministic V1 5-wave impulse extraction (`find_impulse`) feeding Triggers B/C.
  - `trigger_router.py` — chronological first-valid routing (§12) within the §24 give-up window; same-bar tie-break by §15 compatibility grade (PREFERRED > STRUCTURAL > UNCOMMON) then trigger letter.
  - `trigger_expiry.py` — §24 per-trigger validity windows (`window_bars_for`) + §23 unfilled-order expiry anchors + POI-wide give-up window (Trigger A's 20 M5 bars, V1).
  - `compatibility_matrix.py` — §15 per-model grades (`DEFAULT_MATRIX`); routing tie-break only, no frozen cell is forbidden.
- **`smc/execution/`** — Stage 4:
  - `order_manager.py` — `OrderManager` limit/market placement, cancel, modify via a connector; `OrderRequest`/`OrderResult` contracts.
  - `position_manager.py` — position monitoring + SL/TP adjustment.
  - `news_guard.py` — §11 `should_block_entry` (CPI/NFP/FOMC blackout).
  - `session_filter.py` — §2 `is_allowed_session` gate.
  - `lot_sizing.py` — `risk_lots` sizing helper (Phase 5 risk engine consumer).
- **`smc/orchestration/engine.py`** — `PipelineEngine` (Stage 2→3→4 seam): merge-before-validate, displacement injection, arm-bar bookkeeping, per-bar §5 state feed (`feed_bar`), give-up-bounded `scan_route`, and `execute_route` (news + session gates → LIMIT order → `ExecutionOutcome` with `order_result`).
- **Tests** — 16 Phase 4 files (`test_trigger_{a..f}_*.py`, `test_trigger_router.py`, `test_trigger_expiry.py`, `test_compatibility_matrix.py`, `test_order_manager.py`, `test_position_manager.py`, `test_news_guard.py`, `test_session_filter.py`, `test_lot_sizing.py`, `test_rsi.py`, `test_pipeline_engine.py`) — **76 Phase 4 tests, 250 total passing** (36 Phase 0 + 56 Phase 1 + 42 Phase 2 + 40 Phase 3 + 76 Phase 4).

### Changed
- `00_LOCKED/TODO.md` — Phase 4 fully checked off; phase table row 4 → ✅ COMPLETE; current phase → 5 (Risk Layer — Port v25_DIAG to Python); wave-counting blocked item resolved (deterministic V1 `wave_structure.py`).
- `SESSION_HANDOFF.md` — Phase 4 marked ✅ BUILT; current/next phase → Phase 5; Phase 4 implementation notes + Phase 5 integration seams added.

### Fixed
- **`ExecutionOutcome.order_result` typed field** — was an unannotated attribute that `@dataclass(slots=True)` silently dropped from `__init__` (plain class attribute, not a field), so `engine.execute_route()` raised `TypeError: unexpected keyword argument 'order_result'`. Now `order_result: Optional[OrderResult] = None` with `OrderResult` imported — the execution outcome carries the placed order.
- **Trigger B `TriggerSignal.data` dict contract** — guaranteed every returned signal carries a real dict (never None) so `signal.data["wave5_index"]` is always safe; the Trigger B test fixture no longer crashed before the data assertion. These two fixes took the suite from 245 → **250/250 green** (`python -m pytest tests` from `04_SRC/`).

### Notes / design decisions
- All six triggers are LIMIT entries (Trigger D frozen at 50% of the engulfing body, §10) — no trigger emits a market order.
- Routing is chronological first-valid (§12); the §15 compatibility matrix influences routing only as a same-bar tie-break.
- §7 inducement literals (`score_modifier=1.0/0.7`) from the Phase 3 audit remain value-identical to frozen constants; a constant import refactor is still a candidate at Phase 5 kickoff (no numeric discrepancy).
- v25_DIAG risk thresholds (Phase 5 port scope) remain deliberately outside `locked_constants.py` until formally locked in `LOCKED_DECISIONS.md`.

---

## [2026-09-07] — Phase 3 Independent Audit (docs-only follow-up, no logic change)

### Added
- Independent audit of every file in `04_SRC/smc/validation/` and the 7 Phase 3 test files against the 11 audit criteria (directory/modules, locked-constants-only, Pillar 1 ±0.5×ATR refinement, Pillar 2 displacement reuse, Pillar 3 sole reject ownership, Pillar 4 1-touch freshness, Pillar 5 soft inducement, pipeline order/short-circuit/arming+scoring, state-machine atomicity/terminals/expiry, unit tests, governance docs). Result: **11/11 PASS (2 Notes)** — full audit table reported to the Lead Architect; suite re-run **174/174 green** (36 Phase 0 + 56 Phase 1 + 42 Phase 2 + 40 Phase 3).
- `SESSION_HANDOFF.md` — added a consolidated **"Integration seams Phase 4 must respect"** list to the Phase 3 Implementation Notes (displacement injection contract, merge-before-validate, score-assignment timing/ownership, M8 not-assumed-fresh, state-based Pillar 4 + creation-bar gap, §7 literal-modifier note, `atr_period=14` indicator default). The three audit confirmations (Pillar 3 sole owner of the §6 reject, Pillar 2 caller-injected `DisplacementResult`, UNAVAILABLE on pillars 1–4 ⇒ reject) were already verbatim in the notes — no edit required.

### Changed
- No validation logic or numeric values changed (comments/documentation only, per audit instructions).
- `00_LOCKED/TODO.md` — Completed-log row added for the Phase 3 audit.

### Notes / audit findings (no code fix applied)
- **§7 inducement modifiers used as literals:** `pillar_5_inducement.py` returns `score_modifier=1.0 / 0.7` and `validation_pipeline.py` defaults/comparisons use `1.0` — values exactly match the frozen `INDUCEMENT_WITH_SCORE` (1.0) / `INDUCEMENT_WITHOUT_SCORE` (0.7) in `locked_constants.py` and the docstrings name those constants, but the code does not import them (codebase convention is to import frozen values). No numeric discrepancy; a value-identical constant refactor is recommended before/at Phase 4 kickoff. Remaining literal `atr_period=14` (context/pipeline) is an indicator parameter inherited from `smc.utils.atr`, not a frozen decision value.

---

## [2026-09-07] — Phase 3: 5-Pillar Validation Pipeline (Stage 2)

### Added
- **`smc/validation/`** — Stage 2 per LOCKED_DECISIONS §3/§5/§6/§7/§13 and R1 §6 (pillars 1–5 run in order; 1–4 are hard gates, 5 is soft):
  - `pillar.py` — `Pillar` ABC (number/name/`run(context)`) + `PillarStatus` (PASS/FAIL/UNAVAILABLE), `PillarResult` (detail + score_modifier + data), and the `ValidationContext` every pillar consumes (POI, candles, swings, liquidity levels, pre-computed dealing range / displacement).
  - `pillar_1_zone_refinement.py` — §13: unmitigated FVG or OB (candle before the first FVG candle, R1 §3.1) must overlap the POI level band (zone midpoint ± `ZONE_REFINEMENT_ATR` × ATR); a candidate is mitigated once price closes through its opposite extreme after formation; naked level = FAIL, insufficient data = UNAVAILABLE.
  - `pillar_2_displacement.py` — §3 gate that CONSUMES the Phase 1 `check_displacement` result (BOS + FVG + ≥1× ATR; hard fail < 0.5× ATR). No blind recompute — missing result = UNAVAILABLE (documented reuse decision).
  - `pillar_3_premium_discount.py` — §6 gate and SOLE owner of the 45%/55% hard reject: LONG must classify DISCOUNT, SHORT must classify PREMIUM, 45–55% EQUILIBRIUM = REJECT; `compute_dealing_range() == None` → UNAVAILABLE (never a silent pass).
  - `pillar_4_freshness.py` — §5 strict 1-touch gate: CREATED/FRESH pass; TESTED/VIOLATED reject (state-based; per-bar transitions owned by the state machine).
  - `pillar_5_inducement.py` — §7 SOFT pillar: SSL pools (equal lows / unconfirmed minor swing lows) between the zone approach boundary and last close = 100% (modifier 1.0); none = 70% (modifier 0.7), never a rejection. Trendline inducement not machine-testable in V1 (documented).
  - `validation_pipeline.py` — `ValidationPipeline` runs pillars 1→5 and short-circuits on the first hard (1–4) non-pass; on success arms the POI (CREATED→FRESH) and assigns the §1 confluence `score_poi` when unset; returns a `ValidationResult` (decision PASS/REJECTED, per-pillar results, quality score, inducement modifier, first failure). Dealing range auto-computed from swings via Phase 2 `compute_dealing_range` when not injected.
  - `state_machine.py` — `POIStateMachine` with atomic §5 transitions (CREATED→FRESH→TESTED/VIOLATED, terminals immutable; illegal moves raise `IllegalTransitionError`), `can_trade` (FRESH only — first-touch-OK / no second touches), `touches_zone` helper, and §23 unfilled-order expiry (`expire_unfilled`; frozen M5 = 12 / M1 = 30 bars; H1+ have no frozen rule). V1 in-memory store documented as the seam for a later Redis CAS.
  - `__init__.py` — public re-exports (pillars, pipeline, machine, context/result types).
- **Tests** — 7 new files in `04_SRC/tests/` (`test_pillar_{1..5}_*.py`, `test_validation_pipeline.py`, `test_state_machine.py`) with synthetic OHLCV + reused Phase 1 `check_displacement` fixtures. Each pillar pass/fail (soft path for P5), pipeline short-circuit on first hard fail, full success path (score assignment + arming), dealing-range-None → Pillar 3 UNAVAILABLE/reject, freshness terminal states + first/second-touch semantics, expiry M5/M1. **174 tests total passing** (36 Phase 0 + 56 Phase 1 + 42 Phase 2 + 40 Phase 3).

### Changed
- `00_LOCKED/TODO.md` — Phase 3 fully checked off; phase table row 3 → ✅ COMPLETE; current phase → 4 (LTF Triggers).
- `SESSION_HANDOFF.md` — current phase/next task refreshed to Phase 3 → Phase 4 (still pending in this pass), Phase 3 marked ✅ BUILT in the plan list, Phase 3 implementation notes added below.

### Notes / design decisions (no frozen numbers invented)
- **UNAVAILABLE on pillars 1–4 rejects.** R1 defines PASS/FAIL/UNAVAILABLE; the pipeline treats anything that is not PASS on a hard pillar as a rejection (fail-fast, no silent accept). Distinct from FAIL in the log via `PillarStatus`.
- **Pillar 3 ownership:** the §6 hard reject lives ONLY here; `deal_range.py` classifies the region and nothing more (per the Phase 2 audit note).
- **Pillar 2 input contract:** the caller must inject the Phase 1 `DisplacementResult` for the POI's own sweep → BOS. Phase 2 detectors do not store the sweep/BOS indices yet, so deriving one inside the pillar would be model-specific guesswork; this stays UNAVAILABLE until the detector→pipeline glue supplies it.
- **Pillar 4 is state-based at validation time** (a POI just created has no touches *since creation*); historical per-bar touches/expiry are owned by `POIStateMachine`. A POI creation bar index is not stored on `POI` (Phase 2); revisit if a pre-creation zone-touch scan is wanted.
- **Pillar 5 inducement interval:** structure must lie strictly between the zone's approach boundary and the last close (zone TOP for buys, zone BOTTOM for sells); structures inside the zone body are the POI itself, not inducement.

---

## [2026-09-07] — Phase 2 Independent Audit (docs-only follow-up, no logic change)

### Added
- Independent audit of every file in `04_SRC/smc/poi/` (incl. `models/`) and the Phase 2 tests against the 11 audit criteria (directory/modules, equal-tag architecture, locked-constants-only, CHOCH Rules 1/2/3, M5 vs M7, Model 8, QML full-wick anchor, confluence tiers, deal-range bands, unit tests, governance docs). Result: **11/11 PASS** — full audit table reported to the Lead Architect; suite re-run **134/134 green**.
- `SESSION_HANDOFF.md` — added the audit-required ownership note (**Pillar 3 is the SOLE owner of the §6 45%/55% hard reject; `deal_range.py` only classifies regions for Pillar 3 to consume**) and a consolidated "V1 simplifications / edge cases Phase 3 must be aware of" list (M4 consecutive-swings-only, M8 most-recent-only per kind + forward D&S scan, single-pass `merge_overlapping`, CHOCH Rule 3 last-swing-or-intermediate wick reference, M5 co-tagging M7-style fixtures, M3 shared single tag). Phase 0–2 marked ✅ BUILT in the "Must Be Built" plan list.

### Changed
- No detection or model logic changed (comments/documentation only, per audit instructions).
- `00_LOCKED/TODO.md` — no edit required; already reflects Phase 2 completion (42 Phase 2 tests / 134 total).

---

## [2026-09-07] — Phase 2 Completion Audit + SESSION_HANDOFF Refresh (no logic change)

### Added
- Full audit of the Phase 2 deliverables against the Phase 2 coding prompt and `LOCKED_DECISIONS.md` §1/§6/§8/§9/§14/§17/§20–§22/§26, `CHOCH_TYPES_AND_SWING_VALIDITY.md`, `MODEL_8_HTF_DEMAND_SUPPLY.md`, and R1 §5. Result: PASS — all 14 modules present, no priority hierarchy (equal tags), all numeric thresholds sourced from `locked_constants.py`, Phase 0/1 types + detectors reused.
- **Test hardening (Phase 2 count 41 → 42):** `tests/test_poi_models.py` M8 acceptance now asserts the supply zone equals the FULL high-low range of the single last bullish candle (§22), and a new test asserts M8 ignores non-D1/H4 series (§21 detection-TF rule). **134 tests total passing** (`python -m pytest tests` from `04_SRC/`).
- `SESSION_HANDOFF.md` — refreshed to point at Phase 3 (was stale: still listed Phase 1 as current and Phase 2 as next) + added a Phase 2 Implementation Notes section.

### Changed
- `00_LOCKED/TODO.md` — Phase 2 test counts updated (41 → 42 tests; 133 → 134 total); Phase 2 remains ✅ COMPLETE; phase table unchanged.
- No trading logic changed in `04_SRC/smc/` during this session.

### Notes / audit findings (no code fix applied)
- `confluence_scorer.merge_overlapping` performs a single-pass merge against the first POI of each group; chain-overlapping zones (A∩B and B∩C but not A∩C) can still leave B-adjacent POIs overlapping in the output. Behaviour is documented in the docstring and acceptable V1; revisit if zone-union semantics need a fixed-point merge.
- The §6 dealing-range PASS/FAIL buy/sell gate is intentionally deferred to Phase 3 Pillar 3 (Pillar 3 = Premium/Discount); `deal_range.py` exposes the frozen region classification (`classify_region`) used by that pillar.

---

## [2026-09-06] — Phase 2: POI Classification (M1–M8 modular tags + confluence + CHOCH)

### Added
- **`smc/poi/`** — Stage 1/1b per LOCKED_DECISIONS §1/§4/§8/§9/§17/§20-§22/§26 and R1 §5 geometry:
  - `base_model.py` — `POIModel` abstract contract (`detect(candles, swings, liquidity_levels) -> list[POI]`) + shared pure geometry helpers (`zone_for_swing/zone_for_level/zone_for_candle`, `first_close_beyond`, `atr_up_to`, `has_directional_fvg_after`, `most_recent_swing`). Window slicing is the caller's responsibility (documented V1).
  - `model_registry.py` — `ModelRegistry` (one instance per `ModelType`, idempotent per tag, duplicate registration raises) + `build_registry(timeframe, htf_candles=None)` registering all 8 models.
  - `confluence_scorer.py` — §1 equal-tag scoring: independent tag count, quality tiers (1 base / 2 elevated / 3+ institutional from locked constants), M8 `+0.10` HTF-overlap bonus (§21/§26, quality-score only), and `merge_overlapping` (same-direction zone unions: widest zone, union tags, earliest id, OR overlap flag).
  - `choch_classifier.py` — CHOCH Rule 1 (standard body close beyond last structural swing), Rule 2 (inside body on an intermediate level, last swing intact), Rule 3 (inside wick, kept) per §17/§20; sweep of the final extreme is a pre-condition; bullish is classified via price inversion so one geometric path serves both sides.
  - `deal_range.py` — §6/R1 §3.4 dealing range (recent §19-valid high/low with window-extreme fallback) + premium/discount/equilibrium classification on the frozen 0.45/0.55 thresholds. The actual §6 PASS/FAIL gate is intentionally deferred to Phase 3 Pillar 3.
  - `models/m1_origin_base.py` … `models/m8_htf_demand_supply.py` — the 8 equal-tag model detectors: M1 origin base (BOS + directional FVG + ≥1× ATR from a §19-valid swing), M2 RBS/SBR flip, M3 CHOCH retest (3 sub-variants share one tag), M4 Quasimodo (head beyond shoulder + neckline close), M5 proactive equal-high/low cluster break (EQH/EQL tolerance), M6 double top/bottom neckline retest, M7 reactive bounce-shelf after expansion, M8 HTF D1/H4 zones (OB = pre-FVG candle, FVG zones, §22 last-opposing-candle zones) with the §21/§26 D1+H4 `htf_overlap` flag. M8 implements zone identification only (Step 1) — no M5-approach / M1-trigger logic yet.
  - `smc/poi/__init__.py` — public re-exports.
- **Tests** — 5 new files in `04_SRC/tests/` (`test_model_registry.py`, `test_choch_classifier.py`, `test_deal_range.py`, `test_confluence_scorer.py`, `test_poi_models.py`); `conftest.py` gained a shared `swing_factory` fixture. Per-model acceptance fixtures reproduce the canonical R1 §5 geometry with synthetic OHLCV plus a decoy (same geometry minus the decisive element). **133 tests total passing** (36 Phase 0 + 56 Phase 1 + 41 Phase 2).

### Changed
- `00_LOCKED/TODO.md` — Phase 2 fully checked off (registry path corrected to `smc/poi/model_registry.py` per the coding prompt); phase table row 2 → ✅ COMPLETE; current phase → 3.
- No triggers (A–F), 5-pillar validation, execution, or risk implemented.

### Notes / design decisions (no frozen numbers invented)
- **UNFROZEN V1 geometry choices** (documented at each site, not added to `locked_constants.py`): bare-level zone half-width reuses the frozen §13 0.5× ATR multiplier (`level_band_half_width`); M5 cluster zone = full-wick union of the two member candles. List these before live use.
- M3's Rule 1/2/3 variants all emit a single `ModelType.M3` tag (§1 equal-tags; the specific rule is exposed via `ChochBreak.rule` for research logging).
- CHOCH Rule 1 breaks require the break to happen AT the anchored bar (an earlier close below the level disqualifies the bar — the break candle is the classification bar).
- M8 accepts `htf_candles` at construction; zones are scanned per D1/H4 and `htf_overlap` is set only for same-direction D1/H4 price overlap (the +0.10 score bonus is applied by `score_poi`, never to position size).
- Overlapping same-direction POIs from different models are merged by `merge_overlapping`; the confluence/validation layers consume `list[POI]` so co-labeled levels stay intact.

---

## [2026-09-06] — Phase 2 Coding Prompt (planning artifact)

### Added
- `01_ARCHITECTURE/SMC_PHASE_2_CODING_PROMPT.md` — Lead Architect instruction prompt for Phase 2 (POI Classification), mirroring the Phase 0/1 prompt format: exact module list for `smc/poi/` (`base_model`, `model_registry`, `confluence_scorer`, `choch_classifier`, `deal_range`, `models/m1–m8`), strict rules (locked constants only, R1 §5 geometry, §1 equal-tags superseding R1 priority text), CHOCH/deal-range/confluence/M8 requirements, per-model acceptance-fixture test requirements, and the required ambiguities report. No code changed; TODO Phase 2 remains Pending until the prompt is executed.

---

## [2026-09-06] — Phase 1: Core Detection (Stage 0A/0b/0c)

### Added
- **`smc/detection/`** — 10 modules implementing Stages 0A/0b/0c per LOCKED_DECISIONS §2/§3/§18/§19/§27:
  - `liquidity_scanner.py` — orchestrator returning `List[LiquidityLevel]` (session, periodic PDH/PDL+PWH/PWL, EQH/EQL, structural-swing families; family filter). POI-level / D&S / OB-boundary types deferred until POI zones exist (Phase 2+).
  - `session_levels.py` — Asia/London/NY session H/L from the frozen §2 UTC windows.
  - `periodic_levels.py` — PDH/PDL + PWH/PWL over the most recent COMPLETED trading day/week (weekend-aware: skips days with no candles).
  - `eqh_eql_detector.py` — clusters swing highs/lows within `EQH_EQL_TOLERANCE` (4.5 pips); BSL level = extreme high, SSL level = extreme low; anchor-bound clustering (no pairwise chaining).
  - `structural_swing_detector.py` — N-bar fractal swings (§27 N=5 HTF / N=3 LTF via `Timeframe.n_bar_confirmation`), plateau-safe, Base-Candle anchored, §19-validated.
  - `base_candle.py` — §18 identification incl. the bearish special wick rule (previous bearish candle stays the Base Candle when the next candle's wick makes the lower low and closes back).
  - `swing_validator.py` — §19 decision gate: valid only on body CLOSE beyond the base candle's opposite extreme; wick-only / two-bar reversal = invalid.
  - `sweep_detector.py` — wick-pierce + body-close-back confirmation for BSL/SSL levels (never self-sweeps the forming candle).
  - `fvg_detector.py` — 3-candle imbalance gaps → `Zone` (bullish/bearish).
  - `displacement_checker.py` — §3 check: BOS close + directional FVG + magnitude ≥ 1× ATR (pre-move Wilder ATR); hard fail < 0.5× ATR; preferred > 1.5× ATR.
- **Tests** — 10 new test files (`04_SRC/tests/test_{base_candle,swing_validator,structural_swing_detector,eqh_eql_detector,session_levels,periodic_levels,sweep_detector,fvg_detector,displacement_checker,liquidity_scanner}.py`) with synthetic OHLCV; shared `candle_factory` fixture in `tests/conftest.py`. **92 tests total passing** (36 Phase 0 + 56 Phase 1).

### Changed
- `00_LOCKED/TODO.md` — Phase 1 fully checked off; phase row 1 → ✅ COMPLETE; current phase → 2.
- No trading logic beyond detection implemented (no POI models, triggers, execution, or risk).

### Notes / design decisions (no frozen numbers invented)
- Swings are only *structural* once §19-validated over available history; candidates are returned with `is_valid=False` until then. Scanner emits only valid swings as `STRUCTURAL_SWING` levels.
- EQH/EQL is detected on swing candidates regardless of §19 validity (an equal-level pool exists at formation, before any later break).
- PDH/PDL semantics: most recent completed *trading* day (calendar days without data are skipped).
- Sweep/structural/EQH families may co-label the same price region; confluence/POI phases dedupe (per §1 modular-tag design).
- Displacement magnitude measured from the sweep candle's extreme to the BOS candle's close; FVG must be directional and start within the move.

---

## [2026-09-06] — Phase 0 Audit & Comment Clarifications (no logic change)

### Added
- Full audit of Phase 0 deliverables performed (code inspection + LOCKED_DECISIONS.md cross-check).
  - Result: PASS. Tree matches claim; all 36 constants exported and frozen-value tests green; 36/36 unit tests pass.
- **Comment clarification A** (`smc/utils/pips.py`): explicit comment block that the `XAUUSD_PIP_SIZE = 0.1` (1 pip = 0.10) assumption is NOT frozen, is broker-dependent, and MUST be verified against the live broker's `digits`/`point` before Phase 4 (execution) and Phase 7 (live).
- **Comment clarification B** (`smc/config/locked_constants.py`): comment block at the top of the file stating that the v25_DIAG risk thresholds (BE 1×ATR, circuit breaker 3 losses → 4h, same-level guard 0.1×ATR, Friday EOD 20:00 UTC, risk 0.5–1.0%, spread grades, 4-bar sweep cooldown, ADX ≥ 25, 1.0×ATR floor) are PROVEN but not yet formally frozen in LOCKED_DECISIONS.md and are therefore deliberately excluded; they will be added before Phase 5.

### Changed
- No logic or values changed — comments only (per Lead Architect instruction).
- `00_LOCKED/TODO.md` — Phase 0 remains ✅ COMPLETE (verified, no edit required).

### Notes
- Audit finding (no fix applied, comments-only scope): LOCKED_DECISIONS.md §10 "Limit order at 50% of the engulfing body" is the only frozen numeric rule not yet in `locked_constants.py`; it belongs with Trigger D and should be added as a named constant when Phase 4 begins.

---

## [2026-09-06] — Phase 0: Foundations — SMC Python Package

### Added
- **04_SRC/smc/** — Complete Phase 0 Python package (Python 3.10+, type hints, dataclasses)
  - `smc/config/locked_constants.py` — All frozen thresholds from `LOCKED_DECISIONS.md` (EQH/EQL 4.5 pips, displacement 1.0/1.5/0.5× ATR, zone refinement 0.5× ATR, P/D 0.55/0.45, expiry M5=12/M1=30 bars, N-bar HTF=5/LTF=3, trigger A–F expiries, sessions, news protocol, Model 8 RR/bonus). Risk-layer numbers (v25_DIAG port scope) deliberately excluded until formally locked.
  - `smc/config/timeframe.py` — `Timeframe` IntEnum (MT5-compatible values) + §27 HTF/LTF N-bar helpers
  - `smc/config/model_type.py` — `ModelType` M1–M8 equal tags (§1)
  - `smc/core/` — `Candle`, `Swing`, `Zone`, `LiquidityLevel`, `POI`, `Event` dataclasses + `enums.py` (`TriggerType` A–F, `LiquidityType` 8 types, `POIState`, `Direction`, `PoolType`)
  - `smc/data/mt5_connector.py` — Thin lazy-import wrapper over the MetaTrader5 API (copy_rates, order_send, order_check, account_info, positions_get, connect/login/shutdown); reusable patterns extracted from `cab_watcher_v16_3-1.py` documented in docstring. No connection at import.
  - `smc/data/csv_loader.py` — stdlib OHLCV CSV → `list[Candle]`
  - `smc/utils/atr.py` — Wilder ATR (matches MT5 `iATR`)
  - `smc/utils/timestamps.py` — UTC normalization + Asia/London/NY session detection (§2 hours, sourced from locked constants)
  - `smc/utils/pips.py` — XAUUSD pip helpers (1 pip = 0.1 price units; 4.5-pip EQH tolerance default)
  - Placeholder packages `smc/detection|poi|validation|triggers|execution|risk|logging|backtest|paper|live/` (importable, no logic)
- **04_SRC/tests/** — 5 Phase 0 unit-test files (dataclasses, enums, locked constants, mocked MT5 connector, ATR) — **36 tests passing** (`python -m pytest tests` from `04_SRC/`)

### Changed
- `00_LOCKED/TODO.md` — Phase 0 checked off; phase table row 0 → COMPLETE; current phase → 1
- No trading logic implemented — structure, types, constants, and thin wrappers only (per Phase 0 scope)

### Notes
- `redis_store.py` left unimplemented (explicitly OPTIONAL for V1; in-memory state acceptable) — decision still open in TODO "Blocked/Waiting"
- v25_DIAG risk thresholds (Phase 5) intentionally NOT added to `locked_constants.py` — not yet frozen in `LOCKED_DECISIONS.md`; see module note

---

## [2026-09-06] — Project Restructuring & Architecture Lock

### Added
- **00_LOCKED/** — Source of truth directory
  - `LOCKED_DECISIONS.md` — Frozen Rev 5 (2026-09-01)
  - `DEVELOPMENT_PLAN.md` — Option A Locked (Python-First + MQL5 Safety Watchdog)
  - `CHOCH_TYPES_AND_SWING_VALIDITY.md`
  - `MODEL_8_HTF_DEMAND_SUPPLY.md`
  - `SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md`
  - `TODO.md` — Phase-by-phase task board
  - `CHANGELOG.md` — This file
  - `SESSION_HANDOFF.md` — Full context for future agents
- **01_ARCHITECTURE/** — Current design docs
  - `SMC_R1_MODULE_ARCHITECTURE.md`, `SMC_WORKFLOW_ORCHESTRATION.md`, `SMC_R1_POI_TRIGGER_COMPATIBILITY.csv`
  - `SMC_SESSION_HANDOFF.md`, `SMC_STATE.json`
  - `N8N_WORKFLOW_GUIDE.md`, `N8N_WORKFLOW_PROMPT.md`, `SMC_Zero_Lag_Pipeline_n8n_workflow.json`
  - `Flowcharts/` — Only v5 diagrams (7 files)
- **02_KNOWLEDGE_BASE/** — 57 PNG visual references
- **03_REFERENCE_CODE/** — Active code for study
  - `GOLD_SMC_v25_DIAG.mq5` — Reference implementation
  - `CAB_Unified_v16.4.mq5`, `cab_watcher_v16_3-1.py`, `start_bot_cab.bat` — CAB bridge pattern (temporary)
- **04_SRC/** — Empty, ready for new Python codebase
- **05_MQL5_SAFETY/** — Empty, ready for Safety Watchdog EA
- **06_RESEARCH/** — Active research scripts and experiments
- **ARCHIVE/** — All historical files organized by era

### Changed
- **Architecture decision locked:** Python-First + MQL5 Safety Watchdog (Option A)
  - Python owns ALL trading logic (Stages 0A–5)
  - MQL5 reduced to Safety Watchdog only (heartbeat + emergency close)
  - Future Flexibility Clause: selectively port back to MQL5 only after measured evidence
- **Project root cleaned:** 14 old directories replaced with 8 numbered folders + ARCHIVE

### Architecture Decisions
- Option A Locked: Python owns ALL trading logic
- MQL5 role: Safety Watchdog only (heartbeat monitoring + emergency position close)
- No HTTP bridge needed — Python connects directly to MT5 via MetaTrader5 API
- v25_DIAG is a reference implementation for porting, not a runtime component

### Notes
- 49 old MQL5 files archived to `ARCHIVE/MQL5_History/`
- 34+ TradingView scripts archived to `ARCHIVE/TradingView_Era/`
- 19 research ledger files archived to `ARCHIVE/Research_Archive/`
- Old flowcharts (v1–v4) archived to `ARCHIVE/Old_Flowcharts/`
- Old reports/logs archived to `ARCHIVE/Old_Reports_Logs/`
- Superseded docs archived to `ARCHIVE/Superseded_Docs/`
