# PFE-3 — EXPERT VALIDATION PACK (STRUCTURE + CONFIRM + ENTRY)

**Date:** 2026-11-15 · **Program:** PFE step 3 · **`LOGIC_CHANGED: NO`**
**PDF:** `06_RESEARCH/results/pfe3_expert_pack/EXPERT_REVIEW_PACK.pdf` ·
**Events:** `06_RESEARCH/results/pfe3_expert_pack/events.csv` ·
**Charts:** `06_RESEARCH/results/pfe3_expert_pack/charts/`

**Diagnostic review pack — not performance. No expectancy language is
used anywhere in the pack, by design.**

## 1. What is in the pack

| Section | Events | What it is |
|---|---|---|
| A — menu fills | 27 | every fill in the three PFE-2 menu windows (Jun/Sep/Oct 1–10 2025) — the product law |
| B — armed, no confirmation | 30 | armed menu POIs that never produced a winner (up to 10 per window, even stride) |
| C — seek fills | 10 | six-month seek book, even stride — CONTINUITY ONLY, not the live default |

Selection was fixed in `06_RESEARCH/scripts/pfe3_expert_pack.py` before any
chart existed and applied mechanically: all menu fills, even-stride negative
and seek samples, no additions or removals afterwards.

## 2. How each chart reads

| Element | Meaning |
|---|---|
| Blue band | the POI zone, labelled with its detection timeframe and model tags |
| Black solid | entry price |
| Red dashed | original SL |
| Teal dashed | TP |
| Orange dotted | sweep instant (menu stamp) |
| Purple dotted | confirmation instant (menu stamp) |
| Grey dashed | exit |

## 3. Rubric

**CORRECT** — zone, sweep/confirmation read and entry all match the flowchart.
**PARTIAL** — real event, one element arguable (zone width, confirmation choice, entry placement).
**WRONG** — this should not have been a setup.
**UNCLEAR** — the chart does not carry enough context.

Score in `events.csv` (`expert_score`, `expert_note`) or on the PDF page.
Architect-side notes below are deliberately separated so scoring is blind.

## 4. Architect draft notes (do not read before scoring)

<details><summary>Notes</summary>

- All 27 menu fills in the PFE-2 windows are Trigger F; A/D never won. If the
  expert marks F-only entries as PARTIAL/WRONG, that is evidence about the
  menu's trigger subsets, not about C3 or the sweep stage.
- Menu TP source splits 17 structural / 10 fallback across the three windows;
  the pack includes both, so the expert can judge fallback targets on their
  own merits rather than against a single target style.
- Section B is the honest negative set: charting idle armed POIs is how we
  learn whether the confirmation stage is too strict, without touching it.
  Any judgment that these should have fired is a PFE-4 design question.

</details>

## 5. Event index

| # | event_id | kind | tf | trigger | tp_source | close | chart |
|---|---|---|---|---|---|---|---|
| 1 | `menu_jun01_10:fill:1` | menu_fill | H4 | F | structural_swing | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_fill_1.png` |
| 2 | `menu_jun01_10:fill:2` | menu_fill | H4 | F | structural_swing | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_fill_2.png` |
| 3 | `menu_jun01_10:fill:3` | menu_fill | H4 | F | structural_swing | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_fill_3.png` |
| 4 | `menu_jun01_10:fill:4` | menu_fill | H4 | F | structural_swing | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_fill_4.png` |
| 5 | `menu_jun01_10:fill:5` | menu_fill | H4 | F | structural_swing | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_fill_5.png` |
| 6 | `menu_jun01_10:fill:6` | menu_fill | M15 | F | structural_swing | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_fill_6.png` |
| 7 | `menu_jun01_10:fill:7` | menu_fill | M15 | F | atr_fallback | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_fill_7.png` |
| 8 | `menu_jun01_10:fill:8` | menu_fill | M15 | F | atr_fallback | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_fill_8.png` |
| 9 | `menu_jun01_10:fill:9` | menu_fill | M15 | F | atr_fallback | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_fill_9.png` |
| 10 | `menu_jun01_10:fill:10` | menu_fill | M15 | F | structural_swing | stop_loss | `` |
| 11 | `menu_jun01_10:fill:11` | menu_fill | M15 | F | structural_swing | stop_loss | `` |
| 12 | `menu_sep01_10:fill:1` | menu_fill | M15 | F | structural_swing | take_profit | `` |
| 13 | `menu_sep01_10:fill:2` | menu_fill | M15 | F | structural_swing | take_profit | `` |
| 14 | `menu_oct01_10:fill:1` | menu_fill | M15 | F | structural_swing | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_oct01_10_fill_1.png` |
| 15 | `menu_oct01_10:fill:2` | menu_fill | M15 | F | structural_swing | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_oct01_10_fill_2.png` |
| 16 | `menu_oct01_10:fill:3` | menu_fill | M15 | F | structural_swing | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_oct01_10_fill_3.png` |
| 17 | `menu_oct01_10:fill:4` | menu_fill | M15 | F | structural_swing | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_oct01_10_fill_4.png` |
| 18 | `menu_oct01_10:fill:5` | menu_fill | M15 | F | structural_swing | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_oct01_10_fill_5.png` |
| 19 | `menu_oct01_10:fill:6` | menu_fill | M15 | F | structural_swing | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_oct01_10_fill_6.png` |
| 20 | `menu_oct01_10:fill:7` | menu_fill | M15 | F | structural_swing | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_oct01_10_fill_7.png` |
| 21 | `menu_oct01_10:fill:8` | menu_fill | D1 | F | atr_fallback | stop_loss | `` |
| 22 | `menu_oct01_10:fill:9` | menu_fill | D1 | F | atr_fallback | stop_loss | `` |
| 23 | `menu_oct01_10:fill:10` | menu_fill | D1 | F | atr_fallback | stop_loss | `` |
| 24 | `menu_oct01_10:fill:11` | menu_fill | D1 | F | atr_fallback | stop_loss | `` |
| 25 | `menu_oct01_10:fill:12` | menu_fill | D1 | F | atr_fallback | stop_loss | `` |
| 26 | `menu_oct01_10:fill:13` | menu_fill | D1 | F | atr_fallback | stop_loss | `` |
| 27 | `menu_oct01_10:fill:14` | menu_fill | D1 | F | atr_fallback | stop_loss | `` |
| 28 | `menu_jun01_10:no_winner:poi-000567` | menu_no_winner | H1 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_no_winner_poi-000567.png` |
| 29 | `menu_jun01_10:no_winner:poi-000796` | menu_no_winner | D1 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_no_winner_poi-000796.png` |
| 30 | `menu_jun01_10:no_winner:poi-001310` | menu_no_winner | D1 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_no_winner_poi-001310.png` |
| 31 | `menu_jun01_10:no_winner:poi-001560` | menu_no_winner | D1 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_no_winner_poi-001560.png` |
| 32 | `menu_jun01_10:no_winner:poi-001808` | menu_no_winner | D1 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_no_winner_poi-001808.png` |
| 33 | `menu_jun01_10:no_winner:poi-002055` | menu_no_winner | D1 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_no_winner_poi-002055.png` |
| 34 | `menu_jun01_10:no_winner:poi-002298` | menu_no_winner | D1 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_no_winner_poi-002298.png` |
| 35 | `menu_jun01_10:no_winner:poi-003284` | menu_no_winner | M15 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_no_winner_poi-003284.png` |
| 36 | `menu_jun01_10:no_winner:poi-004184` | menu_no_winner | D1 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_no_winner_poi-004184.png` |
| 37 | `menu_jun01_10:no_winner:poi-005386` | menu_no_winner | M15 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_jun01_10_no_winner_poi-005386.png` |
| 38 | `menu_sep01_10:no_winner:poi-000018` | menu_no_winner | H4 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_sep01_10_no_winner_poi-000018.png` |
| 39 | `menu_sep01_10:no_winner:poi-000965` | menu_no_winner | H1 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_sep01_10_no_winner_poi-000965.png` |
| 40 | `menu_sep01_10:no_winner:poi-002819` | menu_no_winner | H4 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_sep01_10_no_winner_poi-002819.png` |
| 41 | `menu_sep01_10:no_winner:poi-003859` | menu_no_winner | H4 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_sep01_10_no_winner_poi-003859.png` |
| 42 | `menu_sep01_10:no_winner:poi-005111` | menu_no_winner | H4 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_sep01_10_no_winner_poi-005111.png` |
| 43 | `menu_sep01_10:no_winner:poi-006133` | menu_no_winner | M15 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_sep01_10_no_winner_poi-006133.png` |
| 44 | `menu_sep01_10:no_winner:poi-008003` | menu_no_winner | D1 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_sep01_10_no_winner_poi-008003.png` |
| 45 | `menu_sep01_10:no_winner:poi-008816` | menu_no_winner | D1 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_sep01_10_no_winner_poi-008816.png` |
| 46 | `menu_sep01_10:no_winner:poi-009638` | menu_no_winner | D1 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_sep01_10_no_winner_poi-009638.png` |
| 47 | `menu_sep01_10:no_winner:poi-010312` | menu_no_winner | H4 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_sep01_10_no_winner_poi-010312.png` |
| 48 | `menu_oct01_10:no_winner:poi-001899` | menu_no_winner | H4 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_oct01_10_no_winner_poi-001899.png` |
| 49 | `menu_oct01_10:no_winner:poi-003317` | menu_no_winner | H4 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_oct01_10_no_winner_poi-003317.png` |
| 50 | `menu_oct01_10:no_winner:poi-006522` | menu_no_winner | M15 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_oct01_10_no_winner_poi-006522.png` |
| 51 | `menu_oct01_10:no_winner:poi-007339` | menu_no_winner | D1 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_oct01_10_no_winner_poi-007339.png` |
| 52 | `menu_oct01_10:no_winner:poi-008400` | menu_no_winner | D1 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_oct01_10_no_winner_poi-008400.png` |
| 53 | `menu_oct01_10:no_winner:poi-009303` | menu_no_winner | M15 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_oct01_10_no_winner_poi-009303.png` |
| 54 | `menu_oct01_10:no_winner:poi-009495` | menu_no_winner | D1 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_oct01_10_no_winner_poi-009495.png` |
| 55 | `menu_oct01_10:no_winner:poi-009751` | menu_no_winner | H1 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_oct01_10_no_winner_poi-009751.png` |
| 56 | `menu_oct01_10:no_winner:poi-010023` | menu_no_winner | H1 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_oct01_10_no_winner_poi-010023.png` |
| 57 | `menu_oct01_10:no_winner:poi-010229` | menu_no_winner | D1 | — | — | — | `06_RESEARCH/results/pfe3_expert_pack/charts/menu_oct01_10_no_winner_poi-010229.png` |
| 58 | `seek6m:fill:1` | seek_fill | — | F | structural_swing | take_profit | `06_RESEARCH/results/pfe3_expert_pack/charts/seek6m_fill_1.png` |
| 59 | `seek6m:fill:9` | seek_fill | — | F | atr_fallback | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/seek6m_fill_9.png` |
| 60 | `seek6m:fill:17` | seek_fill | — | F | structural_swing | take_profit | `06_RESEARCH/results/pfe3_expert_pack/charts/seek6m_fill_17.png` |
| 61 | `seek6m:fill:25` | seek_fill | — | F | atr_fallback | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/seek6m_fill_25.png` |
| 62 | `seek6m:fill:33` | seek_fill | — | F | atr_fallback | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/seek6m_fill_33.png` |
| 63 | `seek6m:fill:41` | seek_fill | — | F | atr_fallback | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/seek6m_fill_41.png` |
| 64 | `seek6m:fill:49` | seek_fill | — | F | atr_fallback | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/seek6m_fill_49.png` |
| 65 | `seek6m:fill:57` | seek_fill | — | F | structural_swing | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/seek6m_fill_57.png` |
| 66 | `seek6m:fill:65` | seek_fill | — | F | atr_fallback | take_profit | `06_RESEARCH/results/pfe3_expert_pack/charts/seek6m_fill_65.png` |
| 67 | `seek6m:fill:73` | seek_fill | — | F | structural_swing | stop_loss | `06_RESEARCH/results/pfe3_expert_pack/charts/seek6m_fill_73.png` |

## 6. What this pack does not claim

No edge, expectancy, win rate, profitability or optimisation. Counts here
are review volume on a boundary sample, not a trading rate. Menu and seek
are never ranked against each other.
