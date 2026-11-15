"""OPT-4 WIDER JOIN — MENU PATH ONLY (measurement; sweep-lag-informed).

Extends the OPT-4 place-side join smoke (`confirm_vs_zone_opt4_smoke.py`,
which itself extends the frozen OPT-1 replay) from the primary SUBSET
(exec-from 2025-10-01) to the FULL pack-aligned primary window:
WINDOWS["primary"] = load_from 2025-05-01, **exec_from 2025-06-01 →
exec_to 2025-11-30** (no exec-from override — the natural window). Goal:
LATE n above the pre-registered n>=10 bar where possible.

Scope (bound by the 2026-11-08 (2) sweep-lag ruling  ANCHOR_PATH_SPECIFIC):
* MENU PATH ONLY. The adapter (no sweep gate, no sweep stamp in product) is
  EXCLUDED from this join by construction — never blended into any table.
* OPT-B flag frozen OFF (`POLICY_OPT_B_FLAG_2026-11-07`); R7 unchanged
  (verdicts READ through the REAL frozen `zone_place_allowed`, never
  re-implemented); no OPT-2 implementation; no detector retune; no PnL.

Reuse (everything frozen, identical code paths as the OPT-4 smoke):
* replay = ``confirm_vs_zone_opt1_smoke.replay_episode`` (engine's own OPT-1
  stamp: label_at_confirm / distance_at_confirm_atr / completion fields).
* submit frame = ``confirm_vs_zone_opt4_smoke.submit_frame`` (first closed M5
  execution bar at/after completion_ts; distance_at_place_atr via the ONE
  OPT-1 convention — nearest zone edge, 0 inside, Wilder prefix ATR(14);
  r7_verdict = placed | SKIP_PLACE_FAR_FROM_ZONE via the REAL guard).
* S2 context (report-only, from the sweep-lag study's definitions):
  sweep_close_ts -> completion_ts in raw minutes and in confirm-TF bars
  (DATA_GAP when the completion is absent — never invented).

Arming checkpoint: `arming_{window}_{exec-from}.pkl` under the output dir —
a DIFFERENT window/cut than the OPT-4 smoke checkpoint, so the two are never
cross-blended (fail loud on zero armed POIs / zero episodes).

CSVs are byte-stable: fixed fieldnames, rows in deterministic episode order.
No trades are placed — analysis-only over stamps (documented caveat).
"""

from __future__ import annotations

import argparse
import csv
import json
import pickle
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

# Proven smc import order: OPT-B harness first, then the OPT-1 smoke (whose
# product imports initialise the smc package graph), then the OPT-4 smoke
# (which pulls the frozen risk guard).
from opt_b_confirm_measure import (  # noqa: E402  (frozen harness, unchanged)
    BANNER,
    WINDOWS,
    _parse_day,
    arm_pois,
    first_episodes,
    load_series,
)
from confirm_vs_zone_opt1_smoke import (  # noqa: E402  (frozen replay reuse)
    replay_episode,
)
from confirm_vs_zone_opt4_smoke import (  # noqa: E402  (frozen join reuse)
    CSV_FIELDS as OPT4_CSV_FIELDS,
    submit_frame,
)
from smc.risk.fill_regime_policy import (  # noqa: E402 (REAL frozen guard)
    SKIP_PLACE_FAR_FROM_ZONE,
)

OUT_WIDER = REPO_ROOT / "06_RESEARCH" / "results" / "confirm_vs_zone_opt4_wider"

CSV_FIELDS = OPT4_CSV_FIELDS + [
    "status", "sweep_ts", "sweep_close_ts",
    "s2_lag_confirm_bars", "s2_lag_m5_minutes",
]

LATE_LABEL = "LATE"


def sweep_close_ts_of(episode: dict, series: dict) -> str | None:
    from datetime import timedelta

    det_bars = series.get(episode["detection_tf"])
    if not det_bars:
        return None
    bar = det_bars[episode["sweep_index"]]
    close = bar.timestamp + timedelta(minutes=bar.timeframe.minutes)
    return close.isoformat()


def s2_context(row: dict) -> None:
    """sweep_close_ts -> completion_ts lag, raw minutes + confirm-TF bars."""
    from smc.config.timeframe import Timeframe

    row["s2_lag_m5_minutes"] = None
    row["s2_lag_confirm_bars"] = None
    completion_ts = row.get("completion_ts")
    sweep_close_ts = row.get("sweep_close_ts")
    if not completion_ts or not sweep_close_ts:
        return                            # DATA_GAP by absence — never invented
    completion_dt = datetime.fromisoformat(completion_ts)
    sweep_dt = datetime.fromisoformat(sweep_close_ts)
    minutes = (completion_dt - sweep_dt).total_seconds() / 60.0
    row["s2_lag_m5_minutes"] = minutes
    conf_tf = row.get("confirmation_tf")
    if conf_tf and getattr(Timeframe, conf_tf, None) is not None:
        row["s2_lag_confirm_bars"] = round(
            minutes / Timeframe[conf_tf].minutes, 3)


def _median(values):
    vals = sorted(float(v) for v in values if v is not None)
    return round(vals[len(vals) // 2], 4) if vals else None


def summarise_wider(rows: list[dict]) -> dict:
    """label x r7_verdict counts + placed/skip split + medians (full n)."""
    won = [r for r in rows if r.get("r7_verdict")]
    labels = sorted({r["label_at_confirm"] for r in won
                     if r.get("label_at_confirm")})
    join = {}
    for label in labels:
        group = [r for r in won if r["label_at_confirm"] == label]
        placed = [r for r in group if r["r7_verdict"] == "placed"]
        skip_far = [r for r in group
                    if r["r7_verdict"] == SKIP_PLACE_FAR_FROM_ZONE]
        other = len(group) - len(placed) - len(skip_far)
        join[label] = {
            "n": len(group),
            "n_placed": len(placed),
            "n_skip_far": len(skip_far),
            "n_other_verdict": other,
            "skip_far_rate": (round(len(skip_far) / len(group), 4)
                              if group else None),
            "median_distance_at_confirm_atr": _median(
                [r.get("distance_at_confirm_atr") for r in group]),
            "median_distance_at_place_atr": _median(
                [r.get("distance_at_place_atr") for r in group]),
            "median_s2_lag_confirm_bars": _median(
                [r.get("s2_lag_confirm_bars") for r in group]),
            "median_s2_lag_m5_minutes": _median(
                [r.get("s2_lag_m5_minutes") for r in group]),
            "confirm_tf_mix": {
                name: sum(1 for r in group if r.get("confirmation_tf") == name)
                for name in sorted({r.get("confirmation_tf", "")
                                    for r in group} if group else [])
            },
        }
    return {
        "n_episodes": len(rows),
        "n_won": sum(1 for r in rows if r.get("status") == "won"),
        "n_expired": sum(1 for r in rows if r.get("status") == "expired"),
        "n_no_winner": sum(1 for r in rows
                           if r.get("status") == "no_winner"),
        "n_with_verdict": len(won),
        "n_missing_label": sum(1 for r in won if not r.get("label_at_confirm")),
        "label_x_r7_verdict": join,
    }


def hypothesis_check(rows: list[dict]) -> dict:
    """Report-only: LATE_MOSTLY_SKIPPED_BY_R7 = YES iff LATE n>=10 AND
    skip-far rate >= 80%; else NO (n>=10) / INSUFFICIENT (n<10)."""
    won = [r for r in rows if r.get("r7_verdict")]
    late = [r for r in won if r.get("label_at_confirm") == LATE_LABEL]
    skipped = sum(1 for r in late if r["r7_verdict"] == SKIP_PLACE_FAR_FROM_ZONE)
    rate = round(skipped / len(late), 4) if late else None
    if len(late) < 10:
        verdict = "INSUFFICIENT"
    elif rate >= 0.8:
        verdict = "YES"
    else:
        verdict = "NO"
    return {
        "claim": "LATE mostly skipped by R7 (pre-registered: n>=10 AND "
                 "skip_far_rate >= 0.80)",
        "rule": "YES if LATE n>=10 and skip rate >=80% else NO/INSUFFICIENT",
        "late_n": len(late),
        "late_skip_far": skipped,
        "late_placed": sum(1 for r in late if r["r7_verdict"] == "placed"),
        "skip_far_rate": rate,
        "verdict": verdict,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", default="primary",
                        choices=sorted(WINDOWS))
    parser.add_argument("--exec-from", default=None,
                        help="leave EMPTY for the natural pack-aligned window "
                             "start (primary = 2025-06-01)")
    parser.add_argument("--max-episodes", type=int, default=0)
    args = parser.parse_args(argv)
    exec_from = _parse_day(args.exec_from) if args.exec_from else None
    cut_key = args.exec_from or "natural"

    OUT_WIDER.mkdir(parents=True, exist_ok=True)
    spec = dict(WINDOWS[args.window])
    if exec_from is not None:
        spec["exec_from"] = exec_from

    series = load_series(args.window, exec_from)

    # Arming checkpoint keyed by window + cut — never cross-blend with the
    # OPT-4 smoke's 2025-10-01 checkpoint (different dir + different key).
    checkpoint = OUT_WIDER / f"arming_{args.window}_{cut_key}.pkl"
    if checkpoint.exists():
        with checkpoint.open("rb") as fh:
            armed = pickle.load(fh)
        print(f"[opt4w] checkpoint: loaded {len(armed)} armed POIs "
              f"from {checkpoint.name}", flush=True)
    else:
        armed = arm_pois(args.window, series, exec_from)
        if not armed:
            raise SystemExit("[opt4w] FAIL LOUD: zero armed POIs — refusing")
        with checkpoint.open("wb") as fh:
            pickle.dump(armed, fh, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"[opt4w] checkpoint: saved {len(armed)} armed POIs "
              f"to {checkpoint.name}", flush=True)
    episodes = first_episodes(armed, series)
    if not episodes:
        raise SystemExit("[opt4w] FAIL LOUD: zero first episodes — refusing")
    if args.max_episodes:
        episodes = episodes[: args.max_episodes]

    rows: list[dict] = []
    t0 = time.perf_counter()
    for index, episode in enumerate(episodes, 1):
        won = replay_episode(episode, series)
        poi = episode["poi"]
        zone = poi.zone
        row = {
            "poi_id": poi.id,
            "detection_tf": episode["detection_tf"].name,
            "direction": str(zone.direction.value),
            "zone_low": zone.bottom,
            "zone_high": zone.top,
            "status": won.get("status"),
            "confirmation_tf": won.get("confirmation_tf"),
            "trigger": won.get("trigger"),
            "label_at_confirm": won.get("label_at_confirm"),
            "completion_ts": won.get("completion_ts"),
            "completion_close": won.get("completion_close"),
            "atr_at_confirm": won.get("atr_at_confirm"),
            "distance_at_confirm_atr": won.get("distance_at_confirm_atr"),
            "sweep_ts": series[episode["detection_tf"]][
                episode["sweep_index"]].timestamp.isoformat(),
            "sweep_close_ts": sweep_close_ts_of(episode, series),
        }
        if won.get("status") == "won":
            row.update(submit_frame(row, series))
        s2_context(row)
        rows.append(row)
        if index % 25 == 0 or index == len(episodes):
            print(f"[opt4w] {index}/{len(episodes)} episodes "
                  f"({round(time.perf_counter() - t0, 1)}s)", flush=True)

    summary = {
        "banner": BANNER,
        "measure": "OPT-4 WIDER place-side join, MENU PATH ONLY (label x "
                   "r7_verdict — report only, NOT a performance or "
                   "expectancy claim)",
        "window": args.window,
        "window_spec": {k: str(v) for k, v in spec.items()},
        "natural_window": exec_from is None,
        "cut": cut_key,
        "sweep_lag_ruling": "ANCHOR_PATH_SPECIFIC (2026-11-08 (2)) — menu "
                            "stamp verified; ADAPTER EXCLUDED from this "
                            "join (no sweep stamp in product)",
        "opt_b_flag": "frozen OFF (POLICY_OPT_B_FLAG_2026-11-07)",
        "r7": "READ-only through the REAL frozen zone_place_allowed — "
              "unchanged",
        "atr_period_place": 14,
        "join": summarise_wider(rows),
        "hypothesis_check": hypothesis_check(rows),
        "caveats": [
            "Submit approximation: first closed M5 execution bar at/after "
            "completion_ts (the loop queues the winner the moment it "
            "appears); no risk-side blocks (board/news/session/spread) "
            "modelled — conditional on an accepted risk verdict.",
            "R9-deferred later placements out of scope (at-submit join).",
            "First episode per armed POI only (frozen harness convention).",
            "S2 context = sweep_close_ts -> completion_ts (raw minutes + "
            "confirm-TF bars); absent completion => not reported, never "
            "invented.",
            "Analysis-only over stamps — no trades placed; CSVs are "
            "byte-stable (fixed fields, deterministic episode order).",
            "MENU PATH ONLY — the adapter is excluded per the sweep-lag "
            "ruling (no sweep stamp in product on that path).",
            "Counts and geometry only — no expectancy, no edge, no PnL; "
            "no OPT-2 implementation.",
        ],
    }
    (OUT_WIDER / f"summary_{args.window}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")

    with (OUT_WIDER / f"join_{args.window}.csv").open(
        "w", newline="", encoding="utf-8"
    ) as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS,
                                extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(json.dumps(summary["join"], indent=2), flush=True)
    print(json.dumps(summary["hypothesis_check"], indent=2), flush=True)
    print(f"[opt4w] wrote {OUT_WIDER}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
