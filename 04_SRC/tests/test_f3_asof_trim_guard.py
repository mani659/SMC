"""F3 guard — as_of trim convention for the validation series (look-ahead).

Look-ahead audit (2026-10-06, CONFIRMED_CLEAN): Pillar 1's ``_mitigated``
reads the ``candles[active_index+1:]`` suffix of whatever series the caller
supplies. That is look-ahead-safe ONLY because every batch call site trims
the series to ``as_of`` before the pipeline sees it:

* research funnel — ``h1[:cut+1]`` (phase3_structure_funnel),
* paper runner — ``build_htf_prefixes(series_by_tf, as_of)``
  (``smc/paper/runner.py::arm_multi_tf``),
* live loop — dispatches through the same paper seam (``arm_multi_tf``).

F3 = Pillar-1 mitigation suffix is safe by upstream trim convention. These
tests LOCK that convention in (no production behavior change):

1. Pillar 1's mitigation decision is demonstrably suffix-sensitive — a
   post-as_of mitigating close flips PASS → FAIL. This is the reason the
   trim is load-bearing.
2. ``build_htf_prefixes`` (the product trim seam) never delivers a series
   whose last bar is after ``as_of``, on any timeframe.
3. The product batch call site (``PaperRunner.arm_multi_tf``) delivers
   trimmed prefixes — last bar ≤ as_of — to the runtime for every TF.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, LiquidityType, PoolType
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.detection.displacement_checker import check_displacement
from smc.orchestration.multi_tf_runtime import build_htf_prefixes
from smc.validation.pillar import PillarStatus
from smc.validation.validation_pipeline import (
    ValidationDecision,
    ValidationPipeline,
)
from tests.test_multi_tf_product_path import (
    _FakeOrderManager,
    _FakePositionManager,
    _SpyRuntime,
    _make_series,
    _paper_runner,
)

TF = Timeframe.M5
CALM = [(99.5, 99.7, 99.3, 99.6)]

# Same success fixture shape as test_validation_pipeline: 15 calm bars +
# bullish FVG [100.0, 100.2] + approach bars (no close below the zone).
TRIMMED_ROWS = CALM * 15 + [
    (99.9, 100.0, 99.7, 99.9),       # c1: first FVG candle (OB candidate)
    (100.0, 100.1, 99.6, 100.0),     # c2: middle candle
    (100.15, 100.35, 100.2, 100.3),  # c3: FVG [100.0, 100.2]
    (100.3, 100.4, 100.1, 100.35),   # approach
    (100.35, 100.5, 100.3, 100.45),  # approach
    (100.45, 100.6, 100.4, 100.55),  # as_of bar (close 100.55)
]
# The ONE post-as_of bar: a close below the zone bottom (100.0) AND below
# the OB wick low (99.7) — mitigates both refinement candidates. Shaped so
# it mints NO new FVG of its own (no strict gap vs the prior triplet), so
# the ONLY decision change is the mitigation of the pre-as_of candidates.
# Only a series that is NOT trimmed to as_of would ever contain it.
POST_ASOF_ROW = [(99.9, 100.3, 99.5, 99.65)]

PRE_DISP = [(100.5, 101.5, 99.5, 100.5)] * 15

START = datetime(2026, 3, 12, 8, 0, tzinfo=timezone.utc)


def _fvg_poi() -> POI:
    return POI(
        zone=Zone(top=100.2, bottom=100.0, direction=Direction.LONG, timeframe=TF),
        models=[ModelType.M1, ModelType.M2],
    )


def _displacement(candle_factory):
    candles = candle_factory(
        PRE_DISP
        + [
            (99.8, 100.5, 98.2, 99.6),
            (100.0, 102.5, 100.3, 100.8),
            (101.0, 103.5, 102.0, 103.2),
        ]
    )
    return check_displacement(candles, Direction.LONG, sweep_index=15, bos_level=101.2)


def _validate(candle_factory, swing_factory, rows):
    candles = candle_factory(rows, timeframe=TF)
    swings = [
        swing_factory(candles, 3, True, level=105.0),
        swing_factory(candles, 4, False, level=99.0),
    ]
    poi = _fvg_poi()
    result = ValidationPipeline().validate(
        poi,
        candles,
        swings,
        [LiquidityLevel(type=LiquidityType.EQUAL_HIGHS_LOWS, level=100.3,
                        pool=PoolType.SSL, timeframe=TF)],
        displacement=_displacement(candle_factory),
    )
    return result, result.pillar_results[0]


# ---------------------------------------------------------------------- #
# 1 — the suffix sensitivity that makes the trim load-bearing
# ---------------------------------------------------------------------- #
def test_pillar1_mitigation_is_suffix_sensitive(candle_factory, swing_factory):
    """Trimmed to as_of → the FVG refines (PASS); untrimmed → mitigated (FAIL).

    This is the F3 statement: Pillar 1's suffix read is correct ONLY on an
    as_of-trimmed series. A future mitigating close must never influence the
    decision — and it does not, precisely because the callers trim.
    """
    trimmed, trimmed_p1 = _validate(candle_factory, swing_factory, TRIMMED_ROWS)
    assert trimmed.decision is ValidationDecision.PASS
    assert trimmed_p1.status is PillarStatus.PASS

    untrimmed, untrimmed_p1 = _validate(
        candle_factory, swing_factory, TRIMMED_ROWS + POST_ASOF_ROW)
    assert untrimmed.decision is ValidationDecision.REJECTED
    assert untrimmed_p1.status is PillarStatus.FAIL
    assert "naked level" in untrimmed_p1.detail


# ---------------------------------------------------------------------- #
# 2 — the product trim seam never delivers a future bar
# ---------------------------------------------------------------------- #
def test_build_htf_prefixes_last_bar_never_exceeds_as_of():
    """Every TF prefix ends at or before as_of (F3 trim contract)."""
    end = START + timedelta(hours=300)
    series_by_tf = {
        Timeframe.H4: _make_series(Timeframe.H4, 90, start=end - timedelta(hours=360)),
        Timeframe.H1: _make_series(Timeframe.H1, 260, start=end - timedelta(hours=260)),
        Timeframe.D1: _make_series(Timeframe.D1, 40, start=end - timedelta(days=40),
                                   step_minutes=1440),
    }
    # as_of sits strictly BETWEEN two bars of every series: no bar == as_of.
    as_of = series_by_tf[Timeframe.H1][-2].timestamp + timedelta(minutes=30)
    prefixes = build_htf_prefixes(series_by_tf, as_of)
    for tf, prefix in prefixes.items():
        assert prefix, f"{tf.name} prefix unexpectedly empty"
        last = prefix[-1].timestamp
        assert last <= as_of, f"{tf.name} prefix includes a future bar ({last} > {as_of})"

    # When a bar lands exactly ON as_of, it is the inclusive last bar.
    exact = series_by_tf[Timeframe.H1][-2].timestamp
    prefixes2 = build_htf_prefixes(series_by_tf, exact)
    for tf, prefix in prefixes2.items():
        assert prefix[-1].timestamp <= exact
    assert prefixes2[Timeframe.H1][-1].timestamp == exact


# ---------------------------------------------------------------------- #
# 3 — the product batch call site delivers trimmed series
# ---------------------------------------------------------------------- #
def test_paper_arm_multi_tf_delivers_asof_trimmed_series():
    """arm_multi_tf (live loop's dispatch target) trims BEFORE the runtime."""
    spy = _SpyRuntime()
    runner, _adapter = _paper_runner(spy)
    end = START + timedelta(hours=200)
    series_by_tf = {
        Timeframe.H4: _make_series(Timeframe.H4, 80, start=end - timedelta(hours=320)),
        Timeframe.H1: _make_series(Timeframe.H1, 220, start=end - timedelta(hours=220)),
    }
    as_of = series_by_tf[Timeframe.H1][-3].timestamp   # mid-series: future bars exist

    runner.arm_multi_tf(series_by_tf, as_of=as_of, arm_bar=0)

    assert len(spy.calls) == 1
    delivered = spy.calls[0]["series_by_tf"]
    for tf, prefix in delivered.items():
        assert prefix, f"{tf.name} series unexpectedly empty"
        assert prefix[-1].timestamp <= as_of, (
            f"{tf.name} series reached the runtime UNTRIMMED "
            f"({prefix[-1].timestamp} > {as_of}) — Pillar 1's mitigation "
            "suffix read would see future bars"
        )
    # And the delivered prefixes are exactly the trim seam's output.
    expected = build_htf_prefixes(series_by_tf, as_of)
    for tf in series_by_tf:
        assert delivered[tf] == expected[tf]
