#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BRANCH C — why Trigger C never completes on the product path (measurement only).

Phase-0 evidence for the Trigger C E2E audit. Trigger C (ending diagonal) is
wired ONLY on the product DAY tier (D1 detection -> H1 confirmation); the
liveness run recorded 0 C completions in 2025-09-01 -> 2025-11-30 while 68 D1
POIs were armed. This script establishes *why*, on the real series.

Method (no production edit; every patch restored in ``finally``):

1. Build the identical product stack and drive the frozen
   ``menu_trade_funnel.MenuCycle`` from the window start to the last M5 bar of
   the window. The confirmation *scan* is stubbed for H4/H1/M15 (C is
   inadmissible there), the D1 tier scan runs for real, so arming, sweeps,
   episode opening/expiry and §5 state are the production behaviour.
   ``ProductMenuEngine.register_armed`` is wrapped read-only to record the
   accepted arm census (fail-loud: D1 arms must reproduce the liveness 68).
2. Structural-swing availability: ``detect_swings`` can only report a fractal
   at index ``i`` once ``i + N`` bars exist (N = N_BAR_HTF = 5 on H1). The
   script derives each H1 swing's first-available bar from the same fractal
   test and VERIFIES the derived view against the production
   ``detect_swings(prefix)`` at sampled bars (fail-loud on mismatch).
3. Superset scan: for every H1 bar in the window and every armed D1 POI, the
   REAL ``EndingDiagonalTrigger.evaluate`` is called with ``from_bar = 0``
   (no episode anchor, no menu window) — i.e. every bar on which C could
   possibly complete, not only the bars the menu happened to evaluate.
   ``find_ending_diagonal`` is memoised (one call per bar/direction) and the
   Wilder ATR prefix series is supplied through ``hints`` (spot-checked
   identical to ``latest_atr(prefix)``).
4. Expiry counterfactual: the same scan is repeated with``signal_expired``
   forced False, so the script can report how far past the frozen 3-bar §24
   window the pattern actually becomes observable. This is instrumentation,
   NOT a proposed change.

Post-C1 expectation (amendment accepted 2026-11-28): C's clock now starts at
the terminal's observability (``terminal + N``, N=5 on H1), so legal terminal
ages are 5..8. The REAL trigger is therefore expected to complete on the
frozen window, in the pre-registered band 1..3 (upper bound = the audited
expiry-ignored counterfactual, of which C1's legal set is a subset). Anything
outside that band is fail-loud. The product-path funnel is also reported
(routes → placed → fills) from the same run, because the DAY tier's H1
confirmation scan is real here.

Artifacts (gitignored): 06_RESEARCH/results/branch_c_geometry/
    c_pattern_census.csv, c_would_fire.csv, summary.json, run.log
Report (committed): 06_RESEARCH/BRANCH_C_ROOT_CAUSE.md
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "04_SRC"))
sys.path.insert(0, str(ROOT / "06_RESEARCH" / "scripts"))

from smc.backtest.bar_loop import BarLoop  # noqa: E402
from smc.backtest.cost_model import CostConfig  # noqa: E402
from smc.backtest.data_feed import CandleSeries  # noqa: E402
from smc.backtest.pipeline_adapter import PipelineAdapter  # noqa: E402
from smc.backtest.runner import BacktestRunner, RunnerConfig  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402
from smc.core.candle import Candle  # noqa: E402
from smc.core.enums import Direction  # noqa: E402
from smc.data.resample import resample_ohlcv  # noqa: E402
from smc.detection.structural_swing_detector import detect_swings  # noqa: E402
from smc.orchestration.engine import PipelineEngine  # noqa: E402
from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime  # noqa: E402
from smc.orchestration.product_menu_mtf import (  # noqa: E402
    PRODUCT_MENU_CONFIRMATION_TIMEFRAMES,
    PRODUCT_MENU_DETECTION_TIMEFRAMES,
    ProductMenuEngine,
)
from smc.risk.risk_engine import RiskEngine  # noqa: E402
from smc.utils.atr import atr_series, latest_atr  # noqa: E402
from smc.utils.timestamps import Session  # noqa: E402

import smc.triggers.trigger_c_ending_diagonal as cmod  # noqa: E402
from smc.triggers.base_trigger import TriggerContext  # noqa: E402
from smc.triggers.trigger_c_ending_diagonal import EndingDiagonalTrigger  # noqa: E402
from smc.triggers.wave_structure import find_ending_diagonal  # noqa: E402

import menu_trade_funnel as mtf  # noqa: E402
from plan_complement_ledger import load_m1  # noqa: E402

DETECTION_TFS = [Timeframe.D1, Timeframe.H4, Timeframe.H1, Timeframe.M15]
EXEC_TF = Timeframe.M5
DATA_PATH = ROOT / "07_DATA" / "XAUUSD_M1.parquet"

WARMUP_START = datetime(2025, 8, 1, tzinfo=timezone.utc)
WINDOW_START = datetime(2025, 9, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2025, 12, 1, tzinfo=timezone.utc)
BATCH_EVERY_M15_BARS = 48

#: Liveness census this run must reproduce (fail-loud).
EXPECTED_D1_ARMS = 68
#: C1 pre-registered completion band (see the design lock §7). 3 is the
#: expiry-ignored counterfactual count; C1's legal set is a strict subset.
EXPECTED_C_COMPLETIONS_MIN = 1
EXPECTED_C_COMPLETIONS_MAX = 3

OUT_DIR = ROOT / "06_RESEARCH" / "results" / "branch_c_geometry"
_run_env = os.environ.get("BRANCH_C_OUT")
if _run_env:
    OUT_DIR = Path(_run_env) if Path(_run_env).is_absolute() else ROOT / _run_env
#: Smoke: stop the arming phase early (no census assertion, no verdict).
_stop_env = os.environ.get("BRANCH_C_STOP")
if _stop_env:
    WINDOW_END = datetime.fromisoformat(_stop_env)
    if WINDOW_END.tzinfo is None:
        WINDOW_END = WINDOW_END.replace(tzinfo=timezone.utc)

FEED_TFS = tuple(
    dict.fromkeys(
        tuple(PRODUCT_MENU_DETECTION_TIMEFRAMES)
        + tuple(PRODUCT_MENU_CONFIRMATION_TIMEFRAMES)
    )
)
N_H1 = Timeframe.n_bar_confirmation(Timeframe.H1)
C_EXPIRY = cmod.window_bars_for(cmod.TriggerType.C_ENDING_DIAGONAL)


def _close_ts(bar: Candle) -> datetime:
    return bar.timestamp + timedelta(minutes=bar.timeframe.minutes)


def _dir_name(value) -> str:
    return getattr(value, "name", None) or str(value)


class _Hints:
    """Minimal hint carrier: the Wilder ATR prefix series for H1."""

    __slots__ = ("atr_values",)

    def __init__(self, atr_values):
        self.atr_values = atr_values


def _fractal_indexes(candles: list[Candle], window: int) -> dict:
    """Index of every N-bar fractal extreme -> True (high) / False (low).

    This is the SAME predicate ``detect_swings`` applies; it is re-stated here
    only to attach a *detection bar* (``i + N``) to each swing object, which
    ``Swing`` does not carry.
    """
    found: dict[int, list[bool]] = {}
    for index in range(window, len(candles) - window):
        candle = candles[index]
        left_highs = [c.high for c in candles[index - window : index]]
        right_highs = [c.high for c in candles[index + 1 : index + window + 1]]
        left_lows = [c.low for c in candles[index - window : index]]
        right_lows = [c.low for c in candles[index + 1 : index + window + 1]]
        if candle.high > max(left_highs) and candle.high >= max(right_highs):
            found.setdefault(index, []).append(True)
        if candle.low < min(left_lows) and candle.low <= min(right_lows):
            found.setdefault(index, []).append(False)
    return found


def _availability(candles: list[Candle], window: int, swings) -> list[tuple[int, object]]:
    """(first bar index at which the swing exists, swing) pairs.

    ``detect_swings`` loops ``range(window, len - window)``, so a fractal at
    index ``i`` appears in the prefix the first time ``len - 1 >= i + window``,
    i.e. at bar ``i + window``. A swing low's §18 base candle may sit one bar
    before the fractal; the pair is matched on (polarity, level).
    """
    fractals = _fractal_indexes(candles, window)
    pairs: list[tuple[int, object]] = []
    for swing in swings:
        matches = [
            i for i, pols in fractals.items()
            if (swing.is_high in pols)
            and (
                (swing.is_high and i == swing.candle_index)
                or (not swing.is_high and i in (swing.candle_index, swing.candle_index + 1))
            )
            and (candles[i].high if swing.is_high else candles[i].low) == swing.level
        ]
        if not matches:  # pragma: no cover - fail loud, never guess
            raise SystemExit(
                f"SWING_MATCH_FAIL: {swing.is_high} level={swing.level} "
                f"candle_index={swing.candle_index}"
            )
        fractal = min(matches)
        pairs.append((fractal + window, swing))
    pairs.sort(key=lambda item: item[1].candle_index)
    return pairs


def _available(pairs, bar: int) -> list:
    return [swing for available_at, swing in pairs if available_at <= bar]


def run() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_PATH.exists():
        raise SystemExit(f"DATA_GAP: missing {DATA_PATH}")
    started = time.perf_counter()

    print("=" * 78, flush=True)
    print("BRANCH C GEOMETRY — Trigger C reachability on the product path",
          flush=True)
    print(f"window {WINDOW_START.isoformat()} -> {WINDOW_END.isoformat()}", flush=True)
    print(f"H1 N_BAR = {N_H1}, C expiry (sweep candle + extra) = {C_EXPIRY}",
          flush=True)
    print("Measurement only: no trigger/risk/tier/threshold edit",
          flush=True)
    print("=" * 78, flush=True)

    mtf.install_deterministic_poi_ids()

    m1_all = load_m1(DATA_PATH, WARMUP_START, WINDOW_END + timedelta(days=2))
    if not m1_all:
        raise SystemExit("DATA_GAP: no M1 bars")
    print(f"loaded M1 bars={len(m1_all)}", flush=True)

    needed = set(DETECTION_TFS) | set(FEED_TFS) | {EXEC_TF}
    series: dict = {}
    for tf in sorted(needed, key=lambda t: t.minutes, reverse=True):
        series[tf] = resample_ohlcv(m1_all, tf)
        print(f"  resampled {tf.name}={len(series[tf])}", flush=True)

    exec_all = series[EXEC_TF]
    window_bars = [c for c in exec_all if WINDOW_START <= c.timestamp < WINDOW_END]
    if not window_bars:
        raise SystemExit("DATA_GAP: no execution bars in window")
    stop_ts = window_bars[-1].timestamp

    m15_window = [
        c for c in series[Timeframe.M15]
        if WINDOW_START <= c.timestamp < WINDOW_END
    ]
    batch_instants = {
        _close_ts(m15_window[i])
        for i in range(0, len(m15_window), BATCH_EVERY_M15_BARS)
    }

    engine = PipelineEngine()
    menu = ProductMenuEngine(symbol="XAUUSD")
    adapter = PipelineAdapter(engine, timeframe=EXEC_TF, menu_confirmation=menu)
    adapter.set_candles(exec_all)
    runtime = MultiTFProductRuntime(
        detection_timeframes=DETECTION_TFS, execution_timeframe=EXEC_TF
    )
    order_book = mtf.CountingOrderBook()
    positions = mtf.CountingPositionStore()
    runner = BacktestRunner(
        risk_engine=RiskEngine(),
        order_book=order_book,
        position_store=positions,
        config=RunnerConfig(
            equity=10_000.0,
            risk_fraction=0.01,
            pip_value_per_lot=10.0,
            min_lots=0.01,
            lot_step=0.01,
            allowed_sessions=(Session.ASIA, Session.LONDON, Session.NEW_YORK),
            news_events=[],
            timeframe=EXEC_TF,
            spread_price=0.0,
            cost=CostConfig(),
        ),
    )
    adapter.attach(runner)

    cycle = mtf.MenuCycle(
        runner=runner,
        adapter=adapter,
        runtime=runtime,
        engine=engine,
        menu=menu,
        series=series,
        exec_bars=exec_all,
        batch_instants=batch_instants,
        total_bars=len(window_bars),
        started_at=started,
    )
    cycle.total_bars = sum(
        1 for c in exec_all if WINDOW_START <= c.timestamp <= stop_ts
    )

    # ---- read-only arm census ------------------------------------------- #
    armed: dict[str, object] = {}
    original_register = menu.register_armed

    def recording_register(poi, detection_tf, armed_ts=None):
        accepted = original_register(poi, detection_tf, armed_ts)
        if accepted and detection_tf is Timeframe.D1:
            armed[str(getattr(poi, "id", poi))] = poi
        return accepted

    original_route_for = menu._route_for
    original_win = menu._win
    route_log: list[dict] = []
    scan_calls = 0

    def recording_win(episode, route, ctf):
        """Read-only: log every menu winner with its trigger identity."""
        winner = original_win(episode, route, ctf)
        if winner is not None:
            route_log.append({
                "poi_id": winner.poi_id,
                "trigger": winner.trigger,
                "route_id": winner.route_id,
                "confirmation_tf": getattr(ctf, "name", str(ctf)),
                "completion_index": getattr(
                    getattr(route, "signal", None), "completion_index", None
                ),
                "eval_bar": getattr(route, "bar", None),
            })
        return winner

    def d1_only_route_for(episode, ctf):
        """Real D1-tier scan; every other tier stubbed (C is inadmissible there)."""
        nonlocal scan_calls
        if episode.tier.detection_tf is Timeframe.D1:
            return original_route_for(episode, ctf)
        scan_calls += 1
        return None

    stats = None
    menu.register_armed = recording_register  # type: ignore[assignment]
    menu._route_for = d1_only_route_for  # type: ignore[assignment]
    menu._win = recording_win  # type: ignore[assignment]
    try:
        loop = BarLoop(CandleSeries(exec_all, EXEC_TF), cycle)
        print("arming phase (non-D1 confirmation tiers stubbed)…", flush=True)
        stats = loop.run(start_timestamp=WINDOW_START, end_timestamp=stop_ts)
    finally:
        menu.register_armed = original_register  # type: ignore[assignment]
        menu._route_for = original_route_for  # type: ignore[assignment]
        menu._win = original_win  # type: ignore[assignment]
        elapsed = max(time.perf_counter() - started, 1e-9)
        print(
            f"arming done: bars={getattr(stats, 'bars_processed', 'ERR')} "
            f"batches={cycle.batches} batch_errors={cycle.batch_errors} "
            f"menu_errors={cycle.menu_errors} scan_calls_stubbed={scan_calls} "
            f"d1_arms={len(armed)} elapsed={elapsed/60.0:.1f}min",
            flush=True,
        )

    d1_pois = [armed[k] for k in sorted(armed)]
    is_smoke = bool(_stop_env)

    # ---- product-path C funnel: routes -> placed -> fills --------------- #
    c_value = str(
        getattr(cmod.TriggerType.C_ENDING_DIAGONAL, "value", "c_ending_diagonal")
    )
    c_routes = [row for row in route_log if row["trigger"] == c_value]
    c_poi_ids = {row["poi_id"] for row in c_routes}
    c_placed = [row for row in order_book.records if row["trigger"] == c_value]
    c_fills = [row for row in positions.fills if row["poi_id"] in c_poi_ids]
    print(
        f"product-path C: winners/routes={len(c_routes)} "
        f"placed={len(c_placed)} fills={len(c_fills)}",
        flush=True,
    )
    if not is_smoke and len(d1_pois) != EXPECTED_D1_ARMS:
        raise SystemExit(
            f"RECONSTRUCTION_FAIL: D1 arms {len(d1_pois)} != {EXPECTED_D1_ARMS}"
        )

    # ---- H1 confirm series + swing availability ------------------------- #
    h1 = menu._confirm[Timeframe.H1]
    h1_closes = menu._closes[Timeframe.H1]
    win_lo = next(i for i, ts in enumerate(h1_closes) if ts >= WINDOW_START)
    win_hi = max(i for i, ts in enumerate(h1_closes) if ts <= WINDOW_END)
    print(f"H1 bars={len(h1)} window indexes=[{win_lo}, {win_hi}] "
          f"({h1_closes[win_lo].isoformat()} -> {h1_closes[win_hi].isoformat()})",
          flush=True)

    swings_full = detect_swings(h1, Timeframe.H1)
    pairs = _availability(h1, N_H1, swings_full)
    print(f"H1 swings={len(swings_full)} availability pairs={len(pairs)}",
          flush=True)

    # Fail-loud: the derived availability view must equal detect_swings(prefix).
    sample_bars = sorted({
        win_lo, win_hi, (win_lo + win_hi) // 2,
        win_lo + (win_hi - win_lo) // 3, win_lo + 2 * (win_hi - win_lo) // 3,
    })
    for bar in sample_bars:
        prefix_view = detect_swings(h1[: bar + 1], Timeframe.H1)
        derived = _available(pairs, bar)
        key = lambda s: (s.candle_index, s.is_high, s.level)  # noqa: E731
        if sorted(map(key, prefix_view)) != sorted(map(key, derived)):
            raise SystemExit(
                f"AVAILABILITY_FAIL: derived swing view != detect_swings(prefix) "
                f"at bar {bar}"
            )
    print(f"availability verified at bars {sample_bars}", flush=True)

    # Wilder ATR prefix series (hints): atr_values[bar - 1] == latest_atr(h1[:bar]).
    atr_values = atr_series(h1, 14)
    for bar in sample_bars:
        expect = latest_atr(h1[:bar], 14)
        got = atr_values[bar - 1] if bar > 0 else None
        if expect != got:
            raise SystemExit(
                f"ATR_HINT_FAIL at bar {bar}: hint={got} prefix={expect}"
            )
    print("ATR hint identity verified on sampled bars", flush=True)

    # ---- memoised diagonal lookups (identical objects, one call per key) - #
    diag_cache: dict[tuple[int, Direction], object] = {}

    def cached_find(swings, direction, up_to):
        key = (up_to, direction)
        if key not in diag_cache:
            diag_cache[key] = find_ending_diagonal(swings, direction, up_to)
        return diag_cache[key]

    trigger = EndingDiagonalTrigger()
    hints = _Hints(atr_values)

    # ---- PASS 1: pattern census + the REAL trigger (frozen expiry) ------ #
    census: list[dict] = []
    completions: list[dict] = []
    per_bar_swings: dict[int, list] = {}

    cmod.find_ending_diagonal = cached_find  # type: ignore[assignment]
    try:
        for bar in range(win_lo, win_hi + 1):
            swings = _available(pairs, bar)
            per_bar_swings[bar] = swings
            for direction in (Direction.SHORT, Direction.LONG):
                diagonal = cached_find(swings, direction, bar)
                if diagonal is None:
                    continue
                census.append({
                    "bar": bar,
                    "bar_close_ts": _close_ts(h1[bar]).isoformat(),
                    "direction": direction.name,
                    "terminal_index": diagonal.terminal_index,
                    "terminal_level": round(float(diagonal.terminal_level), 6),
                    "terminal_age_bars": bar - diagonal.terminal_index,
                    "boundary_touch_level": round(
                        float(diagonal.boundary_touch_level), 6
                    ),
                    "converging": bool(diagonal.converging),
                })
    finally:
        cmod.find_ending_diagonal = find_ending_diagonal  # type: ignore[assignment]

    # ---- PASS 2: the real evaluate(), plus the expiry counterfactual ---- #
    # POI direction -> the diagonal direction C looks for (opposite the trade).
    def diag_direction_for(poi) -> Direction:
        return (
            Direction.SHORT
            if poi.zone.direction is Direction.LONG
            else Direction.LONG
        )

    def scan(ignore_expiry: bool) -> list[dict]:
        found: list[dict] = []
        original_expired = cmod.signal_expired

        def forced(idx, expiry, bar):
            if ignore_expiry:
                return False
            return original_expired(idx, expiry, bar)

        cmod.signal_expired = forced  # type: ignore[assignment]
        cmod.find_ending_diagonal = cached_find  # type: ignore[assignment]
        try:
            for bar in range(win_lo, win_hi + 1):
                swings = per_bar_swings[bar]
                close = float(h1[bar].close)
                for poi in d1_pois:
                    direction = diag_direction_for(poi)
                    diagonal = cached_find(swings, direction, bar)
                    if diagonal is None:
                        continue
                    context = TriggerContext(
                        poi=poi,
                        candles=h1,
                        swings=swings,
                        bar_index=bar,
                        from_bar=0,
                        hints=hints,
                    )
                    signal = trigger.evaluate(context)
                    if signal is None:
                        continue
                    zone = poi.zone
                    found.append({
                        "poi_id": str(poi.id),
                        "bar": bar,
                        "bar_close_ts": _close_ts(h1[bar]).isoformat(),
                        "zone_direction": _dir_name(zone.direction),
                        "zone_low": round(float(zone.bottom), 6),
                        "zone_high": round(float(zone.top), 6),
                        "completion_close": close,
                        "entry_price": round(float(signal.entry_price), 6),
                        "stop_reference": round(
                            float(signal.stop_reference), 6
                        ),
                        "terminal_index": diagonal.terminal_index,
                        "terminal_age_bars": bar - diagonal.terminal_index,
                        "terminal_age_at_first_possible_bar": None,
                        "expiry_bars": int(signal.expiry_bars),
                        "ignored_expiry": ignore_expiry,
                    })
        finally:
            cmod.signal_expired = original_expired  # type: ignore[assignment]
            cmod.find_ending_diagonal = find_ending_diagonal  # type: ignore[assignment]
        return found

    real_hits = scan(ignore_expiry=False)
    counterfactual_hits = scan(ignore_expiry=True)

    # ---- why each superset completion did (not) become a product route -- #
    # The scan uses from_bar=0; the product also needs an ACTIVE episode whose
    # sweep is at/after the terminal (§24 + from_bar gate) and a C3-clean
    # completion. Report the episode facts per completion POI (no retuning,
    # no counterfactual fill).
    episodes = list(getattr(menu, "_episodes", ()))
    route_diag: list[dict] = []
    for row in real_hits:
        poi_id = row["poi_id"]
        terminal_ts = _close_ts(h1[row["terminal_index"]])
        completion_ts = datetime.fromisoformat(row["bar_close_ts"])
        mine = [e for e in episodes if str(e.poi_id) == poi_id]
        route_diag.append({
            "poi_id": poi_id,
            "completion_ts": completion_ts.isoformat(),
            "terminal_ts": terminal_ts.isoformat(),
            "episodes": len(mine),
            "sweep_blocks_terminal": [
                bool(
                    isinstance(getattr(e, "sweep_close_ts", None), datetime)
                    and e.sweep_close_ts > terminal_ts
                )
                for e in mine
            ],
            "episode_status": [
                getattr(getattr(e, "status", None), "name", None) for e in mine
            ],
            "episode_decisions": [list(e.decisions) for e in mine],
            "episode_winners": [
                row for row in route_log
                if row["poi_id"] == poi_id and row["trigger"] != c_value
            ],
        })
    for entry in route_diag:
        print(
            f"  route-diag {entry['poi_id']}: episodes={entry['episodes']} "
            f"sweep_after_terminal={entry['sweep_blocks_terminal']} "
            f"status={entry['episode_status']} "
            f"decisions={entry['episode_decisions']} "
            f"other_winners={[(w['trigger'], w['completion_index']) for w in entry['episode_winners']]}",
            flush=True,
        )

    ages = [row["terminal_age_bars"] for row in census]
    ages_sorted = sorted(ages) if ages else []
    def pct(values, q):
        if not values:
            return None
        return values[min(len(values) - 1, int(q * (len(values) - 1)))]

    print(f"diagonal census rows={len(census)} "
          f"distinct_bars={len({r['bar'] for r in census})} "
          f"min_terminal_age={min(ages) if ages else None} "
          f"(allowed<= {C_EXPIRY})", flush=True)
    print(f"REAL evaluate() completions={len(real_hits)} (superset scan)", flush=True)
    print(f"counterfactual (expiry ignored)={len(counterfactual_hits)}", flush=True)

    problems: list[str] = []
    if not is_smoke:
        if not (
            EXPECTED_C_COMPLETIONS_MIN
            <= len(real_hits)
            <= EXPECTED_C_COMPLETIONS_MAX
        ):
            problems.append(
                f"C completions {len(real_hits)} outside the pre-registered "
                f"band [{EXPECTED_C_COMPLETIONS_MIN}, "
                f"{EXPECTED_C_COMPLETIONS_MAX}]"
            )
        if not census:
            problems.append("no ending diagonal detected at all in the window")
        if real_hits and min(
            row["terminal_age_bars"] for row in real_hits
        ) < N_H1:
            problems.append(
                "a completion fired before the terminal was observable "
                f"(N={N_H1})"
            )
        if counterfactual_hits and len(counterfactual_hits) < len(real_hits):
            problems.append(
                "expiry-ignored counterfactual is SMALLER than the real scan — "
                "C1 must be a subset of ignoring expiry"
            )
    if problems:
        print("ANALYSIS_FAIL:", flush=True)
        for p in problems:
            print("  -", p, flush=True)
        # Still write artifacts so the failure is inspectable.
    else:
        print(
            "ANALYSIS_OK: C is reachable under the C1 observability anchor — "
            f"{len(real_hits)} superset completions, terminal ages "
            f"{sorted({r['terminal_age_bars'] for r in real_hits})} "
            f"(legal {N_H1}..{N_H1 + C_EXPIRY}), product winners "
            f"{len(c_routes)} / placed {len(c_placed)} / fills {len(c_fills)}",
            flush=True,
        )

    # ---- artifacts ------------------------------------------------------- #
    if census:
        with (OUT_DIR / "c_pattern_census.csv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(census[0].keys()))
            writer.writeheader()
            writer.writerows(census)
    else:
        (OUT_DIR / "c_pattern_census.csv").write_text("", encoding="utf-8")

    hits_out = real_hits + [row for row in counterfactual_hits]
    if hits_out:
        with (OUT_DIR / "c_would_fire.csv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(hits_out[0].keys()))
            writer.writeheader()
            writer.writerows(hits_out)
    else:
        (OUT_DIR / "c_would_fire.csv").write_text("", encoding="utf-8")

    d1_zone_summary = {}
    for poi in d1_pois:
        key = _dir_name(poi.zone.direction)
        d1_zone_summary[key] = d1_zone_summary.get(key, 0) + 1

    summary = {
        "RUN": "branch_c_geometry",
        "LOGIC_CHANGED": "NO",
        "SMOKE": is_smoke,
        "WINDOW": [WINDOW_START.isoformat(), WINDOW_END.isoformat()],
        "H1_N_BAR": N_H1,
        "C_EXPIRY_BARS": C_EXPIRY,
        "D1_ARMS": len(d1_pois),
        "D1_ARMS_BY_DIRECTION": d1_zone_summary,
        "H1_BARS_TOTAL": len(h1),
        "H1_SCAN_BARS": win_hi - win_lo + 1,
        "H1_SWINGS": len(swings_full),
        "DIAGONAL_CENSUS_ROWS": len(census),
        "DIAGONAL_DISTINCT_BARS": len({r["bar"] for r in census}),
        "DIAGONAL_TERMINAL_AGE_MIN": min(ages) if ages else None,
        "DIAGONAL_TERMINAL_AGE_P10": pct(ages_sorted, 0.10),
        "DIAGONAL_TERMINAL_AGE_MEDIAN": pct(ages_sorted, 0.50),
        "DIAGONAL_TERMINAL_AGE_MAX": max(ages) if ages else None,
        "DIAGONAL_BARS_INSIDE_C1_WINDOW": sum(
            1 for a in ages if N_H1 <= a <= N_H1 + C_EXPIRY
        ),
        "DIAGONAL_BARS_INSIDE_PRE_C1_WINDOW": sum(
            1 for a in ages if a <= C_EXPIRY
        ),
        "C_ANCHOR_RULE": (
            "anchor = terminal_index + N(confirm_tf); legal "
            "anchor .. anchor + TRIGGER_C_EXPIRY_EXTRA"
        ),
        "C_COMPLETIONS_SUPERSET": len(real_hits),
        "C_COMPLETIONS": len(real_hits),
        "C_COMPLETIONS_BAND": [
            EXPECTED_C_COMPLETIONS_MIN, EXPECTED_C_COMPLETIONS_MAX
        ],
        "C_ROUTE_DIAGNOSTICS": route_diag,
        "C_PRODUCT_ROUTES": len(c_routes),
        "C_PRODUCT_PLACED": len(c_placed),
        "C_PRODUCT_FILLS": len(c_fills),
        "C_COUNTERFACTUAL_IGNORE_EXPIRY": len(counterfactual_hits),
        "C_COUNTERFACTUAL_MIN_AGE": (
            min(r["terminal_age_bars"] for r in counterfactual_hits)
            if counterfactual_hits else None
        ),
        "ANALYSIS_PROBLEMS": problems,
        "ARMING": {
            "EXEC_BARS": getattr(stats, "bars_processed", None),
            "BATCHES": cycle.batches,
            "BATCH_ERRORS": cycle.batch_errors,
            "MENU_ERRORS": cycle.menu_errors,
            "SCAN_CALLS_STUBBED": scan_calls,
        },
        "ELAPSED_SECONDS": round(time.perf_counter() - started, 1),
    }
    with (OUT_DIR / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, default=str)

    print(json.dumps(summary, indent=2, default=str), flush=True)
    print(f"artifacts: {OUT_DIR}", flush=True)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(run())
