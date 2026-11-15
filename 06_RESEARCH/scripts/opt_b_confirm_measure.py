"""OPT-B menu-path measurement — flag OFF vs ON on the SAME frozen window.

DIAGNOSTIC — NOT EDGE — NOT A PERFORMANCE CLAIM.

What this measures (Part 3 of the OPT-B brief): for every menu-tier POI that
actually sweeps, what does the *product menu* confirmation decide, and where is
price at that moment — with the OPT-B anchor OFF (serial sweep-bar close) and ON
(sweep-extreme bar close)?

Method (menu path only — the adapter/P1 path is not touched by OPT-B):

1. **Arming.** The frozen product runtime (``MultiTFProductRuntime``, detection
   D1/H4/H1/M15, M8 supply from D1) runs at its new-H1-close cadence over the
   frozen window and arms POIs into a ``PipelineEngine``.
2. **Episode census.** For each armed POI the first closed detection bar that
   satisfies the locked R2 rule (``smc.dumb.rules.is_sweep``) after the arm is
   its first menu episode.
3. **Per-episode replay.** A FRESH ``ProductMenuEngine`` is built per episode
   per flag and driven through its public ``on_execution_bar`` API: one call
   seeds the sweep detection bar plus a bounded prefix of the tier's
   confirmation streams, then every later closed bar of those streams (and of
   the detection stream, for the 20-detection-bar expiry) is fed in close order
   until a winner or expiry. Both flags see byte-identical bars; only the flag
   differs.
4. **Label.** The winner's confirmation-bar close is labelled with the SAME
   frozen rule as the timing study (``timing_label`` from
   ``poi_timing_early_late_study``: band = existing FR-3/R7
   ``ZONE_REFINEMENT_ATR x ATR``), so OFF and ON are directly comparable.

Scoping (stated, not hidden):

* Only each POI's FIRST episode is probed (later episodes after an expiry are
  out of scope here; the timing study also keys on first decisions).
* Confirmation streams are seeded with a bounded prefix
  (``EPISODE_SEED_BARS``). The menu is stateless per bar; the seed only supplies
  swing/ATR context and is capped well above the ATR period.
* No placement, no risk, no R7, no fills: this is a confirmation-geometry
  measurement, not a PnL study.

Usage::

    PYTHONPATH=04_SRC python -X utf8 06_RESEARCH/scripts/opt_b_confirm_measure.py \
        [--window primary|secondary] [--limit N]
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

from poi_timing_early_late_study import (  # noqa: E402
    LABEL_LATE,
    LABEL_ON_WINDOW,
    WINDOWS,
    timing_label,
)

OUT_ROOT = REPO_ROOT / "06_RESEARCH" / "results" / "opt_b_confirm_measure"
BANNER = "DIAGNOSTIC PROBE — NOT EDGE — NOT A PERFORMANCE CLAIM"

#: Bounded confirmation-stream seed (bars closed AT/BEFORE the sweep close).
EPISODE_SEED_BARS = 600

DETECTION_TFS = ("D1", "H4", "H1", "M15")


def _parse_day(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _close_ts(bar) -> datetime:
    return bar.timestamp + timedelta(minutes=bar.timeframe.minutes)


def load_series(window: str, exec_from: datetime | None = None) -> dict:
    from smc.config.timeframe import Timeframe
    from smc.data.parquet_loader import load_ohlcv_parquet
    from smc.data.resample import resample_multi

    spec = dict(WINDOWS[window])
    if exec_from is not None:
        spec["exec_from"] = exec_from
    path = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    if not path.exists():
        raise SystemExit(f"canonical dataset missing: {path}")
    m1 = load_ohlcv_parquet(path)
    m1 = [c for c in m1
          if spec["load_from"] <= c.timestamp <= spec["exec_to"] + timedelta(days=1)]
    tfs = [Timeframe.M1, Timeframe.M5, Timeframe.M15, Timeframe.H1,
           Timeframe.H4, Timeframe.D1]
    multi = resample_multi(m1, tfs)
    series = {tf: list(multi[tf]) for tf in tfs}
    for tf in series:
        series[tf] = [c for c in series[tf]
                      if c.timestamp <= spec["exec_to"]]
    print("[opt-b] series " + " | ".join(
        f"{tf.name} {len(bars)}" for tf, bars in series.items()), flush=True)
    return series


def arm_pois(window: str, series: dict, exec_from: datetime | None = None) -> list:
    """Run the frozen product runtime; return armed POIs with their tier TF."""
    from smc.backtest.pipeline_adapter import PipelineAdapter
    from smc.config.timeframe import Timeframe
    from smc.orchestration.engine import PipelineEngine
    from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime

    spec = dict(WINDOWS[window])
    if exec_from is not None:
        spec["exec_from"] = exec_from
    m5 = [c for c in series[Timeframe.M5]
          if spec["exec_from"] <= c.timestamp <= spec["exec_to"]]
    if len(m5) < 50:
        raise SystemExit("execution window too small")
    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=Timeframe.M5)
    adapter.set_candles(m5)
    runtime = MultiTFProductRuntime(
        execution_timeframe=Timeframe.M5,
        detection_timeframes=tuple(Timeframe[name] for name in DETECTION_TFS),
    )
    htf = {name: series[Timeframe[name]] for name in DETECTION_TFS}
    stamps = {name: [c.timestamp for c in htf[name]] for name in DETECTION_TFS}
    h1_ts = stamps["H1"]
    last_h1 = None
    armed: list = []
    batches = 0
    t0 = time.perf_counter()
    for index, bar in enumerate(m5):
        cut = bisect.bisect_right(h1_ts, bar.timestamp) - 1
        if cut < 0:
            continue
        current = htf["H1"][cut].timestamp
        if current == last_h1:
            continue
        last_h1 = current
        series_by_tf = {
            Timeframe[name]: htf[name][: bisect.bisect_right(
                stamps[name], bar.timestamp)]
            for name in DETECTION_TFS
        }
        try:
            report = runtime.run_batch(
                engine=engine,
                series_by_tf=series_by_tf,
                as_of=bar.timestamp,
                arm_bar=index,
                adapter=adapter,
            )
        except Exception as exc:                      # noqa: BLE001 - diagnostic
            print(f"[opt-b] batch error at {bar.timestamp}: {exc}", flush=True)
            continue
        batches += 1
        for poi in report.armed:
            tf = getattr(poi.zone, "timeframe", None)
            armed.append({
                "poi": poi,
                "detection_tf": tf,
                "arm_ts": bar.timestamp,
                "arm_index": index,
            })
        if batches % 50 == 0:
            print(f"[opt-b] arm progress {batches} batches, {len(armed)} POIs, "
                  f"{round(time.perf_counter() - t0, 1)}s", flush=True)
    print(f"[opt-b] armed {len(armed)} POIs in {batches} batches "
          f"({round(time.perf_counter() - t0, 1)}s)", flush=True)
    return armed


def first_episodes(armed: list, series: dict) -> list:
    """First R2 sweep after each arm, per POI (the menu's first episode)."""
    from smc.dumb.rules import is_sweep

    episodes = []
    for rec in armed:
        tf = rec["detection_tf"]
        bars = series.get(tf)
        if not bars:
            continue
        start = bisect.bisect_right([c.timestamp for c in bars], rec["arm_ts"])
        for index in range(start, len(bars)):
            if is_sweep(bars[index], rec["poi"].zone):
                episodes.append({**rec, "sweep_index": index})
                break
    print(f"[opt-b] {len(episodes)} first episodes over {len(armed)} armed POIs",
          flush=True)
    return episodes


def _seed(engine, tier, series: dict, sweep_bar, tf):
    from smc.config.timeframe import Timeframe  # noqa: F401 (typing only)

    sweep_close = _close_ts(sweep_bar)
    seed = {sweep_bar.timeframe: [sweep_bar]}
    for ctf in tier.confirmation_tfs:
        bars = series[ctf]
        closes = [_close_ts(b) for b in bars]
        upto = bisect.bisect_right(closes, sweep_close)
        seed[ctf] = bars[max(0, upto - EPISODE_SEED_BARS): upto]
    return seed, sweep_close


def measure_episode(episode: dict, series: dict, *, same_bar_asof: bool) -> dict:
    """Replay one episode with one flag through ProductMenuEngine's public API."""
    from smc.orchestration.product_menu_mtf import (
        PRODUCT_MENU_TIERS,
        MenuEpisodeStatus,
        ProductMenuEngine,
    )
    from smc.utils.atr import latest_atr

    poi = episode["poi"]
    tf = episode["detection_tf"]
    tier = next((t for t in PRODUCT_MENU_TIERS if t.detection_tf is tf), None)
    if tier is None:
        return {"status": "not_a_menu_tier"}
    engine = ProductMenuEngine(symbol="XAUUSDm", same_bar_asof=same_bar_asof)
    if not engine.register_armed(poi, tf):
        return {"status": "not_registered"}
    det_bars = series[tf]
    sweep_bar = det_bars[episode["sweep_index"]]
    seed, sweep_close = _seed(engine, tier, series, sweep_bar, tf)
    seed_winners = engine.on_execution_bar(seed, as_of=sweep_close)
    if not engine.episodes():
        return {"status": "no_episode_opened"}
    episode_state = engine.episodes()[0]
    deadline_index = episode["sweep_index"] + tier.expiry_bars
    deadline = (_close_ts(det_bars[deadline_index])
                if deadline_index < len(det_bars) else None)

    events: list[tuple] = []
    for offset, bar in enumerate(det_bars[episode["sweep_index"] + 1:
                                         deadline_index + 1]):
        events.append((_close_ts(bar), bar.timeframe.minutes, bar.timeframe, bar))
    for ctf in tier.confirmation_tfs:
        for bar in series[ctf]:
            stamp = _close_ts(bar)
            if stamp <= sweep_close:
                continue
            if deadline is not None and stamp > deadline:
                break
            events.append((stamp, bar.timeframe.minutes, ctf, bar))
    events.sort(key=lambda item: (item[0], item[1]))

    # The seed call itself may already win (OPT-B: the sweep-bar interior is
    # eligible), so it is part of the measurement. The winner's route id embeds
    # the confirmation-stream index it was evaluated at, and at this point the
    # stream holds exactly the seeded bars.
    winner_bar = None
    winner_close_ts = None
    if seed_winners:
        winner = seed_winners[-1]
        winner_bar = _winner_bar(engine, winner)
        winner_close_ts = _close_ts(winner_bar) if winner_bar else sweep_close
    for stamp, _minutes, ftf, bar in events:
        if winner_bar is not None:
            break
        winners = engine.on_execution_bar({ftf: [bar]}, as_of=stamp)
        if winners:
            winner_bar = bar
            winner_close_ts = stamp
            break
        if episode_state.status is not MenuEpisodeStatus.ACTIVE:
            break
    if winner_bar is None:
        return {
            "status": "expired" if episode_state.status is MenuEpisodeStatus.EXPIRED
            else "no_winner",
            "sweep_close_ts": sweep_close.isoformat(),
        }

    ctf = winner_bar.timeframe
    atr_value = latest_atr(engine._confirm[ctf], engine.atr_period)
    atr = float(atr_value) if atr_value is not None else None
    label, distance_atr = timing_label(
        poi.zone.direction, poi.zone.bottom, poi.zone.top,
        winner_bar.close, atr,
    )
    return {
        "status": "won",
        "confirmation_tf": ctf.name,
        "trigger": engine.winners[-1].trigger,
        "close": winner_bar.close,
        "atr": atr,
        "label": label,
        "distance_atr": distance_atr,
        "winner_close_ts": winner_close_ts.isoformat(),
        "sweep_close_ts": sweep_close.isoformat(),
    }


def _winner_bar(engine, winner):
    """Confirm bar a seed-call winner was evaluated at (route id ``...@index``)."""
    tf = winner.confirmation_tf
    try:
        index = int(str(winner.route_id).rsplit("@", 1)[1])
    except (IndexError, ValueError):
        index = len(engine._confirm[tf]) - 1
    bars = engine._confirm[tf]
    if 0 <= index < len(bars):
        return bars[index]
    return bars[-1] if bars else None


def _pct(part: int, whole: int) -> float | None:
    return None if not whole else round(100.0 * part / whole, 2)


def _median(values):
    values = [v for v in values if v is not None]
    return round(statistics.median(values), 2) if values else None


def summarise(rows: list[dict]) -> dict:
    won = [r for r in rows if r["status"] == "won"]
    labels = [r["label"] for r in won]
    return {
        "episodes": len(rows),
        "won": len(won),
        "expired": sum(1 for r in rows if r["status"] == "expired"),
        "no_winner_before_deadline": sum(1 for r in rows if r["status"] == "no_winner"),
        "on_window": labels.count(LABEL_ON_WINDOW),
        "late": labels.count(LABEL_LATE),
        "on_window_pct": _pct(labels.count(LABEL_ON_WINDOW), len(won)),
        "late_pct": _pct(labels.count(LABEL_LATE), len(won)),
        "median_distance_atr_all_won": _median([r["distance_atr"] for r in won]),
        "median_distance_atr_late": _median(
            [r["distance_atr"] for r in won if r["label"] == LABEL_LATE]),
        "by_confirmation_tf": {
            name: {
                "won": sum(1 for r in won if r["confirmation_tf"] == name),
                "on_window": sum(1 for r in won
                                 if r["confirmation_tf"] == name
                                 and r["label"] == LABEL_ON_WINDOW),
            }
            for name in sorted({r["confirmation_tf"] for r in won})
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", default="primary", choices=sorted(WINDOWS))
    parser.add_argument("--limit", type=int, default=0,
                        help="probe only the first N episodes (smoke runs)")
    parser.add_argument("--exec-from", default=None,
                        help="smoke runs: override the window's execution start")
    args = parser.parse_args(argv)
    exec_from = _parse_day(args.exec_from) if args.exec_from else None

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    series = load_series(args.window, exec_from)
    armed = arm_pois(args.window, series, exec_from)
    episodes = first_episodes(armed, series)
    if args.limit:
        episodes = episodes[: args.limit]

    results = {"off": [], "on": []}
    t0 = time.perf_counter()
    for index, episode in enumerate(episodes, 1):
        for flag, key in ((False, "off"), (True, "on")):
            row = measure_episode(episode, series, same_bar_asof=flag)
            row.update({
                "poi_id": episode["poi"].id,
                "detection_tf": episode["detection_tf"].name,
                "direction": str(episode["poi"].zone.direction.value),
                "zone_low": episode["poi"].zone.bottom,
                "zone_high": episode["poi"].zone.top,
                "sweep_ts": series[episode["detection_tf"]][
                    episode["sweep_index"]].timestamp.isoformat(),
            })
            results[key].append(row)
        if index % 10 == 0:
            print(f"[opt-b] {index}/{len(episodes)} episodes "
                  f"({round(time.perf_counter() - t0, 1)}s)", flush=True)

    summary = {
        "banner": BANNER,
        "window": args.window,
        "window_spec": {k: str(v) for k, v in WINDOWS[args.window].items()},
        "exec_from_override": args.exec_from,
        "flag_name": "enable_opt_b_same_bar_confirm",
        "seed_bars": EPISODE_SEED_BARS,
        "episodes_probed": len(episodes),
        "off": summarise(results["off"]),
        "on": summarise(results["on"]),
        "delta": {
            "on_window_pct": [
                summarise(results["off"])["on_window_pct"],
                summarise(results["on"])["on_window_pct"],
            ],
            "late_pct": [
                summarise(results["off"])["late_pct"],
                summarise(results["on"])["late_pct"],
            ],
            "median_distance_atr_all_won": [
                summarise(results["off"])["median_distance_atr_all_won"],
                summarise(results["on"])["median_distance_atr_all_won"],
            ],
        },
        "caveats": [
            "First episode per POI only; later episodes after expiry are out of scope.",
            "Confirmation streams seeded with a bounded prefix (no long-history replay).",
            "Confirmation geometry only — no placement, fills, R7 or PnL is measured.",
            "The adapter/P1 path is unaffected by OPT-B by construction and is not re-run here.",
        ],
    }
    (OUT_ROOT / f"summary_{args.window}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")

    fields = ["detection_tf", "direction", "poi_id", "sweep_ts", "zone_low",
              "zone_high", "status", "confirmation_tf", "trigger", "close",
              "atr", "label", "distance_atr", "winner_close_ts"]
    for key in ("off", "on"):
        with (OUT_ROOT / f"episodes_{args.window}_{key}.csv").open(
            "w", newline="", encoding="utf-8"
        ) as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for row in results[key]:
                writer.writerow(row)

    print(json.dumps(summary["off"], indent=2), flush=True)
    print(json.dumps(summary["on"], indent=2), flush=True)
    print(f"[opt-b] wrote {OUT_ROOT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
