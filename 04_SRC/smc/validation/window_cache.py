"""Per-detection-window artifact cache (Phase C perf patch — exact).

Batch validation over one detection window previously re-derived
O(window) artifacts per POI: pillar 1 re-ran ``detect_fvgs`` for every
POI (and re-scanned each candidate's full mitigation suffix), and the
per-sweep displacement checks re-ran FVG detection + an O(window) ATR
rebuild per sweep (hoisted separately — see ``DetectionDriver.stage0``).

:class:`WindowCache` holds each of those artifacts ONCE per window:

* ``fvgs`` — the window's ``detect_fvgs`` list (same inputs → same
  list, so reuse is value-identical). Every zone validated in a window
  is stamped with the window's own detection timeframe, so the cached
  list matches the timeframe each POI's pillar-1 read would pass.
* ``atr_values`` — the window's full Wilder ATR series; the tail is
  exactly ``latest_atr(window)`` (same fold, same final value).
* ``min_close_suffix`` / ``max_close_suffix`` — suffix min/max of the
  CLOSES, ``len == len(candles) + 1`` (sentinels ±inf at the empty
  suffix). Pillar 1's mitigation rule ("price closed beyond the zone's
  opposite extreme after it formed") reads ``exists j >= k:
  close[j] < bottom`` (LONG) / ``close[j] > top`` (SHORT) — the suffix
  min/max answers both with the identical comparison set, so every
  per-candidate O(window) suffix re-scan becomes two O(1) reads.
"""

from __future__ import annotations

from dataclasses import dataclass

from smc.core.candle import Candle

__all__ = ["WindowCache"]


@dataclass(slots=True)
class WindowCache:
    """Once-per-window artifacts shared by every POI validated on it."""

    fvgs: list | None = None                 # detect_fvgs(window) — shared
    atr_values: list | None = None           # atr_series(window) — shared
    min_close_suffix: list[float] | None = None  # closes suffix min, len N+1
    max_close_suffix: list[float] | None = None  # closes suffix max, len N+1

    @classmethod
    def build(
        cls,
        candles: list[Candle],
        *,
        fvgs: list | None = None,
        atr_values: list | None = None,
    ) -> "WindowCache":
        """Build the suffix arrays in O(N); attach pre-computed artifacts.

        ``min_close_suffix[k]`` is ``min(c.close for c in candles[k:])``
        (+inf for the empty suffix) and ``max_close_suffix[k]`` the max
        (-inf) — the same closes the per-candidate re-scans compared.
        """
        n = len(candles)
        mins: list[float] = [float("inf")] * (n + 1)
        maxs: list[float] = [float("-inf")] * (n + 1)
        lo = float("inf")
        hi = float("-inf")
        for i in range(n - 1, -1, -1):
            close = candles[i].close
            if close < lo:
                lo = close
            if close > hi:
                hi = close
            mins[i] = lo
            maxs[i] = hi
        return cls(
            fvgs=fvgs,
            atr_values=atr_values,
            min_close_suffix=mins,
            max_close_suffix=maxs,
        )
