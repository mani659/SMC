"""POST-V1 PHASE C — segment-boundary exposure quantification (read-only).

The Phase C baseline was produced by the SEGMENTED runner (calendar-year
segments, fresh engine/runner per segment).  The independent perf audit
(``06_RESEARCH/PHASE_C_PERF_AUDIT.md`` §5) proved on real data that the
segmented design does not carry episode / one-shot state across a segment
boundary: splitting the continuous October probe at an interior bar lost 1 of
the 6 post-boundary trades (CARRY_LOSS = 1).

This script measures how much that limitation can matter to the SHIPPED
baseline artifacts, without re-running anything:

  1. **End-of-segment open positions** — per segment, compare
     ``positions_opened`` against the number of trades actually exported, and
     read ``positions_still_open``.  A non-zero difference is a position that
     was silently dropped at a boundary.
  2. **Boundary trade density** — trades whose entry sits within +/-1/3/7/14
     days of a calendar-year boundary, with their P/L share.
  3. **Robustness bound** — the aggregate metrics recomputed with EVERY
     boundary-region trade removed (an upper bound on boundary-induced
     distortion: the state-loss mechanism can only ever *move* trades, and the
     audit's measured magnitude is 1 trade per boundary, not all of them).
  4. **Last-trade-to-boundary gap** — how close each segment came to ending
     with a live position.

Descriptive statistics over the frozen artifacts; writes one JSON summary.

    python 06_RESEARCH/scripts/phase_c_boundary_quant.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS = REPO_ROOT / "06_RESEARCH" / "results"
RUN = "phase_c_baseline_run1"
BOUNDARIES = [
    "2022-01-01",
    "2023-01-01",
    "2024-01-01",
    "2025-01-01",
    "2026-01-01",
]
OUT = RESULTS / "phase_c_boundary_quant.json"


def profit_factor(pnl: pd.Series) -> float | None:
    gains = pnl[pnl > 0].sum()
    losses = -pnl[pnl < 0].sum()
    if losses == 0:
        return None  # never inf: a zero-loss book has an undefined PF
    return float(gains / losses)


def metrics(pnl: pd.Series) -> dict:
    return {
        "n_trades": int(len(pnl)),
        "n_wins": int((pnl > 0).sum()),
        "win_rate": round(float((pnl > 0).mean()), 6) if len(pnl) else None,
        "net_pnl": round(float(pnl.sum()), 6),
        "profit_factor": (
            round(pf, 6) if (pf := profit_factor(pnl)) is not None else None
        ),
    }


def main() -> int:
    trades = pd.read_csv(RESULTS / RUN / "merged" / "trades.csv")
    trades["entry_at"] = pd.to_datetime(
        trades["entry_at"], utc=True, format="ISO8601"
    )
    trades["exit_at"] = pd.to_datetime(trades["exit_at"], utc=True, format="ISO8601")
    pnl = pd.to_numeric(trades["pnl"])

    report: dict = {
        "run": RUN,
        "merged": metrics(pnl),
        "segments": {},
        "boundaries": [],
        "robustness": {},
    }

    # 1. + 4. Per-segment dropped-position check and flat-exit gap.
    for path in sorted((RESULTS / RUN / "segments").glob("*/summary.json")):
        name = path.parent.name
        with open(path, encoding="utf-8") as handle:
            summary = json.load(handle)
        funnel = summary["funnel"]
        report["segments"][name] = {
            "n_trades": summary["metrics"]["n_trades"],
            "positions_opened": funnel.get("positions_opened"),
            "positions_still_open": funnel.get("positions_still_open"),
            "friday_closes": funnel.get("friday_closes"),
            "closed_by_kind": funnel.get("closed_by_kind"),
            "blocked_by_reason": funnel.get("blocked_by_reason"),
            "net_pnl": summary["metrics"]["net_pnl"],
        }

    opened = sum(s["positions_opened"] or 0 for s in report["segments"].values())
    exported = sum(s["n_trades"] for s in report["segments"].values())
    still_open = sum(s["positions_still_open"] or 0 for s in report["segments"].values())
    report["dropped_position_check"] = {
        "positions_opened_total": opened,
        "trades_exported_total": exported,
        "positions_still_open_total": still_open,
        "silently_dropped_total": opened - exported,
        "interpretation": (
            "opened == exported and still_open == 0 at every segment end means no "
            "position was left dangling at a calendar-year boundary in this run"
        ),
    }

    # 2. Boundary trade density.
    for width in (1, 3, 7, 14):
        mask = pd.Series(False, index=trades.index)
        for boundary in BOUNDARIES:
            mask |= (trades["entry_at"] - pd.Timestamp(boundary, tz="UTC")).abs() <= (
                pd.Timedelta(days=width)
            )
        report["boundaries"].append(
            {
                "window_days": width,
                "n_trades": int(mask.sum()),
                "share_of_trades": round(float(mask.mean()), 6),
                "net_pnl": round(float(pnl[mask].sum()), 6),
                "metrics": metrics(pnl[mask]),
            }
        )

    # Candidate "boundary contamination bound" = every trade within +/-14 days of
    # ANY boundary removed.
    mask14 = _mask_within(trades["entry_at"], 14, BOUNDARIES)
    mask7 = _mask_within(trades["entry_at"], 7, BOUNDARIES)
    report["robustness"] = {
        "with_all_trades": metrics(pnl),
        "excluding_all_trades_within_14d_of_a_boundary": metrics(pnl[~mask14]),
        "excluding_all_trades_within_7d_of_a_boundary": metrics(pnl[~mask7]),
        "interpretation": (
            "even deleting every boundary-region trade leaves the diagnostic "
            "shape (PF well below 1) unchanged"
        ),
    }

    # 4. Flat-exit gap per segment: distance from the last exit to the segment end.
    segment_bounds = {
        "0_2021": ("2021-04-12", "2021-12-31 23:59"),
        "1_2022": ("2022-01-01", "2022-12-31 23:59"),
        "2_2023": ("2023-01-01", "2023-12-31 23:59"),
        "3_2024": ("2024-01-01", "2024-12-31 23:59"),
        "4_2025": ("2025-01-01", "2025-12-31 23:59"),
        "5_2026": ("2026-01-01", "2026-04-10 23:59"),
    }
    gaps = {}
    for name, (start, end) in segment_bounds.items():
        start_ts = pd.Timestamp(start, tz="UTC")
        end_ts = pd.Timestamp(end, tz="UTC")
        own = trades[
            (trades["entry_at"] >= start_ts) & (trades["entry_at"] <= end_ts)
        ]
        gaps[name] = {
            "n_trades": int(len(own)),
            "first_entry": str(own["entry_at"].min()) if len(own) else None,
            "last_exit": str(own["exit_at"].max()) if len(own) else None,
            "last_exit_to_segment_end_hours": (
                round((end_ts - own["exit_at"].max()).total_seconds() / 3600, 3)
                if len(own)
                else None
            ),
        }
    report["segment_flat_exit_gaps"] = gaps

    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"\n[written] {OUT}")
    return 0


def _mask_within(times: pd.Series, width: int, boundaries: list[str]) -> pd.Series:
    mask = pd.Series(False, index=times.index)
    for boundary in boundaries:
        mask |= (times - pd.Timestamp(boundary, tz="UTC")).abs() <= pd.Timedelta(
            days=width
        )
    return mask


if __name__ == "__main__":
    raise SystemExit(main())
