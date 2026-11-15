# TRACK A — UNGATED MULTI-TF SWEEP LEDGER REPORT

> **OBSERVATION ONLY.** This ledger is an ungated density observation of
> liquidity sweeps on H4/H1 (+M5). It is **not** a signal, not a strategy,
> not POLICY_MTF_H4, not expectancy, not a quality or edge claim, and not
> expert-validated. No confirm path, no orders, no risk path was touched.

```text
TRACK_A_STATUS: PASS
WINDOW: 2025-09-01 → 2025-11-30 (UTC, frozen — identical to the P1/H4 event ledgers)
DEFS: A+B
H4_SWEEPS: 162
H1_SWEEPS: 761
M5_SWEEPS: 11,531
CHARTS: 6 (3 × H4, 3 × H1)
SUITE: 1342 passed
LOCKED_CONSTANTS_DIFF: empty
PROD_GATE_USED: NO
REPORT_PATH: 06_RESEARCH/TRACK_A_SWEEP_LEDGER_REPORT.md
NEXT: Architect score a small Track A sweep sample → coupling design-lock only after
```

## 1. Purpose and authority

Authority: Lead Architect "TRACK A — UNGATED MULTI-TF SWEEP LEDGER"
(prerequisite `PHASE0_STATUS: PASS`, recorded 2026-10-28 in
`06_RESEARCH/PHASE0_EVENT_SCORE_SHEET.md` / SESSION_HANDOFF 2026-10-28 (1)).

Emit SWEEP as a first-class observation stream on H4 and H1 (M5 included —
cheap, same machinery), independent of POI gates and LTF confirms, on the
same frozen window as the event ledgers.

## 2. Definitions used (exact code paths) — **DEFS: A+B, both ran**

**Primary sweep semantics (locked, unchanged):**
`04_SRC/smc/detection/sweep_detector.py` → `detect_sweeps`
(LOCKED_DECISIONS §2: the candle's WICK pierces the level and its BODY
closes back; a close beyond is a breakout, not a sweep; the `formed_at`
bound stops a level from being swept at its own forming bar; **at most ONE
sweep per level — no re-arm, no new subtypes**).

**Definition A — structural swing sweeps:** every valid §18/§19 swing from
`smc.detection.structural_swing_detector.detect_swings` (the identical
machinery as `06_RESEARCH/scripts/ungated_event_ledger_p1.py`, including
TF-native N and causal `known_at = max(pivot_index + N, §19 confirmed_index)`)
becomes a `LiquidityLevel` (`STRUCTURAL_SWING`; pool `BSL` for swing highs,
`SSL` for swing lows) the moment it is knowable. **Level-set choice
(documented):** *all valid swings*, not latest-only — the latest-only rule in
the structure ledger exists for BOS/CHOCH classification; every valid swing
is real liquidity, so each becomes a sweepable level once knowable. No new
geometry: pivot recovery reuses the ledger's own `_swing_pivot_index`.

**Definition B — explicit zone-bound sweeps:** zone bounds of prior event
rows from the SAME `ungated_event_ledger_p1` machinery — **imported, not
forked** (`_event_rows` called directly, so BOS/CHOCH/OB/FVG rows are
bit-identical provenance): FVG zone top/bottom (`POI_LEVEL`) and
`LAST_OPPOSITE_BEFORE_BOS` full-wick bounds (`ORDER_BLOCK_BOUNDARY`),
pool `BSL` = zone top / `SSL` = zone bottom, `formed_at` = the row's forming
bar open time, so the zone cannot sweep at its own bar.

**Direction labels (pool-side only, not an edge claim):** `BSL → SHORT`
(stops above highs run and rejected), `SSL → LONG` (stops below lows run
and rejected). Identification only; carry `pool` in the CSV for auditing.

## 3. Window, data, bar counts

Frozen window `2025-09-01 → 2025-11-30 UTC`, canonical M1 parquet
(`07_DATA/XAUUSD_M1.parquet`) → `resample_multi`, closed bars only (a bar is
dropped if its nominal close lies beyond the window), same causal
availability rules as the P1/H4 ledger extensions:

| TF | Closed bars | N (§27) |
|----|------------|---------|
| H4 | 402        | 5       |
| H1 | 1,488      | 5       |
| M5 | 17,840     | 3       |

Bar counts reconcile with `UNGATED_EVENT_LEDGER_H4_REPORT.md` (H4: 402) and
`UNGATED_EVENT_LEDGER_P1_REPORT.md` (H1: 1,488 / M5: 17,840).

## 4. Counts by TF × definition × direction (pool shown)

| TF | A BSL (SHORT) | A SSL (LONG) | A total | B BSL (SHORT) | B SSL (LONG) | B total | TF total |
|----|--------------|--------------|---------|---------------|--------------|---------|----------|
| H4 | 12           | 5            | **17**  | 69            | 76           | **145** | **162**  |
| H1 | 73           | 50           | **123** | 307           | 331          | **638** | **761**  |
| M5 | 1,611        | 1,523        | **3,134** | 4,165       | 4,232        | **8,397** | **11,531** |

- **Total rows: 12,454** (`events_sweep.csv`; SHA-256
  `167ebcc15c65a058b8090190af4e4722c8fa3a4162a5fc86ef189fd40b7dfacc` — matches
  `summary.json`, which is the reconciliation record).
- Per TF: sweep of almost every definition-B level geometry is far denser
  than swing sweeps, as expected (zone bounds are numerous and tight).
- Definition B produced sweeps on both source families; the CSV `level_type`
  column splits `poi_level` (FVG bounds) vs `order_block_boundary`
  (LAST_OPPOSITE wick bounds) vs `structural_swing` (A).

## 5. Comparison note — gated vs ungated (density ≠ quality)

The gated P1 confirmation engine re-run (2026-10-26 order-fix ruling) found
exactly **1 POI-linked sweep in the whole frozen 6m window** and 0
episodes→0 confirms. This Track A ledger, by contrast, records **162 H4
sweeps in 3 months** ungated. The difference is *definition and gating
density, not quality*: the product path requires a sweep of a tracked M8
POI extreme only, while these ledgers sweep every valid structural swing and
every FVG/OB-observation zone bound. **No count here may be read as an edge,
a hit rate, or a promotion argument.** It is the observation substrate that
lets the Architect score a sweep sample before any coupling design-lock.

## 6. Charts (scoring sample — not a completeness claim)

Selection rule (deterministic, documented): per TF (H4, H1) — the earliest
Definition-A sweep, the earliest Definition-B sweep, then the earliest
remaining; up to 3 per TF. Labels: `SWEEP (H4/H1) — <direction> @ <level>`
with the level's knowable time (index) and the sweep candle (index) marked.

| File | TF | Def | Pool/Dir | Level | Sweep close (UTC) |
|------|----|-----|----------|-------|-------------------|
| `charts/h4_sweep_a_01_h4-sweep-h4-a-000040-h-000075.png` | H4 | A | BSL/SHORT | 3673.645 | 2025-09-17 08:00 |
| `charts/h4_sweep_b_02_h4-sweep-h4-fvg-000016-top-000017.png` | H4 | B | BSL/SHORT | 3561.035 | 2025-09-04 00:00 |
| `charts/h4_sweep_b_03_h4-sweep-h4-fvg-000011-bot-000018.png` | H4 | B | SSL/LONG | 3520.215 | 2025-09-04 04:00 |
| `charts/h1_sweep_a_04_h1-sweep-h1-a-000006-h-000027.png` | H1 | A | BSL/SHORT | 3489.595 | 2025-09-02 07:00 |
| `charts/h1_sweep_b_05_h1-sweep-h1-fvg-000010-bot-000013.png` | H1 | B | SSL/LONG | 3473.725 | 2025-09-01 14:00 |
| `charts/h1_sweep_b_06_h1-sweep-h1-fvg-000010-top-000015.png` | H1 | B | BSL/SHORT | 3474.305 | 2025-09-01 16:00 |

M5 sweeps are recorded in the CSV/summary only (M5 charts not required by
the spec; M5 remains a noisy observation tier).

## 7. Bans honored

- No POLICY_MTF_H4 / confirm path / auto orders — `04_SRC` production code
  **untouched** except the additive test file (helpers only).
- `locked_constants.py` diff: **empty** (verified).
- Wick/close-back semantics unchanged — the locked `sweep_detector` is
  consumed as-is; no semantic tweak to raise counts.
- No sweep subtypes beyond the locked detector; one sweep per level; no
  re-arm invention.
- No Track B / sweep-coupling implementation — `sweep_episode_coordinator`
  and the multi-TF sweep episodes design remain design references only.

## 8. Tests / verification

- New focused tests: `04_SRC/tests/test_track_a_sweep_ledger.py`
  (4 tests — pool→direction labels, OB-origin causality, swing known-at
  causality, zone-bound provenance) — **4 passed**.
- Full suite (repo root, `PYTHONPATH=04_SRC`): **1,342 passed, EXIT=0**
  (1,338 prior + 4 new), including `test_review_merge_smoke.py`, which now
  finds `06_RESEARCH/results/track_a_sweep_ledger` as required.
- CSV row count (12,454) = `summary.json` `event_rows`; SHA-256 reconciled;
  no duplicate `event_id`s.
- Script: `06_RESEARCH/scripts/track_a_sweep_ledger.py`
  (`python -X utf8 06_RESEARCH/scripts/track_a_sweep_ledger.py`,
  default `--tfs H4,H1,M5`).
- Artifacts (ignored): `06_RESEARCH/results/track_a_sweep_ledger/`
  (`events_sweep.csv`, `summary.json`, `charts/`).

## 9. Governance ledger

Recorded: SESSION_HANDOFF (2026-10-28 (2)), POST_V1_ACTIVE_TODO, CHANGELOG
(2026-10-28 (2)). PHASE0 PASS is the recorded prerequisite (2026-10-28 (1)).

**NEXT = Architect scores a small Track A sweep sample the same way
(CORRECT/PARTIAL/WRONG/UNCLEAR, pre-registered thresholds) → only then a
coupling design-lock. No coupling design before that score.**
