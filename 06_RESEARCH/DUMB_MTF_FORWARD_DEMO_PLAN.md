# DUMB-MTF Forward Demo Plan — 2026-10-25

## Current demo scope

Run only `DUMB_MTF_H4` for approximately one market week.

- Source POI: closed H4 M8 emission.
- Episode clock: M5.
- Confirmation race: closed M5 and M15; earliest valid event wins, M5 wins an exact-time tie.
- Sequence: first zone touch → six M5-bar primary → boundary fallback only after primary expiry → sixteen M5-bar fallback.
- Primary entry requires a real wick-through/close-back sweep before confirmation; that wick anchors the DUMB stop.
- Existing PaperRunner risk/order/management path remains in force.
- Baseline DUMB is comparison-only; Essence V1 and COMPLEX are not run by this demo config.

## What to review after the week

Count and inspect the closed event chain:

`touch → qualifying sweep → primary/fallback → confirmation TF → candidate → risk/order result → trade outcome`.

Review M5 versus M15 winners, primary versus fallback usage, timeout and invalidation reasons, same-direction concurrent orders from distinct episodes, and blocked/rejected candidates. This is operational observation only—not a PF, expectancy, SQN, or promotion test.

## Deferred policy intent

The registered policy table remains the intended expansion surface:

| Source | Confirmation streams | Clock owner | Status |
| --- | --- | --- | --- |
| D1 | H1 | H1 | Deferred: D1 source/feed leg not enabled |
| H4 | M5, M15 | M5 | Enabled for forward demo |
| H1 | M1, M5 | M1 | Deferred: no approved H1 source-POI emitter |
| M15 | M1 | M1 | Deferred: no approved M15 source-POI emitter |

After the demo review, decide one row at a time whether its expected additional
observations justify a dedicated source-emitter design. No deferred row may be
enabled by substituting generic liquidity sweeps or inventing zone geometry.

`FORWARD_DEMO_STATUS: READY`  
`NEXT_DECISION: review one-week DUMB_MTF_H4 evidence before expanding policy rows`
