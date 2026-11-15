# PRODUCT 9 FILLS - READ-ONLY DECODE

**READ-ONLY decode of the 9 unique product-menu fills from the PRODUCT_6M one-story diagnostic (raw 27 -> 9 under the guard). Diagnostic only: pnl column is a diagnostic net on the frozen machine-completeness config, NOT performance. No strategy change, no optimization, no retune; `locked_constants.py` untouched.**

- **Sources:** `06_RESEARCH/results/product_6m_one_story/run1/` per-window `trades.csv` + `armed_records.json` + the menu stamp (`signal_data_json.product_menu`). Nothing is re-run; nothing invented.
- **Plain-label rules (never invented):** M8 alone = HTF Demand/Supply zone (DEMAND/SUPPLY from the trade's own direction - architecture legend, `01_ARCHITECTURE/SMC_WORKFLOW_ORCHESTRATION.md` L85); >1 tag = MERGED; a single non-M8 tag (M4 QML, M5 Extreme-EQH) has no word in the allowed vocab -> UNKNOWN (raw `model_tags` column keeps the truth). `m8_kind` is not exported by the harness -> NOT_EXPORTED.
- **Trigger letters** read only from fields already exported: F rows carry `ob_index` + `bos_index` (BOS+OB per the locked master card); the A row carries `broken_level` + `rule_1` + `sweep_index` (CHOCH Rule 1).

## 1. The 9 unique fills

| story_id | ticket | window | dir | det_tf | tags | trigger | zone | entry | SL | TP | tp_source | close | pnl (diag) | label |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| JUN-1 | 1 | jun | short | H4 | M8 | F | 3367.57-3382.28 | 3379.60 | 3381.62 | 3378.80 | structural_swing | stop_loss | +0.022 | SUPPLY |
| JUN-2 | 2 | jun | short | M15 | M5 | F | 3359.60-3364.95 | 3363.05 | 3364.28 | 3362.65 | structural_swing | stop_loss | -0.123 | UNKNOWN |
| JUN-3 | 3 | jun | long | M15 | M4+M5+M7+M8 | F | 3344.76-3372.45 | 3358.00 | 3353.88 | 3369.57 | atr_fallback | stop_loss | -0.412 | MERGED |
| JUN-4 | 4 | jun | long | M15 | M5+M8 | F | 3339.55-3364.95 | 3341.61 | 3340.74 | 3341.95 | structural_swing | stop_loss | -0.087 | MERGED |
| SEP-1 | 1 | sep | long | M15 | M1+M7+M8 | F | 3622.24-3631.76 | 3626.98 | 3625.95 | 3628.50 | structural_swing | take_profit | +0.152 | MERGED |
| OCT-1 | 1 | oct | short | M15 | M5 | F | 3964.95-3977.12 | 3976.01 | 3979.23 | 3968.91 | structural_swing | stop_loss | -0.322 | UNKNOWN |
| OCT-2 | 2 | oct | long | M15 | M4 | F | 4007.74-4024.41 | 4014.74 | 4011.27 | 4022.55 | structural_swing | stop_loss | -0.346 | UNKNOWN |
| OCT-3 | 3 | oct | short | M15 | M4 | A | 3958.07-3964.84 | 3960.07 | 3964.20 | 3950.91 | atr_fallback | stop_loss | -0.413 | UNKNOWN |
| OCT-4 | 4 | oct | long | D1 | M8 | F | 3975.93-3995.78 | 3995.78 | 3970.51 | 4067.98 | atr_fallback | stop_loss | -2.527 | DEMAND |

Full geometry (pillars, displacement, anchor, one-sentence) in `06_RESEARCH/results/product_9_fills_decode/fills_decode.csv`; one house-style chart per fill in `charts/`.

## 2. Per-fill narrative (short)

**JUN-1** (SUPPLY, H4, short, trigger F, 2025-06-05 00:25 -> 2025-06-05 00:35, stop_loss): Price returned into the marked zone: both the confirmation close and the fill sat inside it. Trigger F (the BOS+OB letter per the locked master card): BOS+OB fields present (ob_index 797, bos_index 800). NOT_LABELED (no internal/external liquidity field in the export).

**JUN-2** (UNKNOWN, M15, short, trigger F, 2025-06-06 02:05 -> 2025-06-06 02:05, stop_loss): Price returned into the marked zone: both the confirmation close and the fill sat inside it. Trigger F (the BOS+OB letter per the locked master card): BOS+OB fields present (ob_index 6049, bos_index 6052). NOT_LABELED (no internal/external liquidity field in the export).

**JUN-3** (MERGED, M15, long, trigger F, 2025-06-06 13:20 -> 2025-06-06 13:20, stop_loss): Price returned into the marked zone: both the confirmation close and the fill sat inside it. Trigger F (the BOS+OB letter per the locked master card): BOS+OB fields present (ob_index 6723, bos_index 6726). NOT_LABELED (no internal/external liquidity field in the export).

**JUN-4** (MERGED, M15, long, trigger F, 2025-06-10 11:35 -> 2025-06-10 11:35, stop_loss): Price returned into the marked zone: both the confirmation close and the fill sat inside it. Trigger F (the BOS+OB letter per the locked master card): BOS+OB fields present (ob_index 9381, bos_index 9382). NOT_LABELED (no internal/external liquidity field in the export).

**SEP-1** (MERGED, M15, long, trigger F, 2025-09-10 00:30 -> 2025-09-10 00:30, take_profit): Price returned into the marked zone: both the confirmation close and the fill sat inside it. Trigger F (the BOS+OB letter per the locked master card): BOS+OB fields present (ob_index 9716, bos_index 9719). NOT_LABELED (no internal/external liquidity field in the export).

**OCT-1** (UNKNOWN, M15, short, trigger F, 2025-10-07 14:20 -> 2025-10-07 14:30, stop_loss): Price returned into the marked zone: both the confirmation close and the fill sat inside it. Trigger F (the BOS+OB letter per the locked master card): BOS+OB fields present (ob_index 6652, bos_index 6655). NOT_LABELED (no internal/external liquidity field in the export).

**OCT-2** (UNKNOWN, M15, long, trigger F, 2025-10-09 15:35 -> 2025-10-09 15:35, stop_loss): Price returned into the marked zone: both the confirmation close and the fill sat inside it. Trigger F (the BOS+OB letter per the locked master card): BOS+OB fields present (ob_index 9456, bos_index 9458). NOT_LABELED (no internal/external liquidity field in the export).

**OCT-3** (UNKNOWN, M15, short, trigger A, 2025-10-09 18:35 -> 2025-10-09 19:05, stop_loss): Price returned into the marked zone: both the confirmation close and the fill sat inside it. Trigger A (the CHOCH letter per the locked master card): CHOCH fields present (broken_level 3960.075, rule_1). NOT_LABELED (no internal/external liquidity field in the export).

**OCT-4** (DEMAND, D1, long, trigger F, 2025-10-10 14:00 -> 2025-10-10 14:05, stop_loss): Price returned into the marked zone: both the confirmation close and the fill sat inside it. Trigger F (the BOS+OB letter per the locked master card): BOS+OB fields present (ob_index 467, bos_index 470). NOT_LABELED (no internal/external liquidity field in the export).

## 3. Duplicate residual check

Pairwise plan identity (locked story_guard rules 2-6) inside the 9: **0 duplicate pairs**. The diagnostic already measured identical-plan groups = 0 after the guard; the decode confirms the surviving book carries no residual twin (no two of the nine share direction + trigger + entry + SL + TP + overlapping zone).

## 4. Decode summary

- By trigger: {'A': 1, 'F': 8}
- By detection TF: {'D1': 1, 'H4': 1, 'M15': 7}
- By plain label: {'DEMAND': 1, 'MERGED': 3, 'SUPPLY': 1, 'UNKNOWN': 4}
- By direction: {'long': 5, 'short': 4}
- By close_kind: {'stop_loss': 8, 'take_profit': 1}
- By tp_source: {'atr_fallback': 3, 'structural_swing': 6}

**NEXT = Architect review of the 9 fills -> 1y product menu+one-story diagnostic.** No expectancy claim, no ship recommendation; liquidity labels NOT_LABELED where no field proves them.
