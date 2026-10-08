"""Model 8 — HTF Demand/Supply zones, W1/D1/H4 (R1 §5, LOCKED_DECISIONS §21/§22/§26).

Zone identification ONLY (Step 1 of the §21 flow — no M5-approach / M1
trigger logic yet):

* Order Block: the candle immediately BEFORE the first candle of a FVG
  (R1 §3.1); zone = the OB candle's full range; demand if the FVG is bullish.
* Fair Value Gap: gap zone from `smc.detection.detect_fvgs`.
* Demand/Supply zones (§22): the SINGLE last opposing candle before a strong
  impulse (move >= DISPLACEMENT_MIN_ATR over the next N_BAR_LTF candles);
  zone = that opposing candle's full high-low range.

Zones are scanned per HTF timeframe (W1/D1/H4) and emitted with their own
timeframe. W1 is the above-daily context tier added by the Lead Architect
weekly-provisioning directive (2026-10-06): same scanner, same frozen
constants, no new thresholds — a W1 zone is a context POI exactly like a
D1/H4 one. When a D1 and an H4 zone of the same direction overlap in price,
both POIs get ``htf_overlap=True`` (quality-score +0.10 applied later by
the confluence scorer, §26). The overlap pairing remains D1×H4 (frozen
§26 rule): W1 is deliberately NOT added to the pairing so quality scores
are untouched by provisioning.
"""

from __future__ import annotations

from smc.config.locked_constants import DISPLACEMENT_MIN_ATR, N_BAR_LTF
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
from smc.core.swing import Swing
from smc.core.zone import Zone
from smc.detection.fvg_detector import detect_fvgs
from smc.poi.base_model import POIModel, zone_for_candle
from smc.utils.atr import latest_atr
__all__ = ["M8HtfDemandSupply", "M8_KIND_PRIORITY", "collapse_episodes"]


HTF_TIMEFRAMES = (Timeframe.W1, Timeframe.D1, Timeframe.H4)

# F1 episode-uniqueness: one geometric episode → one POI. Kind priority
# when several facets share identical bounds (ob > demand_supply; fvg is
# the residual category — order documented, not tuned).
M8_KIND_PRIORITY = {"ob": 0, "demand_supply": 1, "fvg": 2}


def _episode_key(zone) -> tuple:
    """Geometric episode identity: rounded bounds (direction excluded so
    opposite-direction conflicts on one geometry collide by design)."""
    return (round(float(zone.bottom), 3), round(float(zone.top), 3))


def collapse_episodes(items: list[tuple]) -> list[tuple]:
    """Collapse raw ``(kind, direction, start_index, zone)`` yields so one
    geometric episode produces exactly one tuple.

    Winner per episode: kind priority (ob > demand_supply > fvg), then
    direction name ascending (LONG-first, arbitrary-but-deterministic),
    then earliest origin. Winners return in chronological (origin) order.
    Pure function — no series access, fully unit-testable.
    """
    groups: dict[tuple, list] = {}
    for kind, direction, start, zone in items:
        groups.setdefault(_episode_key(zone), []).append(
            (kind, direction, start, zone))
    winners = [
        min(members, key=lambda m: (
            M8_KIND_PRIORITY.get(m[0], 99),
            m[1].name,
            m[2],
        ))
        for members in groups.values()
    ]
    winners.sort(key=lambda w: (w[2], M8_KIND_PRIORITY.get(w[0], 99)))
    return winners


class M8HtfDemandSupply(POIModel):
    """Multi-timeframe zone identification on D1/H4 (§21 Step 1)."""

    tag = ModelType.M8

    def __init__(
        self,
        timeframe: Timeframe,
        htf_candles: dict[Timeframe, list[Candle]] | None = None,
        atr_period: int = 14,
    ) -> None:
        super().__init__(timeframe, atr_period=atr_period)
        self.htf_candles: dict[Timeframe, list[Candle]] = dict(htf_candles or {})

    def detect(
        self,
        candles: list[Candle],
        swings: list[Swing],
        liquidity_levels: list[LiquidityLevel],
    ) -> list[POI]:
        pois: list[POI] = []
        for tf in HTF_TIMEFRAMES:
            series = self.htf_candles.get(tf)
            if not series:
                continue
            pois.extend(self._scan_timeframe(series, tf))
        self._flag_overlaps(pois)
        return pois

    # ------------------------------------------------------------------ #
    def _scan_timeframe(self, series: list[Candle], tf: Timeframe) -> list[POI]:
        pois: list[POI] = []
        latest: dict[tuple[Direction, str], tuple] = {}  # most recent per kind
        for kind, direction, _start, zone in self._zones(series, tf):
            latest[(direction, kind)] = (zone, kind)
        for (direction, _kind), (zone, kind) in latest.items():
            pois.append(
                POI(
                    zone=zone,
                    models=[self.tag],
                    htf_overlap=False,
                    m8_kind=kind,
                )
            )
        return pois

    def _zones(self, series: list[Candle], tf: Timeframe):
        """Yield (kind, direction, start_index, Zone) for OB/FVG/DS zones.

        F1 episode uniqueness: yields are collected and collapsed so one
        geometric episode produces exactly one tuple — never LONG and SHORT
        on the same bounds, never two kinds differing only by facet on the
        same bounds + direction. Winner per episode: kind priority
        (ob > demand_supply > fvg), then direction name ascending
        (LONG-first, arbitrary-but-deterministic), then earliest origin.
        Winners yield in chronological (origin) order.
        """
        raw: list[tuple] = []
        for fvg in detect_fvgs(series, tf):
            direction = fvg.zone.direction
            # FVG zone itself.
            raw.append(("fvg", direction, fvg.start_index, fvg.zone))
            # OB = candle immediately before the first FVG candle (R1 §3.1).
            ob_index = fvg.start_index - 1
            if ob_index >= 0:
                ob = series[ob_index]
                raw.append(("ob", direction, ob_index,
                            zone_for_candle(ob, direction, tf)))
        # Demand / Supply zones (§22): single last opposing candle.
        window = N_BAR_LTF
        for i in range(len(series) - window):
            candle = series[i]
            horizon = series[i + 1 : i + 1 + window]
            atr = latest_atr(series[: i + 1], self.atr_period)
            if atr is None:
                continue
            if candle.is_bearish:
                rise = max(c.high for c in horizon) - candle.low
                if rise >= DISPLACEMENT_MIN_ATR * atr:
                    raw.append(("demand_supply", Direction.LONG, i,
                                zone_for_candle(candle, Direction.LONG, tf)))
            elif candle.is_bullish:
                fall = candle.high - min(c.low for c in horizon)
                if fall >= DISPLACEMENT_MIN_ATR * atr:
                    raw.append(("demand_supply", Direction.SHORT, i,
                                zone_for_candle(candle, Direction.SHORT, tf)))
        for kind, direction, start, zone in collapse_episodes(raw):
            yield kind, direction, start, zone

    def _flag_overlaps(self, pois: list[POI]) -> None:
        """Set htf_overlap when a D1 and an H4 zone overlap in price (§21/§26)."""
        d1 = [p for p in pois if p.zone.timeframe is Timeframe.D1]
        h4 = [p for p in pois if p.zone.timeframe is Timeframe.H4]
        for a in d1:
            for b in h4:
                if a.zone.direction is not b.zone.direction:
                    continue
                if a.zone.bottom <= b.zone.top and b.zone.bottom <= a.zone.top:
                    a.htf_overlap = True
                    b.htf_overlap = True