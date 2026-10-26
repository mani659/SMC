"""Multi-timeframe detection cascade (FR-1).

Runs the frozen single-TF detection stack once per configured detection
timeframe (H4 + H1 minimum per R2) over caller-supplied series, sharing
one HTF candle map so Model 8 is fed rather than silent (R1). M1/M5 stay
execution / trigger timeframes — this module never routes or sizes.

Composition, not a shadow pipeline: every timeframe reuses
:class:`~smc.orchestration.detection_driver.DetectionDriver` (Stage 0/1 →
merge → validate) and one caller-owned
:class:`~smc.orchestration.engine.PipelineEngine`. No thresholds, no
trigger geometry, no risk logic lives here.

Loudness contract (FR-1 acceptance): a required detection timeframe with
no supplied series raises ``ValueError`` naming every missing timeframe —
a run can never silently degrade to M1-only and claim multi-TF. Explicit
opt-in degraded mode (``missing_ok=True``) records per-TF errors and
marks the result degraded instead.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.orchestration.detection_driver import DetectionDriver
from smc.orchestration.engine import PipelineEngine

__all__ = [
    "MultiTFDetectionDriver",
    "MultiTFDriverResult",
    "PerTFResult",
    "check_single_tf_detect_exec",
]

#: HTF series Model 8 reads (R1 §5, LOCKED_DECISIONS §21/§22).
#: W1 added 2026-10-06 (weekly-provisioning directive): a supplied weekly
#: series is shared into M8's map the same way D1/H4 are, so weekly zones
#: are emitted as context POIs. Missing W1 stays OPTIONAL (unlike the
#: required H4/H1 detection minimum) — the runtime decides, loudly.
M8_HTF_TIMEFRAMES = (Timeframe.W1, Timeframe.D1, Timeframe.H4)


def check_single_tf_detect_exec(
    detection_timeframes, execution_timeframe: Timeframe
) -> bool:
    """True when detection adds nothing above the execution timeframe.

    Non-compliant for FR-1: detection running solely on the execution TF
    (e.g. M1-only detect+exec) collapses the cascade. Empty detection set
    also returns True (nothing multi-TF happened).
    """
    evaluated = set(detection_timeframes)
    if not evaluated:
        return True
    return evaluated <= {execution_timeframe}


@dataclass(frozen=True, slots=True)
class PerTFResult:
    """One detection timeframe's batch outcome."""

    timeframe: Timeframe
    detected_raw: int
    merged: int
    passed: int
    first_failure: dict = field(default_factory=dict)
    skipped_models: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MultiTFDriverResult:
    """Whole-cascade outcome (per-TF streams; no cross-TF merge in FR-1)."""

    per_tf: dict
    single_tf_detect_exec: bool
    degraded: bool = False
    errors: dict = field(default_factory=dict)
    # FR-4: populated only when validate_multi(..., return_details=True).
    # Maps TF -> {"passed": [...], "results": [...], "disp_map": {...}}
    # so callers can arm + feed route context without re-deriving.
    details: dict = field(default_factory=dict)

    def counts_by_tf(self) -> dict:
        """Per-TF detection counts for run summaries."""
        return {
            tf: {"detected_raw": r.detected_raw, "merged": r.merged,
                 "passed": r.passed}
            for tf, r in self.per_tf.items()
        }


class MultiTFDetectionDriver:
    """Run frozen detection once per configured detection timeframe.

    ``htf_candles`` is an explicit override map; series supplied for D1/H4
    detection are additionally shared into Model 8's map automatically, so
    M8 cannot stay silent by accident when its data is present.
    """

    def __init__(
        self,
        detection_timeframes=(Timeframe.H4, Timeframe.H1),
        execution_timeframe: Timeframe = Timeframe.M5,
        htf_candles: dict[Timeframe, list[Candle]] | None = None,
        atr_period: int = 14,
        missing_ok: bool = False,
    ) -> None:
        if not detection_timeframes:
            raise ValueError("MultiTFDetectionDriver needs ≥1 detection timeframe")
        self.detection_timeframes = tuple(detection_timeframes)
        self.execution_timeframe = execution_timeframe
        self.htf_candles: dict[Timeframe, list[Candle]] = dict(htf_candles or {})
        self.atr_period = atr_period
        self.missing_ok = missing_ok

    def validate_multi(
        self,
        series_by_tf: dict[Timeframe, list[Candle]],
        engine: PipelineEngine | None = None,
        arm_bars: dict[Timeframe, int] | None = None,
        return_details: bool = False,
    ) -> MultiTFDriverResult:
        """Validate one batch per detection timeframe (no cross-TF merge).

        ``arm_bars`` maps timeframe → arm anchor; when provided, passed POIs
        are armed at their timeframe's anchor (mirrors the live loop's
        arm-only-new contract at batch granularity). Default ``None`` =
        validate-only, exactly like ``DetectionDriver.validate_window``.
        ``return_details`` attaches per-TF passed POIs, validation results
        and displacement maps for callers that arm/feed context themselves
        (FR-4 loop with geometric dedup); default off keeps the result light.
        """
        missing = [tf for tf in self.detection_timeframes
                   if not series_by_tf.get(tf)]
        if missing and not self.missing_ok:
            raise ValueError(
                "multi-TF detection requires series for: "
                + ", ".join(tf.name for tf in missing)
                + " (pass series_by_tf entries or opt into missing_ok=True)"
            )
        engine = engine if engine is not None else PipelineEngine()
        # M8's map: explicit overrides win; detection series for D1/H4 double
        # as M8 input so a supplied HTF series can never leave M8 unfed.
        htf_map: dict[Timeframe, list[Candle]] = dict(self.htf_candles)
        for tf in M8_HTF_TIMEFRAMES:
            if tf not in htf_map and series_by_tf.get(tf):
                htf_map[tf] = series_by_tf[tf]

        per_tf: dict[Timeframe, PerTFResult] = {}
        errors: dict[Timeframe, str] = {}
        evaluated: list[Timeframe] = []
        details: dict[Timeframe, dict] = {}
        for tf in self.detection_timeframes:
            series = series_by_tf.get(tf)
            if not series:
                errors[tf] = f"no {tf.name} series supplied"
                continue
            driver = DetectionDriver(
                tf, htf_candles=htf_map or None, atr_period=self.atr_period
            )
            passed, results, _run, skipped, detected = driver.validate_window(
                series, engine=engine, merge_first=True
            )
            if arm_bars is not None and tf in arm_bars:
                for poi in passed:
                    engine.arm_at(poi, arm_bar=arm_bars[tf])
            failures = Counter(
                r.first_failure.name if r.first_failure is not None else "PASS"
                for r in results
            )
            per_tf[tf] = PerTFResult(
                timeframe=tf, detected_raw=len(detected), merged=len(results),
                passed=len(passed), first_failure=dict(failures),
                skipped_models=dict(skipped),
            )
            evaluated.append(tf)
            if return_details:
                details[tf] = {
                    "passed": list(passed),
                    "results": list(results),
                    "disp_map": driver.attribute_displacement(detected, _run),
                }
        return MultiTFDriverResult(
            per_tf=per_tf,
            single_tf_detect_exec=check_single_tf_detect_exec(
                evaluated, self.execution_timeframe),
            degraded=bool(errors),
            errors={tf.name: msg for tf, msg in errors.items()},
            details=details,
        )
