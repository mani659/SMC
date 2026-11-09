"""Closed-bar H4 -> M5/M15 event feed for the DUMB-MTF demo slice.

This module owns no broker mutation.  It emits only the three events accepted
by :class:`DumbMtfPaperAdapter`: first POI-zone touch, post-expiry boundary
sweep, and an in-zone DUMB confirmation.  H4 is deliberately the only source
enabled here: it is the first slice approved in the MTF episode design and is
the only one with a DUMB-owned, read-only M8 zone emitter.
"""

from __future__ import annotations

from dataclasses import dataclass

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.zone import Zone
from smc.dumb.mtf import DumbMtfEpisodeKey, DumbMtfStatus
from smc.dumb.mtf_paper_adapter import DumbMtfPaperAdapter, DumbMtfRoute
from smc.dumb.rules import is_confirm, is_sweep
from smc.utils.atr import latest_atr

__all__ = ["DumbMtfH4Feed"]


@dataclass(frozen=True, slots=True)
class _H4Poi:
    poi_id: str
    zone: Zone


class DumbMtfH4Feed:
    """H4 POI source with closed M5/M15 confirmation streams.

    A zone becomes usable only from a closed H4 prefix.  A primary episode
    starts on the first M5 range touch after price was outside that zone.
    M5 is the H4 policy clock; M15 events are supplied only when their closed
    bar advances.  The feed does not manufacture H1/M15 source POIs.
    """

    def __init__(self, adapter: DumbMtfPaperAdapter, *, symbol: str) -> None:
        self.adapter = adapter
        self.symbol = symbol
        self._h4_pois: dict[str, _H4Poi] = {}
        self._episode_zones: dict[str, Zone] = {}
        self._sweep_extremes: dict[str, float] = {}
        self._sweep_timestamps: dict[str, object] = {}
        self._touching: set[str] = set()
        self._m5_bars: list[Candle] = []
        self._m5_index = -1
        self._last_m15_ts = None

    @property
    def active_h4_poi_count(self) -> int:
        return len(self._h4_pois)

    def on_m5_closed(
        self,
        bar: Candle,
        *,
        h4_closed: list[Candle],
        m15_closed: Candle | None = None,
    ) -> list[str]:
        """Consume one closed M5 bar and optional newly closed M15 bar."""
        if bar.timeframe is not Timeframe.M5:
            raise ValueError("DUMB-MTF H4 feed requires closed M5 execution bars")
        self._m5_bars.append(bar)
        self._m5_index += 1
        self._refresh_h4_pois(h4_closed)
        self.adapter.advance_clock(Timeframe.M5, self._m5_index)
        self._start_primary_on_new_touches(bar)

        routes: list[DumbMtfRoute] = []
        routes.extend(self._routes_for_bar(bar, Timeframe.M5))
        if m15_closed is not None and m15_closed.timestamp != self._last_m15_ts:
            self._last_m15_ts = m15_closed.timestamp
            routes.extend(self._routes_for_bar(m15_closed, Timeframe.M15))
        return self.adapter.record_confirmations(routes)

    def _refresh_h4_pois(self, h4_closed: list[Candle]) -> None:
        """Read H4 M8 output from a closed prefix; geometry is stable identity."""
        if not h4_closed:
            return
        from smc.poi.models.m8_htf_demand_supply import M8HtfDemandSupply

        model = M8HtfDemandSupply(Timeframe.H4, htf_candles={Timeframe.H4: h4_closed})
        current: dict[str, _H4Poi] = {}
        for poi in model.detect(h4_closed, [], []):
            zone = poi.zone
            kind = getattr(poi, "m8_kind", "m8") or "m8"
            poi_id = (
                f"dumb-mtf-h4|{kind}|{zone.direction.name}|"
                f"{zone.bottom:.6f}|{zone.top:.6f}"
            )
            current[poi_id] = _H4Poi(poi_id, zone)
        self._h4_pois = current
        self._touching.intersection_update(current)

    def _start_primary_on_new_touches(self, bar: Candle) -> None:
        now_touching: set[str] = set()
        for poi_id, poi in self._h4_pois.items():
            if not _range_touches(poi.zone, bar):
                continue
            now_touching.add(poi_id)
            if poi_id in self._touching:
                continue
            key = DumbMtfEpisodeKey(
                self.symbol,
                poi.zone.direction.name,
                Timeframe.H4,
                poi_id,
                f"touch@{bar.timestamp.isoformat()}",
            )
            episode_id = self.adapter.start_primary(key, self._m5_index)
            self._episode_zones[episode_id] = poi.zone
        self._touching = now_touching

    def _routes_for_bar(self, bar: Candle, timeframe: Timeframe) -> list[DumbMtfRoute]:
        routes: list[DumbMtfRoute] = []
        for episode_id, zone in self._episode_zones.items():
            episode = self.adapter.machine.get(episode_id)
            if episode is None or episode.status not in (
                DumbMtfStatus.IN_ZONE_PRIMARY,
                DumbMtfStatus.BOUNDARY_FALLBACK,
            ):
                continue
            if episode_id not in self._sweep_extremes and is_sweep(bar, zone):
                if episode.status is DumbMtfStatus.BOUNDARY_FALLBACK:
                    self.adapter.record_boundary_sweep(episode_id, self._m5_index)
                self._sweep_extremes[episode_id] = (
                    bar.low if zone.direction.name == "LONG" else bar.high
                )
                self._sweep_timestamps[episode_id] = bar.timestamp
                continue  # the qualifying sweep bar never also confirms
            # Owner ruling 2026-10-25: primary confirmation is eligible only
            # after a real in-zone wick/close-back sweep supplies the locked
            # DUMB stop anchor.  Fallback follows the same evidence rule.
            sweep_timestamp = self._sweep_timestamps.get(episode_id)
            if sweep_timestamp is None or bar.timestamp <= sweep_timestamp:
                continue
            # Primary is in-zone only. Fallback remains a POI-boundary route,
            # and its confirmation likewise cannot chase outside the POI.
            if not zone.contains(bar.close) or not is_confirm(bar, zone):
                continue
            atr = latest_atr(self._m5_bars, 14)
            if atr is None:
                continue
            routes.append(DumbMtfRoute(
                episode_id=episode_id,
                timeframe=timeframe,
                route_id=f"{episode_id}|{timeframe.name}|{bar.timestamp.isoformat()}",
                zone=zone,
                entry_price=bar.close,
                sweep_extreme=self._sweep_extremes[episode_id],
                atr=float(atr),
                completed_at=bar.timestamp,
            ))
        return routes


def _range_touches(zone: Zone, bar: Candle) -> bool:
    """True when a closed candle's full range intersects the POI zone."""
    return bar.high >= zone.bottom and bar.low <= zone.top
