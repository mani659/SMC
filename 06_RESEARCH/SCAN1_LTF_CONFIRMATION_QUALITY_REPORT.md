# SCAN 1 — LTF Confirmation Quality (1A no-POI baseline vs 1B product link)

**Status: measurement only — DIAGNOSTIC CENSUS, NOT a trade claim.**
No threshold, C3, TP/SL, pillar, or trigger-definition change was made or proposed;
`locked_constants.py` untouched (diff empty). Window, load rule, trigger code, and
scan-horizon rule are all imported from existing frozen sources; nothing was
re-implemented.

---

## 1. Window + methods (1A vs 1B — no ambiguity)

**Window (frozen, identical for both layers and for product_1y):**
- Exec: **2024-11-01 → 2025-10-31 UTC** (exec-to inclusive of the FULL last day —
  the phase3 convention `_parse_day(exec_to) + 1d − 1min`; M5 census = **70,885
  bars**, byte-consistent with the product_1y segment tiling, whose `bars_m5`
  sums to exactly 70,885).
- Load/warm-up: **2024-09-01** (61 days before exec start), same as product_1y.
  M5 evaluation starts at exec start (no M5 warm-up) — the product's own
  convention; the loaded window only feeds HTF/series construction upstream.
- Source: `07_DATA/XAUUSD_M1.parquet` → `resample_multi` → M5 (the same path the
  product_1y / Stage3 packs use).

**Scan 1A — NO POI filter (baseline detector census).**
Question: *does the structure exist / does the detector fire?*
- NO requirement that a POI be armed; NO product menu / one-story gate.
- PRODUCTION trigger code imported and evaluated as-is (the six locked trigger
  classes + `TriggerRouter.eligible_types`; evaluation path identical to
  `stage3_trigger_visibility` Pass 2: `TriggerContext(candles/swings prefix
  through bar, from_bar, hints=SeriesState)`).
- Every M5 bar × both directions × all six triggers, against a synthetic M8 POI
  whose sentinel zone spans **[0, 1e6]** — zone BOUNDS never accept/reject
  anything; direction comes from the synthetic zone (both directions evaluated;
  the direction that fires is the geometry's own).
- Scan-horizon rule: `from_bar = max(0, bar − poi_give_up_bars())` (20 M5 bars —
  existing frozen constant, imported, not re-typed).
- Dedupe: one completion per (trigger, direction, signal.data geometry).
- Dual-run: the full census is computed **twice in-process**; per-trigger counts
  must match (fail-loud otherwise). Full byte-identity dual run was judged
  unnecessary at this layer: the census is deterministic single-threaded and the
  cheap count check already covers the risk (documented choice per engagement
  spec).
- HARD RULE honoured: 1A never calls product arm/route/fill — detector/eval only.
- Recorded but flagged: under the sentinel zone, F's FR-3.1 entry anchor always
  re-anchors to a zone edge (`entry_degenerate`) — F entries in 1A are census
  geometry only; A/D/E entries are geometry-derived and meaningful.

**Scan 1B — WITH POI / product link.**
Question: *of the fires, which attach to an accepted zone story, and which still
never become a routed/filled plan?*
- Universe: the product-linked armed-POI records from the segmented 1y menu
  census (`product_1y_one_story/run1/{nov24..oct25}/armed_records.json`,
  armed per segment 193–462, total 3,731 non-additive segments), **real zone
  bounds** from each record; no new thresholds.
- For each armed POI: the SAME Stage-3 trigger inventory over its product
  horizon window `[arm, arm + LA_M5_BARS]` (20 M5 bars, via
  `ltf_confirmation_pack.lookahead_window`), with TWO synthetic M8 wrappers
  (LONG and SHORT) carrying the POI's real bounds; direction evaluated both ways
  (armed records export no direction; validated against fills' product
  directions — see §6).
- Lifecycle mapping (explicit; verified premise: `armed_records.routed == true`
  ⇔ the filled-POI set, exact match all 12 segments, fail-loud in code):
  - **FILLED** — armed POI whose routed order filled (= trades.csv POI set;
    239 total, reconciled to product_1y fill mix, fail-loud).
  - **ROUTED_NOT_FILLED** — winners that reached the order seam but never
    filled. **AGGREGATE ONLY** (submitted-unplaced 33 + placed-unfilled 13 =
    46): per-POI placed flags are not exported by the 1y artifacts.
  - **COMPLETED_NOT_ROUTED** — armed POI with ≥1 M5 trigger completion in its
    window whose menu episode never routed (includes menu-guard intake drops,
    580 aggregate, and never-won episodes).
  - **ARMED_NO_COMPLETION** — armed POI with ZERO M5 trigger completions in its
    window (armed, but the M5 geometry never completed — armed from
    M15/H1/H4/D1 detection; menu confirmation may occur on other TFs).
  - **OPEN_SCAN_ROUTED** — non-exclusive marker = winner set (865 aggregate).
- Cross-tabs: 1A vs 1B by trigger (capability vs product use); among POI-linked
  completions, filled vs died in lifecycle; fills (239) trigger mix reconciled
  to product_1y (`F 226 / A 13`), **FAIL LOUD** on mismatch.

**M1:** not scanned (`m1_scan = 0`). Trigger code never reads a timeframe; an M1
pass would duplicate the same TF-agnostic windows and double-count — the
STAGE3_TRIGGER_VISIBILITY convention. Menu confirmation TF additionally varies
by tier (M1/M5/H1), so exact-geometry reconciliation between the M5 inventory
and the 239 fills is NOT assumed (see §6).

## 2. 1A baseline table (A–F counts, proof-field rates)

Census: **2,497 unique completions** over **70,885 M5 exec bars**
(2024-11-01 → 2025-10-31, full days). Dual in-process passes: counts equal
(PASS). Runtime ≈ 40 min per census pass, single-threaded.

| Trigger | Completions | Share | Long | Short | Proof fields present |
|---|---|---|---|---|---|
| A CHOCH REVERSAL | 131 | 5.2% | 71 | 60 | rule / sweep_index / broken_level = **100%** |
| B LEADING DIAGONAL | 267 | 10.7% | 129 | 138 | origin_level / wave5_index / fib_band = **100%** |
| C ENDING DIAGONAL | 75 | 3.0% | 21 | 54 | terminal_index / converging / boundary = **100%** |
| D TWO-BAR REVERSAL | **0** | 0.0% | — | — | n/a — can never emit (see below) |
| E RSI DIVERGENCE | 143 | 5.7% | 68 | 75 | peak1_index / peak2_index = **100%** |
| F BOS + OB CONTINUATION | 1,881 | 75.3% | 945 | 936 | bos_index / ob_index / entry_anchor = **100%** |
| **Total** | **2,497** | | 1,234 | 1,263 | |

- Direction mix is essentially symmetric overall (1,234 long / 1,263 short).
- By calendar month: uniform 191–229 completions/month (no dead months).
- Setup→signal gap (cheap, proof-field based): F median **4 bars**
  (signal bar − bos_index); A median **1 bar** (signal bar − sweep_index,
  where sweep present). Setup geometry completes close to the signal bar —
  detectors fire on recently-formed structure, not stale geometry.
- **D = 0 BY LOCKED CONSTRUCTION, not a detector failure:** the feed
  (`XAUUSD_M1.parquet`) carries no volume (every bar volume = 0.0), and D's
  frozen confirmation gate `engulfer.volume < engulfed.volume` can never pass
  (`0 < 0` is False). The trigger docstring itself states "no volume data ⇒ no
  signal in V1". D is therefore structurally dead on the product data path —
  reported, not "fixed" (no volume source was invented, no gate relaxed).
- Charts: 35 stratified panels (`scan1a_ltf_no_poi/charts/`, quota-limited by
  trigger — D contributes none), all labeled `TRIGGER_X · NO_POI_FILTER`.
- Proof-field note: field lists are the ACTUAL `signal.data` keys observed in
  the census (initially guessed lists for B/C were corrected post-run from the
  events CSV; census rows and dual-pass equality untouched).

## 3. 1B product-linked table + lifecycle buckets

Universe: **3,731 armed POIs** (12 product_1y segments, non-additive tiling) —
winners 865, submitted 285, placed 252, fills 239. M5 trigger inventory over
each armed POI's product horizon window `[arm, arm+20]` with real zone bounds,
both directions, production trigger code: **2,480 completion occurrences**
(1,443 distinct geometry keys; occurrences are NOT deduped across POI windows).

**Trigger mix of POI-linked completions (occurrences vs distinct geometry):**

| Trigger | Occurrences | Unique geometry (distinct signal.data keys) | Unique L/S |
|---|---|---|---|
| A CHOCH | 156 | 68 | 37 / 31 |
| B LEADING DIAGONAL | 185 | 97 | 47 / 50 |
| C ENDING DIAGONAL | 12 | 12 | 0 / 12 (short only) |
| D TWO-BAR REVERSAL | 0 | 0 | — (cannot emit — see §2) |
| E RSI DIVERGENCE | 21 | 20 | 12 / 8 |
| F BOS+OB | 2,106 | 1,246 | 644 / 602 |
| **Total** | **2,480** | **1,443** | |

**Lifecycle buckets (exclusive, sum = 3,731):**

| Bucket | POIs | Meaning |
|---|---|---|
| FILLED | **239** | armed POI whose routed order filled (routed=true ⇔ trades.csv POI set — verified per segment, fail-loud) |
| COMPLETED_NOT_ROUTED | **1,796** | armed POI with ≥1 M5 completion in its window, menu episode never routed (incl. menu-guard intake drops, 580 aggregate, and never-won episodes) |
| ARMED_NO_COMPLETION | **1,696** | armed POI with ZERO M5 trigger completions in its 20-bar window (armed from M15/H1/H4/D1 detection; confirmation may occur above M5) |
| ROUTED_NOT_FILLED (AGGREGATE ONLY) | 46 | winners that reached the order seam but never filled (submitted-unplaced 33 + placed-unfilled 13); per-POI placed flags not exported |
| OPEN_SCAN_ROUTED (non-exclusive) | 865 | = winner set |

Arithmetic checks: 239 + 1,796 + 1,696 = 3,731 ✓; winners 865 = 580 guard
drops + 33 submitted-unplaced + 13 placed-unfilled + 239 filled ✓; fill mix
{F 226, A 13} = product_1y `fills_by_trigger` ✓ (fail-loud checks passed).

**Filled-POI direction validation (residual, not a failure):** of the 239
filled POIs, only **147** have ≥1 M5 completion in their armed window at all,
and **95** of those have the product's direction among their completion
directions. The product's menu confirmation happens on the POI's detection TF
(M15 161 / H1 37 / H4 35 / D1 6 of the 239 fills) — often above M5 — so the
M5 window inventory is a LOWER bound on confirmation activity for those POIs.

Per-segment (armed / M5 completions / FILLED · COMPLETED_NOT_ROUTED ·
ARMED_NO_COMPLETION): nov24 232/155 (21·114·97) · dec24 193/150 (12·101·80) ·
jan25 198/132 (12·99·87) · feb25 290/163 (23·126·141) · mar25 394/241
(14·174·206) · apr25 386/246 (18·188·180) · may25 320/215 (30·146·144) ·
jun25 284/217 (19·146·119) · jul25 331/228 (27·162·142) · aug25 198/138
(22·94·82) · sep25 462/337 (18·257·187) · oct25 443/258 (23·189·231).
Full detail in `scan1b_ltf_with_poi/summary.json`.

Charts: 24 panels, 8 per group (`scan1b_ltf_with_poi/charts/`): 1A-only-no-POI,
POI-linked-not-routed (with real POI zone band), filled.

## 4. Comparison: structure exists (1A) vs admitted to product (1B) vs filled

| Trigger | 1A completions (no POI) | 1B POI-linked occ. | Link ratio (occ./1A) | Fills (of 239) |
|---|---|---|---|---|
| A | 131 | 156 | 1.19 | 13 |
| B | 267 | 185 | 0.69 | **0** |
| C | 75 | 12 | 0.16 | **0** |
| D | 0 | 0 | — | 0 (cannot emit) |
| E | 143 | 21 | 0.15 | **0** |
| F | 1,881 | 2,106 | 1.12 | 226 |
| **Total** | **2,497** | **2,480** | | **239** |

Reading (measurement, no recommendations):

- **F dominates every layer**: 75.3% of 1A, 84.9% of 1B occurrences, and
  226/239 (94.6%) of fills. The product's filled story is overwhelmingly a
  BOS+OB story.
- **A is the only other filled trigger** (13 fills, 5.4%) and links at ≥1× —
  its M5 geometry attaches to armed zones about as often as it exists at all.
- Link ratios ≥1 for A/F are a window-overlap effect, not a contradiction:
  1B counts one occurrence per armed-POI window, and the same geometry can sit
  inside several (overlapping, both-direction) POI windows; additionally F's
  `entry_anchor` embeds the zone, so real-zone geometry keys can never be
  identical to sentinel-zone 1A keys.
- **B, C, E: the structure exists (material 1A) and partially attaches to
  armed zones (B strongly: 185 occurrences), yet contributes ZERO of the 239
  fills.** The product fill funnel is A/F-only end to end.
- Of 3,731 armed POIs, 2,035 (54.5%) show ≥1 M5 completion in their window;
  1,696 (45.5%) show none; 239 (6.4%) fill.
- The M5-window view is blind to M15/H1/H4/D1 confirmation: 92 of the 239
  FILLED POIs show no M5 completion at all (§3 residual).

## 5. Major-concern test

Listed explicitly per the engagement spec — **NOT fixed** (measurement-only):

- **B — LEADING DIAGONAL (primary concern):** material baseline existence
  (267 no-POI completions) AND the second-largest POI-linked presence
  (185 occurrences, 0.69× link ratio, both directions), yet **zero fills in
  the 239**. The structure fires and attaches to accepted-zone stories but
  never becomes a filled plan anywhere in the product year.
- **C — ENDING DIAGONAL:** 75 no-POI completions but only 12 POI-linked
  occurrences (0.16×) — all short-direction — and **zero fills**.
- **E — RSI DIVERGENCE:** 143 no-POI completions but only 21 POI-linked
  occurrences (0.15×) and **zero fills**.
- **D — TWO-BAR REVERSAL (structural note, different from the above):** 0
  completions in BOTH layers — not "material 1A / no product use" but a
  detector that can never fire on this feed at all (frozen volume gate; the
  feed carries no volume). Recorded so the zero is not mistaken for absence
  of structure.
- **A, F:** no concern — both link at ≥1× and both fill (A 13, F 226).

No trigger was "fixed", gated, re-weighted, or removed; no threshold or
definition was touched.

## 6. Residuals

- **Segment tiling:** 1B reuses the product_1y 12-segment tiling (adjacent
  calendar months). Product-level boundary dedupe dropped 0 fills; armed-window
  scan is per segment, so an armed POI's 20-bar window never crosses a segment
  edge by construction (windows are clamped to the segment series).
- **M1 vs M5:** M1 not scanned (reason in §1). Fill detection-TF mix is
  M15 161 / H1 37 / H4 35 / D1 6 — the product's menu confirmation happens on
  TFs above M5 for many tiers, so the M5 inventory around the armed bar is a
  LOWER bound on confirmation activity for those POIs; exact-geometry
  reconciliation of the 239 fills is NOT assumed and was validated only at
  direction level (§3 table).
- **Direction:** armed records export no direction; 1B supplies both
  directions synthetically with real zone bounds and validates the product
  direction against the completion set per filled POI (residual: completion
  direction ≠ product direction is possible and is counted, not filtered).
- **1A sentinel zone:** F entries are always re-anchored (degenerate) — census
  geometry only; zone containment effects (which the product applies at POI
  level upstream of arming) are therefore outside 1A by design.
- **ROUTED_NOT_FILLED is aggregate-only** (per-POI placed flags not exported by
  the 1y artifacts) — bucket counts per POI are impossible without new
  instrumentation; aggregate is reported instead.
- **Chart sample bias:** ≤36 (1A) / ≤24 (1B) stratified panels are
  illustrations, not statistics; sampled deterministically by time-spread
  within trigger/bucket quotas.
- **1A-only chart group caveat:** "1A-only" = geometry key absent from every
  armed-POI window's completion set (string-equality on json signal.data);
  field-ordering differences between JSON dumps could hide an identity —
  counted as a chart-group convention, not a census number.

## 7. Explicit scope statement

This engagement makes **NO expectancy claim, NO stop-loss redesign, and NO ship
recommendation**. It is a detector/product visibility census on a frozen window.
Stop-loss / MAE–MFE autopsy is deliberately OUT OF SCOPE here and is scheduled
as Scan 2 (on the 239 fills) after Architect review of this report.

**NEXT = Architect review of Scan 1 → Scan 2 stop/MAE autopsy on the 239 fills
→ then demo.**
