"""Phase 7 — live main loop: connector → detection → paper/live cycle + heartbeat.

Composes the EXISTING frozen stack exactly as the backtest does — one
engine, one §5 machine, one M4 ``PipelineAdapter``, one ``RiskEngine`` —
plus the Phase 7 additions (rolling-window detection driver, heartbeat
publisher):

    connector (MT5Connector or fake)
      → poll new closed bars (execution timeframe)
      → rolling detection window → DetectionDriver.validate_window
           → arm ONLY newly-passed POIs into the engine (the adapter drives
             the engine's scan/feed each bar — no re-arm, §24 anchors stay)
      → PaperRunner.run_one_cycle(bar) — the same bar-close cycle as M6,
        with the REAL adapter (scan → risk gate → broker limit)
      → heartbeat published continuously (interval-bounded, injected clock)

Integration contract (Phase 7 brief): initialize connector → start heartbeat
→ per new bar: detection driver validate/arm, then one live/paper cycle →
keep heartbeat updated throughout → clean stop on shutdown request.

Safety posture:

* ``start()`` refuses to run when the connector cannot initialize.
* ``stop()`` writes a ``shutdown`` heartbeat so operators can tell a clean
  stop from a crash. The MQL5 Safety Watchdog does NOT distinguish — it
  treats any stale/unreadable heartbeat as dead-Python and emergency-closes
  (fail-closed). See ``smc.live.heartbeat`` for the tested decision spec.
* ``run_once()`` is a single poll (no sleep, no wall clock beyond the
  injected heartbeat clock) — the deterministic seam tests drive.
* Cold start: the FIRST poll only records the latest bar timestamp; history
  is not replayed through the live cycle (only genuinely NEW closed bars
  are processed after startup).

V1 limitations (documented, nothing faked): the driver is fed the execution-
timeframe window only — M8's HTF series are not provisioned in V1 (the
registry registers M8 but it emits nothing without HTF candles); the
O(bars²) per-bar window rescan is accepted for the demo window size.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.orchestration.detection_driver import DetectionDriver
from smc.paper.runner import PaperRunner

__all__ = ["LiveLoop"]


class LiveLoop:
    """Bar-poll live loop over the frozen stack (Python owns the brain)."""

    def __init__(
        self,
        *,
        connector,
        runner: PaperRunner,
        driver: DetectionDriver,
        heartbeat,
        symbol: str = "XAUUSD.x",
        timeframe: Timeframe = Timeframe.M5,
        window_bars: int = 200,
        poll_interval: float = 0.5,
    ) -> None:
        self.connector = connector
        self.runner = runner
        self.driver = driver
        self.heartbeat = heartbeat
        self.symbol = symbol
        self.timeframe = timeframe
        self.window_bars = window_bars
        self.poll_interval = poll_interval
        self._window: list[Candle] = []
        self._last_bar_ts: datetime | None = None
        self._started = False
        self._running = False

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start(self) -> bool:
        """Initialize the connector; refuse to run when it fails."""
        connect = getattr(self.connector, "connect", None)
        if callable(connect):
            ok = bool(connect())
        else:
            initialize = getattr(self.connector, "initialize", None)
            ok = bool(initialize() if callable(initialize) else False)
        if not ok:
            self._started = False
            return False
        self._started = True
        return True

    def stop(self) -> None:
        """Clean stop: stop polling and mark the heartbeat as shutdown.

        The watchdog treats this the same as a crash (stale heartbeat →
        emergency close); the ``shutdown`` marker is for operators only.
        """
        self._running = False
        self.heartbeat.publish_shutdown()

    # ------------------------------------------------------------------ #
    # Polling
    # ------------------------------------------------------------------ #
    def run_once(self) -> int:
        """One poll: fetch new bars, process each, publish the heartbeat.

        Returns the number of NEW bars processed (0 when the poll found no
        new closed bar). The FIRST poll records the latest bar timestamp
        without replaying history through the live cycle.
        """
        if not self._started:
            raise RuntimeError("LiveLoop.start() must succeed before run_once()")
        processed = 0
        for bar in self._fetch_new_bars():
            self._window.append(bar)
            self._arm_new_pois()
            self.runner.run_one_cycle(bar)
            processed += 1
        self.heartbeat.maybe_publish()
        return processed

    def run(self) -> None:
        """Blocking loop: ``run_once`` + poll-interval sleep until ``stop()``."""
        if not self.start():
            raise RuntimeError("connector failed to initialize — refusing to run")
        self._running = True
        try:
            while self._running:
                self.run_once()
                time.sleep(self.poll_interval)
        finally:
            self.stop()

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _fetch_new_bars(self) -> list[Candle]:
        """Closed bars newer than the last processed bar (broker truth)."""
        raw = self.connector.copy_rates(
            self.symbol, self.timeframe, 0, self.window_bars + 1
        )
        if raw is None:
            return []
        bars = [self._to_candle(row, self.timeframe) for row in raw]
        bars.sort(key=lambda b: b.timestamp)
        if self._last_bar_ts is None:
            # Cold start: anchor to the latest bar; do not replay history.
            self._last_bar_ts = bars[-1].timestamp if bars else None
            return []
        new_bars = [b for b in bars if b.timestamp > self._last_bar_ts]
        if new_bars:
            self._last_bar_ts = new_bars[-1].timestamp
        return new_bars

    def _arm_new_pois(self) -> int:
        """Validate the rolling window and arm ONLY newly-passed POIs.

        ``validate_window`` never arms; a POI already tracked by the engine
        (episode exists) keeps its §24 arm-bar anchor and §11 one-shot. A
        protocol-conformant adapter stub without an ``engine`` simply skips
        arming (documented — the loop's detection wiring targets the real
        adapter). Returns the number of newly armed POIs.
        """
        engine = getattr(self.runner.adapter, "engine", None)
        if engine is None:
            return 0
        passed, _results, _run, _skipped, _detected = self.driver.validate_window(
            self._window, engine=engine, merge_first=True
        )
        armed = 0
        for poi in passed:
            if engine.episode(poi) is None:
                engine.arm_at(poi, arm_bar=len(self._window) - 1)
                armed += 1
        return armed

    @staticmethod
    def _to_candle(row, timeframe: Timeframe) -> Candle:
        """Map an MT5-style rate row (numpy record or dict) to a Candle."""
        ts = datetime.fromtimestamp(int(row["time"]), tz=timezone.utc)
        return Candle(
            timestamp=ts,
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            timeframe=timeframe,
        )