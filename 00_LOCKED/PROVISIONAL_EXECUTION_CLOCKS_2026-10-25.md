# PROVISIONAL Execution Clocks — 2026-10-25

**Authority:** Lead Architect, 2026-10-25  
**Evidence class:** PROVISIONAL DEMO OPS — pending measurement; forward-demo
only; not expectancy-locked. This ruling makes no Monte Carlo, SQN, PF, or
multi-regime performance claim.

## Scope and prohibition

This is a sequential state rule for the future multi-timeframe sweep episode
layer. It does not alter lot sizing, spread, TP/SL, locked risk constants,
zone gates, or the §5a seek/scan redesign. Parallel primary and boundary
fallback handling is forbidden.

| Phase | Starts at | Duration | Outcome at deadline |
| --- | --- | --- | --- |
| `IN_ZONE_PRIMARY` | first in-zone penetration/touch of the POI (`zone_entry_bar`) | 6 bars of that episode's confirmation timeframe (`TF_C`) | `EXPIRED_NO_ENTRY`; then enable `BOUNDARY_FALLBACK` only |
| `BOUNDARY_FALLBACK` | completed POI boundary-sweep bar (`sweep_print_bar`) | 16 bars of `TF_C` | `EXPIRED_SWEEP_TIMEOUT` |

Structural invalidation outranks either clock and emits
`INVALIDATED_STRUCTURE`. Parent/execution give-up may terminate the episode
earlier when already wired; it does not extend either provisional clock.

Required status labels: `IN_ZONE_PRIMARY`, `BOUNDARY_FALLBACK`,
`EXPIRED_NO_ENTRY`, `EXPIRED_SWEEP_TIMEOUT`, `INVALIDATED_STRUCTURE`.

## Dual-confirmation clock owner (approved 2026-10-25)

Each episode has exactly one clock owner: its **finer eligible confirmation
timeframe**. This is an operational clock only; the coarser stream remains
eligible to win the confirmation race.

| Source | Eligible confirmation streams | Single clock owner |
| --- | --- | --- |
| D1 | H1 | H1 |
| H4 | M5, M15 | M5 |
| H1 | M1, M5 | M1 |
| M15 | M1 | M1 |

## Survey conflict and implementation boundary

The current Essence V1 runner already expires a zone-sweep setup after 30 M1
bars (`ESSENCE_LIMIT_EXPIRY_BARS`), and its signed contract explicitly leaves
the fallback boundary-sweep family **include later**. This ruling therefore
does not overwrite Essence V1's 30-bar behavior. The current complex path
uses a 20-M5-bar seek span anchored to `arm_bar`, not to a sweep. Neither path
currently implements the required sequential primary/fallback state machine.

**Dated implementation selection (owner, 2026-10-25):** isolated DUMB-MTF is
the demo path; the baseline DUMB runner is comparison-only and Essence V1 and
COMPLEX remain untouched. `smc/dumb/mtf.py` implements these clocks and
`smc/dumb/mtf_paper_adapter.py` feeds a winner into the existing PaperRunner
risk/order path. The adapter accepts closed external events only; the H4
source feed and operator selection are specified below.

**H4 live slice completed (2026-10-25):** `smc/dumb/mtf_h4_feed.py` reads
only completed H4 M8 POIs and completed M5/M15 bars. It starts primary on the
first M5 range touch, but, by owner clarification, requires a later qualifying
wick-through/close-back sweep before a primary confirmation can order; that
real sweep wick is the DUMB stop anchor. `strategy_mode: "DUMB_MTF_H4"` opts
the operator into this isolated H4→M5/M15 demo path. D1/H1/M15 source rows
remain registered but are not enabled: no source emitter was invented.

`LOGIC_CHANGED: YES — isolated DUMB-MTF only`
`LOCKED_CONSTANTS_CHANGED: NO`
