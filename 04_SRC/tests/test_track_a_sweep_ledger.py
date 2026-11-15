"""Unit tests for new pure helpers in the Track A sweep observation ledger."""

from pathlib import Path
import sys

import pytest

from smc.config.timeframe import Timeframe
from smc.core.enums import PoolType

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))
from track_a_sweep_ledger import (  # noqa: E402
    _pool_direction,
    _sweep_rows,
    _zone_bound_levels,
)


def test_pool_direction_labels_are_pool_side_only():
    assert _pool_direction(PoolType.BSL) == "SHORT"
    assert _pool_direction(PoolType.SSL) == "LONG"
    with pytest.raises(ValueError, match="unsweepable pool"):
        _pool_direction(PoolType.OB_EXTREME)


def _causality_series():
    """Shared synthetic M5 series (N=3) with a valid swing high + LONG BOS.

    idx4 = swing-high pivot (105.0); idx7 closes below the base-candle low
    (§19 validity, from idx7 the swing is knowable); idx8 closes above the
    swing high (BOS LONG); idx7 is also the nearest earlier bearish candle,
    i.e. the ledger's LAST_OPPOSITE_BEFORE_BOS origin with full-wick bounds
    99.0–101.6; idx9 wicks above 101.6 with a close back below — the sweep.
    """
    from conftest import make_candles

    return make_candles([
        (100.0, 100.5, 99.5, 100.2),
        (100.2, 100.8, 100.0, 100.6),
        (100.6, 101.0, 100.4, 100.9),
        (100.9, 101.4, 100.7, 101.2),
        (101.2, 105.0, 101.0, 101.5),   # idx4 pivot high 105.0
        (101.5, 101.9, 101.2, 101.6),
        (101.6, 102.0, 100.1, 101.0),   # bearish
        (101.0, 101.6, 99.0, 99.6),     # idx7: §19 confirming close; OB origin (bearish), bounds 99.0–101.6
        (99.6, 106.0, 99.0, 107.0),     # idx8: close above 105 (BOS LONG); breakout, NOT a sweep
        (107.0, 107.5, 100.0, 100.2),   # idx9: wick above 105, close back below (BSL A-sweep of swing high)
        (100.0, 102.0, 99.8, 100.5),    # idx10: wick above 101.6, close back below (BSL B-sweep of OB top)
    ], timeframe=Timeframe.M5)


def test_ob_origin_cannot_sweep_at_its_own_forming_bar():
    """Definition B causality: the OB origin candle must not count as its own sweep.

    The origin candle (idx7) closes below its own wick top, so a naive scan
    would flag it as a BSL sweep of its own bound — the formed_at bound must
    exclude it; the first legal sweep is idx9.
    """
    rows, defs_ran = _sweep_rows(_causality_series(), Timeframe.M5)
    assert "B" in defs_ran
    b_rows = [row for row in rows if row["definition"] == "B"]
    bsl_rows = [row for row in b_rows if row["pool"] == "bsl"]
    assert bsl_rows
    for row in b_rows:
        assert row["swept_bar_index"] > row["level_formed_index"]


def test_structural_sweep_lands_only_after_known_at():
    """Definition A causality: a swing cannot sweep inside its confirmation window."""
    rows, defs_ran = _sweep_rows(_causality_series(), Timeframe.M5)
    assert "A" in defs_ran
    a_rows = [row for row in rows if row["definition"] == "A"]
    assert a_rows
    for row in a_rows:
        assert row["swept_bar_index"] > row["level_formed_index"]
        assert row["swept_bar_index"] >= int(row["notes"].split("known_at=")[1].split(";")[0])


def test_zone_specs_carry_ledger_provenance_and_bounds():
    """Every B spec's bound must equal its source event-row bound."""
    candles = _causality_series()
    import ungated_event_ledger_p1 as base_ledger

    ledger_rows = {row["event_id"]: row for row in base_ledger._event_rows(candles, Timeframe.M5)}
    specs = _zone_bound_levels(candles, Timeframe.M5)
    assert specs
    for _level_id, level, meta in specs:
        assert meta["definition"] == "B"
        source = ledger_rows[meta["source_event_id"]]
        bound = float(level.level)
        assert (
            bound == float(source["price_or_high"])
            or bound == float(source["price_or_low"])
        )
        assert level.formed_at == candles[meta["level_formed_index"]].timestamp
        assert level.pool in (PoolType.BSL, PoolType.SSL)
