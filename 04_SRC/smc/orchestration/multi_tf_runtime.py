"""C1 — the ONE product multi-TF runtime seam (research = paper = live).

Contract: ``00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md`` (Phase 0, 2026-09-23).

This module is a **facade**, not a second detection stack: it composes the
frozen pieces exactly as the accepted research chain does —

    HTF series (H4 + H1 required, D1 optional for M8)
      → MultiTFDetectionDriver.validate_multi (per-TF frozen drivers,
        one caller-owned PipelineEngine, M8's D1/H4 map shared)
      → per-TF details (passed POIs, ValidationResults, displacement map)
      → geometry dedup (ZoneDedup — same direction + overlapping zone is
        ONE episode; the research chain's ZoneRegistry rule, now shared)
      → engine.arm_at for NEWLY passed POIs only (episode/arm-bar preserved)
      → adapter.note_route_context (logging-only identity context)

Loud-fail policy (contract §3):

* Product mode (default): required H1/H4 series missing or empty ⇒
  ``MissingHtfSeriesError`` naming every missing timeframe; nothing arms.
* ``allow_single_tf_degraded=True`` (tests only): explicit opt-in to the
  legacy single-TF ``DetectionDriver.validate_window`` path; the report is
  stamped ``degraded=True`` with a reason. There is NO automatic fallback.
* Poisoned input (non-ascending HTF series, malformed rows) raises — the
  runtime never trusts silently.

No thresholds, no trigger geometry, no risk logic lives here. Everything
comes from the frozen modules; the runtime only orchestrates + counts.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from datetime import datetime

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.orchestration.detection_driver import DetectionDriver
from smc.orchestration.engine import PipelineEngine
from smc.orchestration.multi_tf import (
    M8_HTF_TIMEFRAMES,
    MultiTFDetectionDriver,
    MultiTFDriverResult,
)

__all__ = [
    "MissingHtfSeriesError",
    "ZoneDedup",
    "MultiTFBatchReport",
    "MultiTFProductRuntime",
    "REQUIRED_DETECTION_TIMEFRAMES",
    "OPTIONAL_W1_TIMEFRAME",
    "OPTIONAL_D1_TIMEFRAME",
    "DEFAULT_HTF_WINDOW_BARS",
    "build_htf_prefixes",
    "missing_required_series",
]

#: Required detection timeframes (R2 minimum — H4 + H1).
REQUIRED_DETECTION_TIMEFRAMES = (Timeframe.H4, Timeframe.H1)

#: Optional above-daily HTF context series (weekly) — M8 scans it when a
#: series is available; never required for a session to run. Added by the
#: 2026-10-06 weekly-provisioning directive (Lead Architect).
OPTIONAL_W1_TIMEFRAME = Timeframe.W1

#: Optional HTF series supplied to M8 when available (contract §1).
OPTIONAL_D1_TIMEFRAME = Timeframe.D1

#: Default HTF fetch depth per timeframe (live/paper provisioning bound).
DEFAULT_HTF_WINDOW_BARS = 300


class MissingHtfSeriesError(ValueError):
    """Raised when required HTF series are missing in product mode.

    Loud by design: the product runtime MUST NOT silently collapse to
    single-TF detection (see contract §3). The message names every missing
    timeframe and the explicit degraded flag that would allow the fallback.
    """


def missing_required_series(
    series_by_tf: dict, required=(Timeframe.H4, Timeframe.H1)
) -> tuple[Timeframe, ...]:
    """Required timeframes with no usable (non-empty) series supplied."""
    missing: list[Timeframe] = []
    for tf in required:
        series = series_by_tf.get(tf) if isinstance(series_by_tf, dict) else None
        if not series:
            missing.append(tf)
    return tuple(missing)


def _timestamps(series: list[Candle]) -> list[datetime]:
    """Ascending timestamps with a loud disorder check (poisoned input)."""
    stamps: list[datetime] = []
    previous: datetime | None = None
    for candle in series:
        ts = getattr(candle, "timestamp", None)
        if ts is None:
            raise ValueError("HTF series contains a candle without a timestamp")
        if previous is not None and not previous <= ts:
            raise ValueError(
                "HTF series must be strictly ascending; disorder at "
                f"{ts!r}"
            )
        stamps.append(ts)
        previous = ts
    return stamps


def build_htf_prefixes(
    series_by_tf: dict, as_of: datetime
) -> dict:
    """Honest prefixes: bars with ``timestamp <= as_of`` (per timeframe).

    Mirrors the accepted research cadence exactly (bisect on timestamps,
    ``bisect_right`` semantics) — the current FORMING HTF bar is included,
    future bars never are. Timestamps are assumed ascending; disorder
    raises loudly (never silently reorder).
    """
    prefixes: dict = {}
    for tf, series in (series_by_tf or {}).items():
        if not series:
            prefixes[tf] = []
            continue
        stamps = _timestamps(series)
        cut = bisect.bisect_right(stamps, as_of)
        prefixes[tf] = list(series[:cut])
    return prefixes


class ZoneDedup:
    """Geometric episode dedup: same direction + overlapping zone.

    Byte-for-byte the rule the accepted research chain used
    (``fr4_fidelity_baseline.ZoneRegistry``): two zones of the same
    direction whose spans overlap are the same episode, so the same POI
    re-detected by a later HTF batch is never armed twice. Shared here so
    live/paper/research all dedup identically (POI ids are uuid4, so
    identity comparison alone is not enough).
    """

    def __init__(self) -> None:
        self._zones: list[tuple[str, float, float]] = []

    def seen(self, zone) -> bool:
        """True when an equivalent (same-direction, overlapping) zone exists."""
        top = float(zone.top)
        bottom = float(zone.bottom)
        direction = str(getattr(zone, "direction", ""))
        for known_direction, known_top, known_bottom in self._zones:
            if known_direction != direction:
                continue
            if known_top >= bottom and top >= known_bottom:
                return True
        return False

    def register(self, zone) -> None:
        """Record a zone as an armed episode (rounded to 6dp, as research)."""
        self._zones.append(
            (str(getattr(zone, "direction", "")),
             round(float(zone.top), 6), round(float(zone.bottom), 6))
        )

    def __len__(self) -> int:
        return len(self._zones)


@dataclass(slots=True)
class MultiTFBatchReport:
    """Outcome of ONE product detection batch (machine-readable)."""

    as_of: datetime | None
    arm_bar: int
    batches: int = 1
    per_tf: dict = field(default_factory=dict)       # tf name → counts dict
    armed: list = field(default_factory=list)         # newly armed POIs
    duplicates: list = field(default_factory=list)    # skipped duplicate ids
    skipped_tracked: list = field(default_factory=list)  # already-tracked ids
    degraded: bool = False
    degraded_reason: str | None = None
    missing: tuple = ()                               # missing TF names
    single_tf_detect_exec: bool = False
    skipped_models: dict = field(default_factory=dict)
    errors: dict = field(default_factory=dict)
    # L1 observability (2026-10-06 structure console): POI id → sweep-link
    # info {"side", "magnitude_atr", "passed"} for every passed POI whose
    # displacement context paired it with a liquidity sweep this batch.
    # Logging/display ONLY — never read by scan, risk, or fill decisions.
    displacements: dict = field(default_factory=dict)

    @property
    def armed_count(self) -> int:
        return len(self.armed)

    def summary(self) -> dict:
        """Compact dict for logging / KPI records (no POI objects)."""
        return {
            "batches": self.batches,
            "as_of": self.as_of.isoformat() if self.as_of is not None else None,
            "arm_bar": self.arm_bar,
            "per_tf": dict(self.per_tf),
            "armed": len(self.armed),
            "duplicates": len(self.duplicates),
            "skipped_tracked": len(self.skipped_tracked),
            "degraded": self.degraded,
            "degraded_reason": self.degraded_reason,
            "missing": list(self.missing),
            "single_tf_detect_exec": self.single_tf_detect_exec,
            "skipped_models": dict(self.skipped_models),
            "errors": dict(self.errors),
        }


class MultiTFProductRuntime:
    """The one product detection/arming seam (contract §2).

    Holds NO strategy logic: it composes ``MultiTFDetectionDriver`` (the
    frozen implementation), the caller's ``PipelineEngine``, and the shared
    ``ZoneDedup``. Batch state (batch counter, dedup) lives here so
    live/paper keep the same cadence and the same episode dedup.

    Timeframe roles (weekly-provisioning directive 2026-10-06):

    * ``detection_timeframes`` — REQUIRED set; a missing series for any of
      these raises ``MissingHtfSeriesError`` (loud, product mode).
    * ``optional_timeframes`` — provisioned context (W1, D1); a missing
      series is tolerated and simply means fewer context zones. Adding W1
      to the detection set via operator config makes it required and the
      loud-fail applies to it too.
    """

    def __init__(
        self,
        *,
        execution_timeframe: Timeframe = Timeframe.M5,
        detection_timeframes=(Timeframe.H4, Timeframe.H1),
        optional_timeframes=(OPTIONAL_W1_TIMEFRAME, OPTIONAL_D1_TIMEFRAME),
        atr_period: int = 14,
        allow_single_tf_degraded: bool = False,
        supply_d1_to_m8: bool = True,
    ) -> None:
        if not detection_timeframes:
            raise ValueError("detection_timeframes must name at least one timeframe")
        detection_tuple = tuple(detection_timeframes)
        if not allow_single_tf_degraded:
            # Product-mode detection policy (unified audit ruling 2026-10-06,
            # superseding amendment recorded in LOCKED_DECISIONS §4/§21):
            # the H4+H1 required detection minimum is enforced AT CONSTRUCTION
            # — a product runtime cannot be built whose detection set omits
            # either required timeframe. Degraded opt-in skips the check.
            missing = [tf.name for tf in (Timeframe.H4, Timeframe.H1)
                       if tf not in detection_tuple]
            if missing:
                raise ValueError(
                    "product mode requires H4+H1 in detection_timeframes; "
                    "missing: " + ", ".join(missing)
                    + " (set allow_single_tf_degraded=True only for explicit "
                      "degraded opt-in / tests)"
                )
        self.execution_timeframe = execution_timeframe
        self.detection_timeframes = detection_tuple
        self.optional_timeframes = tuple(optional_timeframes)
        self.atr_period = atr_period
        self.allow_single_tf_degraded = bool(allow_single_tf_degraded)
        self.supply_d1_to_m8 = bool(supply_d1_to_m8)
        self.dedup = ZoneDedup()
        self.batches = 0
        self._fallback_driver: DetectionDriver | None = None

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #
    @property
    def required_timeframes(self) -> tuple:
        """Detection timeframes this runtime refuses to run without."""
        return self.detection_timeframes

    def missing_series(self, series_by_tf: dict) -> tuple:
        """Required timeframes with no usable series in ``series_by_tf``."""
        return missing_required_series(series_by_tf, self.required_timeframes)

    def single_tf_detect_exec(self) -> bool:
        """True when the configured detection set collapses on execution TF."""
        evaluated = set(self.detection_timeframes)
        if not evaluated:
            return True
        return evaluated <= {self.execution_timeframe}

    # ------------------------------------------------------------------ #
    # Batch
    # ------------------------------------------------------------------ #
    def run_batch(
        self,
        *,
        engine: PipelineEngine,
        series_by_tf: dict,
        as_of: datetime | None = None,
        arm_bar: int = 0,
        adapter=None,
        execution_candles: list | None = None,
        dedup: ZoneDedup | None = None,
    ) -> MultiTFBatchReport:
        """Run ONE detection batch and arm newly passed POIs (contract §2).

        ``series_by_tf`` carries the HTF series (H4/H1 required; D1 optional
        and forwarded to M8 when ``supply_d1_to_m8``). ``execution_candles``
        is the execution-TF series and is required only for the explicit
        degraded fallback. ``adapter`` (optional) receives the logging-only
        ``note_route_context`` hook when it exposes one. ``dedup`` overrides
        the runtime-owned registry (tests); default = the runtime's own.
        """
        zone_dedup = dedup if dedup is not None else self.dedup
        missing = self.missing_series(series_by_tf)
        if missing:
            names = ", ".join(tf.name for tf in missing)
            if not self.allow_single_tf_degraded:
                raise MissingHtfSeriesError(
                    f"product multi-TF runtime is missing required series for: "
                    f"{names} — refusing to fall back to single-TF detection "
                    f"(set allow_single_tf_degraded=True only for tests)"
                )
            return self._run_degraded(
                engine=engine,
                missing=missing,
                execution_candles=execution_candles,
                as_of=as_of,
                arm_bar=arm_bar,
                adapter=adapter,
                dedup=zone_dedup,
            )

        driver, driver_series = self._build_driver(series_by_tf)
        result: MultiTFDriverResult = driver.validate_multi(
            driver_series, engine=engine, return_details=True
        )
        self.batches += 1
        skipped_models: dict = {}
        for tf, per_tf in (getattr(result, "per_tf", {}) or {}).items():
            name = getattr(tf, "name", str(tf))
            for model, reason in (getattr(per_tf, "skipped_models", {}) or {}).items():
                skipped_models[f"{name}:{model}"] = reason
        report = MultiTFBatchReport(
            as_of=as_of,
            arm_bar=arm_bar,
            batches=self.batches,
            per_tf=self._per_tf_counts(result),
            single_tf_detect_exec=bool(result.single_tf_detect_exec),
            skipped_models=skipped_models,
            errors=dict(getattr(result, "errors", {}) or {}),
        )
        self._arm_passed(
            engine=engine,
            result=result,
            arm_bar=arm_bar,
            adapter=adapter,
            dedup=zone_dedup,
            report=report,
        )
        return report

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _build_driver(self, series_by_tf: dict):
        """Driver + per-TF series map (D1/H4 forwarded to M8 when present)."""
        driver_series = {
            tf: series_by_tf[tf]
            for tf in self.detection_timeframes
            if series_by_tf.get(tf)
        }
        htf_map: dict = {}
        if self.supply_d1_to_m8:
            for tf in M8_HTF_TIMEFRAMES:
                if tf is self.execution_timeframe:
                    continue
                if series_by_tf.get(tf):
                    htf_map[tf] = series_by_tf[tf]
        driver = MultiTFDetectionDriver(
            detection_timeframes=self.detection_timeframes,
            execution_timeframe=self.execution_timeframe,
            htf_candles=htf_map or None,
            atr_period=self.atr_period,
        )
        return driver, driver_series

    def _per_tf_counts(self, result) -> dict:
        counts: dict = {}
        for tf, per_tf in (getattr(result, "per_tf", {}) or {}).items():
            name = getattr(tf, "name", str(tf))
            counts[name] = {
                "detected_raw": int(getattr(per_tf, "detected_raw", 0)),
                "merged": int(getattr(per_tf, "merged", 0)),
                "passed": int(getattr(per_tf, "passed", 0)),
            }
        return counts

    def _arm_passed(self, *, engine, result, arm_bar, adapter, dedup, report) -> None:
        """Arm only NEWLY passed POIs (episode + geometry dedup), in TF order."""
        note = getattr(adapter, "note_route_context", None) if adapter is not None else None
        for tf, info in (getattr(result, "details", {}) or {}).items():
            if not info:
                continue
            results_by_id = {r.poi.id: r for r in info.get("results", [])}
            disp_map = info.get("disp_map", {}) or {}
            # L1 sweep links (display only): every passed POI with a paired
            # displacement gets its sweep side retained on the report.
            for poi in info.get("passed", []):
                disp = disp_map.get(poi.id)
                if disp is None:
                    continue
                direction = getattr(disp, "direction", None)
                report.displacements[poi.id] = {
                    "side": getattr(direction, "name", None),
                    "magnitude_atr": getattr(disp, "magnitude_atr", None),
                    "passed": getattr(disp, "passed", None),
                }
            for poi in info.get("passed", []):
                if engine.episode(poi) is not None:
                    report.skipped_tracked.append(poi.id)
                    continue
                if dedup.seen(poi.zone):
                    report.duplicates.append(poi.id)
                    continue
                if note is not None:
                    try:
                        from smc.backtest.pipeline_bridge import pillar_path_summary
                        res = results_by_id.get(poi.id)
                        note(poi.id, displacement=disp_map.get(poi.id),
                             pillar_path=(pillar_path_summary(res)
                                          if res is not None else None))
                    except Exception:  # noqa: BLE001 — identity never blocks arming
                        pass
                try:
                    engine.arm_at(poi, arm_bar=arm_bar)
                except Exception as exc:  # noqa: BLE001 — one POI never kills the batch
                    report.errors[poi.id] = f"{type(exc).__name__}: {exc}"
                    continue
                dedup.register(poi.zone)
                report.armed.append(poi)

    def _fallback_single_tf(self) -> DetectionDriver:
        """Lazily built legacy driver for the EXPLICIT degraded mode only."""
        if self._fallback_driver is None:
            self._fallback_driver = DetectionDriver(
                self.execution_timeframe, atr_period=self.atr_period
            )
        return self._fallback_driver

    def _run_degraded(
        self,
        *,
        engine,
        missing,
        execution_candles,
        as_of,
        arm_bar,
        adapter,
        dedup,
    ) -> MultiTFBatchReport:
        """Explicit test-only fallback: single-TF detection on the exec series."""
        if not execution_candles:
            raise MissingHtfSeriesError(
                "degraded single-TF fallback needs the execution series; "
                "none was supplied (missing: "
                + ", ".join(tf.name for tf in missing) + ")"
            )
        result = self._fallback_single_tf().validate_window(
            list(execution_candles), engine=engine, merge_first=True
        )
        passed, results, _run, skipped, detected = result
        self.batches += 1
        report = MultiTFBatchReport(
            as_of=as_of,
            arm_bar=arm_bar,
            batches=self.batches,
            per_tf={self.execution_timeframe.name: {
                "detected_raw": len(detected),
                "merged": len(results),
                "passed": len(passed),
            }},
            degraded=True,
            degraded_reason=(
                "allow_single_tf_degraded=True (tests only) — missing: "
                + ", ".join(tf.name for tf in missing)
            ),
            missing=tuple(tf.name for tf in missing),
            single_tf_detect_exec=True,
            skipped_models=dict(skipped or {}),
        )
        note = getattr(adapter, "note_route_context", None) if adapter is not None else None
        results_by_id = {r.poi.id: r for r in results}
        from smc.backtest.pipeline_bridge import pillar_path_summary
        for poi in passed:
            if engine.episode(poi) is not None:
                report.skipped_tracked.append(poi.id)
                continue
            if dedup.seen(poi.zone):
                report.duplicates.append(poi.id)
                continue
            if note is not None:
                try:
                    res = results_by_id.get(poi.id)
                    note(poi.id, displacement=None,
                         pillar_path=(pillar_path_summary(res)
                                      if res is not None else None))
                except Exception:  # noqa: BLE001
                    pass
            try:
                engine.arm_at(poi, arm_bar=arm_bar)
            except Exception as exc:  # noqa: BLE001
                report.errors[poi.id] = f"{type(exc).__name__}: {exc}"
                continue
            dedup.register(poi.zone)
            report.armed.append(poi)
        return report
