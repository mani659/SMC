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

from smc.backtest.pipeline_bridge import candidate_from_route, structural_tp_target
from smc.triggers.in_between import NOT_IN_BETWEEN
from smc.triggers.trigger_expiry import poi_give_up_bars
from smc.config.locked_constants import ZONE_REFINEMENT_ATR
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, POIState, TriggerType
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

#: §5 states in which a POI may be evaluated by the menu (F6). FRESH is the
#: live state; TESTED is included because the first touch may already have
#: registered when the confirmation fires. CREATED has not been validated as
#: fresh yet and VIOLATED is dead, so neither may open or win a window.
MENU_ALLOWED_POI_STATES = frozenset({POIState.FRESH, POIState.TESTED})


def _close_ts(bar: Candle) -> datetime:
    """Close instant of a closed bar (open timestamp + timeframe length)."""
    return bar.timestamp + timedelta(minutes=bar.timeframe.minutes)


def confirmation_order_key(
    completed_at: datetime, tf: Timeframe, route_id
) -> tuple:
    """Deterministic cross-TF winner order (F2, 2026-11-09).

    The earliest COMPLETION instant wins; an exact timestamp tie chooses the
    lower timeframe, then the stable route id. This is the same batch rule the
    sweep-episode coordinator already documents
    (``SweepEpisodeCoordinator.resolve_confirmations``) — feed arrival order
    must never decide between two eligible confirmations, and the product
    engine must not carry a second, divergent ordering.
    """
    return (completed_at, tf.minutes, str(route_id or ""))


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
    # F5: the instant the POI was armed. A sweep that closed at or before it
    # is pre-arm and may not open this window (``None`` = unknown arm instant,
    # counted as ``armed_without_ts`` — never invented).
    armed_ts: datetime | None = None
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
    # F7: last instant this confirmation may still be submitted. The menu
    # window's end (sweep close + the locked expiry in detection bars); the
    # adapter drops an unaccepted confirmation at this instant.
    window_end_ts: datetime | None = None


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class ProductMenuEngine:
    """Sweep → LTF confirmation menu over the product detection streams.

    Public surface used by the runtime/harness:

    * ``register_armed(poi, detection_tf, armed_ts=instant)`` — arm a POI for
      one shot (F5: the arm instant bounds which sweeps may open it);
    * ``set_state_source(resolver)`` / ``retire(poi_id)`` — §5 gate + pruning
      wiring (F6); the menu never owns POI state or keeps dead arms;
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

        # F5: po_id → (poi, tier, armed_ts). ``armed_ts`` is the batch
        # decision instant; None means the caller could not supply it.
        self._armed: dict[str, tuple[POI, MenuTier, datetime | None]] = {}
        self._consumed: set[str] = set()
        # F6: optional §5 state resolver wired by the adapter (the menu never
        # owns POI state). None = gate not wired (research/stub), and the
        # absence is reported rather than guessed.
        self._state_source = None

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
        # F0.2 funnel counters (measurement only — no decision reads them).
        # Names mirror the audit's funnel: seen → evaluated → opened/expired.
        self._counters: dict[str, int] = {
            "detection_bars_seen": 0,
            "confirm_bars_seen": 0,
            "confirm_bars_evaluated": 0,
            "episodes_opened": 0,
            "episodes_expired": 0,
            "sweeps_out_of_window": 0,
            # F5: sweeps that closed at/before the arm instant (pre-arm).
            "sweeps_pre_arm": 0,
            # F5: arms registered without an arm instant (guard inactive).
            "armed_without_ts": 0,
            # F6: evaluations skipped because the POI was not FRESH/TESTED.
            "menu_blocked_by_state": 0,
        }

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

    def counters(self) -> dict:
        """Funnel counters (F0.2): measurement surface, never an input."""
        return {
            **self._counters,
            "sweeps_total": self.sweeps_total,
            "episodes_total": len(self._episodes),
            "winners_total": len(self.winners),
            "active_episodes": self.active_count(),
            "armed_pois": len(self._armed),
        }

    # ------------------------------------------------------------------ #
    # Arming
    # ------------------------------------------------------------------ #
    def register_armed(
        self,
        poi: POI,
        detection_tf: Timeframe,
        armed_ts: datetime | None = None,
    ) -> bool:
        """Arm ``poi`` for a one-shot window on ``detection_tf``'s tier.

        ``armed_ts`` is the instant the POI became armable (the batch's
        decision instant). F5: a sweep that closed at or before it can never
        open this POI's window, so a backfilled/batched feed cannot attach a
        months-old sweep to a POI that did not exist yet. ``None`` leaves the
        guard inactive and is counted (``armed_without_ts``), never guessed.

        Returns ``False`` when the TF is not a menu tier or the POI was
        already consumed by an earlier sweep (one-shot discipline).
        Re-arming the same POI is idempotent: the ORIGINAL arm instant wins.
        """
        tier = self.tier_for(detection_tf)
        if tier is None:
            return False
        poi_id = getattr(poi, "id", None)
        if poi_id is None or poi_id in self._consumed:
            return False
        key = str(poi_id)
        existing = self._armed.get(key)
        if existing is not None:
            poi0, tier0, armed0 = existing
            if armed0 is None and armed_ts is not None:
                # Late-arriving arm instant: keep the POI, adopt the stamp.
                self._armed[key] = (poi0, tier0, armed_ts)
                self._counters["armed_without_ts"] -= 1
            return True
        if armed_ts is None:
            self._counters["armed_without_ts"] += 1
        self._armed[key] = (poi, tier, armed_ts)
        return True

    def set_state_source(self, resolver) -> None:
        """Wire the §5 state resolver (F6): ``resolver(poi) -> POIState``.

        The menu does not own §5 state — the pipeline engine's
        ``POIStateMachine`` does. The adapter binds it here, so the menu can
        evaluate only live POIs without keeping a second state store.
        """
        self._state_source = resolver if callable(resolver) else None

    def _poi_state(self, poi) -> POIState | None:
        """§5 state from the wired resolver, or ``None`` when unwired."""
        if self._state_source is None:
            return None
        try:
            return self._state_source(poi)
        except Exception:  # noqa: BLE001 — a resolver fault must not fake a block
            return None

    def retire(self, poi_id) -> bool:
        """Drop a POI's arming bookkeeping (F6): the engine retired it.

        Called from the adapter's prune path so ``_armed`` stays bounded by
        live POIs instead of growing for the whole session. ``_consumed`` is
        NOT cleared — a consumed POI must never be re-armed.
        """
        return self._armed.pop(str(poi_id), None) is not None

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
                added = self._append_new(
                    self._series, self._det_closes, tf, bars, as_of
                )
                detection_new[tf] = added
                self._counters["detection_bars_seen"] += len(added)
            if tf in self.confirmation_timeframes:
                added = self._append_new(
                    self._confirm, self._closes, tf, bars, as_of
                )
                confirm_new[tf] = added
                self._counters["confirm_bars_seen"] += len(added)

        self._expire(detection_new)
        self._open_episodes(detection_new)

        new_winners: list[MenuWinner] = []
        for episode in self._episodes:
            if episode.status is not MenuEpisodeStatus.ACTIVE:
                continue
            # F6 (§5): a POI that died (VIOLATED / consumed elsewhere) must
            # not be confirmed. The window simply expires.
            state = self._poi_state(episode.poi)
            if state is not None and state not in MENU_ALLOWED_POI_STATES:
                self._counters["menu_blocked_by_state"] += 1
                continue
            # F2 (2026-11-09): every eligible confirmation bar of THIS batch is
            # evaluated, and the winner across the tier's confirmation TFs is
            # the EARLIEST completion — never the tier list order and never
            # merely the batch tail.
            best: tuple | None = None
            for ctf in episode.tier.confirmation_tfs:
                if not confirm_new.get(ctf):
                    continue
                route = self._route_for(episode, ctf)
                if route is None:
                    continue
                key = confirmation_order_key(
                    self._route_completion_ts(episode, route, ctf),
                    ctf,
                    getattr(route, "route_id", None),
                )
                if best is None or key < best[0]:
                    best = (key, route, ctf)
            if best is not None:
                winner = self._win(episode, best[1], best[2])
                if winner is not None:  # C3 reject -> not a winner
                    new_winners.append(winner)
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
                self._counters["episodes_expired"] += 1

    def _open_episodes(self, detection_new: dict[Timeframe, list[int]]) -> None:
        """Open a one-shot episode on the first R2 sweep seen after arming."""
        if not detection_new or not self._armed:
            return
        for tf, indexes in detection_new.items():
            if not indexes:
                continue
            series = self._series[tf]
            for poi_id, (poi, tier, armed_ts) in list(self._armed.items()):
                if tier.detection_tf is not tf:
                    continue
                if poi_id in self._consumed:
                    continue
                # F6 (§5): the menu may only evaluate live POIs. FRESH and
                # TESTED are allowed (the menu's sweep IS the first touch);
                # CREATED has not been validated fresh, VIOLATED is dead.
                state = self._poi_state(poi)
                if state is not None and state not in MENU_ALLOWED_POI_STATES:
                    self._counters["menu_blocked_by_state"] += 1
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
                    # F5: the sweep must have closed AFTER the arm instant.
                    # A backfilled feed can hand a batch months of detection
                    # bars; without this a POI would claim a sweep that
                    # happened before it existed (pre-arm window).
                    if armed_ts is not None and _close_ts(bar) <= armed_ts:
                        self._counters["sweeps_pre_arm"] += 1
                        continue
                    self.sweeps_total += 1
                    # F2 window-open guard (2026-11-09): a one-shot window
                    # that has ALREADY closed (sweep older than
                    # ``expiry_bars`` detection bars at the newest closed
                    # bar) must not open. Batched/backfilled feeds (startup,
                    # research step 0) otherwise open on months-old sweeps and
                    # then evaluate bars from that closed window — the P1-2
                    # stale-window defect, and a compute blow-up. The arm
                    # timestamp half of P1-2 remains F5 scope.
                    if index < indexes[-1] - tier.expiry_bars:
                        self._counters["sweeps_out_of_window"] += 1
                        continue
                    self._episode_seq += 1
                    episode = MenuEpisode(
                        episode_id=f"{poi_id}#{self._episode_seq}",
                        poi=poi,
                        tier=tier,
                        sweep_index=index,
                        sweep_ts=bar.timestamp,
                        sweep_close_ts=_close_ts(bar),
                        armed_ts=armed_ts,
                    )
                    episode.decisions.append(
                        f"armed_{tier.name}_sweep@{index}"
                    )
                    self._episodes.append(episode)
                    self._counters["episodes_opened"] += 1
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

    def _window_end_ts(self, episode: MenuEpisode) -> datetime | None:
        """Close of the last detection bar inside the one-shot window.

        Expiry counts DETECTION-TF bars (locked policy), so the window holds
        through the close of the bar at ``sweep_index + expiry_bars``. A
        confirmation bar closing after that instant is ineligible even while
        ``_expire`` has not run yet (episodes opened in the same batch are
        evaluated immediately — audit P1-2). ``None`` = that detection bar has
        not closed yet, so the window is still open.
        """
        det = self._series[episode.tier.detection_tf]
        end_index = episode.sweep_index + episode.tier.expiry_bars
        if 0 <= end_index < len(det):
            return _close_ts(det[end_index])
        return None

    def _route_for(self, episode: MenuEpisode, ctf: Timeframe) -> TriggerRoute | None:
        """First valid route on ``ctf`` for bars not yet evaluated (F2).

        Non-OPT-B (default): evaluate EVERY confirmation bar that closed at or
        after the sweep and is still inside the window, in ascending close
        order, skipping bars already evaluated. The pre-F2 branch evaluated
        only the batch tail, so batched feeds sampled M5 1-in-3 and M1 1-in-15
        (locked policy: the FIRST valid confirmation wins). Returns the route
        without consuming the episode — the caller orders across TFs.
        """
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
            start = max(from_index, episode._evaluated.get(ctf, -1) + 1)
            end_ts = self._window_end_ts(episode)
            upper = len(series)
            if end_ts is not None:
                upper = min(upper, bisect_right(self._closes[ctf], end_ts))
            if start >= upper:
                return None
            starts = range(start, upper)

        router = self._router_for(episode.tier)
        swings = self._swings_for(ctf)
        for index in starts:
            route = router.evaluate_at(
                episode.poi, series, swings, index, from_index
            )
            episode._evaluated[ctf] = index
            self._counters["confirm_bars_evaluated"] += 1
            if route is not None:
                return route
        return None

    def _route_completion_ts(
        self, episode: MenuEpisode, route: TriggerRoute, ctf: Timeframe
    ) -> datetime:
        """Close instant of the bar the route completed on (ordering key)."""
        series = self._confirm[ctf]
        index = getattr(getattr(route, "signal", None), "completion_index", None)
        if isinstance(index, int) and 0 <= index < len(series):
            return _close_ts(series[index])
        last = episode._evaluated.get(ctf)
        if isinstance(last, int) and 0 <= last < len(series):
            return _close_ts(series[last])
        return _close_ts(series[-1])

    def _evaluate_episode(
        self, episode: MenuEpisode, ctf: Timeframe, as_of: datetime
    ) -> MenuWinner | None:
        """Single-TF convenience wrapper: first route on ``ctf`` → winner.

        The multi-TF batch path uses ``_route_for`` directly so it can order
        candidates across TFs before consuming the episode.
        """
        route = self._route_for(episode, ctf)
        if route is None:
            return None
        return self._win(episode, route, ctf)

    # ------------------------------------------------------------------ #
    # Winner bridge
    # ------------------------------------------------------------------ #
    def _win(
        self, episode: MenuEpisode, route: TriggerRoute, tf: Timeframe
    ) -> MenuWinner | None:
        """Consume the episode one-shot and build its candidate (frozen bridge).

        ``None`` when the C3 in-between gate rejects the completion — the
        episode stays ACTIVE and unconsumed (later completions may still win).
        """
        window_end = self._window_end_ts(episode)
        if window_end is None:
            # The window's last detection bar has not closed yet: stamp the
            # window's nominal end (enough detection-TF bars after the sweep).
            # F7 uses it only to bound resubmission of an unaccepted winner.
            window_end = episode.sweep_close_ts + timedelta(
                minutes=episode.tier.detection_tf.minutes * episode.tier.expiry_bars
            )
        candidate = self._candidate(episode, route, tf, window_end_ts=window_end)
        if candidate is None:
            # C3: not a valid in-between completion. Leave the episode ACTIVE
            # and unconsumed; the confirmation scan resumes on later bars.
            episode.decisions.append(
                f"rejected_{tf.name}_{NOT_IN_BETWEEN}"
            )
            return None
        episode.status = MenuEpisodeStatus.WON
        episode.winner_tf = tf
        episode.winner_route_id = candidate.route_id
        episode.decisions.append(
            f"won_{tf.name}_{route.signal.trigger.value}"
        )
        self._consumed.add(episode.poi_id)
        # F6 bounding: a consumed POI never opens another window, so its
        # arming record has no job left.
        self._armed.pop(episode.poi_id, None)
        winner = MenuWinner(
            episode_id=episode.episode_id,
            poi_id=episode.poi_id,
            tier_name=episode.tier.name,
            detection_tf=episode.tier.detection_tf,
            confirmation_tf=tf,
            route_id=candidate.route_id,
            trigger=str(getattr(route.signal.trigger, "value", route.signal.trigger)),
            candidate=candidate,
            window_end_ts=window_end,
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
        self,
        episode: MenuEpisode,
        route: TriggerRoute,
        tf: Timeframe,
        *,
        window_end_ts: datetime | None = None,
    ) -> object | None:
        """Frozen bridge output + menu identity stamp (never re-derived edges).

        Returns ``None`` when the C3 in-between gate rejects the completion
        (the frozen bridge owns that decision — this layer never re-derives
        entry/SL/TP geometry and never bypasses the gate).
        """
        series = self._confirm[tf]
        atr_value = latest_atr(series, self.atr_period)
        atr = float(atr_value) if atr_value is not None else None
        # C3 (master card §3.4): the candidate builder is the menu's choke
        # point — pass the completion bar's CLOSE so an out-of-zone
        # completion cannot become a menu candidate.
        index = getattr(getattr(route, "signal", None), "completion_index", None)
        completion_close = (
            float(series[index].close)
            if isinstance(index, int) and 0 <= index < len(series)
            else None
        )
        # §21b TP parity (PFE-1.5): the SAME first-swing selector the seek
        # adapter feeds (``pipeline_bridge.structural_tp_target``) — never a
        # second swing rule. Placement bar = this completion bar, so only
        # swings §19-confirmed strictly before it qualify (lookahead ban);
        # no qualifying swing → the frozen 4×ATR fallback, unchanged.
        structural_target = structural_tp_target(
            self._swings_for(tf),
            route.signal.entry_price,
            route.signal.direction,
            atr,
            placement_bar=(
                index if isinstance(index, int) and index >= 0 else None
            ),
            max_age_bars=poi_give_up_bars(),
        )
        base = candidate_from_route(
            route, pillar_path=PRODUCT_MENU_PILLAR_PATH, atr=atr,
            structural_target=structural_target,
            completion_price=completion_close,
        )
        if base is None:
            # C3: completion outside the POI body — not a valid confirmation.
            return None
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
            # F5/F7: when the POI was armed and when this confirmation's
            # window closes (the adapter's retry bound). Reported for audit;
            # no risk, geometry or sizing decision reads them.
            "armed_ts": (
                episode.armed_ts.isoformat()
                if episode.armed_ts is not None
                else None
            ),
            "window_end_ts": (
                window_end_ts.isoformat() if window_end_ts is not None else None
            ),
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
