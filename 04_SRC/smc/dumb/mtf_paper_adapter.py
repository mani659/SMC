"""PaperRunner adapter for the isolated DUMB-MTF episode path.

It deliberately has no detector or broker logic.  A closed-bar feed supplies
zone touches, boundary sweeps, and DUMB confirmations; this adapter enforces
the sequential episode clock and submits exactly one ordinary CandidateEntry
for a winning episode to the existing PaperRunner.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from smc.backtest.runner import CandidateEntry
from smc.config.timeframe import Timeframe
from smc.core.zone import Zone
from smc.dumb.mtf import DumbMtfEpisodeKey, DumbMtfStateMachine, DumbMtfStatus
from smc.dumb.rules import compute_sl_tp
from smc.utils.atr import latest_atr

__all__ = ["DumbMtfPaperAdapter", "DumbMtfRoute"]


@dataclass(frozen=True, slots=True)
class DumbMtfRoute:
    """Closed-bar DUMB confirmation geometry for one already-known episode."""

    episode_id: str
    timeframe: Timeframe
    route_id: str
    zone: Zone
    entry_price: float
    sweep_extreme: float
    atr: float
    completed_at: datetime


class DumbMtfPaperAdapter:
    """Minimal PaperRunner protocol adapter for DUMB-MTF only.

    Event producers call the explicit methods below after their source bar is
    final.  ``generate_candidates`` only drains winners already formed before
    the current PaperRunner entry step; it never inspects future candles.
    """

    def __init__(self, state_machine: DumbMtfStateMachine | None = None) -> None:
        self.machine = state_machine or DumbMtfStateMachine()
        self._runner = None
        self._candles = []
        self._queued: list[CandidateEntry] = []
        self.accepted_route_ids: set[str] = set()

    def attach(self, runner) -> None:
        self._runner = runner
        runner.set_pipeline_adapter(self)

    def start_primary(self, key: DumbMtfEpisodeKey, clock_bar: int) -> str:
        episode, _ = self.machine.start_primary(key, clock_bar)
        return episode.episode_id

    def advance_clock(self, timeframe: Timeframe, closed_bar: int) -> None:
        self.machine.advance_clock(timeframe, closed_bar)

    def record_boundary_sweep(self, episode_id: str, clock_bar: int) -> None:
        self.machine.record_boundary_sweep(episode_id, clock_bar)

    def record_confirmation(self, route: DumbMtfRoute) -> bool:
        """Accept one closed DUMB confirmation.

        A feed which closes more than one eligible confirmation timeframe at
        one instant should use :meth:`record_confirmations` so the specified
        lower-timeframe tie break is deterministic rather than arrival-order
        dependent.
        """
        return self._record_confirmation(route)

    def record_confirmations(self, routes: Iterable[DumbMtfRoute]) -> list[str]:
        """Register a closed-bar batch; earliest time then finer TF wins ties."""
        ordered = sorted(
            routes,
            key=lambda route: (route.completed_at, route.timeframe.minutes, route.route_id),
        )
        return [route.route_id for route in ordered if self._record_confirmation(route)]

    def _record_confirmation(self, route: DumbMtfRoute) -> bool:
        """Accept a closed DUMB confirmation if it is the episode's winner."""
        episode = self.machine.confirm(route.episode_id, route.timeframe, route.route_id)
        if episode is None or episode.status is not DumbMtfStatus.WON:
            return False
        if episode.winner_route_id != route.route_id:
            return False
        sl, tp = compute_sl_tp(
            route.zone.direction, route.entry_price, route.sweep_extreme, route.atr
        )
        candidate = CandidateEntry(
            direction=route.zone.direction,
            entry_price=route.entry_price,
            sl_price=sl,
            tp_price=tp,
            sweep_level=route.sweep_extreme,
            poi_id=episode.episode_id,
            trigger="DUMB_MTF",
            route_id=f"DUMB_MTF|{route.route_id}",
            model_tags=("DUMB_MTF",),
            pillar_path="DUMB_MTF_SEQUENTIAL",
            original_sl=sl,
            zone_low=route.zone.bottom,
            zone_high=route.zone.top,
            signal_data_json=(
                f'{{"episode_id":"{episode.episode_id}",'
                f'"confirm_tf":"{route.timeframe.name}",'
                f'"phase":"{episode.history[-2]}"}}'
            ),
            entry_anchor="dumb_mtf_confirmation",
            tp_source="dumb_mtf_fixed_2r",
            detection_tf=episode.key.source_timeframe,
        )
        self._queued.append(candidate)
        return True

    def invalidate(self, episode_id: str, reason: str) -> None:
        self.machine.invalidate(episode_id, reason)

    def generate_candidates(self, bar, bar_index: int, now) -> None:
        """PaperRunner protocol: submit only winners queued before this bar."""
        if self._runner is None:
            return
        queued, self._queued = self._queued, []
        for candidate in queued:
            self._runner.submit_entry(candidate)

    def on_candidate_accepted(self, candidate: CandidateEntry) -> None:
        if candidate.route_id:
            self.accepted_route_ids.add(candidate.route_id)

    def current_atr(self, _bar_index: int | None = None) -> float:
        """Console-compatible read of the closed M5 ATR; never a signal gate."""
        atr = latest_atr(self._candles, 14)
        return float(atr) if atr is not None else 0.0
