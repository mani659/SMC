"""Product HTF detection-series hygiene for research harnesses.

The shipped product runtime requires the master-card POI inventory set
`(D1, H4, H1, M15)` (`LOCKED_DECISIONS` §4b, `PRODUCT_RUNTIME_CONTRACT` §1).
A harness that supplies only H1/H4/D1 therefore makes every batch fail loudly
and can report an empty funnel that looks like "no setups".

This helper is the one place that:

* keeps any pre-built HTF series the caller already has;
* derives every missing product timeframe from a **finer** series by
  resampling (M1 or M5 → M15 / H1 / H4 / D1) and drops the last bucket unless
  it has fully closed by the source's last close (**no lookahead**);
* validates strictly ascending, tz-aware timestamps;
* fails loudly, naming the missing timeframes, when a required series cannot
  be produced.

No strategy logic, no thresholds, no product-runtime change.
"""

from __future__ import annotations

from datetime import timedelta

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.data.resample import resample_ohlcv

__all__ = [
    "PRODUCT_DETECTION_TIMEFRAMES",
    "MissingProductHtfSeries",
    "assert_product_detection_complete",
    "ensure_product_detection_frames",
]

#: Master-card product POI inventory (LOCKED_DECISIONS §4b / contract §1).
PRODUCT_DETECTION_TIMEFRAMES = (
    Timeframe.D1,
    Timeframe.H4,
    Timeframe.H1,
    Timeframe.M15,
)

#: The subset every product diagnostic can always produce from M5/M1.
ALWAYS_DERIVABLE = (Timeframe.M15, Timeframe.H1, Timeframe.H4)


class MissingProductHtfSeries(ValueError):
    """Raised when a product-mode detection series cannot be supplied."""


def _close_time(candle: Candle):
    return candle.timestamp + timedelta(minutes=candle.timeframe.minutes)


def _drop_unclosed(bars: list[Candle], timeframe: Timeframe,
                   source_last: Candle) -> list[Candle]:
    """Drop the trailing bucket unless it closed by the source's last close."""
    if not bars:
        return []
    if _close_time(bars[-1]) <= _close_time(source_last):
        return bars
    return bars[:-1]


def _validate(timeframe: Timeframe, bars: list[Candle]) -> None:
    if bars[0].timestamp.tzinfo is None:
        raise ValueError(
            f"{timeframe.name} series has naive timestamps; product detection "
            "requires tz-aware UTC bars"
        )
    for previous, current in zip(bars, bars[1:]):
        if not previous.timestamp < current.timestamp:
            raise ValueError(
                f"{timeframe.name} series is not strictly ascending at "
                f"{current.timestamp!r}"
            )


def ensure_product_detection_frames(
    frames: dict[Timeframe, list[Candle]] | None,
    *,
    source: list[Candle] | None = None,
    require_d1: bool = True,
) -> dict[Timeframe, list[Candle]]:
    """Return a product-complete HTF map, deriving missing TFs by resampling.

    ``frames`` may hold any subset of the product timeframes (e.g. H1/H4/D1
    loaded by a frozen harness). ``source`` is a finer series (M1 or M5) used
    to derive every missing timeframe with closed-bar semantics. Raises
    :class:`MissingProductHtfSeries` naming each timeframe that is still
    missing — never returns a silently incomplete map.
    """
    out: dict[Timeframe, list[Candle]] = {
        timeframe: list(series)
        for timeframe, series in (frames or {}).items()
        if series
    }
    missing = [tf for tf in PRODUCT_DETECTION_TIMEFRAMES if tf not in out]
    if missing and source:
        for timeframe in missing:
            derived = _drop_unclosed(
                resample_ohlcv(source, timeframe), timeframe, source[-1]
            )
            if derived:
                out[timeframe] = derived

    required = list(PRODUCT_DETECTION_TIMEFRAMES)
    if not require_d1:
        required.remove(Timeframe.D1)
    still_missing = [tf for tf in required if not out.get(tf)]
    if still_missing:
        names = ", ".join(tf.name for tf in still_missing)
        hint = (
            "supply the series or pass a finer `source` series to resample"
            if source else "pass a finer `source` series (M1/M5) to resample"
        )
        raise MissingProductHtfSeries(
            f"product detection series missing: {names} — {hint}"
        )

    for timeframe in PRODUCT_DETECTION_TIMEFRAMES:
        series = out.get(timeframe)
        if series:
            _validate(timeframe, series)
    return out


def assert_product_detection_complete(
    frames: dict[Timeframe, list[Candle]] | None,
    *,
    require_d1: bool = True,
) -> None:
    """Raise :class:`MissingProductHtfSeries` naming what is absent/empty."""
    required = list(PRODUCT_DETECTION_TIMEFRAMES)
    if not require_d1:
        required.remove(Timeframe.D1)
    missing = [tf for tf in required if not (frames or {}).get(tf)]
    if missing:
        names = ", ".join(tf.name for tf in missing)
        raise MissingProductHtfSeries(
            f"product detection series missing: {names}"
        )
