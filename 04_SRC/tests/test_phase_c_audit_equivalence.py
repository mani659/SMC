"""INDEPENDENT AUDIT — Phase C equivalence under fresh seeds + extremes.

The standing suite (``test_series_state_equivalence``) pins the Phase C
incremental state against the batch originals on ONE fixed seed. This
audit file re-derives every pinned identity on NEW deterministic inputs
(different seeds, extreme price regimes) so a seed-specific accident
cannot pass the net. All comparisons are EXACT (bit-identity, list
isomorphism), never approximate:

1. Indicator folds (ATR + RSI both price spaces) vs ``atr_series`` /
   ``rsi_series`` — every prefix element, None placement included.
2. §27/§19 swings vs ``detect_swings`` at checkpoints — full dataclass
   equality (is_valid / confirmed_index / level / base).
3. ``SwingIndex`` queries vs the linear scans they replace — last_valid,
   last_two (trigger E selection), minor_lows_between (CHOCH R2/3),
   sorted_up_to (wave chains).
4. Mirror isomorphism — inverted candles/swings/RSI equal the explicit
   per-object inversion the CHOCH classifier / trigger E perform.
5. Extreme regimes — huge jumps, one-tick series, flat stretches: folds
   must still match exactly and stay finite where the batch is finite.
"""

from __future__ import annotations

import math
import random

import pytest

from smc.backtest.series_state import SeriesState
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.detection.structural_swing_detector import detect_swings
from smc.utils.atr import atr_series
from smc.utils.rsi import rsi_series

TF = Timeframe.M1
AUDIT_SEEDS = (7, 123_456, 987_654_321)
EXTREME_SEEDS = (31,)


def _gen(n: int, seed: int, *, spikes: bool = False) -> list[Candle]:
    """Deterministic M1-like random walk (ints — realistic price grid)."""
    rng = random.Random(seed)
    base = 10_000.0
    out: list[Candle] = []
    from datetime import datetime, timedelta, timezone

    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    price = base
    for i in range(n):
        step = rng.randint(-8, 8)
        if spikes and rng.random() < 0.03:
            step += rng.choice([-60, 60])
        if spikes and rng.random() < 0.02:
            step = 0  # flat stretch
        price += step
        spread = rng.randint(1, 12)
        high = price + spread
        low = price - rng.randint(1, 12)
        out.append(
            Candle(
                timestamp=t0 + timedelta(minutes=i),
                open=price - rng.randint(0, 3),
                high=high,
                low=low,
                close=price,
                volume=float(rng.randint(0, 5_000)),
                timeframe=TF,
            )
        )
    return out


def _feed(candles: list[Candle]) -> SeriesState:
    state = SeriesState(TF, atr_period=14)
    for candle in candles:
        state.extend(candle)
    return state


def _assert_series_exact(got: list, want: list, label: str) -> None:
    assert len(got) == len(want), f"{label}: length {len(got)} != {len(want)}"
    for i, (g, w) in enumerate(zip(got, want)):
        if w is None:
            assert g is None, f"{label}[{i}]: {g} != None"
        else:
            assert g is not None and g == w, f"{label}[{i}]: {g} != {w}"


# ---------------------------------------------------------------------- #
# 1. Folds on fresh seeds
# ---------------------------------------------------------------------- #
@pytest.mark.parametrize("seed", AUDIT_SEEDS)
def test_folds_exact_fresh_seeds(seed: int) -> None:
    candles = _gen(600, seed)
    state = _feed(candles)
    _assert_series_exact(state.atr_values, atr_series(candles, 14), f"atr[{seed}]")
    _assert_series_exact(state.rsi_values, rsi_series(candles, 14), f"rsi[{seed}]")
    inverted = [
        Candle(
            timestamp=c.timestamp,
            open=-c.open,
            high=-c.low,
            low=-c.high,
            close=-c.close,
            volume=c.volume,
            timeframe=c.timeframe,
        )
        for c in candles
    ]
    _assert_series_exact(
        state.rsi_values_inverted, rsi_series(inverted, 14), f"rsi_inv[{seed}]"
    )


# ---------------------------------------------------------------------- #
# 2. Swings vs batch at checkpoints (fresh seeds)
# ---------------------------------------------------------------------- #
@pytest.mark.parametrize("seed", AUDIT_SEEDS)
def test_swings_checkpoint_isomorphism_fresh_seeds(seed: int) -> None:
    candles = _gen(650, seed)
    state = SeriesState(TF, atr_period=14)
    checkpoints = set(range(80, 651, 97))
    for i, candle in enumerate(candles, start=1):
        state.extend(candle)
        if i in checkpoints:
            batch = detect_swings(candles[:i], TF)
            assert len(state.swings) == len(batch), (
                f"seed {seed} bar {i}: {len(state.swings)} vs batch {len(batch)}"
            )
            for a, b in zip(state.swings, batch):
                assert a == b, f"seed {seed} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------- #
# 3. SwingIndex queries vs the linear scans
# ---------------------------------------------------------------------- #
def _linear_last_valid(swings, is_high, before):
    cands = [
        s for s in swings if s.is_high is is_high and s.is_valid and s.candle_index < before
    ]
    return max(cands, key=lambda s: s.candle_index) if cands else None


def _linear_last_two(swings, is_high, before):
    sel = sorted(
        (s for s in swings if s.is_high is is_high and s.candle_index < before),
        key=lambda s: s.candle_index,
    )
    return (sel[-2] if len(sel) >= 2 else None, sel[-1] if sel else None)


def _linear_minor_lows(swings, after, before):
    return [
        s
        for s in swings
        if not s.is_high and not s.is_valid and after < s.candle_index < before
    ]


@pytest.mark.parametrize("seed", AUDIT_SEEDS)
def test_swing_index_queries_fresh_seeds(seed: int) -> None:
    candles = _gen(700, seed)
    state = SeriesState(TF, atr_period=14)
    idx = state.swing_index.original
    for i, candle in enumerate(candles, start=1):
        state.extend(candle)
        if i % 53 != 0:
            continue
        prefix = state.swings
        for bar in (i - 1, i // 2, 1):
            assert idx.last_valid(True, bar) == _linear_last_valid(prefix, True, bar)
            assert idx.last_valid(False, bar) == _linear_last_valid(prefix, False, bar)
            assert idx.last_two(True, bar) == _linear_last_two(prefix, True, bar)
            assert idx.last_two(False, bar) == _linear_last_two(prefix, False, bar)
            assert idx.minor_lows_between(bar // 3, bar) == _linear_minor_lows(
                prefix, bar // 3, bar
            )
            up_to = i // 4
            want = sorted(
                (s for s in prefix if s.candle_index <= up_to),
                key=lambda s: s.candle_index,
            )
            assert idx.sorted_up_to(up_to) == want


# ---------------------------------------------------------------------- #
# 4. Mirror isomorphism (classifier's explicit inversion)
# ---------------------------------------------------------------------- #
@pytest.mark.parametrize("seed", AUDIT_SEEDS)
def test_mirror_isomorphism_fresh_seeds(seed: int) -> None:
    candles = _gen(400, seed)
    state = _feed(candles)
    inv_idx = state.swing_index.inverted
    for bar in (100, 250, 400):
        # Inverted-space highs ARE the original-space lows (level negated).
        inv_high = inv_idx.last_valid(True, bar)
        orig_low = state.swing_index.original.last_valid(False, bar)
        if orig_low is None:
            assert inv_high is None
        else:
            assert inv_high is not None
            assert inv_high.candle_index == orig_low.candle_index
            assert inv_high.level == -orig_low.level
            assert inv_high.is_valid == orig_low.is_valid
        # Mirrored candle list equals the classifier's construction.
        assert len(state.inverted) == len(candles)
        c = candles[bar - 1]
        m = state.inverted[bar - 1]
        assert (m.open, m.high, m.low, m.close) == (-c.open, -c.low, -c.high, -c.close)


# ---------------------------------------------------------------------- #
# 5. Extreme regimes
# ---------------------------------------------------------------------- #
@pytest.mark.parametrize("seed", EXTREME_SEEDS)
def test_extreme_regimes_exact(seed: int) -> None:
    candles = _gen(500, seed, spikes=True)
    state = _feed(candles)
    _assert_series_exact(state.atr_values, atr_series(candles, 14), "atr/extreme")
    _assert_series_exact(state.rsi_values, rsi_series(candles, 14), "rsi/extreme")
    batch = detect_swings(candles, TF)
    assert [s for s in state.swings] == batch
    for v in state.atr_values:
        if v is not None:
            assert not math.isnan(v) and not math.isinf(v)


def test_one_tick_series_folds() -> None:
    """A perfectly flat series: every fold step is degenerate but exact."""
    from datetime import datetime, timedelta, timezone

    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    candles = [
        Candle(
            timestamp=t0 + timedelta(minutes=i),
            open=100.0,
            high=100.0,
            low=100.0,
            close=100.0,
            volume=0.0,
            timeframe=TF,
        )
        for i in range(120)
    ]
    state = _feed(candles)
    _assert_series_exact(state.atr_values, atr_series(candles, 14), "atr/flat")
    _assert_series_exact(state.rsi_values, rsi_series(candles, 14), "rsi/flat")
    assert state.atr_values[-1] == pytest.approx(0.0, abs=1e-12)
