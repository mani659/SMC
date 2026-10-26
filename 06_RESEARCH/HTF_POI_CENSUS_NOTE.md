# HTF POI CENSUS — FLOWCHART STEP 1 (READ-ONLY NOTE)

> **DIAGNOSTIC — NOT EDGE.**
> 1,093 unique POI episodes inventoried by TF and kind with the real
> product detection path — before any sweep/LTF/entry analysis. No
> POI was armed, no pillar run, no threshold moved, no production code
> touched. No table supports or refutes edge or licenses any filter.

**Date:** 2026-10-11 · **Authority:** Lead Architect Step-1 directive (research re-anchor: POI first).
**POI_CENSUS_STATUS: PASS** (script + artifacts + 4 new tests green; rerun-stable by construction — pure transforms of fixed inputs).
**LOGIC_CHANGED: NO** (detectors only CALLED with frozen params, under `04_SRC` + research tests).

---

## 1. What "POI" means in code for this census

A POI is a `smc.core.poi.POI`: a price zone (bounds + direction + TF)
carrying equal-weight model tags (`M1`–`M8`), emitted by one registry
model (`model.detect`) on a series prefix — with no timestamp (the
`created_at` field is wall-clock, never used), no validity (pre-pillar),
and no arm. An **episode** is the same side + same rounded geometry
re-detected across days, dated by first-seen day (daily rolling
prefixes); **raw** counts every daily-prefix emission (re-detects
included); **merged** applies the product `merge_overlapping` (same-
direction overlap, tag union) to first-seen POIs. Model tags accumulate
per episode (`all_tags`); the first-seen tag stands as the attribution.

## 2. Table by TF × kind (episodes in exec 2025-06-01 → 2025-11-30)

| Group | Raw in-window | Unique episodes | Merged | Direction L/S |
|---|---|---|---|---|
| H4 M1–M7 (registry) | 889 (M4 157 / M5 157 / M6 157 / M7 157 / M1 115 / M2 45 / M3 1) | **75** (M1 31 / M2 24 / M4 11 / M7 8 / M3 1 — first-tag attribution) | **25** | 46 / 29 |
| H1 M1–M7 (registry) | 889 (M4 157 / M5 314 / M7 157 / M1 113 / M2 43 / M6 104) | **196** (M1 90 / M2 37 / M4 35 / M7 29 / M5 3 / M6 2) | **67** | 111 / 85 |
| M8←H4 | 659 (ob 177 / ds 305 / fvg 177) | **659** | **98** | 369 / 290 |
| M8←D1 | 137 (ob 43 / ds 50 / fvg 44) | **137** | **35** | 86 / 51 |
| M8←W1 (deep history from 2021) | 26 (ob 9 / ds 9 / fvg 8) | **26** | **10** | 22 / 4 |
| **Total** | 2,600 emissions | **1,093 episodes** | 235 merged | — |

Kind language (no fabrication): M1–M7 rows carry MODEL TAGS — no
tag→kind map exists in code, so none was invented (M1 Origin, M2
Breaker, M3 CHOCH-retest, M4 QML, M5 extremes, M6 neckline, M7 shelf
per `MODEL_DESCRIPTIONS`); M8 rows carry their `m8_kind` facet
(ob / demand_supply / fvg).

## 3. Reuse-or-redetect decision (disclosed)

The H4/D1 review packs were **not** reused as inputs: H4 raw rows come
from an M8-only enumerator plus a validation-gated merged layer — a
different construction from product emission. This census re-detected
with the product path (`DetectionDriver.stage0` + `detect_pois` per
daily prefix, registry M1–M8 with no HTF feed so M8 stays silent;
M8 separately per HTF input via `_zones` + `collapse_episodes`).
Cross-check: the census M8-H4 set is a strict superset of the pack's
raw rows by exactly **one** zone (LONG 4204.348–4230.349
demand_supply; window-edge membership — disclosed, not chased).
Pack-merged (3, validation-gated) vs census-merged (98, geometric) are
different operations — the gap between them is pillar rejection, now
visible as a number.

## 4. Readings (descriptive only — DIAGNOSTIC)

- **Re-detection is the norm, episodes the exception:** 889 raw → 75
  episodes (H4), 889 → 196 (H1). The identical 157-counts across models
  are the same zones re-fired ~daily (first-seen attribution + tag
  union in `all_tags`; dominant signature M1+M7 on 89 episodes).
- **M5/M6 tags ride along:** 157 + 157 raw H4 emissions, zero
  M5/M6-first episodes (H1: 3 + 2) — their geometries were always
  already seen under another tag. M3 fired once on H4, never on H1.
- **M8 dominates episode counts** (822/1,093 = 75%) and collapses hard
  under geometric merge (659 → 98 on H4 — the same overlap density
  behind the 99.9% zone-blanket finding).
- **M8 emits on W1** (26 episodes from deep history) — small but
  nonzero; M1–M7 run on H4+H1 only (the product's detection TFs), D1/W1
  emit via M8 only.
- Zero model skips across ~700 prefix runs; zero M8-tagged POIs in
  registry runs (starved-HTF equivalence holds); 15 thin early-May
  prefixes skipped by the frozen 60-bar floor (out-of-window dates).

## 5. Limitations (binding on reuse — DIAGNOSTIC)

- First-seen dating at day granularity; formation inside a day untimed.
- Thin-history early-May prefixes behave like product cold-start
  (out-of-window dates only); W1-deep load applies to the M8-W1 leg.
- Episode attribution is first-tag-wins (full tag unions in
  `all_tags`); merge runs on first-seen POIs.
- Single 6m window, single feed; no gate, no threshold, no live rule
  follows.

## 6. Pointer: NEXT = POI-linked sweep rate (Step 2)

The episode ledger (`results/htf_poi_census/poi_episodes.csv`, 1,093
rows with bounds + direction + TF) is the POI side of the Step-2 join:
of these POIs, how many are swept (pierce + close-back) in-window —
not "how many sweeps exist in the universe."

---

**Artifacts:** `06_RESEARCH/scripts/htf_poi_census.py` (new) ·
`06_RESEARCH/results/htf_poi_census/` (`poi_episodes.csv` 1,093 rows,
`summary.json` with loader rules, raw/episode/merged counts, skips,
pack comparison) · tests `04_SRC/tests/test_htf_poi_census.py` (4).
