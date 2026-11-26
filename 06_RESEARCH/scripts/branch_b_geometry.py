#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BRANCH B — geometry of the five C3-rejected B completions (measurement only).

Phase-0 evidence for the Trigger B E2E audit. The liveness artifacts record
*which* POIs completed B at H1 bar index 1717 (close 2025-11-13 18:00) but not
the geometry, so this script re-derives exactly that bar from the same frozen
composition and reads the numbers the C3 gate compared.

Method (no production edit, instrumentation restored in ``finally``):

1. Build the identical product stack and drive ``menu_trade_funnel.MenuCycle``
   from the declared window start to the M5 bar whose close is the recorded
   completion instant (H1 index 1717 = the bar opening 2025-11-13 18:00 UTC and
   closing 19:00; last M5 bar timestamp 18:55 -> close 19:00).
2. While arming, ``ProductMenuEngine._route_for`` is REPLACED by a stub that
   returns ``None``. Arming, sweep detection, episode opening/expiry, §5 state
   and the runner all run normally; only the per-bar confirmation *scan* is
   skipped. This keeps the state that produced the completions and removes the
   76-minute confirmation cost.
3. ``_route_for`` is restored, and the DAY-tier router (all six triggers, the
   real tier subset) is evaluated at the ONE recorded H1 bar for every active
   D1 episode, with ``from_bar`` = the first H1 close at/after the episode's
   sweep close — i.e. exactly the call ``_route_for`` makes per bar.
4. Validation is fail-loud: the set of POI ids that produce a B route at that
   bar must equal the five ids in the liveness ``completions.csv``, the H1 bar
   index must be 1717, and every such route must be C3-rejected
   (``trigger_in_between`` False). Any mismatch aborts with exit 1 — a
   reconstruction that does not reproduce the audit is not evidence.

Geometry reported per completion: direction, entry, stop reference, fib band,
wave-5 index/level, impulse origin, completion close, POI zone bounds, and the
signed distance of the completion close and the planned entry from the zone
body (price units and H1 ATR units).

Artifacts (gitignored): 06_RESEARCH/results/branch_b_geometry/
    b_completions.csv, summary.json, run.log
Report (committed): 06_RESEARCH/BRANCH_B_ROOT_CAUSE.md
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from bisect import bisect_right
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
from smc.data.resample import resample_ohlcv  # noqa: E402
from smc.orchestration.engine import PipelineEngine  # noqa: E402
from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime  # noqa: E402
from smc.orchestration.product_menu_mtf import (  # noqa: E402
    PRODUCT_MENU_CONFIRMATION_TIMEFRAMES,
    PRODUCT_MENU_DETECTION_TIMEFRAMES,
    ProductMenuEngine,
)
from smc.risk.risk_engine import RiskEngine  # noqa: E402
from smc.triggers.in_between import trigger_in_between  # noqa: E402
from smc.utils.atr import latest_atr  # noqa: E402
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

# Recorded B completion: H1 series index 1717. That index is the bar OPENING
# 2025-11-13 18:00 and CLOSING 19:00 UTC (the liveness report quoted the open).
TARGET_CLOSE = datetime(2025, 11, 13, 19, 0, tzinfo=timezone.utc)
TARGET_EXPECTED_H1_INDEX = 1717
EXPECTED_B_POIS = {
    "poi-004029",
    "poi-004092",
    "poi-004154",
    "poi-004759",
    "poi-004032",
}
EXPECTED_B_COUNT = 5

OUT_DIR = ROOT / "06_RESEARCH" / "results" / "branch_b_geometry"
_run_env = os.environ.get("BRANCH_B_OUT")
if _run_env:
    OUT_DIR = Path(_run_env) if Path(_run_env).is_absolute() else ROOT / _run_env
# Smoke: override the stop instant (no validation of the 5 completions then).
_target_env = os.environ.get("BRANCH_B_TARGET")
if _target_env:
    TARGET_CLOSE = datetime.fromisoformat(_target_env)
    if TARGET_CLOSE.tzinfo is None:
        TARGET_CLOSE = TARGET_CLOSE.replace(tzinfo=timezone.utc)

FEED_TFS = tuple(
    dict.fromkeys(
        tuple(PRODUCT_MENU_DETECTION_TIMEFRAMES)
        + tuple(PRODUCT_MENU_CONFIRMATION_TIMEFRAMES)
    )
)


def _close_ts(bar: Candle) -> datetime:
    return bar.timestamp + timedelta(minutes=bar.timeframe.minutes)


def _letter(value) -> str | None:
    if value is None:
        return None
    return getattr(value, "value", None) or str(value)


def _dir_name(value) -> str | None:
    if value is None:
        return None
    return getattr(value, "name", None) or str(value)


def _gap_to_zone(price: float, low: float, high: float) -> float:
    """Signed distance OUTSIDE [low, high] in price units (0 when inside)."""
    if low <= price <= high:
        return 0.0
    return (low - price) if price < low else (price - high)


def run() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_PATH.exists():
        raise SystemExit(f"DATA_GAP: missing {DATA_PATH}")
    started = time.perf_counter()

    print("=" * 78, flush=True)
    print("BRANCH B GEOMETRY — C3-rejected B completions on the product path",
          flush=True)
    print(f"stop at M5 close {TARGET_CLOSE.isoformat()}", flush=True)
    print("Measurement only: no trigger/risk/threshold edit; scan stub restored",
          flush=True)
    print("=" * 78, flush=True)

    mtf.install_deterministic_poi_ids()

    m1_all = load_m1(DATA_PATH, WARMUP_START, WINDOW_END)
    if not m1_all:
        raise SystemExit("DATA_GAP: no M1 bars")
    print(f"loaded M1 bars={len(m1_all)}", flush=True)

    needed = set(DETECTION_TFS) | set(FEED_TFS) | {EXEC_TF}
    series: dict = {}
    for tf in sorted(needed, key=lambda t: t.minutes, reverse=True):
        series[tf] = resample_ohlcv(m1_all, tf)
        print(f"  resampled {tf.name}={len(series[tf])}", flush=True)

    exec_all = series[EXEC_TF]
    window_bars = [c for c in exec_all if c.timestamp >= WINDOW_START]
    if not window_bars:
        raise SystemExit("DATA_GAP: no execution bars in window")

    # The stop bar is the M5 bar whose CLOSE equals TARGET_CLOSE.
    stop_bars = [
        c for c in window_bars
        if c.timestamp + timedelta(minutes=EXEC_TF.minutes) <= TARGET_CLOSE
    ]
    if not stop_bars:
        raise SystemExit("DATA_GAP: no M5 bar closes at/before the target")
    stop_ts = stop_bars[-1].timestamp

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

    original_route_for = menu._route_for
    scan_calls = 0

    def d1_only_route_for(episode, ctf):
        """Real confirmation scan for the D1 tier; stub every other tier.

        B is confirmable only on the D1 tier (``_TIER_ADF`` excludes it from
        H4/H1/M15), so scanning D1 for real reproduces every B completion,
        every C3 rejection and every one-shot consumption that can involve B,
        while skipping the ~20k unrelated H4/H1/M15 confirmations.
        """
        nonlocal scan_calls
        if episode.tier.detection_tf is Timeframe.D1:
            return original_route_for(episode, ctf)
        scan_calls += 1
        return None

    stats = None
    menu._route_for = d1_only_route_for  # type: ignore[assignment]
    try:
        loop = BarLoop(CandleSeries(exec_all, EXEC_TF), cycle)
        print("arming phase (confirmation scan stubbed)…", flush=True)
        stats = loop.run(start_timestamp=WINDOW_START, end_timestamp=stop_ts)
    finally:
        menu._route_for = original_route_for  # type: ignore[assignment]
        elapsed = max(time.perf_counter() - started, 1e-9)
        print(
            f"arming done: bars={getattr(stats, 'bars_processed', 'ERR')} "
            f"batches={cycle.batches} batch_errors={cycle.batch_errors} "
            f"menu_errors={cycle.menu_errors} scan_calls={scan_calls} "
            f"elapsed={elapsed/60.0:.1f}min",
            flush=True,
        )

    # ---- evaluate the ONE recorded confirmation bar --------------------- #
    h1 = menu._confirm[Timeframe.H1]
    target_index = None
    for index in range(len(h1) - 1, -1, -1):
        if _close_ts(h1[index]) == TARGET_CLOSE:
            target_index = index
            break
    if target_index is None:
        raise SystemExit(
            f"RECONSTRUCTION_FAIL: no H1 bar closes at {TARGET_CLOSE.isoformat()} "
            f"(ingested={len(h1)})"
        )
    print(f"H1 target index={target_index} "
          f"close={_close_ts(h1[target_index]).isoformat()}", flush=True)

    swings = menu._swings_for(Timeframe.H1)
    day_tier = menu.tier_for(Timeframe.D1)
    if day_tier is None:
        raise SystemExit("RECONSTRUCTION_FAIL: no D1 tier")
    router = menu._router_for(day_tier)
    atr_value = latest_atr(h1[: target_index + 1], menu.atr_period)
    atr = float(atr_value) if atr_value is not None and float(atr_value) > 0 else None
    print(f"H1 swings={len(swings)} atr14={atr}", flush=True)

    # ---- D1 episodes: window bounds + earlier-consumption simulation ---- #
    # The arming pass stubs the confirmation SCAN, so a POI the real run had
    # already traded earlier in the window still carries an open episode here.
    # Reproduce the engine's per-bar loop for every D1 episode (real router,
    # real C3 via ``_candidate``) and record whether/when it would have been
    # consumed before the target bar. A consumed POI cannot complete again.
    d1_episodes = []
    for episode in menu.episodes():
        if episode.tier.detection_tf is not Timeframe.D1:
            continue
        from_index = menu._first_close_at_or_after(
            Timeframe.H1, episode.sweep_close_ts
        )
        window_end_ts = menu._window_end_ts(episode)
        upper = len(h1)
        if window_end_ts is not None:
            upper = bisect_right(menu._closes[Timeframe.H1], window_end_ts)
        d1_episodes.append(
            {
                "episode": episode,
                "poi_id": str(episode.poi.id),
                "from_index": from_index,
                "upper": upper,
                "window_end_ts": window_end_ts,
                "consumed_at": None,
                "consumed_trigger": None,
            }
        )

    # The real D1 scan already consumed every winner (``_win`` fires inside
    # ``on_execution_bar``), so an ACTIVE episode is one that never won. No
    # manual consumption simulation is needed or wanted.
    consumed_pois: set[str] = set()
    for info in d1_episodes:
        episode = info["episode"]
        if episode.status.name == "WON":
            info["consumed_at"] = episode._evaluated.get(Timeframe.H1)
            info["consumed_trigger"] = episode.winner_route_id
            consumed_pois.add(info["poi_id"])

    print(f"D1 episodes={len(d1_episodes)} consumed_before_target="
          f"{len(consumed_pois)} {sorted(consumed_pois)}", flush=True)

    rows: list[dict] = []
    episodes_seen = len(d1_episodes)
    for info in d1_episodes:
        episode = info["episode"]
        if episode.status.name != "ACTIVE":
            continue
        if info["poi_id"] in consumed_pois:
            continue  # traded earlier in the real run -> no completion here
        from_index = info["from_index"]
        window_end_ts = info["window_end_ts"]
        if from_index is None or target_index < from_index:
            continue
        within_window = target_index < info["upper"]
        route = router.evaluate_at(
            episode.poi, h1, swings, target_index, from_index
        )
        if route is None:
            continue
        signal = route.signal
        letter = _letter(getattr(signal, "trigger", None))
        zone = episode.poi.zone
        low = float(zone.bottom)
        high = float(zone.top)
        close = float(h1[target_index].close)
        entry_price = float(signal.entry_price)
        stop_ref = getattr(signal, "stop_reference", None)
        data = getattr(signal, "data", {}) or {}
        fib_band = data.get("fib_band")
        c3_ok = trigger_in_between(
            zone_low=low, zone_high=high, completion_price=close
        )
        rows.append(
            {
                "poi_id": str(episode.poi.id),
                "trigger": letter,
                "direction": _dir_name(zone.direction),
                "tier": episode.tier.name,
                "confirmation_tf": "H1",
                "episode_status": episode.status.name,
                "poi_consumed_at_index": info["consumed_at"],
                "poi_consumed_trigger": info["consumed_trigger"],
                "window_end_ts": (
                    window_end_ts.isoformat() if window_end_ts is not None else None
                ),
                "within_window": bool(within_window),
                "sweep_index": episode.sweep_index,
                "sweep_close_ts": episode.sweep_close_ts.isoformat(),
                "from_index": from_index,
                "completion_index": target_index,
                "completion_close": close,
                "zone_low": low,
                "zone_high": high,
                "zone_height": round(high - low, 6),
                "entry_price": entry_price,
                "stop_reference": float(stop_ref) if stop_ref is not None else None,
                "wave5_index": data.get("wave5_index"),
                "origin_level": (
                    float(data["origin_level"])
                    if data.get("origin_level") is not None
                    else None
                ),
                "fib_deep": float(fib_band[0]) if fib_band else None,
                "fib_shallow": float(fib_band[1]) if fib_band else None,
                "close_gap_to_zone": round(_gap_to_zone(close, low, high), 6),
                "close_gap_atr": (
                    round(_gap_to_zone(close, low, high) / atr, 6)
                    if atr else None
                ),
                "entry_gap_to_zone": round(
                    _gap_to_zone(entry_price, low, high), 6
                ),
                "entry_gap_atr": (
                    round(_gap_to_zone(entry_price, low, high) / atr, 6)
                    if atr else None
                ),
                "impulse_height": (
                    round(abs(entry_price - stop_ref) / 0.5, 6)
                    if stop_ref is not None else None
                ),
                "impulse_height_atr": (
                    round(abs(entry_price - float(stop_ref)) / 0.5 / atr, 6)
                    if (stop_ref is not None and atr) else None
                ),
                "c3_in_between": bool(c3_ok),
                "route_id": getattr(route, "route_id", None),
            }
        )

    eligible = [r for r in rows if r["within_window"]]
    b_rows = [r for r in eligible if r["trigger"] == "B"]
    print(f"D1 episodes seen={episodes_seen} routes_at_bar={len(rows)} "
          f"in_window={len(eligible)} B_routes={len(b_rows)} "
          f"B_outside_window="
          f"{len([r for r in rows if r['trigger'] == 'B' and not r['within_window']])}",
          flush=True)

    is_smoke = bool(_target_env)
    if not is_smoke:
        got = {r["poi_id"] for r in b_rows}
        problems = []
        if len(b_rows) != EXPECTED_B_COUNT:
            problems.append(f"B count {len(b_rows)} != {EXPECTED_B_COUNT}")
        if got != EXPECTED_B_POIS:
            problems.append(f"POI set mismatch: missing={EXPECTED_B_POIS - got} "
                            f"extra={got - EXPECTED_B_POIS}")
        if target_index != TARGET_EXPECTED_H1_INDEX:
            problems.append(
                f"H1 index {target_index} != {TARGET_EXPECTED_H1_INDEX}"
            )
        not_c3 = [r["poi_id"] for r in b_rows if r["c3_in_between"]]
        if not_c3:
            problems.append(f"C3 accepted (should reject): {not_c3}")
        if problems:
            print("RECONSTRUCTION_FAIL:", flush=True)
            for p in problems:
                print("  -", p, flush=True)
            return 1
        print("RECONSTRUCTION_OK: 5 B completions, exact POI set, C3 reject ×5",
              flush=True)

    if rows:
        for name, subset in (
            ("b_completions.csv", b_rows),
            ("d1_b_scan_all.csv", [r for r in rows if r["trigger"] == "B"]),
            ("d1_scan_all_triggers.csv", rows),
        ):
            if not subset:
                (OUT_DIR / name).write_text("", encoding="utf-8")
                continue
            with (OUT_DIR / name).open(
                "w", newline="", encoding="utf-8"
            ) as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=list(subset[0].keys())
                )
                writer.writeheader()
                writer.writerows(subset)
    else:
        (OUT_DIR / "b_completions.csv").write_text("", encoding="utf-8")

    if d1_episodes:
        with (OUT_DIR / "d1_episodes.csv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "poi_id", "status", "sweep_index", "sweep_close_ts",
                    "from_index", "window_end_ts", "upper",
                    "consumed_at", "consumed_trigger",
                ],
            )
            writer.writeheader()
            for info in d1_episodes:
                writer.writerow(
                    {
                        "poi_id": info["poi_id"],
                        "status": info["episode"].status.name,
                        "sweep_index": info["episode"].sweep_index,
                        "sweep_close_ts": info["episode"].sweep_close_ts.isoformat(),
                        "from_index": info["from_index"],
                        "window_end_ts": (
                            info["window_end_ts"].isoformat()
                            if info["window_end_ts"] is not None else None
                        ),
                        "upper": info["upper"],
                        "consumed_at": info["consumed_at"],
                        "consumed_trigger": info["consumed_trigger"],
                    }
                )

    summary = {
        "RUN": "branch_b_geometry",
        "LOGIC_CHANGED": "NO",
        "SMOKE": is_smoke,
        "TARGET_CLOSE": TARGET_CLOSE.isoformat(),
        "H1_TARGET_INDEX": target_index,
        "H1_SWINGS": len(swings),
        "H1_ATR14": atr,
        "D1_EPISODES_SEEN": episodes_seen,
        "D1_CONSUMED_BEFORE_TARGET": sorted(consumed_pois),
        "ROUTES_AT_BAR": len(rows),
        "ROUTES_IN_WINDOW": len(eligible),
        "B_ROUTES": len(b_rows),
        "B_POIS": sorted(r["poi_id"] for r in b_rows),
        "RECONSTRUCTION_OK": (not is_smoke),
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
    return 0


if __name__ == "__main__":
    sys.exit(run())
