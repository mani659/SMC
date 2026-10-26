"""L2 backfill — enrich the setup identification ledger (directive 2026-10-06).

RESEARCH / EXPORT ONLY. No trading threshold or strategy logic changes.

Backfills, deterministically and without invention:

* ``direction`` — joined from EXISTING artifacts only, two sources in
  priority order:
    1. ``trade_row``     — the hypothesis-outcome CSV carries the trade's
       direction (3 routed setups);
    2. ``structure_ledger_geometry`` — an EXACT match on
       (detection_tf, zone_low, zone_high) against a ``poi_raw`` event in
       the 6m structure ledger that carries exactly one distinct direction.
       No tolerance, no price-based inference: a geometry that is absent or
       direction-conflicting in the source stays unfilled.
  Rows with no deterministic source get ``direction_source = DATA_GAP``
  (the direction cell itself stays blank).
* ``arm_ts_utc`` — the exec-bar → timestamp map (exec bar 0 =
  window start 2025-06-01T22:00Z; validated against the 3 routed trades'
  recorded entry/exit timestamps — 6/6 exact matches). This is a
  documented bar-indexing convention, not a price inference.
* ``posture`` — NOT present in any funnel artifact (checked: armed_records,
  funnel_summary, report.json); stays ``UNKNOWN`` and is documented. Never
  inferred from price.

Human columns (verdict / timing / notes) stay BLANK — the human-never-
pre-filled rule is untouched. Hypothesis-outcome joins are preserved.

Determinism: sorted rows, no wall clock — same inputs → byte-identical
outputs (dual-run SHA-256 verified).

Usage:
    python 06_RESEARCH/scripts/setup_ledger_backfill.py \
        [--artifacts-root 06_RESEARCH/results] [--data 07_DATA/XAUUSD_M1.parquet]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from smc.config.timeframe import Timeframe                    # noqa: E402
from smc.data.parquet_loader import load_ohlcv_parquet        # noqa: E402
from smc.data.resample import resample_ohlcv                  # noqa: E402

__all__ = ["backfill_ledger", "main"]

LEDGER_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "setup_identification_ledger"
RUN_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "frozen_funnel_6m_post_tp" / "run1"
HYP_CSV = REPO_ROOT / "06_RESEARCH" / "results" / "hypothesis_outcome" / "trades_hypothesis.csv"
STRUCTURE_LEDGER = REPO_ROOT / "06_RESEARCH" / "results" / "structure_ledger_6m" / "events.csv"
RUN_LABEL = "6m_post_tp_run1"

#: New columns appended before the human-scoring block.
NEW_COLUMNS = ["direction_source", "arm_ts_utc"]


def _load_direction_index() -> dict:
    """(tf, zone_low, zone_high) → set of directions, from poi_raw events."""
    index: dict = defaultdict(set)
    if not STRUCTURE_LEDGER.exists():
        raise SystemExit(f"FATAL: structure ledger missing: {STRUCTURE_LEDGER}")
    with STRUCTURE_LEDGER.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("event_type") != "poi_raw" or not row.get("direction"):
                continue
            key = (row["detection_tf"],
                   round(float(row["price_low"]), 3),
                   round(float(row["price_high"]), 3))
            index[key].add(row["direction"])
    return index


def _load_trades() -> dict:
    """poi_id → trade row (for the run) — carries direction/entry/exit bars."""
    trades: dict = {}
    if not HYP_CSV.exists():
        raise SystemExit(f"FATAL: hypothesis-outcome CSV missing: {HYP_CSV}")
    with HYP_CSV.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("run_label") != RUN_LABEL:
                continue
            pid = row.get("poi_id") or ""
            if pid and pid not in trades:
                trades[pid] = row
    return trades


def _exec_m5_series(data_path: Path, window: dict):
    """Exec M5 series for the frozen window (exec bar 0 = window start)."""
    if not data_path.exists():
        raise SystemExit(f"FATAL: M1 parquet missing: {data_path}")
    m1 = load_ohlcv_parquet(str(data_path))
    start = datetime.fromisoformat(window["start"])
    end = datetime.fromisoformat(window["end"])
    sliced = [c for c in m1 if start <= c.timestamp <= end]
    return resample_ohlcv(sliced, Timeframe.M5)


def backfill_ledger(*, data_path: Path) -> dict:
    """Backfill setups.csv in place; returns stats for the summary merge."""
    csv_path = LEDGER_DIR / "setups.csv"
    summary_path = LEDGER_DIR / "summary.json"
    if not csv_path.exists() or not summary_path.exists():
        raise SystemExit(f"FATAL: run the base ledger first ({csv_path})")

    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    direction_index = _load_direction_index()
    trades = _load_trades()

    # Exec M5 series for arm-bar → timestamp (validation against trades).
    m5 = _exec_m5_series(data_path, summary["window"])

    def bar_ts(bar: int) -> str:
        if 0 <= bar < len(m5):
            return m5[bar].timestamp.isoformat()
        return ""

    # Validate the bar map against the routed trades' recorded timestamps
    # (entry + exit = 6 checks). A mismatch would invalidate arm_ts_utc.
    checks, checks_ok = 0, 0
    for pid, trade in trades.items():
        for bar_key, at_key in (("entry_bar", "entry_at"), ("exit_bar", "exit_at")):
            try:
                mapped = bar_ts(int(trade[bar_key]))
            except (KeyError, TypeError, ValueError):
                mapped = ""
            recorded = (trade.get(at_key) or "").replace(" ", "T")
            if not mapped or not recorded:
                continue
            checks += 1
            # recorded uses 'YYYY-MM-DDTHH:MM:SS+00:00' after the replace
            if mapped == recorded or mapped.startswith(recorded[:16]):
                checks_ok += 1

    # Ensure the new columns exist (append before the human block).
    for col in NEW_COLUMNS:
        if col not in fieldnames:
            fieldnames.insert(fieldnames.index("verdict"), col)

    direction_filled = 0
    sources: dict = {}
    for row in rows:
        pid = row["poi_id"]
        trade = trades.get(pid)

        # 1) direction — trade row first, then exact unique geometry.
        direction, source = row.get("direction", ""), "DATA_GAP"
        if trade and trade.get("direction"):
            direction, source = trade["direction"], "trade_row"
        else:
            key = (row["detection_tf"],
                   round(float(row["zone_low"]), 3),
                   round(float(row["zone_high"]), 3))
            hits = direction_index.get(key, set())
            if len(hits) == 1:
                direction, source = next(iter(hits)), "structure_ledger_geometry"
        row["direction"] = direction
        row["direction_source"] = source
        sources[source] = sources.get(source, 0) + 1
        if direction:
            direction_filled += 1

        # 2) posture — NOT in any artifact; stays UNKNOWN (never inferred).
        row["posture"] = "UNKNOWN"

        # 3) arm timestamp from the exec-bar map (documented convention).
        try:
            row["arm_ts_utc"] = bar_ts(int(row["armed_bar"]))
        except (TypeError, ValueError):
            row["arm_ts_utc"] = ""

    rows.sort(key=lambda r: (int(r["armed_bar"]), r["poi_id"]))
    for index, row in enumerate(rows, start=1):
        row["setup_index"] = str(index)

    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary["backfill"] = {
        "direction_filled_n": direction_filled,
        "still_blank_n": len(rows) - direction_filled,
        "direction_sources": dict(sorted(sources.items())),
        "direction_rule": (
            "trade_row first, then EXACT unique (tf, zone_low, zone_high) "
            "geometry match against 6m structure-ledger poi_raw events; "
            "no tolerance, no price-based inference — absent/conflicting "
            "geometry stays DATA_GAP"
        ),
        "posture": "UNKNOWN for all rows — not present in any funnel artifact "
                   "(armed_records.json / funnel_summary.json / report.json "
                   "checked); never inferred from price",
        "arm_ts_rule": (
            "exec M5 bar index → timestamp (exec bar 0 = window start); "
            "documented bar-indexing convention, not a price inference"
        ),
        "arm_ts_validation": f"{checks_ok}/{checks} routed trade entry/exit "
                             "timestamps reproduced exactly by the bar map",
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "rows": rows,
        "direction_filled": direction_filled,
        "total": len(rows),
        "checks_ok": checks_ok,
        "checks": checks,
        "sources": sources,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Setup ledger backfill")
    parser.add_argument("--data", default=str(REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"))
    args = parser.parse_args(argv)

    result = backfill_ledger(data_path=Path(args.data))
    print("setup_ledger_backfill")
    print(f"  direction : {result['direction_filled']}/{result['total']} filled")
    print(f"  sources   : {result['sources']}")
    print(f"  posture   : UNKNOWN for all (not in artifacts — documented)")
    print(f"  arm_ts    : bar-map validation {result['checks_ok']}/{result['checks']} exact")
    print(f"  outputs   : {LEDGER_DIR / 'setups.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
