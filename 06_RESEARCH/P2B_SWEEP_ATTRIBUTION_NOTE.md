# P2b — Sweep Attribution (enter_at-safe) + Co-location Census

**Status:** IMPLEMENTED (additive attribution module + tests + measurement). Detection unchanged.
**Date:** 2026-11-11
**Authority:** `06_RESEARCH/P2_LIQUIDITY_POOL_DESIGN.md` (R1–R5), `06_RESEARCH/P2A_POOL_REGISTRY_NOTE.md` (P2a accepted).

## 1) Detector path reused

| Piece | Path | Reused how |
|---|---|---|
| Sweep definition | `04_SRC/smc/detection/sweep_detector.py` → `detect_sweep(candles, level, start_index=0)` | Called directly; **no second sweep definition was forked** |
| Pool registry | `04_SRC/smc/liquidity/pool.py` → `LiquidityPool.active_asof`, `PoolLevel.is_active_at` | Active-set membership for every hit |
| Stage-0 reference | `04_SRC/smc/orchestration/detection_driver.py` → `stage0()` calls `detect_sweeps(candles, levels)` | Not modified; the pool path mirrors its semantics |

Detector semantics preserved exactly: BSL = wick pierce above **and** body close back below; SSL = wick pierce below **and** body close back above. `detect_sweep` stops at the first qualifying bar per level.

### The lookahead trap, stated once

`detect_sweep` bounds its scan with `max(start_index, _first_after(candles, level.formed_at))`. For pool levels that bound is wrong. `LiquidityLevel.formed_at` is the **extreme bar**: for PDH/PDL it sits inside the prior completed day, and for structural swings it is the base candle that precedes §19 confirmation. Scanning from `formed_at` therefore lets a bar that traded *before* the level was knowable register as its sweep. P2b never forwards `formed_at` to the detector — the adapter level is built with `formed_at=None` and the explicit `start_index` is the only bound.

## 2) start_index rule + synthetic proof

**Rule (R4):** `start_index = first bar index with timestamp >= level.enter_at` on the series the level's `source_tf` refers to. If `enter_at` is after the series end the level is `not_applicable` (skipped and counted, never a silent zero). Unordered series raise `ValueError` (fail-closed).

Proof by test (`04_SRC/tests/test_liquidity_sweep_attribution.py`):

| Test | Proves |
|---|---|
| `test_resolve_start_index_is_first_bar_at_or_after_enter_at` | index mapping, including inter-bar times and past-series-end → `None` |
| `test_pierce_before_enter_at_is_ignored` | a bar that pierces **before** `enter_at` produces **no** hit |
| `test_pierce_after_enter_at_is_a_hit` | the same pierce after `enter_at` produces exactly one hit at the right index |
| `test_scan_starts_at_enter_at_not_formed_at` | with `formed_at` far earlier than `enter_at`, `start_index_used == enter_at` index and only the later pierce counts |
| `test_attribution_uses_pool_builder_enter_at` | end-to-end: a PDH from `from_pdh_pdl` has `enter_at` = next UTC midnight, and the scan bound lands there |
| `test_resolve_start_index_fails_closed_on_unordered_series` | loud failure on poisoned input |

## 3) Attribution API surface

`04_SRC/smc/liquidity/attribution.py` (exported from `smc.liquidity`):

```python
SweepHit(family, side, period_id, price, sweep_bar_ts, sweep_bar_index,
         direction, enter_at, start_index_used)   # level_id property
AttributionReport(hits: tuple[SweepHit, ...], not_applicable: tuple[PoolLevelId, ...])

resolve_start_index(series, enter_at) -> int | None
attribute_sweeps(pool, series, *, levels=None) -> AttributionReport
sweeps_on_bar(pool, series, bar_index) -> list[SweepHit]
```

Behavioural guarantees:

- Active set only: a hit is kept only if `level.is_active_at(hit_bar_ts)` (equivalent to `active_asof` at that bar, evaluated per level).
- **All** hits are emitted. When one bar sweeps several active levels, every hit is returned in deterministic `(bar_index, family, side, period_id)` order — no winner is selected, because that is the ranking decision that is not frozen.
- `direction` follows the existing driver mapping: SSL sweep → `long`, BSL sweep → `short`.

## 4) Measurement results (frozen window, counts only)

Window `2025-06-01T00:00:00Z .. 2025-11-30T23:59:59Z`; pool built exactly as in P2a (periodic + structural on H4, session on M5). Cadence: **event-driven** — one first-sweep scan per registered level.

| Metric | Value |
|---|---:|
| Levels registered / scanned | 1305 / 1305 |
| Total hits | **637** |
| Bars with ≥1 hit | 590 |
| Bars with ≥2 hits | **42** |
| Max hits on one bar | **3** |
| EQH/EQL hits | **0** (structurally impossible — absent from `PoolFamily`) |
| Not-applicable levels | 0 |

| Family / side | Hits |
|---|---:|
| previous_day / BSL | 54 |
| previous_day / SSL | 51 |
| previous_week / BSL | 16 |
| previous_week / SSL | 11 |
| session / BSL | 253 |
| session / SSL | 216 |
| structural_swing / BSL | 19 |
| structural_swing / SSL | 17 |

Series split: H4 levels 525 → 168 hits; M5 session levels 780 → 469 hits.

Determinism: dual-run byte-identical `summary.json` (SHA256 `3869955209349e0493e0c6d5184539fc8c5493fdaace62ec8c03286e733b8851`) and `hits_by_family.csv` (`c0980032692b1581fa1b466a913b57bd7b7bab1facca3fa6ce6ccdf6f411ec5f`).

## 5) Co-location findings (descriptive only)

- 590 distinct bars produced 637 hits, so most sweep bars carry a single level.
- 42 bars (~7% of hit bars) carried two or more simultaneous pool sweeps; the maximum seen is 3.
- Session levels dominate both the population (780 of 1305) and the hit count (469 of 637), which is expected given one pair per session per day over six months.
- **No ordering or priority claim is made from these counts.** Whether co-located sweeps deserve arbitration is exactly the P2c ranking question, and these frequencies alone cannot settle it.

## 6) Residuals

1. **Structural "broken" exit** — still unimplemented (needs a locked break definition); attribution uses enter/exit as built in P2a.
2. **No live wiring** — nothing imports `smc.liquidity` from detection, orchestration, triggers, risk, live or paper.
3. **Ranking not frozen** — no scores, no winner selection, no family priority.
4. **H4/H1 duplicate provenance** — inventory and attribution use H4 only; the identity collision remains design open question 8.
5. **Sweep cadence** — event-driven first-sweep-per-level, matching `detect_sweep`; repeated sweeps of the same level are not tracked (single `swept_at` semantics).
6. **Windows are fixed** — no walk-forward yet; these are census numbers, not performance.

## 7) Suite / bans checklist

- `PYTHONPATH=. python -m pytest -q` → **1463 passed, 7 skipped** (26 liquidity tests: 15 P2a + 11 P2b).
- `locked_constants.py` diff: **empty**.
- Detection / trigger / risk / orchestration / live / paper diff: **empty** (only `smc/liquidity/*` additive + new test + research script).
- EQH/EQL in pool or hits: **none**.
- Pre-`enter_at` pierce ignored: **proven by test**.
- No expectancy, edge, optimal-stop or frequency claim made.

`LOGIC_CHANGED: NO` (attribution additive; detection unchanged)
