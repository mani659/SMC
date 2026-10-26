# Frozen-Window Funnel - 6 Months, Post Structural-TP Feed

**WINDOW:** exec 2025-06-01 -> 2025-11-30 (M1 load 2025-05-01; frozen, pack-aligned, 35,725 M5 bars)

**MACHINE:** current product path - seek/scan Section 5a + structural TP feed live (selector `structural_tp_target`, existing `structural_target=` / `structural_else_4ATR`; 4xATR fallback byte-for-byte unchanged; SL unchanged; 30-pip absent). Measurement only - NOT performance.

---

## Results (run1; run2 semantically identical)

- HTF batches: 2979 (errors 0)
- Raw merged: 43004 (|raw H4 44922 + H1 51093)
- Pillar pass: 2021
- **Armed: 30** (M8 28)
- Scans: 501
- **Routes: 10** {'F': 9, 'C': 1}
- Placed: 4 (TP 4/4 non-null)
- **Fills: 3**
- **Trades: 3**

### TP accounting on placed orders (n=3)

- TP non-null rate: 100.0% (3/3)
- tp_source structural_swing: 1 (33.3%)
- tp_source atr_fallback: 2 (66.7%)
- tp_source none/other: 0

### Posture mix on armed

POSTURE DATA NOT AVAILABLE FROM THESE RUN ARTIFACTS.

The composition's run artifacts (armed_records.json, report.json, trades.csv) were inspected and contain no armed-posture field. The harness wrapped `PipelineEngine.arm_at` and counted postures in-memory, but the composition did not flush an armed-posture column and the in-memory counts were not persisted to disk by this harness's run_one path on these two runs.

Reported posture_mix below is therefore an empty placeholder and is NOT a measurement. The honest posture result for this window is UNKNOWN from the artifacts on disk.

For reference, the pre-TP-feed 6m funnel on the same window reported posture mix CLEAN 30 / IN_ZONE 0 / VIOLATION 0 (that harness persisted posture_log.json). The current product path's armed population is pillar-filtered; whatever its posture mix is, it is what it is - reported honestly when instrumentation is present.

### Exit mix

{
  "stop_loss": 2,
  "take_profit": 1,
  "be_scratch_subset": 1,
  "stop_loss_total": 2
}
### Per-trade detail (run1)

```
[
  {
    "ticket": "1",
    "direction": "short",
    "symbol": "",
    "volume": "0.1",
    "entry_price": "3281.298",
    "exit_price": "3310.402665496033",
    "sl": "3310.402665496033",
    "tp": "3271.8624600528956",
    "entry_bar": "5659",
    "exit_bar": "5776",
    "entry_at": "2025-06-30 12:05:00+00:00",
    "exit_at": "2025-06-30 22:50:00+00:00",
    "close_kind": "stop_loss",
    "win": "0",
    "pnl": "-2.910466549603325",
    "poi_id": "poi-014146",
    "trigger": "F",
    "route_id": "poi-014146:F@5653",
    "model_tags": "M8",
    "pillar_path": "PASS:1+2+3+4+5;inducement=1.0",
    "disp_magnitude_atr": "1.861090023795744",
    "original_sl": "3310.402665496033",
    "zone_low": "3281.298",
    "zone_high": "3309.695",
    "signal_data_json": "{\"bos_index\": 5650, \"entry_anchor\": \"zone_edge_reanchor\", \"ob_index\": 5648}",
    "entry_anchor": "zone_edge_reanchor",
    "tp_source": "atr_fallback"
  },
  {
    "ticket": "2",
    "direction": "short",
    "symbol": "",
    "volume": "0.1",
    "entry_price": "3490.257",
    "exit_price": "3486.405",
    "sl": "3493.985",
    "tp": "3486.405",
    "entry_bar": "18296",
    "exit_bar": "18297",
    "entry_at": "2025-09-02 13:45:00+00:00",
    "exit_at": "2025-09-02 13:50:00+00:00",
    "close_kind": "take_profit",
    "win": "1",
    "pnl": "0.3851999999999862",
    "poi_id": "poi-047805",
    "trigger": "C",
    "route_id": "poi-047805:C@18278",
    "model_tags": "M8",
    "pillar_path": "PASS:1+2+3+4+5;inducement=0.7",
    "disp_magnitude_atr": "2.2060123052942116",
    "original_sl": "3493.985",
    "zone_low": "3476.625",
    "zone_high": "3508.228",
    "signal_data_json": "{\"boundary\": 3490.257, \"converging\": false, \"terminal_index\": 18275}",
    "entry_anchor": "",
    "tp_source": "structural_swing"
  },
  {
    "ticket": "3",
    "direction": "long",
    "symbol": "",
    "volume": "0.1",
    "entry_price": "4244.725",
    "exit_price": "4245.440385166171",
    "sl": "4245.440385166171",
    "tp": "4275.664250362713",
    "entry_bar": "27585",
    "exit_bar": "27637",
    "entry_at": "2025-10-20 05:50:00+00:00",
    "exit_at": "2025-10-20 10:10:00+00:00",
    "close_kind": "stop_loss",
    "win": "0",
    "pnl": "0.0715385166170563",
    "poi_id": "poi-073511",
    "trigger": "F",
    "route_id": "poi-073511:F@27542",
    "model_tags": "M8",
    "pillar_path": "PASS:1+2+3+4+5;inducement=0.7",
    "disp_magnitude_atr": "1.327926723498081",
    "original_sl": "4177.034556222796",
    "zone_low": "4179.355",
    "zone_high": "4244.725",
    "signal_data_json": "{\"bos_index\": 27541, \"entry_anchor\": \"zone_edge_reanchor\", \"ob_index\": 27540}",
    "entry_anchor": "zone_edge_reanchor",
    "tp_source": "atr_fallback"
  }
]
```

### Determinism

- Funnel agreement run1==run2: True
- trades.csv SHA-256 run1/run2: 84a308be3f3272558c3d233af72c144b307bdf9b55b03eda6a50190c55ebb02b / 84a308be3f3272558c3d233af72c144b307bdf9b55b03eda6a50190c55ebb02b - IDENTICAL
- report.json SHA-256 run1/run2: 22d5665cac7c46e89fa802e1682d4266e939004ce992238d2e7bcc0bcfa50366 / 22d5665cac7c46e89fa802e1682d4266e939004ce992238d2e7bcc0bcfa50366 - IDENTICAL

### Net PnL (diagnostic, n=3)

- run1: -2.4537
- run2: -2.4537

---

## Comparison anchors (diagnostic only - NOT performance)

### vs pre-TP-feed 6m (same window, seek/scan Section 5a only)

- window: exec 2025-06-01 -> 2025-11-30 (load 2025-05-01, same contract, PRE-TP-feed)
- armed: 30
- routes: 10
- routes_by_trigger: {'F': 9, 'C': 1}
- fills: 3
- trades: 3
- note: seek/scan Section 5a only; TP stayed 4xATR (structural branch UNFED); posture mix CLEAN 30/IN_ZONE 0/VIOLATION 0; net -3.2117 diagnostic n=3

### vs post-TP-feed 3m (mechanism proof)
- window: exec 2025-09-01 -> 2025-11-30 (load 2025-08-01, POST-TP-feed mechanism proof)
- placed: 2
- tp_structural_share_pct: 50.0
- tp_atr_fallback_share_pct: 50.0
- tp_non_null_rate_pct: 100.0
- note: mechanism proof n=2; exit mix take_profit 1 + stop_loss 1; Trigger C poi-001022 flipped SL -0.3728 to structural TP +0.3852

### vs stage-3 lifecycle pack (same window)
- window: exec 2025-06-01 -> 2025-11-30 (pack window = this window)
- open_scan_share_pct: 78.33
- routes_replay: 196
- note: pre-pillar replay visibility, not the full product path

---

## Residuals / honesty notes

1. **Diagnostic only.** Every PnL figure here is labelled diagnostic n=3.
   It is not an edge claim, not a performance verdict, and not authorization for any threshold/filter/window change.
2. **Window frozen.** This is the same frozen 6m window used pre-TP-feed (exec 2025-06-01->11-30, load 2025-05-01). No widening, no cherry-picking.
3. **Non-CLEAN postures.** If the armed population arms CLEAN across all 6 months again (pre-TP 6m was CLEAN 30/IN_ZONE 0/VIOLATION 0), that is reported honestly - the product path's pillar-filtered armed population is what it is. Suite + pack-window replay remain the evidence for the other postures.
4. **TP shares are descriptive, not tuned.** If structural share is 0% on this window, that is reported honestly - the selector and fallback are proven by tests; the share is a sample outcome, not a target.
5. **Small filled sample.** Even at 6 months, expect small fill/trade counts. The measurement's value is TP-share observability + determinism + comparison anchors, not statistical significance.
6. **No strategy edits.** This harness imports the production composition; the redesign + TP feed are measured by running them.

---

*Generated by `06_RESEARCH/scripts/frozen_funnel_6m_post_tp.py` - diagnostic only.*
