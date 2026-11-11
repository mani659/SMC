"""Sweep attribution over the P2 liquidity pool (P2b).

Reuses ``smc.detection.sweep_detector.detect_sweep`` — there is no second
sweep definition. The single difference from the Stage-0 path is the scan
bound: a pool level is knowable only from ``enter_at``, so the scan starts at
the first bar whose timestamp is ``>= enter_at``.

Why that matters (the lookahead trap): ``LiquidityLevel.formed_at`` is the
*extreme bar*. For PDH/PDL that bar sits inside the prior completed day, and
for structural swings it is the base candle that precedes §19 confirmation.
Scanning from ``formed_at`` therefore lets a bar that traded *before* the
level was knowable register as its sweep. This module never passes
``formed_at`` to the detector: the adapter level carries ``formed_at=None``
and the explicit ``start_index`` is the only bound.

No ranking, no winner selection, no wiring into live/paper/triggers/risk.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from smc.core.enums import LiquidityType, PoolType
from smc.core.liquidity_level import LiquidityLevel
from smc.detection.sweep_detector import detect_sweep
from smc.liquidity.pool import PoolFamily, PoolLevel, PoolLevelId, PoolSide

__all__ = [
    "AttributionReport",
    "SweepHit",
    "attribute_sweeps",
    "resolve_start_index",
    "sweeps_on_bar",
]

_LIQUIDITY_TYPE: dict[PoolFamily, LiquidityType] = {
    PoolFamily.PREVIOUS_DAY: LiquidityType.PREVIOUS_DAY,
    PoolFamily.PREVIOUS_WEEK: LiquidityType.PREVIOUS_WEEK,
    PoolFamily.SESSION: LiquidityType.SESSION,
    PoolFamily.STRUCTURAL_SWING: LiquidityType.STRUCTURAL_SWING,
}

_POOL_TYPE: dict[PoolSide, PoolType] = {
    PoolSide.BSL: PoolType.BSL,
    PoolSide.SSL: PoolType.SSL,
}


@dataclass(frozen=True, slots=True)
class SweepHit:
    """One pool level swept by one bar. Identity is the pool ``level_id``."""

    family: str
    side: str
    period_id: str
    price: float
    sweep_bar_ts: datetime
    sweep_bar_index: int
    direction: str          # "long" after an SSL sweep, "short" after a BSL sweep
    enter_at: datetime
    start_index_used: int

    @property
    def level_id(self) -> PoolLevelId:
        return (self.family, self.side, self.period_id)


@dataclass(frozen=True, slots=True)
class AttributionReport:
    """Hits plus the levels that could never be scanned in this series."""

    hits: tuple[SweepHit, ...]
    not_applicable: tuple[PoolLevelId, ...]


def _assert_ascending(series: list) -> None:
    """Fail closed on unordered input (never silently reorder a series)."""
    previous = None
    for index, bar in enumerate(series):
        if previous is not None and bar.timestamp <= previous:
            raise ValueError(
                "sweep-attribution series must be strictly ascending; "
                f"disorder at index {index} ({bar.timestamp!r})"
            )
        previous = bar.timestamp


def resolve_start_index(series: list, enter_at: datetime) -> int | None:
    """First bar index with ``timestamp >= enter_at``; ``None`` after series end."""
    if not series:
        raise ValueError("cannot resolve a start index on an empty series")
    _assert_ascending(series)
    for index, bar in enumerate(series):
        if bar.timestamp >= enter_at:
            return index
    return None


def _adapter(level: PoolLevel) -> LiquidityLevel:
    """Detector-facing level carrying NO ``formed_at`` (bounds come from us)."""
    return LiquidityLevel(
        type=_LIQUIDITY_TYPE[level.family],
        level=level.price,
        pool=_POOL_TYPE[level.side],
        timeframe=level.source_tf,
        formed_at=None,
    )


def attribute_sweeps(
    pool,
    series: list,
    *,
    levels: list[PoolLevel] | None = None,
) -> AttributionReport:
    """First sweep of each level, scanning only from ``enter_at`` onward.

    ``series`` must be the series that ``level.source_tf`` refers to (the
    caller groups levels by timeframe). All hits are returned; when several
    levels are swept by the same bar, every hit is emitted — this function
    never picks a winner, because that is a ranking decision that is not
    frozen.
    """
    _assert_ascending(series)
    selected = pool.all_levels() if levels is None else list(levels)

    hits: list[SweepHit] = []
    not_applicable: list[PoolLevelId] = []

    for level in selected:
        start = resolve_start_index(series, level.enter_at)
        if start is None:
            # enter_at is after the series: no sweep can be observed here.
            not_applicable.append(level.level_id)
            continue
        result = detect_sweep(series, _adapter(level), start_index=start)
        if result is None:
            continue
        hit_ts = result.candle.timestamp
        if not level.is_active_at(hit_ts):
            # Level already superseded/expired when the bar printed.
            continue
        hits.append(
            SweepHit(
                family=level.family.value,
                side=level.side.value,
                period_id=level.period_id,
                price=level.price,
                sweep_bar_ts=hit_ts,
                sweep_bar_index=result.candle_index,
                direction="long" if level.side is PoolSide.SSL else "short",
                enter_at=level.enter_at,
                start_index_used=start,
            )
        )

    hits.sort(
        key=lambda h: (
            h.sweep_bar_index,
            h.sweep_bar_ts,
            h.family,
            h.side,
            h.period_id,
        )
    )
    return AttributionReport(hits=tuple(hits), not_applicable=tuple(not_applicable))


def sweeps_on_bar(pool, series: list, bar_index: int) -> list[SweepHit]:
    """All pool levels swept by one specific bar (active at that bar only)."""
    _assert_ascending(series)
    if not 0 <= bar_index < len(series):
        raise IndexError(f"bar_index {bar_index} out of range")
    bar = series[bar_index]
    hits: list[SweepHit] = []
    for level in pool.active_asof(bar.timestamp):
        wick_beyond = (
            bar.high > level.price if level.side is PoolSide.BSL else bar.low < level.price
        )
        close_back = (
            bar.close < level.price if level.side is PoolSide.BSL else bar.close > level.price
        )
        if wick_beyond and close_back:
            hits.append(
                SweepHit(
                    family=level.family.value,
                    side=level.side.value,
                    period_id=level.period_id,
                    price=level.price,
                    sweep_bar_ts=bar.timestamp,
                    sweep_bar_index=bar_index,
                    direction="long" if level.side is PoolSide.SSL else "short",
                    enter_at=level.enter_at,
                    start_index_used=resolve_start_index(series, level.enter_at) or 0,
                )
            )
    hits.sort(key=lambda h: (h.family, h.side, h.period_id))
    return hits
