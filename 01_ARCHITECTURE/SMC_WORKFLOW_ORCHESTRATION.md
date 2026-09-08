# SMC Workflow Orchestration — Zero-Lag Event-Driven Pipeline (Locked Decisions)

**Date:** 2026-09-05
**Status:** CANONICAL — implements every rule in `SMC_RESEARCH/LOCKED_DECISIONS.md` (Sections 1–22)
**Design Goal:** Each pipeline level communicates with every other level through an event bus with **no polling and no lag**. Output = the best possible signal set (fully validated, confluence-ranked) plus deterministic trade tickets.

---

## 1. Design Principles (the "no lag" contract)

1. **Event-driven push, never polling.** Every stage publishes events the instant a condition resolves (bar close, sweep wick, pillar pass). No stage "checks" another stage — it reacts to its subscribed events. Latency target: `< 50 ms` between bar-close and stage-1 classification.
2. **Contract-first typed events.** All communication uses versioned JSON schemas (Section 4). Stages only consume published contracts — no shared function calls across levels.
3. **Single source of truth = State Store.** POI states, freshness, cooldowns, sweep registry, and order book live in a Redis-style key-value store. Events are facts; the store is the current truth; logs are the audit trail.
4. **Deterministic ordering.** Events are processed in arrival order **per partition** (symbol + timeframe + price level). Chronological trigger selection (Locked §12) requires this ordering to be guaranteed.
5. **Idempotency & dedup.** Every event carries `event_id` (hash of source + bar time + level). Consumers dedup by `event_id`, so retries never double-fire a signal.
6. **Hard gates, soft gates.** Pillars 1–4 are hard (reject on failure); Inducement is soft (70/100 scoring). A signal is only emitted when all hard gates pass.
7. **Backpressure, not silence.** If a consumer falls behind, the bus buffers per partition and the Health Monitor raises a lag alert — stages never drop events silently.
8. **One pipeline, two outputs.** Every validated POI produces (a) a ranked **signal** (for review/auto-trading) and (b) an auditable **reason trail** (which tags, which pillars, which trigger) so every decision can be replayed.

---

## 2. Architecture Overview

```
┌───────────────────────────────  EVENT BUS (Redis Streams / NATS / RabbitMQ)  ───────────────────────────────┐
│  partitioned by {symbol} + {symbol, poi_id} • ordered • idempotent • versioned contracts                    │
└───────▲────────────▲────────────▲────────────▲────────────▲────────────▲────────────▲───────────▲───────────┘
        │            │            │            │            │            │            │           │
   ┌────┴───┐   ┌────┴────┐  ┌────┴────┐  ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────┐  ┌───┴────┐  ┌───┴───────┐
   │ L0     │   │ L1      │  │ L2      │  │ L3       │  │ L4       │  │ L5       │  │ L6     │  │ L7        │
   │ DATA   │──▶│ LIQUID- │─▶│ DISPL & │─▶│ POI      │─▶│ VALIDATE │─▶│ TRIGGER  │─▶│ EXECUTE│─▶│ MANAGE    │
   │ INGEST │   │ ITY     │  │ SWING   │  │ CLASSIFY │  │ (5       │  │ ROUTE    │  │ (NEWS, │  │ (PURE-    │
   │        │   │ (0A)    │  │ (0b/0c) │  │ (1/1b)   │  │ PILLARS) │  │ (3)      │  │ LOTS)  │  │ RUNNER)   │
   └────────┘   └─────────┘  └─────────┘  └──────────┘  └──────────┘  └──────────┘  └────────┘  └───────────┘
        ▲             ▲              ▲              ▲             ▲              ▲            ▲            ▲
        └─────────────┴──────────────┴──────────────┴─────────────┴──────────────┴────────────┴────────────┘
                                        STATE STORE (Redis): poi:{id} • freshness • cooldowns • sweep registry
                                        HEALTH MONITOR: per-level heartbeats • lag alerts • dead-letter queue
                                        OUTPUT LAYER: ranked signals (3+ tags first) + trade tickets + audit log
```

**Level ownership of the locked pipeline stages:**

| Level | Pipeline Stage(s) | Owns |
|-------|-------------------|------|
| L0 Data Ingest | — | MT5 bar stream (D/H4/H1/M30/M5/M1), news calendar (CPI/NFP/FOMC) |
| L1 Liquidity | Stage 0A | Sweep detection on the 6 locked liquidity types |
| L2 Displacement & Swing | Stages 0b, 0c | BOS + FVG + ≥1× ATR; Base Candle & Swing Validity gate |
| L3 POI Classification | Stages 1, 1b | Modular tags M1–M8, CHOCH Rule 1/2/3 |
| L4 Validation | Stage 2 | 5 Pillars (refinement, displacement, P/D, freshness, inducement) |
| L5 Trigger Routing | Stage 3 | 6 triggers A–F, chronological first-valid |
| L6 Execution | Stage 4 | News hard-cancel, lot sizing, limit orders |
| L7 Management | Stage 5 | PureRunner, FVG invalidation, circuit breaker, same-level guard, Friday EOD |

---

## 3. Level-by-Level Responsibilities (all thresholds locked)

### L0 — Data Ingestion
- **Two distinct streams** (bar-close vs tick — they drive different levels):
  1. `bar.closed` — published the moment the bar closes (MT5 via Python bridge, tick-accurate timestamps). Drives L1 (sweeps), L2 (displacement/swing), L3 (classification), L4 (pillars incl. FVG invalidation check), L5 (trigger routing). Sweep confirmation and BOS **require finalized bars** — never evaluated intra-bar.
  2. `tick.quote` — published on every tick arrival. Drives **only L7 (trade management)**: PureRunner SL→BE at +1.0× ATR and any real-time exit must react to ticks, not wait for a bar close (waiting exposes 100% risk to intra-bar reversals).
- Push `news.flash` ≥ 30 min ahead of high-impact events (US CPI, NFP, FOMC).
- Push `order.execution` (fill/partial/reject) from the broker.
- **No analysis here** — this level is a dumb, fast pipe.

### L1 — Liquidity & Sweep Engine (Stage 0A)
- Maintains the **sweep registry**: one entry per level of the locked taxonomy:
  1. Session H/L (Asia 00:00–07:00, London 07:00–13:00, NY 13:00–20:00 UTC)
  2. PDH/PDL, PWH/PWL
  3. EQH/EQL — top (BSL) **and** bottom (SSL), tolerance ≤ 4.5 pips on XAUUSD
  4. Structural Swing H/L — Base Candle gate only (minor noise discarded)
  5. POI sweeps — any OB or FVG boundary sweep at a POI **is** a liquidity sweep
  6. D&S / OB boundary fallback sweeps — zone extreme when no in-between entry occurred
- Sweep rule: wick pierces the level **and** candle body closes back inside → emit `liquidity.sweep` with direction BSL/SSL.
- Marks the swept level in the store as "consumed" (smart-money zero-return edge, Locked §2.7).

### L2 — Displacement & Swing Validation (Stages 0b/0c)
- On `liquidity.sweep`, verify displacement: **BOS confirmed + FVG created + ≥ 1× ATR** (hard fail < 0.5× ATR).
- On displacement, run the **Swing Validation Gate**: find the Base Candle at the extreme; require body close beyond the opposite extreme. Wick-only or two-bar-only = `swing.invalid` (no POI). Bearish exception: next candle wick can create the low.
- Emit `displacement.confirmed` or `swing.invalidated`.

### L3 — POI Classification (Stages 1/1b) — modular, no hierarchy
- Labels the level with **all** matching tags M1–M8 (equal tags, no suppression):
  - M1 Origin D/S base · M2 RBS/SBR breaker · M3 CHOCH retest (Rule 1/2/3 sub-classified) · M4 QML (full wick range) · M5 Extreme EQH (continuation, entry at broken equal level) · M6 Neckline/DBDT · M7 Equal resistance shelf (reactive) · M8 HTF D/S zones (D1/H4 → M5 approach → M1 trigger, +10% bonus if D1+H4 overlap)
- Confluence score = f(number of independent tags): 1 = base, 2 = elevated, 3+ = institutional-grade.
- Emit `poi.classified` with `tags[]`, level boundaries, detection TF.

### L4 — Validation (Stage 2 — 5 Pillars)
On `poi.classified`, run in order (all hard except Pillar 5):
1. Zone refinement — unmitigated OB/FVG within **±0.5× ATR** (else reject: naked level)
2. Displacement — BOS + FVG + **≥ 1× ATR** (else reject)
3. Premium/Discount — coupled to POI detection TF; buys < 45%, sells > 55%; 45–55% = reject
4. Freshness — `STATE_FRESH` (strict 1-touch); tested/violated = reject
5. Inducement — soft: 100% with, 70% without; never hard reject
- Emit `poi.validated` (score, timestamp) or `poi.rejected` (reason).

### L5 — Trigger Routing (Stage 3)
- On `poi.validated`, drop to M1/M5 and arm the compatible triggers (per Locked §15 matrix).
- **Chronological first-valid wins** (Locked §12) — the store's per-level order guarantees this.
- Triggers: A CHOCH (body close; entry at broken structural level, **not** origin OB) · B Leading Diagonal (Fib 50–61.8%) · C Ending Diagonal (Wave 5 throw-under; preferred for M8) · D Two-Bar (limit at **50% of engulfing body**, volume Bar2 < Bar1) · E DBT + RSI divergence · F BOS + OB continuation.
- No trigger within expiry (per-trigger: A:20, B:30, C:sweep+3, D:next, E:15, F:first touch) → mark POI `STATE_TESTED`, expire order.

### L6 — Execution (Stage 4)
- **News gate:** if high-impact news ≤ 15 min → hard cancel all pending POI limits (Locked §11); re-arm after dust settles (~30 min).
- Lot sizing: `lots = (equity × risk%) / (sl_distance × tick_value)`, risk 0.5–1.0%.
- Order: limit with physical SL/TP on broker server. SL at structural sweep extreme ± 0.3× ATR; TP structural or 4× ATR cap.
- Emit `order.placed` / `order.cancelled` / `order.filled`.

### L7 — Trade Management (Stage 5)
- PureRunner: no early partials; SL→BE at 1.0× ATR favorable; 100% runs to structural TP.
- FVG invalidation: candle close beyond FVG boundary = hard exit.
- Circuit breaker: 3 consecutive losses → 4h pause.
- Same-level guard: failed sweep level → 4-bar cooldown on re-entry.
- Friday EOD: force-close 20:00 UTC Friday.
- Emit `trade.closed` (ticket, pnl, reason) and update all POI freshness states.

---

## 4. Communication Contracts (event schemas)

| Event | Emitted By | Payload (JSON) |
|-------|-----------|----------------|
| `bar.closed` | L0 | `{event_id, symbol, tf, ts, o, h, l, c, vol, atr}` |
| `tick.quote` | L0 | `{event_id, symbol, ts, bid, ask, atr}` — drives L7 management only |
| `news.flash` | L0 | `{event_id, name, impact, ts_scheduled}` |
| `liquidity.sweep` | L1 | `{event_id, level_id, level_type, direction: BSL|SSL, price, sweep_extreme, tf, ts, bar_close_ts, source}` — `sweep_extreme` = the wick extreme of the sweep candle (Head), required by L6 for SL anchor & lot sizing without secondary queries |
| `displacement.confirmed` | L2 | `{event_id, sweep_id, atr_mult, bos_price, fvg_top, fvg_bottom, impulse_origin, bos: bool, fvg: bool}` — geometry fields so L3/L4 compute zone refinement & entries without re-querying bars |
| `swing.invalidated` | L2 | `{event_id, sweep_id, reason}` |
| `poi.classified` | L3 | `{event_id, poi_id, tags: ["M1".."M8"], choch_rule: 1|2|3, level_hi, level_lo, detection_tf, score_tags}` |
| `poi.validated` / `poi.rejected` | L4 | `{event_id, poi_id, pillars: {p1..p5}, score, reason?}` |
| `trigger.armed` | L5 | `{event_id, poi_id, triggers: ["A".."F"]}` |
| `trigger.fired` | L5 | `{event_id, poi_id, trigger, price, expiry_bars}` |
| `order.placed` / `order.cancelled` / `order.filled` | L6 | `{event_id, poi_id, order_id, side, price, sl, tp, lots}` |
| `trade.closed` | L7 | `{event_id, ticket, poi_id, pnl, rr, reason, ts}` |
| `poi.state` | L4/L5/L7 | `{poi_id, from, to: CREATED|FRESH|TESTED|VIOLATED}` |
| `heartbeat` | ALL | `{level, ts, processed, lag_ms}` |

Every consumer acknowledges by `event_id`; the bus redelivers only unacked events.

---

## 5. State Store (single source of truth)

| Key Pattern | Contents |
|-------------|----------|
| `liq:{level_id}` | level type, price, direction pool, status (fresh/consumed), tf |
| `poi:{poi_id}` | tags, boundaries, detection_tf, state machine, pillars, score, expiry |
| `poi:{poi_id}:triggers` | armed triggers, first-valid result |
| `cooldown:{level_id}` | same-level guard expiry timestamp |
| `breaker:{account}` | consecutive loss count, pause-until timestamp |
| `orders:{poi_id}` | broker order id, status |
| `partition:{sym}:{tf}:{level}` | event cursor (ordering watermark) |

POI state machine (Locked §5):
```
STATE_CREATED → STATE_FRESH → STATE_TESTED (1st touch — terminal)
STATE_CREATED → STATE_FRESH → STATE_VIOLATED (closed beyond without touch)
Unfilled limit expiry after N bars (M5=12, M1=30) ⇒ mark STATE_TESTED
```

All state transitions are **atomic** via a Redis Lua CAS script — the strict 1-touch law (Locked §5) must be race-proof under concurrent sweep/tick events:

```lua
-- Atomic Freshness Lock: only the FIRST touch may transition STATE_FRESH -> STATE_TESTED
if redis.call('HGET', KEYS[1], 'status') == 'STATE_FRESH' then
    redis.call('HSET', KEYS[1], 'status', 'STATE_TESTED', 'tested_at', ARGV[1])
    return 1
else
    return 0 -- Rejected: double touch or depleted volume
end
```

Same CAS pattern guards the same-level guard cooldown (`cooldown:{level_id}`) and the circuit breaker counter (`breaker:{account}`).

---

## 6. Ordering, Concurrency & "Best Possible Results"

- **Two-tier partitioning** (fixes multi-TF race conditions, e.g. Model 8's D1/H4 → M5 → M1 flow):
  - **Tier 1 (bar feed):** partition by `{symbol}` only — time-ordered `bar.closed` / `tick.quote` for every timeframe share one lane per symbol, so chronological ordering (Locked §12) is trivially correct across timeframes.
  - **Tier 2 (post-discovery):** from L4 onward, partition by `{symbol, poi_id}` — every event touching a specific POI (pillars, triggers, orders, management) lives on the same lane, so cross-timeframe stages (e.g. H4 zone discovery + M1 trigger for M8) cannot race each other.
  - L1–L3 may parallelize across symbols/timeframes/levels; L4–L7 are serialized per `{symbol, poi_id}`.
- **Concurrency:** L1–L4 can parallelize across different levels/timeframes; only L5 trigger resolution and L6 execution are serialized per POI.
- **Signal quality pipeline (what gets printed):**
  1. Only POIs that pass every hard gate (P1–P4) reach the output layer.
  2. Signals are **ranked**: 3+ tags (institutional-grade) → 2 tags (elevated) → 1 tag (base).
  3. Within a rank, chronological first-valid trigger wins.
  4. Every signal carries its reason trail (tags → pillars → trigger) so results are explainable and back-testable.
  5. Zero-lag sweep levels are marked "consumed" (smart-money edge, Locked §2.7) so the same level is never re-hunted by the system.

---

## 7. Failure Modes & Watchdog

| Failure | Behavior |
|---------|----------|
| Consumer behind (lag > threshold) | Buffer per partition + `lag.alert`; no silent drops |
| Duplicate event | Dedup by `event_id`; idempotent consumers |
| MT5 bridge down | L0 heartbeats stop → all stages idle-safe; no stale signals |
| Broker rejects order | `order.rejected` → POI released for re-trigger if freshness allows |
| News within 15 min | L6 hard-cancels; L1–L5 continue classifying but nothing executes |
| 3 consecutive losses | Circuit breaker pauses L5/L6 for 4h (L0–L4 keep running) |
| Friday ≥ 20:00 UTC | L7 closes all positions; L6 blocks new orders |

---

## 8. Latency Budget

The budget is **split** — internal decision latency is deterministic and auditable; broker transmission is infrastructure-dependent and must not be conflated with pipeline quality.

### Internal Decision Pipeline (per bar-close event — deterministic, zero-polling)

| Step | Budget |
|------|--------|
| MT5 → L0 publish | ≤ 5 ms |
| L0 → L1 sweep eval | ≤ 5 ms |
| L1 → L2 displacement/swing | ≤ 5 ms |
| L2 → L3 classify | ≤ 5 ms |
| L3 → L4 pillars | ≤ 5 ms |
| L4 → L5 trigger arming | ≤ 5 ms |
| L5 → L6 order dispatch (OrderSend call) | ≤ 5 ms |
| **Internal decision pipeline total** | **≤ 35 ms** |

### Broker Transmission & Execution (infrastructure-dependent)

| Leg | Budget |
|-----|--------|
| OrderSend network RTT (VPS near broker: Equinix LD4-class) | ≤ 20 ms |
| Remote VPS / long-haul RTT | 20–180 ms |

### Total (bar close → broker ACK)
- **Best case (VPS co-located with broker):** ≤ 55 ms
- **Budgeted target:** ≤ 100 ms end-to-end (internal ≤ 35 ms + broker leg ≤ 70 ms)
- `tick.quote` → L7 management reaction: ≤ 5 ms (PureRunner BE/trailing must fire on tick, not bar close)

*All rules above are locked; this document only defines *how* they communicate. Any conflict with `LOCKED_DECISIONS.md` resolves in favor of the locked file.*