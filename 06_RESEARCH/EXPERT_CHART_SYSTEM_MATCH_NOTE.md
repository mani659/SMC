# EXPERT CHART SYSTEM MATCH NOTE — READ-ONLY PROBE

**Date:** 2026-10-05 · **Directive:** Lead Architect expert-chart archive +
match probe. `LOGIC_CHANGED: NO` — no strategy code, threshold, trigger,
pillar, or locked constant touched; **no new detectors or Fib engines**
(the probe only cross-references the existing frozen ledger).

## 1. What was probed

The operator's 11 marked example charts (archived at
`03_REFERENCE_CODE/expert_marked_charts/`, inventoried in
`EXPERT_MARKED_CHARTS_INDEX.md` + `results/expert_marked_charts/ledger.csv`)
against the **existing frozen detection / Stage 3 / M8 outputs** — the
6-month structure ledger `06_RESEARCH/results/structure_ledger_6m/
events.csv` (13,247 rows, 2025-06-01 → 2025-11-30; events.csv SHA-256
`903e5a3b…` unchanged, read-only). Available classes and counts: sweep
2,041 · fvg 802 (+219 poi_raw kind=fvg) · ob (poi_raw) 217 ·
demand_supply (poi_raw) 457 · poi_armed 31 · route_ltf 10 · fill 2 ·
displacement 1,117 (NO prices — see DATA_GAP).

## 2. Method (and its limits — stated up front)

1. **Time matching: DATA_GAP for every chart.** No dates are readable on
   any image (only a bare clock `170000` on chart 6). Per the directive,
   timestamps were NOT invented; the probe is price-zone-only.
2. **Price zones:** red-marking pixels extracted (OpenCV connected
   components over a saturated-red mask), calibrated to price by linear
   y→price mapping from the OCR'd right-axis ticks. Zone types: drawn
   box / horizontal line / diagonal line / — where the operator marked
   with text+arrows only — the coarse red-annotation span (never
   upgraded to YES; PARTIAL cap). Chart 4's axis is partially obscured
   by the Fib tool → approximate calibration.
3. **TF honesty:** the ledger's detection TFs are H4/H1/D1 only. Charts
   marked M5/M1/W1 are probed on the nearest available TF (H1 for M5/M1,
   D1 for W1) and **capped at PARTIAL** — a same-price H1 event is not a
   same-TF match and is not reported as one.
4. **No re-detection:** nothing was re-run, no thresholds touched. A
   verdict says "the frozen ledger already contains an event of this
   class in this price band", nothing more.

## 3. Match table

| Chart | Operator marking (verbatim) | Marked zone (price, approx) | Probed class (TF) | Verdict | Evidence / miss detail |
|---|---|---|---|---|---|
| 1 | "sweep in H4" | ~4145–4426 (annotation span) | sweep (H4) | **PARTIAL** | 155 sweep bands intersect the coarse span (4143.69–4379.12); span is coarse — text/arrow marking, no drawn zone |
| 2 | "Double TOP in M5 / Here selling confirm" | ~4212–4226 | sweep (M5→H1, capped) | **PARTIAL** | 27 H1 sweep bands in 4208.15–4226.73; route_ltf: 2 routes in span (4158.69–4244.73) — same-price H1, NOT same-TF |
| 3 | "Sweep in H4" | ~4251–4688 (diagonal) | sweep (H4) | **YES** | 25 H4 sweep bands intersect the diagonal's price span (4250.77–4379.12) |
| 4 | "Confirmaton in M1 @ Fibu golden level / CHOCH / buying" | ~4253–4287 | fvg (M1→H1, capped) / displacement (M1) | **PARTIAL** / DATA_GAP | 21 H1 fvg bands in 4244.73–4336.94; displacement events carry no prices in the ledger |
| 5 | "H4 FVG area" | ~4399–4428 (drawn box) | fvg (H4) | **NO** | 1,021 fvg events; closest band **39.6 price units** below the box — a clean, honest miss |
| 6 | "Ending Diagnol @ H4 FVG area in M1" | ~4403–4407 (two lines) | fvg (M1/H4) | **NO** | closest band **46.2** away (1,021 fvg events) — the M1 ending diagonal itself has no ledger analogue at all |
| 7 | "D1 structural level sweep" | ~4009–4745 (annotation span) | sweep (D1) | **PARTIAL** | 434 sweep bands intersect the coarse span (4004.42–4379.12); span coarse |
| 8 | "CHOCH / Fibu Golden ARea in M5" | ~4283–4333 (diagonal) | fvg (M5→H1, capped) / sweep (M5→H1, capped) | **PARTIAL** / **PARTIAL** | 20 H1 fvg bands (4244.73–4342.38); 9 sweep bands — same-price H1, not M5 CHOCH |
| 9 | "OB Week" | ~4092–4208 (drawn box) | ob (W1→D1, capped) / demand_supply (W1→D1, capped) | **PARTIAL** / **PARTIAL** | 26 D1 ob bands in 4003.30–4239.19; 69 demand_supply bands — no W1 detection exists in the system |
| 10 | "Double Bottom in M5 / Buying confirmatoin" | ~4110–4121 (drawn box) | sweep (M5→H1, capped) / route_ltf (M5) | **PARTIAL** / **NO** | 27 H1 sweep bands in 4105.00–4124.80; but 0 of 10 product routes in the zone (closest 126.3 away — zone is off the routed-path family) |
| 11 | "entry / entry" | ~4371–4388 (annotation span) | poi_armed (H1) / route_ltf / fill | **PARTIAL** / **NO** / **NO** | 1 armed POI in span (4307.10–4379.12); 0 of 10 routes and 0 of 2 fills near the marked entries (closest 126.3) |

**Score:** YES 1 (chart 3) · PARTIAL 9 charts (several at coarse/TF-capped
strength) · clean NO 3 charts (5, 6 — FVG zone genuinely unmatched;
10, 11 at route/entry level) · DATA_GAP: all time matching + displacement
class. The coarse-span and TF-capped PARTIALs are honest-but-weak: they
say "the system sees this price band", not "the system sees this pattern".

## 4. Honest reading (misses NOT explained away)

1. **Pattern classes the system does not emit at all:** M5/M1 double
   top/bottom, CHOCH, Fib golden level, ending diagonal — these are
   LTF confirmation *patterns*, and the pipeline's LTF vocabulary is
   trigger A–F geometry, not chart patterns. The PARTIALs on charts 2,
   4, 8, 10 reflect price-band co-location of H1 sweeps/FVGs only.
   Closing that vocabulary gap would be a strategy change — out of scope
   here by directive.
2. **W1 does not exist in the detection stack** (H4/H1/D1 only). Chart
   9's weekly OB can only ever match at D1 resolution (PARTIAL cap).
3. **Clean geometric miss:** chart 5's drawn H4 FVG box (~4399–4428) has
   no ledger fvg band within ~39.6 price units — the system's frozen
   FVG definition did not emit there while the operator's eye did.
   Chart 6's lines miss by ~46.2. Both reported as-is; no threshold
   conclusion is drawn from n=1–2 eye-vs-system disagreements.
4. **Entry-level divergence:** chart 11's marked entries (~4371–4388)
   sit far from every product route/fill (closest 126.3) — expected,
   since the fills ledger has n=2 in the frozen window and the operator's
   charts are undated examples, not this window's trades.
5. **Method limits:** zone extraction is automated (OCR calibration +
   red-pixel geometry) because the visual-screenshot path is broken in
   this build; the browser preview rendered pages but produced no
   capturable frames. Calibration is linear between extreme OCR'd ticks;
   chart 4 is approximate. The coarse annotation-span fallback (charts
   1, 7, 11) marks where the operator wrote, not a drawn zone — kept at
   PARTIAL cap regardless of hit count.

## 5. POLICY CAPTURE (docs only — PENDING Architect ruling)

The operator stated two policy rules alongside the charts. **They are
recorded verbatim below and are NOT implemented — no code, threshold, or
constant reflects them:**

> **(a) "TP must always be the first swing low/high."**
> **(b) "SL must always be 30 pips below/above the small-TF entry."**

**Current V1 behaviour (for contrast — unchanged by this task):**

- **TP:** the structural-else-4ATR TP branch exists in the bridge but is
  **UNFED** — placements currently carry TP from the placed-order path
  (frozen funnel: TP non-null 100% on placed orders), not a
  first-swing-high/low rule. No swing-based TP engine is wired.
- **SL:** structural SL ± buffer / ATR-derived (frozen §28 family) —
  **not** a fixed 30-pip distance. A fixed-pip SL would be a locked-
  constants change.

**Status: PENDING Architect ruling.** Both statements are candidate
policy amendments to the TP/SL sections of `LOCKED_DECISIONS.md`; they
are recorded here as operator policy input only. This note makes no
recommendation and implements nothing.

## 6. Bans verification

- No edits under `04_SRC/smc/**` (none made — read-only probe).
- `locked_constants.py` diff empty (verified post-task).
- No SL=30-pip implementation; no TP=first-swing implementation; no new
  detectors or Fib engines (the probe reads existing ledger CSV only).

---

**Artifacts:** charts `03_REFERENCE_CODE/expert_marked_charts/` ·
`06_RESEARCH/EXPERT_MARKED_CHARTS_INDEX.md` ·
`06_RESEARCH/results/expert_marked_charts/{ledger.csv, match_probe.json,
ocr/ocr_full.json, ocr/red_mask_stats.json, ocr/contact_sheet.html}` ·
probe script `06_RESEARCH/scripts/expert_chart_match_probe.py`.
