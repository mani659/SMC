# Provisional Execution Clocks — Survey and Registration

**Date:** 2026-10-25  
**Authority:** Lead Architect  
**Class:** PROVISIONAL DEMO OPS; forward-demo only; no expectancy or PF claim.

## Plain-language answers

**Q1 — fallback timing.** On first in-zone touch, the engine watches only the primary confirmation path for six bars of the episode's confirmation timeframe. If it does not produce an entry, primary expires and only then may boundary fallback start. Primary and fallback never run in parallel.

**Q2 — sweep-to-confirmation lifetime.** A completed boundary sweep starts a 16-bar window in the episode's confirmation timeframe. Structural invalidation wins immediately. A pre-existing parent/execution give-up may end the episode earlier, but cannot prolong the 16-bar window.

| Item | Registered value |
| --- | --- |
| Gap 1 start | `zone_entry_bar` (first in-zone penetration/touch) |
| Gap 1 clock | 6 `TF_C` bars |
| Gap 1 expiry status | `EXPIRED_NO_ENTRY` |
| Gap 2 start | `sweep_print_bar` (closed boundary sweep) |
| Gap 2 clock | 16 `TF_C` bars |
| Gap 2 expiry status | `EXPIRED_SWEEP_TIMEOUT` |
| Structural stop | `INVALIDATED_STRUCTURE` |
| Primary/fallback | sequential only; parallel forbidden |

## Code survey

| Gap | Status | Evidence | Finding |
| --- | --- | --- | --- |
| Gap 1: in-zone wait then fallback | PARTIAL | `smc/backtest/pipeline_adapter.py:_may_route`; `smc/orchestration/engine.py:scan_route`; `smc/essence/runner.py` | Complex has an in-zone/arm seek but no separate six-`TF_C` counter or fallback-state transition. Essence has zone sweep/confirm logic but no in-zone primary-versus-boundary fallback state. |
| Gap 2: sweep-to-confirm expiry | PARTIAL | `smc/essence/runner.py:run`; `smc/essence/constants.py:ESSENCE_LIMIT_EXPIRY_BARS`; `smc/triggers/trigger_expiry.py:poi_give_up_bars` | Essence expires a sweep setup after 30 M1 bars. Complex uses 20 M5 bars from `arm_bar`, not the sweep. Neither is the requested generic 16-`TF_C` episode clock. |

## Conflicts (reported; not overwritten)

1. **Essence V1:** `ESSENCE_LIMIT_EXPIRY_BARS = 30` M1 bars, whereas the provisional Gap 2 clock is 16 `TF_C` bars. The 30-bar Essence behavior is existing, clear, and signed; it remains unchanged.
2. **Essence V1 contract:** boundary fallback is explicitly “include later,” so adding it to Essence would exceed the signed V1 scope.
3. **Complex path:** §5a keeps a 20-M5-bar scan span from `arm_bar`; it is not a sweep-started timer and cannot be relabelled as the provisional clock.

## DUMB-MTF implementation update

The owner selected the isolated DUMB-MTF path for demo. `smc/dumb/mtf.py`
implements the registered state machine, and `smc/dumb/mtf_paper_adapter.py`
uses the existing PaperRunner candidate/risk/order shell without altering its
locked constants. The adapter takes only already-closed POI-zone touch,
boundary-sweep, and confirmation events; a same-close M5/M15 or M1/M5 race
is sorted by the finer timeframe before one candidate is made.

The H4→M5/M15 event-producing slice is now connected. It reads only completed
H4 M8 POIs and completed confirmation bars, and the operator selects it only
with `strategy_mode: "DUMB_MTF_H4"`. Owner clarification closes the stop
anchor ambiguity: a primary must first print a real wick-through/close-back
sweep; that wick becomes its stop anchor, and cannot confirm itself. D1/H1/M15
source rows remain intentionally unwired because no source emitter was defined.

## Decision and next step

**Recommendation: B (H4 slice complete) — forward-demo observe.** The same
runner shell now consumes a DUMB-MTF H4 winner without changing Essence or
COMPLEX. Do not add the other source rows by inference; collect episodes and
orders from this explicit H4 slice first.

If the operator remains without armed POIs, the clocks will create no trades; structure/POI availability is upstream of either clock.

`LOGIC_CHANGED: YES — isolated DUMB-MTF only`
`LOCKED_CONSTANTS_DIFF: empty`  
`CODE_IMPLEMENTED: YES — H4→M5/M15 slice; other source rows intentionally NO`
