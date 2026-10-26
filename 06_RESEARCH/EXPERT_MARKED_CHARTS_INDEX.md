# EXPERT MARKED CHARTS — INDEX

**Date:** 2026-10-05 · **Directive:** Lead Architect expert-chart archive +
inventory + optional system match probe (READ-ONLY; `LOGIC_CHANGED: NO`).
**Source:** 11 chart images received via Downloads on 2026-10-05
(16:27–16:28 local): `C:/Users/User10/Downloads/1.jfif … 11.jfif`.
**Copied (byte-identical, MD5-verified on sample):**
`03_REFERENCE_CODE/expert_marked_charts/chart_1.jfif … chart_11.jfif` —
originals untouched in Downloads.

**Nature of the set:** TradingView-style XAUUSD-VIP screenshots (no
platform dates visible; header OCR shows symbol "XAUUSD-VIP" on charts
6, 7, 9, 10, 11; live price at capture ≈ 4141–4158). The operator's red
markings walk the intended multi-TF SMC narrative:

> W1 OB → D1 structural sweep → H4 sweep / H4 FVG → LTF (M5/M1)
> double top/bottom, CHOCH, Fib golden, ending diagonal → entry.

**Reading method (honesty):** RapidOCR (harness-local, pip-only) read
19–25 text items per chart (`results/expert_marked_charts/ocr/
ocr_full.json`); red-marking geometry extracted by pixel mask +
connected components. The browser screenshot path was unavailable in
this build (webview compositing error), so labels rest on OCR + pixel
analysis, not human viewing — marked-element tags below are
**high-confidence for text and zone geometry**, and marked TF is quoted
from the operator's own red text.

## Per-chart inventory (summary — full data in ledger.csv)

| # | TF (header/marking) | Marking (verbatim) | Marked elements (plain tags) | Direction | Role in flow | Price region (approx) |
|---|---|---|---|---|---|---|
| 1 | — (mark: H4) | sweep in H4 | SWEEP (H4) + diagonal trendline | SHORT | HTF_SWEEP | ~4145–4426 |
| 2 | M5 (mark) | Double TOP in M5 / Here selling confirm | DOUBLE TOP (M5) | SHORT | LTF_CONFIRM | ~4212–4226 |
| 3 | — (mark: H4) | Sweep in H4 | STRUCTURAL SWEEP (H4) | SHORT | HTF_SWEEP | ~4251–4688 (diag) |
| 4 | M1 (mark) | Confirmaton in M1 @ Fibu golden level / CHOCH / buying | CHOCH (M1) + FIB GOLDEN (M1) | LONG | LTF_CONFIRM | ~4253–4287 |
| 5 | — (mark: H4) | H4 FVG area | FVG (H4) | SHORT | HTF_POI | ~4399–4428 |
| 6 | M1 (mark) | Ending Diagnol @ H4 FVG area in M1 | ENDING DIAGONAL (M1) @ FVG (H4) | SHORT | LTF_CONFIRM | ~4403–4407 |
| 7 | Daily (header) | D1 structural level sweep | STRUCTURAL SWEEP (D1) | SHORT | HTF_SWEEP | ~4009–4745 (diag) |
| 8 | M5 (mark) | CHOCH / Fibu Golden ARea in M5 | CHOCH (M5) + FIB GOLDEN (M5) | LONG | LTF_CONFIRM | ~4283–4333 |
| 9 | Weekly (header) | OB Week | ORDER BLOCK (W1) | LONG | HTF_POI | ~4092–4208 |
| 10 | M5 (header) | Double Bottom in M5 / Buying confirmatoin | DOUBLE BOTTOM (M5) | LONG | LTF_CONFIRM | ~4110–4121 |
| 11 | H1 (header) | entry / entry | ENTRY (H1) ×2 | SHORT | ENTRY | ~4371–4388 |

## Flow reconstruction (as marked)

HTF context: W1 order block (chart 9) → D1 structural sweep (7) →
H4 sweep (1, 3) → H4 FVG (5, 6 context) — then LTF confirmation:
M5 double top (2) / M1 CHOCH + Fib golden (4, 8) / M5 double bottom (10) /
M1 ending diagonal (6) → entry (11). Both directions present: the W1-OB +
double-bottom + CHOCH-buying charts read LONG; the sweep + double-top +
ending-diagonal charts read SHORT.

## Files

- Charts: `03_REFERENCE_CODE/expert_marked_charts/chart_{1..11}.jfif`
- Ledger: `06_RESEARCH/results/expert_marked_charts/ledger.csv`
- OCR raw: `06_RESEARCH/results/expert_marked_charts/ocr/ocr_full.json`
- Red-mask stats: `06_RESEARCH/results/expert_marked_charts/ocr/red_mask_stats.json`
- Match probe output: `06_RESEARCH/results/expert_marked_charts/match_probe.json`
- Probe script: `06_RESEARCH/scripts/expert_chart_match_probe.py`
- Match note: `06_RESEARCH/EXPERT_CHART_SYSTEM_MATCH_NOTE.md`

## Explicit limitations

1. **No dates are readable on any chart** — timestamps are UNKNOWN; the
   only clock-like OCR hit is a bare `170000` (chart 6), not a date.
2. Labels derive from OCR + red-pixel geometry (the visual-preview
   screenshot path is broken in this build); confident for text and
   zone/line geometry, less so for candle-level narrative detail.
3. Chart 4's price axis is partially obscured by the Fib tool — its
   calibration is approximate (flagged in ledger + probe).
