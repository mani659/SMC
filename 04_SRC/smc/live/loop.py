"""Phase 7 — live main loop: connector → detection → paper/live cycle + heartbeat.

Composes the EXISTING frozen stack exactly as the backtest does — one
engine, one §5 machine, one M4 ``PipelineAdapter``, one ``RiskEngine`` —
plus the Phase 7 additions (heartbeat publisher) and the C1 product seam
(one multi-TF runtime shared by research/paper/live):

    connector (MT5Connector or fake)
      → poll new closed bars (execution timeframe)
      → on a NEW H1 close: product multi-TF batch (H4 + H1 detection,
        D1 supplied to M8 when available) through
        :class:`~smc.orchestration.multi_tf_runtime.MultiTFProductRuntime`
        → arm ONLY newly-passed POIs (episode + geometry dedup)
      → PaperRunner.run_one_cycle(bar) — the same bar-close cycle as M6,
        with the REAL adapter (scan → risk gate → broker limit)
      → heartbeat published continuously (interval-bounded, injected clock)

C1 contract (``00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md``):

* **Product mode** = a runtime is configured. Required HTF series missing ⇒
  ``MissingHtfSeriesError`` — the batch arms nothing, the error is recorded
  loudly (``arm_errors`` / ``last_arm_error``) and NO single-TF fallback
  happens. ``start()`` additionally refuses to start when the HTF probe
  finds no usable H1/H4 series.
* **Degraded mode** (tests only) = ``allow_single_tf_degraded=True``: the
  explicit opt-in to the legacy single-TF path; never the default.
* **Legacy mode** (compatibility) = no runtime and a ``DetectionDriver``
  supplied: the pre-C1 single-TF behaviour, kept for the Phase 7 tests and
  logged as legacy on first use.

Integration contract (Phase 7 brief): initialize connector → start heartbeat
→ per new bar: detection batch, then one live/paper cycle → keep heartbeat
updated throughout → clean stop on shutdown request.

Safety posture:

* ``start()`` refuses to run when the connector cannot initialize, or when
  product-mode HTF provisioning fails (C1 §3.4).
* ``stop()`` writes a ``shutdown`` heartbeat so operators can tell a clean
  stop from a crash. The MQL5 Safety Watchdog does NOT distinguish — it
  treats any stale/unreadable heartbeat as dead-Python and emergency-closes
  (fail-closed). See ``smc.live.heartbeat`` for the tested decision spec.
* ``run_once()`` is a single poll (no sleep, no wall clock beyond the
  injected heartbeat clock) — the deterministic seam tests drive.
* Cold start: the FIRST poll only records the latest bar timestamp; history
  is not replayed through the live cycle (only genuinely NEW closed bars
  are processed after startup).

V1 limitations (documented, nothing faked): the HTF history is a bounded
fetch (``htf_window_bars`` per timeframe) — deep-history warm-up is not
provisioned; the O(bars²) per-bar execution-window rescan is accepted for
the demo window size.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone

from smc.backtest.pipeline_bridge import pillar_path_summary
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.orchestration.detection_driver import DetectionDriver
from smc.orchestration.multi_tf_runtime import (
    DEFAULT_HTF_WINDOW_BARS,
    MissingHtfSeriesError,
    MultiTFProductRuntime,
)
from smc.paper.runner import PaperRunner

__all__ = ["LiveLoop"]

logger = logging.getLogger(__name__)


class LiveLoop:
    """Bar-poll live loop over the frozen stack (Python owns the brain)."""

    def __init__(
        self,
        *,
        connector,
        runner: PaperRunner,
        driver: DetectionDriver | None = None,
        heartbeat,
        symbol: str = "XAUUSD.x",
        timeframe: Timeframe = Timeframe.M5,
        window_bars: int = 200,
        poll_interval: float = 0.5,
        runtime: MultiTFProductRuntime | None = None,
        htf_window_bars: int = DEFAULT_HTF_WINDOW_BARS,
        htf_fetch=None,
        include_d1: bool = True,
        allow_single_tf_degraded: bool | None = None,
        dumb_mtf_feed=None,
        menu_confirmation=None,
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
        self.dumb_mtf_feed = dumb_mtf_feed
        # Product menu (sweep → LTF confirmation). Optional: absent in
        # research/legacy modes and in every pre-menu test seam.
        self.menu_confirmation = menu_confirmation
        if menu_confirmation is not None:
            adapter = getattr(runner, "adapter", None)
            if adapter is not None:
                set_menu = getattr(adapter, "set_menu_confirmation", None)
                if callable(set_menu):
                    set_menu(menu_confirmation)
                elif hasattr(adapter, "menu_confirmation"):
                    adapter.menu_confirmation = menu_confirmation
        # C1 product seam. Resolution order: explicit runtime → the runner's
        # own runtime (paper builds one by default) → legacy single-TF path.
        self.runtime = (
            None if dumb_mtf_feed is not None
            else runtime if runtime is not None else getattr(runner, "runtime", None)
        )
        if allow_single_tf_degraded is not None and self.runtime is not None:
            # Explicit operator/test override of the runtime's contract flag.
            self.runtime.allow_single_tf_degraded = bool(allow_single_tf_degraded)
        self.htf_window_bars = int(htf_window_bars)
        self.htf_fetch = htf_fetch
        # HTF timeframes to provision: the runtime's detection set plus its
        # optional context set (weekly provisioning 2026-10-06: W1, D1) so
        # above-daily context series are fetched live in product mode. The
        # batch CADENCE is untouched — still keyed on the H1 close; W1 is
        # fetched/detected only and never becomes an execution timeframe.
        tfs: list[Timeframe] = []
        if menu_confirmation is not None:
            # Product menu streams: detection TFs (sweeps) + confirmation TFs
            # (trigger evaluation). The execution TF is the polled bar itself
            # and is never fetched as an HTF series.
            tfs.extend(menu_confirmation.detection_timeframes)
            tfs.extend(menu_confirmation.confirmation_timeframes)
        if dumb_mtf_feed is not None:
            # DUMB-MTF first slice: H4 source POIs plus optional M15
            # confirmation. The M5 execution feed is already polled.
            tfs.extend((Timeframe.H4, Timeframe.M15))
        elif self.runtime is not None:
            supply_d1 = include_d1 and self.runtime.supply_d1_to_m8
            tfs.extend(self.runtime.detection_timeframes)
            for tf in self.runtime.optional_timeframes:
                # D1 remains governed by the include_d1 / supply_d1_to_m8
                # flags (pre-existing contract); W1 and any future optional
                # context TF is provisioned unconditionally.
                if tf is Timeframe.D1 and not supply_d1:
                    continue
                tfs.append(tf)
            if supply_d1:
                tfs.append(Timeframe.D1)
        else:
            tfs.extend((Timeframe.H4, Timeframe.H1))
            if include_d1:
                tfs.append(Timeframe.D1)
        seen: list[Timeframe] = []
        for tf in tfs:
            if tf is not self.timeframe and tf not in seen:
                seen.append(tf)
        self.htf_timeframes: tuple[Timeframe, ...] = tuple(seen)
        # Observability (operator board / events.log / tests).
        self.htf_batches = 0
        self.arm_errors = 0
        self.last_arm_error: str | None = None
        self.last_report = None
        # L1 structure console (2026-10-06): cumulative sweep links —
        # POI id → {"side", "magnitude_atr", "passed"} — merged from each
        # batch report. Display only; no decision reads this.
        self.sweep_links: dict[str, dict] = {}
        self._last_htf_close: datetime | None = None
        self._legacy_warned = False
        self._active_htf_fetch_errors: dict[Timeframe, tuple[str, str]] = {}

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start(self) -> bool:
        """Initialize the connector; refuse when HTF provisioning fails.

        C1 §3.4: in product mode (runtime present, degradation not opted
        into) a session must not begin without usable H1/H4 series — the
        probe uses the same fetch path the batches use.
        """
        connect = getattr(self.connector, "connect", None)
        if callable(connect):
            ok = bool(connect())
        else:
            initialize = getattr(self.connector, "initialize", None)
            ok = bool(initialize() if callable(initialize) else False)
        if not ok:
            self._started = False
            return False
        if self.runtime is not None and not self.runtime.allow_single_tf_degraded:
            series = self._fetch_htf_series()
            missing = self.runtime.missing_series(series)
            if missing:
                names = ", ".join(tf.name for tf in missing)
                self.last_arm_error = (
                    f"HTF probe failed — no usable series for: {names} "
                    f"(product mode refuses to start; set "
                    f"allow_single_tf_degraded=True only for tests)"
                )
                logger.error("%s", self.last_arm_error)
                self.arm_errors += 1
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
        if self.heartbeat is not None:
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
            if self.dumb_mtf_feed is not None:
                self._drive_dumb_mtf(bar)
            else:
                self._detect_and_arm(bar)
                # Product menu runs AFTER the detection batch armed this
                # bar's POIs (one-shot sweep → confirm window).
                self._drive_menu_confirmation(bar)
            self.runner.run_one_cycle(bar)
            processed += 1
        if self.heartbeat is not None:
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
        if self.dumb_mtf_feed is not None:
            # MT5 position 0 includes its still-forming current candle. The
            # DUMB-MTF contract is stricter than the legacy live path: every
            # touch/sweep/confirmation input must be closed, so omit it here.
            bars = bars[:-1]
        if self._last_bar_ts is None:
            # Cold start: anchor to the latest bar; do not replay history.
            self._last_bar_ts = bars[-1].timestamp if bars else None
            return []
        new_bars = [b for b in bars if b.timestamp > self._last_bar_ts]
        if new_bars:
            self._last_bar_ts = new_bars[-1].timestamp
        return new_bars

    # ------------------------------------------------------------------ #
    # C1 — detection batch dispatch
    # ------------------------------------------------------------------ #
    def _drive_dumb_mtf(self, bar: Candle) -> None:
        """Dispatch the opt-in DUMB-MTF H4 slice using closed external bars."""
        h4 = self._closed_before(
            self._fetch_htf(Timeframe.H4, self.htf_window_bars), bar
        )
        m15 = self._latest_closed_before(
            self._fetch_htf(Timeframe.M15, self.htf_window_bars), bar
        )
        self.dumb_mtf_feed.on_m5_closed(bar, h4_closed=h4, m15_closed=m15)

    @staticmethod
    def _closed_before(bars: list[Candle], reference: Candle) -> list[Candle]:
        """Retain only bars complete by the execution bar's timestamp."""
        return [
            candidate for candidate in bars
            if candidate.timestamp + timedelta(minutes=candidate.timeframe.minutes)
            <= reference.timestamp
        ]

    @staticmethod
    def _closed_at(bars: list[Candle], as_of: datetime) -> list[Candle]:
        """Bars CLOSED at or before ``as_of`` (menu stream prefix, no lookahead)."""
        out: list[Candle] = []
        for bar in bars or ():
            close = bar.timestamp + timedelta(minutes=bar.timeframe.minutes)
            if close <= as_of:
                out.append(bar)
        return out

    def _latest_closed_before(self, bars: list[Candle], reference: Candle) -> Candle | None:
        closed = self._closed_before(bars, reference)
        return closed[-1] if closed else None

    def _detect_and_arm(self, bar: Candle) -> int:
        """Run the product multi-TF batch on a new H1 close (C1 cadence).

        Returns the number of newly armed POIs. In legacy mode (no runtime)
        the pre-C1 single-TF path runs, warned once — loud, never silent.
        """
        if self.runtime is None:
            if self.driver is None:
                raise RuntimeError(
                    "LiveLoop has no detection source: supply a "
                    "MultiTFProductRuntime (product mode) or a DetectionDriver"
                )
            if not self._legacy_warned:
                self._legacy_warned = True
                logger.warning(
                    "LiveLoop running LEGACY single-TF detection (no runtime "
                    "configured) — not compliant with the product runtime "
                    "contract"
                )
            return self._arm_new_pois(bar)
        try:
            return self._arm_product(bar)
        except MissingHtfSeriesError as exc:
            self.arm_errors += 1
            self.last_arm_error = str(exc)
            logger.error("multi-TF batch refused (loud): %s", exc)
            return 0

    def _arm_product(self, bar: Candle) -> int:
        """Fetch HTF series, run one batch when the H1 bar advanced."""
        series = self._fetch_htf_series()
        missing = self.runtime.missing_series(series)
        degraded = bool(self.runtime.allow_single_tf_degraded)
        if missing and not degraded:
            names = ", ".join(tf.name for tf in missing)
            raise MissingHtfSeriesError(
                "product multi-TF batch cannot run: no usable series for "
                f"{names} (connector/feed returned nothing)"
            )
        if not missing:
            h1 = series.get(Timeframe.H1) or []
            current_h1 = h1[-1].timestamp
            if (self._last_htf_close is not None
                    and current_h1 == self._last_htf_close):
                return 0  # same H1 bar — the batch cadence has not advanced
            self._last_htf_close = current_h1
        # Degraded mode (no usable HTF): one batch per new execution bar —
        # the legacy single-TF rhythm, explicit and reported as degraded.
        arm_bar = max(len(self._window) - 1, 0)
        report = self._run_seam_batch(
            series, as_of=bar.timestamp, arm_bar=arm_bar
        )
        self.htf_batches += 1
        self.last_report = report
        links = getattr(report, "displacements", None) or {}
        if isinstance(links, dict) and links:
            self.sweep_links.update(links)
        logger.info("multi-TF batch: %s", report.summary())
        if self.menu_confirmation is not None:
            # F5: the batch's decision instant is the arm instant
            # (``as_of`` above = this closed execution bar's open stamp, the
            # same instant the closed-bar HTF prefixes were cut at). A sweep
            # that closed at or before it is pre-arm and cannot open the POI.
            for poi in getattr(report, "armed", ()) or ():
                det_tf = getattr(getattr(poi, "zone", None), "timeframe", None)
                if det_tf is not None:
                    self.menu_confirmation.register_armed(
                        poi, det_tf, armed_ts=bar.timestamp
                    )
        return report.armed_count

    def _drive_menu_confirmation(self, bar: Candle) -> None:
        """Feed the product menu its closed detection + confirmation streams.

        Runs once per closed execution bar, AFTER the detection batch armed
        this bar's POIs: the layer checks the newly closed detection bar for a
        locked R2 sweep, opens the tier's one-shot window (20 detection-TF
        bars), evaluates A/D/F on the tier's own confirmation streams, and
        queues the first valid winner into the pipeline adapter so it enters
        the SAME risk/order seam as a routed POI (nothing is placed here).
        """
        menu = self.menu_confirmation
        if menu is None:
            return
        needed = tuple(dict.fromkeys(
            (*menu.detection_timeframes, *menu.confirmation_timeframes)
        ))
        # The execution bar IS closed (the runner only ever sees closed bars),
        # so the honest "as of" instant is its close, not its open.
        as_of = bar.timestamp + timedelta(minutes=self.timeframe.minutes)
        closed: dict = {}
        for tf in needed:
            if tf is self.timeframe:
                # Never fetched as an HTF series — it is the bar being processed.
                closed[tf] = [bar]
                continue
            try:
                series = self._fetch_htf(tf, self.htf_window_bars)
            except Exception as exc:  # noqa: BLE001 — one stream never kills the loop
                logger.error(
                    "menu stream fetch failed operation=copy_rates "
                    "timeframe=%s error=%r", tf.name, exc, exc_info=True,
                )
                closed[tf] = []
                continue
            closed[tf] = self._closed_at(series, as_of)
        try:
            winners = menu.on_execution_bar(closed, as_of=as_of)
        except Exception as exc:  # noqa: BLE001 — loud, never fatal mid-session
            self.arm_errors += 1
            self.last_arm_error = f"menu_confirmation: {type(exc).__name__}: {exc}"
            logger.error("menu confirmation failed: %r", exc, exc_info=True)
            return
        if not winners:
            return
        adapter = getattr(self.runner, "adapter", None)
        queue = getattr(adapter, "queue_menu_candidate", None)
        if not callable(queue):
            self.arm_errors += 1
            self.last_arm_error = (
                "menu confirmation produced winners but the pipeline adapter "
                "cannot queue them (no queue_menu_candidate)"
            )
            logger.error("menu confirmation cannot deliver winners (no adapter seam)")
            return
        for winner in winners:
            queue(winner.candidate)
            logger.info(
                "menu confirmation WON tier=%s detect=%s confirm=%s trigger=%s "
                "poi=%s",
                winner.tier_name, winner.detection_tf.name,
                winner.confirmation_tf.name, winner.trigger, winner.poi_id,
            )
        self._record_menu_confirm_kpi(winners, as_of)

    def _record_menu_confirm_kpi(self, winners, now: datetime) -> None:
        """OPT-1 confirm-vs-zone export: one structured KPI event per winner.

        Audit only, same class as the existing ``entry_blocked`` /
        ``place_skip`` records: the KPI log is never read by a risk verdict,
        a placement or an eligibility decision (exercised by test). Fields are
        carried from the candidate's ``product_menu`` enrich stamp verbatim —
        missing/unresolvable values stay ``None`` (never invented here).
        """
        kpi = getattr(self.runner, "kpi", None)
        if kpi is None:
            return   # KPI-less runners (test stubs) lose nothing but the log
        for winner in winners:
            try:
                payload = json.loads(winner.candidate.signal_data_json or "{}")
                stamp = payload.get("product_menu") or {}
            except (TypeError, ValueError):
                stamp = {}
            try:
                kpi.record(
                    "menu_confirm",
                    at=now,
                    episode_id=winner.episode_id,
                    poi_id=winner.poi_id,
                    tier=winner.tier_name,
                    detection_tf=winner.detection_tf.name,
                    confirmation_tf=winner.confirmation_tf.name,
                    trigger=winner.trigger,
                    route_id=winner.candidate.route_id,
                    sweep_ts=stamp.get("sweep_ts"),
                    completion_ts=stamp.get("completion_ts"),
                    completion_close=stamp.get("completion_close"),
                    atr_at_confirm=stamp.get("atr_at_confirm"),
                    distance_at_confirm_atr=stamp.get(
                        "distance_at_confirm_atr"),
                    label_at_confirm=stamp.get("label_at_confirm"),
                )
            except Exception as exc:  # noqa: BLE001 — audit log never fatal
                logger.warning(
                    "menu_confirm KPI record failed poi=%s error=%r",
                    winner.poi_id, exc,
                )

    def _run_seam_batch(self, series_by_tf: dict, *, as_of, arm_bar: int):
        """Dispatch the batch to the SHARED seam (paper runner or runtime)."""
        seam = getattr(self.runner, "arm_multi_tf", None)
        if callable(seam):
            return seam(
                series_by_tf,
                as_of=as_of,
                arm_bar=arm_bar,
                execution_candles=self._window,
            )
        adapter = getattr(self.runner, "adapter", None)
        engine = getattr(adapter, "engine", None)
        if engine is None:
            raise RuntimeError(
                "no arming target: runner exposes neither arm_multi_tf nor a "
                "real adapter engine"
            )
        return self.runtime.run_batch(
            engine=engine,
            series_by_tf=series_by_tf,
            as_of=as_of,
            arm_bar=arm_bar,
            adapter=adapter,
            execution_candles=self._window,
        )

    def _fetch_htf_series(self) -> dict:
        """Bounded HTF series per configured timeframe (empty list on failure).

        A failed fetch yields ``[]`` for that timeframe — the runtime's
        missing-series policy is the single decision point (loud raise in
        product mode, degraded fallback only when explicitly enabled).
        """
        out: dict = {}
        for tf in self.htf_timeframes:
            try:
                bars = self._fetch_htf(tf, self.htf_window_bars)
            except Exception as exc:  # noqa: BLE001 — decision lives in the runtime
                signature = (type(exc).__name__, str(exc))
                if self._active_htf_fetch_errors.get(tf) != signature:
                    logger.error(
                        "HTF fetch failed operation=copy_rates timeframe=%s "
                        "error=%r",
                        tf.name,
                        exc,
                        exc_info=True,
                    )
                else:
                    logger.debug(
                        "Repeated HTF fetch failure operation=copy_rates "
                        "timeframe=%s error=%r",
                        tf.name,
                        exc,
                    )
                self._active_htf_fetch_errors[tf] = signature
                out[tf] = []
            else:
                if self._active_htf_fetch_errors.pop(tf, None) is not None:
                    logger.info(
                        "HTF fetch recovered operation=copy_rates timeframe=%s",
                        tf.name,
                    )
                out[tf] = bars
        return out

    def _fetch_htf(self, tf: Timeframe, count: int) -> list[Candle]:
        """HTF bars for ``tf``: injected feed first, else connector rates."""
        if self.htf_fetch is not None:
            rows = self.htf_fetch(tf, count)
            if rows is None:
                return []
            bars = list(rows)
            if bars and not isinstance(bars[0], Candle):
                bars = [self._to_candle(row, tf) for row in bars]
            bars.sort(key=lambda b: b.timestamp)
            return bars
        raw = self.connector.copy_rates(self.symbol, tf, 0, count)
        if raw is None:
            return []
        rows = [self._to_candle(row, tf) for row in raw]
        rows.sort(key=lambda b: b.timestamp)
        return rows

    def _arm_new_pois(self, bar: Candle) -> int:
        """LEGACY single-TF arming (pre-C1): validate the rolling window.

        Kept only for the legacy mode (no runtime) — the product path is
        :meth:`_arm_product`. ``validate_window`` never arms; a POI already
        tracked by the engine (episode exists) keeps its §24 arm-bar anchor
        and §11 one-shot. A protocol-conformant adapter stub without an
        ``engine`` simply skips arming (documented — the loop's detection
        wiring targets the real adapter). Returns the number newly armed.
        """
        engine = getattr(self.runner.adapter, "engine", None)
        if engine is None:
            return 0
        passed, _results, _run, _skipped, _detected = self.driver.validate_window(
            self._window, engine=engine, merge_first=True
        )
        # Identity context (logging only): retain each newly-passed POI's
        # displacement + pillar path on the adapter so routed candidates
        # carry them. Stub adapters without the hook simply skip this.
        adapter = getattr(self.runner, "adapter", None)
        note = getattr(adapter, "note_route_context", None)
        results_by_id = {r.poi.id: r for r in _results}
        disp_map: dict = {}
        if note is not None:
            try:
                disp_map = self.driver.attribute_displacement(_detected, _run)
            except Exception:                    # noqa: BLE001 — identity never blocks arming
                disp_map = {}
        armed = 0
        for poi in passed:
            if engine.episode(poi) is None:
                if note is not None:
                    res = results_by_id.get(poi.id)
                    note(poi.id,
                         displacement=disp_map.get(poi.id),
                         pillar_path=pillar_path_summary(res) if res is not None else None)
                engine.arm_at(poi, arm_bar=len(self._window) - 1)
                armed += 1
                if self.menu_confirmation is not None:
                    det_tf = getattr(getattr(poi, "zone", None), "timeframe", None) or self.timeframe
                    # F5: same contract — the arm instant is the instant this
                    # closed-bar pass decided on (the bar's open stamp, i.e.
                    # the batch ``as_of`` convention).
                    self.menu_confirmation.register_armed(
                        poi, det_tf, armed_ts=bar.timestamp
                    )
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
