# P2a — Liquidity Pool Registry + Lifecycle + Frozen-Window Inventory

**Status:** IMPLEMENTED (additive module + tests + measurement). `LOGIC_CHANGED: NO` for detection.
**Date:** 2026-11-11
**Authority:** `06_RESEARCH/P2_LIQUIDITY_POOL_DESIGN.md` accepted with amendments **R1–R5**.

Detection mathematics (PDH/PDL, PWH/PWL, Session, Structural, EQH/EQL), triggers, risk, live and paper loops are untouched. This phase adds a thin pool package, its tests, and a read-only inventory.

## 1) Module paths + public API

| Path | Contents |
|---|---|
| `04_SRC/smc/liquidity/__init__.py` | package exports |
| `04_SRC/smc/liquidity/pool.py` | `PoolFamily`, `PoolSide`, `PoolStatus`, `PoolLevel`, `LiquidityPool`, builders, `inventory_sort_key` |
| `04_SRC/tests/test_liquidity_pool.py` | 15 dedicated tests |
| `06_RESEARCH/scripts/p2a_pool_inventory.py` | frozen-window inventory (research) |

Public surface:

- `PoolLevel(family, side, price, period_id, source_tf, formed_at, enter_at, exit_at=None, status=ACTIVE)` with `level_id == (family.value, side.value, period_id)` — **price is an attribute, never part of identity**.
- `LiquidityPool.add(level)` / `add_detected(...)` (hard-rejects EQH/EQL), `active_asof(asof)`, `inventory(asof)`, `apply_lifecycle(asof)`, `all_levels()`.
- Builders: `from_pdh_pdl`, `from_pwh_pwl`, `from_session(..., source_tf=Timeframe.M5)`, `from_structural`.

No MT5 imports, no wall clock, no ranking, no scoring, no sweep code.

## 2) Lifecycle table — implemented vs R2 residuals

| Family | R2 requirement | Implemented |
|---|---|---|
| PDH/PDL | enter next UTC midnight after day close; only current pair per side | **YES** `enter_at = day+1 00:00`; exit by supersession |
| PWH/PWL | enter next Monday 00:00 UTC; replaced by next week pair | **YES** `enter_at = monday+7 00:00` |
| Session | enter at session close; replaced by next same-session print | **YES** `enter_at` = session end hour from locked constants; **R1 source_tf = M5** |
| Structural | enter at §19 confirmation close; exit broken **or** superseded | **PARTIAL** — enter at confirmation bar close (`candles[confirmed_index].timestamp + tf`); supersession implemented; **broken-exit deferred** |
| All | exit on replacement | **YES** — `exit_at = successor.enter_at` (no new numbers) |

Two documented details:

1. **Weekend carry-over works by construction.** Only trading days generate PDH/PDL, so Friday's pair (enter Sat 00:00) stays active until the next pair enters Tuesday 00:00 — matching production "Monday sees Friday's levels" without a calendar table.
2. **Simultaneous structural confirmations coexist.** Two swings of the same side/TF confirmed on the same bar share an `enter_at`; neither supersedes the other (a zero-length exit is not a lifecycle). A non-chronological add still raises `ValueError`.

`status` is time-derived: `add()` never pre-marks `EXITED`; `apply_lifecycle(asof)` does when `exit_at <= asof`. `active_asof` recomputes from timestamps and never depends on the stored marker.

## 3) Session M5 provenance (R1) — proof

- **Test:** `test_session_source_tf_is_m5_and_enters_at_session_close` asserts `source_tf is Timeframe.M5`, `period_id == "2026-01-05_ASIA"` and `enter_at == 07:00 UTC`.
- **Test:** `test_sessions_of_the_same_day_coexist` proves Asia/London/NY are independent series (the session name is part of the supersession key), so a new Asia print does not evict London.
- **Inventory:** `summary.json.session_source_tf == "M5"`; all 390 BSL / 390 SSL session levels were produced by `detect_session_levels` on the **M5** resample (35,725 bars), never on H4.

## 4) Inventory results (frozen window, counts only)

Window `2025-06-01T00:00:00Z .. 2025-11-30T23:59:59Z`, warm-up from `2025-03-01T00:00:00Z`; 732 samples at 6-hour steps. Detection series: periodic + structural **H4**, session **M5**.

| Family / side | Distinct levels in window |
|---|---:|
| previous_day / BSL | 157 |
| previous_day / SSL | 157 |
| previous_week / BSL | 27 |
| previous_week / SSL | 27 |
| session / BSL | 390 |
| session / SSL | 390 |
| structural_swing / BSL | 40 |
| structural_swing / SSL | 47 |

- Registered levels: **1305** (all generated levels accepted; zero rejections after the simultaneous-confirmation fix).
- Max active at one instant: **14** (`2025-07-21T18:00:00Z`), by family `{"previous_day": 2, "previous_week": 2, "session": 6, "structural_swing": 4}` — consistent with 3 sessions × 2 sides + one current PD/PD pair + one PWH/PWL pair + live structural swings.
- `eqh_included: false`; `equal_highs_lows` is absent from `PoolFamily` entirely, and `add_detected` raises on it.
- Determinism: dual-run byte-identical summary; `active_counts_by_family.csv` SHA256 `f78d6207b705cfaccd57f877e60f20d1194605f68f116ed3809f54bf796e550a`.
- Periodic equivalence spot-check: **3/3 matched** `detect_periodic_levels(m1_all, M1, as_of)` PDH/PDL prices at the 25%/50%/75% dates, so H4-derived generation agrees with the production constructor.

Artifacts: `06_RESEARCH/results/p2a_pool_inventory/{active_counts_by_family.csv, sample_active_levels.csv, summary.json, run.log}`.

## 5) Explicit non-wiring

- `detection_driver`, `multi_tf_runtime`, `sweep_episode_coordinator`, triggers, risk, `live/`, `paper/`, `backtest/` are **unchanged** — no production path imports `smc.liquidity` yet.
- `liquidity_scanner.scan` is untouched (full suite green).
- No ranking, no scores, no family-priority trading logic. `inventory_sort_key` (R3: PWH/PWL > PDH/PDL > Session > Structural) is applied only to the sample CSV; `active_asof` remains chronological.

## 6) Residuals for P2b

1. **Sweep bounds (R4).** `detect_sweep` still bounds at `formed_at`; the pool must pass `start_index` from `enter_at` before any sweep attribution is trusted.
2. **Structural "broken" exit (R2).** Requires a locked break definition; only supersession is implemented.
3. **Session exit reading.** Implemented as "next same-session print"; the alternative R2 phrase ("end of session day") is not mixed in. Architect may switch.
4. **H1 duplicate provenance.** `level_id = (family, side, period_id)` collides across H4/H1, so H1 periodic/structural levels are not registered alongside H4 (design open question 8). Inventory uses H4 only.
5. **Unbounded tail.** The newest level of a series has `exit_at=None` by design; the inventory window truncates. No age cap exists (no locked number).
6. **No touch history.** One `swept_at` per level, matching `LiquidityLevel`; multi-touch ranking remains unimplemented (design §6).

## 7) Suite

`PYTHONPATH=. python -m pytest -q` → **1452 passed, 7 skipped** (includes the 15 new pool tests).

## Verification

- `locked_constants.py` diff: **empty**.
- Detection / trigger / risk / live / paper / orchestration diff: **empty** (only new package + new test + research script).
- EQH/EQL in pool: **none**.

`LOGIC_CHANGED: NO` (pool registry additive only; detection unchanged)
