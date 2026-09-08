"""Model 8 — HTF Demand/Supply zones, D1/H4 (R1 §5, LOCKED_DECISIONS §21/§22/§26).

Zone identification ONLY (Step 1 of the §21 flow — no M5-approach / M1
trigger logic yet):

* Order Block: the candle immediately BEFORE the first candle of a FVG
  (R1 §3.1); zone = the OB candle's full range; demand if the FVG is bullish.
* Fair Value Gap: gap zone from `smc.detection.detect_fvgs`.
* Demand/Supply zones (§22): the SINGLE last opposing candle before a strong
  impulse (move >= DISPLACEMENT_MIN_ATR over the next N_BAR_LTF candles);
  zone = that opposing candle's full high-low range.

Zones are scanned per HTF timeframe (D1/H4) and emitted with their own
timeframe. When a D1 and an H4 zone of the same direction overlap in price,
both POIs get ``htf_overlap=True`` (quality-score +0.10 applied later by
the confluence scorer, §26).
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

__all__ = ["M8HtfDemandSupply"]

HTF_TIMEFRAMES = (Timeframe.D1, Timeframe.H4)


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
        latest: dict[tuple[Direction, str], Zone] = {}  # most recent zone per kind
        for kind, direction, _start, zone in self._zones(series, tf):
            latest[(direction, kind)] = zone  # keep only the latest of each kind
        for (direction, _kind), zone in latest.items():
            pois.append(
                POI(
                    zone=zone,
                    models=[self.tag],
                    htf_overlap=False,
                )
            )
        return pois

    def _zones(self, series: list[Candle], tf: Timeframe):
        """Yield (kind, direction, start_index, Zone) for OB/FVG/DS zones."""
        for fvg in detect_fvgs(series, tf):
            direction = fvg.zone.direction
            # FVG zone itself.
            yield "fvg", direction, fvg.start_index, fvg.zone
            # OB = candle immediately before the first FVG candle (R1 §3.1).
            ob_index = fvg.start_index - 1
            if ob_index >= 0:
                ob = series[ob_index]
                yield "ob", direction, ob_index, zone_for_candle(ob, direction, tf)
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
                    yield "demand_supply", Direction.LONG, i, zone_for_candle(
                        candle, Direction.LONG, tf
                    )
            elif candle.is_bullish:
                fall = candle.high - min(c.low for c in horizon)
                if fall >= DISPLACEMENT_MIN_ATR * atr:
                    yield "demand_supply", Direction.SHORT, i, zone_for_candle(
                        candle, Direction.SHORT, tf
                    )

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