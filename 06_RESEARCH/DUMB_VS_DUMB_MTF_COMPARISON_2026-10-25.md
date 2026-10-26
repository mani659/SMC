# DUMB vs DUMB-MTF — Detailed Comparison Probe

**Date:** 2026-10-25  
**Authority:** Lead Architect / owner session  
**Mode:** Read-only evidence reconstruction. No source, config, or constants were changed.

## Inventory

| Path | Role | First appears (commit/date) | Live-wired? |
|---|---|---|---|
| [`04_SRC/smc/dumb/__init__.py`](../04_SRC/smc/dumb/__init__.py) | Package exports for DUMB rules/constants and, after the MTF addition, the MTF public surface. | `e10fe66` / 2026-10-22; MTF export updated 2026-10-25 | Baseline no; MTF used by live path |
| [`04_SRC/smc/dumb/runner.py`](../04_SRC/smc/dumb/runner.py) | Baseline `run_dumb_flowchart` M5 research/backtest loop; M8 zone feed, one sweep/confirm/trade state per POI. | `e10fe66` / 2026-10-22 | No |
| [`04_SRC/smc/dumb/rules.py`](../04_SRC/smc/dumb/rules.py) | Shared sweep, confirm, expiry and SL/TP functions. | `e10fe66` / 2026-10-22 | Baseline via runner; MTF via adapter/feed |
| [`04_SRC/smc/dumb/constants.py`](../04_SRC/smc/dumb/constants.py) | Baseline-owned 12-bar confirmation expiry, 0.10 ATR stop buffer, 2R target and ATR(14). | `e10fe66` / 2026-10-22 | Baseline yes; MTF imports shared SL/TP function |
| [`04_SRC/smc/dumb/types.py`](../04_SRC/smc/dumb/types.py) | Baseline `DumbTrade` backtest record. | `e10fe66` / 2026-10-22 | No |
| [`04_SRC/tests/test_dumb_flowchart.py`](../04_SRC/tests/test_dumb_flowchart.py) | Baseline rule, runner and isolation tests. | `e10fe66` / 2026-10-22 | No |
| [`06_RESEARCH/DUMB_FLOWCHART_V1_DESIGN.md`](DUMB_FLOWCHART_V1_DESIGN.md) | Baseline DUMB design lock and rule definitions. | `e10fe66` / 2026-10-22 | No |
| [`06_RESEARCH/DUMB_FLOWCHART_V1_IMPLEMENTATION_NOTE.md`](DUMB_FLOWCHART_V1_IMPLEMENTATION_NOTE.md) | Baseline implementation and explicit no-live/no-promotion status. | `e10fe66` / 2026-10-22 | No |
| [`04_SRC/smc/orchestration/sweep_episode_coordinator.py`](../04_SRC/smc/orchestration/sweep_episode_coordinator.py) | Generic closed-source sweep episode identity, expiry and confirmation arbitration. | `b835710` / 2026-10-25 | No; isolated |
| [`04_SRC/smc/dumb/mtf.py`](../04_SRC/smc/dumb/mtf.py) | DUMB-MTF policy table and sequential 6/16-bar episode state machine. | `5ca7a1d` / 2026-10-25 | Yes, through the H4 feed |
| [`04_SRC/smc/dumb/mtf_paper_adapter.py`](../04_SRC/smc/dumb/mtf_paper_adapter.py) | Adapts one winning closed confirmation to one existing `CandidateEntry`/PaperRunner submission. | `ef3e8fe` / 2026-10-25 | Yes, H4 mode |
| [`04_SRC/smc/dumb/mtf_h4_feed.py`](../04_SRC/smc/dumb/mtf_h4_feed.py) | Closed H4 M8 POIs plus M5/M15 touch, sweep and confirmation event feed. | `d013018` / 2026-10-25 | Yes, H4 mode |
| [`04_SRC/smc/live/loop.py`](../04_SRC/smc/live/loop.py) | Selects DUMB-MTF feed dispatch and filters forming bars on that path. | `d013018` / 2026-10-25 | Yes, when explicitly selected |
| [`04_SRC/smc/live/run_operator.py`](../04_SRC/smc/live/run_operator.py) | Selects DUMB-MTF adapter/feed instead of the COMPLEX pipeline adapter. | `d013018` / 2026-10-25 | Yes, when explicitly selected |
| [`04_SRC/smc/live/operator_config.py`](../04_SRC/smc/live/operator_config.py) | Validates `COMPLEX` and `DUMB_MTF_H4`; requires M5 execution for H4 mode. | `d013018` / 2026-10-25 | Yes |
| [`config/live_demo.json`](../config/live_demo.json) | Current demo operator profile; explicitly selects H4 DUMB-MTF. | `d013018` / 2026-10-25 | Yes when this profile is passed to operator |
| [`config/live_tester.json`](../config/live_tester.json), [`config/live_console_dryrun.json`](../config/live_console_dryrun.json), [`config/ops_density_smoke.json`](../config/ops_density_smoke.json) | Other operator profiles; dry-run profiles do not explicitly select DUMB-MTF. | Present in repo; no DUMB-MTF selection found | Not DUMB-MTF by their current mode setting |
| [`00_LOCKED/PROVISIONAL_EXECUTION_CLOCKS_2026-10-25.md`](../00_LOCKED/PROVISIONAL_EXECUTION_CLOCKS_2026-10-25.md) | Authority/policy note: 6-bar primary, 16-bar fallback, sequential only; selects isolated DUMB-MTF for demo. | `f1e0f54` / 2026-10-25 | N/A |
| [`06_RESEARCH/PROVISIONAL_EXECUTION_CLOCKS_NOTE.md`](PROVISIONAL_EXECUTION_CLOCKS_NOTE.md) | Survey of prior clock differences and DUMB-MTF implementation boundary. | `f1e0f54` / 2026-10-25 | N/A |
| [`06_RESEARCH/DUMB_MTF_FORWARD_DEMO_PLAN.md`](DUMB_MTF_FORWARD_DEMO_PLAN.md) | H4 observation scope and post-run evidence review plan. | Untracked local note; first-appearance commit unavailable | N/A |
| [`docs/superpowers/specs/2026-10-25-multitimeframe-sweep-episodes-design.md`](../docs/superpowers/specs/2026-10-25-multitimeframe-sweep-episodes-design.md) | Generic episode design; H4→M5/M15 as the initial proposed slice. | `7e3d424` / 2026-10-25 | No; design only |

**Historical DUMB variants:** The dated code history shows one implemented baseline DUMB package: DUMB Flowchart V1, added by `e10fe66`. The MTF package is its later, separately wired demo path, not another pre-existing live DUMB runner. No evidence found that baseline DUMB was previously selected by the live operator. The implementation note explicitly says “no product flag was added” and “Live/EA: nothing live.” Therefore the request to identify the last baseline DUMB live/demo runner has no evidenced instance: **UNKNOWN / none found**. The current operator config history adds `DUMB_MTF_H4`, not a baseline-DUMB mode.

## Baseline DUMB

1. **Entry module / classes:** [`run_dumb_flowchart`](../04_SRC/smc/dumb/runner.py) is the runner. `M8LibraryZoneFeed` supplies `ZoneEntry` items, `_Pending` tracks a swept setup, and `DumbTrade` records results. The implementation note labels it “DUMB IMPLEMENTATION — DIAGNOSTIC — NOT EDGE.”
2. **Source structure/POIs:** `M8LibraryZoneFeed` filters to the M8 emitter's W1, D1 and H4 timeframes. It scans timestamp prefixes through the current M5 bar (`timestamp <= as_of`); its own documentation says the forming HTF bar is included. H1/M15/M5/M1 are not DUMB source-emitter timeframes.
3. **Confirmation / execution:** All loop bars and confirmations are M5. M5 is also the recorded `entry_idx` series. The first later M5 close through the zone midpoint can confirm.
4. **Sweep / stop:** `is_sweep` requires a wick beyond the POI extreme and a close back inside. The sweep bar starts the pending setup and its low (long) or high (short) anchors SL; a newer sweep while pending replaces the anchor and restarts the expiry. The confirmation bar itself cannot be the sweep bar.
5. **Clock / expiry:** `DUMB_CONFIRM_MAX_BARS = 12`, measured in M5 bars from the latest sweep, inclusive through sweep index + 12. A candidate expires after that. No touch-started primary phase or boundary-fallback phase is present in this baseline.
6. **Candidate / order path:** `run_dumb_flowchart` computes its own trade record and uses `evaluate_position_bar` for subsequent exit simulation. It does not create a `CandidateEntry`, attach to `PaperRunner`, or call a live order manager. Baseline DUMB is a research/backtest execution loop, not an operator order path.
7. **Config key:** No baseline-DUMB `strategy_mode` exists in the current operator config. `strategy_mode` defaults to `COMPLEX`; accepted values are only `COMPLEX` and `DUMB_MTF_H4`. Baseline invocation is via the DUMB capture/backtest runner, not an operator profile key.
8. **Runnable status:** The baseline runner and capture script remain usable for measurement/backtest. They are **not live-wired** and are explicitly described as not live in the implementation note. Active demo config uses DUMB-MTF instead.

Evidence: [`runner.py`](../04_SRC/smc/dumb/runner.py) module docstring, `M8LibraryZoneFeed`, `run_dumb_flowchart`; [`rules.py`](../04_SRC/smc/dumb/rules.py) `is_sweep`, `is_confirm`, `is_expired`, `compute_sl_tp`; [`constants.py`](../04_SRC/smc/dumb/constants.py); [`DUMB_FLOWCHART_V1_IMPLEMENTATION_NOTE.md`](DUMB_FLOWCHART_V1_IMPLEMENTATION_NOTE.md) §§1–2; [`DUMB_FLOWCHART_V1_DESIGN.md`](DUMB_FLOWCHART_V1_DESIGN.md) §§R1–R6.

## DUMB-MTF_H4

1. **Entry module / classes:** `DumbMtfStateMachine` in [`mtf.py`](../04_SRC/smc/dumb/mtf.py), `DumbMtfH4Feed` in [`mtf_h4_feed.py`](../04_SRC/smc/dumb/mtf_h4_feed.py), and `DumbMtfPaperAdapter` in [`mtf_paper_adapter.py`](../04_SRC/smc/dumb/mtf_paper_adapter.py). The operator constructs those only for `strategy_mode == "DUMB_MTF_H4"`.
2. **Source structure/POIs:** The live feed emits only H4 POIs, by running M8 over completed H4 candles. D1, H1 and M15-as-source policies appear in the policy registry but have no active source feed here; no other source emitter is constructed for this mode.
3. **Confirmation / execution:** Both closed M5 and closed M15 confirmation bars are eligible. M5 is the execution/poll timeframe and sole clock owner for H4 episodes. Earliest completion wins; equal-time races sort by finer timeframe first, so M5 beats M15, then route ID stabilizes ties. The feed computes the candidate entry at the confirmation close.
4. **Sweep / stop:** The H4 feed starts a primary episode on first M5 range-touch after price was outside. It requires a later wick-through/close-back sweep before either primary or fallback confirmation; the sweep bar does not confirm itself. Its low/high supplies the stop extreme. `compute_sl_tp` uses the DUMB-owned 0.10×M5 ATR(14) stop buffer and fixed 2R target. The baseline and MTF therefore share that SL/TP formula, though their event clocks and execution paths differ.
5. **Clock / expiry:** The provisional ruling is six M5 clock bars from first touch for `IN_ZONE_PRIMARY`. After primary expiry, only `BOUNDARY_FALLBACK` is allowed; a closed boundary sweep starts a 16-M5-bar fallback window. The state machine uses inclusive deadlines: expiry is applied when the next clock index is reached. Structural invalidation can terminate either active phase. H4 is the source; M5 is the single clock owner even though M15 is eligible to confirm.
6. **Candidate / order path:** The feed sends closed confirmation routes to `DumbMtfPaperAdapter`. The adapter accepts one episode winner, computes brackets, creates one `CandidateEntry`, queues it, and later submits it through `PaperRunner.submit_entry`; the existing risk engine, order manager, and position manager are constructed by the operator. This is materially different from baseline DUMB's local backtest simulation.
7. **Config key:** `config/live_demo.json` contains `"strategy_mode": "DUMB_MTF_H4"` and `"timeframe": "M5"`. Operator config validates this mode and rejects non-M5 execution. Other modes/omitted keys do not select baseline DUMB.
8. **Runnable status:** Current live operator wiring exists when `config/live_demo.json` (or another correctly configured profile) is explicitly passed. Current values are `dry_run: false`, `require_demo: true`, `risk_fraction: 0.01`, and `heartbeat_path: "logs/phase_d/heartbeat.txt"`. `require_demo` is an account guard, not a strategy selector; heartbeat resolution can prefer the terminal data-folder candidate over the config fallback.

**Parallel primary/fallback:** The state machine enforces phase order: it changes from primary to fallback only after primary expiry; it records a fallback sweep only in fallback state; and it refuses fallback confirmation until `sweep_clock_bar` exists. The clocks are not parallel in the state machine. However, see the feed-path issue in **Open unknowns**: the current H4 feed may fail to register the fallback sweep if it already cached a primary sweep.

**Relationship to generic coordinator:** [`sweep_episode_coordinator.py`](../04_SRC/smc/orchestration/sweep_episode_coordinator.py) is isolated and not used by `run_operator`, `LiveLoop`, or `DumbMtfH4Feed`. Governance records this explicitly. DUMB-MTF uses its own touch-based state machine, not that coordinator's closed source-sweep lifecycle.

Evidence: [`mtf.py`](../04_SRC/smc/dumb/mtf.py) policy/status/methods; [`mtf_h4_feed.py`](../04_SRC/smc/dumb/mtf_h4_feed.py) `_refresh_h4_pois`, `_start_primary_on_new_touches`, `_routes_for_bar`; [`mtf_paper_adapter.py`](../04_SRC/smc/dumb/mtf_paper_adapter.py) `_record_confirmation`, `generate_candidates`; [`loop.py`](../04_SRC/smc/live/loop.py) `_fetch_new_bars`, `_drive_dumb_mtf`; [`run_operator.py`](../04_SRC/smc/live/run_operator.py) `OperatorSession._build_stack`; [`operator_config.py`](../04_SRC/smc/live/operator_config.py) `strategy_mode` validation; [`PROVISIONAL_EXECUTION_CLOCKS_2026-10-25.md`](../00_LOCKED/PROVISIONAL_EXECUTION_CLOCKS_2026-10-25.md) “H4 live slice completed”; [`DUMB_MTF_FORWARD_DEMO_PLAN.md`](DUMB_MTF_FORWARD_DEMO_PLAN.md) “Current demo scope.”

## Difference matrix

| Dimension | Baseline DUMB | DUMB-MTF_H4 |
|---|---|---|
| Source TFs | W1, D1, H4 M8 zones; forming HTF bar can be included in the honest prefix. | H4 only; completed H4 M8 bars only. |
| Confirm TFs | M5 only. | M5 and M15, closed bars; earliest event wins; M5 wins exact-time tie. |
| Clock model | One 12-M5-bar inclusive window from the latest sweep; newer sweep resets it. | Touch-started primary: 6 M5 bars, then boundary fallback only: 16 M5 bars from its sweep. |
| Sweep requirement | Wick beyond zone edge, close back inside; required before confirmation. | Also requires a real later wick/close-back sweep before confirmation; H4 feed caches this sweep as stop evidence. Fallback additionally needs a fallback-phase sweep clock. |
| Candidate-rate drivers | Three M8 source TFs, M5 sweep/confirm cadence, active zones, per-zone busy/re-arm state, inside-zone confirmation. | One source TF, completed H4/M5/M15 inputs, touch-started primary, required later sweep, one-winner M5/M15 race, sequential fallback. |
| Isolation from COMPLEX / Essence | Separate research runner/package; no COMPLEX branches; not an operator product mode. | Separate opt-in operator adapter and state machine; does not alter COMPLEX or Essence. |
| Risk/order path shared? | No PaperRunner/risk/order path in `run_dumb_flowchart`; simulated fill-model exits. | Yes; one candidate goes through existing PaperRunner and operator risk/order/position managers. |
| Live selectable today? | No baseline selector or live wiring found. | Yes, with explicit `strategy_mode: "DUMB_MTF_H4"` and M5 execution. |
| Expected setup density (qualitative only) | More source-timeframe coverage (W1/D1/H4); actual density unknown. | Fewer source families (H4 only) and stricter closed-bar source availability; M15 confirmation and fallback add paths within H4. Aggregate trade density remains unknown without matched observations. |

## Trade-chance impact (mechanics only)

- **Does H4 DUMB-MTF likely produce fewer opportunities than baseline DUMB?** It likely has fewer *source-generated episode opportunities*: only H4 emits zones instead of baseline W1/D1/H4, and the H4 feed only uses completed H4 bars whereas baseline's documented prefix can include the current forming HTF bar. That is a coverage argument, not a trade-count or performance claim. On the other hand, MTF has M15 as an additional confirmation stream and a sequential fallback phase. Without matched event data, the total number of submitted candidates/trades is **UNKNOWN**.
- **What could expand density later?** Design and provision one source emitter at a time (for example an approved H1 source-POI emitter), then add its policy/clock-owner row and closed-bar feed wiring under a dated owner ruling. H1's registered confirmation streams are M1/M5 with M1 as sole clock owner. Keep one episode clock and primary-then-fallback sequence; do not run the two phases in parallel or substitute generic liquidity sweeps for POI-boundary events. The D1 and M15 source rows likewise need real approved source emitters before they can be enabled.
- **Config footguns:** `strategy_mode` omitted/defaulted or set to `COMPLEX` selects COMPLEX, not baseline DUMB or DUMB-MTF; only `DUMB_MTF_H4` opts into the new path. That mode requires `timeframe: "M5"`. `dry_run: true` (as in tester/console dry-run profiles) prevents live order sends; current `live_demo.json` is `false`. Keep `require_demo: true`. The configured heartbeat path is a candidate/fallback path; operator code prefers the terminal's EA-readable data-folder location when available and probes writable candidates before startup. If running the wrong profile, the strategy mode and dry-run setting can therefore differ from `live_demo.json`.

## Open unknowns

1. **Fallback feed registration edge (observed code-path limitation):** `DumbMtfH4Feed._routes_for_bar` only enters its sweep-recording block when the episode ID is absent from `_sweep_extremes`. A valid primary-phase sweep stores that ID. If the primary expires without confirmation, a later fallback-phase boundary sweep is consequently skipped by that block, so `record_boundary_sweep` is not called. The state machine then rejects fallback confirmations while `sweep_clock_bar` is unset and does not time out an unset fallback clock. The focused feed tests cover primary sweep/confirmation and sweep-bar non-confirmation, not this primary-sweep-then-fallback sequence. This appears to leave some fallback episodes unable to confirm or expire; verify against intended behavior before relying on fallback opportunities. No fix was made.
2. **Baseline vs MTF aggregate counts:** No matched forward/backtest report comparing these exact two paths was located for this probe. Relative realized trade frequency is UNKNOWN.
3. **Historical live usage:** No evidence that baseline DUMB was ever live-wired or selected for demo before `DUMB_MTF_H4`. The prior path is explicitly documented as research-only. Treat any claim about actual prior baseline demo usage as UNKNOWN.
4. **Baseline midpoint boundary:** The design's R3 example uses `>=` / `<=` at the midpoint, while `rules.py:is_confirm` implements strict `>` / `<`. The active baseline code behavior is strict; whether the design's inclusive notation was intended to change implementation semantics is UNKNOWN. DUMB-MTF reuses the strict code function.
5. **Operational readiness:** Config values establish mode, dry-run and demo-account guard; they do not prove the operator is currently running, the selected terminal is the intended one, active closed H4 POIs exist, or heartbeat publication has succeeded.
6. **Generic coordinator:** Its future integration state is separate from DUMB-MTF H4. It is present in source and tests, but documentation says it remains isolated and not wired.

## Return block

PROBE_STATUS: COMPLETE — READ-ONLY EVIDENCE REPORT  
BASELINE_DUMB_LIVE_WIRING: NOT FOUND  
CURRENT_DEMO_MODE: DUMB_MTF_H4  
ACTIVE_CONFIG: config/live_demo.json  
DRY_RUN: false  
REQUIRE_DEMO: true  
GENERIC_SWEEP_EPISODE_COORDINATOR: ISOLATED / NOT WIRED  
FALLBACK_FEED_PATH: POSSIBLE REGISTRATION GAP — SEE OPEN UNKNOWNS  
RELATIVE_TOTAL_TRADE_DENSITY: UNKNOWN  
SOURCE_DENSITY_EXPECTATION: H4-ONLY MTF HAS FEWER SOURCE FAMILIES THAN BASELINE W1/D1/H4  
CHANGES_MADE: REPORT FILE ONLY; NO CODE, CONFIG, OR LOCKED-CONSTANT CHANGES  
