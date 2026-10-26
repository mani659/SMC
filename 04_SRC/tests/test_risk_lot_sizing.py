"""Phase 5 — risk lot sizing policy tests (band clamp + LOT_MAX_SAFETY cap)."""

import pytest

from smc.config.locked_constants import LOT_MAX_SAFETY, RISK_PCT_MAX, RISK_PCT_MIN
from smc.risk.lot_sizing import clamp_risk_fraction, risk_lots, sized_lots


def test_risk_lots_is_re_exported_from_single_implementation():
    # Same pure v25 formula as smc.execution.lot_sizing.risk_lots (one path).
    lots = risk_lots(
        equity=10_000, risk_fraction=0.01, sl_distance=5.0,
        pip_value_per_lot=10.0, min_lots=0.01, lot_step=0.01,
    )
    assert lots == pytest.approx(2.0)


def test_clamp_risk_fraction_inside_band_passes_through():
    mid = (RISK_PCT_MIN + RISK_PCT_MAX) / 2 / 100.0
    assert clamp_risk_fraction(mid) == pytest.approx(mid)


def test_clamp_risk_fraction_floor():
    below = (RISK_PCT_MIN / 100.0) - 0.001
    assert clamp_risk_fraction(below) == pytest.approx(RISK_PCT_MIN / 100.0)


def test_clamp_risk_fraction_ceiling():
    above = (RISK_PCT_MAX / 100.0) + 0.001
    assert clamp_risk_fraction(above) == pytest.approx(RISK_PCT_MAX / 100.0)


def test_sized_lots_clamps_oversized_risk_into_band():
    # 5% requested → clamped to RISK_PCT_MAX (1%) → lots reflect the band.
    lots = sized_lots(
        equity=1_000, risk_fraction=0.05, sl_distance=20.0,
        pip_value_per_lot=10.0, min_lots=0.01, lot_step=0.01,
    )
    expected = (1_000 * (RISK_PCT_MAX / 100.0)) / (20.0 * 10.0)
    assert lots == pytest.approx(expected)


def test_sized_lots_caps_at_lot_max_safety():
    # Aggressive band-max sizing on a small SL yields lots >> LOT_MAX_SAFETY.
    lots = sized_lots(
        equity=1_000_000, risk_fraction=RISK_PCT_MAX / 100.0, sl_distance=1.0,
        pip_value_per_lot=10.0, min_lots=0.01, lot_step=0.01,
    )
    assert lots == pytest.approx(LOT_MAX_SAFETY)


def test_sized_lots_keeps_sub_cap_lots_untouched():
    # Wide SL keeps the band-max size well under LOT_MAX_SAFETY → no cap.
    lots = sized_lots(
        equity=10_000, risk_fraction=0.01, sl_distance=200.0,
        pip_value_per_lot=10.0, min_lots=0.01, lot_step=0.01,
    )
    assert lots == pytest.approx(0.05)


def test_sized_lots_below_minimum_returns_zero():
    lots = sized_lots(
        equity=100, risk_fraction=0.001, sl_distance=50.0,
        pip_value_per_lot=10.0, min_lots=0.01, lot_step=0.01,
    )
    assert lots == 0.0


def test_sized_lots_no_equity_returns_zero():
    assert (
        sized_lots(0.0, 0.01, 5.0, 10.0, 0.01, 0.01) == 0.0
    )


def test_sized_lots_invalid_distances_raise():
    with pytest.raises(ValueError):
        sized_lots(10_000, 0.01, 0.0, 10.0, 0.01, 0.01)
    with pytest.raises(ValueError):
        sized_lots(10_000, 0.01, 5.0, 0.0, 0.01, 0.01)