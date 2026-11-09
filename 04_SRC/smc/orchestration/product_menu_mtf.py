"""Product multi-TF sweep → LTF confirmation menu engine (P1 policy engine).

Implements ``00_LOCKED/PRODUCT_POLICY_MULTI_TF_CONFIRMATION.md`` verbatim:

* POI/structure is established on a **detection TF** (D1 / H4 / H1 / M15).
* A locked R2 **sweep** (wick beyond the zone extreme, body back inside —
  the frozen product sweep discipline, never re-defined)
  of that POI's zone arms a **one-shot** confirmation window.
* Confirmation runs only on that tier's confirmation TFs, using the tier's
  trigger subset; the first valid confirmation wins and consumes the sweep.
* Expiry counts **detection-TF bars** (``MENU_EXPIRY_BARS``), not wall clock.
* The winner is bridged to a ``CandidateEntry`` through the frozen
  ``candidate_from_route`` mapping — this layer never re-derives entry/SL/TP
  and never places anything; the existing risk/order seam does that.

OPT-1 (measure/export only): every winner's ``product_menu`` stamp also carries
the completion-bar geometry (close, ATR, nearest-edge distance, timing label).
Report-only — no eligibility, risk or placement decision reads those fields,
and unresolvable inputs stay ``None`` (``UNLOCATABLE``), never invented.

OPT-B (``same_bar_asof``, DEFAULT OFF): when enabled, the lower eligibility
anchor moves from the sweep bar's close to the close of the confirmation bar
that carries the sweep extreme, and the evaluated bar is addressed at its own
index. OFF keeps the serial anchor byte-identical to prior behaviour.

.. note::
   **Recovery provenance (2026-11-08).** This module was lost to a file
   corruption event: the in-tree copy was overwritten with a line-numbered
   dump (only lines 685-784 survived) and no copy existed in git. It was
   rebuilt from (a) the surviving fragment, (b) the intact consumers
   (``live/loop.py``, ``tests/test_confirm_vs_zone_opt1.py``,
   ``tests/test_confirm_vs_zone_opt4.py``, ``06_RESEARCH/scripts/
   opt_b_confirm_measure.py``, ``sweep_lag_study.py``), and (c) the locked
   design docs. Behaviour is restored as specified; **byte-parity with the
   pre-loss file is neither claimed nor assumed.**
"""

from __future__ import annotations

import json
from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import Enum

from smc.backtest.pipeline_bridge import candidate_from_route
from smc.config.locked_constants import ZONE_REFINEMENT_ATR
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.detection.structural_swing_detector import detect_swings
from smc.triggers.trigger_router import (
    TriggerRoute,
    TriggerRouter,
    default_triggers,
)
from smc.utils.atr import latest_atr

__all__ = [
    "LABEL_BEYOND_STOP_SIDE",
    "LABEL_LATE",
    "LABEL_ON_WINDOW",
    "LABEL_OTHER",
    "LABEL_UNLOCATABLE",
    "MENU_EXPIRY_BARS",
    "MenuEpisode",
    "MenuEpisodeStatus",
    "MenuTier",
    "MenuWinner",
    "PRODUCT_MENU_DETECTION_TIMEFRAMES",
    "PRODUCT_MENU_PILLAR_PATH",
    "PRODUCT_MENU_TIERS",
    "ProductMenuEngine",
    "completion_timing_label",
    "completion_zone_edge_distance_atr",
    "menu_covers",
]

# --------------------------------------------------------------------------- #
# OPT-1 timing taxonomy — the FROZEN timing-study semantics, read not changed
# --------------------------------------------------------------------------- #
LABEL_ON_WINDOW = "ON_WINDOW"
LABEL_LATE = "LATE"
LABEL_BEYOND_STOP_SIDE = "BEYOND_STOP_SIDE"
LABEL_OTHER = "OTHER"
LABEL_UNLOCATABLE = "UNLOCATABLE"

#: Pillar-path summary stamped on every menu bridge candidate.
PRODUCT_MENU_PILLAR_PATH = "PRODUCT_MTF_MENU"

#: Detection-TF bar count every tier's one-shot window lives for.
MENU_EXPIRY_BARS = 20


def _close_ts(bar: Candle) -> datetime:
    """Close instant of a closed bar (open timestamp + timeframe length)."""
    return bar.timestamp + timedelta(minutes=bar.timeframe.minutes)


def _is_zone_sweep(bar: Candle, zone: Zone) -> bool:
    """Locked R2 sweep: one bar wicks beyond the zone extreme and closes back.

    LONG (demand): ``low < zone.bottom`` AND ``close > zone.bottom``.
    SHORT (supply): ``high > zone.top`` AND ``close < zone.top``.
    A bar that closes beyond the extreme is a genuine breakout, not a sweep.
    This is the frozen product sweep discipline read as a pure predicate; the
    menu layer never imports the research package for it.
    """
    if zone.direction is Direction.LONG:
        return bar.low < zone.bottom and bar.close > zone.bottom
    return bar.high > zone.top and bar.close < zone.top


def _direction_of(direction) -> Direction | None:
    """Resolve a ``Direction`` (or its string value) — ``None`` when unknown."""
    if isinstance(direction, Direction):
        return direction
    try:
        return Direction(str(direction).lower())
    except (TypeError, ValueError):
        return None


def completion_timing_label(
    direction,
    zone_low: float | None,
    zone_high: float | None,
    close: float | None,
    atr: float | None,
    band_atr: float = ZONE_REFINEMENT_ATR,
) -> str:
    """Frozen timing-study label for one completion close vs the POI zone.

    ``band_atr`` defaults to the LOCKED ``ZONE_REFINEMENT_ATR`` (read, never
    modified). LONG: the trade side is ABOVE the zone (stop below), so a close
    displacing ABOVE the far edge is ``LATE`` and one leaking BELOW the near
    edge is ``BEYOND_STOP_SIDE``; SHORT is mirrored. The band is INCLUSIVE.

    Unresolvable inputs (missing bounds/close, non-positive ATR, unknown
    direction) are ``UNLOCATABLE`` / ``OTHER`` — never guessed.
    """
    side = _direction_of(direction)
    if side is None:
        return LABEL_OTHER
    if (
        zone_low is None
        or zone_high is None
        or close is None
        or atr is None
        or float(atr) <= 0
    ):
        return LABEL_UNLOCATABLE
    low, high = sorted((float(zone_low), float(zone_high)))
    price = float(close)
    band = float(band_atr) * float(atr)
    if side is Direction.LONG:
        trade_excursion = price - high      # displacement away from the stop
        stop_excursion = low - price        # leakage past the protective side
    else:
        trade_excursion = low - price
        stop_excursion = price - high
    if stop_excursion > band:
        return LABEL_BEYOND_STOP_SIDE
    if trade_excursion > band:
        return LABEL_LATE
    return LABEL_ON_WINDOW


def completion_zone_edge_distance_atr(
    zone_low: float | None,
    zone_high: float | None,
    close: float | None,
    atr: float | None,
) -> float | None:
    """Nearest-zone-edge distance in ATR units (0.0 inside), ``None`` if unknown.

    The ONE OPT-1 distance convention: bounds are normalised when inverted and
    unresolvable inputs return ``None`` (never invented).
    """
    if (
        zone_low is None
        or zone_high is None
        or close is None
        or atr is None
        or float(atr) <= 0
    ):
        return None
    low, high = sorted((float(zone_low), float(zone_high)))
    price = float(close)
    if low <= price <= high:
        return 0.0
    gap = low - price if price < low else price - high
    # 6 dp: the frozen export convention (stamps and seam records agree
    # bit-for-bit without float noise like 1.6000000000000014).
    return round(gap / float(atr), 6)


# --------------------------------------------------------------------------- #
# Tier table — the menu is DATA, not logic (locked 2026-10-26)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class MenuTier:
    """One sweep tier: detection TF, its confirmation TFs, and the window."""

    name: str
    detection_tf: Timeframe
    confirmation_tfs: tuple[Timeframe, ...]
    expiry_bars: int
    trigger_types: tuple[TriggerType, ...]


_TIER_ADF = (
    TriggerType.A_CHOCH,
    TriggerType.D_TWO_BAR_REVERSAL,
    TriggerType.F_BOS_OB,
)
_DAY_TRIGGERS = tuple(TriggerType)

PRODUCT_MENU_TIERS: tuple[MenuTier, ...] = (
    MenuTier("DAY", Timeframe.D1, (Timeframe.H1,), MENU_EXPIRY_BARS, _DAY_TRIGGERS),
    MenuTier("H4", Timeframe.H4, (Timeframe.M5, Timeframe.M15), MENU_EXPIRY_BARS, _TIER_ADF),
    MenuTier("H1", Timeframe.H1, (Timeframe.M5, Timeframe.M1), MENU_EXPIRY_BARS, _TIER_ADF),
    MenuTier("M15", Timeframe.M15, (Timeframe.M1,), MENU_EXPIRY_BARS, _TIER_ADF),
)

PRODUCT_MENU_DETECTION_TIMEFRAMES: tuple[Timeframe, ...] = tuple(
    tier.detection_tf for tier in PRODUCT_MENU_TIERS
)

PRODUCT_MENU_CONFIRMATION_TIMEFRAMES: tuple[Timeframe, ...] = tuple(
    dict.fromkeys(
        ctf for tier in PRODUCT_MENU_TIERS for ctf in tier.confirmation_tfs
    )
)

_TIER_BY_DETECTION = {tier.detection_tf: tier for tier in PRODUCT_MENU_TIERS}


def menu_covers(timeframes) -> bool:
    """True when ``timeframes`` carries every detection stream the menu needs."""
    present = set(timeframes or ())
    return all(tf in present for tf in PRODUCT_MENU_DETECTION_TIMEFRAMES)


# --------------------------------------------------------------------------- #
# Episode / winner records
# --------------------------------------------------------------------------- #
class MenuEpisodeStatus(Enum):
    """One-shot episode lifecycle (ACTIVE → WON | EXPIRED, terminal)."""

    ACTIVE = "active"
    WON = "won"
    EXPIRED = "expired"


@dataclass
class MenuEpisode:
    """One armed POI's one-shot confirmation window, opened by an R2 sweep."""

    episode_id: str
    poi: POI
    tier: MenuTier
    sweep_index: int
    sweep_ts: datetime
    sweep_close_ts: datetime
    status: MenuEpisodeStatus = MenuEpisodeStatus.ACTIVE
    decisions: list[str] = field(default_factory=list)
    winner_tf: Timeframe | None = None
    winner_route_id: str | None = None
    # OPT-B: per-confirmation-TF cached extreme-carrying bar close (None = no
    # interior bar observed → fall back to the sweep-close anchor).
    sweep_anchor: dict = field(default_factory=dict)
    # Last confirmation-bar index evaluated per TF (never re-evaluate a bar).
    _evaluated: dict = field(default_factory=dict, repr=False)

    @property
    def poi_id(self) -> str:
        return self.poi.id

    @property
    def zone(self) -> Zone:
        return self.poi.zone

    @property
    def detection_tf(self) -> Timeframe:
        return self.tier.detection_tf


@dataclass(frozen=True, slots=True)
class MenuWinner:
    """A confirmed menu winner (bridge candidate + frozen identity)."""

    episode_id: str
    poi_id: str
    tier_name: str
    detection_tf: Timeframe
    confirmation_tf: Timeframe
    route_id: str | None
    trigger: str
    candidate: object


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class ProductMenuEngine:
    """Sweep → LTF confirmation menu over the product detection streams.

    Public surface used by the runtime/harness:

    * ``register_armed(poi, detection_tf)`` — arm a POI for one shot;
    * ``on_execution_bar({tf: [closed bars]}, as_of=instant)`` — ingest closed
      bars, expire windows, detect sweeps, evaluate confirmations, return any
      new winners;
    * ``episodes()`` / ``winners`` / ``active_count()`` / ``sweeps_total`` —
      read-only inspection for the runtime, KPI export and research harnesses.
    """

    def __init__(
        self,
        symbol: str = "XAUUSDm",
        *,
        same_bar_asof: bool = False,
        atr_period: int = 14,
        tiers: tuple[MenuTier, ...] = PRODUCT_MENU_TIERS,
    ) -> None:
        self.symbol = symbol
        # OPT-B posture: DEFAULT OFF — enabling it is an explicit operator
        # decision (config ``enable_opt_b_same_bar_confirm``), never implicit.
        self.same_bar_asof = bool(same_bar_asof)
        self.atr_period = int(atr_period)
        self.tiers = tuple(tiers)
        self.detection_timeframes = tuple(t.detection_tf for t in self.tiers)
        self.confirmation_timeframes = tuple(
            dict.fromkeys(ctf for t in self.tiers for ctf in t.confirmation_tfs)
        )

        # Router: ``None`` → per-tier router built from the tier's trigger
        # subset. Tests/harnesses may inject one router for every tier.
        self._router: TriggerRouter | None = None
        self._tier_routers: dict[str, TriggerRouter] = {}

        self._armed: dict[str, tuple[POI, MenuTier]] = {}
        self._consumed: set[str] = set()

        # Detection and confirmation streams are separate stores even when a
        # TF serves both roles (H1/M15): the same bar feeds sweeps AND
        # confirmation, so each store keeps its own close-timestamp index.
        self._series: dict[Timeframe, list[Candle]] = defaultdict(list)
        self._confirm: dict[Timeframe, list[Candle]] = defaultdict(list)
        self._det_closes: dict[Timeframe, list[datetime]] = defaultdict(list)
        self._closes: dict[Timeframe, list[datetime]] = defaultdict(list)
        self._swings_cache: dict[Timeframe, tuple[int, list]] = {}

        self._episodes: list[MenuEpisode] = []
        self.winners: list[MenuWinner] = []
        self.sweeps_total = 0
        self._episode_seq = 0

    # ------------------------------------------------------------------ #
    # Read-only surface
    # ------------------------------------------------------------------ #
    def tier_for(self, detection_tf: Timeframe) -> MenuTier | None:
        """The tier whose detection TF is ``detection_tf`` (``None`` if none)."""
        return _TIER_BY_DETECTION.get(detection_tf)

    def episodes(self) -> tuple[MenuEpisode, ...]:
        """Every episode opened so far, in open order (immutable view)."""
        return tuple(self._episodes)

    def active_count(self) -> int:
        """Number of episodes still inside their one-shot window."""
        return sum(
            1 for e in self._episodes if e.status is MenuEpisodeStatus.ACTIVE
        )

    # ------------------------------------------------------------------ #
    # Arming
    # ------------------------------------------------------------------ #
    def register_armed(self, poi: POI, detection_tf: Timeframe) -> bool:
        """Arm ``poi`` for a one-shot window on ``detection_tf``'s tier.

        Returns ``False`` when the TF is not a menu tier or the POI was already
        consumed by an earlier sweep (one-shot discipline).
        """
        tier = self.tier_for(detection_tf)
        if tier is None:
            return False
        poi_id = getattr(poi, "id", None)
        if poi_id is None or poi_id in self._consumed:
            return False
        self._armed[str(poi_id)] = (poi, tier)
        return True

    # ------------------------------------------------------------------ #
    # Ingestion
    # ------------------------------------------------------------------ #
    def _append_new(
        self,
        store: dict[Timeframe, list[Candle]],
        closes: dict[Timeframe, list[datetime]],
        tf: Timeframe,
        bars,
        as_of: datetime,
    ) -> list[int]:
        """Append the closed bars newer than the stored tail; return indexes.

        No-lookahead guard: a bar whose close is after ``as_of`` is dropped, and
        out-of-order/duplicate bars (close at or before the stored tail) are
        dropped — the pre-existing ``_new_closed`` contract.
        """
        series = store[tf]
        close_list = closes[tf]
        added: list[int] = []
        for bar in bars or ():
            if getattr(bar, "timeframe", None) is not tf:
                continue
            stamp = _close_ts(bar)
            if stamp > as_of:
                continue
            if close_list and stamp <= close_list[-1]:
                continue
            series.append(bar)
            close_list.append(stamp)
            added.append(len(series) - 1)
        return added

    def on_execution_bar(self, closed, *, as_of: datetime) -> list[MenuWinner]:
        """Ingest one execution step's closed streams and evaluate the menu.

        ``closed`` maps a timeframe to the closed bars visible at ``as_of``.
        Returns the winners produced by THIS call (possibly empty).
        """
        detection_new: dict[Timeframe, list[int]] = {}
        confirm_new: dict[Timeframe, list[int]] = {}

        for tf, bars in (closed or {}).items():
            if tf in self.detection_timeframes:
                detection_new[tf] = self._append_new(
                    self._series, self._det_closes, tf, bars, as_of
                )
            if tf in self.confirmation_timeframes:
                confirm_new[tf] = self._append_new(
                    self._confirm, self._closes, tf, bars, as_of
                )

        self._expire(detection_new)
        self._open_episodes(detection_new)

        new_winners: list[MenuWinner] = []
        for episode in self._episodes:
            if episode.status is not MenuEpisodeStatus.ACTIVE:
                continue
            for ctf in episode.tier.confirmation_tfs:
                if not confirm_new.get(ctf):
                    continue
                winner = self._evaluate_episode(episode, ctf, as_of)
                if winner is not None:
                    new_winners.append(winner)
                    break
        return new_winners

    # ------------------------------------------------------------------ #
    # Window lifecycle
    # ------------------------------------------------------------------ #
    def _expire(self, detection_new: dict[Timeframe, list[int]]) -> None:
        """Expire windows whose detection TF advanced past their last bar."""
        if not detection_new:
            return
        last_index: dict[Timeframe, int] = {}
        for tf, indexes in detection_new.items():
            if indexes:
                last_index[tf] = indexes[-1]
        for episode in self._episodes:
            if episode.status is not MenuEpisodeStatus.ACTIVE:
                continue
            index = last_index.get(episode.tier.detection_tf)
            if index is None:
                continue
            if index > episode.sweep_index + episode.tier.expiry_bars:
                episode.status = MenuEpisodeStatus.EXPIRED
                episode.decisions.append("expired")

    def _open_episodes(self, detection_new: dict[Timeframe, list[int]]) -> None:
        """Open a one-shot episode on the first R2 sweep seen after arming."""
        if not detection_new or not self._armed:
            return
        for tf, indexes in detection_new.items():
            if not indexes:
                continue
            series = self._series[tf]
            for poi_id, (poi, tier) in self._armed.items():
                if tier.detection_tf is not tf:
                    continue
                if poi_id in self._consumed:
                    continue
                if any(
                    e.status is MenuEpisodeStatus.ACTIVE and e.poi_id == poi_id
                    for e in self._episodes
                ):
                    continue
                for index in indexes:
                    bar = series[index]
                    if not _is_zone_sweep(bar, poi.zone):
                        continue
                    self.sweeps_total += 1
                    self._episode_seq += 1
                    episode = MenuEpisode(
                        episode_id=f"{poi_id}#{self._episode_seq}",
                        poi=poi,
                        tier=tier,
                        sweep_index=index,
                        sweep_ts=bar.timestamp,
                        sweep_close_ts=_close_ts(bar),
                    )
                    episode.decisions.append(
                        f"armed_{tier.name}_sweep@{index}"
                    )
                    self._episodes.append(episode)
                    break

    # ------------------------------------------------------------------ #
    # Confirmation
    # ------------------------------------------------------------------ #
    def _router_for(self, tier: MenuTier) -> TriggerRouter:
        """Tier router (trigger subset) unless a caller injected one."""
        if self._router is not None:
            return self._router
        router = self._tier_routers.get(tier.name)
        if router is None:
            allowed = set(tier.trigger_types)
            router = TriggerRouter(
                triggers=[t for t in default_triggers() if t.type in allowed]
            )
            self._tier_routers[tier.name] = router
        return router

    def _swings_for(self, ctf: Timeframe) -> list:
        """Structural swings for the confirmation series (cached by length)."""
        series = self._confirm[ctf]
        cached = self._swings_cache.get(ctf)
        if cached is not None and cached[0] == len(series):
            return cached[1]
        try:
            swings = detect_swings(series, ctf)
        except (ValueError, IndexError):  # too few bars / odd series
            swings = []
        self._swings_cache[ctf] = (len(series), swings)
        return swings

    def _first_close_at_or_after(self, ctf: Timeframe, stamp: datetime) -> int | None:
        """Serial anchor (OPT-B OFF): first confirm bar closing at/after the sweep."""
        closes = self._closes[ctf]
        index = bisect_left(closes, stamp)
        return index if index < len(closes) else None

    def _first_close_after(self, ctf: Timeframe, stamp: datetime) -> int | None:
        """OPT-B anchor: first confirm bar closing strictly AFTER ``stamp``."""
        closes = self._closes[ctf]
        index = bisect_right(closes, stamp)
        return index if index < len(closes) else None

    def _sweep_anchor_close(
        self, episode: MenuEpisode, ctf: Timeframe
    ) -> datetime | None:
        """OPT-B: close of the LAST confirm bar carrying the sweep extreme.

        The extreme is the sweep bar's deepest pierce (LONG low / SHORT high);
        only confirmation bars that both close inside the sweep detection bar
        and touch that extreme qualify. ``None`` when no interior bar exists
        (sparse feed) — the caller then falls back to the sweep-close anchor.
        """
        if ctf in episode.sweep_anchor:
            return episode.sweep_anchor[ctf]
        detection_series = self._series[episode.tier.detection_tf]
        if not 0 <= episode.sweep_index < len(detection_series):
            episode.sweep_anchor[ctf] = None
            return None
        sweep_bar = detection_series[episode.sweep_index]
        direction = episode.zone.direction
        extreme = (
            float(sweep_bar.low)
            if direction is Direction.LONG
            else float(sweep_bar.high)
        )
        anchor: datetime | None = None
        closes = self._closes[ctf]
        series = self._confirm[ctf]
        start = bisect_left(closes, sweep_bar.timestamp)
        for index in range(start, len(series)):
            stamp = closes[index]
            if stamp > episode.sweep_close_ts:
                break
            bar = series[index]
            touches = (
                float(bar.low) <= extreme
                if direction is Direction.LONG
                else float(bar.high) >= extreme
            )
            if touches:
                anchor = stamp      # LAST touching bar wins (re-pierce = same grab)
        episode.sweep_anchor[ctf] = anchor
        return anchor

    def _evaluate_episode(
        self, episode: MenuEpisode, ctf: Timeframe, as_of: datetime
    ) -> MenuWinner | None:
        """Evaluate the confirmation stream for one episode on one TF."""
        series = self._confirm[ctf]
        if not series:
            return None
        if self.same_bar_asof:
            anchor = self._sweep_anchor_close(episode, ctf)
            if anchor is None:
                anchor = episode.sweep_close_ts       # sparse-feed fallback
            if anchor >= episode.sweep_close_ts:
                from_index = self._first_close_at_or_after(ctf, anchor)
            else:
                from_index = self._first_close_after(ctf, anchor)
            if from_index is None:
                from_index = len(series) - 1
            starts = [
                i for i in range(from_index, len(series))
                if episode._evaluated.get(ctf, -1) < i
            ]
        else:
            from_index = self._first_close_at_or_after(
                ctf, episode.sweep_close_ts
            )
            if from_index is None:
                return None
            tail = len(series) - 1
            if tail < from_index:
                return None
            if episode._evaluated.get(ctf, -1) >= tail:
                return None
            starts = [tail]

        router = self._router_for(episode.tier)
        swings = self._swings_for(ctf)
        for index in starts:
            route = router.evaluate_at(
                episode.poi, series, swings, index, from_index
            )
            episode._evaluated[ctf] = index
            if route is None:
                continue
            return self._win(episode, route, ctf)
        return None

    # ------------------------------------------------------------------ #
    # Winner bridge
    # ------------------------------------------------------------------ #
    def _win(
        self, episode: MenuEpisode, route: TriggerRoute, tf: Timeframe
    ) -> MenuWinner:
        """Consume the episode one-shot and build its candidate (frozen bridge)."""
        candidate = self._candidate(episode, route, tf)
        episode.status = MenuEpisodeStatus.WON
        episode.winner_tf = tf
        episode.winner_route_id = candidate.route_id
        episode.decisions.append(
            f"won_{tf.name}_{route.signal.trigger.value}"
        )
        self._consumed.add(episode.poi_id)
        winner = MenuWinner(
            episode_id=episode.episode_id,
            poi_id=episode.poi_id,
            tier_name=episode.tier.name,
            detection_tf=episode.tier.detection_tf,
            confirmation_tf=tf,
            route_id=candidate.route_id,
            trigger=str(getattr(route.signal.trigger, "value", route.signal.trigger)),
            candidate=candidate,
        )
        self.winners.append(winner)
        return winner

    def _completion_metrics(
        self, route: TriggerRoute, tf: Timeframe, series: list[Candle], zone
    ) -> dict:
        """OPT-1 export: completion-bar geometry for the enrich stamp.

        The completion bar is ``route.signal.completion_index`` in the
        confirm-TF series. ATR is the Wilder prefix AT that index
        (``latest_atr`` on the closed prefix only — no lookahead, and the
        flag-free convention). Distance = nearest zone edge in ATR (0
        inside); label = the timing-study taxonomy with the locked band.
        Everything is report-only; values are never invented when unavailable.
        """
        index = getattr(route.signal, "completion_index", None)
        if not isinstance(index, int) or index < 0 or index >= len(series):
            return self._unlocatable_completion()
        bar = series[index]
        close = float(bar.close)
        atr_value = latest_atr(series[: index + 1], self.atr_period)
        atr = (
            float(atr_value)
            if atr_value is not None and float(atr_value) > 0
            else None
        )
        direction = zone.direction
        label = completion_timing_label(direction, zone.bottom, zone.top,
                                        close, atr)
        distance = completion_zone_edge_distance_atr(
            zone.bottom, zone.top, close, atr)
        return {
            "completion_index": index,
            "completion_ts": _close_ts(bar).isoformat(),
            "completion_close": close,
            "atr_at_confirm": round(atr, 6) if atr is not None else None,
            "distance_at_confirm_atr": distance,
            "label_at_confirm": label,
        }

    @staticmethod
    def _unlocatable_completion() -> dict:
        """Honest all-None enrichment (never invented)."""
        return {
            "completion_index": None,
            "completion_ts": None,
            "completion_close": None,
            "atr_at_confirm": None,
            "distance_at_confirm_atr": None,
            "label_at_confirm": LABEL_UNLOCATABLE,
        }

    def _candidate(
        self, episode: MenuEpisode, route: TriggerRoute, tf: Timeframe
    ) -> object:
        """Frozen bridge output + menu identity stamp (never re-derived edges)."""
        series = self._confirm[tf]
        atr_value = latest_atr(series, self.atr_period)
        atr = float(atr_value) if atr_value is not None else None
        base = candidate_from_route(
            route, pillar_path=PRODUCT_MENU_PILLAR_PATH, atr=atr
        )
        zone = episode.poi.zone
        # OPT-1 enrich stamp (measure/export only): join the completion-bar
        # geometry onto the same stamp that already carries sweep_ts and the
        # tier identity. Report-only; no eligibility/risk/placement decision
        # reads these fields, and unresolvable values stay None (never
        # invented). Distance convention: NEAREST zone edge, 0 inside.
        completion = self._completion_metrics(route, tf, series, zone)
        stamp = {
            "menu": PRODUCT_MENU_PILLAR_PATH,
            "tier": episode.tier.name,
            "detection_tf": episode.tier.detection_tf.name,
            "confirmation_tf": tf.name,
            "poi_id": episode.poi_id,
            "zone": [float(zone.bottom), float(zone.top)],
            "sweep_ts": episode.sweep_ts.isoformat(),
            "zone_direction": getattr(zone.direction, "value", str(zone.direction)),
            **completion,
        }
        try:
            payload = json.loads(base.signal_data_json or "{}")
        except (TypeError, ValueError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload["product_menu"] = stamp
        return replace(
            base,
            signal_data_json=json.dumps(payload, sort_keys=True, default=str),
        )
