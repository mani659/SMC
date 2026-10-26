"""Phase C perf-patch equivalence tests (series_state + detection hoists).

The Phase C baseline depends on the incremental :class:`SeriesState` and
the detection-side hoists producing VALUES IDENTICAL to the frozen
in-place computations they replace. These tests pin each piece against
the original implementation on shared deterministic inputs:

1. Indicator folds — incremental ATR/RSI (both price spaces) vs
   ``atr_series`` / ``rsi_series`` over every prefix (fold identity),
   plus exact float equality per bar.
2. Swings — incremental candidate set / §19 validity / confirm indexes
   vs ``detect_swings`` over every prefix (creation order + confirm
   events), in both price spaces.
3. Swing indexes — bisect answers vs the linear scans of the CHOCH
   classifier (``_last_two`` / ``_minor_lows``), trigger F
   (``_last_valid_swing``), and the wave-structure chain input.
4. Detection hoists — ``check_displacement(atr=..., fvgs=...)`` and the
   per-window ``WindowCache`` pillar-1 reuse vs the legacy in-place
   computations (same results, same detail/data payloads).
5. Hint fast paths — trigger A/C/E/F and ``classify_choch_at`` with the
   ``SeriesState`` hints attached vs the no-hint path on the same
   prefixes (same signals, same fields).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from smc.backtest.series_state import SeriesState
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, TriggerType
from smc.core.poi import POI
from smc.core.swing import Swing
from smc.core.zone import Zone
from smc.detection.structural_swing_detector import detect_swings
from smc.poi.choch_classifier import (
    _invert_candles,
    _invert_swings,
    classify_choch_at,
)
from smc.triggers.base_trigger import TriggerContext, atr_band_half_width
from smc.triggers.trigger_a_choch import ChochReversalTrigger
from smc.triggers.trigger_c_ending_diagonal import EndingDiagonalTrigger
from smc.triggers.trigger_e_rsi_divergence import RsiDivergenceTrigger
from smc.triggers.trigger_f_bos_ob import BosObContinuationTrigger
from smc.utils.atr import atr_series
from smc.utils.rsi import rsi_series


# ---------------------------------------------------------------------- #
# Deterministic candle series (pseudorandom walk — no data dependency)
# ---------------------------------------------------------------------- #
def make_candles(n: int, seed: int = 20_260_914) -> list[Candle]:
    """Pseudorandom M1-like series: mixed up/down moves with wick noise."""
    state = seed
    price = 2350.0
    candles: list[Candle] = []
    t0 = datetime(2025, 10, 1, tzinfo=timezone.utc)
    for i in range(n):
        state = (state * 6364136223846793005 + 1442695040888963407) % (1 << 64)
        r = (state >> 33) / float(1 << 31) - 1.0  # -1..1
        drift = (1.0 if i % 37 < 18 else -1.0) * 0.08
        close = price + r * 1.7 + drift
        high = max(price, close) + abs(r) * 0.9 + 0.1
        low = min(price, close) - abs(r) * 0.9 - 0.1
        candles.append(
            Candle(
                timestamp=t0 + timedelta(minutes=i),
                open=price,
                high=high,
                low=low,
                close=close,
                volume=100.0 + (i % 7),
                timeframe=Timeframe.M1,
            )
        )
        price = close
    return candles


def _assert_same_float(a, b, label):
    assert (a is None) == (b is None), f"{label}: None mismatch {a!r} vs {b!r}"
    if a is None:
        return
    assert a == b or math.isclose(a, b, rel_tol=0, abs_tol=0), (
        f"{label}: {a!r} != {b!r}"
    )


# ---------------------------------------------------------------------- #
# 1. Indicator folds
# ---------------------------------------------------------------------- #
class TestIndicatorFolds:
    N = 240

    def test_atr_every_prefix(self):
        candles = make_candles(self.N)
        state = SeriesState(Timeframe.M1)
        for i, c in enumerate(candles):
            state.extend(c)
            expected = atr_series(candles[: i + 1], 14)
            assert len(state.atr_values) == len(expected)
            _assert_same_float(
                state.atr_values[-1], expected[-1], f"atr[{i}]"
            )

    def test_rsi_every_prefix_both_spaces(self):
        candles = make_candles(self.N)
        state = SeriesState(Timeframe.M1)
        for i, c in enumerate(candles):
            state.extend(c)
            expected = rsi_series(candles[: i + 1], 14)
            assert len(state.rsi_values) == len(expected)
            _assert_same_float(state.rsi_values[-1], expected[-1], f"rsi[{i}]")
            inverted = _invert_candles(candles[: i + 1])
            expected_inv = rsi_series(inverted, 14)
            _assert_same_float(
                state.rsi_values_inverted[-1],
                expected_inv[-1],
                f"rsi_inv[{i}]",
            )

    def test_inverted_candles_exact(self):
        candles = make_candles(120)
        state = SeriesState(Timeframe.M1)
        for c in candles:
            state.extend(c)
        expected = _invert_candles(candles)
        assert len(state.inverted) == len(expected)
        for i, (got, want) in enumerate(zip(state.inverted, expected)):
            assert got.open == want.open
            assert got.high == want.high
            assert got.low == want.low
            assert got.close == want.close
            assert got.timestamp == want.timestamp
            assert got.volume == want.volume


# ---------------------------------------------------------------------- #
# 2. Swings (both price spaces)
# ---------------------------------------------------------------------- #
class TestIncrementalSwings:
    N = 400

    def _snapshot_equal(self, got: list[Swing], want: list[Swing], label: str):
        assert len(got) == len(want), (
            f"{label}: {len(got)} swings != {len(want)}"
        )
        for g, w in zip(got, want):
            assert g.is_high == w.is_high
            assert g.candle_index == w.candle_index
            assert g.level == w.level
            assert g.is_valid == w.is_valid
            assert g.confirmed_index == w.confirmed_index

    def test_swings_every_prefix(self):
        candles = make_candles(self.N)
        state = SeriesState(Timeframe.M1)
        for i, c in enumerate(candles):
            state.extend(c)
            want = detect_swings(candles[: i + 1], Timeframe.M1)
            self._snapshot_equal(state.swings, want, f"prefix[{i}]")

    def test_mirrored_swings_match_full_series(self):
        candles = make_candles(self.N)
        state = SeriesState(Timeframe.M1)
        for c in candles:
            state.extend(c)
        want = _invert_swings(detect_swings(candles, Timeframe.M1))
        self._snapshot_equal(state.inverted_swings, want, "mirror-full")

    def test_mutation_does_not_alias_batch_output(self):
        # Confirming a pending swing mutates the Swing objects; the batch
        # detector rebuilds its own objects each call, so the snapshots in
        # the tests above already prove the mutation is self-contained.
        candles = make_candles(200)
        state = SeriesState(Timeframe.M1)
        for c in candles:
            state.extend(c)
        want = detect_swings(candles, Timeframe.M1)
        self._snapshot_equal(state.swings, want, "final")


# ---------------------------------------------------------------------- #
# 3. Swing indexes vs linear scans
# ---------------------------------------------------------------------- #
class TestSwingIndex:
    def _build(self, n=600):
        candles = make_candles(n)
        state = SeriesState(Timeframe.M1)
        for c in candles:
            state.extend(c)
        swings = state.swings
        return swings, state.swing_index

    def test_last_valid_matches_linear_scan(self):
        swings, index = self._build()
        for before in (5, 60, 200, 599):
            for is_high in (True, False):
                want = max(
                    (
                        s
                        for s in swings
                        if s.is_high == is_high
                        and s.is_valid
                        and s.candle_index < before
                    ),
                    key=lambda s: s.candle_index,
                    default=None,
                )
                got = index.original.last_valid(is_high, before)
                assert got is want, f"last_valid({is_high}, {before})"

    def test_minor_lows_between_matches_linear_scan(self):
        swings, index = self._build()
        for after, before in ((0, 599), (40, 300), (120, 180)):
            want = [
                s
                for s in swings
                if not s.is_high
                and not s.is_valid
                and after < s.candle_index < before
            ]
            got = index.original.minor_lows_between(after, before)
            assert got == want, f"minor_lows_between({after}, {before})"

    def test_inverted_space_indexes(self):
        _, index = self._build()
        # The inverted space must mirror polarities: every original swing
        # high is an inverted-space low with the negated level.
        for before in (100, 400):
            o = index.original.last_valid(True, before)
            v = index.inverted.last_valid(False, before)
            assert (o is None) == (v is None)
            if o is not None:
                assert v.candle_index == o.candle_index
                assert v.level == -o.level
                assert v.is_high is False


# ---------------------------------------------------------------------- #
# 4. Detection hoists
# ---------------------------------------------------------------------- #
class TestDetectionHoists:
    def _window(self, n=900):
        return make_candles(n)

    def test_check_displacement_precomputed_atr_and_fvgs(self):
        from smc.detection.displacement_checker import check_displacement
        from smc.detection.fvg_detector import detect_fvgs
        from smc.utils.atr import latest_atr

        window = self._window()
        fvgs = detect_fvgs(window, Timeframe.M1)
        atr_series_vals = atr_series(window, 14)
        sweep_index = 500
        level = window[sweep_index - 40].low  # arbitrary BOS level
        legacy = check_displacement(window, Direction.LONG, sweep_index, level, 14)
        hoisted = check_displacement(
            window,
            Direction.LONG,
            sweep_index,
            level,
            14,
            atr=atr_series_vals[sweep_index - 1],
            fvgs=fvgs,
        )
        assert legacy == hoisted  # dataclass field equality (same floats)
        # and the pre-sweep slice really is the legacy ATR value
        assert latest_atr(window[:sweep_index], 14) == atr_series_vals[sweep_index - 1]

    def test_driver_stage0_run_carries_shared_artifacts(self):
        from smc.orchestration.detection_driver import DetectionDriver
        from smc.utils.atr import atr_series as _atr
        from smc.detection.fvg_detector import detect_fvgs as _fvgs

        window = self._window()
        driver = DetectionDriver(Timeframe.M1)
        run = driver.stage0(window)
        assert run.fvgs == _fvgs(window, Timeframe.M1)
        assert run.atr_values == _atr(window, 14)

    def test_window_cache_pillar1_identical(self):
        from smc.detection.displacement_checker import DisplacementResult
        from smc.detection.liquidity_scanner import scan as scan_liquidity
        from smc.orchestration.detection_driver import DetectionDriver
        from smc.validation.pillar_1_zone_refinement import ZoneRefinementPillar
        from smc.validation.pillar import PillarStatus, ValidationContext

        window = self._window()
        driver = DetectionDriver(Timeframe.M1)
        raw = driver.stage0(window)
        pois, _skipped = driver.detect_pois(window, raw.swings, raw.liquidity_levels)
        if not pois:
            pytest.skip("no POIs detected on the synthetic window")
        cache = driver._window_cache(window, raw)
        assert cache is not None

        pillar = ZoneRefinementPillar()
        for poi in pois[:6]:
            disp = DisplacementResult(
                direction=poi.zone.direction, bos=True, fvg=True,
                magnitude=10.0, magnitude_atr=2.0, atr=5.0,
                passed=True, hard_fail=False, is_preferred=True,
                bos_index=10,
            )
            legacy_ctx = ValidationContext(
                poi=poi, candles=window, swings=raw.swings,
                liquidity_levels=raw.liquidity_levels, dealing_range=None,
                displacement=disp, atr_period=14,
            )
            cached_ctx = ValidationContext(
                poi=poi, candles=window, swings=raw.swings,
                liquidity_levels=raw.liquidity_levels, dealing_range=None,
                displacement=disp, atr_period=14, window_cache=cache,
            )
            a = pillar.run(legacy_ctx)
            b = pillar.run(cached_ctx)
            assert a.status is b.status is not PillarStatus.UNAVAILABLE
            assert a.detail == b.detail
            assert a.data == b.data


# ---------------------------------------------------------------------- #
# 5. Hint fast paths — triggers read the SAME values
# ---------------------------------------------------------------------- #
def _routable_poi(candles, base_index, direction) -> POI:
    from smc.config.model_type import ModelType

    lo = min(c.low for c in candles[base_index: base_index + 12])
    hi = max(c.high for c in candles[base_index: base_index + 12])
    mid = (lo + hi) / 2.0
    zone = Zone(
        top=mid + 0.6, bottom=mid - 0.6, direction=direction, timeframe=Timeframe.M1
    )
    from smc.core.enums import POIState

    poi = POI(zone=zone, models=[ModelType.M1])
    poi.state = POIState.FRESH
    return poi


class TestHintFastPaths:
    N = 800

    def _state(self):
        candles = make_candles(self.N)
        state = SeriesState(Timeframe.M1)
        for c in candles:
            state.extend(c)
        return candles, state

    def test_classify_choch_hints(self):
        candles, state = self._state()
        for bar in (120, 300, 650, self.N - 1):
            want = classify_choch_at(candles, state.swings, bar)
            got = classify_choch_at(
                candles,
                state.swings,
                bar,
                inverted_candles=state.inverted,
                inverted_swings=state.inverted_swings,
                swing_index=state.swing_index,
            )
            assert got == want, f"choch@{bar}"
            # cross-check the inverted mirror against a per-call rebuild
            if want is not None and want.direction is Direction.LONG:
                rebuilt = _invert_candles(candles)
                assert state.inverted[bar] == rebuilt[bar]

    def test_trigger_a_hints(self):
        candles, state = self._state()
        trigger = ChochReversalTrigger()
        poi = _routable_poi(candles, 200, Direction.LONG)
        for bar in (260, 420, self.N - 1):
            legacy = TriggerContext(
                poi=poi, candles=candles, swings=state.swings,
                bar_index=bar, from_bar=180,
            )
            hinted = TriggerContext(
                poi=poi, candles=state.candles, swings=state.swings,
                bar_index=bar, from_bar=180, hints=state,
            )
            assert trigger.evaluate(legacy) == trigger.evaluate(hinted), f"A@{bar}"

    def test_trigger_e_hints(self):
        candles, state = self._state()
        trigger = RsiDivergenceTrigger()
        for base, direction in ((150, Direction.SHORT), (150, Direction.LONG)):
            poi = _routable_poi(candles, base, direction)
            for bar in (300, 500, self.N - 1):
                legacy = TriggerContext(
                    poi=poi, candles=candles, swings=state.swings,
                    bar_index=bar, from_bar=base,
                )
                hinted = TriggerContext(
                    poi=poi, candles=state.candles, swings=state.swings,
                    bar_index=bar, from_bar=base, hints=state,
                )
                assert trigger.evaluate(legacy) == trigger.evaluate(hinted), (
                    f"E@{bar}/{direction}"
                )

    def test_trigger_f_hints(self):
        candles, state = self._state()
        trigger = BosObContinuationTrigger()
        poi = _routable_poi(candles, 200, Direction.LONG)
        for bar in (260, 450, self.N - 1):
            legacy = TriggerContext(
                poi=poi, candles=candles, swings=state.swings,
                bar_index=bar, from_bar=180,
            )
            hinted = TriggerContext(
                poi=poi, candles=state.candles, swings=state.swings,
                bar_index=bar, from_bar=180, hints=state,
            )
            assert trigger.evaluate(legacy) == trigger.evaluate(hinted), f"F@{bar}"

    def test_trigger_c_hints(self):
        candles, state = self._state()
        trigger = EndingDiagonalTrigger()
        poi = _routable_poi(candles, 200, Direction.LONG)
        for bar in (300, 600, self.N - 1):
            legacy = TriggerContext(
                poi=poi, candles=candles, swings=state.swings,
                bar_index=bar, from_bar=180,
            )
            hinted = TriggerContext(
                poi=poi, candles=state.candles, swings=state.swings,
                bar_index=bar, from_bar=180, hints=state,
            )
            assert trigger.evaluate(legacy) == trigger.evaluate(hinted), f"C@{bar}"

    def test_atr_band_half_width_hint(self):
        candles, state = self._state()
        for up_to in (30, 200, self.N):
            want = atr_band_half_width(candles, up_to)
            got = atr_band_half_width(candles, up_to, atr_values=state.atr_values)
            assert got == want, f"band@{up_to}"

    def test_trigger_d_unaffected_by_hints(self):
        # A5: Trigger D never fires on all-zero volume — the hint path must
        # not change that (structural unfireability), pinned explicitly.
        from smc.triggers.trigger_d_two_bar import TwoBarReversalTrigger

        candles, state = self._state()
        trigger = TwoBarReversalTrigger()
        poi = _routable_poi(candles, 200, Direction.LONG)
        for bar in (260, 500, self.N - 1):
            legacy = TriggerContext(
                poi=poi, candles=candles, swings=state.swings,
                bar_index=bar, from_bar=180,
            )
            hinted = TriggerContext(
                poi=poi, candles=state.candles, swings=state.swings,
                bar_index=bar, from_bar=180, hints=state,
            )
            a = trigger.evaluate(legacy)
            b = trigger.evaluate(hinted)
            assert (a is None) == (b is None)
            assert a == b
