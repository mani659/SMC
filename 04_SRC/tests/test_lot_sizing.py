"""Phase 4 — risk lot sizing formula tests (v25 reference, parameters injected)."""

import pytest

from smc.execution.lot_sizing import risk_lots


def test_standard_formula():
    # Lots = (Equity × Risk%) / (SL × tick value) = (10_000 × 0.01)/(5×10)
    lots = risk_lots(
        equity=10_000, risk_fraction=0.01, sl_distance=5.0,
        pip_value_per_lot=10.0, min_lots=0.01, lot_step=0.01,
    )
    assert lots == pytest.approx(2.0)


def test_rounds_down_to_lot_step():
    lots = risk_lots(
        equity=10_000, risk_fraction=0.01, sl_distance=8.0,
        pip_value_per_lot=10.0, min_lots=0.01, lot_step=0.01,
    )
    # raw = 1.25 → floor to 1.25? 1.25/0.01=125 steps → 1.25 exact
    assert lots == pytest.approx(1.25)


def test_floors_to_step_grid():
    lots = risk_lots(
        equity=10_000, risk_fraction=0.01, sl_distance=7.5,
        pip_value_per_lot=10.0, min_lots=0.01, lot_step=0.1,
    )
    # raw = 1.333… → 13 steps of 0.1 → 1.3
    assert lots == pytest.approx(1.3)


def test_below_minimum_returns_zero():
    lots = risk_lots(
        equity=100, risk_fraction=0.001, sl_distance=50.0,
        pip_value_per_lot=10.0, min_lots=0.01, lot_step=0.01,
    )
    assert lots == 0.0


def test_no_equity_returns_zero():
    assert (
        risk_lots(0.0, 0.01, 5.0, 10.0, 0.01, 0.01) == 0.0
    )


def test_invalid_distances_raise():
    with pytest.raises(ValueError):
        risk_lots(10_000, 0.01, 0.0, 10.0, 0.01, 0.01)
    with pytest.raises(ValueError):
        risk_lots(10_000, 0.01, 5.0, 0.0, 0.01, 0.01)
