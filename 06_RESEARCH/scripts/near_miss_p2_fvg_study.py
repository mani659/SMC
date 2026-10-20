"""LEG 1 — near-miss counterfactual (P2 FVG / BOS). MEASUREMENT ONLY.

Authority: ``00_LOCKED/TECHNICAL_OWNER_PLAN_POST_PROBE.md`` (LEG 1).

What this script does
---------------------
1. Drives the **product** multi-TF composition over the frozen 6m window by
   importing ``phase3_structure_funnel.run`` unmodified (same window, same
   engine/adapter/runner, same C1 seam). Two logging-only wrappers capture
   what that composition discards:
     * ``MultiTFProductRuntime.run_batch`` — the execution (M5) bar index the
       batch was evaluated on (the honest "as-known-at" clock);
     * ``DetectionDriver.validate_window`` — every merged POI's
       ``ValidationResult`` plus its production ``DisplacementResult`` and,
       for BOS-failure rows, the sweep/prior-extreme needed to prove a
       *wick-only* break.
   Neither wrapper changes a decision, a threshold, an ordering, or an output.
2. De-duplicates validation *events* into unique candidates (the batch path
   re-validates the whole HTF prefix every hour, so raw event counts repeat
   the same zone many times).
3. Measures forward MFE/MAE from one pre-registered anchor per candidate,
   using the production Wilder ATR(14) on M5 as the R unit.

Pre-registered populations (see the report for the frozen wording):

* A — strict pass: the candidate ever passed the frozen pillars.
* B — P2 near-miss primary: never passed, P2 first failure is exactly
  "missing directional FVG", BOS present, magnitude >= 1.0 x ATR.
* C — P2 near-miss secondary: never passed, P2 first failure is missing BOS
  (body-close), magnitude >= 1.0 x ATR, and the break was **wick-only** in
  the production window.

Anchor: the M5 bar of the *first evaluation event that defines the
population* (A: first PASS; B: first qualifying P2-FVG fail; C: first
qualifying wick-only P2-BOS fail). Forward windows start on the NEXT M5 bar.

R: 1 x ATR(14) at the anchor (stop distance is not reconstructable for
never-routed candidates, so one uniform rule is used for every population).

Usage:
  python 06_RESEARCH/scripts/near_miss_p2_fvg_study.py --capture
  python 06_RESEARCH/scripts/near_miss_p2_fvg_study.py --analyze-only

Diagnostic only — NOT edge. No production module is edited.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import gzip
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "near_miss_p2_fvg"
EVENTS_PATH = OUT_DIR / "events.jsonl.gz"
SUMMARY_PATH = OUT_DIR / "summary.json"
CANDIDATES_PATH = OUT_DIR / "candidates.csv"
BANNER = "DIAGNOSTIC — NOT EDGE"

# Frozen 6m product window (FROZEN_FUNNEL_6M_POST_TP_REPORT.md).
DEFAULT_LOAD_FROM = datetime(2025, 5, 1, tzinfo=timezone.utc)
DEFAULT_EXEC_FROM = datetime(2025, 6, 1, tzinfo=timezone.utc)
DEFAULT_EXEC_TO = datetime(2025, 11, 30, 23, 59, tzinfo=timezone.utc)
LOAD_FROM = DEFAULT_LOAD_FROM
EXEC_FROM = DEFAULT_EXEC_FROM
EXEC_TO = DEFAULT_EXEC_TO

HORIZONS = (20, 50, 100)
PRIMARY_H = 100
MIN_N_FOR_LABEL = 30

# ---------------------------------------------------------------------- #
# Capture (logging-only seams)
# ---------------------------------------------------------------------- #

_EVENTS: list[dict] = []
_CLOCK: dict = {"bar": None, "as_of": None}


def _reset_capture() -> None:
    _EVENTS.clear()
    _CLOCK["bar"] = None
    _CLOCK["as_of"] = None


def _wick_only(
    candles, run, sweep_index: int, is_long: bool
) -> tuple[bool | None, float | None]:
    """True when price wicked beyond the prior swing but never closed beyond.

    Uses the production prior-extreme rule (``most_recent_swing``) at the
    same sweep index the displacement checker consumed.
    """
    from smc.poi.base_model import most_recent_swing

    prior = most_recent_swing(
        run.swings, is_high=not is_long, before_index=sweep_index
    )
    if prior is None:
        return None, None
    level = float(prior.level)
    body_beyond = False
    wick_beyond = False
    for c in candles[sweep_index + 1:]:
        if is_long:
            if c.close > level:
                body_beyond = True
            if c.high > level:
                wick_beyond = True
        else:
            if c.close < level:
                body_beyond = True
            if c.low < level:
                wick_beyond = True
        if body_beyond:
            break
    return (wick_beyond and not body_beyond), level


def install_capture() -> tuple:
    """Install both wrappers; return the originals for restoration."""
    from smc.orchestration.detection_driver import DetectionDriver
    from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime

    orig_run_batch = MultiTFProductRuntime.run_batch
    orig_validate_window = DetectionDriver.validate_window

    def run_batch(self, *args, **kwargs):
        _CLOCK["bar"] = kwargs.get("arm_bar")
        _CLOCK["as_of"] = kwargs.get("as_of")
        try:
            return orig_run_batch(self, *args, **kwargs)
        finally:
            _CLOCK["bar"] = None
            _CLOCK["as_of"] = None

    def validate_window(self, candles, **kwargs):
        passed, results, run, skipped, detected = orig_validate_window(
            self, candles, **kwargs
        )
        bar = _CLOCK["bar"]
        as_of = _CLOCK["as_of"]
        if bar is not None and results:
            disp_map = self.attribute_displacement(detected, run)
            sweep_by_disp = {}
            for idx, disp in run.displacements:
                sweep_by_disp.setdefault(id(disp), (idx, disp))
            for r in results:
                poi = r.poi
                ff = r.first_failure
                d = disp_map.get(poi.id)
                is_long = poi.zone.direction.value == "long"
                wick = None
                level = None
                sweep_index = None
                if (
                    ff is not None
                    and ff.pillar == 2
                    and "missing BOS" in (ff.detail or "")
                    and d is not None
                ):
                    hit = sweep_by_disp.get(id(d))
                    if hit is not None:
                        sweep_index, _ = hit
                        wick, level = _wick_only(
                            candles, run, sweep_index, is_long
                        )
                _EVENTS.append({
                    "arm_bar": int(bar),
                    "as_of": as_of.isoformat() if as_of else "",
                    "tf": self.timeframe.name,
                    "direction": poi.zone.direction.value,
                    "zone_top": float(poi.zone.top),
                    "zone_bottom": float(poi.zone.bottom),
                    "models": "|".join(sorted(m.name for m in poi.models)),
                    "passed": bool(r.passed),
                    "ff_pillar": ff.pillar if ff is not None else None,
                    "ff_status": ff.status.value if ff is not None else None,
                    "ff_detail": ff.detail if ff is not None else "",
                    "bos": getattr(d, "bos", None),
                    "fvg": getattr(d, "fvg", None),
                    "mag_atr": getattr(d, "magnitude_atr", None),
                    "hard_fail": getattr(d, "hard_fail", None),
                    "disp_atr": getattr(d, "atr", None),
                    "sweep_index": sweep_index,
                    "bos_level": level,
                    "wick_only": wick,
                })
        return passed, results, run, skipped, detected

    MultiTFProductRuntime.run_batch = run_batch
    DetectionDriver.validate_window = validate_window
    return orig_run_batch, orig_validate_window


def restore_capture(originals: tuple) -> None:
    from smc.orchestration.detection_driver import DetectionDriver
    from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime

    orig_run_batch, orig_validate_window = originals
    MultiTFProductRuntime.run_batch = orig_run_batch
    DetectionDriver.validate_window = orig_validate_window


def run_capture() -> dict:
    """Drive the frozen product composition and persist raw events."""
    import phase3_structure_funnel as funnel

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _reset_capture()
    originals = install_capture()
    args = argparse.Namespace(
        tag="leg1_near_miss_p2_fvg",
        out_root=str(
            OUT_DIR.relative_to(REPO_ROOT) / "_funnel_capture"
        ),
        load_from=LOAD_FROM.date().isoformat(),
        exec_from=EXEC_FROM.date().isoformat(),
        exec_to=EXEC_TO.date().isoformat(),
        cost_config=None,
        episode_store=None,
    )
    t0 = time.perf_counter()
    try:
        funnel_summary = funnel.run(args)
    finally:
        restore_capture(originals)
        # funnel.run restores its own validate_multi wrapper in its finally;
        # restore_capture above only touches our two seams.
    elapsed = round(time.perf_counter() - t0, 1)

    with gzip.open(EVENTS_PATH, "wt", encoding="utf-8") as fh:
        for ev in _EVENTS:
            fh.write(json.dumps(ev, separators=(",", ":")) + "\n")
    meta = {
        "events": len(_EVENTS),
        "runtime_seconds": elapsed,
        "funnel_summary": funnel_summary,
    }
    (OUT_DIR / "capture_meta.json").write_text(
        json.dumps(meta, indent=2, default=str), encoding="utf-8"
    )
    print(f"[leg1] captured {len(_EVENTS)} validation events in {elapsed}s",
          flush=True)
    return meta


def load_events() -> list[dict]:
    if not EVENTS_PATH.exists():
        raise SystemExit(
            f"capture missing: {EVENTS_PATH} — run with --capture first"
        )
    with gzip.open(EVENTS_PATH, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# ---------------------------------------------------------------------- #
# Analysis
# ---------------------------------------------------------------------- #

def load_m5_full():
    """Full M5 series (warm-up included) + Wilder ATR(14), numpy arrays."""
    import numpy as np

    from smc.config.timeframe import Timeframe
    from smc.data.parquet_loader import load_ohlcv_parquet
    from smc.data.resample import resample_multi
    from smc.utils.atr import atr_series

    path = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    if not path.exists():
        raise SystemExit(f"canonical dataset missing: {path}")
    m1 = load_ohlcv_parquet(path)
    m1 = [c for c in m1 if LOAD_FROM <= c.timestamp <= EXEC_TO + timedelta(days=1)]
    if not m1:
        raise SystemExit("no M1 bars in the frozen window")
    multi = resample_multi(m1, [Timeframe.M5])
    m5 = [c for c in multi[Timeframe.M5] if c.timestamp <= EXEC_TO]
    offset = bisect.bisect_left([c.timestamp for c in m5], EXEC_FROM)
    exec_bars = m5[offset:]
    if not exec_bars:
        raise SystemExit("no execution bars in the frozen window")
    highs = np.array([c.high for c in exec_bars], dtype=float)
    lows = np.array([c.low for c in exec_bars], dtype=float)
    closes = np.array([c.close for c in exec_bars], dtype=float)
    atr = atr_series(m5, 14)[offset:]
    return {
        "n": len(exec_bars),
        "start": exec_bars[0].timestamp,
        "end": exec_bars[-1].timestamp,
        "times": [c.timestamp for c in exec_bars],
        "highs": highs,
        "lows": lows,
        "closes": closes,
        "atr": atr,
        "offset": offset,
        "m5_count": len(m5),
    }


def path_metrics(series, anchor: int, direction: str, horizon: int) -> dict:
    """MFE/MAE from the anchor close, in price and in the anchor-ATR R."""
    n = series["n"]
    highs, lows = series["highs"], series["lows"]
    ref = float(series["closes"][anchor])
    atr = series["atr"][anchor]
    end = anchor + horizon
    complete = end < n
    last = min(end, n - 1)
    out = {"clipped": not complete}
    if last <= anchor or atr is None or atr <= 0:
        out.update(mfe_price=None, mae_price=None, mfe_r=None, mae_r=None)
        return out
    seg_h = highs[anchor + 1: last + 1]
    seg_l = lows[anchor + 1: last + 1]
    if direction == "long":
        fav = float(seg_h.max() - ref)
        adv = float(ref - seg_l.min())
    else:
        fav = float(ref - seg_l.min())
        adv = float(seg_h.max() - ref)
    fav = max(fav, 0.0)
    adv = max(adv, 0.0)
    out.update(
        mfe_price=fav,
        mae_price=adv,
        mfe_r=fav / float(atr),
        mae_r=adv / float(atr),
    )
    return out


def cluster_events(events: list[dict]) -> dict[tuple, list[dict]]:
    """Episode clusters using the product's own ZoneDedup overlap rule.

    ``ZoneDedup.seen`` (``smc.orchestration.multi_tf_runtime``) is the
    accepted chain's rule: same direction + overlapping span = one episode.
    Applied here per detection timeframe (the research funnel counts per
    TF), in chronological order, keeping the first zone of each episode.
    This is what stops the hourly re-validation of a growing HTF prefix
    from counting one structural setup as dozens of "candidates".
    """
    registry: dict[tuple, list[dict]] = defaultdict(list)
    clusters: dict[tuple, list[dict]] = defaultdict(list)
    for ev in sorted(events, key=lambda e: (e["arm_bar"], e["as_of"])):
        stream = (ev["tf"], ev["direction"])
        top, bottom = float(ev["zone_top"]), float(ev["zone_bottom"])
        cid = None
        for known in registry[stream]:
            if known["top"] >= bottom and top >= known["bottom"]:
                cid = known["cid"]
                break
        if cid is None:
            cid = (stream, len(registry[stream]))
            registry[stream].append({"cid": cid, "top": top, "bottom": bottom})
        clusters[cid].append(ev)
    return clusters


def cluster_sensitivity(events: list[dict]) -> dict:
    """Cross-TF variant of the family rule (direction + overlap, any TF).

    The product's ``ZoneDedup`` ignores the detection timeframe, so the
    same price episode detected on both H4 and H1 counts once there. The
    headline tables use the per-TF variant (matches the research funnel's
    per-TF counting); this function reports the other convention so the
    reader can see how much the pairing changes the census.
    """
    registry: dict[str, list[tuple]] = defaultdict(list)
    lookup: dict[tuple, tuple] = {}
    for ev in sorted(events, key=lambda e: (e["arm_bar"], e["as_of"])):
        direction = ev["direction"]
        top, bottom = float(ev["zone_top"]), float(ev["zone_bottom"])
        cid = None
        for known in registry[direction]:
            if known[1] >= bottom and top >= known[2]:
                cid = known[0]
                break
        if cid is None:
            cid = (direction, len(registry[direction]))
            registry[direction].append((cid, top, bottom))
        lookup[(ev["arm_bar"], ev["as_of"], ev["tf"], top, bottom)] = cid
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for ev in events:
        key = (ev["arm_bar"], ev["as_of"], ev["tf"],
               float(ev["zone_top"]), float(ev["zone_bottom"]))
        groups[lookup[key]].append(ev)
    from smc.config.locked_constants import DISPLACEMENT_MIN_ATR

    counts = {"A": 0, "B": 0, "C": 0}
    for rows in groups.values():
        rows.sort(key=lambda e: (e["arm_bar"], e["as_of"]))
        if any(e["passed"] for e in rows):
            counts["A"] += 1
            continue
        if any(
            e["ff_pillar"] == 2
            and e["ff_detail"] == "missing directional FVG"
            and e["bos"] is True
            and e["mag_atr"] is not None
            and e["mag_atr"] >= DISPLACEMENT_MIN_ATR
            for e in rows
        ):
            counts["B"] += 1
        if any(
            e["ff_pillar"] == 2
            and "missing BOS" in (e["ff_detail"] or "")
            and e["mag_atr"] is not None
            and e["mag_atr"] >= DISPLACEMENT_MIN_ATR
            and e["wick_only"] is True
            for e in rows
        ):
            counts["C"] += 1
    return {"n_clusters_cross_tf": len(groups), **counts}


def select_populations(events: list[dict]) -> tuple[dict, dict]:
    """Group events into episodes and apply the frozen definitions."""
    from smc.config.locked_constants import DISPLACEMENT_MIN_ATR

    groups = cluster_events(events)

    pop_a, pop_b, pop_c = {}, {}, {}
    for key, rows in groups.items():
        rows.sort(key=lambda e: e["arm_bar"])
        passes = [e for e in rows if e["passed"]]
        if passes:
            pop_a[key] = passes[0]
            continue
        near_b = [
            e for e in rows
            if e["ff_pillar"] == 2
            and e["ff_detail"] == "missing directional FVG"
            and e["bos"] is True
            and e["mag_atr"] is not None
            and e["mag_atr"] >= DISPLACEMENT_MIN_ATR
        ]
        if near_b:
            pop_b[key] = near_b[0]
        near_c = [
            e for e in rows
            if e["ff_pillar"] == 2
            and "missing BOS" in (e["ff_detail"] or "")
            and e["mag_atr"] is not None
            and e["mag_atr"] >= DISPLACEMENT_MIN_ATR
            and e["wick_only"] is True
        ]
        if near_c:
            pop_c[key] = near_c[0]
    stats = {
        "event_rows": len(events),
        "unique_candidates": len(groups),
        "pass_events": sum(1 for e in events if e["passed"]),
        "unique_a": len(pop_a),
        "unique_b": len(pop_b),
        "unique_c": len(pop_c),
        "overlap_a_b": len(set(pop_a) & set(pop_b)),
        "overlap_a_c": len(set(pop_a) & set(pop_c)),
        "cluster_rule": "ZoneDedup overlap (same direction + overlapping "
                        "span) per detection TF, chronological, first zone "
                        "of each episode retained",
        "events_per_candidate_p50": _median(
            [len(v) for v in groups.values()]
        ),
        "events_per_candidate_max": max((len(v) for v in groups.values()),
                                        default=0),
    }
    return {"A": pop_a, "B": pop_b, "C": pop_c}, stats


def _median(vals):
    s = sorted(v for v in vals if v is not None)
    if not s:
        return None
    m = len(s) // 2
    return (s[m - 1] + s[m]) / 2.0 if len(s) % 2 == 0 else float(s[m])


def _pct(vals, cond):
    s = [v for v in vals if v is not None]
    if not s:
        return None
    return 100.0 * sum(1 for v in s if cond(v)) / len(s)


def build_tables(pops: dict, series: dict) -> tuple[dict, list[dict]]:
    rows: list[dict] = []
    tables: dict = {}
    for pop_name in ("A", "B", "C"):
        pop = pops.get(pop_name, {})
        pop_rows: list[dict] = []
        for key, ev in pop.items():
            anchor = int(ev["arm_bar"])
            if anchor >= series["n"]:
                continue
            row = {
                "population": pop_name,
                "tf": ev["tf"],
                "direction": ev["direction"],
                "zone_top": round(ev["zone_top"], 2),
                "zone_bottom": round(ev["zone_bottom"], 2),
                "models": ev["models"],
                "anchor_bar": anchor,
                "anchor_ts": series["times"][anchor],
                "anchor_close": float(series["closes"][anchor]),
                "atr_at_anchor": series["atr"][anchor],
                "disp_bos": ev["bos"],
                "disp_fvg": ev["fvg"],
                "disp_mag_atr": ev["mag_atr"],
                "ff_detail": ev["ff_detail"],
                "arm_bar_of_event": ev["arm_bar"],
                "as_of": ev["as_of"],
            }
            for h in HORIZONS:
                m = path_metrics(series, anchor, ev["direction"], h)
                row[f"clipped_H{h}"] = m["clipped"]
                row[f"MFE_price_H{h}"] = m["mfe_price"]
                row[f"MAE_price_H{h}"] = m["mae_price"]
                row[f"MFE_R_H{h}"] = m["mfe_r"]
                row[f"MAE_R_H{h}"] = m["mae_r"]
            pop_rows.append(row)
        rows.extend(pop_rows)
        tables[pop_name] = {
            "n": len(pop_rows),
            "horizons": {
                f"H{h}": {
                    "n_complete": sum(1 for r in pop_rows
                                      if not r[f"clipped_H{h}"]),
                    "n_clipped": sum(1 for r in pop_rows
                                     if r[f"clipped_H{h}"]),
                    "median_MFE_price": _median(
                        [r[f"MFE_price_H{h}"] for r in pop_rows
                         if not r[f"clipped_H{h}"]]),
                    "median_MAE_price": _median(
                        [r[f"MAE_price_H{h}"] for r in pop_rows
                         if not r[f"clipped_H{h}"]]),
                    "median_MFE_R": _median(
                        [r[f"MFE_R_H{h}"] for r in pop_rows
                         if not r[f"clipped_H{h}"]]),
                    "median_MAE_R": _median(
                        [r[f"MAE_R_H{h}"] for r in pop_rows
                         if not r[f"clipped_H{h}"]]),
                    "p25_MFE_R": _quantile(
                        [r[f"MFE_R_H{h}"] for r in pop_rows
                         if not r[f"clipped_H{h}"]], 0.25),
                    "p75_MFE_R": _quantile(
                        [r[f"MFE_R_H{h}"] for r in pop_rows
                         if not r[f"clipped_H{h}"]], 0.75),
                    "pct_MFE_ge_1R": _pct(
                        [r[f"MFE_R_H{h}"] for r in pop_rows
                         if not r[f"clipped_H{h}"]],
                        lambda v: v >= 1.0),
                    "pct_MFE_ge_2R": _pct(
                        [r[f"MFE_R_H{h}"] for r in pop_rows
                         if not r[f"clipped_H{h}"]],
                        lambda v: v >= 2.0),
                }
                for h in HORIZONS
            },
        }
    return tables, rows


def _quantile(vals, q):
    s = sorted(v for v in vals if v is not None)
    if not s:
        return None
    if len(s) == 1:
        return float(s[0])
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return float(s[lo] * (1 - frac) + s[hi] * frac)


def _count_by(pops: dict, field: str) -> dict:
    out: dict = {}
    for pop_name, pop in pops.items():
        counts: Counter = Counter()
        for ev in pop.values():
            counts[ev[field]] += 1
        out[pop_name] = dict(sorted(counts.items()))
    return out


def interpret(tables: dict) -> tuple[str, str]:
    """Pre-registered label rule (see the report §5)."""
    a = tables.get("A", {})
    b = tables.get("B", {})
    n_b = b.get("n") or 0
    if n_b < MIN_N_FOR_LABEL or not a.get("n"):
        return (
            "INCONCLUSIVE",
            f"n_B={n_b} < {MIN_N_FOR_LABEL} (or n_A=0): the pre-registered "
            "minimum for a directional label is not met.",
        )

    def cell(pop, h, key):
        return ((pop.get("horizons") or {}).get(f"H{h}") or {}).get(key)

    verdicts = {}
    for h in (50, PRIMARY_H):
        med_a = cell(a, h, "median_MFE_R")
        med_b = cell(b, h, "median_MFE_R")
        p_a = cell(a, h, "pct_MFE_ge_1R")
        p_b = cell(b, h, "pct_MFE_ge_1R")
        if None in (med_a, med_b, p_a, p_b):
            verdicts[h] = "INCONCLUSIVE"
            continue
        if med_b >= 1.5 * med_a and p_b >= p_a + 10.0:
            verdicts[h] = "AMEND"
        elif med_b <= med_a and p_b <= p_a:
            verdicts[h] = "HOLD"
        else:
            verdicts[h] = "MIXED"

    if verdicts[50] == "AMEND" and verdicts[PRIMARY_H] == "AMEND":
        return (
            "AMEND_CANDIDATE",
            "At both H50 and H100 the FVG-absent near-miss population shows a "
            "higher median MFE in R (>=1.5x) and a >=10pp higher rate of "
            "reaching +1R than the strict-pass population, under the frozen "
            "definitions and the pre-registered rule.",
        )
    if verdicts[50] == "HOLD" and verdicts[PRIMARY_H] == "HOLD":
        return (
            "HOLD_P2_FVG",
            "At both H50 and H100 the FVG-absent near-miss population is not "
            "better than the strict-pass population (median MFE in R no "
            "higher, +1R rate no higher), so the gate is not shown to be "
            "cutting off a better class of paths on this window.",
        )
    return (
        "INCONCLUSIVE",
        f"The pre-registered contrast is mixed (H50={verdicts[50]}, "
        f"H{PRIMARY_H}={verdicts[PRIMARY_H]}): medians and +1R rates do not "
        "agree in direction at both horizons.",
    )


def analyze() -> dict:
    events = load_events()
    series = load_m5_full()
    pops, stats = select_populations(events)
    tables, rows = build_tables(pops, series)
    label, why = interpret(tables)

    meta_path = OUT_DIR / "capture_meta.json"
    capture_meta = (
        json.loads(meta_path.read_text(encoding="utf-8"))
        if meta_path.exists() else {}
    )
    funnel_summary = capture_meta.get("funnel_summary") or {}

    # Integrity: the frozen 6m baseline counts (FROZEN_FUNNEL_6M_POST_TP_REPORT).
    frozen = {
        "htf_batches": 2979,
        "merged_pois": 43004,
        "passed_validation": 2021,
        "armed": 30,
        "routes": 10,
        "fills": 3,
    }
    integrity = {
        "observed": {
            k: funnel_summary.get(k) for k in frozen
        },
        "frozen_baseline": frozen,
        "matches": {
            k: funnel_summary.get(k) == v for k, v in frozen.items()
        },
    }

    summary = {
        "banner": BANNER,
        "leg": "LEG 1 — near-miss counterfactual (P2 FVG / BOS)",
        "authority": "00_LOCKED/TECHNICAL_OWNER_PLAN_POST_PROBE.md",
        "window": {
            "load_from": LOAD_FROM.isoformat(),
            "exec_from": EXEC_FROM.isoformat(),
            "exec_to": EXEC_TO.isoformat(),
            "exec_tf": "M5",
            "m5_exec_bars": series["n"],
            "m5_full_bars": series["m5_count"],
            "source": "07_DATA/XAUUSD_M1.parquet",
        },
        "definitions": {
            "pipeline": "smc.validation.validation_pipeline.ValidationPipeline"
                        " (P1–P4 hard, P5 soft)",
            "pass": "ValidationResult.passed (decision PASS)",
            "bos_fvg_magnitude": (
                "smc.detection.displacement_checker.check_displacement: "
                "bos = first body close beyond the prior swing extreme; "
                "fvg = same-direction FVG formed between sweep and BOS; "
                "magnitude_atr = (sweep extreme -> BOS close) / pre-sweep "
                "Wilder ATR(14)"
            ),
            "near_miss_b": (
                "never passed; first_failure.pillar == 2; detail == "
                "'missing directional FVG'; bos is True; "
                "magnitude_atr >= DISPLACEMENT_MIN_ATR (1.0)"
            ),
            "near_miss_c": (
                "never passed; first_failure.pillar == 2; detail starts "
                "'missing BOS'; magnitude_atr >= 1.0; wick-only break "
                "(wick beyond the production prior swing, no body close)"
            ),
            "anchor": (
                "M5 bar of the first evaluation event defining the "
                "population (A first PASS, B/C first qualifying P2 fail); "
                "forward window starts anchor+1"
            ),
            "R": "1 x Wilder ATR(14) on M5 at the anchor (uniform; stop "
                 "distance is not reconstructable for never-routed rows)",
            "dedupe": (
                "episode cluster = product ZoneDedup rule (same direction + "
                "overlapping span), applied per detection TF in "
                "chronological order, first zone retained; the hourly batch "
                "re-validates the whole HTF prefix, so one setup appears "
                "dozens of times"
            ),
            "horizons": "20 / 50 / 100 M5 bars",
        },
        "capture": {
            "runtime_seconds": capture_meta.get("runtime_seconds"),
            "event_rows": stats["event_rows"],
            "pass_events": stats["pass_events"],
            "unique_candidates": stats["unique_candidates"],
            "events_per_candidate_p50": stats["events_per_candidate_p50"],
            "events_per_candidate_max": stats["events_per_candidate_max"],
        },
        "integrity_vs_frozen_6m": integrity,
        "populations": {
            "A_unique": stats["unique_a"],
            "B_unique": stats["unique_b"],
            "C_unique": stats["unique_c"],
            "A_and_B_overlap": stats["overlap_a_b"],
            "A_and_C_overlap": stats["overlap_a_c"],
            "by_tf": _count_by(pops, "tf"),
            "by_direction": _count_by(pops, "direction"),
            "cross_tf_cluster_sensitivity": cluster_sensitivity(events),
        },
        "tables": tables,
        "interpretation": {"label": label, "why": why},
        "guards": {
            "logic_changed": "NO",
            "locked_constants_touched": "NO",
            "threshold_search": "NO",
            "multi_symbol": "NO",
            "edge_or_expectancy_claim": "NO",
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, default=str),
                            encoding="utf-8")

    fields = [
        "population", "tf", "direction", "zone_top", "zone_bottom", "models",
        "anchor_bar", "anchor_ts", "anchor_close", "atr_at_anchor",
        "disp_bos", "disp_fvg", "disp_mag_atr", "ff_detail",
    ]
    for h in HORIZONS:
        fields += [f"clipped_H{h}", f"MFE_price_H{h}", f"MAE_price_H{h}",
                   f"MFE_R_H{h}", f"MAE_R_H{h}"]
    with CANDIDATES_PATH.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(json.dumps({
        "events": stats["event_rows"],
        "unique": stats["unique_candidates"],
        "A": stats["unique_a"], "B": stats["unique_b"],
        "C": stats["unique_c"],
        "label": label,
        "integrity": integrity["matches"],
    }, indent=2))
    return summary


def _parse_day(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def main() -> int:
    global LOAD_FROM, EXEC_FROM, EXEC_TO, OUT_DIR, EVENTS_PATH, SUMMARY_PATH, CANDIDATES_PATH
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", action="store_true",
                    help="drive the product composition and save events")
    ap.add_argument("--analyze-only", action="store_true",
                    help="re-read saved events and regenerate outputs")
    ap.add_argument("--load-from", default=None)
    ap.add_argument("--exec-from", default=None)
    ap.add_argument("--exec-to", default=None)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    if args.out_dir:
        OUT_DIR = REPO_ROOT / args.out_dir
        EVENTS_PATH = OUT_DIR / "events.jsonl.gz"
        SUMMARY_PATH = OUT_DIR / "summary.json"
        CANDIDATES_PATH = OUT_DIR / "candidates.csv"
    if args.load_from:
        LOAD_FROM = _parse_day(args.load_from)
    if args.exec_from:
        EXEC_FROM = _parse_day(args.exec_from)
    if args.exec_to:
        EXEC_TO = _parse_day(args.exec_to) + timedelta(days=1) - timedelta(minutes=1)
    if not args.capture and not args.analyze_only:
        ap.error("choose --capture or --analyze-only")
    if args.capture:
        run_capture()
    if args.analyze_only or args.capture:
        analyze()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
