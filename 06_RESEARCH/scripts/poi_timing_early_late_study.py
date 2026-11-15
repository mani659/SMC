"""POI timing study — frozen EARLY / ON-WINDOW / LATE taxonomy + windows.

This module is the single home of the FROZEN timing label used by every
confirmation-geometry measurement (OPT-1 / OPT-4 / OPT-B), and of the window
family those studies ran on.

The taxonomy
------------
Given a confirmation-bar CLOSE and the POI zone, with ``band = ZONE_REFINEMENT_ATR
× ATR`` (the locked FR-3/R7 band, READ — never re-defined here):

* ``BEYOND_STOP_SIDE`` — the close leaked past the protective side of the zone
  by more than the band (LONG: below ``zone.bottom``; SHORT: above ``zone.top``);
* ``LATE`` — the close displaced AWAY from the protective side by more than the
  band (LONG: above ``zone.top``; SHORT: below ``zone.bottom``);
* ``ON_WINDOW`` — everything else (inside the zone or within the band).

The band is INCLUSIVE: exactly ``band`` beyond an edge stays ``ON_WINDOW``.

``timing_label`` returns ``(label, distance_atr)`` where the distance is the
band excursion in ATR units (0.0 when inside the band), rounded to 6 dp — the
exported convention.

.. note::
   **Recovery provenance (2026-11-08).** The original study body was lost to a
   file corruption event (only the ``WINDOWS`` literal survived). The frozen
   label rule below was re-derived and verified to reproduce all 60 labelled
   rows of ``06_RESEARCH/results/confirm_vs_zone_opt4_wider/join_primary.csv``
   exactly (0 mismatches), so it is the same rule the published measurements
   used. ``main()`` fails loud: the study harness itself is NOT reconstructed
   and must not be silently re-run or cited as new evidence.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from smc.config.locked_constants import ZONE_REFINEMENT_ATR
from smc.core.enums import Direction

LABEL_ON_WINDOW = "ON_WINDOW"
LABEL_LATE = "LATE"
LABEL_BEYOND_STOP_SIDE = "BEYOND_STOP_SIDE"
LABEL_OTHER = "OTHER"
LABEL_UNLOCATABLE = "UNLOCATABLE"

#: Frozen window family (primary = the OPT-1/OPT-4/OPT-B baseline window).
WINDOWS = {
    "primary": {
        "load_from": datetime(2025, 5, 1, tzinfo=timezone.utc),
        "exec_from": datetime(2025, 6, 1, tzinfo=timezone.utc),
        "exec_to": datetime(2025, 11, 30, 23, 59, tzinfo=timezone.utc),
        "fill_takeability_capture": "primary_rerun",
    },
    "secondary": {
        "load_from": datetime(2023, 11, 1, tzinfo=timezone.utc),
        "exec_from": datetime(2023, 12, 1, tzinfo=timezone.utc),
        "exec_to": datetime(2025, 5, 31, 23, 59, tzinfo=timezone.utc),
        "fill_takeability_capture": "secondary_18m",
    },
}


def _direction_of(direction) -> Direction | None:
    if isinstance(direction, Direction):
        return direction
    try:
        return Direction(str(direction).lower())
    except (TypeError, ValueError):
        return None


def timing_label(
    direction,
    zone_bottom: float | None,
    zone_top: float | None,
    close: float | None,
    atr: float | None,
    band_atr: float = ZONE_REFINEMENT_ATR,
) -> tuple[str, float | None]:
    """Frozen timing label + band excursion in ATR for one confirmation close.

    Unresolvable inputs (missing bounds/close, non-positive ATR, unknown
    direction) return ``UNLOCATABLE`` / ``OTHER`` with ``None`` distance —
    values are never invented.
    """
    side = _direction_of(direction)
    if side is None:
        return LABEL_OTHER, None
    if (
        zone_bottom is None
        or zone_top is None
        or close is None
        or atr is None
        or float(atr) <= 0
    ):
        return LABEL_UNLOCATABLE, None
    low, high = sorted((float(zone_bottom), float(zone_top)))
    price = float(close)
    atr = float(atr)
    band = float(band_atr) * atr
    if side is Direction.LONG:
        trade_excursion = price - high      # away from the protective stop
        stop_excursion = low - price        # past the protective side
    else:
        trade_excursion = low - price
        stop_excursion = price - high
    if stop_excursion > band:
        return LABEL_BEYOND_STOP_SIDE, round(stop_excursion / atr, 6)
    if trade_excursion > band:
        return LABEL_LATE, round(trade_excursion / atr, 6)
    inside = max(trade_excursion, stop_excursion, 0.0)
    return LABEL_ON_WINDOW, round(inside / atr, 6)


def main(argv: list[str] | None = None) -> int:
    message = (
        "poi_timing_early_late_study: the ORIGINAL study body was lost to the "
        "2026-11-08 file-corruption event and is NOT reconstructed.\n"
        "The frozen label rule and window family are preserved in this module "
        "(verified against the OPT-4 wider CSV: 0 mismatches over 60 rows).\n"
        "Do not re-run or cite this harness as new evidence. For the menu-path "
        "join use 06_RESEARCH/scripts/opt4_wider_join.py instead."
    )
    print(message, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
