"""Incremental full-prefix series state (Phase C perf patch — exact).

The backtest adapter used to rebuild O(prefix) artifacts inside per-bar /
per-evaluation code paths: ``latest_atr(candles[:i])`` per bar (runner),
``detect_swings(prefix)`` per scanning bar, per-trigger-evaluation RSI
series rebuilds, full-prefix candle/swing inversions (triggers A/E, the
CHOCH classifier) and O(S) linear swing scans (triggers A/E/F, the wave
extraction). At the 5-year scale (1.77M bars, ~336k swings) those terms
dominate the runtime.

:class:`SeriesState` maintains the SAME artifacts incrementally, one bar
at a time, with per-piece exact-equivalence arguments (collected in the
Phase C baseline report; summarized inline):

* **ATR / RSI (both price spaces)** — ``atr_series`` / ``rsi_series`` are
  Wilder folds whose seed and every RMA step read only bars at or before
  the evaluated bar, so the fold over the growing prefix reproduces
  ``atr_series(prefix)`` / ``rsi_series(prefix)`` value-for-value,
  including ``None`` warm-up placement and float addition order. The
  inverted-space RSI is produced from the SAME fold variables:
  negating closes swaps the gain/loss sequences, so by induction
  ``rsi_series(inverted_prefix)[i] == _value(avg_loss_i, avg_gain_i)``
  exactly (the inverted ATR equals the original because the true-range
  max reads the same three quantities).
* **Inverted candles** — the same per-candle construction
  ``choch_classifier._invert_candles`` performs, appended once per bar.
* **Swings** — a §27 N-bar-confirmed fractal candidate at index ``j``
  becomes decidable exactly when bar ``j + N`` exists; the batch detector
  scans ``j in [N, len - N - 1]``, so extending the series by one bar
  adds exactly the candidate ``j = len - 1 - N`` (all its comparison
  windows are final). Each candidate keeps the frozen §18 base-candle
  rule and starts §19-UNCONFIRMED; confirmation is the FIRST later body
  close beyond the base candle's opposite extreme — monotone
  (first-confirm never moves, validity never un-confirms) — so a
  threshold heap (max-heap on the opposite extreme for highs, min-heap
  for lows) pops each pending swing exactly once, at the identical bar
  the batch ``validate_swing`` scan confirms it.
* **Swing indexes** — :class:`SwingIndex` keeps base-sorted lists for the
  exact queries the consumers perform (last-N swings before a bar,
  §19-valid last swing, unconfirmed minors in an open interval, the
  base-sorted prefix slice). Ties keep creation order (``insort_right``),
  matching the stable sorts of the scans they replace.

Every read returns the values (and the same objects' fields) the replaced
recomputations produced; the October golden replay pins it byte-for-byte.
"""

from __future__ import annotations

import bisect
from heapq import heappop, heappush

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.swing import Swing
from smc.detection.base_candle import find_base_candle_index
from smc.detection.swing_validator import validate_swing
from smc.utils.rsi import DEFAULT_RSI_PERIOD
from smc.utils.rsi import _value as _rsi_value

__all__ = ["SeriesState", "SwingIndex"]


def _swing_key(swing: Swing) -> int:
    return swing.candle_index


class _SpaceIndex:
    """Base-sorted swing lookups for ONE price space (original or mirrored)."""

    __slots__ = (
        "all_highs", "all_lows", "valid_highs", "valid_lows",
        "minor_lows", "all_swings",
    )

    def __init__(self) -> None:
        self.all_highs: list[Swing] = []    # every swing high, base order
        self.all_lows: list[Swing] = []     # every swing low, base order
        self.valid_highs: list[Swing] = []  # §19-confirmed only
        self.valid_lows: list[Swing] = []
        self.minor_lows: list[Swing] = []   # §19-unconfirmed lows (CHOCH R2/3)
        self.all_swings: list[Swing] = []   # both polarities, base order

    # -- exact queries ------------------------------------------------- #
    def last_two(self, is_high: bool, before: int) -> tuple[Swing | None, Swing | None]:
        """The two most recent swings of one polarity strictly before a bar.

        Replaces ``sorted([s for s in swings if s.is_high and
        s.candle_index < bar])[-2:]`` (trigger E) — same selection, same
        order (``insort_right`` keeps creation order for equal bases,
        matching the stable sort of a creation-ordered list).
        """
        lst = self.all_highs if is_high else self.all_lows
        pos = bisect.bisect_left(lst, before, key=_swing_key)
        if pos >= 2:
            return lst[pos - 2], lst[pos - 1]
        if pos == 1:
            return None, lst[0]
        return None, None

    def last_valid(self, is_high: bool, before: int) -> Swing | None:
        """Most recent §19-valid swing of one polarity strictly before a bar.

        Replaces the ``max(candidates, key=candle_index)`` scans (trigger F,
        CHOCH ``_last_two``).
        """
        lst = self.valid_highs if is_high else self.valid_lows
        pos = bisect.bisect_left(lst, before, key=_swing_key)
        return lst[pos - 1] if pos > 0 else None

    def minor_lows_between(self, after: int, before: int) -> list[Swing]:
        """Unconfirmed swing lows with ``after < base < before`` (CHOCH R2/3)."""
        lo = bisect.bisect_right(self.minor_lows, after, key=_swing_key)
        hi = bisect.bisect_left(self.minor_lows, before, key=_swing_key)
        return self.minor_lows[lo:hi]

    def sorted_up_to(self, up_to: int) -> list[Swing]:
        """Base-sorted swings at/before a bar (wave-structure chain input).

        Replaces ``_sorted_swings``' filter + sort — the list is kept
        base-sorted with creation-order ties, exactly the stable sort's
        output, so the slice IS the sorted result.
        """
        pos = bisect.bisect_right(self.all_swings, up_to, key=_swing_key)
        return self.all_swings[:pos]


class SwingIndex:
    """Exact swing lookups in BOTH price spaces over the growing prefix.

    ``original`` indexes the §27 swings as detected; ``inverted`` indexes
    their price-mirrored counterparts (high↔low, level negated — the
    objects the CHOCH classifier / trigger E build per evaluation today).
    Consumers read only polarity/level/base/validity fields, which the
    mirrored copies carry identically.
    """

    __slots__ = ("original", "inverted")

    def __init__(self) -> None:
        self.original = _SpaceIndex()
        self.inverted = _SpaceIndex()

    def add(self, swing: Swing, mirrored: Swing) -> None:
        """Register a newly detected candidate in both spaces.

        Most candidates arrive §19-unconfirmed (the confirm may still lie
        ahead); a candidate whose §19 confirm already happened between its
        base candle and its right-window completion arrives VALID (batch
        ``validate_swing`` scans from ``base_index + 1``) and goes straight
        into the valid lists — never into ``minor_lows``.
        """
        o, v = self.original, self.inverted
        if swing.is_high:
            bisect.insort(o.all_highs, swing, key=_swing_key)
            if swing.is_valid:
                bisect.insort(o.valid_highs, swing, key=_swing_key)
        else:
            bisect.insort(o.all_lows, swing, key=_swing_key)
            if swing.is_valid:
                bisect.insort(o.valid_lows, swing, key=_swing_key)
            else:
                bisect.insort(o.minor_lows, swing, key=_swing_key)
        bisect.insort(o.all_swings, swing, key=_swing_key)
        # The mirror flips polarity: an original high is an inverted-space low.
        if mirrored.is_high:
            bisect.insort(v.all_highs, mirrored, key=_swing_key)
            if mirrored.is_valid:
                bisect.insort(v.valid_highs, mirrored, key=_swing_key)
        else:
            bisect.insort(v.all_lows, mirrored, key=_swing_key)
            if mirrored.is_valid:
                bisect.insort(v.valid_lows, mirrored, key=_swing_key)
            else:
                bisect.insort(v.minor_lows, mirrored, key=_swing_key)
        bisect.insort(v.all_swings, mirrored, key=_swing_key)

    def confirm(self, swing: Swing, mirrored: Swing) -> None:
        """Apply the §19 first-confirm event in both spaces (monotone)."""
        o, v = self.original, self.inverted
        if swing.is_high:
            bisect.insort(o.valid_highs, swing, key=_swing_key)
        else:
            bisect.insort(o.valid_lows, swing, key=_swing_key)
            o.minor_lows.remove(swing)
        if mirrored.is_high:
            bisect.insort(v.valid_highs, mirrored, key=_swing_key)
        else:
            bisect.insort(v.valid_lows, mirrored, key=_swing_key)
            v.minor_lows.remove(mirrored)


class SeriesState:
    """One bar at a time, everything the per-bar pipeline reads — exactly.

    Fed by :meth:`extend` in bar order; reads mirror the artifacts the
    per-evaluation recomputations produced (see module docstring for the
    per-piece equivalence arguments).
    """

    __slots__ = (
        "timeframe", "atr_period", "rsi_period",
        "candles", "atr_values", "rsi_values", "rsi_values_inverted",
        "inverted", "swings", "inverted_swings", "swing_index",
        "_trs", "_atr_current",
        "_gains", "_losses", "_avg_gain", "_avg_loss",
        "_window", "_pending_highs", "_pending_lows", "_seq",
    )

    def __init__(self, timeframe: Timeframe, atr_period: int = 14) -> None:
        self.timeframe = timeframe
        self.atr_period = atr_period
        self.rsi_period = DEFAULT_RSI_PERIOD  # trigger E calls rsi_series with the default
        self.candles: list[Candle] = []
        self.atr_values: list[float | None] = []
        self.rsi_values: list[float | None] = []
        self.rsi_values_inverted: list[float | None] = []
        self.inverted: list[Candle] = []
        self.swings: list[Swing] = []
        self.inverted_swings: list[Swing] = []
        self.swing_index = SwingIndex()
        self._trs: list[float] = []
        self._atr_current: float | None = None
        self._gains: list[float] = []
        self._losses: list[float] = []
        self._avg_gain: float | None = None
        self._avg_loss: float | None = None
        self._window = Timeframe.n_bar_confirmation(timeframe)
        # §19 pendings: (threshold, seq, swing, mirrored). Highs confirm on a
        # close BELOW the base low (max-heap on the threshold), lows on a
        # close ABOVE the base high (min-heap) — each pops exactly once.
        self._pending_highs: list[tuple[float, int, Swing, Swing]] = []
        self._pending_lows: list[tuple[float, int, Swing, Swing]] = []
        self._seq = 0

    # ------------------------------------------------------------------ #
    def extend(self, candle: Candle) -> None:
        """Fold one bar in (bar order, no gaps — the runner drives it)."""
        i = len(self.candles)
        prev = self.candles[i - 1] if i else None
        self.candles.append(candle)
        self.inverted.append(
            Candle(
                timestamp=candle.timestamp,
                open=-candle.open,
                high=-candle.low,
                low=-candle.high,
                close=-candle.close,
                volume=candle.volume,
                timeframe=candle.timeframe,
            )
        )
        self._extend_atr(candle, prev)
        self._extend_rsi(candle, prev)
        j = i - self._window
        if j >= self._window:
            self._evaluate_candidate(j)
        self._apply_confirms(candle.close)

    # -- indicators ----------------------------------------------------- #
    def _extend_atr(self, candle: Candle, prev: Candle | None) -> None:
        """Exact step-replica of ``atr_series`` (Wilder RMA, MT5 iATR)."""
        if prev is None:
            tr = candle.high - candle.low
        else:
            tr = max(
                candle.high - candle.low,
                abs(candle.high - prev.close),
                abs(candle.low - prev.close),
            )
        self._trs.append(tr)
        period = self.atr_period
        if len(self.candles) < period:
            self.atr_values.append(None)
        elif len(self.candles) == period:
            # Seed: simple average of the first `period` true ranges.
            self._atr_current = sum(self._trs) / period
            self.atr_values.append(self._atr_current)
        else:
            self._atr_current = (self._atr_current * (period - 1) + tr) / period
            self.atr_values.append(self._atr_current)

    def _extend_rsi(self, candle: Candle, prev: Candle | None) -> None:
        """Exact step-replica of ``rsi_series`` in BOTH price spaces.

        The inverted-space value is produced from the same fold variables
        (negating closes swaps the gain/loss sequences — see module doc).
        """
        if prev is None:
            self.rsi_values.append(None)
            self.rsi_values_inverted.append(None)
            return
        change = candle.close - prev.close
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        self._gains.append(gain)
        self._losses.append(loss)
        period = self.rsi_period
        n_changes = len(self._gains)  # == current candle index
        if n_changes < period:
            self.rsi_values.append(None)
            self.rsi_values_inverted.append(None)
        elif n_changes == period:
            self._avg_gain = sum(self._gains) / period
            self._avg_loss = sum(self._losses) / period
            self.rsi_values.append(_rsi_value(self._avg_gain, self._avg_loss))
            self.rsi_values_inverted.append(_rsi_value(self._avg_loss, self._avg_gain))
        else:
            self._avg_gain = (self._avg_gain * (period - 1) + gain) / period
            self._avg_loss = (self._avg_loss * (period - 1) + loss) / period
            self.rsi_values.append(_rsi_value(self._avg_gain, self._avg_loss))
            self.rsi_values_inverted.append(_rsi_value(self._avg_loss, self._avg_gain))

    # -- swings --------------------------------------------------------- #
    def _evaluate_candidate(self, j: int) -> None:
        """The ONE §27 candidate the batch detector would add at this length.

        The right window ``[j+1, j+N]`` has just become complete (its last
        bar is the one being extended), and every earlier candidate was
        evaluated when its own right window completed — so the incremental
        candidate set equals the batch scan's, in the same order.
        """
        candles = self.candles
        w = self._window
        candle = candles[j]
        left_highs = [c.high for c in candles[j - w : j]]
        right_highs = [c.high for c in candles[j + 1 : j + w + 1]]
        left_lows = [c.low for c in candles[j - w : j]]
        right_lows = [c.low for c in candles[j + 1 : j + w + 1]]
        is_swing_high = candle.high > max(left_highs) and candle.high >= max(right_highs)
        is_swing_low = candle.low < min(left_lows) and candle.low <= min(right_lows)
        for is_high in (True, False):
            if is_high and not is_swing_high:
                continue
            if not is_high and not is_swing_low:
                continue
            base_index = find_base_candle_index(candles, j, is_high)
            level = candle.high if is_high else candle.low
            # §19 validation over the history AVAILABLE NOW — exactly the
            # batch call at this prefix length. The confirm may already have
            # happened between the base candle and this evaluation bar (the
            # batch scan starts at base_index + 1, which can precede the
            # candidate's N-bar right-window completion); later confirms are
            # the heap's monotone first-confirm events.
            validation = validate_swing(candles, base_index, is_high)
            swing = Swing(
                is_high=is_high,
                level=level,
                candle_index=base_index,
                base_candle=candles[base_index],
                timeframe=self.timeframe,
                is_valid=validation.is_valid,
                confirmed_index=validation.confirm_index,
            )
            mirrored = Swing(
                is_high=not is_high,
                level=-level,
                candle_index=base_index,
                base_candle=self.inverted[base_index],
                timeframe=self.timeframe,
                is_valid=validation.is_valid,
                confirmed_index=validation.confirm_index,
            )
            self.swings.append(swing)
            self.inverted_swings.append(mirrored)
            self.swing_index.add(swing, mirrored)
            self._seq += 1
            if swing.is_valid:
                continue  # already §19-confirmed — nothing pending
            if is_high:
                # Confirm when close < base.low → max-heap pops the largest first.
                heappush(self._pending_highs,
                         (-candles[base_index].low, self._seq, swing, mirrored))
            else:
                # Confirm when close > base.high → min-heap pops the smallest first.
                heappush(self._pending_lows,
                         (candles[base_index].high, self._seq, swing, mirrored))

    def _apply_confirms(self, close: float) -> None:
        """First §19 confirm event per pending (monotone — batch-equal).

        Batch ``validate_swing`` confirms a swing high at the FIRST close
        below its base low (and a low at the first close above its base
        high); the threshold heaps pop exactly those pendings at exactly
        that bar. ``seq`` keeps heap ties in creation order.
        """
        while self._pending_highs and -self._pending_highs[0][0] > close:
            _x, _s, swing, mirrored = heappop(self._pending_highs)
            swing.is_valid = True
            swing.confirmed_index = len(self.candles) - 1
            mirrored.is_valid = True
            mirrored.confirmed_index = swing.confirmed_index
            self.swing_index.confirm(swing, mirrored)
        while self._pending_lows and self._pending_lows[0][0] < close:
            _x, _s, swing, mirrored = heappop(self._pending_lows)
            swing.is_valid = True
            swing.confirmed_index = len(self.candles) - 1
            mirrored.is_valid = True
            mirrored.confirmed_index = swing.confirmed_index
            self.swing_index.confirm(swing, mirrored)
