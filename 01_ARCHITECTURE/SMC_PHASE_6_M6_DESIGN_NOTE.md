# Phase 6 — Milestone 6 Design Note: Paper Runner + KPI Logging

Status: COMPLETE (all 501 tests green — 496 pre-existing + 5 audit-fix tests)
Scope: paper-trading runner over the live execution layer + operational KPI logging. Walk-forward / Monte Carlo remain V1.1 (out of scope).

---

## 1. Paper loop structure

`smc/paper/runner.PaperRunner` composes the frozen shared stack — it is not
a copy of `BacktestRunner`:

* **Pipeline side**: the exact M4 `PipelineAdapter` drives `PipelineEngine`
  (scan → route → candidates, §5 freshness feed, §11 one-shot workflows).
  The paper runner IS the adapter's runner: it implements the same
  `submit_entry` / `set_pipeline_adapter` / `cancel_pending_for_poi` /
  `on_candidate_accepted` seam the backtest runner exposes, so the
  identical adapter object drives both paths. **The real adapter is
  auto-attached**: `PaperRunner.__init__` calls `pipeline.attach(self)`
  (guarded for protocol stubs), so no manual wiring step is needed
  (audit I2; proven by the real-adapter composition test).
* **POI provisioning (audit I2)**: validated POIs reach the engine the
  same way they do in the M4 integration tests — an external driver
  calls `engine.validate(...)` (with injected displacement) then
  `engine.arm_at(poi, arm_bar)` before the first cycle. V1 ships no
  in-package detection loop; the Phase 7 live driver owns
  detect → validate → arm, and the paper runner consumes whatever the
  adapter's engine tracks.
* **Risk side**: the same pure `RiskEngine` — `evaluate_entry`,
  `evaluate_exit`, `evaluate_friday_close`, `hard_cancel_pending`,
  `on_trade_opened`, `on_be_applied`, state updates. No second sizing
  path: accepted entries are sized by `evaluate_entry` (§28.7 policy
  band + `LOT_MAX_SAFETY` cap) and sent at that size.
* **Broker side**: the new thin `BrokerAdapter` over the frozen Phase 4
  execution layer (`OrderManager` / `PositionManager`).

Per-bar order (locked backtest order, applied live; `run_one_cycle(bar)`
is called when a bar CLOSES — bar-close driven V1):

1. UTC date change → `reset_day()`;
2. `evaluate_friday_close(now)` → close ALL + cancel ALL (portfolio,
   KPI-logged) and skip the rest of the bar;
3. `hard_cancel_pending(now, news_events)` → cancel all pendings (§11);
   3b. **C1 §23/§24 age expiry**: GTC pendings never expire at the
   broker (`ORDER_TIME_GTC`), so the runner cancels by AGE — M5 = 12 /
   M1 = 30 bars (§23), the 20-bar §24 give-up backstop elsewhere —
   before fill observation, emitting a `management` cancel record;
4. observe broker truth: fills (pending → position) and closes
   (position disappeared);
5. per-position `evaluate_exit` → EXIT (market close) / MOVE_SL (modify);
6. entry step LAST: adapter scan → `evaluate_entry` → real pending limit.

The live scan series: the runner appends each closed bar to the adapter's
candle list (`_remember_bar`), so the adapter's per-bar prefix slicing
keeps the same causal no-lookahead contract as backtest. The bar index
handed to the adapter is the last index of that growing series. The
runner also computes ATR from that same series per bar (I1 parity with
backtest).

## 2. Live adapter responsibilities (`broker_adapter.py`)

Deliberately thin — execution calls only, zero decisions, raises nothing:

| Decision (RiskEngine)     | Adapter call                       | Execution layer |
|---------------------------|------------------------------------|-----------------|
| ENTER                     | `place_limit(OrderRequest)`        | `OrderManager.place_limit` (§10: limits only) |
| EXIT / Friday close       | `close_position(ticket, dir, vol)` | `PositionManager.close_position` (opposite DEAL) |
| MOVE_SL (BE)              | `modify_sl(ticket, new_sl)`        | `PositionManager.modify_sl` — the manager re-sends the position's untouched TP alongside the new SL, so the post-audit rule (an SL move never clears the TP) holds at the execution layer |
| §11 hard-cancel / EOD     | `cancel_pending(ticket)`           | `OrderManager.cancel_order` (REMOVE) |

Failure policy: every method returns a success/latency outcome; the
runner calls `on_be_applied()` ONLY on a successful modify (M6
constraint) and pops tracking state only on confirmed cancels/closes.
`ValueError` from a vanished ticket surfaces as a failed modify, not a
crash. Call latency is measured with the injected `perf` monotonic
source and returned in the outcome so the KPI logger records
decision→ack and management delays without a second clock read.

## 3. KPI set and record shape (`kpi_logger.py`)

Append-only `KPILogger`; every record's timestamp is INJECTED (`at=`),
never wall-clock. One JSON object per event:

| event          | fields |
|----------------|--------|
| `decision`     | latency_ms (bar-close → decision-complete), candidates, placed, blocked, rejected, bar_index |
| `order_ack`    | latency_ms (decision → broker ack), success, retcode, ticket |
| `management`   | op (`modify_sl` / `close` / `cancel`), ticket, success, latency_ms |
| `fill`         | ticket, poi_id, trigger, volume |
| `trade_closed` | ticket, kind, win (None when honestly unknown), poi_id, exit_price |
| `missed_bar`   | expected_at, gap_bars |
| `hard_cancel`  | cancelled |
| `friday_close` | closed, cancelled |

`counters()` derives the operational tallies (orders placed/rejected,
SL-modify success/failures, exit-close success/failures, cancels, fills,
hard-cancels, Friday closes, missed-bar episodes/bars). **No pass/fail
threshold engine** — the Future Flexibility Clause thresholds are not
frozen, so V1 logs metrics only. Exports: `to_json` (sorted keys),
`write_jsonl`, `write_csv` (sorted header union) — byte-identical for
identical inputs (proven by test).

## 4. Fill / close observation (broker truth, not simulation)

* **Fill matching is by ORDER IDENTITY LINKAGE, never ticket equality
  (audit C2).** In the real MT5 API `POSITION_TICKET` is a DIFFERENT
  identifier from the order ticket returned by `order_send` — the
  earlier "position id equals order ticket" claim in this note was
  wrong and is retracted. A placed pending is matched to a broker
  position on `(symbol, magic, comment)` — the fields that carry from
  the order record to the position record (`POSITION_MAGIC` /
  `POSITION_COMMENT`; the order comment is the §11 `route_id`, which
  the runner stamps at placement). `PositionSnapshot` now surfaces
  `magic` / `comment` for this. The pending's client-side identity
  (poi_id, trigger, route_id, FVG context, sweep level) transfers to
  the tracked position keyed by the POSITION ticket; `on_trade_opened()`
  fires (BE latch re-arm); a `fill` KPI record is emitted.
  `ORDER_POSITION_ID`-based matching (polling `orders_get` after fill)
  is the recorded Phase-7 upgrade when order-history polling lands.
* **Close** = a tracked position disappears from `positions_get`.
  Documented V1 limitation (honest, not faked): the closing deal's
  exact price/kind/P&L is NOT reconstructed from MT5 history, so
  close records carry `win=None` and are deliberately NOT fed into the
  circuit breaker (`record_result` must never guess). Same for
  runner-initiated exits and Friday closes. History/deal
  reconciliation is the recorded next-milestone item.

### Hard-cancel ruling (audit I3 — recorded)

A §11 hard-cancel does NOT consume the adapter's one-shot workflow: the
workflow survives and its candidate may be re-submitted once the blackout
clears, but a new limit is placed only while the workflow is still alive
(§24 `signal_expired` drops it; a POI VIOLATION drops it and cancels
resting limits). The §5 machine is never re-armed — FRESH is never
restored, so this is not an auto-rearm of the POI.

## 5. Safety / demo posture

* `start()` refuses to run when `connector.initialize()` fails;
  `stop()` releases the connector (idempotent).
* `dry_run` config flag: decisions are evaluated and KPI-logged, but no
  order is sent and the §11 one-shot is not consumed.
* Symbol/magic live on the injected managers; sizing inputs on
  `PaperConfig`; spread in PRICE units like the backtest.
* The paper package shares NO mutable state with the backtest fill
  model — `PendingOrderBook` / `PositionStore` stay backtest-pure
  (the M2 store import guard remains valid).

## 6. Tests (fake connector + fake perf, real managers/runner)

15 tests cover: start/stop posture, one-cycle decision record,
successful entry (real limit request shape, policy volume 0.10,
identity comment, one-shot consumed), rejected order (KPI counter,
one-shot preserved — I2 parity), dry-run, per-POI cancel parity,
fill observation + identity transfer + `on_trade_opened`, BE modify
success (latch set, SL moved), BE modify failure (latch NOT set,
`on_be_applied` never called), close observation (unknown win, breaker
untouched), Friday EOD (2 closes + 1 cancel + episode record), §11
hard-cancel (pendings only), missed-bar gap detection, and KPI
determinism (`to_json` byte-identical under the fake clock/connector).

## 7. Known MT5/demo limitations (documented, none faked)

1. Close P/L, kind, and price are unknown in V1 (no history
   reconciliation) → breaker/same-level/sweep state updates on live
   closes are deferred until deal-history parsing lands.
2. Partial fills surface as a normal fill at the reported
   volume; volume-specific partial handling is not modelled.
3. Requotes / async rejects appear as a failed `order_ack` with the
   broker retcode (no retry policy in V1 — logged only).
4. `copy_rates` gaps are detected as `missed_bar` records against the
   nominal TF cadence; irregular-session gaps (weekends) are not
   special-cased (the gap counter may over-count across a weekend —
   acceptable for a demo-posture V1, recorded honestly).
5. Fill linkage requires the broker position to carry the order's
   magic/comment (true for real MT5 `positions_get`). Brokers that strip
   comments would need `ORDER_POSITION_ID` polling (Phase 7 upgrade).
   A filled pending matched by linkage is consumed even if the broker
   reports the fill at a position ticket that never appears in
   `positions_get` again.
