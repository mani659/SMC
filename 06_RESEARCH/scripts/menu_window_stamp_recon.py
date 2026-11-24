"""MENU WINDOW STAMP RECONCILIATION — read-only (no replay, no logic change).

Question
--------
The F/B entry-quality study flagged **11 B fills** (F: 0) whose confirmation
timestamp is later than the `window_end_ts` carried on their own menu stamp —
seven by 30.5-39.4 h. Is that a window breach, or an artefact of how the stamp
is written?

Method (read-only, deterministic)
---------------------------------
1. Reuse the entry-quality universe verbatim (`entry_quality_f_b.load_universe`
   + `feature_row`): the post-R1 union of books F and B, 592 fills.
2. Rebuild each row's detection series **exactly as the S3 harness did**
   (`r1_pure_tag_books.segment_series`: M1 parquet -> resample_multi H1/H4/D1,
   M15 derived via `ensure_product_detection_frames(source=m5)`).
3. For every row, compare three things:
   * `window_end_ts` on the stamp (what the adapter/audit reads),
   * the **nominal** projection `sweep_close + MENU_EXPIRY_BARS x det_minutes`
     (the `_win` fallback at product_menu_mtf.py:895-903),
   * the **bar-count** window end: close of the detection bar at
     `sweep_index + MENU_EXPIRY_BARS` (what `_window_end_ts` /
     `_route_for` / `_expire` actually enforce).
4. Classify every fill: confirmation inside/outside each bound, and whether the
   *fill* is late while its confirmation was inside.

Outputs (gitignored results tree)
---------------------------------
`06_RESEARCH/results/menu_window_stamp_recon/post_window_fills.csv` (the 11)
`06_RESEARCH/results/menu_window_stamp_recon/window_bounds_all_rows.csv` (all 592)
`06_RESEARCH/results/menu_window_stamp_recon/summary.json`

Fail-loud assertions: universe 592, post-stamp confirmations == 11 and all in B,
every stamp equals its nominal projection, every late confirmation is inside the
bar-count window. Any violation stops the run — never a silent pass.

Nothing here writes to 04_SRC, locked constants, configs or the S3 artifacts.
"""

from __future__ import annotations

import csv
import json
import sys
from bisect import bisect_right
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "04_SRC"))
sys.path.insert(0, str(REPO / "06_RESEARCH" / "scripts"))

from entry_quality_f_b import feature_row, load_universe  # noqa: E402
from lib.menu_window import window_bounds  # noqa: E402
from smc.orchestration.product_menu_mtf import (  # noqa: E402
    MENU_EXPIRY_BARS,
    PRODUCT_MENU_TIERS,
)

OUT = REPO / "06_RESEARCH" / "results" / "menu_window_stamp_recon"
MINUTES = {"H1": 60, "H4": 240, "M15": 15, "D1": 1440}
EXPECTED_POST_STAMP = 11


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(str(value))


def _pct(values: list[int], q: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * q))]


def main() -> int:
    # The frozen expiry the whole comparison rests on — assert, never assume.
    assert MENU_EXPIRY_BARS == 20, MENU_EXPIRY_BARS
    tiers = {tier.name: tier for tier in PRODUCT_MENU_TIERS}
    # Shipped tier names: DAY is the D1-detection tier (product_menu_mtf.py:246).
    for tier_name in ("DAY", "H4", "H1", "M15"):
        assert tiers[tier_name].expiry_bars == MENU_EXPIRY_BARS

    rows = [feature_row(row) for row in load_universe()]
    if len(rows) != 592:
        raise SystemExit(f"FAIL LOUD: universe {len(rows)} != 592")

    records: list[dict] = []
    wend_equals_nominal = 0
    confirm_past_bar_window = 0
    depth = {"F": [], "B": []}
    gap_windows = Counter()
    gap_hours = Counter()
    fill_after_stamp_only = 0

    for row in rows:
        book = row["book"]
        tf = row["detection_tf"]
        minutes = MINUTES[tf]
        seg = row["segment"]
        sweep = _dt(row["sweep_ts"])
        wend = _dt(row["window_end_ts"])
        confirm = _dt(row["completion_ts"])
        fill = _dt(row["entry_at"])

        # One rule, shared with the entry-quality harness (G2).
        stamps, index, bar_end = window_bounds(seg, tf, sweep)
        nominal = sweep + timedelta(minutes=minutes * (MENU_EXPIRY_BARS + 1))
        if wend == nominal:
            wend_equals_nominal += 1
        # Fully-closed detection bars strictly after the sweep bar, by confirm.
        bars_closed = bisect_right(stamps, confirm - timedelta(minutes=minutes)) - (
            index + 1
        )
        # ``bar_end is None``: the window's 21st detection bar lies past the
        # segment's loaded series (late-month sweep; the harness tiles the year
        # in adjacent months). Such a window never materialises for the engine
        # either, so it is reported as truncated, never as a breach.
        truncated = bar_end is None
        inside_bar_window = None if truncated else confirm <= bar_end
        if inside_bar_window is False:
            confirm_past_bar_window += 1
        depth[book].append(bars_closed)
        if bar_end is not None and bar_end != wend:
            gap_windows[book] += 1
            gap_hours[f"{tf}:{int((bar_end - wend).total_seconds() // 3600)}h"] += 1

        late_stamp = (confirm - wend).total_seconds() / 3600.0
        if fill > wend and late_stamp <= 0:
            fill_after_stamp_only += 1
        records.append({
            "id": row["id"],
            "book": book,
            "tier": row["tier"],
            "detection_tf": tf,
            "confirmation_tf": row["confirmation_tf"],
            "direction": row["direction"],
            "poi_id": row["poi_id"],
            "run": row["run"],
            "sweep_ts": row["sweep_ts"],
            "stamped_window_end": row["window_end_ts"],
            "nominal_window_end": nominal.isoformat(),
            "bar_count_window_end": bar_end.isoformat() if bar_end else "",
            "gap_hours": (round((bar_end - wend).total_seconds() / 3600.0, 2)
                          if bar_end is not None else ""),
            "completion_ts": row["completion_ts"],
            "entry_at": row["entry_at"],
            "exit_at": row["exit_at"],
            "bars_closed_before_confirm": bars_closed,
            "window_truncated_by_segment": truncated,
            "confirm_inside_bar_window": inside_bar_window,
            "late_vs_stamp_h": round(late_stamp, 2),
            "late_vs_bar_window_h": (round((confirm - bar_end).total_seconds() / 3600.0, 2)
                                     if bar_end is not None else ""),
            "fill_lag_vs_confirm_min": int((fill - confirm).total_seconds() // 60),
            "fill_after_stamp_h": round((fill - wend).total_seconds() / 3600.0, 2),
            "entry_price": row["entry_price"],
            "exit_price": row.get("exit_price", ""),
        })

    late = [r for r in records if r["late_vs_stamp_h"] > 0]
    if len(late) != EXPECTED_POST_STAMP:
        raise SystemExit(f"FAIL LOUD: {len(late)} post-stamp rows != {EXPECTED_POST_STAMP}")
    if any(r["book"] != "B" for r in late):
        raise SystemExit("FAIL LOUD: a post-stamp row is not book B")
    if wend_equals_nominal != len(records):
        raise SystemExit(
            f"FAIL LOUD: stamp != nominal on {len(records) - wend_equals_nominal} rows"
        )
    if confirm_past_bar_window:
        raise SystemExit(f"FAIL LOUD: {confirm_past_bar_window} confirmations past the bar window")
    if any(r["window_truncated_by_segment"] for r in late):
        raise SystemExit("FAIL LOUD: a post-stamp row has a truncated bar window")

    summary = {
        "universe": len(records),
        "universe_by_book": dict(Counter(r["book"] for r in records)),
        "menu_expiry_bars": MENU_EXPIRY_BARS,
        "stamped_windows_equal_nominal_projection": wend_equals_nominal,
        "windows_spanning_a_data_gap_by_book": dict(gap_windows),
        "gap_size_histogram": dict(gap_hours),
        "confirmations_after_stamped_window": len(late),
        "confirmations_after_bar_count_window": confirm_past_bar_window,
        "windows_truncated_by_segment_by_book": dict(Counter(
            r["book"] for r in records if r["window_truncated_by_segment"])),
        "late_rows_inside_bar_window": sum(
            1 for r in late if r["confirm_inside_bar_window"] is True),
        "fills_after_stamp_with_in_window_confirmation": fill_after_stamp_only,
        "late_by_detection_tf": dict(Counter(r["detection_tf"] for r in late)),
        "late_over_30h": sum(1 for r in late if r["late_vs_stamp_h"] >= 30),
        "max_fill_lag_vs_confirm_min": max(
            abs(r["fill_lag_vs_confirm_min"]) for r in late),
        "confirm_depth_in_window_p50_p90_max": {
            book: [_pct(v, 0.5), _pct(v, 0.90), max(v)] for book, v in depth.items()
        },
        "verdict": {
            "stamp_is_wall_clock_projection": True,
            "eligibility_is_bar_counted": True,
            "window_breach": False,
            "finding": ("all 11 confirmations are inside the bar-counted window; "
                        "the stamp omits market closures and therefore ends early"),
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    fields = list(records[0].keys())
    for name, payload in (("window_bounds_all_rows.csv", records),
                          ("post_window_fills.csv", late)):
        with (OUT / name).open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(payload)
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")

    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
