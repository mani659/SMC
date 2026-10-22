"""ESSENCE V1 expert-pack chart generator — DIAGNOSTIC / EXPERT REVIEW PACK — NOT PERFORMANCE.

For each of the 7 frozen-window trades (W3 run1 trades.csv) renders an M1
context chart under results/essence_v1_slice/expert_charts/trade_<id>.png:
HTF zone band, sweep marker (M), confirm bar (C), ENTRY/SL_INITIAL/TP lines,
BE note, exit marker. Also, as a read-only audit side-check, verifies per
trade that the initial stop sits 0.20 price units (2 pips at the frozen
assumption) beyond the ending-diagonal terminal candle's extreme at
`terminal_idx`.

Usage: python essence_v1_expert_charts.py
"""

from __future__ import annotations

import csv
import math
import sys
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

from smc.data.parquet_loader import load_ohlcv_parquet  # noqa: E402

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

TRADES_CSV = (REPO_ROOT / "06_RESEARCH/results/essence_v1_slice/W3/run1/trades.csv")
PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
OUT_DIR = REPO_ROOT / "06_RESEARCH/results/essence_v1_slice/expert_charts"

PIP = 0.10  # frozen XAUUSD pip assumption (smc/utils/pips.py)
SL_BUFFER = 0.20  # 2.0 pips minimum band floor used everywhere in the slice


def main() -> None:
    trades = list(csv.DictReader(TRADES_CSV.open(encoding="utf-8")))
    if not trades:
        raise SystemExit("no trades")
    print(f"[charts] {len(trades)} trades", flush=True)

    from datetime import datetime, timezone  # noqa: PLC0415

    rows = list(csv.DictReader(TRADES_CSV.open(encoding="utf-8")))
    # terminal_idx indexes the RUNNER's filtered series (load_from 2025-05-01 —
    # same filter as essence_v1_slice_capture.py), so replicate it exactly.
    load_from = datetime(2025, 5, 1, tzinfo=timezone.utc)
    all_m1 = [c for c in load_ohlcv_parquet(PARQUET) if c.timestamp >= load_from]
    print(f"[charts] {len(all_m1):,} M1 bars (runner-filtered series)", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    audit = []

    for r in rows:
        tid = int(r["ticket"])
        direction = r["direction"]
        short = direction == "SHORT"
        sweep_t = datetime.fromisoformat(r["sweep_ts"])
        confirm_t = datetime.fromisoformat(r["confirm_ts"])
        entry_t = datetime.fromisoformat(r["entry_ts"])
        exit_t = datetime.fromisoformat(r["exit_ts"])

        zone_lo, zone_hi = float(r["zone_low"]), float(r["zone_high"])
        entry = float(r["entry_price"])
        sl_init = entry - float(r["r_stop"]) if not short else entry + float(r["r_stop"])
        tp = float(r["tp_price"])
        exit_price = float(r["exit_price"])
        be_applied = r["be_applied"] == "True"
        term_idx = int(r["terminal_idx"])

        # --- read-only audit side-check: initial SL band floor ---
        # Verified rule (2026-10-22 audit): the stop sits 0.20 price units
        # (2.0 pips) beyond the DEEPER of {sweep extreme, terminal_idx wick}.
        term = all_m1[term_idx]
        wick = term.low if not short else term.high
        sweep = float(r["sweep_extreme"])
        anchor = min(wick, sweep) if not short else max(wick, sweep)
        delta = (sl_init - anchor) if short else (anchor - sl_init)
        ok = math.isclose(delta, SL_BUFFER, abs_tol=1e-9)
        audit.append((tid, direction, anchor, sl_init, round(delta, 10), "OK" if ok else "MISMATCH"))
        if not ok:
            print(f"[charts] WARNING t{tid}: sl_anchor mismatch delta={delta}", flush=True)

        # --- chart window: 90 min before sweep -> 30 min after exit ---
        t0, t1 = sweep_t - timedelta(minutes=90), exit_t + timedelta(minutes=30)
        view = [c for c in all_m1 if t0 <= c.timestamp <= t1]
        if not view:
            raise SystemExit(f"t{tid}: empty view window")
        xs = [c.timestamp for c in view]

        fig, ax = plt.subplots(figsize=(14, 7))
        ax.set_facecolor("#fafafa")
        for i, c in enumerate(view):
            col = "#2e7d32" if c.close >= c.open else "#c62828"
            ax.plot([xs[i], xs[i]], [c.low, c.high], color=col, lw=0.6, zorder=3)
            body_lo, body_hi = min(c.open, c.close), max(c.open, c.close)
            ax.add_patch(
                matplotlib.patches.Rectangle(
                    (mdates.date2num(xs[i]) - 0.00035, body_lo), 0.0007,
                    max(body_hi - body_lo, 0.002), facecolor=col, edgecolor=col,
                    lw=0.4, zorder=3))

        # zone band
        ax.axhspan(zone_lo, zone_hi, color="#1565c0", alpha=0.10, zorder=1)
        ax.axhline(zone_lo, color="#1565c0", lw=0.8, alpha=0.7, ls="--", zorder=1)
        ax.axhline(zone_hi, color="#1565c0", lw=0.8, alpha=0.7, ls="--", zorder=1)

        # markers — level labels placed in the right margin at staggered
        # x positions (axes-fraction coordinates) so near-coincident levels
        # (entry/SL/BE/exit can sit within ~0.1) remain individually readable
        sl_at_exit = float(r["sl_price"])
        p1 = mdates.date2num(exit_t)
        span = p1 - mdates.date2num(t0)
        blended = matplotlib.transforms.blended_transform_factory(
            ax.transAxes, ax.transData)
        levels = (
            (tp, f"TP {tp:.2f} · {float(r['rr_planned']):.1f}R", "#6a1b9a", 1.02),
            (exit_price, f"EXIT {exit_price:.2f}", "#37474f", 1.10),
            (entry, f"ENTRY {entry:.2f}", "#1565c0", 1.18),
            (sl_at_exit, "BE stop" if (
                be_applied and not math.isclose(sl_at_exit, sl_init, abs_tol=1e-9)
            ) else None, "#ef6c00", 1.26),
            (sl_init, f"SL {sl_init:.2f}", "#c62828", 1.34),
        )
        for price, label, color, xfrac in levels:
            if label is None:
                continue
            ax.axhline(price, color=color, lw=1.1, ls="--", alpha=0.85, zorder=2)
            ax.text(xfrac, price, label, transform=blended, fontsize=7,
                    color=color, va="center", ha="left", zorder=6)
        if be_applied and not math.isclose(sl_at_exit, sl_init, abs_tol=1e-9):
            ax.axhline(sl_at_exit, color="#ef6c00", lw=1.0, ls=":", alpha=0.9, zorder=2)
        ax.set_xlim(mdates.date2num(t0) - span * 0.01, p1 + span * 0.03)
        # NOTE: no fig.tight_layout() here — it would override this margin and
        # push the right-margin level labels off the canvas (seen on trade_4).
        fig.subplots_adjust(right=0.72, left=0.09, top=0.93, bottom=0.15)

        def vline(t, price, color, txt, dy, dx=0, ha="center", fs=7.5):
            x = mdates.date2num(t)
            ax.axvline(x, color=color, lw=1.0, ls=":", alpha=0.8, zorder=2)
            ax.scatter([x], [price], color=color, zorder=6, s=26)
            ax.annotate(txt, (x, price), textcoords="offset points",
                        xytext=(dx, dy), ha=ha, fontsize=fs, color=color, zorder=6)

        # sweep label: LONG parks it below-right in clear space under the
        # sweep low; SHORT mirrors it above the sweep high
        vline(sweep_t, float(r["sweep_extreme"]), "#d84315",
              f"M sweep {float(r['sweep_extreme']):.2f}",
              -16 if not short else 16, dx=6, ha="center")
        vline(confirm_t, view[-1].close, "#5d4037", "C confirm", 18)
        vline(entry_t, entry, "#1565c0", "fill", 14, dx=-22, ha="right")

        tf_zone = r["detection_tf"]
        ax.set_title(
            f"DIAGNOSTIC / EXPERT REVIEW PACK — NOT PERFORMANCE\n"
            f"trade {tid} — {direction} • {tf_zone} {r['zone_kind']} zone "
            f"[{zone_lo:.2f}, {zone_hi:.2f}] • confirm {r['confirm_kind']} @ {confirm_t:%H:%M} "
            f"• entry_tf M1 • BE applied: {be_applied}",
            fontsize=10)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d %H:%M", tz=xs[0].tzinfo))
        for lab in ax.get_xticklabels():
            lab.set_rotation(20); lab.set_ha("right"); lab.set_fontsize(8)
        ax.set_ylabel("XAUUSD")
        ax.margins(y=0.18)
        out = OUT_DIR / f"trade_{tid}.png"
        fig.savefig(out, dpi=130)
        plt.close(fig)
        print(f"[charts] wrote {out.name} ({len(view)} bars)", flush=True)

    print("[charts] stop-anchor audit (SL_init vs deeper-of rule ± 0.20):")
    for tid, d, wick, sl, delta, status in audit:
        print(f"  t{tid} {d}: anchor={wick:.3f} sl_init={sl:.3f} delta={delta} [{status}]")


if __name__ == "__main__":
    main()
