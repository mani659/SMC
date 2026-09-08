# PHASE 6 DESIGN — Backtesting & Paper Trading (DESIGN ONLY, NO CODE)

**Status:** Design proposal for Lead Architect review — nothing implemented.
**Date:** 2026-09-08
**Baseline:** Phases 0–5 frozen, audit-clean, 363 tests green.
**Governing constraint:** the SAME Python code runs in backtest and live —
there is no separate `risk_simulator.py` (DEVELOPMENT_PLAN Phase 6, Option A lock).

---

## 0. Current surface report (pre-design inspection)

### 0.1 Orchestration — `smc/orchestration/engine.py` (`PipelineEngine`)

| Method | Role | Phase 6 relevance |
|---|---|---|
| `merge(pois)` | Phase 2 overlap merge (tag union) | Called once per detection batch |
| `validate(pois, candles, swings, liquidity_levels, displacement_map, ...)` | 5-pillar validation + arming + scoring | Per detection batch; needs `displacement_map` injected per POI |
| `arm_at(poi, arm_bar)` | Records the POI's arm bar (anchors §24 give-up window) | Engine-internal bookkeeping; runner must call validate/arm before scanning |
| `feed_bar(poi, candle)` | Per-bar §5 touch/violation feed | **Runner calls once per POI per bar** |
| `scan_route(poi, candles, swings, from_bar)` | Chronological first-valid trigger scan, bounded by `arm_bar + poi_give_up_bars()` (20 M5 bars) | Runner calls per FRESH POI per bar |
| `execute_route(route, *, volume, now, news_events, allowed_sessions)` | News + session gates → LIMIT order | **`now` is a REQUIRED keyword** (post-audit I5 — no `datetime.now()`); blocked outcomes do NOT consume the one-shot (post-audit I2); accepted attempt marks `episode.fired` |
| `compute_risk_lots(route, equity, risk_fraction, pip_value_per_lot, min_lots, lot_step)` | §28.7 policy sizing (clamp + `LOT_MAX_SAFETY`) | Single sizing path — runner uses this (or `RiskEngine.evaluate_entry`) for volume |
| `episode(poi)` | `_PoiEpisode{arm_bar, fired, outcome}` | One-shot identity per POI |

Key post-audit facts to design around:
- `execute_route` requires injected `now`; a news/session block returns
  `ExecutionOutcome(blocked=...)` WITHOUT calling `_mark_fired` — the POI can be
  re-attempted later. Only an accepted attempt consumes the one-shot.
- `ExecutionOutcome` carries `route`, `request`, `order_result`, `blocked`.
- The engine holds `_episodes: dict[poi_id, _PoiEpisode]` — **unbounded growth**
  on long M1 runs (flagged seam, see §8).

### 0.2 Risk — `smc/risk/risk_engine.py` (`RiskEngine`, post-audit API)

| Method | Signature | Owner of side effects |
|---|---|---|
| `evaluate_entry(EntryRequest) -> EntryDecision` | news → session → circuit breaker → same-level → sweep → spread → sizing; first block wins; `blocked_by` machine-readable | **Engine decides, runner acts** (runner places the order on ENTER) |
| `evaluate_exit(PositionState, *, now, fvg_context) -> ExitDecision` | per-position: FVG invalidation → PureRunner BE; `MOVE_SL` carries `new_sl` | Engine decides; **runner applies** SL modify then calls `on_be_applied()` |
| `evaluate_friday_close(now) -> bool` | portfolio-level, **once per bar, BEFORE per-position exits**; True ⇒ close ALL positions + cancel pending | Engine decides; runner closes/cancels |
| `hard_cancel_pending(now, news_events) -> bool` | §11 pre-news blackout; True ⇒ cancel ALL pending limits | Engine decides; runner cancels via `OrderManager` |
| `on_trade_opened()` | re-arms PureRunner BE latch per new trade | **Runner calls** after a fill |
| `on_be_applied()` | sets BE one-shot latch after broker accepted the modify | **Runner calls** after a successful SL modify |
| `record_result(win, at)` | circuit breaker | **Runner calls** on every closed trade |
| `record_sl_close(sl_level, bar_index)` | same-level guard | **Runner calls** on every SL close |
| `record_failed_sweep(sweep_level, bar_index, is_long)` | sweep guard | **Runner calls** on losing closes |
| `reset_day()` | daily rollover (breaker + sweep + same-level) | **Runner calls** on UTC date change |

Runner-vs-engine boundary (already clean): the RiskEngine NEVER calls the
broker — it returns typed decisions; the runner applies them and reports back
through the lifecycle/state hooks. This is the single most important contract
Phase 6 must preserve.

`EntryRequest` carries `current_spread_price` (PRICE units, not MT5 points —
convert at the data boundary) and `now` (injected, no wall clock).

### 0.3 Data / connector surface

| Piece | Facts |
|---|---|
| `smc/data/mt5_connector.py` | Thin lazy facade over `MetaTrader5`. `copy_rates(symbol, tf, start, count)`, `symbol_info`, `symbol_info_tick`, `account_info`, `positions_get`, `order_send`, `order_check`. No connection at import. Used by paper/live; **backtest must NOT touch it** (tests never require the package). |
| `smc/data/csv_loader.py` | `load_ohlcv(path, timeframe, symbol) -> list[Candle]`; ISO-8601 or unix timestamps; **single-timeframe** (one `Timeframe` per file); OHLC sanity-checked; UTC. |
| `smc/core/candle.py` | Frozen `Candle(timestamp, open, high, low, close, volume, timeframe)` with `range`/`body`/wick helpers. |
| `smc/config/timeframe.py` | `Timeframe` IntEnum with MT5-parity values, `minutes`, `is_htf/is_ltf`, `n_bar_confirmation` (§27). |

**Multi-TF gap:** the pipeline consumes M5 (execution) + HTF D1/H4 (M8, §21)
+ detection-timeframe candles. `csv_loader` is single-TF; Phase 6 needs a
multi-TF ingestion layer (three aligned series, or a registry of
`Timeframe -> list[Candle]`). Flagged in §8.

### 0.4 Documented open seams (SESSION_HANDOFF)

1. **FVG context capture** — `evaluate_exit` needs `FvgContext` snapshotted at
   trade open. Verified: `TriggerSignal.data` carries trigger anchors
   (`bos_index`, `ob_index`, `engulfing_index`, `wave5_index`, ...) but **no FVG
   boundaries**. For Trigger A the structural FVG lives in the Phase 1
   `DisplacementResult` injected at validation; for F it is the OB zone. The
   runner needs a trigger-type → FVG-source mapping (decision in §8).
2. **Closed-bar close** — FVG invalidation consumes `PositionState.closed_close`
   (the just-closed bar's close, v25 `iClose(...,1)`); `None` skips the check.
   The runner defines per-bar cadence (decision: skip-and-log vs hard error, §8).
3. **Friday EOD** — `evaluate_friday_close` once per bar, before per-position
   exits; the runner closes the whole book on True.
4. **Injected `now`** — required in `execute_route` and `EntryRequest`; the
   runner owns a single clock (bar timestamp) for determinism.
5. **Unbounded `_episodes` / state-machine stores** — `PipelineEngine._episodes`
   and `POIStateMachine._states` grow for every POI ever seen (long M1 runs).
   Out of audit scope; Phase 6 needs a retention policy (decision, §8).
6. **News hard-cancel** — `hard_cancel_pending` exists; the runner must cancel
   pending limits and decide whether the POI re-arms after the blackout
   (decision, §8 — note the I2 one-shot rule: a cancelled order is not a
   "blocked outcome", so semantics need an explicit ruling).
7. **Single sizing path** — `sized_lots` (band clamp + `LOT_MAX_SAFETY`) is the
   only public sizing path; `evaluate_entry` and `compute_risk_lots` both use it.

### 0.5 Locked constraints that bind the design

- Same code path for backtest and live (no `risk_simulator.py`).
- No HTTP bridge — Python connects directly to MT5 (paper/live).
- Chronological first-valid trigger (§12); same-bar tie-break = grade, then
  earlier letter (post-audit I3).
- Freshness: §5 1-touch machine (FRESH only tradeable; TESTED/VIOLATED
  terminal); §23 unfilled-order expiry (M5=12 / M1=30, H1+ none); §24 trigger
  windows + POI give-up (20 M5 bars).
- §11 news protocol (hard-cancel −15 min, re-evaluate +30 min).
- All §28 risk thresholds (band 0.5–1.0%, LOT_MAX_SAFETY 0.10, breaker 3/4h,
  same-level 0.15×ATR/4 bars, Friday 20:00 UTC, sweep 0.5×ATR/4 bars, BE
  1.0×ATR + 0.10 buffer, spread 0.15×ATR tiered).
- Every trigger is a LIMIT entry (Trigger D at 50% engulfing body, §10).

---

## 1. Recommended package layout

```
smc/backtest/
├── __init__.py
├── backtest_engine.py         # Bar-driven main loop; owns the clock + orchestration order
├── fill_model.py              # PURE fill rules (limit/SL/TP touch, price, same-bar ordering)
├── event_bus.py               # InProcessEventBus (publish/subscribe); interface shared with live
├── state_store.py             # InMemoryStateStore (dict); interface shared with live
├── performance_analyzer.py    # PF, win rate, max DD, exposure, per-model/per-trigger, MFE/MAE
├── walk_forward.py            # V1.1 — IS/OOS windowed validation
├── monte_carlo.py             # V1.1 — resampled trade sequences
└── report_generator.py        # CSV/HTML report output

smc/paper/
├── __init__.py
├── paper_trading_runner.py    # Same loop as backtest_engine, MT5Connector + live fills
├── slippage_simulator.py      # Variable spread + latency model (paper only)
└── kpi_logger.py              # Operational KPIs for the Future Flexibility Clause
```

Notes:
- `fill_model.py` is PURE and shared: the backtest engine evaluates fills
  against bar ranges; the paper runner evaluates the same rules against ticks
  (or bar-close snapshots) — one fill contract, two data feeds.
- `backtest_engine.py` and `paper_trading_runner.py` share the SAME loop
  skeleton (a `PipelineLoop`-style orchestration); the only differences are
  the data feed (historical bars vs broker) and the order/position backend
  (in-memory store vs `OrderManager`/`PositionManager`). This is the
  "same code, two backends" requirement made concrete. If a shared base class
  feels over-engineered, the alternative is one loop module with a
  `BrokerAdapter` protocol — see §4.
- `walk_forward` / `monte_carlo` are V1.1 (see §7); their modules exist as
  placeholders in the tree but are not first milestone.

**BrokerAdapter protocol** (the seam that keeps one pipeline):

```python
class BrokerAdapter(Protocol):
    def place_limit(self, request: OrderRequest) -> OrderResult: ...
    def cancel(self, order_id) -> bool: ...
    def modify_sl(self, ticket, new_sl) -> bool: ...
    def close_position(self, ticket, direction, volume) -> bool: ...
    def open_positions(self) -> list[PositionSnapshot]: ...
    def pending_orders(self) -> list[PendingOrder]: ...
    def account_equity(self) -> float: ...
    def current_spread_price(self) -> float: ...
```

- Backtest implementation: in-memory `StateStore` + `fill_model`.
- Paper/live implementation: wraps `OrderManager` + `PositionManager` +
  `MT5Connector` (existing, frozen, already tested).

---

## 2. Runner contract (the most important section)

### 2.1 Bar loop (closed-bar cadence, v25 semantics)

The loop is **bar-driven**: every decision happens once per closed bar, using
that bar's OHLC and the injected `now` = bar timestamp. Tick handling is a
paper/live-only refinement (see §2.4) and must not change decision order.

```
for each bar b in series (ascending):
    now = b.timestamp                          # THE clock — injected everywhere

    # ── 0. Daily rollover ────────────────────────────────────────────────
    if utc_date(now) != utc_date(prev_now):
        risk.reset_day()

    # ── 1. Portfolio-level guards (ONCE per bar, before anything else) ───
    if risk.evaluate_friday_close(now):
        close ALL open positions               # via BrokerAdapter.close_position
        cancel ALL pending limits              # via BrokerAdapter.cancel
        record each close outcome (win/loss, sl_level, sweep) into risk state
        continue                               # skip per-position + entry work this bar

    if risk.hard_cancel_pending(now, news_events):
        cancel ALL pending limits              # §11 pre-news blackout
        # POI re-arm semantics: OPEN DECISION (§8.6)

    # ── 2. Feed the §5 machine for every armed POI ───────────────────────
    for poi in armed_pois:
        engine.feed_bar(poi, b)                # touch → TESTED, close-beyond → VIOLATED

    # ── 3. §23 unfilled-order expiry ─────────────────────────────────────
    for pending in pending_limits:
        if poi_state_machine.expire_unfilled(poi, bars_open=b.index - pending.placed_bar):
            cancel pending                      # POI now TESTED

    # ── 4. Per-position exit management (FVG invalidation + BE) ──────────
    for position in open_positions:
        decision = risk.evaluate_exit(
            PositionState(
                direction, entry_price, current_sl, atr=b.atr,
                current_price=b.close,           # closed-bar price
                closed_close=b.close,            # the just-closed bar (None → skip FVG)
                bar_index=b.index,
            ),
            now=now,
            fvg_context=trade_fvg[position.ticket],   # captured at trade open
        )
        if decision.action == EXIT:
            close_position(...); record_result(...); record_sl_close(...);
            record_failed_sweep(...) if loss; del trade_fvg[ticket]
        elif decision.action == MOVE_SL:
            if broker.modify_sl(ticket, decision.new_sl):
                risk.on_be_applied()            # latch ONLY after broker acceptance

    # ── 5. Physical SL/TP hits (broker semantics, runner-owned) ──────────
    for position in open_positions:
        if bar_hit_sl(b, position): close at SL; record loss; guards...
        elif bar_hit_tp(b, position): close at TP; record win

    # ── 6. Entries ───────────────────────────────────────────────────────
    for poi in armed_pois where state_machine.can_trade(poi):   # FRESH only
        route = engine.scan_route(poi, candles_up_to(b), swings, from_bar=arm_bar)
        if route is None: continue               # give-up window handles expiry
        # Risk pre-entry gates + sizing (single path):
        decision = risk.evaluate_entry(EntryRequest(
            direction=route.signal.direction, entry_price=route.signal.entry_price,
            sl_price=route.signal.stop_reference, atr=b.atr, current_bar=b.index,
            now=now, equity=account.equity, risk_fraction=CONFIG_RISK,
            pip_value_per_lot=..., min_lots=..., lot_step=...,
            score=poi.score, current_spread_price=broker.current_spread_price(),
            sweep_level=..., news_events=news_events, allowed_sessions=sessions,
        ))
        if decision.action != ENTER: continue    # blocked_by logged; one-shot NOT burned
        outcome = engine.execute_route(          # news/session gates (2nd line of defense)
            route, volume=decision.lots, now=now,
            news_events=news_events, allowed_sessions=sessions,
        )
        if outcome.blocked: continue             # I2: no _mark_fired — retry next bar
        if outcome.order_result is not None and outcome.order_result.placed:
            pending_limits.append(PendingOrder(ticket, route, placed_bar=b.index))
            trade_fvg[poi.id] = capture_fvg(route)   # open seam (§0.4.1 / §8.2)

    # ── 7. Pending limit fills (backtest: bar-range touch; paper: ticks) ──
    for pending in pending_limits:
        if fill_model.limit_filled(pending, b):      # §5 fill rules
            broker-adapter marks filled at fill price
            risk.on_trade_opened()                   # re-arm BE latch
            open_positions.append(Position(...))
            pending_limits.remove(pending)
```

### 2.2 Call-order table (why this order)

| # | Call | When | Why here |
|---|---|---|---|
| 0 | `reset_day()` | UTC date change | v25 daily rollover resets breaker + sweep + same-level |
| 1 | `evaluate_friday_close` | once per bar, first | Portfolio-level §28.4 outranks everything; clears the whole book |
| 1b | `hard_cancel_pending` | once per bar | §11 pre-news; cancels pending before any fill/entry logic |
| 2 | `feed_bar` | per POI per bar | §5 touch/violation must reflect the closed bar before exits/entries |
| 3 | `expire_unfilled` | per pending | §23 — unfilled order past N bars kills the POI |
| 4 | `evaluate_exit` | per position | FVG invalidation + BE on the just-closed bar |
| 5 | SL/TP physical hits | per position | Broker semantics; after risk exits so risk exits win the bar |
| 6 | `evaluate_entry` → `execute_route` | per FRESH POI | Entry only after exits; risk gates + engine gates compose |
| 7 | fills | after entries | A fill from THIS bar's entry uses this bar's range (conservative: fill only if the bar actually traded through) |

### 2.3 Fills: backtest vs paper/live

| Concern | Backtest | Paper/live |
|---|---|---|
| Data feed | Historical `list[Candle]` (CSV) | `MT5Connector.copy_rates` / ticks |
| Limit fill | `fill_model` on bar range | Broker fills; runner observes via `positions_get` + `orders_get` |
| SL/TP hit | `fill_model` on bar range | Broker stops; runner observes closes |
| Spread | Fixed config value (decision §8.8) | `symbol_info_tick` real spread |
| Slippage | Zero (V1) | `slippage_simulator` (25–50 pts, plan §6) |
| Latency | Zero | `kpi_logger` measures bar-close → ACK |
| Equity | Simulated from fills | `account_info()` |

### 2.4 Pending-order lifecycle

- Stored: `PendingOrder{order_id, route, poi_id, placed_bar, limit_price, direction, volume, sl}`.
- Expired: §23 via `expire_unfilled` (M5=12 / M1=30; H1+ no rule → runner must
  not auto-expire; flag if a rule is wanted).
- Cancelled: §11 `hard_cancel_pending`, Friday EOD, or explicit runner action.
- Filled: `fill_model` (backtest) / broker (paper).
- One-shot identity: `PipelineEngine._mark_fired` fires ONLY on an accepted
  `execute_route` (post-audit I2). A pending order that later gets cancelled
  does NOT un-fire the POI — **the POI cannot re-enter after an accepted
  execution**, regardless of the order's fate (R1 §11 event identity). This
  reading is conservative and matches the audit ruling; confirm in §8.6.

---

## 3. State ownership map

| State | Owner | Where | Notes |
|---|---|---|---|
| POI freshness state | **engine-owned** | `PipelineEngine.state_machine` (`POIStateMachine._states`) | Atomic transitions; runner only feeds events |
| POI arm bar / fired / outcome | **engine-owned** | `PipelineEngine._episodes` | One-shot identity; runner reads via `episode(poi)` |
| Pending limit orders | **runner-owned** (backtest: store; paper: broker + mirror) | `PendingOrder` list / broker | Runner enforces §23/§11 lifecycle |
| Open positions | **runner-owned** (backtest: store; paper: broker) | `Position` list / `positions_get` | Runner applies all closes/modifies |
| FVG context per trade | **runner-owned** | `trade_fvg: dict[ticket, FvgContext]` | Captured at trade open; cleared on close |
| Circuit breaker | **risk-owned** | `RiskEngine.circuit_breaker` | Runner only calls `record_result`/`reset_day` |
| Same-level guard | **risk-owned** | `RiskEngine.same_level_guard` | Runner calls `record_sl_close` |
| Sweep guard | **risk-owned** | `RiskEngine.sweep_guard` | Runner calls `record_failed_sweep` |
| Friday latch | **risk-owned** | `RiskEngine.friday_eod` | Runner only calls `evaluate_friday_close` |
| PureRunner BE latch | **risk-owned** | `RiskEngine.pure_runner` | Runner calls `on_trade_opened` / `on_be_applied` |
| Equity / daily stats | **runner-owned** | backtest sim / `account_info` | Backtest derives from fills; paper reads broker |
| News calendar | **runner-owned** | `list[NewsEvent]` injected | Feed from calendar source (Phase 6/7 concern) |
| ATR / indicator state | **computed per call** | `smc.utils.atr.latest_atr` | Pure; no persistent state needed |

**Rule:** the runner NEVER mutates risk-owned or engine-owned state except
through the documented lifecycle calls. This is already enforced by the
frozen code (state objects are internal; only `state` read-only handles are
exposed).

---

## 4. Event bus & state store abstraction

### 4.1 Event bus (minimal)

```python
class EventBus(Protocol):
    def publish(self, event_type: str, payload: dict) -> None: ...
    def subscribe(self, event_type: str, handler: Callable[[dict], None]) -> None: ...

class InProcessEventBus:  # smc/backtest/event_bus.py
    # dict[event_type, list[handler]]; publish is synchronous, in-order
```

- Event types (V1, closed set): `bar_closed`, `poi_created`, `poi_armed`,
  `trigger_fired`, `order_placed`, `order_cancelled`, `order_filled`,
  `position_opened`, `position_closed`, `sl_moved`, `blocked_entry`.
- Backtest: `InProcessEventBus` (synchronous — determinism is the point).
- Live: a `RedisStreamsBus` implementing the same interface later (per
  DEVELOPMENT_PLAN); the interface is the contract, not the transport.
- **V1 recommendation:** the loop can run with an optional bus (None = no
  events). The bus is for observability/replay, NOT for control flow — the
  loop must not depend on handler ordering.

### 4.2 State store (minimal)

```python
class StateStore(Protocol):
    def get(self, key: str) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...
    def delete(self, key: str) -> None: ...

class InMemoryStateStore:  # smc/backtest/state_store.py
    # dict + optional lock; keys: "positions", "pending", "equity", ...
```

- Backtest: `InMemoryStateStore` (plain dict).
- Live: Redis-backed implementation of the same interface (the in-memory
  `POIStateMachine` already documents this exact seam — "the Redis-backed CAS
  replaces this store unchanged").
- Do NOT put engine/risk state in the store in V1 — those already own their
  state internally. The store is for RUNNER state (positions, pending,
  equity, trade log) so a future live run can share it.

---

## 5. Fill model / realism (V1 assumptions)

`smc/backtest/fill_model.py` — pure functions over `(Candle, order)`:

| Rule | V1 assumption | Frozen? |
|---|---|---|
| Limit fill | BUY limit fills iff `bar.low <= limit_price`; SELL limit iff `bar.high >= limit_price` | **Decision needed** (§8.2) |
| Limit fill price | Fill at the LIMIT price (conservative; no price improvement) | Decision needed |
| SL hit | `bar.low <= sl` (long) / `bar.high >= sl` (short) → close at SL price | Frozen semantics (broker) |
| TP hit | `bar.high >= tp` (long) / `bar.low <= tp` (short) → close at TP price | Frozen semantics (broker) |
| Same-bar SL+TP | **SL assumed first (worst case)** — conservative | Decision needed (§8.3) |
| Same-bar entry + SL | Entry evaluated on the bar AFTER the signal bar (limit rests; fill requires a later bar's range) | Conservative, deterministic |
| Partial fills | **NO** for V1 (full fill or none) | Decision needed |
| Spread | Backtest: fixed config value in price units, applied to limit fill price (buy fill = limit + spread/2, sell = limit − spread/2) — or ignored if decision says so | Decision needed (§8.8) |
| Slippage | Zero in backtest V1; `slippage_simulator` in paper | Decision needed |
| Intra-bar ordering | No path reconstruction in V1 — bar-range touch only, with the SL-first rule above | Decision needed |
| FVG invalidation input | `closed_close = bar.close` (the just-closed bar) | **Frozen** (post-audit closed-bar contract) |

**What is frozen:** closed-bar FVG contract, SL/TP price semantics, no market
orders from triggers, one-shot event identity.
**What needs Lead Architect decision:** every row marked "Decision needed".

---

## 6. Performance & reporting minimum (V1)

Mandatory metrics (all derivable from the trade log — no new data needed):

| Metric | Source |
|---|---|
| Trade list (CSV: open/close time, entry/exit price, SL/TP, direction, model tags, trigger, RR, P/L) | Runner trade log |
| Profit Factor, win rate, average RR, recovery factor | `performance_analyzer` |
| Max drawdown (equity curve), exposure (% time in market) | Equity curve from fills |
| Per-model breakdown (PF/win rate per model tag) | Trade log × `poi.models` |
| Per-trigger breakdown (A–F) | Trade log × `route.signal.trigger` |
| MFE/MAE distribution | OHLC between open and close of each trade |
| Blocked-entry log (reason counts: news/session/breaker/same-level/sweep/spread/min_lots) | Runner block log |

KPI for the Future Flexibility Clause (paper only, `kpi_logger`):
- bar-close → order ACK latency
- order success rate (accepted / attempted)
- management delay (signal → SL modify applied)
- missed events / missed bars
- These feed the §8.9 decision (thresholds that would trigger porting a
  component back to MQL5).

Report output: CSV (machine) + one HTML summary (human). No charts library in
V1 unless already in the project (none is).

---

## 7. Walk-forward / Monte Carlo

**Recommendation: V1.1, NOT V1.**

Rationale: the plan itself lists them as statistically complex, and the
"Missing Design Decisions" section flags window sizing as unresolved. Building
them before the bar loop + fills + risk integration are proven risks a
two-week detour. The milestone split (§9) puts them after paper trading.

Minimal viable designs (for the V1.1 kickoff, not this session):

- **Walk-forward:** fixed IS window (2 years) / OOS window (6 months) rolling
  forward (plan's numbers); only parameters that are NOT frozen may be tuned
  (e.g. session config, risk fraction within the locked band) — frozen
  thresholds are never re-fit. OOS metrics reported per window.
- **Monte Carlo:** resample the realized trade sequence (with replacement) to
  build a P/L distribution; report median/5th/95th percentile drawdown and
  PF. No path-level resampling in V1.1.

---

## 8. Open decisions for Lead Architect

1. **Loop mode:** bar-by-bar only for V1 (recommended), hybrid vectorized as a
   later optimization? (Plan mentions vectorized mode; state-dependent logic
   — freshness, cooldowns, one-shot — makes vectorization genuinely hard.)
2. **Limit fill price:** fill at limit price (conservative, recommended) vs
   fill at better-of(open, limit) when the bar gaps?
3. **Same-bar SL+TP:** SL-first (worst case, recommended) vs TP-first vs
   open-close path reconstruction?
4. **Missing `closed_close`:** skip FVG check + log (recommended — matches the
   engine's `None`-skips contract) vs hard error?
5. **Retention policy for `_episodes` / `POIStateMachine._states`:** prune
   episodes whose POI is TESTED/VIOLATED after N bars (recommended: prune at
   give-up + expiry horizon, e.g. 40 bars) vs leave unbounded for V1?
6. **Hard-cancel semantics (§11):** after `hard_cancel_pending`, may the POI
   re-place an order once the blackout clears? Note: I2 says blocks don't burn
   the one-shot, but a CANCELLED order is a different event — recommend: POI
   stays FRESH and may re-fire after the §11 window (the order, not the POI,
   was cancelled).
7. **FVG context source:** map trigger type → FVG boundaries for
   `FvgContext` at trade open. Recommend: `DisplacementResult` FVG for A
   (from the validation `displacement_map`), OB zone for F, and a documented
   "no FVG → `valid=False`" default (invalidation skipped) for B/C/D/E.
8. **Backtest spread:** fixed config value (recommended, price units) vs zero
   spread in V1 vs spread column in CSV? (Affects fill prices and the
   `current_spread_price` gate.)
9. **Paper-trading acceptance:** 30 consecutive trading days (plan) —
   confirm duration + the KPI thresholds that trigger the Future Flexibility
   Clause (latency ms, missed-events %, order success %).
10. **Multi-TF ingestion:** M8 needs D1/H4 aligned with the M5 execution
    series — confirm a `dict[Timeframe, list[Candle]]` registry is the
    accepted V1 shape (CSV loader stays single-TF; a small alignment helper
    is added in Phase 6).
11. **Walk-forward windowing** (V1.1): confirm 2Y IS / 6M OOS rolling with
    6-month steps (plan's numbers) when V1.1 starts.

---

## 9. Proposed Phase 6 milestone split

| Milestone | Scope | Exit criteria |
|---|---|---|
| **M1 — Thin bar loop** | `InMemoryStateStore`, `InProcessEventBus`, `backtest_engine` skeleton: load CSV → iterate bars → `feed_bar` + `scan_route` + `execute_route` (no fills, no risk) | Deterministic run over synthetic CSV; POI/trigger log matches unit-test expectations; suite green |
| **M2 — Fills + order lifecycle** | `fill_model`, pending-order store, §23 expiry, SL/TP hits, position store | Synthetic bar series produces expected fills/closes; equity curve correct |
| **M3 — Risk integration** | `evaluate_entry` sizing+gates, `evaluate_exit` (FVG + BE + `on_be_applied`), `evaluate_friday_close`, `hard_cancel_pending`, all state hooks, `reset_day` | A full synthetic week exercises every risk decision; blocked/exit logs correct |
| **M4 — Reporting** | `performance_analyzer`, `report_generator` (CSV + HTML) | Trade list + metrics match hand-computed values on a tiny fixture |
| **M5 — Paper runner** | `paper_trading_runner` (same loop, `BrokerAdapter` over `OrderManager`/`PositionManager`/`MT5Connector`), `slippage_simulator`, `kpi_logger` | Demo-account dry run for one day; KPIs logged; no entry logic divergence from backtest |
| **M6 — V1.1** | `walk_forward`, `monte_carlo` | OOS + resampled reports on backtest data |

No time estimates per instruction; ordering is dependency-driven (M1→M5
strict, M6 optional after).

---

## 10. Where Phase 0–5 still makes Phase 6 hard (candidates)

1. **FVG boundaries are not persisted anywhere** (verified: `signal.data` has
   anchors, not FVG geometry) — the §8.7 mapping is required before M3.
2. **`_episodes` / state-machine stores are unbounded** — long M1 runs
   (1.3M bars/5y per plan) will grow memory without §8.5.
3. **No multi-TF ingestion** — M8's D1/H4 dependency (§21/§26) has no loader
   path; §8.10.
4. **`POI` has no creation-bar index** (documented Phase 3 note) — the runner
   cannot feed Pillar 4 events "from creation" without the engine's
   `arm_bar` bookkeeping; the design leans on `arm_at`/`_episodes` (works, but
   is engine-internal — worth a public accessor in M1).
5. **`OrderRequest` has no order-id/expiry field** — §23 expiry is anchored to
   `placed_bar` by the RUNNER (engine has no pending-order registry). This is
   acceptable (runner-owned per §3) but should be stated as a contract, not an
   accident.
6. **`Timeframe` H1+ has no §23 expiry rule** (`expiry_bars_for` → None) — the
   runner must not invent one; flag if H1+ orders need a rule.

---

## 11. Design invariants (recap)

- One loop, two backends (backtest store / broker adapter) — never two
  pipelines.
- All clocks injected; `now` = bar timestamp in backtest, `datetime.now(utc)`
  at the paper/live boundary ONLY (the single wall-clock edge).
- The runner applies; engines decide; stores hold runner state only.
- Frozen thresholds never re-fit (walk-forward tunes only non-frozen config).
- Every blocked/cancelled/filled event is logged with a machine-readable
  reason — the KPI and FF-clause data depend on it.