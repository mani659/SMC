"""Coherence patch (CR1) — detection driver: raw candles → validated/armed POIs.

Closes the Stage 0/1 → Stage 2 handoff that previously existed only as
unit-test recipes: this driver is the PRODUCTION path from raw candle
history to validated, armed POIs, composed entirely from existing frozen
pieces:

    candles (+ optional HTF series for M8)
        → swings           (smc.detection.structural_swing_detector.detect_swings)
        → liquidity levels (smc.detection.liquidity_scanner.scan)
        → sweeps           (smc.detection.sweep_detector.detect_sweeps)
        → displacement     (smc.detection.displacement_checker.check_displacement,
                            attributed per POI — see :meth:`attribute_displacement`)
        → M1–M8 detect     (smc.poi.model_registry.build_registry)
        → merge + validate (PipelineEngine.validate — Pillar 2 fed from the
                            honest sweep-displacement map)
        → arm_at           (PipelineEngine.arm_at)

Honesty rules (V1, documented):

* A POI whose zone direction has NO preceding sweep in that direction gets
  NO displacement entry — Pillar 2 then rejects it (UNAVAILABLE, fail-fast).
  The driver never invents displacement. Callers with an external Stage 0
  may inject ``swings`` / ``liquidity_levels`` / ``displacement_map`` (the
  M4 Pillar-2 injection contract) — the auto paths above are the defaults.
* A model whose ``detect`` raises on the supplied window is SKIPPED with
  the exception recorded (``DriverResult.skipped_models``) — one model
  never kills the run.
* No MT5, no wall clock, no randomness: the same candles produce the same
  POIs (callers may inject POI ids / ``created_at`` from the run clock for
  byte-identical identity, per the Phase 7 evidence-run note).
* ``arm_bar`` defaults to the last detection-window bar — the §24 give-up
  anchor; a bar-loop caller passes its own current bar index instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, PoolType
from smc.core.liquidity_level import LiquidityLevel
from smc.core.poi import POI
from smc.core.swing import Swing
from smc.detection.displacement_checker import DisplacementResult, check_displacement
from smc.detection.liquidity_scanner import ALL_FAMILIES, scan as scan_liquidity
from smc.detection.structural_swing_detector import detect_swings
from smc.detection.sweep_detector import SweepResult, detect_sweeps
from smc.orchestration.engine import PipelineEngine
from smc.poi.base_model import most_recent_swing
from smc.poi.model_registry import ModelRegistry, build_registry
from smc.validation.validation_pipeline import ValidationResult

__all__ = ["DetectionDriver", "DetectionRun", "DriverResult"]


@dataclass(slots=True)
class DetectionRun:
    """Stage 0/1 raw outputs for one detection window.

    ``displacements`` pairs each sweep's candle index with its §3
    displacement result — the recency anchor for per-POI attribution.
    """

    swings: list[Swing]
    liquidity_levels: list[LiquidityLevel]
    sweeps: list[SweepResult]
    displacements: list[tuple[int, DisplacementResult]]


@dataclass(slots=True)
class DriverResult:
    """Outcome of one :meth:`DetectionDriver.run` batch."""

    passed: list[POI]                     # merged + validated + armed POIs
    results: list[ValidationResult]       # one per merged POI (validate order)
    detected: list[POI]                   # raw model output (pre-merge)
    run: DetectionRun                     # the Stage 0/1 raw detections
    skipped_models: dict[str, str]        # model tag → skip reason (never fatal)
    arm_bar: int                          # the arm anchor used this run


class DetectionDriver:
    """Batch detect → validate → arm over the frozen Stage 0/1–4 pieces.

    Reusable by the backtest runner (per-window batch) and the paper/live
    driver (per rolling window) — the driver holds no bar-loop state.
    """

    def __init__(
        self,
        timeframe: Timeframe,
        *,
        atr_period: int = 14,
        htf_candles: dict[Timeframe, list] | None = None,
        registry: ModelRegistry | None = None,
        include_liquidity: tuple[str, ...] = ALL_FAMILIES,
    ) -> None:
        self.timeframe = timeframe
        self.atr_period = atr_period
        self.htf_candles = htf_candles or {}
        self.registry = registry or build_registry(
            timeframe, htf_candles=self.htf_candles, atr_period=atr_period
        )
        self.include_liquidity = include_liquidity

    # ------------------------------------------------------------------ #
    # Stage 0/1 — raw detection
    # ------------------------------------------------------------------ #
    def stage0(self, candles: list[Candle]) -> DetectionRun:
        """Swings → liquidity levels → sweeps → displacement (auto path)."""
        swings = detect_swings(candles, self.timeframe)
        levels = scan_liquidity(candles, self.timeframe, include=self.include_liquidity)
        sweeps = detect_sweeps(candles, levels)
        displacements: list[tuple[int, DisplacementResult]] = []
        for sweep in sweeps:
            result = self._displacement_for_sweep(candles, swings, sweep)
            if result is not None:
                displacements.append((sweep.candle_index, result))
        return DetectionRun(swings=swings, liquidity_levels=levels,
                            sweeps=sweeps, displacements=displacements)

    def _displacement_for_sweep(
        self,
        candles: list[Candle],
        swings: list[Swing],
        sweep: SweepResult,
    ) -> DisplacementResult | None:
        """§3 displacement after one sweep (honest, never invented).

        Direction follows the pool: an SSL (sell-side) sweep precedes a
        LONG impulse, a BSL sweep a SHORT impulse. The BOS level is the
        most recent prior swing extreme of the move direction (prior swing
        low for LONG / high for SHORT) — the level price swept is that
        extreme's proxy, but the checker's contract is the actual prior
        extreme. No prior extreme before the sweep → ``None`` (the POI
        attribution then has nothing to feed — Pillar 2 rejects).
        """
        if sweep.pool is PoolType.SSL:
            direction = Direction.LONG
            prior = most_recent_swing(
                swings, is_high=False, before_index=sweep.candle_index
            )
        else:
            direction = Direction.SHORT
            prior = most_recent_swing(
                swings, is_high=True, before_index=sweep.candle_index
            )
        if prior is None:
            return None
        return check_displacement(
            candles, direction, sweep.candle_index, prior.level, self.atr_period
        )

    # ------------------------------------------------------------------ #
    # Stage 2 inputs — model detection + displacement attribution
    # ------------------------------------------------------------------ #
    def detect_pois(
        self,
        candles: list[Candle],
        swings: list[Swing],
        liquidity_levels: list[LiquidityLevel],
    ) -> tuple[list[POI], dict[str, str]]:
        """Run every registered model over the window; skips are recorded.

        Returns ``(pois, skipped_models)`` — a model that raises on the
        supplied window is skipped with its reason (fail clearly, never
        silently pass, never kill the run).
        """
        pois: list[POI] = []
        skipped: dict[str, str] = {}
        for model in self.registry.all():
            try:
                pois.extend(model.detect(candles, swings, liquidity_levels))
            except Exception as exc:  # noqa: BLE001 — one model must not kill the run
                skipped[model.tag.name] = f"{type(exc).__name__}: {exc}"
        return pois, skipped

    def attribute_displacement(
        self, pois: list[POI], run: DetectionRun
    ) -> dict[str, DisplacementResult]:
        """Most recent same-direction displacement per POI (V1 attribution).

        The rule: a POI is attributed the displacement of the MOST RECENT
        sweep (by candle index) whose direction matches the POI's zone
        direction — a LONG POI pairs with the latest SSL-sweep impulse, a
        SHORT POI with the latest BSL-sweep impulse. ``run.displacements``
        is candle-ordered (``detect_sweeps`` sorts), so the last entry per
        direction wins. A POI with no matching sweep gets NO entry → Pillar
        2 rejects it (UNAVAILABLE). The recency anchor is the sweep index —
        the POI needs no formation index of its own.
        """
        best: dict[Direction, DisplacementResult] = {}
        for _sweep_index, result in run.displacements:
            best[result.direction] = result
        return {
            poi.id: best[poi.zone.direction]
            for poi in pois
            if poi.zone.direction in best
        }

    # ------------------------------------------------------------------ #
    # Batch run — detect → merge → validate → arm
    # ------------------------------------------------------------------ #
    def validate_window(
        self,
        candles: list[Candle],
        *,
        engine: PipelineEngine | None = None,
        swings: list[Swing] | None = None,
        liquidity_levels: list[LiquidityLevel] | None = None,
        displacement_map: dict[str, DisplacementResult] | None = None,
        displacement_provider: (
            Callable[[list[POI], DetectionRun], dict[str, DisplacementResult]] | None
        ) = None,
        merge_first: bool = True,
    ) -> tuple[list[POI], list[ValidationResult], DetectionRun, dict[str, str], list[POI]]:
        """Stage 0/1 → M1–M8 detect → merge → validate (NO arming).

        Returns ``(passed, results, run, skipped_models, detected)`` —
        ``detected`` is the raw pre-merge model output. Rolling-window
        callers (the Phase 7 live loop) validate each window and arm ONLY
        the POIs they have not seen, so an already-armed POI is never
        re-armed (its §24 arm-bar anchor and one-shot stay intact).
        :meth:`run` delegates here and then arms every passed POI at the
        batch arm bar.
        """
        engine = engine if engine is not None else PipelineEngine()
        raw = self.stage0(candles)
        swings = raw.swings if swings is None else swings
        levels = raw.liquidity_levels if liquidity_levels is None else liquidity_levels
        run = DetectionRun(
            swings=swings,
            liquidity_levels=levels,
            sweeps=detect_sweeps(candles, levels),  # recompute on effective levels
            displacements=raw.displacements,
        )
        pois, skipped = self.detect_pois(candles, swings, levels)
        if displacement_map is None and displacement_provider is not None:
            displacement_map = displacement_provider(pois, run)
        if displacement_map is None:
            displacement_map = self.attribute_displacement(pois, run)
        passed, results = engine.validate(
            pois,
            candles,
            swings,
            levels,
            displacement_map=displacement_map,
            merge_first=merge_first,
            atr_period=self.atr_period,
        )
        return passed, results, run, skipped, pois

    def run(
        self,
        candles: list[Candle],
        *,
        engine: PipelineEngine | None = None,
        swings: list[Swing] | None = None,
        liquidity_levels: list[LiquidityLevel] | None = None,
        displacement_map: dict[str, DisplacementResult] | None = None,
        displacement_provider: (
            Callable[[list[POI], DetectionRun], dict[str, DisplacementResult]] | None
        ) = None,
        merge_first: bool = True,
        arm_bar: int | None = None,
    ) -> DriverResult:
        """Full batch: Stage 0/1 → M1–M8 detect → merge → validate → arm.

        ``engine`` — the pipeline to drive (defaults to a fresh
        ``PipelineEngine``; its §5 machine is shared with its validation
        pipeline by construction — I1). ``swings`` / ``liquidity_levels`` /
        ``displacement_map`` override the auto paths when an external Stage
        0 owns them (M4 injection contract). ``displacement_provider`` is
        the injection seam for callers whose displacement comes from
        OUTSIDE the driver: it receives the FINAL post-detect POI list and
        the Stage 0/1 run, and returns the per-POI map (so a pre-computed
        map never mismatches freshly-detected POI ids). ``arm_bar``
        defaults to the last window index (the §24 anchor); bar-loop
        callers pass their current bar index.
        """
        engine = engine if engine is not None else PipelineEngine()
        passed, results, run, skipped, detected = self.validate_window(
            candles,
            engine=engine,
            swings=swings,
            liquidity_levels=liquidity_levels,
            displacement_map=displacement_map,
            displacement_provider=displacement_provider,
            merge_first=merge_first,
        )
        arm = arm_bar if arm_bar is not None else max(len(candles) - 1, 0)
        for poi in passed:
            engine.arm_at(poi, arm_bar=arm)
        return DriverResult(
            passed=passed,
            results=results,
            detected=detected,
            run=run,
            skipped_models=skipped,
            arm_bar=arm,
        )