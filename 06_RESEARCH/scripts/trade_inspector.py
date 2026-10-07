"""Track V1 — offline Python research trade inspector / chart renderer.

Conviction and note-taking on backtest/research artifacts. Not a live
trading feature. Not an MT5 overlay.

For a selected trade: price window around the event, entry/SL lines,
exit marker, and an identity panel (trigger, model tags, pillar path,
displacement magnitude, direction, prices, bars, P/L). Geometry absent
from the export (e.g. POI zone bounds) is labeled unknown — never invented.

Inputs: a backtest `trades.csv` WITH identity columns (model_tags,
pillar_path, disp_magnitude_atr — see EXPORT_IDENTITY_PATCH_NOTE.md) +
canonical `07_DATA/XAUUSD_M1.parquet` (read directly; research-only use).

Outputs per inspected trade under --out-dir (default
06_RESEARCH/results/trade_inspector/):
    ticket_<n>.png   — candlestick chart + overlays + identity panel
    ticket_<n>.json  — sidecar: identity fields + notes placeholders

Commands:
    list    trades in an export (filterable)
    show    render one trade by ticket or route_id
    batch   render N trades by filter

Notebook use: from trade_inspector import list_trades, render_trade.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
DEFAULT_OUT = REPO_ROOT / "06_RESEARCH" / "results" / "trade_inspector"

PAD_BARS = 60


# ---------------------------------------------------------------------- #
# Data loading (pandas-free CSV; parquet via pandas — research only)
# ---------------------------------------------------------------------- #
def load_trades(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_bars(parquet: str | Path = DEFAULT_PARQUET):
    """Return (timestamps, opens, highs, lows, closes) as lists."""
    import pandas as pd

    frame = pd.read_parquet(parquet, columns=["timestamp", "open", "high",
                                              "low", "close"])
    return (list(frame["timestamp"]), list(frame["open"]),
            list(frame["high"]), list(frame["low"]), list(frame["close"]))


def filter_trades(trades: list[dict], *, trigger: str | None = None,
                  outcome: str | None = None,
                  limit: int | None = None) -> list[dict]:
    """Filter by trigger and/or outcome ('non-loss' = pnl>0, 'loss' = pnl<=0)."""
    out = [t for t in trades
           if (trigger is None or (t.get("trigger") or "") == trigger)
           and (outcome is None
                or (outcome == "non-loss" and float(t.get("pnl") or 0) > 0)
                or (outcome == "loss" and float(t.get("pnl") or 0) <= 0))]
    return out[:limit] if limit is not None else out


def load_r3_join(path: str | Path | None = None) -> dict:
    """R3 identity rows keyed by route_id (failure_mode/MFE_R/MAE_R).

    Missing file or route → empty/absent (caller falls back to live
    computation, marked as such — never invented).
    """
    default = (REPO_ROOT / "06_RESEARCH" / "results" / "r3_attribution"
               / "trades_identity.csv")
    path = Path(path) if path else default
    if not path.is_file():
        return {}
    with open(path, newline="", encoding="utf-8") as handle:
        return {row["route_id"]: row for row in csv.DictReader(handle)}


def live_excursion(trade: dict, bars) -> dict:
    """R1-method MFE/MAE over the trade's own window + R3-taxonomy mode.

    Returns MFE_R/MAE_R floored at 0, never_favorable flag, failure_mode,
    provenance='computed_live'. Close-kind/pnl decide friday/be classes
    exactly like the R3 taxonomy (friday_artifact → be_scratch →
    instant_stop → no_follow_through → gave_back).
    """
    _ts, _opens, highs, lows, _closes = bars
    b0, _a0 = _resolve_bar(_ts, trade.get("entry_at"), trade["entry_bar"])
    b1, _a1 = _resolve_bar(_ts, trade.get("exit_at"), trade["exit_bar"])
    if b1 < b0:
        b0, b1 = b1, b0
    entry = float(trade["entry_price"])
    # Prefer the placement stop: working sl may be BE-modified, which would
    # inflate R multiples (see FLOWCHART_MATCH_NOTES.md §0).
    ref_sl = trade.get("original_sl") or trade["sl"]
    risk = abs(entry - float(ref_sl))
    is_long = (trade.get("direction") or "").lower() == "long"
    fav, adv = [], []
    for b in range(b0, b1 + 1):
        if is_long:
            fav.append(highs[b] - entry)
            adv.append(entry - lows[b])
        else:
            fav.append(entry - lows[b])
            adv.append(highs[b] - entry)
    raw_mfe, raw_mae = max(fav), max(adv)
    never_fav = raw_mfe < 0
    mfe_r = max(raw_mfe, 0.0) / risk
    mae_r = max(raw_mae, 0.0) / risk
    pnl = float(trade.get("pnl") or 0)
    if (trade.get("close_kind") or "") == "friday_eod":
        mode = "friday_artifact"
    elif pnl > 0:
        mode = "be_scratch"
    elif never_fav:
        mode = "instant_stop"
    elif mfe_r < 1.0:
        mode = "no_follow_through"
    else:
        mode = "gave_back"
    return {"MFE_R": mfe_r, "MAE_R": mae_r, "failure_mode": mode,
            "never_favorable": never_fav, "provenance": "computed_live"}


def enrich_trade(trade: dict, bars, r3: dict | None = None) -> dict:
    """Attach MFE_R/MAE_R/failure_mode: R3 join wins, else live computation."""
    hit = (r3 or {}).get(trade.get("route_id") or "")
    if hit:
        return {"MFE_R": float(hit["MFE_R"]), "MAE_R": float(hit["MAE_R"]),
                "failure_mode": hit["failure_mode"], "provenance": "r3_joined"}
    return live_excursion(trade, bars)


def find_trade(trades: list[dict], *, ticket: str | None = None,
               route_id: str | None = None) -> dict:
    if route_id is not None:
        for trade in trades:
            if trade.get("route_id") == route_id:
                return trade
        raise LookupError(f"no trade route_id={route_id}")
    # Tickets restart per segment in merged multi-segment exports, so a
    # ticket may match several rows — refuse ambiguity loudly instead of
    # silently rendering the first match.
    matches = [t for t in trades if str(t.get("ticket")) == str(ticket)]
    if not matches:
        raise LookupError(f"no trade ticket={ticket}")
    if len(matches) > 1:
        raise LookupError(
            f"ticket={ticket} matches {len(matches)} rows "
            f"({', '.join(str(t.get('route_id')) for t in matches)}); "
            f"re-run with --route-id")
    return matches[0]


def list_trades(trades: list[dict], *, trigger: str | None = None,
                outcome: str | None = None,
                limit: int | None = None) -> list[dict]:
    """Notebook-friendly listing (filtered trade dicts)."""
    return filter_trades(trades, trigger=trigger, outcome=outcome, limit=limit)


# ---------------------------------------------------------------------- #
# Rendering (matplotlib Agg — headless PNG, ASCII-only annotations)
# ---------------------------------------------------------------------- #
def _resolve_bar(ts_list, stamp: str | None, fallback) -> tuple[int, str]:
    """Timestamp-anchored bar lookup (window-relative exports safe).

    Short-window exports (e.g. export_patch_verify) number bars from the
    window start, NOT the canonical series — so raw entry_bar/exit_bar
    cannot index the full parquet. Timestamps are the stable key.
    Returns (index, mode) with mode 'timestamp' or 'raw_index'.
    """
    if stamp:
        key = str(stamp)[:16]
        for i, ts in enumerate(ts_list):
            if str(ts)[:16] == key:
                return i, "timestamp"
    return int(fallback), "raw_index"


def render_trade(trade: dict, bars, out_dir: str | Path,
                 *, pad: int = PAD_BARS,
                 enrichment: dict | None = None) -> tuple[Path, Path]:
    """Render one trade chart + sidecar. Returns (png_path, json_path).

    ``enrichment`` carries MFE_R/MAE_R/failure_mode/provenance (see
    :func:`enrich_trade`); absent → panel marks those fields unknown.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    ts_list, opens, highs, lows, closes = bars
    b0, anchor0 = _resolve_bar(ts_list, trade.get("entry_at"),
                               trade["entry_bar"])
    b1, anchor1 = _resolve_bar(ts_list, trade.get("exit_at"),
                               trade["exit_bar"])
    if b1 < b0:
        b0, b1 = b1, b0
    n = len(closes)
    lo, hi = max(0, b0 - pad), min(n, b1 + pad + 1)
    idx = list(range(lo, hi))
    direction = (trade.get("direction") or "").lower()
    entry = float(trade["entry_price"])
    # Prefer the placement stop: working sl may be BE-modified
    # (see FLOWCHART_MATCH_NOTES.md section 0).
    if trade.get("original_sl") not in (None, ""):
        sl = float(trade["original_sl"])
        sl_source = "original_sl"
    elif trade.get("sl") not in (None, ""):
        sl = float(trade["sl"])
        sl_source = "working_sl"
    else:
        sl, sl_source = None, "unknown"
    exit_price = float(trade["exit_price"])
    zone_txt, zone_low, zone_high = "zone geometry unavailable", None, None
    if trade.get("zone_low") not in (None, "") and trade.get("zone_high") not in (None, ""):
        zone_low, zone_high = float(trade["zone_low"]), float(trade["zone_high"])
        height = zone_high - zone_low
        if height > 0 and zone_low <= entry <= zone_high:
            zone_txt = "entry INSIDE zone"
        elif height > 0:
            off = (entry - zone_high) if entry > zone_high else (zone_low - entry)
            side = "above" if entry > zone_high else "below"
            zone_txt = f"entry {off:.3f} {side} zone ({100.0 * off / height:.0f}% of height)"
        else:
            zone_txt = "zone degenerate (zero height)"

    fig, (ax_price, ax_id) = plt.subplots(
        2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [3, 1]})
    fig.suptitle(f"ticket={trade.get('ticket')} "
                 f"route={trade.get('route_id') or 'n/a'} "
                 f"{direction} {trade.get('trigger') or 'n/a'}",
                 fontsize=11, fontweight="bold")

    # Candlesticks (manual — no mplfinance dependency).
    for i, b in enumerate(idx):
        color = "g" if closes[b] >= opens[b] else "r"
        ax_price.plot([i, i], [lows[b], highs[b]], color=color, linewidth=0.8)
        top, bottom = max(opens[b], closes[b]), min(opens[b], closes[b])
        ax_price.add_patch(Rectangle((i - 0.3, bottom), 0.6,
                                     max(top - bottom, 1e-9),
                                     facecolor=color, edgecolor=color))
    # Overlays: entry (blue), SL (red dashed), exit marker.
    ax_price.axhline(entry, color="blue", linewidth=1.2, label=f"entry {entry}")
    if sl is not None:
        ax_price.axhline(sl, color="red", linestyle="--", linewidth=1.2,
                         label=f"SL {sl} ({sl_source})")
    if zone_low is not None and zone_high is not None and zone_high > zone_low:
        ax_price.axhspan(zone_low, zone_high, color="purple", alpha=0.12,
                         label="POI zone")
    ex = b1 - lo
    ax_price.plot(ex, exit_price, marker="x", markersize=10,
                  color="black", markeredgewidth=2,
                  label=f"exit {exit_price} ({trade.get('close_kind') or 'n/a'})")
    # Entry-bar shading (fill bar — first bar of the position).
    ax_price.axvspan(b0 - lo - 0.5, b0 - lo + 0.5, color="blue", alpha=0.08)
    # Spike-robust y-limits: 0.5/99.5 percentiles of the window range,
    # expanded to always include entry/SL/exit overlays.
    import numpy as np
    w_lows = np.array([lows[b] for b in range(lo, hi)])
    w_highs = np.array([highs[b] for b in range(lo, hi)])
    y0, y1 = float(np.percentile(w_lows, 0.5)), float(np.percentile(w_highs, 99.5))
    for level in [entry, exit_price] + ([sl] if sl is not None else []):
        y0, y1 = min(y0, level), max(y1, level)
    pad_y = max((y1 - y0) * 0.05, 1e-9)
    ax_price.set_ylim(y0 - pad_y, y1 + pad_y)
    ax_price.set_xlim(-1, len(idx))
    ax_price.set_ylabel("price")
    ax_price.legend(loc="upper left", fontsize=8)
    ax_price.grid(True, alpha=0.3)

    # Identity panel (unknown labeled, never invented).
    models = trade.get("model_tags") or "unknown"
    pillar = trade.get("pillar_path") or "unknown"
    disp = trade.get("disp_magnitude_atr")
    disp_txt = f"{float(disp):.3f} ATR" if disp not in (None, "") else "unknown"
    enrichment = enrichment or {}
    mfe_txt = (f"{enrichment['MFE_R']:.2f}R"
               if enrichment.get("MFE_R") is not None else "unknown")
    mae_txt = (f"{enrichment['MAE_R']:.2f}R"
               if enrichment.get("MAE_R") is not None else "unknown")
    fail_txt = enrichment.get("failure_mode") or "unknown"
    prov_txt = enrichment.get("provenance") or "unknown"
    panel = [
        f"direction : {direction or 'unknown'}   "
        f"trigger : {trade.get('trigger') or 'unknown'}",
        f"models    : {models}",
        f"pillar    : {pillar}",
        f"disp      : {disp_txt}",
        f"mfe {mfe_txt}   mae {mae_txt}   failmode: {fail_txt} ({prov_txt})",
        f"entry {entry}   SL {trade.get('sl') or 'unknown'}   "
        f"exit {exit_price}   pnl {trade.get('pnl') or 'n/a'}",
        f"bars {b0} -> {b1} (hold {b1 - b0})   {zone_txt}",
        f"poi {trade.get('poi_id') or 'unknown'}   anchor: {anchor0}/{anchor1}",
    ]
    ax_id.axis("off")
    ax_id.text(0.01, 0.95, "\n".join(panel), transform=ax_id.transAxes,
               fontsize=9, family="monospace", verticalalignment="top",
               bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.4))
    ax_id.text(0.01, 0.02, "NOTES: ", transform=ax_id.transAxes,
               fontsize=9, family="monospace", verticalalignment="bottom")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    png = out / f"ticket_{trade.get('ticket')}.png"
    fig.savefig(png, dpi=100)
    plt.close(fig)

    enrichment = enrichment or {}
    sidecar = {
        "ticket": trade.get("ticket"), "route_id": trade.get("route_id"),
        "poi_id": trade.get("poi_id"), "trigger": trade.get("trigger"),
        "direction": direction, "model_tags": trade.get("model_tags") or None,
        "pillar_path": trade.get("pillar_path") or None,
        "disp_magnitude_atr": trade.get("disp_magnitude_atr") or None,
        "entry_price": entry, "sl": trade.get("sl") or None,
        "sl_display_source": sl_source,
        "exit_price": exit_price, "entry_bar": b0, "exit_bar": b1,
        "hold_bars": b1 - b0, "zone_relation": zone_txt,
        "timestamp_range": [str(trade.get("entry_at")),
                            str(trade.get("exit_at"))],
        "close_kind": trade.get("close_kind"), "pnl": trade.get("pnl"),
        "MFE_R": enrichment.get("MFE_R"), "MAE_R": enrichment.get("MAE_R"),
        "failure_mode": enrichment.get("failure_mode"),
        "enrichment_provenance": enrichment.get("provenance"),
        "window_bars": [lo, hi - 1], "poi_zone": "unavailable_not_exported",
        "notes": "",
    }
    js = out / f"ticket_{trade.get('ticket')}.json"
    js.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    return png, js


# ---------------------------------------------------------------------- #
# CLI
# ---------------------------------------------------------------------- #
def _add_common(sub):
    sub.add_argument("--trades", required=True, help="trades.csv WITH identity columns")
    sub.add_argument("--parquet", default=str(DEFAULT_PARQUET))
    sub.add_argument("--out-dir", default=str(DEFAULT_OUT))
    sub.add_argument("--r3-path", default=None,
                     help="R3 trades_identity.csv for failure-mode joins "
                          "(default: standard path, silently skipped if absent)")
    sub.add_argument("--no-enrich", action="store_true",
                     help="skip MFE/failure-mode enrichment (identity panel only)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SMC research trade inspector (V1)")
    subs = ap.add_subparsers(dest="cmd", required=True)

    p_list = subs.add_parser("list", help="list trades in an export")
    _add_common(p_list)
    p_list.add_argument("--trigger", default=None)
    p_list.add_argument("--outcome", default=None,
                        choices=[None, "non-loss", "loss"])
    p_list.add_argument("--limit", type=int, default=20)

    p_show = subs.add_parser("show", help="render one trade")
    _add_common(p_show)
    p_show.add_argument("--ticket", default=None)
    p_show.add_argument("--route-id", default=None)

    p_batch = subs.add_parser("batch", help="render N trades by filter")
    _add_common(p_batch)
    p_batch.add_argument("--trigger", default=None)
    p_batch.add_argument("--outcome", default=None,
                         choices=[None, "non-loss", "loss"])
    p_batch.add_argument("--limit", type=int, default=5)

    args = ap.parse_args(argv)
    trades = load_trades(args.trades)
    r3 = {} if args.no_enrich else load_r3_join(args.r3_path)

    if args.cmd == "list":
        for trade in filter_trades(trades, trigger=args.trigger,
                                   outcome=args.outcome, limit=args.limit):
            print(f"ticket={trade.get('ticket')} {trade.get('direction')} "
                  f"{trade.get('trigger')} models={trade.get('model_tags') or '-'} "
                  f"pillar={(trade.get('pillar_path') or '-')[:24]} "
                  f"disp={trade.get('disp_magnitude_atr') or '-'} "
                  f"pnl={trade.get('pnl')} route={trade.get('route_id')}")
        return 0

    bars = load_bars(args.parquet)

    def _enrich(trade):
        if args.no_enrich:
            return {}
        return enrich_trade(trade, bars, r3)

    if args.cmd == "show":
        if args.ticket is None and args.route_id is None:
            print("show needs --ticket or --route-id", file=sys.stderr)
            return 2
        trade = find_trade(trades, ticket=args.ticket, route_id=args.route_id)
        png, js = render_trade(trade, bars, args.out_dir,
                               enrichment=_enrich(trade))
        print(f"wrote {png} + {js}")
        return 0

    selected = filter_trades(trades, trigger=args.trigger,
                             outcome=args.outcome, limit=args.limit)
    for trade in selected:
        png, js = render_trade(trade, bars, args.out_dir,
                               enrichment=_enrich(trade))
        print(f"wrote {png}")
    print(f"batch done: {len(selected)} trades")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
