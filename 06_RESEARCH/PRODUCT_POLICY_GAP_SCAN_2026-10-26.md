# Product Policy Gap Scan — Multi-TF Confirmation

**Date:** 2026-10-26  
**Scope:** Read-only mapping of `00_LOCKED/PRODUCT_POLICY_MULTI_TF_CONFIRMATION.md` to the repository. No code, thresholds, or locked policy were changed.  
**Conclusion:** **Partial foundation; policy engine missing.** H4 POI detection, A–F trigger implementations, candidate/risk/order plumbing, and an isolated H4→M5/M15 DUMB-MTF experiment exist. The current COMPLEX product path does not implement “POI sweep arms a one-shot window, then A/D/F may confirm on M5 or M15, with expiry after 20 H4 bars.” The generic sweep-episode coordinator is not wired into that path.

## Executive answers

1. **Can H4 POIs be detected today?** Yes. `DetectionDriver` runs the registered M1–M8 models on a supplied timeframe; M8 emits H4 zones when given the H4 candle map. The canonical `MultiTFProductRuntime` does this in an H4+H1 detection batch. It is not an H4-only policy runtime.
2. **Can those POIs be confirmed on M5 and M15 today?** DUMB-MTF can observe H4 M8 zones and run its own confirmation heuristic on closed M5 and M15 bars. The COMPLEX `TriggerRouter` runs a supplied candle series, but the current product loop/adapter supplies one execution series (normally M5), not both. A/D/F are not connected to the DUMB-MTF feed.
3. **Is multi-TF confirmation orchestration present?** A reusable, generic `SweepEpisodeCoordinator` defines per-source allowed confirmation TFs and first-confirm arbitration, but no live/product caller wires it to POI detection, sweep creation, the COMPLEX trigger router, or candidate submission. The live COMPLEX stack is still single-execution-TF.
4. **First-confirm-wins across M5+M15?** Present in isolated generic arbitration and DUMB-MTF confirmation handling; missing for policy A/D/F confirmations.
5. **Expiry after 20 detection-TF bars?** Missing. COMPLEX uses a 20-bar POI give-up window based on Trigger A’s M5 constant. The generic coordinator accepts caller-provided wall-clock `expires_at`. DUMB-MTF has sequential M5 clocks and 6/16-bar phases (not 20 H4 bars).
6. **What is DUMB-MTF, and what is it not?** It is an opt-in H4 M8 zone-touch/sweep/reclaim experiment with M5/M15 race arbitration and a fixed DUMB entry/SL/TP calculation. It is not the locked policy’s validated POI → POI sweep arms window → A/D/F trigger confirmation engine.

## Phase 1 — Existing resource inventory

### A. Detection / POI

| Resource | Existing capability |
|---|---|
| [`04_SRC/smc/orchestration/detection_driver.py`](../04_SRC/smc/orchestration/detection_driver.py) | Runs Stage 0/1 and all registered M1–M8 POI models, merges and validates POIs for the supplied detection timeframe. |
| [`04_SRC/smc/poi/model_registry.py`](../04_SRC/smc/poi/model_registry.py) | Registers Models 1–8 for any supplied timeframe; M8 additionally receives an optional HTF candle map. |
| [`04_SRC/smc/poi/models/m8_htf_demand_supply.py`](../04_SRC/smc/poi/models/m8_htf_demand_supply.py) | M8 scans W1/D1/H4 and emits OB, demand/supply, and FVG zones; H4 and D1 data can be shared to M8 by the detection drivers. It emits no M15 M8 zones. |
| [`04_SRC/smc/orchestration/multi_tf.py`](../04_SRC/smc/orchestration/multi_tf.py) | Generic detection cascade over caller-selected detection TFs; default is H4+H1. It runs detection only, not confirmation routing. |
| [`04_SRC/smc/orchestration/multi_tf_runtime.py`](../04_SRC/smc/orchestration/multi_tf_runtime.py) | Product detection/validation/arming facade with dedup and H4+H1 required by its current locked runtime contract; it does not coordinate confirmation streams. |
| [`04_SRC/smc/live/loop.py`](../04_SRC/smc/live/loop.py) | Live bar loop; COMPLEX uses the product detection runtime when configured, while DUMB-MTF uses a separate feed. The normal COMPLEX scan remains on its configured execution series. |
| [`04_SRC/smc/config/timeframe.py`](../04_SRC/smc/config/timeframe.py) | Defines M1, M5, M15, H1, H4, D1 and W1; no M8 timeframe exists—M8 is a model tag. |

**Timeframe scope:** generic `DetectionDriver`/`MultiTFDetectionDriver` can evaluate H1 and M15 source series; M8 specifically emits from W1/D1/H4 input. The product runtime currently requires H4+H1 together. P1 can use the existing H4 detector/model stack without adding any DAY/H1/M15 detection tier.

### B. Sweep

| Resource | Existing capability |
|---|---|
| [`04_SRC/smc/detection/sweep_detector.py`](../04_SRC/smc/detection/sweep_detector.py) | `SweepResult`/`detect_sweep(s)` detect wick-through/close-back sweeps of `LiquidityLevel`s and retain the source candle/index; the result is not a sweep event linked to a POI episode. |
| [`04_SRC/smc/orchestration/detection_driver.py`](../04_SRC/smc/orchestration/detection_driver.py) | Computes sweep/displacement artifacts within a detection window and associates displacement context with detected POIs. |
| [`04_SRC/smc/detection/displacement_checker.py`](../04_SRC/smc/detection/displacement_checker.py) | Provides displacement measurement/checking; this is POI validation evidence, not the product’s sweep-armed confirmation lifecycle. |
| [`04_SRC/smc/risk/sweep_guard.py`](../04_SRC/smc/risk/sweep_guard.py) | Failed-sweep re-entry guard after a losing trade, keyed by direction/level/cooldown. It is an entry-risk guard, not source-sweep detection or an arm-window guard. |
| [`04_SRC/smc/orchestration/sweep_episode_coordinator.py`](../04_SRC/smc/orchestration/sweep_episode_coordinator.py) | Defines `ClosedSweep`, `Confirmation`, and `SweepEpisode` event-like types plus lifecycle/arbitration; the caller must already supply a proven closed sweep and expiry. No POI-linked sweep detector is wired to it. |
| [`04_SRC/smc/dumb/rules.py`](../04_SRC/smc/dumb/rules.py) | DUMB-specific zone-extreme wick-through/close-back sweep and midpoint-reclaim rules. These do not route the A/D/F trigger set. |

No `SweepEvent` domain type was found under that name. `SweepResult` and the coordinator’s `ClosedSweep` are existing sweep-event-like types, with different responsibilities.

### C. Triggers A–F

| Resource | Existing capability |
|---|---|
| [`04_SRC/smc/triggers/trigger_a_choch.py`](../04_SRC/smc/triggers/trigger_a_choch.py) | Trigger A implementation. |
| [`04_SRC/smc/triggers/trigger_b_leading_diagonal.py`](../04_SRC/smc/triggers/trigger_b_leading_diagonal.py) | Trigger B implementation. |
| [`04_SRC/smc/triggers/trigger_c_ending_diagonal.py`](../04_SRC/smc/triggers/trigger_c_ending_diagonal.py) | Trigger C implementation. |
| [`04_SRC/smc/triggers/trigger_d_two_bar.py`](../04_SRC/smc/triggers/trigger_d_two_bar.py) | Trigger D implementation. |
| [`04_SRC/smc/triggers/trigger_e_rsi_divergence.py`](../04_SRC/smc/triggers/trigger_e_rsi_divergence.py) | Trigger E implementation. |
| [`04_SRC/smc/triggers/trigger_f_bos_ob.py`](../04_SRC/smc/triggers/trigger_f_bos_ob.py) | Trigger F implementation. |
| [`04_SRC/smc/triggers/trigger_router.py`](../04_SRC/smc/triggers/trigger_router.py) | Chronological first-bar route among matrix-eligible triggers; defaults to all A–F. |
| [`04_SRC/smc/triggers/compatibility_matrix.py`](../04_SRC/smc/triggers/compatibility_matrix.py) | Grades all trigger/model pairs; all are allowed. It does not implement the policy’s per-tier trigger subset. |
| [`04_SRC/smc/triggers/trigger_expiry.py`](../04_SRC/smc/triggers/trigger_expiry.py) | Existing per-trigger and POI give-up windows; POI give-up is `TRIGGER_A_EXPIRY` (20 M5 bars), not detection-TF expiry. |

`TriggerRouter` takes candle/swing lists and has no hard-coded “M5 only” input guard, so its API can be invoked with M15 or M1 candles. That is not equivalent to product support: the router has no per-confirmation-TF policy or cross-stream race, the existing engine scan is passed one series, and the shipped COMPLEX live path is normally M5. Trigger validity constants and the POI give-up deadline are currently M5-based. P1 must preserve existing trigger geometry while making the policy’s allowed A/D/F set and per-stream evaluation explicit.

### D. Seek / arm / lifecycle (COMPLEX path)

| Resource | Existing capability |
|---|---|
| [`04_SRC/smc/orchestration/multi_tf_runtime.py`](../04_SRC/smc/orchestration/multi_tf_runtime.py) | Validates detection batches, deduplicates geometry, and calls `engine.arm_at` for newly passed POIs. Arming is on validation/batch, not a later POI sweep. |
| [`04_SRC/smc/orchestration/engine.py`](../04_SRC/smc/orchestration/engine.py) | Owns POI state and trigger scans. `scan_route` scans from the POI arm bar through its give-up deadline and obtains the first valid route from its router. |
| [`04_SRC/smc/backtest/pipeline_adapter.py`](../04_SRC/smc/backtest/pipeline_adapter.py) | Adapts the engine to the runner; maintains per-POI workflow/scan state and converts eligible routes to candidates. |
| [`04_SRC/smc/live/loop.py`](../04_SRC/smc/live/loop.py) | On the COMPLEX path, batches detections/arms and advances the configured execution bar loop. The DUMB-MTF branch is separate. |
| [`04_SRC/smc/orchestration/sweep_episode_coordinator.py`](../04_SRC/smc/orchestration/sweep_episode_coordinator.py) | Can represent an already-detected closed source sweep and a confirmation episode, but has no connection to the above arm/scan/candidate path. |

**Gap:** today a validated HTF POI becomes an armed POI and enters the COMPLEX seek/scan lifecycle before any sweep-of-that-POI requirement. The locked policy instead requires a specific POI sweep to create a one-shot confirmation window, then evaluates only that tier’s confirmation TFs. The generic coordinator does not fill this gap by itself: it does not detect the source POI sweep, invoke `TriggerRouter`, enforce A/D/F, or submit the winning route.

### E. Risk / orders / paper / live

| Resource | Existing capability |
|---|---|
| [`04_SRC/smc/backtest/pipeline_bridge.py`](../04_SRC/smc/backtest/pipeline_bridge.py) | Converts a `TriggerRoute` to `CandidateEntry`, including trigger, POI, route ID, zone, model tags, and detection TF. |
| [`04_SRC/smc/backtest/runner.py`](../04_SRC/smc/backtest/runner.py) | `CandidateEntry` enters the existing risk-gated runner path; accepted candidates create pending limit orders and carry identity into positions/trade reports. |
| [`04_SRC/smc/risk/risk_engine.py`](../04_SRC/smc/risk/risk_engine.py) | Existing entry-risk decisions and sizing policy. |
| [`04_SRC/smc/execution/order_manager.py`](../04_SRC/smc/execution/order_manager.py) and [`04_SRC/smc/backtest/orders.py`](../04_SRC/smc/backtest/orders.py) | Existing live request and simulated pending-order layers, respectively. |
| [`04_SRC/smc/paper/runner.py`](../04_SRC/smc/paper/runner.py) | Paper candidate submission and existing risk/order/position pipeline. |
| [`04_SRC/smc/live/operator_config.py`](../04_SRC/smc/live/operator_config.py) | `strategy_mode` accepts `COMPLEX` or `DUMB_MTF_H4`; default config class is COMPLEX. `DUMB_MTF_H4` requires M5 execution. |
| [`04_SRC/smc/live/run_operator.py`](../04_SRC/smc/live/run_operator.py) | Builds COMPLEX pipeline by default or constructs a separate DUMB-MTF feed when explicitly selected. |
| [`config/live_demo.json`](../config/live_demo.json) | Current sample demo explicitly selects `DUMB_MTF_H4`; it is an opt-in sample, not the policy engine. |
| [`04_SRC/smc/dumb/mtf_paper_adapter.py`](../04_SRC/smc/dumb/mtf_paper_adapter.py) | DUMB-MTF winners are converted to ordinary `CandidateEntry` records and sent through the existing paper runner. |

Candidate → risk → order plumbing is reusable and substantially present. Policy-specific confirmation identity and the winning source-sweep episode need to be attached at the candidate boundary; do not create a parallel risk/order path.

### F. Export / review identity

| Resource | Existing capability |
|---|---|
| [`04_SRC/smc/backtest/runner.py`](../04_SRC/smc/backtest/runner.py) | Candidate identity includes `poi_id`, `trigger`, `route_id`, `model_tags`, `zone_low/high`, `signal_data_json`, and `detection_tf`. |
| [`04_SRC/smc/backtest/reports.py`](../04_SRC/smc/backtest/reports.py) | Trade identity includes POI, trigger, model tags, validation/displacement context, zone bounds, and signal data. It does not expose first-class tier, detection TF, or confirmation TF fields. |
| [`04_SRC/smc/backtest/export.py`](../04_SRC/smc/backtest/export.py) | CSV/JSON include trigger, POI ID, route ID, model tags, zone bounds, and other review fields; no first-class detection TF / confirmation TF / policy tier columns. |
| [`04_SRC/smc/live/structure_console.py`](../04_SRC/smc/live/structure_console.py) | Read-only display includes POI TF, zone geometry, trigger and candidate context where available. |
| [`04_SRC/smc/dumb/mtf_paper_adapter.py`](../04_SRC/smc/dumb/mtf_paper_adapter.py) | DUMB-MTF stores `confirm_tf` inside `signal_data_json`, and sets detection TF on the candidate; this identity is not a general policy export contract. |

**Review gap:** the underlying POI zone can supply detection TF, and trigger/zone identity exists, but an exported policy trade cannot reliably be grouped by `(tier, detection_tf, confirmation_tf, trigger, zone)` as first-class columns. P1 review should add these fields at candidate creation and preserve them through reports/exports without inventing values for legacy trades.

### G. Structure publish + EA draw (brief)

[`04_SRC/smc/live/structure_publish.py`](../04_SRC/smc/live/structure_publish.py) atomically publishes a full `smc_structure_draw.txt` snapshot in the terminal’s `MQL5/Files` sandbox when available. Its text format starts with `SMC_STRUCTURE_DRAW v1`, a timestamp/symbol header, and pipe-delimited `POI`, `SWEEP`, `SEEK`, and `PLAN` records. The consumer is the draw-capable [`05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5`](../05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5) (combined safety/draw EA); [`05_MQL5_SAFETY/SMC_Structure_Draw.mq5`](../05_MQL5_SAFETY/SMC_Structure_Draw.mq5) is the standalone draw consumer. **DEFERRED:** markers/structure not appearing under DUMB-MTF or after TF changes; record only, do not debug as part of P1.

## Phase 2 — Policy traceability matrix

Status meanings: **Have** = capability is directly present for the requested behavior; **Partial** = a reusable piece or experimental analogue exists but the policy contract is not implemented end-to-end; **Missing** = no matching product capability found. “Exists” names the evidence; status columns are mutually exclusive per row.

| Policy rule / tier | REQUIRED capability | EXISTS (path) | PARTIAL | MISSING | NOTES |
|---|---|---|---|---|---|
| Normative 1 | Establish POI/structure on detection TF | [`detection_driver.py`](../04_SRC/smc/orchestration/detection_driver.py), [`multi_tf.py`](../04_SRC/smc/orchestration/multi_tf.py), [`m8_htf_demand_supply.py`](../04_SRC/smc/poi/models/m8_htf_demand_supply.py) | ✓ |  | H4/D1 M8 and generic per-TF detection exist; current product runtime enforces H4+H1, not P1 H4-only. |
| Normative 2 | A detected POI sweep starts a one-shot confirmation window | [`sweep_detector.py`](../04_SRC/smc/detection/sweep_detector.py), [`sweep_episode_coordinator.py`](../04_SRC/smc/orchestration/sweep_episode_coordinator.py) |  | ✓ | Sweep detector is liquidity-level based; coordinator requires caller-supplied `ClosedSweep`. COMPLEX arms on validated POI, not its sweep. |
| Normative 3 | Only tier confirmation TFs run the tier’s trigger subset | [`trigger_router.py`](../04_SRC/smc/triggers/trigger_router.py), [`sweep_episode_coordinator.py`](../04_SRC/smc/orchestration/sweep_episode_coordinator.py) | ✓ |  | Coordinator has a TF policy table; router has A–F but no tier filter or cross-stream caller. DUMB-MTF handles H4 M5/M15 with DUMB rules, not A/D/F. |
| Normative 4 | First valid confirmation across allowed TFs wins; consume sweep once | [`sweep_episode_coordinator.py`](../04_SRC/smc/orchestration/sweep_episode_coordinator.py), [`dumb/mtf_paper_adapter.py`](../04_SRC/smc/dumb/mtf_paper_adapter.py) | ✓ |  | Generic coordinator and DUMB adapter arbitrate; neither is connected to COMPLEX A/D/F routes. Exact timestamp ties currently choose the finer TF (M5 over M15). |
| Normative 5 | Winning candidate enters existing risk/order path | [`pipeline_bridge.py`](../04_SRC/smc/backtest/pipeline_bridge.py), [`runner.py`](../04_SRC/smc/backtest/runner.py), [`paper/runner.py`](../04_SRC/smc/paper/runner.py) |  |  | Reuse candidate/risk/order seam; no new execution path is needed. |
| Normative 6 | Policy engine is default live product; DUMB/DUMB-MTF are parked experiments | [`operator_config.py`](../04_SRC/smc/live/operator_config.py), [`run_operator.py`](../04_SRC/smc/live/run_operator.py) |  | ✓ | COMPLEX remains default but is not this policy; sample `live_demo.json` explicitly selects DUMB-MTF. No policy-engine mode exists. |
| Normative 7 | Expert validation pack precedes optimization | [`06_RESEARCH/EXPERT_MARKED_CHARTS_INDEX.md`](./EXPERT_MARKED_CHARTS_INDEX.md), [`06_RESEARCH/ESSENCE_V1_EXPERT_REVIEW_BRIEF.md`](./ESSENCE_V1_EXPERT_REVIEW_BRIEF.md), [`backtest/export.py`](../04_SRC/smc/backtest/export.py) | ✓ |  | Review resources exist, but a P1-specific H4 stream pack and complete tier/detect/confirm/trigger/zone identity export do not. |
| DAY | Detect D1; confirm H1 with A–F; expire after 20 D1 bars | [`m8_htf_demand_supply.py`](../04_SRC/smc/poi/models/m8_htf_demand_supply.py), [`sweep_episode_coordinator.py`](../04_SRC/smc/orchestration/sweep_episode_coordinator.py) | ✓ |  | M8 can emit D1 and coordinator has D1→H1 policy data. No wired D1 sweep-to-H1 A–F product lifecycle or D1-bar expiry. Out of P1. |
| H4 | Detect H4; confirm M5+M15 with A/D/F; expire after 20 H4 bars | [`m8_htf_demand_supply.py`](../04_SRC/smc/poi/models/m8_htf_demand_supply.py), [`dumb/mtf_h4_feed.py`](../04_SRC/smc/dumb/mtf_h4_feed.py), [`sweep_episode_coordinator.py`](../04_SRC/smc/orchestration/sweep_episode_coordinator.py) | ✓ |  | H4 detection and DUMB M5/M15 input exist. The DUMB feed is not policy A/D/F; generic coordinator is isolated; COMPLEX give-up is 20 M5 bars, not 20 H4 bars. |
| H1 | Detect H1; confirm M1+M5 with A/D/F; expire after 20 H1 bars | [`detection_driver.py`](../04_SRC/smc/orchestration/detection_driver.py), [`sweep_episode_coordinator.py`](../04_SRC/smc/orchestration/sweep_episode_coordinator.py) | ✓ |  | H1 generic detection and coordinator policy data exist. No integrated H1 source-sweep confirmation streams or H1-bar expiry. Out of P1. |
| M15 | Detect M15; confirm M1 with A/D/F; expire after 20 M15 bars | [`detection_driver.py`](../04_SRC/smc/orchestration/detection_driver.py), [`sweep_episode_coordinator.py`](../04_SRC/smc/orchestration/sweep_episode_coordinator.py) | ✓ |  | Generic Models 1–7 can run at M15; coordinator has policy data. No M15 source emitter lifecycle or detection-bar expiry. Out of P1. |

### Explicit P1 questions and DUMB-MTF distinction

| Question | Finding |
|---|---|
| H4 POIs today? | **Yes:** M8 H4 OB/demand-supply/FVG plus generic POI models; current canonical product batching is H4+H1, while the isolated DUMB feed uses H4 M8 directly. |
| Confirm H4 POIs on M5 today? | **Partially:** COMPLEX trigger routes operate on the live M5 execution series but are not sweep-gated. DUMB-MTF applies its own rule on M5 after its zone-touch episode. |
| Confirm H4 POIs on M15 today? | **Partially:** DUMB-MTF reads closed M15 and races it with M5 using DUMB confirmation logic. COMPLEX A/D/F are not evaluated on an M15 stream in the product loop. |
| Multi-TF confirmation orchestrator? | **Not in the product path.** `SweepEpisodeCoordinator` is a generic isolated abstraction/tested component, not integrated with POI detection, POI sweep creation, trigger execution, or candidate submission. |
| First-confirm-wins on M5+M15? | Generic coordinator and DUMB adapter have deterministic arbitration (earlier timestamp; finer TF on exact tie). **Policy A/D/F route race is missing.** |
| Expiry in detection-TF bars? | **No.** Generic coordinator uses caller-set `expires_at` timestamps; COMPLEX uses a 20-M5-bar POI give-up; DUMB-MTF’s H4 mode uses the M5 episode clock and sequential 6/16-bar phases. None is 20 H4 bars. |
| What is DUMB-MTF not? | Not A/D/F; not POI validation followed by a POI sweep that arms the window; not H4-bar expiry; not the default policy engine. It uses first zone touch, a qualifying zone-edge sweep, DUMB reclaim, and DUMB-specific SL/TP, then shares the paper/risk/order path. |

## Phase 3 — P1 minimal build list (H4 only)

Scope fixed to `detection_tf=H4`, `confirmation_tfs=[M5,M15]`, triggers `{A,D,F}`, expiry `20 H4 bars`, one-shot, existing risk/orders. No DAY/H1/M15 detection tiers and no chart-marker debugging.

| Order | Work item | File action | Minimal scope / reuse |
|---|---|---|---|
| 1 | Define P1 policy config and runtime seam | **NEW** policy/orchestrator module; **EXTEND** [`operator_config.py`](../04_SRC/smc/live/operator_config.py) and runtime wiring | Make H4-only detection and `[M5,M15]` confirmation an explicit policy configuration; do not force the existing H4+H1 `MultiTFProductRuntime` contract onto P1. Keep policy mode distinct from `COMPLEX` and opt-in DUMB-MTF until verified. |
| 2 | H4 POI detection/validation and zone identity | **REUSE** [`detection_driver.py`](../04_SRC/smc/orchestration/detection_driver.py), [`model_registry.py`](../04_SRC/smc/poi/model_registry.py), [`m8_htf_demand_supply.py`](../04_SRC/smc/poi/models/m8_htf_demand_supply.py) | Run the existing frozen H4 detection/validation stack with H4 candles available to M8; preserve POI ID, model tags, zone kind and bounds. Do not add other detection tiers or alter model thresholds. |
| 3 | POI-linked closed H4 sweep → one-shot episode | **NEW** episode/source-event wiring; **REUSE** `SweepResult`/`ClosedSweep` where semantics fit | Detect and identify a closed sweep of the particular H4 POI, bind it to POI/source timestamp, arm exactly one episode, and reject duplicates/invalidated POIs. Existing liquidity-level sweep results are not POI-linked without this association. |
| 4 | Evaluate policy triggers on both confirmation streams | **EXTEND** [`trigger_router.py`](../04_SRC/smc/triggers/trigger_router.py) or add a narrow policy adapter; **REUSE** A, D, F implementations | Evaluate only A/D/F on honest closed M5 and M15 prefixes after the source sweep, retaining existing trigger geometry and no-lookahead behavior. Do not change global A–F compatibility or constants. |
| 5 | First-confirm-wins and expiry | **EXTEND** [`sweep_episode_coordinator.py`](../04_SRC/smc/orchestration/sweep_episode_coordinator.py) or integrate it from the new P1 orchestrator | Route both TF candidates through one episode arbiter; first valid route consumes the episode. Track source H4 bar index and expire at 20 detection-TF bars; do not use elapsed time or M5 bar counts as a substitute. |
| 6 | Build winner candidate and enter existing risk/orders | **REUSE** [`pipeline_bridge.py`](../04_SRC/smc/backtest/pipeline_bridge.py), [`runner.py`](../04_SRC/smc/backtest/runner.py), [`paper/runner.py`](../04_SRC/smc/paper/runner.py), [`execution/order_manager.py`](../04_SRC/smc/execution/order_manager.py); **EXTEND** bridge only if identity needs adding | Convert exactly one winning trigger route to the established `CandidateEntry`; preserve risk, limit-order, paper and live gates. No parallel order/risk implementation. |
| 7 | Preserve P1 expert-review identity and produce review pack | **EXTEND** [`runner.py`](../04_SRC/smc/backtest/runner.py), [`reports.py`](../04_SRC/smc/backtest/reports.py), [`export.py`](../04_SRC/smc/backtest/export.py); **NEW** P1 review-pack script/report if needed | Add first-class tier, detection TF, confirmation TF, trigger, zone kind/bounds, POI/source-sweep identity and route ID; preserve unknown legacy values as unknown. Generate H4-stream expert review material before optimization work. |
| 8 | Verify lifecycle and mode isolation | **EXTEND** focused tests for new seam, adapter and export; **REUSE** existing risk/order tests | Prove H4 sweep arming, A/D/F-only confirmation, M5/M15 first-win, exact tie determinism, 20 H4-bar expiry, one-shot behavior, no lookahead, and passage through existing risk/orders. Verify DUMB-MTF does not become the default policy implementation. |

### Not in P1

- DAY/D1, H1, or M15 detection tiers; H2; Mode B; expectancy optimization.
- Changing locked risk constants, trigger geometry, or model thresholds.
- Replacing expert discretion.
- Structure/chart marker diagnosis under DUMB-MTF or after timeframe changes.

## Phase 4 — TODO binding suggestions only

Suggested checkbox lines for a later authorized edit to `00_LOCKED/POST_V1_ACTIVE_TODO.md` / `00_LOCKED/SESSION_HANDOFF.md`; **neither file was edited in this scan**:

```text
- [ ] Product policy locked (multi_tf_confirmation)
- [ ] P1 H4→M5/M15 confirmation engine
- [ ] Expert review pack for P1
- [ ] DEFERRED: structure chart markers not showing (DUMB-MTF / TF switch)
- [ ] Park DUMB-MTF as non-default
```

## Evidence notes

- The locked source of truth is [`00_LOCKED/PRODUCT_POLICY_MULTI_TF_CONFIRMATION.md`](../00_LOCKED/PRODUCT_POLICY_MULTI_TF_CONFIRMATION.md).
- Existing product detection requirements are separately documented in [`00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md`](../00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md); its H4+H1 detect/M5 exec contract is not the newer H4-only P1 confirmation policy.
- The isolated H4 DUMB-MTF experiment is described in [`06_RESEARCH/DUMB_MTF_FORWARD_DEMO_PLAN.md`](./DUMB_MTF_FORWARD_DEMO_PLAN.md) and [`06_RESEARCH/DUMB_VS_DUMB_MTF_COMPARISON_2026-10-25.md`](./DUMB_VS_DUMB_MTF_COMPARISON_2026-10-25.md).
- Marker visibility remains a recorded deferred operational issue; it was not investigated here.
