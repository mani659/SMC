# L1 — H4 Sweep Fidelity Pack (sweep-only)

**Layer:** L1 (HTF sweep fidelity, per TF, independent)  
**TF:** H4 (first in L1 order per `06_RESEARCH/LAYERED_FIDELITY_PLAN.md` §4)  
**Date:** 2026-11-10  
**Authority:** Lead Architect; plan `06_RESEARCH/LAYERED_FIDELITY_PLAN.md` (ACTIVE)  
**LOGIC_CHANGED:** NO — no 04_SRC strategy/threshold/tier/trigger edits; no `locked_constants.py` changes.

## Scope / non-scope (binding)
- **In scope:** independent H4 liquidity-sweep detection + chart pack + human-scoreable ledger (observation only).
- **Out of scope:** LTF confirmations, orders, trades, PnL, expectancy, L2–L5, any coupling to menu/order paths, and any threshold/pass-rate invention.

## Window
- **Preferred exec window (aligned with expert/structure packs):** `2025-06-01T00:00:00Z` → `2025-11-30T23:59:59Z` (requested). Data coverage confirmed; no closest-available substitution required.
- **Warm-up (documented):** load from `2025-03-01T00:00:00Z` (inclusive in loader range) to allow H4 level formation/history before exec start. Same exec-window convention intended for all later L1 TFs.
- **Actual data observed:** M1 `2025-03-02T23:00:00Z .. 2025-12-01T23:59:00Z` (268,108 bars) → H4 resampled `2025-03-02T20:00:00Z .. 2025-12-01T20:00:00Z` (1,208 bars). Exec-window event filter applied on sweep bar timestamp within the requested exec range.

## Method (existing detection APIs only, evaluation mode)
No new sweep rule invented. Pipeline used (as-is):
1. **Load M1:** `06_RESEARCH/scripts/plan_complement_ledger.py:load_m1` from `07_DATA/XAUUSD_M1.parquet` (UTC, ascending).
2. **Resample H4:** `smc.data.resample.resample_ohlcv(m1, Timeframe.H4)` — deterministic UTC-aligned bins, bar stamp = bin open, no invented bars.
3. **Phase 1 liquidity levels (H4):** `smc.detection.liquidity_scanner.scan(h4, Timeframe.H4, include=ALL_FAMILIES)` where `ALL_FAMILIES=("session","periodic","equal","structural")` (`04_SRC/smc/detection/liquidity_scanner.py`). Structural levels are emitted only for swings that passed the §19 validity gate (scanner behavior). POI/boundary families that depend on Phase 2+ POI zones are not part of this Phase 1 scan and are out of scope here.
4. **Sweep detection:** `smc.detection.sweep_detector.detect_sweeps(h4, levels)` (`04_SRC/smc/detection/sweep_detector.py`) — first confirmed sweep per level, levels scanned only after `formed_at` (when set), results in candle order.
5. **Exec-window filter:** keep sweeps whose H4 candle timestamp falls within the requested exec window. Dual-run determinism check (events hash + counts) required to be stable.

## Locked definition cited (exact paths; not reinvented)
- **Valid liquidity levels / sweep classification (locked):** `00_LOCKED/LOCKED_DECISIONS.md` — Liquidity Sweep Detection / valid liquidity level families and sweep principles for Stage 0A (e.g. structural swing/session/periodic/equal-high-low level families and the wick-pierce + body-close-back sweep principle as defined there; POI/boundary sweep types listed in that section are Phase 2+ objects and are **not** produced by the Phase 1 `liquidity_scanner.scan` used in this pack).
- **As-coded confirmation rule used (evaluation, no rule change):** `04_SRC/smc/detection/sweep_detector.py` module contract — *“A sweep of a liquidity level is confirmed by a single candle that: BSL pool … WICK pierces ABOVE the level (`high > level`) and its BODY closes back BELOW it (`close < level`); SSL pool … WICK pierces BELOW the level (`low < level`) and its BODY closes back ABOVE it (`close > level`). … A candle that closes beyond the level (a genuine breakout) is NOT a sweep.”* First sweep per level; `formed_at` bound respected (`detect_sweep` / `_first_after`).
- **Structural swing/validity context for scanned structural levels:** `04_SRC/smc/detection/structural_swing_detector.py`, `04_SRC/smc/detection/swing_validator.py`, and `00_LOCKED/LOCKED_DECISIONS.md` (swing/validity sections referenced by detector, incl. §19/§27 semantics as implemented) — scanner emits only §19-valid structural swings as `STRUCTURAL_SWING` levels.

Directional label in ledger: `pool=BSL` (buy-side liquidity above) + wick above / close below ⇒ recorded as `BEARISH_SWEEP_BSL`; `pool=SSL` ⇒ `BULLISH_SWEEP_SSL` (derived from pool+confirmation semantics only, no invented rule).

## Results (exec window)
- **Events (exec window):** `N_SWEEPS = 753` total
  - **Bear BSL (downside rejection of BSL):** 394
  - **Bull SSL (upside rejection of SSL):** 359
- **Series-wide (for context):** levels scanned 1316; sweeps detected (all series, incl. outside exec window) 1120.
- **Determinism:** dual-run identical — `hash=2515fdfdf3022f36a5c7debb70eb06409bfcb09b16195d1bc2b72b621d177f90`, counts stable (`deterministic=True`).

## Sample & charts
- **Sample size:** 40 (stratified bull/bear + time-spread, seed `20260601`; bull_ssl=19, bear_bsl=21). If total &lt; 40, all would be charted (not applicable).
- **Chart contents:** H4 candles around event, sweep-bar marker, swept level line, and caption `(ts, direction, pool, level_type, level)`. Tag is **SWEEP (H4)** only — no POI/trade overlay.
- **Charts generated:** 40 PNGs.

## Artifacts (gitignored under results/)
- `06_RESEARCH/results/l1_h4_sweep_fidelity/events_h4_sweep.csv` — full exec-window ledger (753 rows)
- `06_RESEARCH/results/l1_h4_sweep_fidelity/summary.json` — counts, window, determinism hash, APIs/families
- `06_RESEARCH/results/l1_h4_sweep_fidelity/charts/` — 40 sampled H4 sweep charts
- `06_RESEARCH/results/l1_h4_sweep_fidelity/run.log` — run trace

## How to score (human gate)
Score each sampled chart/event against the locked definition cited above:
- **CORRECT** — the marked bar clearly performs the locked wick-pierce + body-close-back sweep of the marked H4 liquidity level (and the level/timing read as a valid H4 sweep per lock).
- **PARTIAL** — a real/related sweep is present but marking/timing/level or classification is materially imperfect or ambiguous.
- **WRONG** — not a sweep per the locked rule (e.g. breakout/close beyond, wrong level, or no genuine sweep).
- **UNCLEAR** — insufficient visual/context evidence to decide from the chart/ledger.

**No LTF, no trades, no PnL. No CORRECT-rate pass threshold is invented here.** Human score gate required after charts; the Architect sets the CORRECT-rate threshold after the first L1 pack (per `LAYERED_FIDELITY_PLAN.md` §4 L1). This note records observations only, not a PASS/FAIL quality verdict.

## Repro
```bash
PYTHONPATH=04_SRC python 06_RESEARCH/scripts/l1_h4_sweep_fidelity.py
```
Script: `06_RESEARCH/scripts/l1_h4_sweep_fidelity.py`. Suite not modified/run for this docs+research-only pack (no 04_SRC/test changes).
