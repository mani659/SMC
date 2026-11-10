# P1 Visual Level Fidelity Note

`LOGIC_CHANGED: NO`  
Scope: **Liquidity LEVEL labeling only** (Stage 0A level construction evidence). No sweep overlay, no displacement, no OB/FVG trade-quality audit, no trigger A–F, no expectancy, no P2. Read-only use of production detectors/constructors; no edits to `04_SRC/smc/**` or `locked_constants.py`.

## Goal

Provide human-scorable chart evidence from a frozen sample run to verify that **level construction labels** are correct on chart (code existence is not acceptance). If charts expose a systematic labeling issue, document it; **do not patch detectors in this pack** unless Architect directs a targeted fix.

Families covered (one evidence pack per family, scored independently):

1. **Session H/L** (Asia / London / NY UTC extremes on correct windows)
2. **PDH / PDL** (prior completed UTC day only; not current day)
3. **PWH / PWL** (prior completed week only; Monday-anchored)
4. **EQH / EQL** (clusters within `EQH_EQL_TOLERANCE = 4.5` pips; reject singles)
5. **Structural swings** (only `is_valid` swings per base-candle / §19 validity gate)

## Window & data

- **Primary exec window:** `2025-06-01T00:00:00Z` → `2025-11-30T23:59:59Z` (UTC), XAUUSD M1 parquet (`07_DATA/XAUUSD_M1.parquet`).
- **Warm-up:** from `2025-03-01T00:00:00Z` (sufficient history for prior-day/week references and H4 resampling context).
- Detection/counts run on the **full window**; charts are a **stratified sample** (capped per family) for human scoring. Run fails loud if data is missing or does not cover `exec_start`.

## Method (production constructors, no reimplementation)

Levels are emitted by the same production constructors used by `liquidity_scanner` / detection flow:

| Family | Constructor (as-called) | Detection series / notes |
|---|---|---|
| session | `smc.detection.session_levels.detect_session_levels(m1_exec, Timeframe.M1)` | M1 for true session extremes; rows with `formed_at` in exec window. Session name derived from UTC session windows (`smc.utils.timestamps`). |
| pdh_pdl | `smc.detection.periodic_levels.detect_periodic_levels(m1_all, Timeframe.M1, as_of=each UTC day start in exec)` → `PREVIOUS_DAY` rows | Prior completed UTC day extremes; deduped by formed extreme (`type,pool,level,formed_at`) across `as_of` evaluations. |
| pwh_pwl | `smc.detection.periodic_levels.detect_periodic_levels(m1_all, Timeframe.M1, as_of=each UTC day start in exec)` → `PREVIOUS_WEEK` rows | Prior completed week extremes (Monday-anchored); deduped by formed extreme. |
| eqh_eql | `smc.detection.eqh_eql_detector.detect_equal_levels(detect_swings(h4_all, Timeframe.H4), Timeframe.H4)` | Swings on H4; clusters within frozen 4.5-pip tolerance, ≥2 members; cluster extreme level (BSL = highest high, SSL = lowest low). `formed_at` in exec. |
| structural_swing | `smc.detection.structural_swing_detector.detect_swings(h4_all, Timeframe.H4)` filtered to `is_valid == True` | N-bar confirmation per production detector (Timeframe-driven); base-candle / §19 validity gate required. Emitted as `STRUCTURAL_SWING` liquidity levels (BSL swing highs / SSL swing lows). |

Reference: `smc.detection.liquidity_scanner.scan` is the canonical Phase 1 emitter; families are called directly here for per-family, per-chart evidence.

## Artifacts

Under `06_RESEARCH/results/p1_visual_levels/` (gitignored as research results):

- `p1_levels.csv` — all exported levels (full-window detection counts basis): `family, type, pool, level_price, timeframe, formed_at, session_name, constructor_source, note`
- `summary.json` — counts per family, sample sizes, chart counts, window, `level_csv_sha256`, constructors/modules, determinism (dual-run)
- `run.log` — execution log
- `charts/<family>/*.png` — per-family chart packs:
  - `charts/session/`, `charts/pdh_pdl/`, `charts/pwh_pwl/`, `charts/eqh_eql/`, `charts/structural_swing/`

Each chart includes: **family tag** in title, horizontal line at exact level price, vertical marker at `formed_at`, and caption with `type`, pool (BSL/SSL), timeframe, `formed_at`, session (when applicable), and constructor source. Context bars shown around formation to judge the extreme. Charts capped at **≤15 per family** with stratified sampling (spread across months and both BSL/SSL).

## How to score (human / Architect)

For each sampled chart, assign one label:

- **CORRECT** — level type, pool direction, price, and formation context match the rule (e.g. true session extreme in correct UTC window; PDH/PDL is the prior completed day, not current day; PWH/PWL prior completed week; EQH/EQL is a ≥2-member cluster within tolerance at cluster extreme; structural swing is a valid base-candle-confirmed swing, not a wick-only unconfirmed extreme).
- **PARTIAL** — level exists but labeling/context is imprecise or ambiguous in a way that matters (document why).
- **WRONG** — mislabeled (e.g. current-day high marked PDH, wrong session window, single point labeled EQH/EQL, invalid/wick-only swing labeled structural-valid, wrong pool/side).
- **UNCLEAR** — insufficient visual/context to judge.

**Pass bar (family-level, set by Architect):** enough CORRECT that the label can be trusted, and **zero systematic wrong class** (e.g. current-day high marked as PDH is a systematic failure). Suggested reference: ≥70% CORRECT on scored sample with no systematic wrong class — **Architect confirms acceptance per family**. No pass % is invented here.

**Program rule:** Code probe ≠ acceptance. Wrong labels → stop → fix (targeted, if directed) → re-chart → re-score → then next concept. **P2 (sweep interaction) is blocked until P1 labels are accepted.**

## Known limitations / notes

- **Series choice:** Session/periodic levels are computed on M1 to reflect true extremes; EQH/EQL and structural swings are computed on H4 (`Timeframe.H4`, production N-bar/validity) consistent with scanner-style structural detection. Chart candle context uses the corresponding series (M1 for session/periodic, H4 for eqh/structural).
- **Periodic dedupe:** `detect_periodic_levels` returns prior completed day/week levels valid `as_of` a reference; to enumerate instances over the window the script evaluates per UTC day start and dedupes by formed extreme. This preserves stable level instances but is an evidence-export choice (documented) — scoring should focus on whether the labeled extreme is the correct prior completed period.
- **Structural validity:** Only swings with `is_valid == True` (base-candle confirmation / §19 gate) are included in the structural family, per spec.
- **No trade semantics:** These charts evidence level formation/labeling only. They do not assert sweeps, displacement, POI/trade quality, triggers, or outcomes.

## Repro

```bash
PYTHONPATH=04_SRC python 06_RESEARCH/scripts/p1_visual_level_fidelity.py
```

Outputs: `06_RESEARCH/results/p1_visual_levels/{p1_levels.csv,summary.json,run.log,charts/<family>/*.png}`. Determinism: level CSV/rows compared across two in-process runs (see `summary.json.determinism`).

## Scoring log (to be filled by Architect)

| Family | CORRECT | PARTIAL | WRONG | UNCLEAR | Verdict | Notes |
|---|---:|---:|---:|---:|---|---|
| session |  |  |  |  |  |  |
| pdh_pdl |  |  |  |  |  |  |
| pwh_pwl |  |  |  |  |  |  |
| eqh_eql |  |  |  |  |  |  |
| structural_swing |  |  |  |  |  |  |

`LOGIC_CHANGED: NO`
