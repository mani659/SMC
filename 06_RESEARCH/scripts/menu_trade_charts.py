#!/usr/bin/env python
"""MENU TRADE CHART PACK — 9 closed fills (eyes, no retune).

Reruns the menu-path funnel for 2024-04-01..2024-05-01 (same deterministic
harness/setup as menu_trade_funnel.py) to recover POI zone geometry and menu
stamps for the 9 closed trades, then renders a 2-panel chart per trade:
  - detection TF panel: candles + zone band (if recovered) + sweep/confirm/entry/exit marks
  - confirm TF panel:   candles + entry/SL/TP/exit levels + entry/exit marks

Stage: quality review after stage-success fills. LOGIC_CHANGED: NO. No edge/PnL.

Outputs (gitignored charts dir + committed note):
  06_RESEARCH/results/menu_trade_charts_1m/ticket_{t}_{poi}.png  (9)
  06_RESEARCH/results/menu_trade_charts_1m/chart_index.json
  06_RESEARCH/MENU_TRADE_CHARTS_1M_NOTE.md
"""

from __future__ import annotations

import bisect
import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
SCRIPTS_DIR = REPO_ROOT / "06_RESEARCH" / "scripts"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from smc.backtest.bar_loop import BarLoop  # noqa: E402
from smc.backtest.cost_model import CostConfig  # noqa: E402
from smc.backtest.data_feed import CandleSeries  # noqa: E402
from smc.backtest.pipeline_adapter import PipelineAdapter  # noqa: E402
from smc.backtest.runner import BacktestRunner, RunnerConfig  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402
from smc.data.resample import resample_ohlcv  # noqa: E402
from smc.orchestration.engine import PipelineEngine  # noqa: E402
from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime  # noqa: E402
from smc.orchestration.product_menu_mtf import ProductMenuEngine  # noqa: E402
from smc.risk.risk_engine import RiskEngine  # noqa: E402
from smc.utils.timestamps import Session, to_utc  # noqa: E402

from plan_complement_ledger import load_m1  # noqa: E402
import menu_trade_funnel as funnel  # noqa: E402

TRADES_CSV = REPO_ROOT / "06_RESEARCH/results/menu_trade_funnel_1m/trades.csv"
DROPS_CSV = REPO_ROOT / "06_RESEARCH/results/menu_trade_funnel_1m/drops.csv"
OUT_DIR = Path(
    os.environ.get(
        "MENU_CHART_OUT",
        str(REPO_ROOT / "06_RESEARCH/results/menu_trade_charts_1m"),
    )
)
NOTE_PATH = REPO_ROOT / "06_RESEARCH/MENU_TRADE_CHARTS_1M_NOTE.md"

TF_BY_NAME = {
    "M1": Timeframe.M1,
    "M5": Timeframe.M5,
    "M15": Timeframe.M15,
    "H1": Timeframe.H1,
    "H4": Timeframe.H4,
    "D1": Timeframe.D1,
}


@dataclass
class Target:
    ticket: int
    poi_id: str
    route_id: str
    direction: str
    entry_price: float
    sl_at_entry: float
    tp_price: float
    entry_at: datetime
    exit_at: datetime
    exit_price: float
    kind: str
    be_scratch: str
    pnl_raw: float
    det_tf: str
    conf_tf: str
    tier: str
    sweep_ts: str | None
    confirm_at: str | None
    trigger: str | None
    tp_source: str | None
    zone_low: float | None = None
    zone_high: float | None = None
    zone_type: str | None = None
    zone_dir: str | None = None


def _parse_ts(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).strip()
    if not s or s.lower() == "none":
        return None
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _ts_iso(value):
    dt = _parse_ts(value)
    return dt.isoformat() if dt else None


def load_targets():
    trades = list(csv.DictReader(TRADES_CSV.open(encoding="utf-8")))
    drops = list(csv.DictReader(DROPS_CSV.open(encoding="utf-8")))
    by_poi = {d["poi_id"]: d for d in drops}
    targets = []
    for t in trades:
        d = by_poi[t["poi_id"]]
        targets.append(
            Target(
                ticket=int(t["ticket"]),
                poi_id=t["poi_id"],
                route_id=t.get("route_id") or "",
                direction=t["direction"],
                entry_price=float(t["entry_price"]),
                sl_at_entry=float(t["sl_at_entry"]),
                tp_price=float(t["tp_price"]),
                entry_at=_parse_ts(t["entry_at"]),
                exit_at=_parse_ts(t["exit_at"]),
                exit_price=float(t["exit_price"]),
                kind=t["kind"],
                be_scratch=t.get("be_scratch_derived", "NO"),
                pnl_raw=float(t["realized_pnl_raw"]),
                det_tf=d.get("detection_tf") or "",
                conf_tf=d.get("confirmation_tf") or "",
                tier=d.get("tier") or d.get("detection_tf") or "",
                sweep_ts=_ts_iso(d.get("t_sweep") or d.get("sweep_ts")),
                confirm_at=_ts_iso(d.get("t_confirm") or d.get("confirm_at")),
                trigger=(d.get("trigger") or None),
                tp_source=(d.get("tp_source") or None),
            )
        )
    non_closed = [d for d in drops if d.get("stage") != "closed"]
    return targets, non_closed


def capture_context(targets):
    """Rerun the month (deterministic, same setup as menu_trade_funnel.run)."""
    want = {t.poi_id: t for t in targets}
    captured = {}

    funnel.install_deterministic_poi_ids()

    m1_all = load_m1(funnel.DATA_PATH, funnel.WARMUP_START, funnel.WINDOW_END)
    needed = set(funnel.DETECTION_TFS) | set(funnel.FEED_TFS) | {funnel.EXEC_TF}
    series = {}
    for tf in sorted(needed, key=lambda x: x.minutes, reverse=True):
        series[tf] = resample_ohlcv(m1_all, tf)

    exec_all = series[funnel.EXEC_TF]
    window_bars = [c for c in exec_all if c.timestamp >= funnel.WINDOW_START]
    m15_window = [
        c for c in series[Timeframe.M15]
        if funnel.WINDOW_START <= c.timestamp < funnel.WINDOW_END
    ]
    batch_instants = {
        funnel._close_ts(m15_window[i])
        for i in range(0, len(m15_window), funnel.BATCH_EVERY_M15_BARS)
    }

    engine = PipelineEngine()
    menu = ProductMenuEngine(symbol="XAUUSD")
    adapter = PipelineAdapter(engine, timeframe=funnel.EXEC_TF, menu_confirmation=menu)
    adapter.set_candles(exec_all)
    runtime = MultiTFProductRuntime(
        detection_timeframes=funnel.DETECTION_TFS, execution_timeframe=funnel.EXEC_TF
    )
    order_book = funnel.CountingOrderBook()
    positions = funnel.CountingPositionStore()
    runner = BacktestRunner(
        risk_engine=RiskEngine(),
        order_book=order_book,
        position_store=positions,
        config=RunnerConfig(
            equity=10_000.0,
            risk_fraction=0.01,
            pip_value_per_lot=10.0,
            min_lots=0.01,
            lot_step=0.01,
            allowed_sessions=(Session.ASIA, Session.LONDON, Session.NEW_YORK),
            news_events=[],
            timeframe=funnel.EXEC_TF,
            spread_price=0.0,
            cost=CostConfig(),
        ),
    )
    adapter.attach(runner)

    cycle = funnel.MenuCycle(
        runner=runner,
        adapter=adapter,
        runtime=runtime,
        engine=engine,
        menu=menu,
        series=series,
        exec_bars=exec_all,
        batch_instants=batch_instants,
        total_bars=len(window_bars),
        started_at=__import__("time").perf_counter(),
    )

    def try_capture(poi_id, stamp=None):
        if not poi_id or poi_id not in want:
            return
        info = captured.setdefault(poi_id, {"poi_id": poi_id})
        store = getattr(runtime, "poi_store", None)
        poi = store.get(poi_id) if store else None
        if poi is not None and info.get("zone_low") is None:
            info["zone_low"] = getattr(poi, "zone_low", None)
            info["zone_high"] = getattr(poi, "zone_high", None)
            info["zone_dir"] = str(getattr(poi, "direction", "") or "")
            info["zone_type"] = str(getattr(poi, "poi_type", "") or "")
        if stamp:
            for k in ("sweep_ts", "confirm_at", "trigger", "tp_source", "tier", "armed_ts"):
                v = stamp.get(k)
                if v and not info.get(k):
                    info[k] = v

    # Wrap on_bar to snapshot zone/stamp info whenever a target appears as a
    # winner (cycle.winners grows inside MenuCycle.on_bar).
    orig_on_bar = cycle.on_bar
    seen_w = 0

    def on_bar_with_capture(bar, bar_index, clock):
        nonlocal seen_w
        orig_on_bar(bar, bar_index, clock)
        for w in cycle.winners[seen_w:]:
            poi_id = w.get("poi_id") if isinstance(w, dict) else getattr(w, "poi_id", None)
            stamp = {}
            cand = w.get("candidate") if isinstance(w, dict) else getattr(w, "candidate", None)
            if cand is not None:
                try:
                    stamp = json.loads(getattr(cand, "signal_data_json", "{}") or "{}").get("product_menu", {}) or {}
                except Exception:
                    stamp = {}
            # candidate-level trigger/tp_source may live on the candidate object
            if cand is not None:
                if not stamp.get("trigger") and getattr(cand, "trigger", None):
                    stamp["trigger"] = getattr(cand, "trigger", None)
                if not stamp.get("tp_source") and getattr(cand, "tp_source", None):
                    stamp["tp_source"] = getattr(cand, "tp_source", None)
            try_capture(poi_id, stamp)
        seen_w = len(cycle.winners)
        # opportunistic: try store for any still-missing target
        for pid in list(want):
            if captured.get(pid, {}).get("zone_low") is None:
                try_capture(pid)

    cycle.on_bar = on_bar_with_capture

    loop = BarLoop(CandleSeries(exec_all, funnel.EXEC_TF), cycle)
    print("rerunning month to capture zones/stamps...", flush=True)
    loop.run(start_timestamp=funnel.WINDOW_START, end_timestamp=window_bars[-1].timestamp)
    print(f"rerun done. winners={len(cycle.winners)} captured={len(captured)}", flush=True)

    # final pass
    for pid in list(want):
        try_capture(pid)

    for t in targets:
        info = captured.get(t.poi_id, {})
        if info.get("zone_low") is not None:
            t.zone_low = float(info["zone_low"])
            t.zone_high = float(info["zone_high"])
        t.zone_dir = info.get("zone_dir") or t.zone_dir
        t.zone_type = info.get("zone_type") or t.zone_type
        if not t.sweep_ts and info.get("sweep_ts"):
            t.sweep_ts = _ts_iso(info.get("sweep_ts"))
        if not t.confirm_at and info.get("confirm_at"):
            t.confirm_at = _ts_iso(info.get("confirm_at"))
        if not t.trigger and info.get("trigger"):
            t.trigger = str(info.get("trigger"))
        if not t.tp_source and info.get("tp_source"):
            t.tp_source = str(info.get("tp_source"))
    return captured


# ---------------- charting ---------------- #

def _slice_series(series, center_dt, n_each):
    times = [to_utc(c.timestamp) for c in series]
    i = bisect.bisect_left(times, center_dt)
    i = max(0, min(i, len(series) - 1))
    lo = max(0, i - n_each)
    hi = min(len(series), i + n_each + 1)
    return series[lo:hi]


def _plot_candles(ax, candles, title):
    if not candles:
        ax.set_title(title + " (no data)", fontsize=9)
        return
    xs = []
    for c in candles:
        t = mdates.date2num(to_utc(c.timestamp))
        xs.append(t)
        up = c.close >= c.open
        color = "#26a69a" if up else "#ef5350"
        ax.vlines(t, c.low, c.high, color=color, linewidth=0.7)
        lo, hi = (c.open, c.close) if up else (c.close, c.open)
        h = max(hi - lo, (c.high - c.low) * 0.04 + 1e-9)
        ax.add_patch(Rectangle((t - 0.00045, lo), 0.0009, h, facecolor=color, edgecolor=color, linewidth=0.3))
    ax.set_xlim(min(xs) - 0.002, max(xs) + 0.002)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M", tz=timezone.utc))
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(25)
        lbl.set_ha("right")
        lbl.set_fontsize(7)
    ax.set_title(title, fontsize=9)
    ax.grid(True, alpha=0.2)


def _vline(ax, ts, label, color, ls="--"):
    dt = _parse_ts(ts)
    if not dt:
        return
    ax.axvline(mdates.date2num(dt), color=color, linestyle=ls, linewidth=1.0, alpha=0.85, label=label)


def render_trade(t, m1_all, series_cache):
    det_tf = TF_BY_NAME.get(t.det_tf, Timeframe.M15)
    conf_tf = TF_BY_NAME.get(t.conf_tf, Timeframe.M1)
    det_series = series_cache.setdefault(det_tf, resample_ohlcv(m1_all, det_tf) if det_tf != Timeframe.M1 else m1_all)
    conf_series = series_cache.setdefault(conf_tf, resample_ohlcv(m1_all, conf_tf) if conf_tf != Timeframe.M1 else m1_all)

    det_c = _slice_series(det_series, t.entry_at, 70)
    conf_c = _slice_series(conf_series, t.entry_at, 90)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 8.5), constrained_layout=True)

    # detection panel
    ztxt = "zone n/a"
    _plot_candles(ax1, det_c, f"Detection {t.det_tf} — {t.poi_id} ({t.tier}, {t.direction}{' '+t.zone_type if t.zone_type else ''})")
    if t.zone_low is not None and t.zone_high is not None:
        ax1.axhspan(t.zone_low, t.zone_high, color="#4c78a8", alpha=0.18, label=f"zone {t.zone_low:.2f}-{t.zone_high:.2f}")
        ztxt = f"{t.zone_low:.2f}-{t.zone_high:.2f}"
    _vline(ax1, t.sweep_ts, "sweep", "#9467bd", "-.")
    _vline(ax1, t.confirm_at, "confirm", "#ff7f0e", ":")
    _vline(ax1, t.entry_at, "entry", "#17becf", "--")
    _vline(ax1, t.exit_at, "exit", "#7f7f7f", "-")
    ax1.legend(loc="upper left", fontsize=7, ncol=4)

    # confirm panel
    _plot_candles(ax2, conf_c, f"Confirmation {t.conf_tf} — levels & outcome")
    for y, lbl, col, ls in [
        (t.entry_price, f"entry {t.entry_price:.3f}", "#17becf", "-"),
        (t.sl_at_entry, f"SL(orig) {t.sl_at_entry:.3f}", "#d62728", "--"),
        (t.tp_price, f"TP {t.tp_price:.3f}", "#2ca02c", "--"),
        (t.exit_price, f"exit {t.exit_price:.3f} ({t.kind})", "#111111", "-."),
    ]:
        ax2.axhline(y, color=col, linestyle=ls, linewidth=1.0, alpha=0.85, label=lbl)
    _vline(ax2, t.entry_at, "entry", "#17becf", "--")
    _vline(ax2, t.exit_at, "exit", "#7f7f7f", "-")
    ax2.legend(loc="upper left", fontsize=7, ncol=3)

    cap = (f"ticket {t.ticket} | {t.poi_id} | {t.route_id} | {t.det_tf}->{t.conf_tf} | {t.direction} | tier={t.tier} | "
           f"trigger={t.trigger or 'n/a'} | tp_src={t.tp_source or 'n/a'} | exit={t.kind} | "
           f"be_scratch={t.be_scratch} | pnl_raw={t.pnl_raw:.6f} (NOT edge)")
    fig.suptitle(cap, fontsize=8.5)
    fig.text(0.5, 0.01, "DIAGNOSTIC — quality review, NOT edge/PnL", ha="center", fontsize=8, color="#555555")

    fname = f"ticket_{t.ticket}_{t.poi_id}.png"
    fig.savefig(OUT_DIR / fname, dpi=130)
    plt.close(fig)
    return fname


def write_note(targets, non_closed, index):
    lines = []
    lines.append("# Menu trade chart pack — 9 closed fills (1m, 2024-04)")
    lines.append("")
    lines.append("`LOGIC_CHANGED: NO`. Quality review after stage-success fills. **No PnL ranking, not edge.**")
    lines.append("")
    lines.append("Source: `06_RESEARCH/results/menu_trade_funnel_1m/trades.csv` + `drops.csv` (joined by `poi_id`).")
    lines.append(f"Charts (gitignored): `06_RESEARCH/results/menu_trade_charts_1m/` ({len(index)} charts).")
    lines.append("Script: `06_RESEARCH/scripts/menu_trade_charts.py` (deterministic rerun of the same menu-path harness to recover zone/stamps).")
    lines.append("")
    lines.append("## Index — 9 closed paths")
    lines.append("")
    lines.append("| # | Ticket | POI | Route | Tier | Det→Conf | Dir | Trigger | TP src | Exit | BE | PnL raw | Chart | Zone (recovered) | Sweep | Confirm |")
    lines.append("|---:|---:|---|---|---|---|---|---|---|---|---|---:|---|---|---|---|")
    for i, (t, rec) in enumerate(zip(targets, index), 1):
        zone = f"{t.zone_low:.2f}-{t.zone_high:.2f}" if t.zone_low is not None and t.zone_high is not None else "n/a"
        lines.append(
            f"| {i} | {t.ticket} | {t.poi_id} | {t.route_id} | {t.tier} | {t.det_tf}→{t.conf_tf} | "
            f"{t.direction} | {t.trigger or 'n/a'} | {t.tp_source or 'n/a'} | {t.kind} | {t.be_scratch} | "
            f"{t.pnl_raw:.6f} | `{rec['file']}` | {zone} | {t.sweep_ts or 'n/a'} | {t.confirm_at or 'n/a'} |"
        )
    lines.append("")
    lines.append("## 5 non-closed plans (drop reasons, table only)")
    lines.append("")
    lines.append("| # | POI | Tier | Det→Conf | Dir | Stage | Reason | Ticket |")
    lines.append("|---:|---|---|---|---|---|---|---|")
    for d in non_closed:
        lines.append(
            f"| {d.get('winner_index','')} | {d.get('poi_id','')} | {d.get('tier','')} | "
            f"{d.get('detection_tf','')}/{d.get('confirmation_tf','')} | {d.get('direction','')} | "
            f"{d.get('stage','')} | {d.get('reason','')} | {d.get('ticket') or '—'} |"
        )
    lines.append("")
    lines.append("## Read me")
    lines.append("")
    lines.append("- Each chart: detection TF panel (candles, recovered zone band when available, sweep/confirm/entry/exit marks) + confirmation TF panel (candles, entry/SL(original)/TP/exit levels and marks).")
    lines.append("- Human scoring target: **CORRECT / PARTIAL / WRONG** vs flowchart (eyes only). No automated score, no PnL ranking.")
    lines.append("- Limitations: 1m window (2024-04), zero spread/cost, backtest F7 retry not exercised, `LOT_MAX_SAFETY` capped all 9 lots. Zone/sweep/confirm/trigger shown only where recoverable from the deterministic rerun/menu stamp; unavailable fields marked `n/a` (not guessed).")
    lines.append("")
    NOTE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    if not TRADES_CSV.exists() or not DROPS_CSV.exists():
        raise SystemExit("missing funnel artifacts (trades.csv/drops.csv)")
    targets, non_closed = load_targets()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"targets={len(targets)} non_closed={len(non_closed)} out={OUT_DIR}", flush=True)

    captured = capture_context(targets)
    print(f"captured info for {len(captured)}/{len(targets)} pois", flush=True)

    # load M1 for chart windows (reuse funnel window with padding)
    pad_start = funnel.WINDOW_START - timedelta(days=5)
    pad_end = funnel.WINDOW_END + timedelta(days=2)
    m1_all = load_m1(funnel.DATA_PATH, pad_start, pad_end)
    series_cache = {Timeframe.M1: m1_all}

    index = []
    for i, t in enumerate(targets, 1):
        fname = render_trade(t, m1_all, series_cache)
        index.append({"ticket": t.ticket, "poi_id": t.poi_id, "file": fname})
        print(f"  chart {i}/9: {fname}", flush=True)

    (OUT_DIR / "chart_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    write_note(targets, non_closed, index)
    print(f"note: {NOTE_PATH}", flush=True)
    print("CHARTS_N:", len(index), flush=True)


if __name__ == "__main__":
    main()
