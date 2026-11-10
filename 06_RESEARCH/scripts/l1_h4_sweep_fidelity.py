#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""L1 — H4 sweep-only fidelity pack (independent, observation only).

Authority: 06_RESEARCH/LAYERED_FIDELITY_PLAN.md (ACTIVE, L1).
LOGIC_CHANGED: NO. No 04_SRC edits, no LTF, no orders, no PnL.

Uses existing detection APIs as-is (evaluation mode):
- smc.data.resample.resample_ohlcv  (M1 -> H4, deterministic)
- smc.detection.liquidity_scanner.scan  (Phase 1 liquidity levels on H4)
- smc.detection.sweep_detector.detect_sweeps (wick-pierce + body-close-back,
  first sweep per level, formed_at respected) — no new sweep rule invented.

Outputs (gitignored under results/):
  06_RESEARCH/results/l1_h4_sweep_fidelity/{events_h4_sweep.csv,summary.json,charts/,run.log}
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
SCRIPTS_DIR = REPO_ROOT / "06_RESEARCH" / "scripts"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from plan_complement_ledger import load_m1  # existing loader (parquet, UTC)
from smc.config.timeframe import Timeframe
from smc.data.resample import resample_ohlcv
from smc.detection.liquidity_scanner import scan as scan_liquidity, ALL_FAMILIES
from smc.detection.sweep_detector import detect_sweeps

DATA_PATH = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "l1_h4_sweep_fidelity"
CHARTS_DIR = OUT_DIR / "charts"

# Preferred exec window (aligned with expert/structure packs); documented warm-up.
WARMUP_START = datetime(2025, 3, 1, tzinfo=timezone.utc)
EXEC_START = datetime(2025, 6, 1, tzinfo=timezone.utc)
EXEC_END = datetime(2025, 11, 30, 23, 59, 59, tzinfo=timezone.utc)

SEED = 20260601
SAMPLE_N = 40


def _iso(dt):
    if dt is None:
        return ""
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _h4_close_ts(bar):
    return bar.timestamp + timedelta(minutes=Timeframe.H4.minutes)


def event_key(ev: dict) -> tuple:
    """Stable identity for determinism check."""
    return (
        ev["sweep_ts"],
        ev["pool"],
        ev["level_type"],
        f"{ev['level']:.6f}",
        ev["candle_index_h4"],
    )


def events_hash(rows: list[dict]) -> str:
    blob = json.dumps([event_key(r) for r in rows], sort_keys=False).encode()
    return hashlib.sha256(blob).hexdigest()


def collect_events(h4, exec_start, exec_end):
    """Run scanner + sweep detector on full H4 series; return exec-window events."""
    # Level formation may use history before exec_start; scan full series.
    levels = scan_liquidity(h4, Timeframe.H4, include=ALL_FAMILIES)
    sweeps = detect_sweeps(h4, levels)

    rows = []
    for i, sw in enumerate(sweeps):
        c = sw.candle
        ts = c.timestamp
        if not (exec_start <= ts <= exec_end):
            continue
        pool = getattr(sw.pool, "name", str(sw.pool))
        lvl = sw.level
        # Directional label derived only from pool/confirmation semantics:
        # BSL pool (buy stops above) swept = wick above level, close below -> downside rejection.
        # SSL pool (sell stops below) swept = wick below level, close above -> upside rejection.
        direction = "BEARISH_SWEEP_BSL" if pool == "BSL" else "BULLISH_SWEEP_SSL"
        rows.append({
            "event_id": f"h4sweep-{i:06d}",
            "sweep_ts": _iso(ts),
            "sweep_close_ts": _iso(_h4_close_ts(c)),
            "candle_index_h4": sw.candle_index,
            "direction": direction,
            "pool": pool,
            "level_type": getattr(lvl.type, "name", str(lvl.type)),
            "level": round(float(lvl.level), 6),
            "formed_at": _iso(getattr(lvl, "formed_at", None)),
            "open": round(float(c.open), 6),
            "high": round(float(c.high), 6),
            "low": round(float(c.low), 6),
            "close": round(float(c.close), 6),
            "timeframe": "H4",
        })
    # stable order
    rows.sort(key=lambda r: (r["sweep_ts"], r["pool"], r["level_type"], r["level"]))
    # reassign deterministic ids after sort
    for idx, r in enumerate(rows, start=1):
        r["event_id"] = f"h4sweep-{idx:05d}"
    return rows, len(levels), len(sweeps)


def stratified_sample(rows, n, seed=SEED):
    if len(rows) <= n:
        return list(rows), "all (total <= n)"
    rng = random.Random(seed)
    bulls = [r for r in rows if r["pool"] == "SSL"]
    bears = [r for r in rows if r["pool"] == "BSL"]
    # proportional by direction, at least spread across time within each
    n_bull = max(1, round(n * len(bulls) / len(rows))) if bulls else 0
    n_bear = n - n_bull
    # adjust if one side too small
    if n_bull > len(bulls):
        n_bear += n_bull - len(bulls); n_bull = len(bulls)
    if n_bear > len(bears):
        n_bull += n_bear - len(bears); n_bear = len(bears)
    def pick_time_spread(pool_rows, k):
        if k <= 0 or not pool_rows:
            return []
        pool_rows = sorted(pool_rows, key=lambda r: r["sweep_ts"])
        if k >= len(pool_rows):
            return list(pool_rows)
        # bucket by time quantiles then pick one per bucket (deterministic)
        buckets = [[] for _ in range(k)]
        for i, r in enumerate(pool_rows):
            b = min(k - 1, int(i * k / len(pool_rows)))
            buckets[b].append(r)
        chosen = []
        for b in buckets:
            if b:
                chosen.append(rng.choice(b))
        # fill if any empty bucket collision
        remaining = [r for r in pool_rows if r not in chosen]
        rng.shuffle(remaining)
        for r in remaining:
            if len(chosen) >= k:
                break
            chosen.append(r)
        return chosen[:k]
    sample = pick_time_spread(bulls, n_bull) + pick_time_spread(bears, n_bear)
    # de-dup preserving
    seen=set(); out=[]
    for r in sorted(sample, key=lambda x: x["sweep_ts"]):
        k=event_key(r)
        if k in seen: continue
        seen.add(k); out.append(r)
    # top-up if rounding short
    if len(out) < n:
        rest=[r for r in rows if event_key(r) not in seen]
        rng.shuffle(rest)
        out += rest[: n-len(out)]
        out.sort(key=lambda x: x["sweep_ts"])
    return out[:n], f"stratified bull/bear + time-spread (seed={seed}, bull={len([r for r in out if r['pool']=='SSL'])}, bear={len([r for r in out if r['pool']=='BSL'])})"


def render_chart(event, h4, out_path: Path, bars_each_side=40):
    idx = event["candle_index_h4"]
    lo = max(0, idx - bars_each_side)
    hi = min(len(h4), idx + bars_each_side + 1)
    window = h4[lo:hi]
    if not window:
        return False
    times = [mdates.date2num(c.timestamp) for c in window]
    fig, ax = plt.subplots(figsize=(14, 5))
    width = 0.12  # days, H4 bar
    for t, c in zip(times, window):
        color = "#2ca02c" if c.close >= c.open else "#d62728"
        ax.vlines(t, c.low, c.high, color=color, linewidth=1)
        bottom = min(c.open, c.close)
        height = max(abs(c.close - c.open), 1e-6)
        ax.add_patch(Rectangle((t - width/2, bottom), width, height,
                               facecolor=color, edgecolor=color, alpha=0.8))
    # sweep candle highlight
    st = mdates.date2num(h4[idx].timestamp)
    ax.axvline(st, color="#9467bd", linestyle="--", linewidth=1.2, alpha=0.8, label="sweep bar")
    ax.axhline(event["level"], color="#1f77b4", linestyle="-", linewidth=1.2, alpha=0.9, label=f"level {event['level']}")
    ax.scatter([st], [h4[idx].high if event["pool"]=="BSL" else h4[idx].low],
               marker="v" if event["pool"]=="BSL" else "^", s=80, color="#9467bd", zorder=5,
               label="sweep wick")
    title = (f"SWEEP (H4) | {event['sweep_ts']} | {event['direction']} | pool={event['pool']} "
             f"| level_type={event['level_type']} | level={event['level']}")
    ax.set_title(title, fontsize=9)
    ax.set_ylabel("Price")
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d\n%H:%M', tz=timezone.utc))
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return True


def write_csv(rows, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    cols = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    log_lines = []

    def log(msg):
        print(msg, flush=True)
        log_lines.append(msg)

    # --- window/data availability (fail-loud) ---
    log(f"[l1-h4] DATA={DATA_PATH}")
    if not DATA_PATH.exists():
        log(f"[l1-h4] FAIL: data parquet missing: {DATA_PATH}")
        (OUT_DIR / "run.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        return 2

    warm_start = WARMUP_START
    exec_start = EXEC_START
    exec_end = EXEC_END
    log(f"[l1-h4] requested exec={exec_start.isoformat()}..{exec_end.isoformat()} warmup_from={warm_start.isoformat()}")

    # load M1 covering warmup..exec_end (end exclusive in loader semantics; pad 1 day)
    m1 = load_m1(DATA_PATH, warm_start, exec_end + timedelta(days=1))
    if not m1:
        log("[l1-h4] FAIL: no M1 bars loaded for requested window")
        (OUT_DIR / "run.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        return 2
    m1_min = m1[0].timestamp
    m1_max = m1[-1].timestamp
    log(f"[l1-h4] m1 bars={len(m1)} range={m1_min.isoformat()}..{m1_max.isoformat()}")

    # window availability checks
    if m1_min > exec_start:
        log(f"[l1-h4] FAIL: M1 starts after exec_start ({m1_min} > {exec_start})")
        (OUT_DIR / "run.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        return 2
    if m1_max < exec_start:
        log(f"[l1-h4] FAIL: M1 ends before exec_start ({m1_max} < {exec_start})")
        (OUT_DIR / "run.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        return 2
    if m1_max < exec_end.replace(hour=0, minute=0, second=0, microsecond=0):
        log(f"[l1-h4] NOTE: M1 ends before requested exec_end ({m1_max} < {exec_end}); window documented as available coverage")

    # resample H4 (existing deterministic resampler)
    h4 = resample_ohlcv(m1, Timeframe.H4)
    log(f"[l1-h4] h4 bars={len(h4)} range={h4[0].timestamp.isoformat()}..{h4[-1].timestamp.isoformat() if h4 else 'n/a'}")

    # --- pass 1 ---
    rows1, n_levels1, n_sweeps_all1 = collect_events(h4, exec_start, exec_end)
    hash1 = events_hash(rows1)
    log(f"[l1-h4] pass1: levels={n_levels1} sweeps_all={n_sweeps_all1} exec_events={len(rows1)} hash={hash1}")

    # --- pass 2 determinism ---
    rows2, n_levels2, n_sweeps_all2 = collect_events(h4, exec_start, exec_end)
    hash2 = events_hash(rows2)
    deterministic = (hash1 == hash2 and len(rows1) == len(rows2) and n_levels1 == n_levels2 and n_sweeps_all1 == n_sweeps_all2)
    log(f"[l1-h4] pass2: levels={n_levels2} sweeps_all={n_sweeps_all2} exec_events={len(rows2)} hash={hash2} deterministic={deterministic}")
    if not deterministic:
        log("[l1-h4] FAIL: non-deterministic event emission across dual runs")
        summary = {
            "status": "FAIL", "reason": "non_deterministic",
            "hash1": hash1, "hash2": hash2,
        }
        (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (OUT_DIR / "run.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        return 3

    rows = rows1
    bull = sum(1 for r in rows if r["pool"] == "SSL")  # bullish sweep of SSL
    bear = sum(1 for r in rows if r["pool"] == "BSL")  # bearish sweep of BSL
    log(f"[l1-h4] exec window events: n={len(rows)} bull_ssl={bull} bear_bsl={bear}")

    # --- sample + charts ---
    sample, sample_method = stratified_sample(rows, SAMPLE_N, seed=SEED)
    log(f"[l1-h4] sample_n={len(sample)} method={sample_method}")
    charts_written = 0
    for ev in sample:
        ts_clean = ev["sweep_ts"].replace(":", "").replace("-", "")
        fname = f"h4_sweep_{ev['event_id']}_{ev['pool']}_{ts_clean}.png"
        try:
            ok = render_chart(ev, h4, CHARTS_DIR / fname)
            if ok:
                charts_written += 1
        except Exception as e:  # noqa: BLE001
            log(f"[l1-h4] chart error {ev['event_id']}: {e!r}")

    # --- write artifacts ---
    write_csv(rows, OUT_DIR / "events_h4_sweep.csv")
    summary = {
        "status": "PASS",
        "layer": "L1",
        "tf": "H4",
        "window_exec_start": exec_start.isoformat(),
        "window_exec_end_requested": EXEC_END.isoformat(),
        "window_exec_end_data": m1_max.isoformat(),
        "warmup_start": warm_start.isoformat(),
        "m1_bars": len(m1),
        "h4_bars": len(h4),
        "h4_range_start": h4[0].timestamp.isoformat() if h4 else None,
        "h4_range_end": h4[-1].timestamp.isoformat() if h4 else None,
        "levels_scanned_total": n_levels1,
        "sweeps_detected_all_series": n_sweeps_all1,
        "n_sweeps_exec_window": len(rows),
        "n_bull_ssl": bull,
        "n_bear_bsl": bear,
        "sample_n": len(sample),
        "sample_method": sample_method,
        "charts_n": charts_written,
        "determinism": {
            "dual_run_equal": deterministic,
            "hash1": hash1,
            "hash2": hash2,
        },
        "detector_apis": {
            "levels": "smc.detection.liquidity_scanner.scan(h4, Timeframe.H4, include=ALL_FAMILIES)",
            "sweeps": "smc.detection.sweep_detector.detect_sweeps(h4, levels)",
            "resample": "smc.data.resample.resample_ohlcv(m1, Timeframe.H4)",
            "loader": "06_RESEARCH.scripts.plan_complement_ledger.load_m1 (parquet)",
        },
        "families_included": list(ALL_FAMILIES),
        "logic_changed": "NO",
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT_DIR / "run.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    log(f"[l1-h4] DONE status=PASS events={len(rows)} charts={charts_written}")
    log(f"[l1-h4] artifacts: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
