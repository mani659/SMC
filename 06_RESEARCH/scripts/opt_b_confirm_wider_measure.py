"""OPT-B wider-menu measurement — flag OFF vs ON across BOTH frozen windows.

WIDER MEASURE ONLY. DIAGNOSTIC — NOT EDGE — NOT A PERFORMANCE CLAIM.

Authority: Lead Architect "WIDER MENU MEASURE — OPT-B OFF vs ON" (GO).
The live flag stays OFF (`config/live_demo.json`
``enable_opt_b_same_bar_confirm: false``); no R7/R9/threshold/product edit.

This script does NOT re-implement the measurement. It imports the frozen
harness from ``opt_b_confirm_measure`` (same ``ProductMenuEngine`` path, same
frozen R2 sweep rule, same ``timing_label`` = FR-3/R7 band) and:

* runs the FULL frozen windows (no ``--exec-from`` smoke override):
    primary   2025-06-01 → 2025-11-30   (load 2025-05-01)
    secondary 2023-12-01 → 2025-05-31   (load 2023-11-01, 18 months)
* adds the wider-measure metrics on top of the frozen summary:
    - ``n_armed`` / ``n_with_confirm_or_route`` (defined below),
    - ON_WINDOW / LATE percentages per flag,
    - median AND p90 zone-distance-ATR at the confirm decision,
    - same-bar wins (ON only: confirmation close <= sweep-bar close — the
      class OFF structurally cannot see),
    - wins gained/lost OFF → ON and episodes expired per flag,
    - R7 skip observability statement (the harness places nothing, so R7 is
      NOT observable here by construction — unchanged, never "fixed").
* writes ``06_RESEARCH/results/opt_b_confirm_wider/``.

Definitions (pinned, so the numbers are auditable):

* ``n_armed`` — POIs armed by the frozen `MultiTFProductRuntime` in the
  window (all menu detection TFs).
* ``n_with_confirm_or_route`` — union denominator: episodes where AT LEAST
  ONE flag produced a menu confirmation (a winning route) before expiry.
  Episodes expired under both flags are excluded from label percentages
  (they never reach a confirm decision) but are reported.
* ``on_window_pct`` / ``late_pct`` — share of each flag's CONFIRMED wins
  labelled ON_WINDOW / LATE by the frozen FR-3/R7 band rule.

Usage::

    PYTHONPATH=04_SRC python -X utf8 \
        06_RESEARCH/scripts/opt_b_confirm_wider_measure.py [--window both]

    # rebuild summary_both_windows.json from the two existing summaries
    PYTHONPATH=04_SRC python -X utf8 \
        06_RESEARCH/scripts/opt_b_confirm_wider_measure.py --compose-only
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

from opt_b_confirm_measure import (                          # noqa: E402
    BANNER,
    EPISODE_SEED_BARS,
    arm_pois,
    first_episodes,
    load_series,
    measure_episode,
    summarise,
)

from poi_timing_early_late_study import (                    # noqa: E402
    LABEL_LATE,
    LABEL_ON_WINDOW,
    WINDOWS,
)

OUT_ROOT = REPO_ROOT / "06_RESEARCH" / "results" / "opt_b_confirm_wider"

#: The two frozen windows, unchanged from the timing/fill-takeability captures.
#: No new composition is invented here.
WINDOW_LIST = ("primary", "secondary")


def _p90(values) -> float | None:
    """Nearest-rank p90 (small-n honest: no interpolation smoothing)."""
    clean = sorted(v for v in values if v is not None)
    if not clean:
        return None
    index = max(0, min(len(clean) - 1, int(round(0.9 * (len(clean) - 1)))))
    return round(clean[index], 2)


def _bar_counts(series: dict) -> dict:
    return {tf.name: len(bars) for tf, bars in series.items()}


def wider_summary(rows: list[dict], win_summary: dict) -> dict:
    """Frozen summary + median/p90 + label mix for the wider measure."""
    won = [r for r in rows if r.get("status") == "won"]
    distances = [r.get("distance_atr") for r in won
                 if r.get("distance_atr") is not None]
    labels = [r.get("label") for r in won]
    return {
        **win_summary,
        "confirmed": len(won),
        "label_mix": {
            LABEL_ON_WINDOW: labels.count(LABEL_ON_WINDOW),
            LABEL_LATE: labels.count(LABEL_LATE),
            "other": len(labels) - labels.count(LABEL_ON_WINDOW)
                     - labels.count(LABEL_LATE),
        },
        "median_distance_atr_at_confirm": (
            round(statistics.median(distances), 2) if distances else None
        ),
        "p90_distance_atr_at_confirm": _p90(distances),
        "median_distance_atr_late": (
            round(statistics.median(
                [r["distance_atr"] for r in won
                 if r.get("label") == LABEL_LATE]), 2)
            if [r for r in won if r.get("label") == LABEL_LATE] else None
        ),
        "same_bar_wins": sum(
            1 for r in won
            if r.get("winner_close_ts") and r.get("sweep_close_ts")
            and r["winner_close_ts"] <= r["sweep_close_ts"]
        ),
    }


def run_window(window: str) -> dict:
    spec = WINDOWS[window]
    print(f"[wider] === window {window}: exec {spec['exec_from']} → "
          f"{spec['exec_to']} (load {spec['load_from']}) ===", flush=True)
    t0 = time.perf_counter()
    series = load_series(window)
    bars = _bar_counts(series)
    armed = arm_pois(window, series)
    episodes = first_episodes(armed, series)
    print(f"[wider] {window}: armed {len(armed)} POIs, {len(episodes)} first "
          f"episodes ({round(time.perf_counter() - t0, 1)}s)", flush=True)

    results = {"off": [], "on": []}
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
            print(f"[wider] {window}: {index}/{len(episodes)} episodes "
                  f"({round(time.perf_counter() - t0, 1)}s)", flush=True)

    off = wider_summary(results["off"], summarise(results["off"]))
    on = wider_summary(results["on"], summarise(results["on"]))
    # union denominator: episodes with a confirmation under EITHER flag
    union = [i for i, (o, n) in enumerate(zip(results["off"], results["on"]))
             if o.get("status") == "won" or n.get("status") == "won"]
    gained = [i for i, (o, n) in enumerate(zip(results["off"], results["on"]))
              if n.get("status") == "won" and o.get("status") != "won"]
    lost = [i for i, (o, n) in enumerate(zip(results["off"], results["on"]))
            if o.get("status") == "won" and n.get("status") != "won"]

    summary = {
        "banner": BANNER,
        "window": window,
        "window_spec": {k: str(v) for k, v in spec.items()},
        "exec_from_override": None,
        "flag_name": "enable_opt_b_same_bar_confirm",
        "seed_bars": EPISODE_SEED_BARS,
        "bar_counts": bars,
        "n_armed": len(armed),
        "n_episodes_probed": len(episodes),
        "n_with_confirm_or_route": len(union),
        "off": off,
        "on": on,
        "delta": {
            "on_window_pct": [off["on_window_pct"], on["on_window_pct"]],
            "late_pct": [off["late_pct"], on["late_pct"]],
            "confirmed": [off["confirmed"], on["confirmed"]],
            "median_distance_atr_at_confirm": [
                off["median_distance_atr_at_confirm"],
                on["median_distance_atr_at_confirm"],
            ],
            "p90_distance_atr_at_confirm": [
                off["p90_distance_atr_at_confirm"],
                on["p90_distance_atr_at_confirm"],
            ],
            "wins_gained_off_to_on": len(gained),
            "wins_lost_off_to_on": len(lost),
            "same_bar_wins_on_only": on["same_bar_wins"],
        },
        "r7_observable": False,
        "r7_note": (
            "R7 is a PLACE guard on the routed candidate. This harness places "
            "nothing (confirmation geometry only), so R7 skips are not "
            "observable here; OPT-B does not change R7 and no R7 claim is made."
        ),
        "caveats": [
            "First episode per POI only; later episodes after expiry are out of scope.",
            "Confirmation streams seeded with a bounded prefix (no long-history replay).",
            "Confirmation geometry only — no placement, fills, R7 or PnL is measured.",
            "The adapter/P1 path is unaffected by OPT-B by construction and is not re-run here.",
            "Small-n honesty: percentages are counts over confirmed wins; no stability claim is made.",
        ],
    }
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / f"summary_{window}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")

    fields = ["detection_tf", "direction", "poi_id", "sweep_ts", "zone_low",
              "zone_high", "status", "confirmation_tf", "trigger", "close",
              "atr", "label", "distance_atr", "winner_close_ts",
              "sweep_close_ts"]
    for key in ("off", "on"):
        with (OUT_ROOT / f"episodes_{window}_{key}.csv").open(
            "w", newline="", encoding="utf-8"
        ) as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for row in results[key]:
                writer.writerow(row)

    print(f"[wider] {window} DONE in {round(time.perf_counter() - t0, 1)}s", flush=True)
    return summary


def _combined(summaries: dict) -> dict:
    """Count-weighted totals across windows (never an average of percentages)."""
    out = {}
    for key in ("off", "on"):
        confirmed = sum(s[key]["confirmed"] for s in summaries.values())
        on_window = sum(s[key]["on_window"] for s in summaries.values())
        late = sum(s[key]["late"] for s in summaries.values())
        other = sum(s[key]["label_mix"]["other"] for s in summaries.values())
        expired = sum(s[key]["expired"] for s in summaries.values())
        out[key] = {
            "confirmed": confirmed,
            "expired": expired,
            "on_window": on_window,
            "late": late,
            "beyond_stop_side": other,
            "on_window_pct": (round(100.0 * on_window / confirmed, 2)
                              if confirmed else None),
            "late_pct": (round(100.0 * late / confirmed, 2)
                         if confirmed else None),
        }
    out["wins_gained_off_to_on"] = sum(
        s["delta"]["wins_gained_off_to_on"] for s in summaries.values())
    out["wins_lost_off_to_on"] = sum(
        s["delta"]["wins_lost_off_to_on"] for s in summaries.values())
    out["same_bar_wins_on_only"] = sum(
        s["delta"]["same_bar_wins_on_only"] for s in summaries.values())
    return out


def compose_payload(summaries: dict) -> dict:
    """The cross-window comparison artifact (also usable post-hoc)."""
    return {
        "banner": BANNER,
        "flag_name": "enable_opt_b_same_bar_confirm",
        "windows": summaries,
        "comparison": {
            w: {
                "n_armed": s["n_armed"],
                "n_with_confirm_or_route": s["n_with_confirm_or_route"],
                "on_window_pct": s["delta"]["on_window_pct"],
                "late_pct": s["delta"]["late_pct"],
                "confirmed": s["delta"]["confirmed"],
                "median_distance_atr_at_confirm":
                    s["delta"]["median_distance_atr_at_confirm"],
                "p90_distance_atr_at_confirm":
                    s["delta"]["p90_distance_atr_at_confirm"],
                "wins_gained_off_to_on": s["delta"]["wins_gained_off_to_on"],
                "wins_lost_off_to_on": s["delta"]["wins_lost_off_to_on"],
                "same_bar_wins_on_only": s["delta"]["same_bar_wins_on_only"],
            }
            for w, s in summaries.items()
        },
        "combined": _combined(summaries),
        "note": (
            "Windows were measured as separate processes; this file was "
            "composed from summary_<window>.json. Combined percentages are "
            "count-weighted totals, not averages of per-window percentages."
        ),
    }


def load_summaries() -> dict:
    """Read existing per-window summaries (for --compose-only)."""
    summaries = {}
    for window in WINDOW_LIST:
        path = OUT_ROOT / f"summary_{window}.json"
        if not path.exists():
            raise SystemExit(f"[wider] missing {path}; run that window first")
        summaries[window] = json.loads(path.read_text(encoding="utf-8"))
    return summaries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", default="both",
                        choices=("both",) + WINDOW_LIST)
    parser.add_argument("--compose-only", action="store_true",
                        help="Only rebuild summary_both_windows.json from the "
                             "existing per-window summaries (no re-run).")
    args = parser.parse_args(argv)

    if args.compose_only:
        summaries = load_summaries()
    else:
        windows = WINDOW_LIST if args.window == "both" else (args.window,)
        summaries = {window: run_window(window) for window in windows}

    if len(summaries) == 2:
        payload = compose_payload(summaries)
        (OUT_ROOT / "summary_both_windows.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({w: s["delta"] for w, s in summaries.items()}, indent=2),
          flush=True)
    print(f"[wider] wrote {OUT_ROOT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
