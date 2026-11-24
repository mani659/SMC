"""Engine window bound for a menu stamp — one rule for the research harnesses.

The `window_end_ts` on a product-menu stamp is a **wall-clock projection**
(`sweep_close + MENU_EXPIRY_BARS x detection-bar minutes`, written by
`ProductMenuEngine._win` when `_window_end_ts` returns `None` because the
window's last detection bar has not closed). The engine's actual eligibility
is **bar-counted**: `_expire` and `_route_for` work on the detection-bar index
(`sweep_index + MENU_EXPIRY_BARS`). Across market closures (no Saturday bars in
the M1 feed) the projection lands inside the closure and reads early, so a
confirmation the engine accepted can appear "after the window" on the stamp.

This module exposes the engine-side bound so both
`entry_quality_f_b.py` (G2) and `menu_window_stamp_recon.py` measure the same
thing, and nothing re-derives the rule. Read-only: it loads the canonical M1
parquet through the frozen harness loader/resampler (`r1_pure_tag_books.
segment_series`) and never writes.

`bar_count_window_end` returns ``None`` when the window's 21st detection bar
lies beyond the loaded series (a sweep in the last 20 detection bars of a
month-tiled segment). In that case the engine itself has no upper bound
either — the caller must treat the window as open, never as closed.
"""

from __future__ import annotations

import sys
from bisect import bisect_left
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO / "06_RESEARCH" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "06_RESEARCH" / "scripts"))

MINUTES = {"H1": 60, "H4": 240, "M15": 15, "D1": 1440}
SERIES_KEY = {"H1": "h1", "H4": "h4", "M15": "m15", "D1": "d1"}

_SEGMENT_CACHE: dict[str, dict] = {}


def segment_series(segment: str) -> dict:
    """Detection/execution series for one segment, built as the S3 harness did."""
    if segment not in _SEGMENT_CACHE:
        import r1_pure_tag_books as r1  # local import: heavy module

        lo, hi = r1.SEGMENTS[segment]
        _SEGMENT_CACHE[segment] = r1.segment_series(lo, hi)
    return _SEGMENT_CACHE[segment]


def expiry_bars() -> int:
    """The frozen menu expiry, read from the engine (never hard-coded here)."""
    from smc.orchestration.product_menu_mtf import MENU_EXPIRY_BARS

    return int(MENU_EXPIRY_BARS)


def window_bounds(segment: str, detection_tf: str,
                  sweep_ts: datetime) -> tuple[list[datetime], int,
                                               datetime | None]:
    """``(detection bar open stamps, sweep index, bar-counted window end)``.

    The window end is the close of the bar at ``sweep_index +`` the frozen
    expiry; ``None`` means that bar is not in the loaded segment series, so the
    engine's window never materialises (open window, no upper bound in
    ``_route_for``). Raises when the sweep bar itself is missing — a silent
    miss would make the caller compare against the wrong window.
    """
    series = segment_series(segment)[SERIES_KEY[detection_tf]]
    stamps = [bar.timestamp for bar in series]
    index = bisect_left(stamps, sweep_ts)
    if index >= len(stamps) or stamps[index] != sweep_ts:
        raise ValueError(
            f"sweep {sweep_ts} is not a {detection_tf} bar of segment {segment!r}"
        )
    end_index = index + expiry_bars()
    if end_index >= len(stamps):
        return stamps, index, None
    return (stamps, index,
            stamps[end_index] + timedelta(minutes=MINUTES[detection_tf]))


def bar_count_window_end(segment: str, detection_tf: str,
                         sweep_ts: datetime) -> datetime | None:
    """Engine window end for one row (``None`` = open; see :func:`window_bounds`)."""
    return window_bounds(segment, detection_tf, sweep_ts)[2]
