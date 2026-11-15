"""Track A — ungated multi-TF liquidity SWEEP observation ledger (2026-10-28).

OBSERVATION ONLY: not trade signals, not POLICY_MTF_H4, not performance,
not a quality or edge claim. Emits SWEEP as a first-class observation
stream on H4 + H1 (M5 optional), independent of POI gates and LTF confirms.

Authority: Lead Architect "TRACK A — UNGATED MULTI-TF SWEEP LEDGER"
(prerequisite PHASE0_STATUS PASS, recorded 2026-10-28).
Run from the repository root or any working directory:
    python -X utf8 06_RESEARCH/scripts/track_a_sweep_ledger.py

Definitions (both reuse ONLY locked machinery; no new geometry):
  A — sweep of structural swing high/low: every valid §18/§19 swing from
      smc.detection.structural_swing_detector.detect_swings (same TF-native
      N and causal known_at = max(pivot+N, §19 confirmed_index) as
      ungated_event_ledger_p1) becomes a LiquidityLevel the moment it is
      knowable; pool BSL for swing highs, SSL for swing lows.
  B — sweep of explicit zone bounds from prior event rows of the SAME
      ungated_event_ledger_p1 machinery (FVG zone top/bottom and
      LAST_OPPOSITE_BEFORE_BOS full-wick bounds). Levels only; the zone
      row machinery is imported, not forked, so no geometry is re-derived.

Sweep semantics are the locked detector smc.detection.sweep_detector
(LOCKED_DECISIONS §2): wick pierces the level, body closes back; a close
beyond is a breakout, not a sweep; a level cannot sweep itself at the bar
that created it (formed_at bound). detect_sweeps returns at most ONE sweep
per level — re-arms/repeats are not invented here.

Direction is a pool-side LABEL only: BSL (stops above highs) -> "SHORT",
SSL (stops below lows) -> "LONG". It carries no edge or expectancy claim.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

from smc.config.timeframe import Timeframe  # noqa: E402
from smc.core.candle import Candle  # noqa: E402
from smc.core.enums import LiquidityType, PoolType  # noqa: E402
from smc.core.liquidity_level import LiquidityLevel  # noqa: E402
from smc.data.parquet_loader import load_ohlcv_parquet  # noqa: E402
from smc.data.resample import resample_multi  # noqa: E402
from smc.detection.sweep_detector import detect_sweeps  # noqa: E402

import ungated_event_ledger_p1 as base_ledger  # noqa: E402

PARQUET = base_ledger.PARQUET
WINDOW_START = base_ledger.WINDOW_START
WINDOW_END_EXCLUSIVE = base_ledger.WINDOW_END_EXCLUSIVE
OUT_DIR = REPO_ROOT / "06_RESEARCH/results/track_a_sweep_ledger"
TIMEFRAMES = (Timeframe.H4, Timeframe.H1, Timeframe.M5)
CHART_TFS = (Timeframe.H4, Timeframe.H1)  # spec: charts up to 3 per H4/H1
POOL_DIRECTION = {PoolType.BSL: "SHORT", PoolType.SSL: "LONG"}
CSV_FIELDS = (
    "event_id", "tf", "definition", "level_type", "pool", "direction",
    "level_price", "t_sweep_close", "swept_bar_index", "level_formed_index",
    "source_event_id", "notes",
)


def _pool_direction(pool: PoolType) -> str:
    """Pool-side direction label of a sweep (BSL->SHORT, SSL->LONG)."""
    if pool not in POOL_DIRECTION:
        raise ValueError(f"unsweepable pool for this ledger: {pool!r}")
    return POOL_DIRECTION[pool]


def _structural_levels(
    candles: list[Candle], timeframe: Timeframe
) -> list[tuple[str, LiquidityLevel, dict[str, Any]]]:
    """Definition A: every valid §18/§19 swing becomes a level when knowable.

    Same swing machinery as the ungated structure ledger (imported helpers):
    TF-native N confirmation plus §19 validity; the level is knowable at
    ``known_at = max(pivot_index + N, confirmed_index)`` and the formed_at
    bound makes the locked detector scan strictly AFTER that bar, so the
    pivot-window bars (including the extreme candle) can never sweep it.
    """
    pivot_len = Timeframe.n_bar_confirmation(timeframe)
    from smc.detection.structural_swing_detector import detect_swings

    swings = detect_swings(candles, timeframe)
    specs: list[tuple[str, LiquidityLevel, dict[str, Any]]] = []
    for swing in swings:
        if not swing.is_valid or swing.confirmed_index is None:
            continue
        pivot_index = base_ledger._swing_pivot_index(swing, candles)
        if pivot_index is None:
            continue
        known_at = max(pivot_index + pivot_len, swing.confirmed_index)
        if known_at >= len(candles):
            continue
        pool = PoolType.BSL if swing.is_high else PoolType.SSL
        level_id = f"{timeframe.name}-A-{pivot_index:06d}-{'H' if swing.is_high else 'L'}"
        level = LiquidityLevel(
            type=LiquidityType.STRUCTURAL_SWING,
            level=swing.level,
            pool=pool,
            timeframe=timeframe,
            formed_at=candles[known_at].timestamp,
        )
        meta = {
            "definition": "A",
            "source_event_id": "",
            "level_formed_index": known_at,
            "notes": (
                f"locked sweep_detector semantics on valid §18/§19 swing; "
                f"pivot_index={pivot_index}; known_at={known_at}; "
                f"pivot_len={pivot_len}; one sweep per level"
            ),
        }
        specs.append((level_id, level, meta))
    return specs


def _zone_bound_levels(
    candles: list[Candle], timeframe: Timeframe
) -> list[tuple[str, LiquidityLevel, dict[str, Any]]]:
    """Definition B: explicit zone bounds of prior FVG / LAST_OPPOSITE rows.

    Rows come from the SAME ungated_event_ledger_p1 machinery (imported,
    not forked): FVG zone top/bottom as POI_LEVEL and
    LAST_OPPOSITE_BEFORE_BOS full-wick bounds as ORDER_BLOCK_BOUNDARY.
    A zone row becomes knowable at the close of its own bar, so formed_at
    is that bar's open timestamp and the locked detector's strict
    after-bound excludes the forming bar itself.
    """
    specs: list[tuple[str, LiquidityLevel, dict[str, Any]]] = []
    for row in base_ledger._event_rows(candles, timeframe):
        family = row["event_family"]
        if family == "FVG":
            level_type = LiquidityType.POI_LEVEL
        elif family == "ORDER_BLOCK":
            level_type = LiquidityType.ORDER_BLOCK_BOUNDARY
        else:
            continue
        top, bottom = float(row["price_or_high"]), float(row["price_or_low"])
        for bound in (top, bottom):
            if not math.isfinite(bound):
                raise RuntimeError(f"non-finite zone bound in {row['event_id']}")
        bar_index = int(row["bar_index"])
        formed_at = candles[bar_index].timestamp
        formed_close = base_ledger._bar_close_time(candles[bar_index], timeframe)
        for pool, bound in ((PoolType.BSL, top), (PoolType.SSL, bottom)):
            level_id = f"{row['event_id']}-{'TOP' if pool is PoolType.BSL else 'BOT'}"
            level = LiquidityLevel(
                type=level_type, level=bound, pool=pool,
                timeframe=timeframe, formed_at=formed_at,
            )
            meta = {
                "definition": "B",
                "source_event_id": row["event_id"],
                "level_formed_index": bar_index,
                "notes": (
                    f"locked sweep_detector semantics on {family} row zone bound; "
                    f"source_event={row['event_id']}; knowable at bar close "
                    f"{formed_close.isoformat()}; one sweep per level"
                ),
            }
            specs.append((level_id, level, meta))
    return specs


def _sweep_rows(candles: list[Candle], timeframe: Timeframe) -> tuple[list[dict[str, Any]], set[str]]:
    """Run the locked detector over this timeframe's Definition A+B levels.

    Returns (rows, definitions_that_ran). A definition that produced levels
    but zero sweeps still counts as ran — reported honestly.
    """
    specs = _structural_levels(candles, timeframe) + _zone_bound_levels(candles, timeframe)
    definitions_that_ran = {meta["definition"] for _, _, meta in specs}
    by_level = {id(lv): (lid, meta) for lid, lv, meta in specs}
    rows: list[dict[str, Any]] = []
    for result in detect_sweeps(candles, [lv for _, lv, _ in specs]):
        level_id, meta = by_level[id(result.level)]
        definition = meta["definition"]
        swept_index = result.candle_index
        swept_close = base_ledger._bar_close_time(result.candle, timeframe)
        rows.append({
            "event_id": f"{timeframe.name}-SWEEP-{level_id}-{swept_index:06d}",
            "tf": timeframe.name,
            "definition": definition,
            "level_type": result.level.type.value,
            "pool": result.pool.value,
            "direction": _pool_direction(result.pool),
            "level_price": result.level.level,
            "t_sweep_close": swept_close.isoformat(),
            "swept_bar_index": swept_index,
            "level_formed_index": meta["level_formed_index"],
            "source_event_id": meta["source_event_id"],
            "notes": meta["notes"] + f"; swept at close {swept_close.isoformat()}",
        })
    rows.sort(key=lambda row: (row["t_sweep_close"], row["event_id"]))
    return rows, definitions_that_ran


def _count_summary(
    rows: list[dict[str, Any]],
    bar_counts: dict[str, int],
    timeframes: tuple[Timeframe, ...],
    defs_used: str,
) -> dict[str, Any]:
    counts: dict[str, dict[str, dict[str, dict[str, int]]]] = {tf.name: {} for tf in timeframes}
    for row in rows:
        leaf = counts[row["tf"]].setdefault(row["definition"], {}).setdefault(row["direction"], {})
        leaf[row["pool"]] = leaf.get(row["pool"], 0) + 1
    return {
        "purpose": "OBSERVATION ONLY — not trade signals, not expectancy, not expert-validated",
        "window": {
            "start_inclusive": WINDOW_START.isoformat(),
            "end_exclusive": WINDOW_END_EXCLUSIVE.isoformat(),
        },
        "timeframes": [tf.name for tf in timeframes],
        "defs_used": defs_used,
        "bar_counts": bar_counts,
        "sweep_counts_by_tf_definition_direction": counts,
        "event_rows": len(rows),
        "method": {
            "sweep_semantics": (
                "smc.detection.sweep_detector.detect_sweeps (LOCKED_DECISIONS §2): "
                "wick pierce + body close back; close beyond = breakout, not a sweep; "
                "formed_at bound prevents a level sweeping at its forming bar; "
                "at most ONE sweep per level, no re-arm, no subtype invention"
            ),
            "definition_a": (
                "ungated_event_ledger_p1 swing machinery (detect_swings, §18 pivot "
                "recovery, §19 validity); every valid swing becomes a LiquidityLevel "
                "(STRUCTURAL_SWING; BSL for highs, SSL for lows) at "
                "known_at=max(pivot+N, confirmed_index); level-set choice is "
                "all-valid-swings (documented, not latest-only)"
            ),
            "definition_b": (
                "ungated_event_ledger_p1 event rows (FVG zone top/bottom as "
                "POI_LEVEL, LAST_OPPOSITE_BEFORE_BOS wick bounds as "
                "ORDER_BLOCK_BOUNDARY); rows imported, not forked; formed_at = the "
                "row's forming bar timestamp, so the zone cannot sweep at its own bar"
            ),
            "direction_mapping": (
                "pool-side label only: BSL->SHORT, SSL->LONG; not an edge or "
                "expectancy claim"
            ),
            "gates": "none; no POI, policy, confirm, trading, or risk path",
        },
    }


def _draw_sweep_chart(
    candles: list[Candle], row: dict[str, Any], out_path: Path
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    swept_index = int(row["swept_bar_index"])
    tf = row["tf"]
    minutes = Timeframe[tf].minutes
    half = {"H1": 28, "M5": 48, "H4": 20}.get(tf, 48)
    left, right = max(0, swept_index - half), min(len(candles), swept_index + half + 1)
    segment = candles[left:right]
    label = (
        f"SWEEP ({tf}) — {row['direction']} @ {float(row['level_price']):.2f} "
        f"(definition {row['definition']})"
    )
    fig, ax = plt.subplots(figsize=(11, 5.8))
    dates = [c.timestamp for c in segment]
    xs = mdates.date2num(dates)
    if len(xs) > 1:
        spacing = min(
            (xs[i + 1] - xs[i] for i in range(len(xs) - 1) if xs[i + 1] > xs[i]),
            default=1 / 24,
        )
    else:
        spacing = 1 / 24
    width = spacing * 0.66
    for x, candle in zip(xs, segment):
        color = "#2c8c70" if candle.close >= candle.open else "#c25752"
        ax.vlines(x, candle.low, candle.high, color=color, linewidth=0.75, zorder=2)
        body_bottom = min(candle.open, candle.close)
        body_height = max(abs(candle.close - candle.open), (candle.high - candle.low) * 0.004, 1e-8)
        ax.add_patch(Rectangle((x - width / 2, body_bottom), width, body_height,
                               facecolor=color, edgecolor=color, linewidth=0.5, zorder=3))
    level_price = float(row["level_price"])
    ax.axhline(level_price, color="#5c4db1", linewidth=1.2, linestyle="--", label=label)
    # The sweep candle itself is highlighted at its open time; the level's
    # knowable time (close of the level_formed_index bar) is the second marker.
    ax.axvline(mdates.date2num(datetime.fromisoformat(row["t_sweep_close"]) - timedelta(minutes=minutes)),
               color="#333333", linestyle=":", linewidth=1.0, alpha=0.8,
               label=f"sweep bar (index {swept_index})")
    formed_index = int(row["level_formed_index"])
    if 0 <= formed_index < len(candles):
        knowable_at = candles[formed_index].timestamp + timedelta(minutes=minutes)
        ax.axvline(mdates.date2num(knowable_at), color="#e6a943", linestyle="-.",
                   linewidth=1.0, alpha=0.9,
                   label=f"level knowable (index {formed_index})")
    ax.set_title(f"SWEEP ({tf}) — {row['direction']}", fontsize=13, weight="bold")
    ax.set_ylabel("Price")
    ax.grid(alpha=0.2)
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M", tz=timezone.utc))
    ax.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def _select_charts(
    rows: list[dict[str, Any]], timeframes: tuple[Timeframe, ...]
) -> list[dict[str, Any]]:
    """Deterministic per-TF sample: earliest A, earliest B, then earliest other.

    Charts are a scoring SAMPLE, not a completeness claim; the CSV stays the
    full ledger. Chart TFs are H4/H1 per the Track A spec.
    """
    chosen: list[dict[str, Any]] = []
    for tf in timeframes:
        if tf not in CHART_TFS:
            continue
        tf_rows = sorted(
            (row for row in rows if row["tf"] == tf.name),
            key=lambda row: row["t_sweep_close"],
        )
        first_a = next((row for row in tf_rows if row["definition"] == "A"), None)
        first_b = next((row for row in tf_rows if row["definition"] == "B"), None)
        picked: dict[str, dict[str, Any]] = {
            row["event_id"]: row for row in (first_a, first_b) if row is not None
        }
        for row in tf_rows:
            if len(picked) >= 3:
                break
            picked.setdefault(row["event_id"], row)
        chosen.extend(list(picked.values())[:3])
    return chosen


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tfs", default=",".join(tf.name for tf in TIMEFRAMES),
        help="comma-separated timeframe names (default: H4,H1,M5)",
    )
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
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
    defs_ran: set[str] = set()
    for tf in timeframes:
        tf_rows, tf_defs = _sweep_rows(closed[tf], tf)
        rows.extend(tf_rows)
        defs_ran.update(tf_defs)
    defs_used = "+".join(sorted(defs_ran)) if defs_ran else "NONE"
    rows.sort(key=lambda row: (row["t_sweep_close"], row["tf"], row["definition"], row["event_id"]))

    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    charts_dir = out_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    events_path = out_dir / "events_sweep.csv"
    with events_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    bar_counts = {tf.name: len(closed[tf]) for tf in timeframes}
    summary = _count_summary(rows, bar_counts, timeframes, defs_used)

    chart_index: list[dict[str, Any]] = []
    for row in _select_charts(rows, timeframes):
        chart_name = (
            f"{row['tf'].lower()}_sweep_{row['definition'].lower()}_{len(chart_index) + 1:02d}_"
            f"{row['event_id'].lower()}.png"
        )
        path = charts_dir / chart_name
        _draw_sweep_chart(closed[Timeframe[row["tf"]]], row, path)
        chart_index.append({
            "file": f"charts/{chart_name}", "tf": row["tf"], "definition": row["definition"],
            "pool": row["pool"], "direction": row["direction"],
            "level_price": row["level_price"], "event_id": row["event_id"],
            "t_sweep_close": row["t_sweep_close"],
        })
    summary["chart_count"] = len(chart_index)
    summary["chart_selection_rule"] = (
        "per chart TF (H4, H1): earliest definition-A sweep, earliest definition-B "
        "sweep, then earliest remaining; up to 3 per TF; scoring sample only"
    )
    summary["chart_index"] = chart_index
    summary["events_csv_sha256"] = hashlib.sha256(events_path.read_bytes()).hexdigest()
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "window": summary["window"],
        "defs_used": defs_used,
        "bar_counts": bar_counts,
        "sweep_counts_by_tf_definition_direction": summary["sweep_counts_by_tf_definition_direction"],
        "event_rows": len(rows),
        "chart_count": len(chart_index),
        "events_csv_sha256": summary["events_csv_sha256"],
        "artifacts": str(out_dir),
    }, indent=2))


if __name__ == "__main__":
    main()
