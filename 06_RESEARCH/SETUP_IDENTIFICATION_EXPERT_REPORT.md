# SETUP IDENTIFICATION — EXPERT REPORT (pack cover)

**Directive:** Lead Architect, 2026-10-06 (backfill + expert pack; research/export only)
**Pack (share this):** `06_RESEARCH/results/setup_identification_ledger/EXPERT_SETUP_REVIEW_PACK.pdf`
**Ledger:** `06_RESEARCH/results/setup_identification_ledger/setups.csv` (30 rows)
**Charts:** `06_RESEARCH/results/setup_identification_ledger/charts/` (15 PNGs)
**Purpose:** identification-quality review by a human expert. **NOT a PnL or
edge claim.** No trading threshold or strategy logic changed to produce it.

---

## 1. What the engine identified (frozen 6m window)

Window 2025-06-01T22:00Z → 2025-11-30T23:55Z (exec M5, M1 loaded from
2025-05-01), frozen 6m post-TP funnel artifacts:

| Metric | Value |
|---|---|
| Armed setups (passed all 5 pillars + arming + dedup) | **30** |
| By detection TF | H4 19 · H1 6 · D1 5 |
| Routed (trigger fired, plan produced) | 3 — triggers F, F, C |
| Hypothesis-outcome join on routed | SL_THEN_TP_PATH 2 · TP_REACHED 1 |
| tp_source at trade level | atr_fallback 2 · structural_swing 1 |

## 2. Backfill provenance (what identity is deterministic)

- **direction: 17/30 filled.** Sources: `trade_row` 3 (the routed trades),
  `structure_ledger_geometry` 14 (EXACT match on detection_tf +
  zone_low + zone_high against a 6m structure-ledger `poi_raw` event with
  one distinct direction — no tolerance, no price inference).
  **13 rows = DATA_GAP**: the source artifacts simply do not contain those
  zones' geometry+direction; they are left blank, never guessed.
- **posture: UNKNOWN for all 30.** Not present in any funnel artifact
  (armed_records.json / funnel_summary.json / report.json all checked).
  Not recoverable without invention — left UNKNOWN, documented.
- **arm_ts_utc: 30/30.** Exec M5 bar-index → timestamp map (exec bar 0 =
  window start); validated by reproducing the 3 routed trades' recorded
  entry AND exit timestamps exactly (6/6 checks).
- Human columns `verdict / timing / notes` are **blank by design** — the
  pipeline never pre-fills a human judgement.

## 3. Scoring rubric (for the reviewer)

**Identification quality only — not PnL, not edge, not "would you trade it".**

verdict (per setup, against the chart):

- **CORRECT** — the zone and direction match the structure a competent SMC
  reader would mark; this is the kind of POI the system intends to find.
- **PARTIAL** — partly right: right level but wrong side / wrong direction,
  or zone materially too wide/narrow vs the structural leg, or a valid POI
  of a different intended class.
- **WRONG** — not a valid POI: noise, unstructured level, wrong side, or
  geometry that no reader would mark.
- **UNCLEAR** — the chart window / data does not allow a judgement.

timing (the arm moment relative to the structure it claims):

- **EARLY** — armed before the structure was complete/confirmed.
- **ON_TIME** — armed at a natural completion point.
- **LATE** — armed well after the structure had played out.
- **N_A** — no meaningful timing reference (e.g. UNCLEAR verdict).

notes: free text — what a reader would mark differently, which TF, any
pattern-vocabulary class the system lacks (double top/bottom, Fib golden,
W1 OB, etc. — known backlog classes from the expert-chart match note).

## 4. Pack contents

- PDF: cover + rubric, full 30-row ledger table, then all 15 charts
  (3 per page).
- Charts (PNG, full resolution in `charts/`): candlesticks on the
  detection TF around the arm bar, zone band, arm-bar marker; routed
  setups add entry / SL / TP levels, exit mark, and the plan + outcome
  caption. DATA_GAP direction rows are labeled as such — honestly.
- Sampling rule (deterministic): **all 3 routed** + stratified non-routed
  **D1 ≤ 4, H4 ≤ 6, H1 ≤ 3** evenly spaced by arm bar → 15 charts.

## 5. How to return scores

Fill the three columns in `setups.csv` (rows keyed by `setup_index` /
`poi_id`), or mark the printed PDF pages. Only rows in the chart sample
can be scored from the pack; the remaining rows can be scored after a
follow-up chart run on request.

---

## APPENDIX — Architect draft notes on the 3 routed rows

> **"Architect draft — not expert verdict."** Clearly separated so the
> expert can ignore it; these are prior-review observations, not scoring.

- **poi-014146 (D1, SHORT, trigger F, atr_fallback, SL_THEN_TP_PATH)** —
  stop-first exit with the TP level touched strictly after exit: a timing/
  management-cost class observation, not a zone-quality verdict.
- **poi-047805 (H4, LONG, trigger C, structural_swing, TP_REACHED)** — the
  structural target was reached live: the carried TP was realized.
- **poi-073511 (D1, SHORT, trigger F, atr_fallback, SL_THEN_TP_PATH)** —
  same stop-first/TP-later class as poi-014146.
- These notes describe trade paths, NOT zone quality — the expert's
  verdict/timing columns remain entirely their own.
