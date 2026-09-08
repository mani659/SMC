# N8N Workflow Prompt — SMC Zero-Lag Event-Driven Pipeline

**How to use:** Paste the prompt below (the block between `--- PROMPT START ---` and `--- PROMPT END ---`) into the N8N AI workflow builder (or use it as the specification to hand-build the workflow). Then compare the generated workflow against `SMC_RESEARCH/SMC_WORKFLOW_ORCHESTRATION.md` — my canonical design.

---

```text
--- PROMPT START ---

Build an n8n workflow named "SMC Zero-Lag Event-Driven Pipeline" for an institutional
Smart Money Concepts (SMC) trading system on XAUUSD (Gold). The workflow must be
EVENT-DRIVEN (webhook push, never polling), with each pipeline stage as a separate
sub-workflow that communicates with the others through a shared event stream and a
Redis state store. Latency targets: internal decision pipeline <= 35 ms;
total bar-close to broker ACK <= 100 ms (broker RTT is infrastructure-dependent,
budgeted separately - typical 20-180 ms: ~20 ms co-located VPS, up to ~180 ms
long-haul - never conflated with pipeline quality). Produce the best
possible signal output: only fully validated POIs, ranked by confluence score,
with a full reason trail for every signal.

## INPUTS (Webhook triggers only)

1. Webhook "MT5 Bar Closed" (from a Python MetaTrader5 bridge):
   JSON { event_id, symbol, tf, ts, o, h, l, c, vol, atr }
   Published for timeframes D1, H4, H1, M30, M5, M1. Drives L1-L5 and FVG
   invalidation only - sweeps and BOS must be evaluated on finalized bars, never
   intra-bar.
2. Webhook "Tick Quote": JSON { event_id, symbol, ts, bid, ask, atr }
   Published on every tick. Drives L7 trade management ONLY (PureRunner SL to
   breakeven at +1.0x ATR and real-time exits must react to ticks, not wait for
   a bar close).
3. Webhook "News Flash": JSON { event_id, name, impact, ts_scheduled }
   High-impact events: US CPI, NFP, FOMC (pushed at least 30 min ahead).
4. Webhook "Order Execution": JSON { event_id, order_id, poi_id, status }
   status = filled | rejected | cancelled | closed.

## ARCHITECTURE (one sub-workflow per level, all connected via the event stream)

- L0 Data Ingest: receives the three webhooks, normalizes payloads, publishes to
  the event stream with dedup key event_id.
- L1 Liquidity & Sweep Engine: on each bar close, evaluates the SIX locked
  liquidity types and publishes "liquidity.sweep" when a sweep occurs. The sweep
  payload MUST include sweep_extreme (the wick extreme of the sweep candle /
  Head), because L6 needs it for the SL anchor (sweep extreme +/- 0.3x ATR) and
  lot sizing without secondary bar queries:
    1. Session Highs/Lows (Asia 00:00-07:00, London 07:00-13:00, NY 13:00-20:00 UTC)
    2. PDH/PDL and PWH/PWL
    3. EQH/EQL on BOTH top (BSL) and bottom (SSL), tolerance <= 4.5 pips on XAUUSD
    4. Structural Swing High/Low only (Base Candle validity gate; ignore minor noise)
    5. POI sweeps: any Order Block (OB) or Fair Value Gap (FVG) boundary sweep at a
       POI counts as a liquidity sweep
    6. Demand/Supply and OB boundary fallback sweeps: if no in-between entry inside
       the zone, the sweep of the zone extreme is the event
   Sweep rule: wick pierces the level AND candle body closes back inside. Emit
   direction BSL or SSL. Mark swept levels "consumed" (smart money has eaten retail
   stops; the market will NOT return to re-hunt swept levels).
- L2 Displacement & Swing Validation: on sweep, require displacement of at least
  1x ATR plus BOS (close beyond prior swing) plus FVG (3-candle imbalance).
  Hard fail if displacement < 0.5x ATR. Then validate the swing via the Base
  Candle gate: a swing is only valid if price breaks the Base Candle's OPPOSITE
  extreme AND closes beyond it; wick-only or two-bar-reversal-only = invalid swing,
  no POI. Bearish exception: the next candle's wick may create the low and the
  bearish candle remains the Base Candle.
- L3 POI Classification (modular, NO priority hierarchy): label the level with ALL
  matching tags M1-M8 as EQUAL tags - never suppress a tag:
    M1 Origin Demand/Supply Base
    M2 RBS/SBR Breaker
    M3 CHOCH Retest (sub-classify Rule 1 Standard / Rule 2 Inside Body / Rule 3
       Inside Wick - Rule 3 is KEPT at lowest strength, no extra confluence gate)
    M4 Quasimodo QML (full wick range [left_shoulder_low, high])
    M5 Extreme Equal Highs (CONTINUATION setup, entry at broken equal level;
       distinguished from M7 reactive shelf)
    M6 Neckline / Double Top-Bottom
    M7 Equal Resistance Shelf (reactive)
    M8 HTF Demand/Supply (D1/H4 zones = last opposing candle before impulse,
       full body + wicks; M5 approach, M1 trigger; +10% bonus if D1 and H4 zones
       overlap; SL 2-5 pips, RR 1:5+)
   Confluence score: 1 tag = base quality, 2 tags = elevated, 3+ = institutional.
   CHOCH entry placement: at the broken structural level, NOT the origin OB.
- L4 Validation (5 Pillars) - pillars 1-4 HARD reject, pillar 5 soft:
    P1 Zone refinement: unmitigated OB/FVG within +/-0.5x ATR of the POI
       (reject naked levels: a POI with no OB/FVG inside the tolerance is
       invalid)
    P2 Displacement: BOS + FVG + >= 1x ATR
    P3 Premium/Discount: coupled to the POI detection timeframe; buys < 45% of the
       dealing range, sells > 55%; 45-55% = REJECT (equilibrium trap)
    P4 Freshness: strict 1-touch only (STATE_FRESH -> STATE_TESTED, terminal).
       Unfilled limit orders expire after N bars (M5=12, M1=30) AND mark the POI STATE_TESTED.
    P5 Inducement: soft score only - 100% with inducement, 70% without, never reject
  Emit poi.validated (with pillar results + score) or poi.rejected (with reason).
- L5 Trigger Routing: on validated POI, drop to M1/M5 and arm compatible triggers
  A-F. CHRONOLOGICAL first-valid trigger wins (not priority-based). Triggers:
    A CHOCH (body close)  B Leading Diagonal (Fib 50-61.8%)
    C Ending Diagonal (Wave 5 throw-under; preferred for M8)
    D Two-Bar Reversal (LIMIT order at 50% of engulfing body; volume Bar2 < Bar1)
    E Double Top/Bottom + RSI divergence  F BOS + OB continuation
  No trigger within the expiry window -> mark POI STATE_TESTED.
- L6 Execution: if high-impact news is within 15 minutes -> HARD CANCEL all pending
  POI limit orders (re-arm after ~30 min). Lot sizing:
  lots = (equity * risk%) / (sl_distance * tick_value), risk 0.5-1.0%. Place LIMIT
  orders with physical SL/TP on the broker. SL at structural sweep extreme +/- 0.3x
  ATR; TP at structural target or 4x ATR cap.
- L7 Trade Management: PureRunner (no early partials; SL to breakeven at 1.0x ATR;
  100% runner to structural TP); FVG invalidation = hard exit if a candle closes
  beyond the FVG boundary; circuit breaker = pause 4h after 3 consecutive losses;
  same-level guard = 4-bar cooldown before re-entering a failed sweep level;
  Friday EOD = force-close all positions at 20:00 UTC Friday.

## STATE & MESSAGING REQUIREMENTS

- Use a Redis node set as the shared state store with these key patterns:
  liq:{level_id}, poi:{poi_id}, poi:{poi_id}:triggers, cooldown:{level_id},
  breaker:{account}, orders:{poi_id}.
- POI state machine: STATE_CREATED -> STATE_FRESH -> STATE_TESTED (terminal);
  STATE_FRESH -> STATE_VIOLATED if closed beyond without touch.
- Two-tier partitioning: (1) bar feed partition by {symbol} only, so
  time-ordered bar.closed / tick.quote events across ALL timeframes share one
  lane and chronological trigger selection is correct; (2) post-discovery
  partition by {symbol, poi_id} for L4-L7, so cross-timeframe stages (e.g. H4
  zone discovery + M1 trigger for Model 8) never race. Dedup every event by
  event_id (idempotent consumers). If a stage falls behind, buffer per partition
  and emit a lag alert - never silently drop events.
- Enforce the strict 1-touch freshness law ATOMICALLY with a Redis Lua
  compare-and-swap script: only the first touch may transition
  STATE_FRESH -> STATE_TESTED (a second concurrent touch must be rejected). Use
  the same CAS pattern for the same-level cooldown and the circuit-breaker
  counter.

## OUTPUTS

1. Webhook/Telegram "Signal Feed": only fully validated POIs, ranked 3+ tags first,
   then 2 tags, then 1 tag; each signal carries {poi_id, tags[], score, direction,
   entry, sl, tp, trigger, reason_trail}.
2. Webhook/Telegram "Trade Ticket": on trigger.fired + execution, include order id,
   side, lots, sl, tp.
3. Webhook "Audit Log": every event with event_id for replay and backtesting.
4. Health monitor: heartbeat per level {level, ts, processed, lag_ms}.

## CONSTRAINTS

- Do NOT introduce any model priority hierarchy: all 8 tags are equal; more tags =
  higher score; no tag suppresses another.
- Detection timeframes: Daily = Macro, H4 = Primary, H1 = all models, M30 =
  Intraday; Model 8 uses D1/H4 zones with M5 approach and M1 execution.
- News protocol: US CPI, NFP, FOMC only; hard cancel 15 minutes before.
- Strict 1-touch freshness; no second-touch trades.
- Return the workflow with: (1) the node graph structure, (2) the JSON schema for
  each webhook input/output, (3) the Redis key layout, (4) the sub-workflow
  boundaries, and (5) any nodes needed for dedup, ordering, and the health monitor.

--- PROMPT END ---
```

---

## Comparison Checklist (my design vs N8N's output)

| Aspect | Check |
|--------|-------|
| Event-driven push (no polling) | ☐ N8N uses webhook triggers only |
| Levels L0–L7 as sub-workflows | ☐ One sub-workflow per level |
| Redis state store with the key patterns | ☐ Present |
| Dedup by `event_id` | ☐ Present |
| Per-partition ordering for chronological triggers | ☐ Present |
| All 6 liquidity types incl. POI/fallback sweeps | ☐ Present |
| All 5 pillars (P1–P4 hard, P5 soft) | ☐ Present |
| Modular equal tags M1–M8, no hierarchy | ☐ Present |
| 6 triggers, chronological first-valid | ☐ Present |
| News hard-cancel 15 min | ☐ Present |
| 1-touch freshness + expiry | ☐ Present |
| Outputs: ranked signal feed + trade ticket + audit + health | ☐ Present |
| Internal pipeline ≤ 35 ms; bar-close → broker ACK ≤ 100 ms (broker RTT separate) | ☐ Present |
| `tick.quote` stream drives L7 (PureRunner BE on tick, not bar close) | ☐ Present |
| `sweep_extreme` present in `liquidity.sweep` payload | ☐ Present |
| Two-tier partitioning: `{symbol}` bar feed + `{symbol, poi_id}` post-discovery | ☐ Present |
| Atomic CAS (Redis Lua) for 1-touch freshness | ☐ Present |