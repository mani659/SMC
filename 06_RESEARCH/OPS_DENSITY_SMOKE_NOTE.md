# OPS DENSITY SMOKE — post–ZoneDedup lifecycle (M-2 gate)

**Date:** 2026-10-20 · **Authority:** Architect disposition 2026-10-20 (LIVE_PROMOTION blocked until density soak under ~20× arm class)
**Scope:** ops/measurement only — the *live/paper operator path* under the post-LEG-5b arming machinery. **No edge / PnL claim; no expectancy conclusion.** `LOGIC_CHANGED: NO` — no strategy, locked_constants, pillar, trigger or dedup-rule edit; no `04_SRC` edit. Research/diagnostic additions only (`06_RESEARCH/scripts/ops_density_preflight.py`, `config/ops_density_smoke.json`, this note + artifacts).

**Provenance honesty (class qualifier):** the soak ran on the *current live market structure*, so the concurrent armed class on the live path was small (max 3). The ~20× density provenance (LEG 5b armed 30→606 on frozen 6m, `NEW_ARMS_SIMILAR_TO_LEGACY`) remains a backtest-level fact; this session proves the **operator-path mechanics** under denser arming (batch machinery, dedup/retire live in product mode, board↔detect coherence, heartbeat, zero-order dry-run), not a wider-armed live soak.

---

## 1. Preflight (06_RESEARCH/scripts/ops_density_preflight.py; results 06_RESEARCH/results/ops_density_smoke_20261020_121117/preflight.json)

- **Identity gate: PASS** — `initialize(path)` succeeded after the documented cooldown quirk (§5), then:
  - `mode=DEMO`, `login=474608655`, `server=Exness-MT5Trial15`, `company=Exness Technologies Ltd`, `leverage 2000`
  - terminal dir configured == live (EXNESS Copy), `terminal_data_path = ...\Terminal\6FE846653CB9AC4D5ACECF98EF447F40` (EXNESS Copy's data dir; XAUUSDm available)
- **Product tree coherence: PASS** — `zone_dedup_retire: true`, `retire_result_probe: 1`, `register_requires_owner: true` — the post-LEG-5b ZoneDedup-retire tree is what the operator imports live.
- **Heartbeat path:** operator resolves the heartbeat next to `terminal_data_path/MQL5/Files/smc_heartbeat.txt` (EA-readable default); marker path `smc_markers.csv` same dir. EA GUI attach: not verifiable from this session — heartbeat *file* contract coherent, EA**panel** consumption observationally BLOCKED (documented; not a smoke failure per brief §PREFLIGHT-3).
- **Git record:** short SHA `9b649d5`, branch `main`, 130 dirty paths at session start.

## 2. Session 1 — bounded operator run (dry_run=true; exit = max-seconds bound)

- **Config:** `config/ops_density_smoke.json` — `dry_run=true`, `require_demo=true`, product mode: `detection_timeframes ["H4","H1"]`, `allow_single_tf_degraded=false`, timeframes W1/D1/H4/H1 provisioned deeper per phase D; poll 0.5 s; console_mode `board` (45 s refresh) for observability; `log_dir logs/ops_density`; marker_enabled true.
- **Bump:** executed `python 04_SRC/smc/live/run_operator.py --config config/ops_density_smoke.json --max-seconds ~1500` (25 min upper bound). Stop reason: **max-seconds bound** (documented per brief).
- **Window:** started 12:22:05.85 UTC (15:22:05 local) → stopped 12:47:05.99 UTC. Session record: **polls 2981, bars_processed 5, decisions 5**.
- **HTF fetch depths:** W1/D1/H4/H1 provisioned; board snapshots show W1 + D1 + H4 + H1 zones (live quotes via copies).
- **Batches:** 1 HTF batch processed (in 25-min bound): `arm_bar 0`; per-TF — H4 raw 20 / merged 6 / passed 3; H1 raw 22 / merged 8 / passed 3. **duplicates_suppressed 3**, `armed 3`, `skipped_tracked 0`, `errors {}` — funnel counters live per the brief ITEM-C shape (raw/merged/passed/armed/dup).
- **Structure board coherence:** POIS.board armed count matches `detect.armed` at every sampled board (armed always 3; zero lag). Sweeps recorded per POI; SEEKING shows CLEAN_ARM postures with no trigger Plexed.
- **Max concurrent armed:** 3. **Retire churn visible:** no on-window detect (window < give-up clock 20×M5; no VIOLATED in this window) — retirement facts carried by `04_SRC/tests/test_zone_dedup_lifecycle.py` + LEG 5b/6 backtest records instead.
- **Heartbeat:** seq advanced cleanly with 0-storm (sample seq 180 → 720+ visible in snapshots; age stayed ~0–0.5 s; state `running`).
- **Errors: 0** (events.log ERROR/Exception count 0; `session_summary.errors=[]`). Rejects 0; missed bars 0 (`bars_missed 0`, `missed_bar_episodes 0`).
- **Orders/fills: 0** (required for dry_run=true): `orders_placed 0, orders_rejected 0, fills 0`; BOOK panels (product + mode=T) `positions 0 pendings 0`.
- **Full stdout + console mirrored** to `06_RESEARCH/results/ops_density_smoke_20261020_121117/session1/` (config_effective.json, console_mirror.log, events.log, identity.json, kpi_records.jsonl, session_summary.json, session_stderr_and_stdout.log).

## 3. Session 2 — restart residual (approx 5 min, `--max-seconds 300`)

- Window 12:49:43.97 → 12:54:44.22 UTC (bound exit; polls 596; bars 1; **errors 0; orders 0**).
- **Cold dedup (F-7) documented:** fresh session spawns with in-memory dedup reset — startup batch runs the same funnel with **no persistent dedup suppressions**: same H4 20/6/3 + H1 22/8/3, **armed 3, duplicates 3, skipped_tracked 0** — same composition as session 1's first batch (dedup state is per-session in-memory; arms re-appear vs prior session as expected per F-7). Session 2's identity re-confirmed same DEMO terminal.
- Artifacts at `06_RESEARCH/results/ops_density_smoke_20261020_121117/session2/`.

## 4. PASS / FAIL ledger (ops, not research)

| Gate | Requirement | Result |
|---|---|---|
| Identity gate | DEMO + expected path + symbol | **PASS** (both sessions) |
| Session completes w/o crash/exception storm | clean exit | **PASS** (×2, bound exits) |
| errors=0 (non-fatal warnings only) | 0 errors | **PASS** |
| dry_run ⇒ zero orders | 0 | **PASS** |
| console armed ↔ detect.armed match | sampled boards | **YES** |
| ≥1 HTF batch processed | — | **PASS** (1 batch; second H1 boundary not inside the 25-min window — honest note) |
| HB healthy | seq advances, no stale storm | **YES** |
| **Overall** | — | **OPS_DENSITY_STATUS: PASS** |

Not-failed non-gates: EA GUI attach BLOCKED (owner-side observation pending) — heartbeat file contract is coherent; retire churn not observable on-window — lifecycle retirement is suite-pinned + backtest-proven (LEG 5b/6), Honesty note §F-7 done via restart residual instead.

## 5. Documented ops quirks (for the operator runbook, no gate effect)

1. **MT5 python API cooldown:** spawning a terminal then `shutdown()` leaves `terminal64.exe` running; an immediate respawn (≲60 s) can fail with `IPC initialize failed` (Windows/AV cooldown) — preflight retried with clean-up + spacing; the `.py` had to use a single-backslash `terminal_path` (the double-backslash JSON literal failed in one earlier attempt; single-backslash passes — keep as is).
2. **`events.log` clock labels** show local time with a `Z` suffix; parse timestamps from the JSON payloads (`stopped_utc`, `session_started_utc`, kpi `at`) when precision matters.

## 6. Return block

```
OPS_DENSITY_STATUS: PASS
TERMINAL_IDENTITY: PASS
ACCOUNT: DEMO 474608655 @ Exness-MT5Trial15
DURATION_S: 1500 (session 1; +300 s session 2 restart residual)
HTF_BATCHES: 1
ARMED_MAX: 3
ARMED_BOARD_MATCH: YES
HB_HEALTHY: YES
ERRORS: 0
ORDERS: 0  (expect 0 if dry_run — confirmed)
DRY_RUN: true
RESTART_SECOND_SESSION: DONE (F-7 cold dedup: arms re-appear, no persistent dedup state)
SUITE: NOT_RUN
LOGIC_CHANGED: NO
NOTE_PATH: 06_RESEARCH/OPS_DENSITY_SMOKE_NOTE.md
NEXT_READY: Architect live-promotion residual ruling | commit split
```
