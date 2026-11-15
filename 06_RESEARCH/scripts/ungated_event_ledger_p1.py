"""Ungated H1/M5 structure + OB + FVG observation ledger (2026-10-28).

OBSERVATION ONLY: not trade signals, not POLICY_MTF_H4, not performance.
The detector paths are timeframe-local and do not consume a sweep or POI gate.
Run from the repository root or any working directory:
    python -X utf8 06_RESEARCH/scripts/ungated_event_ledger_p1.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

from smc.config.timeframe import Timeframe  # noqa: E402
from smc.core.candle import Candle  # noqa: E402
from smc.core.swing import Swing  # noqa: E402
from smc.data.parquet_loader import load_ohlcv_parquet  # noqa: E402
from smc.data.resample import resample_multi  # noqa: E402
from smc.detection.fvg_detector import detect_fvgs  # noqa: E402
from smc.detection.structural_swing_detector import detect_swings  # noqa: E402

PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
OUT_DIR = REPO_ROOT / "06_RESEARCH/results/ungated_event_ledger_p1"
WINDOW_START = datetime(2025, 9, 1, tzinfo=timezone.utc)
WINDOW_END_EXCLUSIVE = datetime(2025, 12, 1, tzinfo=timezone.utc)
TIMEFRAMES = (Timeframe.H1, Timeframe.M5)
CSV_FIELDS = (
    "event_id", "tf", "event_family", "event_type", "direction",
    "t_start", "t_end", "price_or_low", "price_or_high", "bar_index",
    "pivot_len", "notes", "linked_bos_event_id",
)


def _bar_close_time(candle: Candle, timeframe: Timeframe) -> datetime:
    """Return the nominal close timestamp for a UTC-aligned resampled bar."""
    return candle.timestamp + timedelta(minutes=timeframe.minutes)


def _classify_bias_break(bias: str | None, direction: str) -> tuple[str, str]:
    """Return (BOS/CHOCH, resulting bias) under the approved ledger rule."""
    if direction not in ("LONG", "SHORT"):
        raise ValueError(f"invalid break direction: {direction}")
    if bias not in (None, "LONG", "SHORT"):
        raise ValueError(f"invalid structure bias: {bias}")
    if bias is None or direction == bias:
        return "BOS", direction
    return "CHOCH", direction


def _opposite_color_index(candles: list[Candle], bos_index: int, direction: str) -> int | None:
    """Nearest strictly earlier opposing-body candle; dojis are not opposite."""
    for index in range(bos_index - 1, -1, -1):
        candle = candles[index]
        if direction == "LONG" and candle.close < candle.open:
            return index
        if direction == "SHORT" and candle.close > candle.open:
            return index
    return None


def _swing_pivot_index(swing: Swing, candles: list[Candle]) -> int | None:
    """Recover the §27 extreme index from the §18 base-candle anchor.

    Swing highs always use their extreme candle as base. A §18 swing low may
    anchor one candle before its extreme; permit only that documented offset.
    """
    for index in range(swing.candle_index, min(swing.candle_index + 2, len(candles))):
        value = candles[index].high if swing.is_high else candles[index].low
        if math.isclose(value, swing.level, rel_tol=0.0, abs_tol=1e-10):
            return index
    return None


def _structure_events(candles: list[Candle], timeframe: Timeframe) -> list[dict[str, Any]]:
    """Walk closed bars, exposing valid §18/§19 swings only when knowable."""
    pivot_len = Timeframe.n_bar_confirmation(timeframe)
    swings = detect_swings(candles, timeframe)  # frozen TF-native N (H1=5/M5=3)
    become_known: dict[int, list[Swing]] = defaultdict(list)
    for swing in swings:
        if not swing.is_valid or swing.confirmed_index is None:
            continue
        pivot_index = _swing_pivot_index(swing, candles)
        if pivot_index is None:
            continue
        # Both the right-side N-bar pivot confirmation and §19 close-break
        # must have occurred; the later one is the first causal availability.
        known_at = max(pivot_index + pivot_len, swing.confirmed_index)
        if known_at < len(candles):
            become_known[known_at].append(swing)

    latest: dict[bool, tuple[Swing, int]] = {}
    last_broken: dict[bool, tuple[int, float] | None] = {True: None, False: None}
    bias: str | None = None
    events: list[dict[str, Any]] = []
    for bar_index, candle in enumerate(candles):
        for swing in become_known.get(bar_index, ()):
            current = latest.get(swing.is_high)
            pivot_index = _swing_pivot_index(swing, candles)
            if current is None or (pivot_index is not None and pivot_index >= current[1]):
                latest[swing.is_high] = (swing, pivot_index if pivot_index is not None else swing.candle_index)

        if bar_index == 0:
            continue
        previous_close = candles[bar_index - 1].close
        high_item, low_item = latest.get(True), latest.get(False)
        candidates: list[tuple[str, Swing]] = []
        if high_item is not None:
            level = high_item[0].level
            if previous_close <= level < candle.close:
                candidates.append(("LONG", high_item[0]))
        if low_item is not None:
            level = low_item[0].level
            if previous_close >= level > candle.close:
                candidates.append(("SHORT", low_item[0]))

        # If anomalous overlapping levels make a single close cross both
        # boundaries, retain only the direction of the larger close move.
        if len(candidates) > 1:
            candidates = [max(candidates, key=lambda item: abs(candle.close - previous_close))]
        for direction, swing in candidates:
            polarity = swing.is_high
            pivot_index = _swing_pivot_index(swing, candles)
            identity = (pivot_index if pivot_index is not None else swing.candle_index, swing.level)
            if last_broken[polarity] == identity:
                continue
            last_broken[polarity] = identity
            event_type, bias = _classify_bias_break(bias, direction)
            event_id = f"{timeframe.name}-STRUCTURE-{event_type}-{bar_index:06d}"
            events.append({
                "event_id": event_id, "tf": timeframe.name,
                "event_family": "STRUCTURE", "event_type": event_type,
                "direction": direction, "t_start": _bar_close_time(candle, timeframe).isoformat(),
                "t_end": "", "price_or_low": swing.level,
                "price_or_high": swing.level, "bar_index": bar_index,
                "pivot_len": pivot_len,
                "notes": (f"close crossed latest valid {'swing high' if direction == 'LONG' else 'swing low'}; "
                          f"pivot_index={pivot_index}; available_at={bar_index}; §18/§19 valid"),
                "linked_bos_event_id": "",
            })
    return events


def _event_rows(candles: list[Candle], timeframe: Timeframe) -> list[dict[str, Any]]:
    """Create one timeframe's independent structure, OB-observation, and FVG rows."""
    rows = _structure_events(candles, timeframe)
    structure = list(rows)
    for bos in structure:
        if bos["event_type"] != "BOS":
            continue
        bos_index = int(bos["bar_index"])
        direction = str(bos["direction"])
        origin_index = _opposite_color_index(candles, bos_index, direction)
        if origin_index is None:
            bos["notes"] += "; no earlier opposite-color candle, OB observation omitted"
            continue
        origin = candles[origin_index]
        rows.append({
            "event_id": f"{timeframe.name}-OB-{bos_index:06d}-{origin_index:06d}",
            "tf": timeframe.name, "event_family": "ORDER_BLOCK",
            "event_type": "LAST_OPPOSITE_BEFORE_BOS", "direction": direction,
            "t_start": origin.timestamp.isoformat(),
            "t_end": _bar_close_time(candles[bos_index], timeframe).isoformat(),
            "price_or_low": min(origin.low, origin.high),
            "price_or_high": max(origin.low, origin.high), "bar_index": origin_index,
            "pivot_len": "", "notes": f"full wick of nearest strictly earlier opposite-color candle; origin_index={origin_index}; linked BOS at {_bar_close_time(candles[bos_index], timeframe).isoformat()}",
            "linked_bos_event_id": bos["event_id"],
        })

    for fvg in detect_fvgs(candles, timeframe):
        form_index = fvg.start_index + 2
        third = candles[form_index]
        direction = "LONG" if fvg.zone.direction.name == "LONG" else "SHORT"
        rows.append({
            "event_id": f"{timeframe.name}-FVG-{form_index:06d}",
            "tf": timeframe.name, "event_family": "FVG", "event_type": "FVG",
            "direction": direction, "t_start": _bar_close_time(third, timeframe).isoformat(),
            "t_end": "", "price_or_low": fvg.zone.bottom,
            "price_or_high": fvg.zone.top, "bar_index": form_index,
            "pivot_len": "", "notes": f"existing classic 3-candle detector; first candle index={fvg.start_index}; emitted at third-candle close",
            "linked_bos_event_id": "",
        })
    rows.sort(key=lambda row: (row["t_start"], row["tf"], row["event_family"], row["event_id"]))
    return rows


def _count_summary(
    rows: list[dict[str, Any]],
    bar_counts: dict[str, int],
    timeframes: tuple[Timeframe, ...],
) -> dict[str, Any]:
    counts: dict[str, dict[str, dict[str, dict[str, int]]]] = {
        tf.name: {} for tf in timeframes
    }
    for row in rows:
        tf = row["tf"]
        family = row["event_family"]
        kind = row["event_type"]
        direction = row["direction"]
        leaf = counts[tf].setdefault(family, {}).setdefault(kind, {})
        leaf[direction] = leaf.get(direction, 0) + 1
    return {
        "purpose": "OBSERVATION ONLY — not trade signals, not expectancy, not expert-validated",
        "window": {"start_inclusive": WINDOW_START.isoformat(), "end_exclusive": WINDOW_END_EXCLUSIVE.isoformat()},
        "timeframes": [tf.name for tf in timeframes],
        "bar_counts": bar_counts,
        "event_counts_by_tf_family_type_direction": counts,
        "event_rows": len(rows),
        "method": {
            "structure": "smc.detection.structural_swing_detector.detect_swings; latest valid swing high/low available only after max(pivot_index+N, §19 confirmed_index); strict close crossing emits BOS/CHOCH",
            "pivot_len": {tf.name: Timeframe.n_bar_confirmation(tf) for tf in timeframes},
            "order_block_observation": "nearest strictly earlier opposite-body-color candle before each BOS; full wick range; ledger-only LAST_OPPOSITE_BEFORE_BOS",
            "fvg": "smc.detection.fvg_detector.detect_fvgs; classic 3-candle gap, emitted on third candle close",
            "gates": "none; no POI, sweep, policy engine, trading, or risk path",
        },
    }


def _draw_chart(candles: list[Candle], row: dict[str, Any], out_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    bar_index = int(row["bar_index"])
    half = {"H1": 28, "M5": 48, "H4": 20}.get(row["tf"], 48)
    left, right = max(0, bar_index - half), min(len(candles), bar_index + half + 1)
    segment = candles[left:right]
    fig, ax = plt.subplots(figsize=(11, 5.8))
    dates = [c.timestamp for c in segment]
    xs = mdates.date2num(dates)
    if len(xs) > 1:
        spacing = min((xs[i + 1] - xs[i] for i in range(len(xs) - 1) if xs[i + 1] > xs[i]), default=1 / 24)
    else:
        spacing = 1 / 24
    width = spacing * 0.66
    for x, candle in zip(xs, segment):
        color = "#2c8c70" if candle.close >= candle.open else "#c25752"
        ax.vlines(x, candle.low, candle.high, color=color, linewidth=0.75, zorder=2)
        body_bottom = min(candle.open, candle.close)
        body_height = max(abs(candle.close - candle.open), (candle.high-candle.low) * 0.004, 1e-8)
        ax.add_patch(Rectangle((x - width/2, body_bottom), width, body_height,
                               facecolor=color, edgecolor=color, linewidth=0.5, zorder=3))

    low, high = row.get("price_or_low"), row.get("price_or_high")
    label = f"{row['event_type']} ({row['tf']})"
    if low not in (None, "") and high not in (None, ""):
        low, high = float(low), float(high)
        if row["event_family"] == "STRUCTURE" and math.isclose(low, high):
            ax.axhline(low, color="#5c4db1", linewidth=1.2, linestyle="--", label=label)
        else:
            ax.axhspan(low, high, color="#e6a943", alpha=0.28, label=label)
    event_time = row["t_end"] if row["event_family"] == "ORDER_BLOCK" else row["t_start"]
    event_x = mdates.date2num(datetime.fromisoformat(event_time))
    ax.axvline(event_x, color="#333333", linestyle=":", linewidth=1.0, alpha=0.8)
    ax.set_title(label, fontsize=13, weight="bold")
    ax.set_ylabel("Price")
    ax.grid(alpha=0.2)
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M", tz=timezone.utc))
    ax.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tfs", default=",".join(tf.name for tf in TIMEFRAMES),
        help="comma-separated timeframe names (default: H1,M5)",
    )
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--events-name", default="events.csv")
    args = parser.parse_args(argv)
    try:
        timeframes = tuple(Timeframe[name.strip().upper()] for name in args.tfs.split(",") if name.strip())
    except KeyError as exc:
        parser.error(f"unsupported timeframe {exc.args[0]!r}")
    if not timeframes or len(set(timeframes)) != len(timeframes):
        parser.error("--tfs must contain one or more unique timeframe names")

    if not PARQUET.is_file():
        raise FileNotFoundError(f"canonical M1 parquet missing: {PARQUET}")
    loaded = load_ohlcv_parquet(PARQUET, timeframe=Timeframe.M1)
    m1 = [c for c in loaded if WINDOW_START <= c.timestamp < WINDOW_END_EXCLUSIVE]
    if not m1:
        raise RuntimeError(f"no M1 data in frozen window {WINDOW_START}..{WINDOW_END_EXCLUSIVE}")
    series = resample_multi(m1, timeframes)
    closed: dict[Timeframe, list[Candle]] = {}
    for tf in timeframes:
        # Do not include a bar whose nominal close lies beyond the frozen window.
        closed[tf] = [c for c in series[tf] if c.timestamp + timedelta(minutes=tf.minutes) <= WINDOW_END_EXCLUSIVE]
        if len(closed[tf]) < 2 * Timeframe.n_bar_confirmation(tf) + 2:
            raise RuntimeError(f"insufficient closed {tf.name} bars in frozen window: {len(closed[tf])}")

    rows: list[dict[str, Any]] = []
    for tf in timeframes:
        rows.extend(_event_rows(closed[tf], tf))
    rows.sort(key=lambda row: (row["t_start"], row["tf"], row["event_family"], row["event_id"]))

    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    charts_dir = out_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    events_path = out_dir / args.events_name
    with events_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    bar_counts = {tf.name: len(closed[tf]) for tf in timeframes}
    summary = _count_summary(rows, bar_counts, timeframes)

    # Keep up to three real examples per timeframe × event type/category;
    # this retains separate BOS and CHOCH exemplars where both exist.
    by_tf = {tf.name: closed[tf] for tf in timeframes}
    chart_index = []
    selected: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        chart_category = (
            row["event_type"] if row["event_family"] == "STRUCTURE"
            else row["event_type"]
        )
        key = (row["tf"], chart_category)
        if selected[key] >= 3:
            continue
        chart_name = f"{row['tf'].lower()}_{chart_category.lower()}_{selected[key] + 1:02d}_{row['event_id'].lower()}.png"
        path = charts_dir / chart_name
        _draw_chart(by_tf[row["tf"]], row, path)
        selected[key] += 1
        chart_index.append({"file": f"charts/{chart_name}", "tf": row["tf"], "family": row["event_family"],
                            "chart_category": chart_category, "type": row["event_type"], "direction": row["direction"],
                            "event_id": row["event_id"], "t_start": row["t_start"]})
    summary["chart_count"] = len(chart_index)
    summary["chart_index"] = chart_index
    summary["chart_sparsity"] = {
        f"{tf.name}:{category}": ("ZERO EVENTS — no chart invented" if selected[(tf.name, category)] == 0
                                   else f"{selected[(tf.name, category)]} sample chart(s)")
        for tf in timeframes for category in ("BOS", "CHOCH", "LAST_OPPOSITE_BEFORE_BOS", "FVG")
    }
    summary["events_csv_sha256"] = hashlib.sha256(events_path.read_bytes()).hexdigest()
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"window": summary["window"], "bar_counts": bar_counts,
                      "event_counts_by_tf_family_type_direction": summary["event_counts_by_tf_family_type_direction"],
                      "chart_count": len(chart_index), "events_csv_sha256": summary["events_csv_sha256"],
                      "artifacts": str(out_dir)}, indent=2))


if __name__ == "__main__":
    main()

