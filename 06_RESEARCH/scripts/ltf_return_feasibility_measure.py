#!/usr/bin/env python3
"""LTF-RETURN FEASIBILITY MEASURE -- Mode A entry representation (read-only)

> BANNER: DIAGNOSTIC -- NOT EDGE / NOT AUTHORIZATION TO SHIP.

Authority chain (this task): 00_LOCKED/MODE_A_LTF_RETURN_ENTRY_DESIGN.md
(section 4 normative family + section 6 pre-registered kill criteria,
APPLIED VERBATIM) after Architect acceptance. Read-only research: no
product decision logic, no 04_SRC/smc edit, no locked_constants edit,
no live/paper/backtest wiring. LOGIC_CHANGED: NO. No post-hoc
parameter change, no widened window, no softened guard, no grid
search, no expectancy claim.

FROZEN METHOD (the accepted design, operationalized with the product's
own detectors via read-only imports; nothing forked):

* Populations (frozen, same as the accepted entry-representation
  study): P0 = the 10 product routes (benchmark rows only); P1 = the
  268 armed+coincident rows of `entry_representation/rows.csv`
  (reused row-for-row; true-frame bar grids already resolved there).
  One candidate per episode at its first proof.

* Proof event: the episode's first-coincidence proof already converted
  to the verified exec->grid frame by the entry-rep study
  (`proof_bar_grid`); direction agrees with the artifact thesis
  (inherent in the reused artifacts).

* PRIMARY structure = the nearest M5 displacement FVG of the proof
  leg, via the product's own detector `smc.detection.fvg_detector.
  detect_fvgs` (LOCKED_DECISIONS §3 semantics: 3-candle imbalance;
  bull zone = [high(c1), low(c3)]; bear zone = [high(c3), low(c1)] --
  reused, not reimplemented). Frozen selection: all three candles
  inside [proof - 48, proof] (a REUSE of the frozen H_PROOF = 48
  lookback -- no new constant); formation in the thesis direction
  (bullish FVG for LONG theses, bearish for SHORT); nearest-the-proof
  = latest third candle. Maturity/validity = the product detector's
  own rules AS-IS (the ratified design Q3: formed at the proof bar;
  no maturity constant added).

* LIMIT = the chosen structure's NEAR edge, accepted IFF strictly on
  the protected side of the true proof-bar close:
      LONG:  limit = FVG zone TOP    (= low(c3))  and limit < close(proof)
      SHORT: limit = FVG zone BOTTOM (= high(c3)) and limit > close(proof)
  If the primary fails the strict-side rule, the REPORT-ONLY alternate
  is evaluated on the SAME leg: the product's own R1 §3.1 origin-OB
  pairing (the candle immediately before the first FVG candle, zone =
  that candle's full range; near edge = OB high for LONG / OB low for
  SHORT) under the same strict rule. If neither qualifies ->
  `STRUCT_UNAVAILABLE` (counted, fail-closed; never inferred, never
  substituted, never an HTF-edge fallback, never an FVG+OB hybrid).
  The alternate's line-item view is reported side-by-side and NEVER
  enters a kill or a verdict.

* Stop / invalidation / lifetime (unchanged product rules, used
  descriptively only): stop reference = the structure's FAR edge
  (FR-2 raw reference; the measure never sizes or exits);
  invalidation semantics = engine §5 (labeled, not re-derived);
  retest window = [proof, proof + rest lifetime] -- the product's own
  rest lifetime, reused (no new constant); no touch in-window ->
  paper EXPIRED_NO_FILL (touch-only; SL/TP never invented).

* HTF-context-zone intersection: LABEL-ONLY column
  (`htf_zone_intersect`: limit inside the episode's zone bounds). Per
  the accepted ruling: never a filter, never a price input. The HTF
  proximal edge appears nowhere in the limit calculation -- the
  CONTROL comparison column carries the retired family's frozen
  geometry as the baseline only.

* Controls scored side-by-side as retired-family baselines only:
  CONTROL_proximal_edge = the frozen entry-rep study gaps.

* Determinism: pure re-analysis of saved artifacts + one series
  load; stable column order; dual runs byte-identical (no wall-clock
  in rows.csv / summary.json).

KILL CRITERIA (design §6, verbatim thresholds, first-fired order;
applied to the PRIMARY family result only):
  1) P1 DATA_GAP rate > 0.30         -> INCONCLUSIVE
  2) median gap_atr(P1) > 2.0        -> FAIL_STILL_FAR
  3) share(gap_atr <= 1.0) < 0.50    -> FAIL_NO_NEAR_MASS
  4) 0/3 control fills retained (evaluable) -> FAIL_BASELINE
  5) paper EXPIRED > 0.85 at n >= 20 -> FAIL_UNFILLABLE
  else -> PASS_FEASIBILITY (discussion unlock ONLY -- never a ship).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path
from statistics import median

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
SCRIPTS_DIR = REPO_ROOT / "06_RESEARCH" / "scripts"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

# Read-only imports of the frozen prior studies + the product's own
# detectors (never forked).
import reactive_admission_measure as ram     # noqa: E402 (grid, ATR, offset)
import near_miss_counterfactual as nm        # noqa: E402 (touch semantics)
import entry_representation_study as er      # noqa: E402 (frames, pct)

from smc.core.enums import Direction         # noqa: E402
from smc.detection.fvg_detector import detect_fvgs  # noqa: E402

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "ltf_return_feasibility"
REP_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "entry_representation"
BANNER = "DIAGNOSTIC -- NOT EDGE / NOT AUTHORIZATION TO SHIP"

# Frozen measure constants (measure-only; never locked_constants).
LOOKBACK_BARS = 48            # design: REUSE of frozen H_PROOF = 48
KILL_GAP_RATE = 0.30          # design §6 (1)
KILL_MEDIAN_FAR = 2.0         # design §6 (2)
KILL_NEAR_SHARE = 0.50        # design §6 (3)
KILL_FILLS_EVALUABLE = 3      # design §6 (4): exactly the 3 control fills
KILL_EXPIRED_RATE = 0.85      # design §6 (5)
KILL_EXPIRED_MIN_N = 20       # design §6 (5)
EXPECTED_P0 = 10
EXPECTED_P1 = 268

PRIMARY = "FVG_primary"
ALTERNATE = "OB_alternate"
CTRL = "CONTROL_proximal_edge"

ROW_FIELDS = [
    "episode_id", "population", "direction", "trigger", "matched_fill",
    "proof_bar_grid", "armed_bar_grid", "rest_bars",
    "struct_kind", "structure_status", "limit",
    "fvg_top", "fvg_bottom", "fvg_start_index",
    "ob_top", "ob_bottom",
    "gap_atr_proof", "gap_atr_arm", "flag_le_1", "flag_le_2",
    "htf_zone_intersect", "zone_low", "zone_high",
    "paper_fill_bar", "paper_outcome", "paper_note",
    "data_gap", "data_gap_reasons",
]

_DIRECTION_BY_NAME = {"long": Direction.LONG, "short": Direction.SHORT}


# --------------------------------------------------------------------------- #
# Pure structural helpers (unit-tested)
# --------------------------------------------------------------------------- #
def fvg_candidates(bars, direction: str, proof_grid: int,
                   lookback: int = LOOKBACK_BARS):
    """Direction-matched FVGs of the product's own detector whose
    3-candle set lies fully inside [proof-lookback, proof], returned
    nearest-the-proof first; each item is (fvg, absolute_start_index).
    Indexes into ``bars`` stay absolute -- never window-relative."""
    want = _DIRECTION_BY_NAME.get(direction)
    if want is None or proof_grid < 0 or proof_grid >= len(bars):
        return []
    window_start = max(0, int(proof_grid) - int(lookback))
    window = bars[window_start: int(proof_grid) + 1]
    found = []
    for fvg in detect_fvgs(window):
        if fvg.zone.direction is want:
            found.append((fvg, window_start + fvg.start_index))
    found.sort(key=lambda item: item[1], reverse=True)
    return found


def structure_for_row(bars, direction: str, proof_grid: int,
                      proof_close: float, lookback: int = LOOKBACK_BARS):
    """The design's selection rule, applied exactly (SINGULAR primary).

    §4b: THE nearest-the-proof FVG (latest third bar) is the primary;
    if ITS near edge passes the strict protected-side rule at the true
    proof close -> PRIMARY. If it fails, the REPORT-ONLY alternate OB
    (the product's R1 §3.1 candle-before-first-FVG pairing of that
    SAME formation) is evaluated under the same strict rule. If neither
    qualifies -> ("", "STRUCT_UNAVAILABLE", None, {}). Never the
    next-nearest FVG, never a hybrid, never an HTF-edge fallback.
    """
    cands = fvg_candidates(bars, direction, proof_grid, lookback)
    if not cands:
        return ("", "STRUCT_UNAVAILABLE", None, {})
    fvg, abs_start = cands[0]               # THE nearest-the-proof FVG
    near = float(fvg.zone.top if direction == "long" else fvg.zone.bottom)
    if (direction == "long" and near < proof_close) or \
            (direction == "short" and near > proof_close):
        return (PRIMARY, "STRUCT_FOUND_FVG", near, {
            "fvg_top": fvg.zone.top, "fvg_bottom": fvg.zone.bottom,
            "fvg_start_index": abs_start})
    ob_index = abs_start - 1
    if ob_index >= 0:
        ob = bars[ob_index]
        ob_near = float(ob.high if direction == "long" else ob.low)
        strict_ok = ((direction == "long" and ob_near < proof_close)
                     or (direction == "short" and ob_near > proof_close))
        if strict_ok:
            return (ALTERNATE, "STRUCT_FOUND_OB", ob_near, {
                "fvg_top": fvg.zone.top,
                "fvg_bottom": fvg.zone.bottom,
                "fvg_start_index": abs_start,
                "ob_top": ob.high, "ob_bottom": ob.low})
    return ("", "STRUCT_UNAVAILABLE", None, {})


def zone_intersects(limit, zone_low, zone_high) -> str:
    """LABEL-ONLY: limit inside the HTF context zone bounds? Never a
    filter. "" when the bounds are missing (fail-closed label)."""
    if limit is None or limit == "" or zone_low in (None, "") \
            or zone_high in (None, ""):
        return ""
    low, high, px = float(zone_low), float(zone_high), float(limit)
    return "True" if low <= px <= high else "False"


def paper_touch(bars_dict, direction, limit, proof: int, rest_bars):
    """Touch-only over the product rest lifetime (SL/TP never
    invented). Returns (outcome, fill_bar, note)."""
    if limit is None or direction is None:
        return "DATA_GAP", None, "limit/direction unavailable"
    if rest_bars is None:
        return "DATA_GAP", None, "missing lifetime"
    last = min(proof + int(rest_bars), len(bars_dict) - 1)
    if last < proof:
        return "DATA_GAP", None, "empty window"
    fill = nm.first_touch(direction, float(limit), bars_dict, proof, last)
    if fill is None:
        return "EXPIRED_NO_FILL", None, ""
    return "FILLED_NO_RESOLVE", fill, ""


def evaluate_row(base: dict, bars, bars_dict, atr_lookup, rest_bars) -> dict:
    """One family row (the PRIMARY family; the alternate is evaluated
    inside the selection rule and labeled -- never hybrid). Fail-closed
    everywhere."""
    row = {f: "" for f in ROW_FIELDS}
    gaps: list[str] = []

    direction = ram.parse_direction(base["direction"])
    proof = int(base["proof_bar_grid"])
    arm = int(base["armed_bar_grid"]) if base["armed_bar_grid"] != "" else None
    proof_close = float(bars[proof].close)
    atr_proof = atr_lookup(proof)
    atr_arm = atr_lookup(arm) if arm is not None else None
    zone_low = base["zone_low"] if base["zone_low"] != "" else None
    zone_high = base["zone_high"] if base["zone_high"] != "" else None

    if direction is None:
        gaps.append("missing_direction")
        status, struct_kind, limit, detail = "DATA_GAP", "", None, {}
    else:
        struct_kind, status, limit, detail = structure_for_row(
            bars, direction, proof, proof_close)
        if limit is None:
            gaps.append("struct_unavailable")
        else:
            row["htf_zone_intersect"] = zone_intersects(
                limit, zone_low, zone_high)
            if row["htf_zone_intersect"] == "":
                gaps.append("zone_bounds_missing_label")

    gap_proof = gap_arm = None
    if limit is not None:
        gap_price = abs(float(limit) - proof_close)
        if atr_proof is None:
            gaps.append("atr_unavailable")
        else:
            gap_proof = gap_price / float(atr_proof)
        if arm is not None and atr_arm is not None:
            gap_arm = (abs(float(limit) - float(bars[arm].close))
                       / float(atr_arm))

    outcome, fill_bar, note = paper_touch(bars_dict, direction, limit,
                                          proof, rest_bars)

    row.update({
        "episode_id": base["episode_id"],
        "population": base["population"],
        "direction": base["direction"],
        "trigger": base["trigger"],
        "matched_fill": base.get("matched_fill", ""),
        "proof_bar_grid": proof,
        "armed_bar_grid": base["armed_bar_grid"],
        "rest_bars": rest_bars if rest_bars is not None else "",
        "struct_kind": struct_kind,
        "structure_status": status,
        "limit": "" if limit is None else limit,
        "fvg_top": detail.get("fvg_top", ""),
        "fvg_bottom": detail.get("fvg_bottom", ""),
        "fvg_start_index": detail.get("fvg_start_index", ""),
        "ob_top": detail.get("ob_top", ""),
        "ob_bottom": detail.get("ob_bottom", ""),
        "gap_atr_proof": "" if gap_proof is None else gap_proof,
        "gap_atr_arm": "" if gap_arm is None else gap_arm,
        "flag_le_1": "True" if (gap_proof is not None
                                and gap_proof <= 1.0) else "False",
        "flag_le_2": "True" if (gap_proof is not None
                                and gap_proof <= 2.0) else "False",
        "zone_low": zone_low if zone_low is not None else "",
        "zone_high": zone_high if zone_high is not None else "",
        "data_gap": "True" if gaps else "False",
        "data_gap_reasons": ";".join(gaps),
        "paper_fill_bar": "" if fill_bar is None else fill_bar,
        "paper_outcome": outcome,
        "paper_note": note,
    })
    return row


# --------------------------------------------------------------------------- #
# Aggregation + the design's frozen first-fired kills
# --------------------------------------------------------------------------- #
def evaluate_rule_kills(stats: dict) -> dict:
    """Design §6, verbatim thresholds, first-fired order 1..5."""
    killed = []
    if stats["data_gap_rate_p1"] is not None \
            and stats["data_gap_rate_p1"] > KILL_GAP_RATE:
        killed.append("INCONCLUSIVE")
    if stats["median_gap_atr_p1"] is not None \
            and stats["median_gap_atr_p1"] > KILL_MEDIAN_FAR:
        killed.append("FAIL_STILL_FAR")
    if stats["share_le_1_p1"] is not None \
            and stats["share_le_1_p1"] < KILL_NEAR_SHARE:
        killed.append("FAIL_NO_NEAR_MASS")
    fills_ok = stats["n_fills_evaluable"] >= KILL_FILLS_EVALUABLE
    if fills_ok and stats["fill_overlap"] == 0:
        killed.append("FAIL_BASELINE")
    n_path = stats["n_paper_lifetime_path"]
    if n_path >= KILL_EXPIRED_MIN_N and stats["paper_expired_rate_path"] \
            is not None and stats["paper_expired_rate_path"] > KILL_EXPIRED_RATE:
        killed.append("FAIL_UNFILLABLE")
    if killed:
        return {"verdict": killed[0], "killed": killed, "gate": None}
    return {"verdict": "PASS_FEASIBILITY", "killed": [], "gate": None}


def _floats(rows, field):
    return [float(r[field]) for r in rows if r[field] != ""]


def _pct(n, d):
    return (n / d) if d else None


def aggregate_sub(label: str, rows_p1: list[dict], kind_filter=None) -> dict:
    """Aggregate a sub-view of the P1 family rows. The alternate
    REPORT-ONLY view re-grades only rows whose chosen kind is the
    alternate (never a verdict, never hybrid counts)."""
    subset = [r for r in rows_p1
              if kind_filter is None or r["struct_kind"] == kind_filter]
    vals = _floats(subset, "gap_atr_proof")
    return {
        "label": label,
        "n_p1_analyzed": len(rows_p1),
        "n_rows": len(subset),
        "median_gap_atr": median(vals) if vals else None,
        "p25_gap_atr": er.pct(vals, 0.25),
        "p75_gap_atr": er.pct(vals, 0.75),
        "share_le_1": _pct(sum(1 for r in subset
                               if r["flag_le_1"] == "True"), len(subset)),
        "share_le_2": _pct(sum(1 for r in subset
                               if r["flag_le_2"] == "True"), len(subset)),
        "htf_zone_intersect_mix": dict(Counter(
            r["htf_zone_intersect"] for r in subset
            if r["htf_zone_intersect"])),
    }


def aggregate_primary(all_rows: list[dict]) -> dict:
    """The verdict carrier: the PRIMARY family over the frozen
    populations (population split asserted before this call)."""
    rows_p1 = [r for r in all_rows if r["population"] == "1"]
    rows_p0 = [r for r in all_rows if r["population"] == "0"]
    vals = _floats(rows_p1, "gap_atr_proof")
    vals_arm = _floats(rows_p1, "gap_atr_arm")
    n_found = sum(1 for r in rows_p1
                  if r["structure_status"] in ("STRUCT_FOUND_FVG",
                                               "STRUCT_FOUND_OB"))
    n_unavail = sum(1 for r in rows_p1
                    if r["structure_status"] == "STRUCT_UNAVAILABLE")
    n_gap = sum(1 for r in rows_p1 if r["data_gap"] == "True")
    fills = [r for r in rows_p0 if r["matched_fill"] == "True"]
    fills_eval = [r for r in fills if r["paper_outcome"] in
                  ("EXPIRED_NO_FILL", "FILLED_NO_RESOLVE")]
    overlap = sum(1 for r in fills_eval
                  if r["paper_outcome"] == "FILLED_NO_RESOLVE")
    path_rows = [r for r in rows_p1 if r["paper_outcome"] in
                 ("EXPIRED_NO_FILL", "FILLED_NO_RESOLVE")]
    expired = sum(1 for r in path_rows
                  if r["paper_outcome"] == "EXPIRED_NO_FILL")
    stats = {
        "n_p1": len(rows_p1),
        "n_p0": len(rows_p0),
        "struct_found_p1": n_found,
        "struct_found_rate_p1": _pct(n_found, len(rows_p1)),
        "struct_unavailable_p1": n_unavail,
        "fvg_first_count": sum(1 for r in rows_p1
                               if r["struct_kind"] == PRIMARY),
        "ob_alternate_count": sum(1 for r in rows_p1
                                  if r["struct_kind"] == ALTERNATE),
        "data_gap_rows_p1": n_gap,
        "data_gap_rate_p1": _pct(n_gap, len(rows_p1)),
        "median_gap_atr_p1": median(vals) if vals else None,
        "p25_gap_atr_p1": er.pct(vals, 0.25),
        "p75_gap_atr_p1": er.pct(vals, 0.75),
        "median_gap_atr_p1_arm": median(vals_arm) if vals_arm else None,
        "share_le_1_p1": _pct(sum(1 for r in rows_p1
                                  if r["flag_le_1"] == "True"),
                              len(rows_p1)),
        "share_le_2_p1": _pct(sum(1 for r in rows_p1
                                  if r["flag_le_2"] == "True"),
                              len(rows_p1)),
        "htf_zone_intersect_mix": dict(Counter(
            r["htf_zone_intersect"] for r in rows_p1
            if r["htf_zone_intersect"])),
        "n_fills_evaluable": len(fills_eval),
        "fill_overlap": overlap,
        "fill_rows": [{k: r[k] for k in ("episode_id", "struct_kind",
                                         "structure_status", "limit",
                                         "gap_atr_proof",
                                         "htf_zone_intersect",
                                         "paper_outcome")}
                      for r in fills],
        "n_paper_lifetime_path": len(path_rows),
        "paper_expired_rate_path": _pct(expired, len(path_rows)),
        "paper_outcome_mix_p1": dict(Counter(
            r["paper_outcome"] for r in rows_p1 if r["paper_outcome"])),
        "terminal_reasons": dict(Counter(r["structure_status"]
                                         for r in rows_p1)),
        "rest_bars_missing_p1": sum(1 for r in rows_p1
                                    if r["rest_bars"] == ""),
    }
    stats["verdict_eval"] = evaluate_rule_kills(stats)
    stats["verdict"] = stats["verdict_eval"]["verdict"]
    return stats


# --------------------------------------------------------------------------- #
# Loaders / main
# --------------------------------------------------------------------------- #
def load_base() -> tuple[list[dict], dict]:
    rep_csv = REP_DIR / "rows.csv"
    reactive_csv = (REPO_ROOT / "06_RESEARCH" / "results"
                    / "reactive_admission_measure" / "rows.csv")
    cand_csv = (REPO_ROOT / "06_RESEARCH" / "results"
                / "near_miss_counterfactual" / "candidates.csv")
    for path in (rep_csv, reactive_csv, cand_csv):
        if not path.exists():
            raise SystemExit(f"required input missing: {path}")
    with rep_csv.open(encoding="utf-8", newline="") as f:
        base = list(csv.DictReader(f))
    with reactive_csv.open(encoding="utf-8", newline="") as f:
        reactive = list(csv.DictReader(f))
    with cand_csv.open(encoding="utf-8", newline="") as f:
        candidates = list(csv.DictReader(f))
    rest_by_episode = {r["episode_id"]: r.get("rest_bars")
                       for r in reactive if r.get("episode_id")}
    rest_by_route = {c["route_id"]: c.get("rest_bars") for c in candidates}
    return base, {"rest_by_episode": rest_by_episode,
                  "rest_by_route": rest_by_route}


def rest_bars_for(base_row: dict, joins: dict):
    if base_row["population"] == "0":
        val = joins["rest_by_route"].get(base_row["route_id"])
        return int(val) if val not in (None, "") else None
    val = joins["rest_by_episode"].get(base_row["episode_id"])
    return int(val) if val not in (None, "") else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", default=None,
                        help="override artifact directory (determinism runs)")
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir) if args.out_dir else OUT_DIR

    t0 = time.perf_counter()
    base_rows, joins = load_base()
    p0 = [r for r in base_rows if r["population"] == "0"]
    p1 = [r for r in base_rows if r["population"] == "1"]
    assert len(p0) == EXPECTED_P0, len(p0)
    assert len(p1) == EXPECTED_P1, len(p1)

    bars, offset = ram.load_series()
    assert offset == er.EXPECTED_WARMUP_OFFSET_SOURCE, offset
    atr_lookup = ram.atr_factory(bars)
    bars_dict = [{"timestamp": c.timestamp, "open": getattr(c, "open", None),
                  "high": c.high, "low": c.low, "close": c.close}
                 for c in bars]

    all_rows = []
    for base in p0 + p1:
        rest = rest_bars_for(base, joins)
        all_rows.append(evaluate_row(base, bars, bars_dict, atr_lookup,
                                     rest))
    assert len(all_rows) == EXPECTED_P0 + EXPECTED_P1, len(all_rows)

    stats_primary = aggregate_primary(all_rows)

    # Report-only alternate view (never a verdict): the rows whose
    # chosen structure was the alternate, graded alone side-by-side.
    rows_p1 = [r for r in all_rows if r["population"] == "1"]
    alt_view = aggregate_sub("OB_alternate_report_only", rows_p1,
                             ALTERNATE)
    ctrl_view = {
        "label": CTRL,
        "median_gap_atr": median(
            [float(r["gap_atr_proof"]) for r in p1
             if r.get("gap_atr_proof") not in (None, "")]),
        "share_le_1": er.share_le(
            [float(r["gap_atr_proof"]) for r in p1
             if r.get("gap_atr_proof") not in (None, "")], 1.0),
        "note": "retired proximal-edge family -- control evidence only",
    }

    meta = {
        "banner": BANNER,
        "logic_changed": "NO",
        "design": ("00_LOCKED/MODE_A_LTF_RETURN_ENTRY_DESIGN.md "
                   "(§4 + §6 verbatim)"),
        "frozen": {
            "primary": PRIMARY,
            "alternate": f"{ALTERNATE} (report-only, no hybrid)",
            "lookback_bars": LOOKBACK_BARS,
            "lookback_provenance": ("REUSE of frozen H_PROOF=48 "
                                    "(no new constant)"),
            "maturity_rule": ("product detector as-is (Q3 ratified; "
                              "no maturity constant added)"),
            "htf_zone": ("label-only column (intersect); never a "
                         "filter, never a price input"),
            "rest_window": ("product rest lifetime via frozen joins "
                            "(REUSE; no new constant)"),
            "strict_side": ("limit on the protected side of the true "
                            "proof close, else STRUCT_UNAVAILABLE "
                            "(fail-closed)"),
            "kill_thresholds": {"gap_rate": KILL_GAP_RATE,
                                "median_far": KILL_MEDIAN_FAR,
                                "near_share": KILL_NEAR_SHARE,
                                "expired_rate": KILL_EXPIRED_RATE,
                                "expired_min_n": KILL_EXPIRED_MIN_N,
                                "fills_evaluable": KILL_FILLS_EVALUABLE},
            "frame": "verified exec->grid (+6018) per the accepted study",
        },
        "stats": {"primary": stats_primary,
                  "alternate_report_only": alt_view,
                  "control_baseline": ctrl_view},
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_path = out_dir / "rows.csv"
    with rows_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(ROW_FIELDS)
        for row in all_rows:
            writer.writerow([row.get(k, "") if row.get(k) is not None
                             else "" for k in ROW_FIELDS])
    summary_path = out_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str, ensure_ascii=False)

    rows_sha = hashlib.sha256(rows_path.read_bytes()).hexdigest()
    sum_sha = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    s = stats_primary
    print(f"[ltf-return] primary: found={s['struct_found_p1']}/"
          f"{s['n_p1']} fvg={s['fvg_first_count']} "
          f"ob_alt={s['ob_alternate_count']} "
          f"unavail={s['struct_unavailable_p1']} "
          f"gap_rate={s['data_gap_rate_p1']:.3f} "
          f"median={s['median_gap_atr_p1']:.3f} "
          f"le1={s['share_le_1_p1']:.3f} "
          f"overlap={s['fill_overlap']}/{s['n_fills_evaluable']}",
          flush=True)
    print(f"[ltf-return] verdict={s['verdict']} "
          f"killed={s['verdict_eval']['killed']}", flush=True)
    print(f"[ltf-return] runtime={time.perf_counter() - t0:.1f}s", flush=True)
    print(f"[ltf-return] sha rows={rows_sha}", flush=True)
    print(f"[ltf-return] sha summary={sum_sha}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
