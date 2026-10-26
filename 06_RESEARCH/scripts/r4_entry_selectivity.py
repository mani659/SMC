"""R4 full entry-selectivity / Pillar-2 diagnosis (Track R, POST_V1_ACTIVE_TODO.md).

Offline diagnosis only. Tiles the canonical 5y M1 series into 14-day
own-windows (10-day prefix each) and runs the frozen DetectionDriver
batch path (detect -> merge -> validate, NO arming/routing/risk) per window,
capturing EVERY candidate's per-pillar outcome. Unit of analysis =
window-evaluation kill events (parallels Phase C's per-bar validation EVENTS;
adjacent-window recounts disclosed, not deduped).

Per Pillar-2 kill: structured displacement sub-reason (bos/fvg/
magnitude_atr/hard_fail via the driver's own attribution map), merged model
tags, zone, session/year of the decision bar, and counterfactual path quality
under two disclosed hypothetical entry/stop models measured forward from the
decision bar (detection never sees future bars; forward measurement uses the
stored series, exactly like R1 MFE windows).

Hypothetical models (both fixed at the decision bar W1, W1 close = ref):
  (a) zone_edge : entry = proximal zone edge, stop = distal edge (zone-width)
  (b) mid_buffer: entry = zone mid, stop = distal edge + 0.5xATR (ATR14@W1)
Horizons +5/+15/+60 bars: MFE/MAE in R; reachability = +1R/+2R before -1R
(SL-first tie-break, TP-credit from W1+1 — mirrors R2 conservatism).

Reads: 07_DATA/XAUUSD_M1.parquet via load_ohlcv_parquet; R3 trades_identity
(augmentation only); R1/R3 cited for admitted-side comparison (no recompute).
Writes: results/r4_entry_selectivity/{pillar2_kills.csv, window_census.csv,
comparison_groups_summary.csv, per_trade_enriched_identity.csv,
assumptions.json, r4_summary.json}.

Hard rules: no threshold changes, no TP implementation, no re-running the
5y strategy, no edge claims, no invented tags (model tags recorded from the
merged POI; kills never routed so trigger = 'never_routed').
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
R3_CSV = REPO_ROOT / "06_RESEARCH" / "results" / "r3_attribution" / "trades_identity.csv"
OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "r4_entry_selectivity"

OWN_DAYS, PREFIX_DAYS = 14, 10
HORIZONS = (5, 15, 60)


def main() -> dict:
    import numpy as np
    import pandas as pd
    from smc.config.timeframe import Timeframe
    from smc.data.parquet_loader import load_ohlcv_parquet
    from smc.orchestration.detection_driver import DetectionDriver

    print("[r4] loading canonical series ...", flush=True)
    candles = load_ohlcv_parquet(PARQUET)
    n = len(candles)
    highs = np.array([c.high for c in candles])
    lows = np.array([c.low for c in candles])
    closes = np.array([c.close for c in candles])
    pn = pd.read_parquet(PARQUET, columns=["timestamp"])["timestamp"]
    t0 = pn.iloc[0].to_pydatetime()
    if t0.tzinfo is None:
        t0 = t0.replace(tzinfo=timezone.utc)
    # Wilder ATR(14), diagnostic context only.
    tr = np.maximum(highs - lows, np.maximum(
        np.abs(highs - np.concatenate([[closes[0]], closes[:-1]])),
        np.abs(lows - np.concatenate([[closes[0]], closes[:-1]]))))
    atr = np.zeros(n)
    s = tr[:14].mean()
    atr[13] = s
    for i in range(14, n):
        s = (s * 13.0 + tr[i]) / 14.0
        atr[i] = s
    t_end = pn.iloc[-1].to_pydatetime()
    if t_end.tzinfo is None:
        t_end = t_end.replace(tzinfo=timezone.utc)
    print(f"[r4] {n} bars {t0.date()}..{t_end.date()}", flush=True)

    # Tile own-windows; prefix for swing/PDH context (clipped at series start).
    bounds, day = [], t0.replace(hour=0, minute=0, second=0, microsecond=0)
    while day < t_end:
        bounds.append(day)
        day += timedelta(days=OWN_DAYS)
    bounds.append(t_end)
    print(f"[r4] {len(bounds) - 1} own-windows", flush=True)

    drv = DetectionDriver(Timeframe.M1)
    kills: list[dict] = []
    census: list[dict] = []
    for w, (ws, we) in enumerate(zip(bounds[:-1], bounds[1:])):
        ps = max(t0, ws - timedelta(days=PREFIX_DAYS))
        a = int(np.searchsorted(pn.values, np.datetime64(ps.replace(tzinfo=None))))
        b = int(np.searchsorted(pn.values, np.datetime64(we.replace(tzinfo=None))))
        b = min(b, n)
        if b - a < 100:
            continue
        seg = candles[a:b]
        passed, results, run, skipped, detected = drv.validate_window(seg)
        disp = drv.attribute_displacement(detected, run)
        w1 = b - 1  # decision bar (absolute); arm-bar equivalent
        ff = Counter(r.first_failure.name if r.first_failure is not None
                     else "PASS" for r in results)
        census.append({"window": w, "own_start": str(ws.date()),
                       "own_end": str(we.date()), "feed_bars": b - a,
                       "raw_detected": len(detected),
                       "merged": len(results), "passed": len(passed),
                       **{f"ff_{k}": v for k, v in ff.items()},
                       "skipped_models": json.dumps(skipped)})
        for r in results:
            if r.first_failure is None or r.first_failure.pillar != 2:
                continue
            poi = r.poi
            d = disp.get(poi.id)
            top, bot = poi.zone.top, poi.zone.bottom
            ref = closes[w1]
            is_long = poi.zone.direction.value == "long"
            # proximal = nearer edge to W1 close; distal = far edge.
            prox = bot if abs(ref - bot) <= abs(ref - top) else top
            dist = top if prox == bot else bot
            row: dict = {
                "window": w, "own_start": str(ws.date()),
                "direction": poi.zone.direction.value,
                "zone_top": top, "zone_bottom": bot,
                "zone_timeframe": poi.zone.timeframe.value,
                "model_tags": "+".join(sorted(m.name for m in poi.models)) or "none",
                "pillar2_detail": r.first_failure.detail,
                "disp_bos": getattr(d, "bos", "UNAVAILABLE"),
                "disp_fvg": getattr(d, "fvg", "UNAVAILABLE"),
                "disp_magnitude_atr": getattr(d, "magnitude_atr", "UNAVAILABLE"),
                "disp_hard_fail": getattr(d, "hard_fail", "UNAVAILABLE"),
                "disp_preferred": getattr(d, "is_preferred", "UNAVAILABLE"),
                "w1_close": ref, "atr14_w1": atr[w1],
                "trigger": "never_routed",
            }
            for mname, entry, stop in (
                ("edge", prox, dist),
                ("midbuf", (top + bot) / 2.0,
                 dist + (0.5 * atr[w1] if is_long else -0.5 * atr[w1])),
            ):
                risk = abs(entry - stop)
                if risk <= 0:
                    continue
                sgn = 1.0 if is_long else -1.0
                for h in HORIZONS:
                    hb = min(w1 + h, n - 1)
                    seg_h, seg_l = highs[w1 + 1:hb + 1], lows[w1 + 1:hb + 1]
                    if len(seg_h) == 0:
                        row[f"{mname}_H{h}_clipped"] = 1
                        continue
                    fav = (seg_h - entry) * sgn
                    adv = (entry - seg_l) * sgn
                    row[f"{mname}_H{h}_MFE_R"] = float(fav.max() / risk)
                    row[f"{mname}_H{h}_MAE_R"] = float(max(adv.max(), 0.0) / risk)
                    row[f"{mname}_H{h}_clipped"] = int(hb < w1 + h)
                # Reachability over +60 (clipped): +1R/+2R before -1R, SL-first.
                hb = min(w1 + 60, n - 1)
                reached = {"1R": 0, "2R": 0}
                alive = True
                for bb in range(w1 + 1, hb + 1):
                    sl_hit = (lows[bb] <= stop) if is_long else (highs[bb] >= stop)
                    if sl_hit:
                        alive = False
                        break
                    for lvl in ("1R", "2R"):
                        tgt = entry + sgn * float(lvl[0]) * risk
                        hit = (highs[bb] >= tgt) if is_long else (lows[bb] <= tgt)
                        if hit:
                            reached[lvl] = 1
                row[f"{mname}_reach_1R"] = reached["1R"]
                row[f"{mname}_reach_2R"] = reached["2R"]
                row[f"{mname}_reach_window"] = hb - w1
            kills.append(row)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "pillar2_kills.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(kills[0].keys()))
        w.writeheader()
        w.writerows(kills)
    with open(OUT_DIR / "window_census.csv", "w", newline="") as f:
        keys = sorted({k for c in census for k in c})
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(census)

    # Enriched admitted-book identity: R3 + trade-book ATR tercile + flags.
    r3 = list(csv.DictReader(open(R3_CSV, newline="")))
    av = sorted(float(r["atr14_at_entry"]) for r in r3
                if r["atr14_at_entry"] not in ("", None))
    q1, q2 = av[len(av) // 3], av[2 * len(av) // 3]
    for r in r3:
        a = float(r["atr14_at_entry"]) if r["atr14_at_entry"] not in ("", None) else -1
        r["atr_trade_tercile"] = ("low" if a < q1 else "mid" if a < q2 else "high")
        r["pillar_path"] = "unrecoverable_not_persisted"
    with open(OUT_DIR / "per_trade_enriched_identity.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(r3[0].keys()))
        w.writeheader()
        w.writerows(r3)

    def med(vals):
        s = sorted(v for v in vals if v is not None)
        if not s:
            return None
        m = len(s) // 2
        return (s[m - 1] + s[m]) / 2.0 if len(s) % 2 == 0 else s[m]

    def reach(rows, m, lvl):
        return sum(r[f"{m}_reach_{lvl}"] for r in rows) / len(rows) * 100.0 if rows else 0.0

    comp = {
        "kills_n": len(kills),
        "windows_n": len(census),
        "census_totals": {k: sum(c.get(k, 0) for c in census)
                          for k in sorted({k for c in census for k in c}
                                          - {"window", "own_start", "own_end",
                                             "skipped_models"})},
        "kill_models": dict(Counter(r["model_tags"] for r in kills)),
        "kill_subreasons": {
            "hard_fail": sum(1 for r in kills if r["disp_hard_fail"] is True),
            "evaluated_fail": sum(1 for r in kills
                                  if r["disp_hard_fail"] is False),
            "unavailable": sum(1 for r in kills
                               if r["disp_hard_fail"] == "UNAVAILABLE"),
        },
        "kill_magnitude_atr_median": med([r["disp_magnitude_atr"] for r in kills
                                          if isinstance(r["disp_magnitude_atr"],
                                                        (int, float))]),
        "counterfactual": {
            m: {f"H{h}_med_MFE_R": med([r[f"{m}_H{h}_MFE_R"] for r in kills
                                        if f"{m}_H{h}_MFE_R" in r]),
                f"H{h}_med_MAE_R": med([r[f"{m}_H{h}_MAE_R"] for r in kills
                                        if f"{m}_H{h}_MAE_R" in r]),
                "reach_1R_pct": reach(kills, m, "1R"),
                "reach_2R_pct": reach(kills, m, "2R")}
            for m in ("edge", "midbuf")
        },
        "atr_trade_terciles": {"q1": q1, "q2": q2},
    }
    with open(OUT_DIR / "comparison_groups_summary.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["kills_n", len(kills)])
        w.writerow(["windows_n", len(census)])
        for m in ("edge", "midbuf"):
            for k, v in comp["counterfactual"][m].items():
                w.writerow([f"{m}_{k}", v])
    with open(OUT_DIR / "assumptions.json", "w") as f:
        json.dump({
            "unit": "window-evaluation kill events (batch validate_window per 14d own-window + 10d prefix; adjacent recounts disclosed, NOT deduped; parallels Phase C per-bar validation EVENTS, not unique POIs)",
            "detection_blind_to_future": True,
            "forward_measurement_uses_stored_series": True,
            "anchor": "W1 = last feed bar of window (arm-bar equivalent); horizons +5/+15/+60 clipped at series end",
            "hypothetical_models": {
                "edge": "entry=proximal zone edge (assumed filled, no touch required), stop=distal edge",
                "midbuf": "entry=zone mid, stop=distal edge + 0.5xATR14@W1"},
            "reachability": "+1R/+2R before -1R, SL-first tie-break, TP-credit from W1+1 (mirrors R2 conservatism)",
            "atr": "Wilder RMA-14 TR over canonical series (diagnostic context, not a rule)",
            "displacement_attribution": "driver.attribute_displacement (most-recent same-direction sweep in feed)",
            "batch_vs_rolling": "batch kills are a SUPERSET of rolling kills (single attribution point); poor counterfactual quality in superset = strong correctly-killed signal; good quality = weak overfilter signal",
            "no_threshold_changes": True, "no_strategy_code_changes": True,
        }, f, indent=2)
    with open(OUT_DIR / "r4_summary.json", "w") as f:
        json.dump(comp, f, indent=2, default=str)
    print(f"[r4] kills={len(kills)} windows={len(census)}", flush=True)
    return comp


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
