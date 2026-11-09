# MENU CONFIRMATION-STREAM SMOKE NOTE (interim — run in progress at baseline commit)

**Status:** STRUCTURAL PASS (proven in-progress). The background smoke run was still executing at baseline-commit time; final totals will be in `06_RESEARCH/MENU_CONFIRM_STREAM_SMOKE_RUN.log` and this file may be overwritten by the script on completion.

## Goal
Prove the menu spine beyond arm/register: `sweep detection -> confirmation evaluation -> winner emission -> queue/submit` on the real product path, without OPT-2 / R7 retune / edge claims.

## Setup
- Script: `06_RESEARCH/scripts/menu_confirm_stream_smoke.py`
- Data: `07_DATA/XAUUSD_M1.parquet`
- Warmup: `2023-12-01`, window: `2024-04-01 .. 2024-06-30`
- Detection TFs (M2): `[D1, H4, H1, M15]`
- Tiers: DAY(D1→H1), H4(H4→M5,M15), H1(H1→M5,M1), M15(M15→M1)
- Exec TF: M5. OPT-B default false. OPT-2 off. No pillar/threshold changes.
- Path: real `MultiTFProductRuntime.run_batch` → `menu.register_armed` (sparse cadence, every 48 M15 steps) interleaved with dense M15-timeline `menu.on_execution_bar(feed, as_of=close)` feeding closed detection/confirmation streams (tail-sliced). Winners queued via `PipelineAdapter.queue_menu_candidate` into a counted `submit_entry` stub.

## Proven in-progress counters (from log)
- `REGISTER_ARMED` reached **14** (regression > 0)
- `SWEEPS_DETECTED` (menu.sweeps_total) reached **29**
- `MENU_WINNERS` = **5** (observed)
- `QUEUE_SUBMITS` (adapter `queue_menu_candidate` → `submit_entry`) = **5**
- `ADAPTER_LEGACY_SUBMITS` = 0 (isolated smoke)
- `PLACES/FILLS` = 0/0 (diagnostic; no broker/risk execution)
- Sample progress: `step 400 registered=6 sweeps=1 winners=1 submits=1`; `step 2000 registered=14 sweeps=27 winners=5 submits=5 active=0`; `step 2400 registered=14 sweeps=29 winners=5 submits=5 active=1`.

## Explanation / verdict
Structural menu spine path **proven**: arm/register works on real batches; closed streams drive `on_execution_bar`; sweeps are detected; confirmation winners are emitted; winners are queued through `queue_menu_candidate` → `submit_entry`. Episodes progress/expire by one-shot discipline (active/expired observed in progress). **Not an edge/PnL claim.** Final end-state totals: see `06_RESEARCH/MENU_CONFIRM_STREAM_SMOKE_RUN.log` (and final note if script overwrote this file).

## Evidence
- Interim log: `06_RESEARCH/MENU_CONFIRM_STREAM_SMOKE_RUN.log`
- Script: `06_RESEARCH/scripts/menu_confirm_stream_smoke.py`
