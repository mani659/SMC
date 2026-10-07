# TRADE INSPECTOR — USAGE NOTE (Track V1)

Offline Python research chart renderer. Conviction and note-taking on
backtest/research artifacts. Not a live feature. Not an MT5 overlay.
No strategy code, no locked constants, no invented geometry.

## Entrypoint

```text
python 06_RESEARCH/scripts/trade_inspector.py {list,show,batch} --trades <trades.csv> [options]
```

| Command | Purpose | Key flags |
|---------|---------|-----------|
| `list` | list trades (filterable) | `--trigger F` `--outcome non-loss\|loss` `--limit N` |
| `show` | render one trade | `--ticket N` or `--route-id ...` |
| `batch` | render N trades by filter | `--trigger` `--outcome` `--limit` |

Common flags: `--parquet` (default canonical M1), `--out-dir`
(default `06_RESEARCH/results/trade_inspector/`), `--r3-path`
(R3 identity join; silently skipped if absent), `--no-enrich`
(identity panel only, no MFE/failure computation).

Notebook: `from trade_inspector import list_trades, render_trade`
(`render_trade(trade, bars, out_dir, enrichment=...)`).

## What each chart shows

Candlestick window (entry ± 60 bars) + entry line + SL dashed line +
exit-X marker + fill-bar shading + identity panel:
trigger, model_tags, pillar_path, disp_magnitude_atr, direction,
MFE_R/MAE_R + failure_mode (R3-joined when the route matches, else
computed live by R1/R3 rules — provenance shown), entry/SL/exit/pnl,
bars, `zone geometry unavailable` (POI bounds are in no export).

Sidecar JSON per trade carries the same fields plus timestamp range,
hold_bars, window bars, and an empty `notes` field for human annotation.

## Honest behaviors worth knowing

- **Timestamp-anchored bars.** Short-window exports number bars from the
  window start, so `entry_bar` cannot index the canonical series.
  Resolution is by `entry_at`/`exit_at` timestamp; mode is recorded
  (`timestamp` vs `raw_index` fallback).
- **Spike-robust ylim.** 0.5/99.5 percentile window range, always expanded
  to include entry/SL/exit overlays.
- **Enrichment provenance.** `r3_joined` = values from the Phase C
  analysis (route matched); `computed_live` = R1-method MFE over the
  trade's own window + R3-taxonomy failure mode. Both are measurement,
  not trading claims.
- **Curated set** (flowchart/KB matching starter):
  `results/trade_inspector/curated/` — 5 F non-loss, 5 F loss, all 3 B
  from the instrumented verify window. Every chart carries non-empty
  model_tags + pillar_path + disp_magnitude_atr.

## Deps

matplotlib only (Agg backend, headless PNG). ASCII annotations throughout.
