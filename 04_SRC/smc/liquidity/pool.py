"""Liquidity pool types + in-memory registry (P2a).

Design lock: ``06_RESEARCH/P2_LIQUIDITY_POOL_DESIGN.md`` (accepted with
amendments R1–R5, 2026-11-11).

Membership (R-EQH-C excludes equal highs/lows):

    previous day high/low, previous week high/low,
    session high/low (Asia / London / NY), structural swing high/low.

Identity is ``level_id = (family, side, period_id)`` — price is an attribute,
never part of the key, so no price-quantum bucketing is invented here.

Lifecycle (amendment R2, implemented without new numeric constants):

    enter_at is family specific (next UTC midnight, next Monday 00:00,
    session close, or the §19 confirmation bar close);
    exit_at is derived purely by supersession — a level exits when the next
    level of the same ``(family, side, source_tf)`` enters.

Consequences of the supersession rule, stated explicitly:

* a Friday PDH/PDL pair stays active across the weekend and exits when the
  next pair (from the following trading day) enters on Tuesday 00:00 UTC,
  which preserves the production "Monday sees Friday's levels" behaviour;
* session levels exit at the next same-session print (the R2 "replaced by
  next same-session print" reading; the alternative "end of session day"
  reading is recorded as a P2b residual instead of being mixed in here);
* structural levels exit on supersession only. Exiting on "broken" requires
  a break definition that is not locked, so it is a P2b residual (R2).

No wall clock: every entry point takes an explicit ``asof``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from enum import Enum

from smc.config.locked_constants import (
    ASIA_END_HOUR_UTC,
    LONDON_END_HOUR_UTC,
    NY_END_HOUR_UTC,
)
from smc.config.timeframe import Timeframe
from smc.core.enums import LiquidityType, PoolType
from smc.core.liquidity_level import LiquidityLevel
from smc.core.swing import Swing

__all__ = [
    "POOL_FAMILIES",
    "LiquidityPool",
    "PoolFamily",
    "PoolLevel",
    "PoolLevelId",
    "PoolSide",
    "PoolStatus",
    "from_pdh_pdl",
    "from_pwh_pwl",
    "from_session",
    "from_structural",
    "inventory_sort_key",
]


class PoolFamily(str, Enum):
    """Families admitted to the P2 pool (R-EQH-C)."""

    PREVIOUS_DAY = "previous_day"
    PREVIOUS_WEEK = "previous_week"
    SESSION = "session"
    STRUCTURAL_SWING = "structural_swing"


class PoolSide(str, Enum):
    """Directional pool side (§2 BSL/SSL)."""

    BSL = "bsl"
    SSL = "ssl"


class PoolStatus(str, Enum):
    """Stored lifecycle marker; ``active_asof`` recomputes from timestamps."""

    ACTIVE = "active"
    EXITED = "exited"


#: Tuple form for reporting/tests.
POOL_FAMILIES: tuple[PoolFamily, ...] = (
    PoolFamily.PREVIOUS_DAY,
    PoolFamily.PREVIOUS_WEEK,
    PoolFamily.SESSION,
    PoolFamily.STRUCTURAL_SWING,
)

#: Soft report ordering (amendment R3). Logging/inventory only — never a
#: trading priority and never consulted by ``active_asof``.
_SOFT_REPORT_ORDER: dict[PoolFamily, int] = {
    PoolFamily.PREVIOUS_WEEK: 0,
    PoolFamily.PREVIOUS_DAY: 1,
    PoolFamily.SESSION: 2,
    PoolFamily.STRUCTURAL_SWING: 3,
}

PoolLevelId = tuple[str, str, str]


def _utc(value: datetime) -> datetime:
    """Normalize to UTC; naive values are assumed UTC (data boundary rule)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _pool_side(pool: PoolType) -> PoolSide:
    if pool is PoolType.BSL:
        return PoolSide.BSL
    if pool is PoolType.SSL:
        return PoolSide.SSL
    raise ValueError(f"unsupported pool side for the liquidity pool: {pool!r}")


_SESSION_END_HOUR = {
    "ASIA": ASIA_END_HOUR_UTC,
    "LONDON": LONDON_END_HOUR_UTC,
    "NEW_YORK": NY_END_HOUR_UTC,
}


@dataclass(frozen=True, slots=True)
class PoolLevel:
    """One pool level. ``price`` is an attribute of ``level_id``, not part of it.

    ``exit_at is None`` means "still the newest level of its series" — it is
    not an unbounded promise (a successor may be added later).
    """

    family: PoolFamily
    side: PoolSide
    price: float
    period_id: str
    source_tf: Timeframe
    formed_at: datetime | None
    enter_at: datetime
    exit_at: datetime | None = None
    status: PoolStatus = PoolStatus.ACTIVE

    def __post_init__(self) -> None:
        if not isinstance(self.family, PoolFamily):
            raise ValueError(f"family must be a PoolFamily member: {self.family!r}")
        if not isinstance(self.side, PoolSide):
            raise ValueError(f"side must be a PoolSide member: {self.side!r}")
        if not self.period_id:
            raise ValueError("period_id is required for pool identity")
        if self.enter_at.tzinfo is None:
            raise ValueError("enter_at must be timezone-aware (UTC)")
        if self.exit_at is not None:
            if self.exit_at.tzinfo is None:
                raise ValueError("exit_at must be timezone-aware (UTC)")
            if self.exit_at <= self.enter_at:
                raise ValueError("exit_at must be after enter_at")

    @property
    def level_id(self) -> PoolLevelId:
        return (self.family.value, self.side.value, self.period_id)

    def is_active_at(self, asof: datetime) -> bool:
        instant = _utc(asof)
        if instant < self.enter_at:
            return False
        if self.exit_at is not None and instant >= self.exit_at:
            return False
        return True


def _series_key(level: PoolLevel) -> tuple:
    """Series a level belongs to; only the newest member stays active.

    Session levels of different sessions coexist on the same day, so the
    session name (the ``period_id`` suffix) is part of the series key. All
    other families form one series per ``(family, side, source_tf)``.
    """
    if level.family is PoolFamily.SESSION:
        return (level.family, level.side, level.source_tf, level.period_id.rsplit("_", 1)[-1])
    return (level.family, level.side, level.source_tf)


def inventory_sort_key(level: PoolLevel) -> tuple:
    """Soft report sort (R3): PWH/PWL, PDH/PDL, Session, Structural.

    This exists so inventory CSVs read predictably. It is explicitly *not* a
    ranking, a score, or a trading priority.
    """
    return (
        _SOFT_REPORT_ORDER[level.family],
        level.period_id,
        level.side.value,
        -level.price,
        level.source_tf.name,
    )


class LiquidityPool:
    """In-memory pool. Add-only; lifecycle is derived, never guessed."""

    def __init__(self) -> None:
        self._levels: dict[PoolLevelId, PoolLevel] = {}

    # ------------------------------------------------------------------ #
    # membership
    # ------------------------------------------------------------------ #
    def add(self, level: PoolLevel) -> PoolLevel:
        """Add one level, applying supersession to its predecessor.

        Requirements: ``level.enter_at`` must be strictly newer than the
        current level of the same ``(family, side, source_tf)`` series, so a
        caller cannot silently reorder history.
        """
        key = level.level_id
        if key in self._levels:
            raise ValueError(f"duplicate pool level_id: {key}")

        stored = self._levels.get(key)
        if stored is not None:  # defensive: dict lookup already guards this
            raise ValueError(f"duplicate pool level_id: {key}")

        previous = self._current_for(_series_key(level))
        if previous is not None:
            if level.enter_at < previous.enter_at:
                raise ValueError(
                    "pool levels must be added chronologically: "
                    f"{key} enter_at {level.enter_at.isoformat()} precedes "
                    f"{previous.level_id} enter_at {previous.enter_at.isoformat()}"
                )
            if level.enter_at > previous.enter_at:
                # Status stays ACTIVE here: EXITED is time-derived by
                # ``apply_lifecycle`` so the stored marker never runs ahead
                # of the clock.
                self._levels[previous.level_id] = replace(
                    previous, exit_at=level.enter_at
                )
            # Equal enter_at: two swings confirmed on the same bar. Neither
            # supersedes the other (a zero-length exit is not a lifecycle),
            # so both stay active from that instant.

        self._levels[key] = level
        return level

    def add_detected(
        self,
        level: LiquidityLevel,
        *,
        source_tf: Timeframe,
        period_id: str,
    ) -> PoolLevel:
        """Hard-reject non-members (R-EQH-C) before they reach the registry."""
        if level.type is LiquidityType.EQUAL_HIGHS_LOWS:
            raise ValueError(
                "EQH/EQL is not a pool member (R-EQH-C); research export only"
            )
        raise ValueError(
            "use the typed builders (from_pdh_pdl / from_pwh_pwl / from_session / "
            f"from_structural) for {level.type.name}; add_detected only rejects"
        )

    def _current_for(self, series: tuple) -> PoolLevel | None:
        """Newest level of one series (highest enter_at)."""
        candidates = [lv for lv in self._levels.values() if _series_key(lv) == series]
        if not candidates:
            return None
        return max(candidates, key=lambda lv: lv.enter_at)

    # ------------------------------------------------------------------ #
    # views
    # ------------------------------------------------------------------ #
    def active_asof(self, asof: datetime) -> list[PoolLevel]:
        """Active levels at ``asof``, chronological (no ranking applied)."""
        active = [lv for lv in self._levels.values() if lv.is_active_at(asof)]
        active.sort(key=lambda lv: (lv.enter_at, lv.family.value, lv.side.value, lv.period_id))
        return active

    def inventory(self, asof: datetime) -> list[PoolLevel]:
        """Active levels in soft report order (R3). Reports/logging only."""
        return sorted(self.active_asof(asof), key=inventory_sort_key)

    def apply_lifecycle(self, asof: datetime) -> list[PoolLevel]:
        """Mark levels EXITED whose ``exit_at`` has passed at ``asof``.

        Purely a stored-status refresh; ``active_asof`` never relies on it.
        """
        instant = _utc(asof)
        changed: list[PoolLevel] = []
        for key, level in list(self._levels.items()):
            if (
                level.exit_at is not None
                and instant >= level.exit_at
                and level.status is not PoolStatus.EXITED
            ):
                updated = replace(level, status=PoolStatus.EXITED)
                self._levels[key] = updated
                changed.append(updated)
        changed.sort(key=lambda lv: lv.level_id)
        return changed

    def all_levels(self) -> list[PoolLevel]:
        """Every level ever added, chronological."""
        return sorted(
            self._levels.values(),
            key=lambda lv: (lv.enter_at, lv.family.value, lv.side.value, lv.period_id),
        )

    def __len__(self) -> int:
        return len(self._levels)


# ---------------------------------------------------------------------- #
# builders (pure adapters over existing detection output)
# ---------------------------------------------------------------------- #
def from_pdh_pdl(level: LiquidityLevel, source_tf: Timeframe) -> PoolLevel:
    """PDH/PDL: enters the next UTC midnight after the completed day closes."""
    if level.type is not LiquidityType.PREVIOUS_DAY:
        raise ValueError(f"expected PREVIOUS_DAY level, got {level.type.name}")
    if level.formed_at is None:
        raise ValueError("PREVIOUS_DAY level requires formed_at")
    formed = _utc(level.formed_at)
    day = formed.date()
    return PoolLevel(
        family=PoolFamily.PREVIOUS_DAY,
        side=_pool_side(level.pool),
        price=float(level.level),
        period_id=day.isoformat(),
        source_tf=source_tf,
        formed_at=formed,
        enter_at=_midnight(day + timedelta(days=1)),
    )


def from_pwh_pwl(level: LiquidityLevel, source_tf: Timeframe) -> PoolLevel:
    """PWH/PWL: enters the next Monday 00:00 UTC after the completed week."""
    if level.type is not LiquidityType.PREVIOUS_WEEK:
        raise ValueError(f"expected PREVIOUS_WEEK level, got {level.type.name}")
    if level.formed_at is None:
        raise ValueError("PREVIOUS_WEEK level requires formed_at")
    formed = _utc(level.formed_at)
    monday = _monday(formed.date())
    return PoolLevel(
        family=PoolFamily.PREVIOUS_WEEK,
        side=_pool_side(level.pool),
        price=float(level.level),
        period_id=monday.isoformat(),
        source_tf=source_tf,
        formed_at=formed,
        enter_at=_midnight(monday + timedelta(days=7)),
    )


def from_session(
    level: LiquidityLevel,
    *,
    session: str,
    day: date,
    source_tf: Timeframe = Timeframe.M5,
) -> PoolLevel:
    """Session H/L: enters at session close (R1: computed on M5)."""
    if level.type is not LiquidityType.SESSION:
        raise ValueError(f"expected SESSION level, got {level.type.name}")
    key = session.upper()
    if key not in _SESSION_END_HOUR:
        raise ValueError(f"unknown session name: {session!r}")
    return PoolLevel(
        family=PoolFamily.SESSION,
        side=_pool_side(level.pool),
        price=float(level.level),
        period_id=f"{day.isoformat()}_{key}",
        source_tf=source_tf,
        formed_at=_utc(level.formed_at) if level.formed_at else None,
        enter_at=datetime(
            day.year, day.month, day.day, _SESSION_END_HOUR[key], tzinfo=timezone.utc
        ),
    )


def from_structural(
    swing: Swing,
    candles: list,
    source_tf: Timeframe,
) -> PoolLevel:
    """Structural swing: enters at the §19 confirmation bar close (R2).

    ``Swing.timestamp`` is the *base candle*, which precedes confirmation, so
    it is never used for ``enter_at``.
    """
    if not swing.is_valid:
        raise ValueError("only §19-valid swings are pool members")
    if swing.confirmed_index is None:
        raise ValueError("valid swing is missing confirmed_index")
    confirm_bar = candles[swing.confirmed_index]
    confirm_close = _utc(confirm_bar.timestamp) + timedelta(minutes=source_tf.minutes)
    return PoolLevel(
        family=PoolFamily.STRUCTURAL_SWING,
        side=_pool_side(swing.pool),
        price=float(swing.level),
        period_id=_utc(swing.timestamp).isoformat(),
        source_tf=source_tf,
        formed_at=_utc(swing.timestamp),
        enter_at=confirm_close,
    )
