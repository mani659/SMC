#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BRANCH E — why Trigger E never completes on the product path (measurement only).

Phase-0 evidence for the Trigger E (double top/bottom + RSI divergence) audit.
E is wired ONLY on the product DAY tier (D1 detection -> H1 confirmation); the
liveness run recorded 0 E completions in 2025-09-01 -> 2025-11-30 with 68 D1
POIs armed.

Method (no production edit; every patch restored in ``finally``):

1. Same product composition as the Branch C pack: the frozen
   ``menu_trade_funnel.MenuCycle`` is driven over the full window, the
   confirmation scan is stubbed for H4/H1/M15 (E is inadmissible there) and
   runs for real on D1. ``register_armed`` is wrapped read-only to record the
   arm census (fail-loud: D1 arms must reproduce the liveness 68).
2. Swing availability on H1 is derived from the same fractal predicate
   ``detect_swings`` uses and verified against ``detect_swings(prefix)`` at
   sampled bars (fail-loud).
3. Superset scan: for every H1 bar in the window and every armed D1 POI the
   REAL ``RsiDivergenceTrigger.evaluate`` is called with ``from_bar = 0`` —
   every bar on which E could complete, not only the bars the menu evaluated.
   Hints supply the Wilder ATR/RSI prefix series and the pre-mirrored series.
4. Staged funnel (instrumentation, replicating ``_detect`` gate by gate in
   production order) so every death is attributed to one gate:
   S1 two swing highs / S2 second high >= first / S3 §2 EQH equality
   tolerance / S4 second high at the POI zone / S5 post-arm / S6 RSI
   divergence / S7 neckline break. Near-miss rows (a second high AT the zone)
   are recorded with the peak-to-peak gap, plus a diagnostic of whether ANY
   adjacent swing-high pair (not only the two most recent) would qualify.

Artifacts (gitignored): 06_RESEARCH/results/branch_e_geometry/
    e_gate_funnel.csv, e_near_miss.csv, summary.json, run.log
Report (committed): 06_RESEARCH/BRANCH_E_ROOT_CAUSE.md
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
from smc.config.locked_constants import EQH_EQL_TOLERANCE  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402
from smc.core.candle import Candle  # noqa: E402
from smc.core.enums import Direction  # noqa: E402
from smc.core.zone import Zone  # noqa: E402
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
from smc.triggers.base_trigger import TriggerContext  # noqa: E402
from smc.triggers.trigger_e_rsi_divergence import (  # noqa: E402
    RsiDivergenceTrigger,
    _invert_candles,
    _invert_swings,
)
from smc.utils.atr import atr_series  # noqa: E402
from smc.utils.pips import price_to_pips, within_pip_tolerance  # noqa: E402
from smc.utils.rsi import rsi_series  # noqa: E402
from smc.utils.timestamps import Session  # noqa: E402

import menu_trade_funnel as mtf  # noqa: E402
from plan_complement_ledger import load_m1  # noqa: E402

DETECTION_TFS = [Timeframe.D1, Timeframe.H4, Timeframe.H1, Timeframe.M15]
EXEC_TF = Timeframe.M5
DATA_PATH = ROOT / "07_DATA" / "XAUUSD_M1.parquet"

WARMUP_START = datetime(2025, 8, 1, tzinfo=timezone.utc)
WINDOW_START = datetime(2025, 9, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2025, 12, 1, tzinfo=timezone.utc)
BATCH_EVERY_M15_BARS = 48

EXPECTED_D1_ARMS = 68
EXPECTED_E_COMPLETIONS = 0

OUT_DIR = ROOT / "06_RESEARCH" / "results" / "branch_e_geometry"
_run_env = os.environ.get("BRANCH_E_OUT")
if _run_env:
    OUT_DIR = Path(_run_env) if Path(_run_env).is_absolute() else ROOT / _run_env
_stop_env = os.environ.get("BRANCH_E_STOP")
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
TOLERANCE_PRICE = EQH_EQL_TOLERANCE * 0.1  # §2 pip convention (pips.py)


def _close_ts(bar: Candle) -> datetime:
    return bar.timestamp + timedelta(minutes=bar.timeframe.minutes)


def _dir_name(value) -> str:
    return getattr(value, "name", None) or str(value)


class _Hints:
    """Hint carrier for the production trigger (Phase C perf contract)."""

    __slots__ = (
        "atr_values", "rsi_values", "rsi_values_inverted",
        "inverted", "inverted_swings",
    )

    def __init__(self, atr_values, rsi_values, rsi_values_inverted,
                 inverted, inverted_swings):
        self.atr_values = atr_values
        self.rsi_values = rsi_values
        self.rsi_values_inverted = rsi_values_inverted
        self.inverted = inverted
        self.inverted_swings = inverted_swings


def _fractal_indexes(candles: list[Candle], window: int) -> dict:
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


def _availability(candles, window, swings) -> list[tuple[int, object]]:
    fractals = _fractal_indexes(candles, window)
    pairs = []
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
        if not matches:
            raise SystemExit(
                f"SWING_MATCH_FAIL: {swing.is_high} level={swing.level} "
                f"candle_index={swing.candle_index}"
            )
        pairs.append((min(matches) + window, swing))
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
    print("BRANCH E GEOMETRY — Trigger E reachability on the product path",
          flush=True)
    print(f"window {WINDOW_START.isoformat()} -> {WINDOW_END.isoformat()}", flush=True)
    print(f"H1 N_BAR={N_H1}, E expiry={15} bars, EQH tolerance="
          f"{EQH_EQL_TOLERANCE} pips ({TOLERANCE_PRICE} price units)", flush=True)
    print("Measurement only: no trigger/risk/tier/threshold edit", flush=True)
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
    runner = BacktestRunner(
        risk_engine=RiskEngine(),
        order_book=mtf.CountingOrderBook(),
        position_store=mtf.CountingPositionStore(),
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

    armed: dict[str, object] = {}
    original_register = menu.register_armed

    def recording_register(poi, detection_tf, armed_ts=None):
        accepted = original_register(poi, detection_tf, armed_ts)
        if accepted and detection_tf is Timeframe.D1:
            armed[str(getattr(poi, "id", poi))] = poi
        return accepted

    original_route_for = menu._route_for
    scan_calls = 0

    def d1_only_route_for(episode, ctf):
        nonlocal scan_calls
        if episode.tier.detection_tf is Timeframe.D1:
            return original_route_for(episode, ctf)
        scan_calls += 1
        return None

    stats = None
    menu.register_armed = recording_register  # type: ignore[assignment]
    menu._route_for = d1_only_route_for  # type: ignore[assignment]
    try:
        loop = BarLoop(CandleSeries(exec_all, EXEC_TF), cycle)
        print("arming phase (confirmation scan stubbed)…", flush=True)
        stats = loop.run(start_timestamp=WINDOW_START, end_timestamp=stop_ts)
    finally:
        menu.register_armed = original_register  # type: ignore[assignment]
        menu._route_for = original_route_for  # type: ignore[assignment]
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
    if not is_smoke and len(d1_pois) != EXPECTED_D1_ARMS:
        raise SystemExit(
            f"RECONSTRUCTION_FAIL: D1 arms {len(d1_pois)} != {EXPECTED_D1_ARMS}"
        )

    # ---- H1 series, swings, indicator hints ----------------------------- #
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
                f"AVAILABILITY_FAIL: derived view != detect_swings(prefix) at {bar}"
            )
    print(f"availability verified at bars {sample_bars}", flush=True)

    atr_values = atr_series(h1, 14)
    rsi_values = rsi_series(h1)
    inv_candles = _invert_candles(h1)
    rsi_inverted = rsi_series(inv_candles)

    trigger = RsiDivergenceTrigger()

    # ---- staged funnel + the REAL trigger ------------------------------- #
    stage_names = ["S1_two_highs", "S2_second_ge_first", "S3_eqh_tolerance",
                   "S4_second_at_zone", "S5_post_arm", "S6_rsi_divergence",
                   "S7_neckline_break"]
    stage_pass = {name: 0 for name in stage_names}
    near_miss: list[dict] = []
    near_miss_seen: set[tuple] = set()
    staged_rows: list[dict] = []
    real_hits: list[dict] = []
    any_pair_hits = 0
    checked = 0

    for bar in range(win_lo, win_hi + 1):
        swings = _available(pairs, bar)
        inv_swings_bar = _invert_swings(swings)
        ev_bar_close = float(h1[bar].close)
        hints = _Hints(atr_values, rsi_values, rsi_inverted,
                       inv_candles, inv_swings_bar)
        atr = atr_values[bar - 1] if bar > 0 and atr_values[bar - 1] is not None else 0.0
        band = 0.5 * atr  # ZONE_REFINEMENT_ATR via atr_band_half_width
        for poi in d1_pois:
            checked += 1
            context = TriggerContext(
                poi=poi, candles=h1, swings=swings, bar_index=bar,
                from_bar=0, hints=hints,
            )
            signal = trigger.evaluate(context)
            is_short = poi.zone.direction is Direction.SHORT
            ws_swings = swings if is_short else inv_swings_bar
            ws_candles = h1 if is_short else inv_candles
            ws_rsi = rsi_values if is_short else rsi_inverted
            zone = (poi.zone if is_short else
                    Zone(top=-poi.zone.bottom, bottom=-poi.zone.top,
                         direction=poi.zone.direction))

            highs = [s for s in ws_swings if s.is_high and s.candle_index < bar]
            highs.sort(key=lambda s: s.candle_index)
            if len(highs) < 2:
                continue
            stage_pass["S1_two_highs"] += 1
            h1s, h2s = highs[-2], highs[-1]
            if h2s.level < h1s.level:
                continue
            stage_pass["S2_second_ge_first"] += 1
            gap = float(h2s.level - h1s.level)
            equal = within_pip_tolerance(h1s.level, h2s.level)
            at_zone = (
                float(zone.bottom) - band
                <= float(h2s.level)
                <= float(zone.top) + band
            )
            r1 = ws_rsi[h1s.candle_index] if h1s.candle_index < len(ws_rsi) else None
            r2 = ws_rsi[h2s.candle_index] if h2s.candle_index < len(ws_rsi) else None
            diverge = r1 is not None and r2 is not None and r2 < r1

            pair_key = (str(poi.id), h1s.candle_index, h2s.candle_index)
            if at_zone and pair_key not in near_miss_seen:
                near_miss_seen.add(pair_key)
                near_miss.append({
                    "bar": bar,
                    "bar_close_ts": _close_ts(h1[bar]).isoformat(),
                    "poi_id": str(poi.id),
                    "zone_direction": _dir_name(poi.zone.direction),
                    "peak1_index": h1s.candle_index,
                    "peak2_index": h2s.candle_index,
                    "peak1_level": round(float(h1s.level), 6),
                    "peak2_level": round(float(h2s.level), 6),
                    "gap_price": round(gap, 6),
                    "gap_pips": round(price_to_pips(gap), 6),
                    "gap_atr": round(gap / atr, 6) if atr else None,
                    "eqh_tolerance_price": TOLERANCE_PRICE,
                    "within_eqh": bool(equal),
                    "rsi1": round(float(r1), 4) if r1 is not None else None,
                    "rsi2": round(float(r2), 4) if r2 is not None else None,
                    "rsi_divergence": bool(diverge),
                })

            staged = False
            neckline = None
            if equal:
                stage_pass["S3_eqh_tolerance"] += 1
                if at_zone:
                    stage_pass["S4_second_at_zone"] += 1
                    stage_pass["S5_post_arm"] += 1  # superset scan: from_bar = 0
                    if diverge:
                        stage_pass["S6_rsi_divergence"] += 1
                        neckline = min(
                            c.low for c in ws_candles[
                                h1s.candle_index + 1 : h2s.candle_index + 1
                            ]
                        )
                        earlier_break = any(
                            ws_candles[i].close < neckline
                            for i in range(h2s.candle_index + 1, bar)
                        )
                        broke = (-ev_bar_close if not is_short else ev_bar_close) < neckline
                        if not earlier_break and broke:
                            stage_pass["S7_neckline_break"] += 1
                            staged = True

            # Diagnostic only: does ANY adjacent swing-high pair qualify?
            if at_zone and any(
                b.level >= a.level and within_pip_tolerance(a.level, b.level)
                for a, b in zip(highs, highs[1:])
            ):
                any_pair_hits += 1

            row = {
                "poi_id": str(poi.id),
                "bar": bar,
                "bar_close_ts": _close_ts(h1[bar]).isoformat(),
                "zone_direction": _dir_name(poi.zone.direction),
                "neckline": round(float(neckline), 6) if neckline is not None else None,
                "entry_price": round(float(signal.entry_price), 6) if signal else None,
                "peak1_index": h1s.candle_index,
                "peak2_index": h2s.candle_index,
                "gap_price": round(gap, 6),
                "gap_pips": round(price_to_pips(gap), 6),
                "rsi1": round(float(r1), 4) if r1 is not None else None,
                "rsi2": round(float(r2), 4) if r2 is not None else None,
            }
            if staged:
                staged_rows.append(row)
            if signal is not None:
                real_hits.append({**row, "real_signal": True})

    print(f"checked (bar x POI)={checked}", flush=True)
    for name in stage_names:
        print(f"  {name}: {stage_pass[name]}", flush=True)
    print(f"near_miss_rows (second peak at zone)={len(near_miss)} "
          f"of which within EQH={sum(1 for r in near_miss if r['within_eqh'])}",
          flush=True)
    print(f"staged S7 completions={len(staged_rows)} "
          f"REAL trigger signals={len(real_hits)}", flush=True)

    problems: list[str] = []
    if not is_smoke:
        if len(real_hits) != EXPECTED_E_COMPLETIONS:
            problems.append(
                f"E completions {len(real_hits)} != {EXPECTED_E_COMPLETIONS}"
            )
        if len(staged_rows) != len(real_hits):
            problems.append(
                "staged funnel and the real trigger disagree on completions"
            )
    if problems:
        print("ANALYSIS_FAIL:", flush=True)
        for p in problems:
            print("  -", p, flush=True)
    else:
        print("ANALYSIS_OK: staged funnel matches the real trigger", flush=True)

    # ---- artifacts ------------------------------------------------------- #
    with (OUT_DIR / "e_gate_funnel.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(["stage", "pass_count"])
        writer.writerow(["S0_checked_bar_poi", checked])
        for name in stage_names:
            writer.writerow([name, stage_pass[name]])

    if staged_rows:
        with (OUT_DIR / "e_staged_completions.csv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(staged_rows[0].keys()))
            writer.writeheader()
            writer.writerows(staged_rows)

    if near_miss:
        with (OUT_DIR / "e_near_miss.csv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(near_miss[0].keys()))
            writer.writeheader()
            writer.writerows(near_miss)
    else:
        (OUT_DIR / "e_near_miss.csv").write_text("", encoding="utf-8")

    gaps = [row["gap_pips"] for row in near_miss if row["within_eqh"]] if near_miss else []
    gaps_all = sorted(row["gap_pips"] for row in near_miss) if near_miss else []

    def pct(values, q):
        if not values:
            return None
        return values[min(len(values) - 1, int(q * (len(values) - 1)))]

    summary = {
        "RUN": "branch_e_geometry",
        "LOGIC_CHANGED": "NO",
        "SMOKE": is_smoke,
        "WINDOW": [WINDOW_START.isoformat(), WINDOW_END.isoformat()],
        "H1_N_BAR": N_H1,
        "E_EXPIRY_BARS": 15,
        "EQH_TOLERANCE_PIPS": EQH_EQL_TOLERANCE,
        "EQH_TOLERANCE_PRICE": TOLERANCE_PRICE,
        "D1_ARMS": len(d1_pois),
        "D1_ARMS_BY_DIRECTION": {
            d: sum(1 for p in d1_pois if _dir_name(p.zone.direction) == d)
            for d in ("LONG", "SHORT")
        },
        "H1_BARS_TOTAL": len(h1),
        "H1_SCAN_BARS": win_hi - win_lo + 1,
        "H1_SWINGS": len(swings_full),
        "CHECKED_BAR_POI": checked,
        "STAGE_PASS": stage_pass,
        "NEAR_MISS_ROWS": len(near_miss),
        "NEAR_MISS_WITHIN_EQH": sum(1 for r in near_miss if r["within_eqh"]),
        "NEAR_MISS_GAP_PIPS_MIN": min(gaps_all) if gaps_all else None,
        "NEAR_MISS_GAP_PIPS_MEDIAN": pct(gaps_all, 0.50),
        "NEAR_MISS_GAP_PIPS_P10": pct(gaps_all, 0.10),
        "STAGED_COMPLETIONS": len(staged_rows),
        "E_COMPLETIONS": len(real_hits),
        "ANY_ADJACENT_PAIR_QUALIFY_ROWS": any_pair_hits,
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
