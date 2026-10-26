# Multi-Timeframe Sweep Episodes — Design

## Status

Approved design for implementation planning.  This is a **parallel, policy-driven
execution layer**; it does not change the frozen Essence or existing complex
strategy semantics until explicitly wired into a selected runtime.

## Purpose

Turn a closed POI sweep into an independently traceable execution episode.  Each
episode races only its eligible lower-timeframe confirmation streams, permits one
winning trade, and then passes that candidate through the existing risk and order
path.  The demo profile is intentionally high-observation: it allows concurrent
same-direction orders when they originate from distinct, validated source
timeframes/levels.

## Policy table

| Source sweep TF | Eligible confirmation TFs |
| --- | --- |
| D1 | H1 |
| H4 | M5, M15 |
| H1 | M1, M5 |
| M15 | M1 |

Only a **closed** source candle can create an episode.  Only closed confirmation
candles may win.  A bar may have multiple roles: for example, a closed H1 bar
can confirm a D1 episode and independently create an H1-sweep episode.

## Episode identity and lifecycle

`SweepEpisode` is immutable at creation and is identified by:

`(symbol, direction, source_tf, poi_id or swept-level identity, closed_sweep_timestamp)`.

The coordinator suppresses only an identical identity.  It must not merge or
replace a later valid sweep solely because it has the same direction or source
timeframe.  Distinct POI/level plus distinct closed sweep timestamp means a
distinct episode.  Each episode records source evidence, allowed confirmation
timeframes, elapsed-time expiry, state, and terminal reason.

Terminal states are: `won`, `expired`, `invalidated`, `risk_cancelled`, and
`execution_cancelled`.  A successful winner permits one candidate/order only;
M5 and M15 (or M1 and M5) cannot both trade for that same episode.

## Confirmation arbitration

The coordinator invokes the existing deterministic trigger scanner separately
for each policy-allowed confirmation stream.  It owns arbitration across streams:

1. The first valid confirmation on a completed candle wins the episode.
2. If two streams become observable at the same instant, use a documented,
   deterministic tie-break (initially: lower timeframe, then stable route ID).
3. Once a winner is accepted, close the other confirmation subscriptions.

No trigger geometry is duplicated.  The existing trigger engine/router remains
the sole evaluator inside each stream.

## Demo execution profile

The demo profile disables strategy-level daily-trade caps, same-direction
portfolio suppression, and one-order-per-symbol/direction suppression for these
episodes.  It permits concurrent same-direction orders from distinct valid
episodes, including separate H4 and H1 episodes.

It retains hard operational safety: completed-bar gating, valid price/volume,
broker/order-state acceptance, stable idempotency, and a configurable emergency
ceiling for active and pending orders.  This ceiling is a fault containment
guard, not a signal-quality filter.  Each candidate and order carries
`sweep_episode_id`, source TF, POI/level identity, sweep timestamp, confirmation
TF, route ID, and a sequence label for later early-versus-late analysis.

## Runtime integration

The layer sits above `TriggerRouter`/pipeline route evaluation and before the
existing risk/order adapters.  It shares the current paper, replay, and live
execution paths.  MQL5 remains watchdog/chart/safety infrastructure; it is not
a second strategy engine.

Implementation starts with **H4 → M5/M15**.  The generic coordinator must not
assume that choice: the remaining rows are enabled by policy additions only once
the first slice passes replay and paper checks.

## Verification

Focused tests must cover closed-source rejection of forming bars, identity
deduplication, multiple same-source episodes, H4/H1 concurrency, M5-vs-M15 and
M1-vs-M5 arbitration, exact-timestamp ties, expiry/invalidation, one-winner
enforcement, relaxed-demo admission, hard-guard rejection, restart/idempotency,
and replay/paper/live provenance parity.

Forward-demo output must make every episode and decision observable, including
why a valid-looking episode did not trade.
