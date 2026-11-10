# L1 — H4 Stage 0A Enriched Pack (Sweep × Displacement × POI link)

**Layer:** L1 (HTF fidelity, enriched chain observation)  
**TF:** H4 (primary; D1/H1 only if Architect asks later)  
**Date:** 2026-11-10  
**Authority:** Lead Architect / Design Architect; `06_RESEARCH/LAYERED_FIDELITY_PLAN.md` (ACTIVE)  
**LOGIC_CHANGED:** NO — read-only use of existing detectors/scanners/POI emitters; no 04_SRC decision-path edits; no `locked_constants.py` changes.

## Scope / non-scope (binding)
- **In scope:** measurement rows/charts for H4 sweep events enriched with as-coded displacement evaluation and explicit POI linkage attempt (M8 H4 zones), plus chain classification and population rates.
- **Out of scope:** expectancy, LTF wiring, orders, trades, PnL, entry/SL/TP tuning, OPT-*, L2–L5. No threshold/pass-rate invention.

## References
- **Stage 0A code↔flowchart map:** `06_RESEARCH/STAGE_0A_CODE_FLOWCHART_MAP.md` (intent, inventory, families, sweep/displacement rules, POI link honesty, gaps).
- **Prior naked-sweep baseline:** `06_RESEARCH/L1_H4_SWEEP_FIDELITY_NOTE.md` (pierce+close-back on scanned levels only; mostly PARTIAL vs full Stage 0A chain).

## Window (frozen, fail-loud if missing)
- **Exec:** `2025-06-01T00:00:00Z` → `2025-11-30T23:59:59Z` (UTC).
- **Warm-up (documented, same convention as L1 H4 pack):** load from `2025-03-01T00:00:00Z`.
- **Observed coverage:** M1 `2025-03-02T23:00:00Z..2025-12-01T23:59:00Z` (268,108 bars) → H4 `2025-03-02T20:00:00Z..2025-12-01T20:00:00Z` (1,208 bars). No substitution required.

## Join rules (explicit; deterministic)
Implemented in `06_RESEARCH/scripts/l1_h4_stage0a_enriched.py` (docstring + `summary.json.join_rules`). No new ATR bands invented for joining; existing geometry helpers used (`smc.core.zone.Zone.contains`).

1. **Sweep row:** one row per exec-window `SweepResult` from `smc.detection.sweep_detector.detect_sweeps` on Phase 1 H4 levels (`scan(..., include=ALL_FAMILIES)`). Stable `event_id` derived from `candle_index_h4 + pool + level_type + level_price`. `sweep_flag=Y`, `sweep_id=sweep@{candle_index}`.
2. **Displacement (per same sweep, as-coded):** `smc.detection.displacement_checker.check_displacement` with direction `SSL→LONG`, `BSL→SHORT`; BOS level = most recent prior structural swing extreme of move direction before sweep (`smc.poi.base_model.most_recent_swing`, mirrors `DetectionDriver._displacement_for_sweep`); pre-sweep ATR and FVGs hoisted (value-equivalent). `displacement_flag = Y` if `result.passed` else `N`; `UNKNOWN` + reason if no prior swing extreme, magnitude/ATR unavailable, or checker error. Magnitude/ATR/BOS/FVG fields recorded only when provided by detector (never invented).
3. **POI link (M8 H4 zones, as-emitted):** source `smc.poi.models.m8_htf_demand_supply.M8HtfDemandSupply(Timeframe.H4, htf_candles={H4:h4}).detect(h4, swings, levels)` → H4 M8 POIs (kinds `ob|demand_supply|fvg`). `poi_link=LINKED` if any POI zone **contains** the swept liquidity level price (inclusive, `Zone.contains`, point containment = no extra tolerance band) **AND** direction compatible: `SSL/BULLISH_SWEEP_SSL` ↔ `LONG` (demand-side) POI, `BSL/BEARISH_SWEEP_BSL` ↔ `SHORT` (supply-side) POI. If multiple qualify, deterministic tie-break: smallest `zone.height`, then `m8_kind` priority `ob > demand_supply > fvg`, then zone bounds, then `stable_poi_key`.
4. **Bar equality:** sweep and displacement share the same sweep candle (`candle_index_h4` / bar). POI join is geometric (zone contains swept level), not bar-stamped.
5. **Stability note (research-only, no 04_SRC change):** core `POI.id` is UUID per emission; this measurement uses `stable_poi_key` derived from zone geometry + kind + direction for deterministic rows/hashes.
6. **Additional rows:** `ORPHAN_POI` emitted for H4 M8 POIs with no linked sweep in exec window. `DISPLACEMENT_WITHOUT_SWEEP` is a defined chain class but not observed/emitted by this sweep-led pipeline (displacement evaluated per sweep only).

## Chain classes (derived)
- `SWEEP_ONLY` — sweep Y, displacement N/UNKNOWN, POI NONE
- `SWEEP_PLUS_DISPLACEMENT` — sweep Y, displacement Y (as-coded passed), POI NONE
- `SWEEP_PLUS_POI` — sweep Y, displacement N/UNKNOWN, POI LINKED
- `FULL_0A` — sweep Y, displacement Y, POI LINKED (all known-true by this measurement)
- `DISPLACEMENT_WITHOUT_SWEEP` — (defined; none observed)
- `ORPHAN_POI` — POI with no sweep in join window

## Population summary (exec window)

**Pipeline counts:** swings 138, Phase 1 levels 1316, sweeps (all series) 1120, sweeps (exec) 753, M8 H4 POIs 6, H4 FVGs 280.  
**Rows:** 754 total = 753 `SWEEP_EVENT` + 1 `ORPHAN_POI`.

### Counts by chain_class
| chain_class | count |
|---|---:|
| `SWEEP_ONLY` | 576 |
| `SWEEP_PLUS_DISPLACEMENT` | 149 |
| `SWEEP_PLUS_POI` | 23 |
| `FULL_0A` | 5 |
| `ORPHAN_POI` | 1 |

### Counts by pool_family (level_type / row family)
| pool_family | count |
|---|---:|
| `SESSION` | 684 |
| `STRUCTURAL_SWING` | 63 |
| `EQUAL_HIGHS_LOWS` | 6 |
| `(none)` (orphan POI row) | 1 |

### Sweep-chain rates (denominator = 753 sweep rows)
| measure | value |
|---|---:|
| Displacement Y | 154 (20.4515%) |
| Displacement N | 599 (79.5485%) |
| Displacement UNKNOWN | 0 (0.0%) |
| Sweeps with POI link | 28 (3.7185%) |
| `FULL_0A` (sweep + displacement Y + POI linked) | 5 (0.6640%) |

**Determinism:** dual-run identical, hash `884fe366f3a4a5c062b3a0605bcd68a39886257190438192691ba99084d981ad` (`deterministic=True`).

## Chart sample
- **Charts:** 40 (stratified by `chain_class` + POI link, seed `20261110`), preferring mix of `FULL_0A`, `SWEEP_PLUS_DISPLACEMENT`, `SWEEP_PLUS_POI`, `SWEEP_ONLY`, linked vs none.
- **Layers:** H4 candles, swept level line, sweep-bar/wick marker, displacement annotation (flag/magnitude_atr,bos,fvg when available), linked M8 POI zone rectangle (when linked). Caption shows `chain_class`, families/types, displacement/POI info (human-readable tags, not only enums).

## Scoring rubric for humans (enriched charts)
Score each sampled enriched chart/row against the Stage 0A intent as mapped in `06_RESEARCH/STAGE_0A_CODE_FLOWCHART_MAP.md` and the locked/as-coded definitions cited there:

- **CORRECT_0A** — credible master/structural liquidity pool context, real sweep of that level per locked wick-pierce+close-back rule, displacement sense credible (impulsive follow-through consistent with BOS/FVG/magnitude as-coded), and linked POI (if shown) fits the zone/chain plausibly.
- **PARTIAL_0A** — chain is partly credible but one or more elements are weak, ambiguous, mis-joined, or incomplete (e.g. sweep real but displacement/POI link or pool quality doubtful).
- **WRONG_0A** — not a credible Stage 0A chain (e.g. not a real sweep/breakout, displacement clearly absent/misread, POI link spurious, or pool not meaningful).
- **UNCLEAR** — insufficient visual/context evidence to decide.

**No pass percentage invented.** Architect scores after charts; this note reports measurements only (not a PASS/FAIL quality verdict).

## Artifacts (gitignored under results/)
- `06_RESEARCH/results/l1_h4_stage0a_enriched/events_stage0a_h4.csv`
- `06_RESEARCH/results/l1_h4_stage0a_enriched/summary.json`
- `06_RESEARCH/results/l1_h4_stage0a_enriched/charts/` (40)
- `06_RESEARCH/results/l1_h4_stage0a_enriched/run.log`

## Repro
```bash
PYTHONPATH=04_SRC python 06_RESEARCH/scripts/l1_h4_stage0a_enriched.py
```
Suite not modified/run for this docs+research-only pack (no 04_SRC/test changes). `LOGIC_CHANGED: NO`.
