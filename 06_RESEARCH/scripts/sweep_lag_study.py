"""SWEEP-LAG FIDELITY STUDY (measure only — anchor before OPT-2).

Question: is the sweep attribution stamped on each path late or wrong
relative to the first physical pierce of the POI zone? If yes, confirm and
place metrics hang on a corrupted clock.

Paths, reported SEPARATELY (never blended):
* PATH A — MENU: ProductMenuEngine episodes (the OPT-1/OPT-4 smoke machinery:
  frozen ``opt_b_confirm_measure`` arm/episode harness, default path, OPT-B
  flag frozen OFF). The sweep stamp is the ENGINE's own episode stamp
  (``sweep_ts`` / ``sweep_close_ts``) — the same source OPT-1 reads.
* PATH B — ADAPTER: the research/partial path. It has NO sweep gate and NO
  sweep stamp BY CONSTRUCTION, so there is nothing to be late — path B gets a
  PROBE ONLY: on the identical frozen window, what a sweep-anchored clock
  WOULD have read (first full frozen-R2 bar post-arm, capped at the menu's
  20-detection-bar expiry window for comparability) vs the first pierce.
  The adapter's own confirm metrics anchor to ``arm_ts`` — sweep-lag is
  therefore N/A as a corruption source for B; the probe documents what an
  anchor there would look like. PROBE rows are never blended with menu rows.

DEFINITIONS (one formula each, frozen):
* ``t_pierce`` (EXACT): on the POI's detection-TF series, the FIRST closed
  bar whose extreme pierces the zone edge in the sweep direction WITHOUT the
  R2 close-back condition — LONG (demand): ``bar.low < zone.bottom``; SHORT
  (supply): ``bar.high > zone.top``. This is the pierce HALF of the locked
  R2 rule (``smc.dumb.rules.is_sweep``). Search window: bars after ``arm_ts``
  up to and INCLUDING the stamp bar's index — prefix-bounded, no lookahead.
  (The stamp bar always satisfies the pierce half, so a pierce inside the
  window exists by construction for any stamped episode.)
* ``sweep stamp`` bar (EXACT): the first closed bar post-arm satisfying the
  FULL frozen R2 rule (pierce AND close back inside). PATH A: the engine's
  stamp. PATH B: post-hoc probe, labelled PROBE.
* ``S1 lag_bars`` = index(stamp bar) − index(t_pierce) on the detection TF.
* ``S1 lag_atr`` = |stamp-bar extreme (LONG low / SHORT high) − pierce-bar
  extreme| / ATR, ATR = Wilder RMA (``smc.utils.atr``, period 14 — the menu
  engine's own ``atr_period``) computed over the CLOSED PREFIX up to the
  stamp bar index (no lookahead). By construction S1 lag_atr = 0.0 and
  lag_bars = 0 when the stamp bar is itself the first pierce.
* ``S2`` (MENU, OPT-1 fields; expired/no-completion ⇒ DATA_GAP, never
  invented): ``lag_bars_confirm_tf`` = (completion_ts − sweep_close_ts) in
  minutes / the winner's confirmation-TF minutes; ``lag_m5_minutes`` = the
  raw minutes; ``lag_atr`` = |completion_close − sweep-bar CLOSE| /
  ``atr_at_confirm`` (the OPT-1 Wilder confirm-TF prefix ATR at completion).
* ``S3`` — already measured by the OPT-4 join; cited in the note only.

Integrity: the engine's episode stamp must carry the SAME poi_id and zone
bounds as the armed POI and the SAME sweep_ts as the harness series (all
asserted — fail loud on mismatch); pierce searches are prefix-bounded;
missing data fails LOUD or is labelled DATA_GAP — never invented.

Report only: no PnL, no OPT-2, no R7 change, no detector retune.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import pickle
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

# Import the OPT-1/OPT-4 smoke chain FIRST (proven smc import order —
# avoids the partially-initialised-module cycle seen on the OPT-4 smoke).
from opt_b_confirm_measure import (  # noqa: E402  (frozen harness, unchanged)
    BANNER,
    _close_ts,
    _parse_day,
    _seed,
    first_episodes,
    load_series,
)
from confirm_vs_zone_opt1_smoke import (  # noqa: E402  (frozen replay style)
    replay_episode,
)
from smc.config.timeframe import Timeframe  # noqa: E402
from smc.core.enums import Direction  # noqa: E402
from smc.dumb.rules import is_sweep  # noqa: E402  (frozen R2, read-only)
from smc.orchestration.product_menu_mtf import (  # noqa: E402
    PRODUCT_MENU_TIERS,
    MenuEpisodeStatus,
    ProductMenuEngine,
)
from smc.utils.atr import latest_atr  # noqa: E402  (frozen Wilder convention)

OUT_ROOT = REPO_ROOT / "06_RESEARCH" / "results" / "sweep_lag"
ATR_PERIOD = 14         # the menu engine's own atr_period / PaperConfig default
PROBE_WINDOW_BARS = 20  # the menu's locked expiry window — comparability cap

MENU_CSV_FIELDS = [
    "poi_id", "detection_tf", "direction", "zone_low", "zone_high",
    "arm_ts", "status",
    "sweep_ts", "sweep_close_ts", "sweep_index",
    "pierce_index", "pierce_ts", "pierce_extreme",
    "sweep_extreme", "atr_at_sweep", "lag_bars", "lag_atr",
    "s2_status", "confirmation_tf", "completion_ts",
    "s2_lag_bars_confirm_tf", "s2_lag_m5_minutes", "s2_lag_atr",
]

ADAPTER_CSV_FIELDS = [
    "poi_id", "detection_tf", "direction", "zone_low", "zone_high",
    "arm_ts", "probe_status",
    "probe_sweep_index", "probe_sweep_ts",
    "pierce_index", "pierce_ts", "pierce_extreme",
    "probe_sweep_extreme", "atr_at_probe_sweep", "lag_bars", "lag_atr",
    "arm_to_pierce_bars",
]

PROBE_CSV_FIELDS = [
    "poi_id", "detection_tf", "direction", "zone_low", "zone_high",
    "arm_ts", "probe_status",
    "probe_sweep_index", "probe_sweep_ts",
    "pierce_index", "pierce_ts", "pierce_extreme",
    "probe_sweep_extreme", "atr_at_probe_sweep", "lag_bars", "lag_atr",
    "arm_to_pierce_bars",
]


# --------------------------------------------------------------------------- #
# Prefix-bounded primitives (EXACT, no lookahead)
# --------------------------------------------------------------------------- #
def _extreme_side(direction: Direction) -> str:
    """The sweep-direction extreme: the LOW for LONG, the HIGH for SHORT."""
    return "low" if direction is Direction.LONG else "high"


def _is_pierce(bar, zone_low: float, zone_high: float,
               direction: Direction) -> bool:
    """The pierce HALF of the frozen R2 rule (no close-back condition)."""
    low, high = sorted((float(zone_low), float(zone_high)))
    if direction is Direction.LONG:
        return bool(bar.low < low)
    if direction is Direction.SHORT:
        return bool(bar.high > high)
    return False


def first_pierce(bars, zone_low, zone_high, direction: Direction,
                 start: int, end_inclusive: int):
    """First pierce index in ``[start, end_inclusive]`` (inclusive cap).

    The stamp bar itself always satisfies the pierce half of R2, so a
    stamped episode always has a pierce inside this window by construction.
    """
    for index in range(start, end_inclusive + 1):
        if _is_pierce(bars[index], zone_low, zone_high, direction):
            return index
    return None


def first_full_sweep(bars, zone_low, zone_high, direction: Direction,
                     start: int, end_inclusive: int):
    """First FULL frozen-R2 bar index in ``[start, end_inclusive]``."""
    from smc.core.zone import Zone

    for index in range(start, end_inclusive + 1):
        probe_zone = Zone(top=zone_high, bottom=zone_low, direction=direction,
                          timeframe=bars[index].timeframe)
        if is_sweep(bars[index], probe_zone):
            return index
    return None


def _atr_at(bars, index: int):
    """Wilder prefix ATR at ``index`` (closed bars only — no lookahead)."""
    atr = latest_atr(list(bars[: index + 1]), ATR_PERIOD)
    return float(atr) if atr is not None and atr > 0 else None


def _s1_fields(bars, direction: Direction, start: int, sweep_index: int) -> dict:
    """S1 pierce/lag fields for ONE stamp bar (prefix-bounded)."""
    first_ = bars[0]
    zone_low = zone_high = None      # set by caller (row carries the bounds)
    raise NotImplementedError


# --------------------------------------------------------------------------- #
# Menu replay (frozen OPT-1/OPT-4 replay structure) + integrity capture
# --------------------------------------------------------------------------- #
def menu_replay(episode: dict, series: dict) -> dict:
    """Same replay as the OPT-1/OPT-4 smokes (default path, flags OFF),
    returning the ENGINE's episode record + the winner's OPT-1 fields."""
    poi = episode["poi"]
    tf = episode["detection_tf"]
    tier = next((t for t in PRODUCT_MENU_TIERS if t.detection_tf is tf), None)
    if tier is None:
        return {"status": "not_a_menu_tier"}
    engine = ProductMenuEngine(symbol="XAUUSDm", same_bar_asof=False)
    if not engine.register_armed(poi, tf):
        return {"status": "not_registered"}
    det_bars = series[tf]
    sweep_bar = det_bars[episode["sweep_index"]]
    if not is_sweep(sweep_bar, poi.zone):
        return {"status": "sweep_recheck_failed"}
    seed, sweep_close = _seed(engine, tier, series, sweep_bar, tf)
    engine.on_execution_bar(seed, as_of=sweep_close)
    if not engine.episodes():
        return {"status": "no_episode_opened"}
    episode_state = engine.episodes()[0]

    # Integrity: the ENGINE must stamp the SAME POI + zone bounds + sweep
    # event the harness attribution points to (fail loud on any mismatch).
    assert episode_state.poi_id == poi.id, "engine episode poi mismatch"
    assert (float(episode_state.zone.bottom),
            float(episode_state.zone.top)) == \
        (float(poi.zone.bottom), float(poi.zone.top)), \
        "engine episode zone bounds mismatch"
    assert episode_state.sweep_ts == sweep_bar.timestamp, \
        "engine sweep_ts stamp mismatch vs harness series"

    # The OPT-1 stamp's sweep_ts must equal the episode record (won rows only).
    stamp_probe = None
    if engine.winners:
        stamp_probe = _stamp_sweep_ts(engine.winners[-1])
        assert stamp_probe == episode_state.sweep_ts.isoformat(), \
            "OPT-1 stamp sweep_ts vs episode record mismatch"
    won = bool(engine.winners)
    deadline_index = episode["sweep_index"] + tier.expiry_bars
    deadline = (_close_ts(det_bars[deadline_index])
                if deadline_index < len(det_bars) else None)
    events = []
    for bar in det_bars[episode["sweep_index"] + 1: deadline_index + 1]:
        events.append((_close_ts(bar), bar.timeframe.minutes, bar.timeframe,
                       bar))
    for ctf in tier.confirmation_tfs:
        for bar in series[ctf]:
            stamp = _close_ts(bar)
            if stamp <= sweep_close:
                continue
            if deadline is not None and stamp > deadline:
                break
            events.append((stamp, bar.timeframe.minutes, ctf, bar))
    events.sort(key=lambda item: (item[0], item[1]))
    for _stamp, _minutes, ftf, bar in events:
        if won:
            break
        engine.on_execution_bar({ftf: [bar]}, as_of=_close_ts(bar))
        if engine.winners:
            won = True
            break
        if episode_state.status is not MenuEpisodeStatus.ACTIVE:
            break
    out = {
        "status": ("won" if won else
                   "expired" if episode_state.status
                   is MenuEpisodeStatus.EXPIRED else "no_winner"),
        "zone_low": float(poi.zone.bottom),
        "zone_high": float(poi.zone.top),
        "sweep_ts": episode_state.sweep_ts,
        "sweep_close_ts": episode_state.sweep_close_ts,
        "sweep_index": episode["sweep_index"],
        "sweep_bar_close": float(det_bars[episode["sweep_index"]].close),
    }
    if won and engine.winners:
        try:
            payload = json.loads(engine.winners[-1].candidate
                                 .signal_data_json or "{}")
            pstamp = payload.get("product_menu") or {}
        except (TypeError, ValueError):
            pstamp = {}
        out.update({
            "confirmation_tf": engine.winners[-1].confirmation_tf.name,
            "confirmation_tf_minutes":
                engine.winners[-1].confirmation_tf.minutes,
            "completion_ts": pstamp.get("completion_ts"),
            "completion_close": pstamp.get("completion_close"),
            "atr_at_confirm": pstamp.get("atr_at_confirm"),
            "stamp_sweep_ts": pstamp.get("sweep_ts"),
        })
    return out


def _stamp_sweep_ts(winner) -> str | None:
    try:
        payload = json.loads(winner.candidate.signal_data_json or "{}")
        return (payload.get("product_menu") or {}).get("sweep_ts")
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Menu S1 + S2 (per row)
# --------------------------------------------------------------------------- #
def _s1(row: dict, det_bars, poi_rec: dict) -> None:
    zone_low = row["zone_low"]
    zone_high = row["zone_high"]
    direction = Direction.LONG if row["direction"] == "long" \
        else Direction.SHORT
    sweep_index = row["sweep_index"]
    start = bisect.bisect_right([b.timestamp for b in det_bars],
                                poi_rec["arm_ts"])
    pierce = first_pierce(det_bars, zone_low, zone_high, direction,
                          start, sweep_index)
    if pierce is None:
        # Fail loud (kept as a labelled anomaly row): a stamped R2 bar is
        # itself a pierce by construction, so None here means the prefix
        # bounds or series are broken — never silently coerced.
        row.update({"pierce_index": None, "pierce_ts": None,
                    "pierce_extreme": None, "sweep_extreme": None,
                    "atr_at_sweep": None, "lag_bars": None, "lag_atr": None,
                    "s1_status": "NO_PIERCE_IN_PREFIX"})
        return
    pierce_bar, sweep_bar = det_bars[pierce], det_bars[sweep_index]
    pierce_extreme = float(getattr(pierce_bar, _extreme_side(direction)))
    sweep_extreme = float(getattr(sweep_bar, _extreme_side(direction)))
    atr = _atr_at(det_bars, sweep_index)
    row.update({
        "pierce_index": pierce,
        "pierce_ts": pierce_bar.timestamp.isoformat(),
        "pierce_extreme": pierce_extreme,
        "sweep_extreme": sweep_extreme,
        "atr_at_sweep": round(atr, 6) if atr else None,
        "lag_bars": sweep_index - pierce,
        "lag_atr": round(abs(sweep_extreme - pierce_extreme) / atr, 6)
        if atr else None,
        "s1_status": "OK",
    })


def _s2(row: dict) -> None:
    if row.get("status") != "won" or not row.get("completion_ts") \
            or row.get("completion_close") is None:
        row.update({"s2_status": "DATA_GAP", "confirmation_tf": None,
                    "s2_lag_bars_confirm_tf": None, "s2_lag_m5_minutes": None,
                    "s2_lag_atr": None})
        return
    completion_dt = datetime.fromisoformat(row["completion_ts"])
    delta_min = (completion_dt - row["sweep_close_ts"]).total_seconds() / 60.0
    atr = row.get("atr_at_confirm")
    row.update({
        "s2_status": "OK",
        "s2_lag_bars_confirm_tf": round(
            delta_min / row["confirmation_tf_minutes"], 3),
        "s2_lag_m5_minutes": delta_min,
        "s2_lag_atr": (round(abs(float(row["completion_close"])
                                 - float(row["sweep_bar_close"]))
                             / float(atr), 6)
                       if atr and float(atr) > 0 else None),
    })


# --------------------------------------------------------------------------- #
# PATH B — adapter probe (no sweep stamp in product; labelled PROBE)
# --------------------------------------------------------------------------- #
def adapter_probe(rec: dict, series: dict) -> dict:
    poi = rec["poi"]
    tf = rec["detection_tf"]
    bars = series.get(tf) or []
    zone_low, zone_high = float(poi.zone.bottom), float(poi.zone.top)
    direction = poi.zone.direction
    start = bisect.bisect_right([b.timestamp for b in bars], rec["arm_ts"])
    out = {
        "poi_id": poi.id,
        "detection_tf": tf.name,
        "direction": str(direction.value),
        "zone_low": zone_low,
        "zone_high": zone_high,
        "arm_ts": rec["arm_ts"].isoformat(),
    }
    if not bars or start >= len(bars):
        return {**out, "probe_status": "NO_DATA",
                "probe_sweep_index": None, "probe_sweep_ts": None,
                "pierce_index": None, "pierce_ts": None,
                "pierce_extreme": None, "probe_sweep_extreme": None,
                "atr_at_probe_sweep": None, "lag_bars": None, "lag_atr": None,
                "arm_to_pierce_bars": None}
    end_inclusive = min(start + PROBE_WINDOW_BARS - 1, len(bars) - 1)
    sweep = first_full_sweep(bars, zone_low, zone_high, direction,
                             start, end_inclusive)
    if sweep is None:
        return {**out, "probe_status": "NO_FULL_R2_IN_WINDOW",
                "probe_sweep_index": None, "probe_sweep_ts": None,
                "pierce_index": None, "pierce_ts": None,
                "pierce_extreme": None, "probe_sweep_extreme": None,
                "atr_at_probe_sweep": None, "lag_bars": None, "lag_atr": None,
                "arm_to_pierce_bars": None}
    pierce = first_pierce(bars, zone_low, zone_high, direction,
                          start, sweep)
    pierce_bar, sweep_bar = bars[pierce], bars[sweep]
    pierce_extreme = float(getattr(pierce_bar, _extreme_side(direction)))
    sweep_extreme = float(getattr(sweep_bar, _extreme_side(direction)))
    atr = _atr_at(bars, sweep)
    out.update({
        "probe_status": "OK",
        "probe_sweep_index": sweep,
        "probe_sweep_ts": sweep_bar.timestamp.isoformat(),
        "pierce_index": pierce,
        "pierce_ts": pierce_bar.timestamp.isoformat(),
        "pierce_extreme": pierce_extreme,
        "probe_sweep_extreme": sweep_extreme,
        "atr_at_probe_sweep": round(atr, 6) if atr else None,
        "lag_bars": sweep - pierce,
        "lag_atr": round(abs(sweep_extreme - pierce_extreme) / atr, 6)
        if atr else None,
        "arm_to_pierce_bars": pierce - start,
    })
    return out


def probe_fill_arm_to_pierce(rows: list[dict], series: dict) -> None:
    for row in rows:
        if row.get("pierce_index") is None:
            row["arm_to_pierce_bars"] = None
            continue
        tf_bars = series[Timeframe[row["detection_tf"]]]
        arm_index = bisect.bisect_right(
            [b.timestamp for b in tf_bars],
            datetime.fromisoformat(row["arm_ts"]))
        row["arm_to_pierce_bars"] = row.get("pierce_index") - arm_index


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def _median(values):
    vals = sorted(float(v) for v in values if v is not None)
    return round(vals[len(vals) // 2], 4) if vals else None


def _p90(values):
    vals = sorted(float(v) for v in values if v is not None)
    if not vals:
        return None
    rank = min(int(0.9 * (len(vals) - 1) + 0.5), len(vals) - 1)
    return round(vals[rank], 4)


def _stats(rows, key):
    return {"n": sum(1 for r in rows if r.get(key) is not None),
            "median": _median([r.get(key) for r in rows]),
            "p90": _p90([r.get(key) for r in rows])}


def _distribution(rows, key):
    counts = {0: 0, 1: 0, "ge2": 0}
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        if value == 0:
            counts[0] += 1
        elif value == 1:
            counts[1] += 1
        else:
            counts["ge2"] += 1
    return counts


def summarise_menu(rows: list[dict]) -> dict:
    s1 = [r for r in rows if r.get("s1_status") == "OK"]
    won = [r for r in rows if r.get("status") == "won"]
    return {
        "episodes": len(rows),
        "won": len(won),
        "data_gap_s2": sum(1 for r in rows if r.get("s2_status") == "DATA_GAP"),
        "S1_lag_bars": _stats(s1, "lag_bars"),
        "S1_lag_atr": _stats(s1, "lag_atr"),
        "S1_lag_bars_distribution": _distribution(s1, "lag_bars"),
        "S2_lag_bars_confirm_tf": _stats(won, "s2_lag_bars_confirm_tf"),
        "S2_lag_m5_minutes": _stats(won, "s2_lag_m5_minutes"),
        "S2_lag_atr": _stats(won, "s2_lag_atr"),
    }


def summarise_adapter(rows: list[dict]) -> dict:
    s1 = [r for r in rows if r.get("lag_bars") is not None]
    pierced = [r for r in rows if r.get("pierce_index") is not None]
    return {
        "probed": len(rows),
        "pierced_in_window": len(pierced),
        "full_r2_in_window": len(s1),
        "no_full_r2_in_window": sum(
            1 for r in rows if r.get("probe_status") == "NO_FULL_R2_IN_WINDOW"),
        "S1_probe_lag_bars": _stats(s1, "lag_bars"),
        "S1_probe_lag_atr": _stats(s1, "lag_atr"),
        "S1_probe_lag_bars_distribution": _distribution(s1, "lag_bars"),
        "arm_to_pierce_bars": _stats(pierced, "arm_to_pierce_bars"),
    }


# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", default="primary",
                        choices=("primary", "secondary"))
    parser.add_argument("--exec-from", default="2025-10-01",
                        help="the frozen OPT-1/OPT-4 primary-subset cut")
    parser.add_argument("--max-episodes", type=int, default=0)
    args = parser.parse_args(argv)
    exec_from = _parse_day(args.exec_from) if args.exec_from else None

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    series = load_series(args.window, exec_from)

    # Armed POIs: reuse the OPT-4 checkpoint when it matches THIS window and
    # cut (same frozen harness product); else arm and checkpoint. Fail loud
    # on any mismatch — the two windows are never blended.
    checkpoint = OUT_ROOT / f"arming_{args.window}_{args.exec_from}.pkl"
    opt4 = REPO_ROOT / "06_RESEARCH" / "results" / "confirm_vs_zone_opt4" / \
        f"arming_{args.window}_{args.exec_from}.pkl"
    if checkpoint.exists():
        with checkpoint.open("rb") as fh:
            armed = pickle.load(fh)
        print(f"[sweep] checkpoint: loaded {len(armed)} armed POIs "
              f"from {checkpoint.name}", flush=True)
    elif opt4.exists():
        with opt4.open("rb") as fh:
            armed = pickle.load(fh)
        print(f"[sweep] reusing the OPT-4 arming checkpoint "
              f"({len(armed)} armed POIs, same window+cut)", flush=True)
    else:
        from opt_b_confirm_measure import arm_pois
        armed = arm_pois(args.window, series, exec_from)
        with checkpoint.open("wb") as fh:
            pickle.dump(armed, fh, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"[sweep] checkpoint: saved {len(armed)} armed POIs", flush=True)
    if not armed:
        raise SystemExit("[sweep] FAIL LOUD: zero armed POIs — refusing")

    episodes = first_episodes(armed, series)
    if args.max_episodes:
        episodes = episodes[: args.max_episodes]
    if not episodes:
        raise SystemExit("[sweep] FAIL LOUD: zero first episodes — refusing")

    # ---------------- PATH A — MENU (engine's own stamps) ---------------- #
    recs_by_poi = {r["poi"].id: r for r in armed}
    menu_rows: list[dict] = []
    t0 = time.perf_counter()
    for index, episode in enumerate(episodes, 1):
        poi = episode["poi"]
        rec = recs_by_poi.get(poi.id)
        if rec is None:
            raise SystemExit(
                f"[sweep] FAIL LOUD: episode poi {poi.id} not in the armed "
                f"records — sweep attribution would be corrupt")
        det_bars = series[episode["detection_tf"]]
        result = menu_replay(episode, series)
        row = {
            "poi_id": poi.id,
            "detection_tf": episode["detection_tf"].name,
            "direction": str(poi.zone.direction.value),
            "zone_low": result.get("zone_low", float(poi.zone.bottom)),
            "zone_high": result.get("zone_high", float(poi.zone.top)),
            "arm_ts": rec["arm_ts"].isoformat(),
            "status": result.get("status"),
        }
        if result.get("status") in ("not_a_menu_tier", "not_registered",
                                    "no_episode_opened", "sweep_recheck_failed"):
            row.update({"sweep_ts": None, "sweep_close_ts": None,
                        "sweep_index": None, "s1_status": "DATA_GAP",
                        "s2_status": "DATA_GAP"})
            menu_rows.append(row) if False else menu_rows.append(row)
            continue
        row.update({
            "sweep_ts": result["sweep_ts"].isoformat(),
            "sweep_close_ts": result["sweep_close_ts"].isoformat(),
            "sweep_index": result["sweep_index"],
        })
        _s1(row, det_bars, rec)
        for key in ("status", "confirmation_tf", "confirmation_tf_minutes",
                    "completion_ts", "completion_close", "atr_at_confirm",
                    "sweep_bar_close"):
            if key in result:
                row[key] = result[key]
        _s2(row)
        menu_rows.append(row)
        if index % 10 == 0 or index == len(episodes):
            print(f"[sweep] menu {index}/{len(episodes)} "
                  f"({round(time.perf_counter() - t0, 1)}s)", flush=True)

    # ---------------- PATH B — ADAPTER PROBE ---------------- #
    adapter_rows = [adapter_probe(rec, series) for rec in armed]
    probe_fill_arm_to_pierce(adapter_rows, series)

    summary = {
        "banner": BANNER,
        "measure": "SWEEP-LAG FIDELITY (sweep stamp vs first pierce — "
                   "measure only, paths never blended)",
        "window": args.window,
        "exec_from_override": args.exec_from,
        "opt_b_flag": "frozen OFF (POLICY_OPT_B_FLAG_2026-11-07)",
        "atr_period": ATR_PERIOD,
        "probe_window_bars": PROBE_WINDOW_BARS,
        "menu": summarise_menu(menu_rows),
        "adapter": summarise_adapter(adapter_rows),
        "caveats": [
            "PATH A uses the ENGINE's own sweep stamps (OPT-1/OPT-4 "
            "machinery, default flag OFF). PATH B has NO sweep stamp in "
            "product — the adapter table is a PROBE (post-hoc first full R2 "
            "capped at the menu's 20-detection-bar window), never blended "
            "with the menu table.",
            "Pierce = the pierce HALF of the frozen R2 rule (no close-back "
            "condition), on the POI's detection TF, prefix-bounded "
            "searches only (no lookahead).",
            "ATR = Wilder RMA, period 14 (the menu engine's atr_period), at "
            "the stamp index over the closed prefix only.",
            "Counts and geometry only — no expectancy, no edge, no PnL.",
        ],
    }
    (OUT_ROOT / f"summary_{args.window}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")

    # Serialize rows (datetimes → ISO) and export CSVs.
    def _iso(value):
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    menu_export = [{k: _iso(v) for k, v in row.items()} for row in menu_rows]
    with (OUT_ROOT / "episodes_menu.csv").open(
        "w", newline="", encoding="utf-8"
    ) as fh:
        writer = csv.DictWriter(fh, fieldnames=MENU_CSV_FIELDS,
                                extrasaction="ignore")
        writer.writeheader()
        for row in menu_export:
            writer.writerow(row)
    with (OUT_ROOT / "episodes_adapter.csv").open(
        "w", newline="", encoding="utf-8"
    ) as fh:
        writer = csv.DictWriter(fh, fieldnames=PROBE_CSV_FIELDS,
                                extrasaction="ignore")
        writer.writeheader()
        for row in adapter_rows:
            writer.writerow(row)

    print(json.dumps(summary["menu"], indent=2), flush=True)
    print(json.dumps(summary["adapter"], indent=2), flush=True)
    print(f"[sweep] wrote {OUT_ROOT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
