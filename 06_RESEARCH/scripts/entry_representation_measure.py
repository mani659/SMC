#!/usr/bin/env python3
"""OFFLINE ENTRY-REPRESENTATION MEASURE -- counterfactual limits only.

> BANNER: DIAGNOSTIC -- NOT EDGE / NOT AUTHORIZATION TO SHIP.

Authority chain (this task): 00_LOCKED/ENTRY_REPRESENTATION_DESIGN.md
(ACCEPTED 2026-10-14; section 4 rules and section 5 kill criteria
applied VERBATIM) executed as a read-only counterfactual limit measure
on the frozen 6m populations. No product limit / Trigger F / FR-3.1 /
routing change; no `locked_constants` edit; the reactive-admission
measure R1-R6 stays CLOSED (its artifacts only provide join keys).
Recompute counterfactual entry limits under
  CONTROL_proximal_edge  (FR-3.1 status quo, scored for comparison),
  RL-1 pullback_shelf    (PRIMARY under test),
  RL-2 retrace_mid       (parameter-free alternative),
  RL-3 edge_plus_wait    (placement-only; limit formula = CONTROL,
                          no stacking)
and score each rule against the design's pre-registered kill criteria.
PASS_MEASURE unlocks an Architect implement discussion only -- it is
NEVER a ship decision. LOGIC_CHANGED: NO.

FROZEN ARCHITECT DEFAULTS (fixed before the run):
  * Primary verdict on RL-1; RL-2 and RL-3 reported side-by-side.
  * No rule stacking (each rule scored alone).
  * TP/SL construction unchanged -- limit only.
  * Verified exec->grid frame (+ warm-up offset) exactly as in the
    entry-representation study (imported, never forked).
  * k = 1.0 for RL-1: a MEASURE constant, not a locked constant.
  * No grid search over k or the 50% transform; single frozen
    definitions only.

FROZEN METHOD (identical to the design section 5, plus operational
pins this measure itself freezes now, BEFORE the run):

* Populations: P0 = the 10 frozen product routes; P1 = the 268
  armed+coincident rows; P2 = the prior R4-fail stratum (report only,
  flagged on rows, never a verdict input). Base rows reuse the frozen
  `entry_representation/rows.csv` (true-frame bar grids already
  resolved there) joined with the reactive artifacts for
  `rest_bars` (and the near-miss candidates for P0 lifetimes).

* Per row x rule {CONTROL, RL-1, RL-2, RL-3}:
  1) counterfactual limit per the design's formal definition; missing
     inputs -> DATA_GAP (limit undefined, fail-closed, never invented);
  2) gap_atr vs the TRUE proof-bar close (primary; same reference and
     frame as the entry-representation study) and vs the arm-bar close
     (secondary);
  3) flags: gap <= 1.0 and <= 2.0 (reporting bands ONLY; <= 2 never
     gates any rule, kill or verdict);
  4) RL-3 only: deferred presentation = first bar in [proof,
     proof + rest_bars] where the design's NAMED rule
     `market_reentered_zone` evaluates true AND
     |limit - close(bar)| <= 1.0 x ATR(bar) (the closed measure's own
     proximity constant, reused verbatim). The proof bar itself is
     included (a market already near at proof presents immediately --
     not a deferral failure). No such bar -> presentation fails within
     the lifetime.
     Operational pin (frozen): rule guards are evaluated at the true
     proof bar for BOTH populations (P0 routes use their first-
     presentation bar as the proof reference -- disclosed in the
     entry-representation study).

* RL-1 guard rails (design 4.1, exactly): protected side
  (LONG limit < proof-bar close; SHORT > close), no zone tunneling
  (LONG limit >= zone_low; SHORT <= zone_high), no proof-extreme
  overshoot (LONG limit >= proof-bar low; SHORT <= proof-bar high).
  Any guard failure -> keep the CONTROL limit and COUNT the fallback
  (never silently dropped, never widened).

* RL-2 leg span (design 4.2, operational pin frozen here): the
  displacement leg = the span [last touch of the proximal edge,
  proof bar], searching backward from the proof bar within the frozen
  LEG_SPAN_LOOKBACK = 96 M5 bars; a span-start bar must contain the
  edge in its [low, high] range. No such bar -> DATA_GAP for RL-2 on
  that row (the design's "zone's own referenced formation window" is
  operationalized this way and cannot be invented when the edge was
  never touched in the lookback).

* Paper path (disclosed secondary): P0 route rows have recorded
  SL/TP -- the rule's limit + the recorded SL/TP simulate through the
  frozen near-miss route semantics (TP_HIT / SL_HIT / EXPIRED_NO_FILL /
  OPEN_UNRESOLVED; BE stop not modeled, as disclosed in the near-miss
  note). P1 rows have NO SL/TP (never invented) -- touch-only
  semantics: FILLED_NO_RESOLVE when the rule's limit is touched within
  its lifetime window, else EXPIRED_NO_FILL. Lifetimes: CONTROL/RL-1/
  RL-2 touch over [proof, proof + rest_bars]; RL-3 over its OWN
  presentation span [present_bar, present_bar + remaining lifetime],
  remaining = rest_bars - bars_to_present.

* Kill criteria (design section 5, first-fired order, per rule):
  1) median gap_atr(P1) >= 6.0        -> FAIL_STILL_FAR
  2) share(gap_atr <= 1.0) < 0.10     -> FAIL_NO_NEAR_MASS
  3) 0 fill overlap with the 3 control fills, when those rows are
     evaluable under the rule's paper path (evaluable = a completed
     touch/simulation without DATA_GAP) -> FAIL_BASELINE
  4) paper EXPIRED_NO_FILL > 0.90 among rows with a defined lifetime
     path and n >= 20                  -> FAIL_UNFILLABLE
  5) rule DATA_GAP rate on P1 > 0.20   -> INCONCLUSIVE
  else -> PASS_MEASURE (discussion unlock only).

* Determinism: pure re-analysis of saved artifacts + one series load;
  stable column order; dual runs byte-identical (no wall-clock in
  rows.csv / summary.json).
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

# Import (never fork) the frozen helpers of prior read-only studies.
import reactive_admission_measure as ram   # noqa: E402 (grid + offset)
import near_miss_counterfactual as nm      # noqa: E402 (paper semantics)
import entry_representation_study as er    # noqa: E402 (frames, edges)

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "entry_representation_measure"
REP_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "entry_representation"
BANNER = "DIAGNOSTIC -- NOT EDGE / NOT AUTHORIZATION TO SHIP"

# Frozen architect defaults / measure constants (NEVER locked_constants).
K_SHELF = 1.0                 # RL-1 (design 4.1, frozen now)
RETRACE_FRACTION = 0.5        # RL-2 (design 4.2, fixed transform)
LEG_SPAN_LOOKBACK = 96        # RL-2 operational pin (frozen here)
PRESENT_PROX_ATR = 1.0        # RL-3 proximity guard (reused constant)
KILL_MEDIAN_FAR = 6.0         # design section 5, frozen
KILL_NEAR_SHARE = 0.10        # design section 5
KILL_EXPIRED_RATE = 0.90      # design section 5
KILL_EXPIRED_MIN_N = 20       # design section 5
KILL_GAP_RATE = 0.20          # design section 5
EXPECTED_P0 = 10
EXPECTED_P1 = 268
EXPECTED_CONTROLS_FILL = 3

RULE_CONTROL = "CONTROL_proximal_edge"
RULE_RL1 = "RL1_pullback_shelf"
RULE_RL2 = "RL2_retrace_mid"
RULE_RL3 = "RL3_edge_plus_wait"
RULES = (RULE_CONTROL, RULE_RL1, RULE_RL2, RULE_RL3)

ROW_FIELDS = [
    "episode_id", "population", "rule", "direction", "trigger",
    "matched_fill", "rest_bars", "fallback", "fallback_reason", "limit",
    "gap_atr_proof", "gap_atr_arm", "flag_le_1", "flag_le_2",
    "present_bar", "bars_to_present",
    "paper_first_bar", "paper_fill_bar", "paper_outcome", "paper_note",
    "data_gap", "data_gap_reasons",
]


# --------------------------------------------------------------------------- #
# Pure rule functions (unit-tested)
# --------------------------------------------------------------------------- #
def rl1_limit(direction: str, proof_close: float, atr: float,
              zone_low, zone_high, proof_high, proof_low,
              k: float = K_SHELF):
    """RL-1 shelf + design guard rails; (limit, fallback_reason).

    Reason is None when the shelf stands; otherwise the FIRST failed
    guard in design order 1-3 names the fallback, and the caller keeps
    the CONTROL limit (fail-closed fallback, counted, never widened).
    """
    if direction == "long":
        limit = proof_close - k * atr
        if not limit < proof_close:
            return limit, "guard1_protected_side"
        if zone_low is not None and limit < float(zone_low):
            return limit, "guard2_zone_tunneling"
        if proof_low is not None and limit < float(proof_low):
            return limit, "guard3_proof_extreme"
        return limit, None
    if direction == "short":
        limit = proof_close + k * atr
        if not limit > proof_close:
            return limit, "guard1_protected_side"
        if zone_high is not None and limit > float(zone_high):
            return limit, "guard2_zone_tunneling"
        if proof_high is not None and limit > float(proof_high):
            return limit, "guard3_proof_extreme"
        return limit, None
    return None, "missing_direction"


def rl2_limit(direction: str, proximal_edge: float, leg_extreme: float,
              fraction: float = RETRACE_FRACTION):
    """RL-2 midpoint of the measured displacement leg (parameter-free)."""
    if direction == "long":
        return (proximal_edge + max(proximal_edge, leg_extreme)) * fraction
    if direction == "short":
        return (proximal_edge + min(proximal_edge, leg_extreme)) * fraction
    return None


def leg_extreme(bars, direction: str, proximal_edge: float,
                proof_grid: int, lookback: int = LEG_SPAN_LOOKBACK):
    """Measured displacement extreme over [last edge touch, proof bar].

    Span start = the LAST bar within ``lookback`` of the proof bar
    whose [low, high] contains the proximal edge (frozen operational
    pin of design 4.2). Returns (extreme, span_start) or (None, None)
    -> caller marks DATA_GAP (never invent the span).
    """
    if direction not in ("long", "short") or proximal_edge is None:
        return None, None
    start_floor = max(0, int(proof_grid) - int(lookback))
    span_start = None
    for i in range(int(proof_grid), start_floor - 1, -1):
        bar = bars[i]
        if float(bar.low) <= float(proximal_edge) <= float(bar.high):
            span_start = i
            break
    if span_start is None:
        return None, None
    if direction == "long":
        return max(float(bars[i].high) for i in range(span_start,
                                                      int(proof_grid) + 1)), span_start
    return min(float(bars[i].low) for i in range(span_start,
                                                 int(proof_grid) + 1)), span_start


def rl3_presentation(bars, direction, limit, zone_low, zone_high,
                     proof_grid: int, rest_bars: int, atr_at,
                     prox_mult: float = PRESENT_PROX_ATR):
    """First bar in [proof, proof+rest] presenting the CONTROL limit.

    Conditions (design 4.3, verbatim): the thesis zone band is
    re-entered (the NAMED product rule `market_reentered_zone`, band
    path on close OR limit touch, over the row's own zone bounds) AND
    the limit is within ``prox_mult`` x ATR of the bar's close (the
    closed measure's proximity constant, reused not re-tuned). The
    proof bar is included (a market already near at proof presents
    immediately). Returns (present_bar, kind) or (None, None).
    """
    if direction not in ("long", "short") or limit is None:
        return None, None
    if zone_low in (None, "") or zone_high in (None, ""):
        return None, None
    last = min(int(proof_grid) + int(rest_bars), len(bars) - 1)
    enum_dir = ram.to_direction_enum(direction)
    for i in range(int(proof_grid), last + 1):
        bar = bars[i]
        atr = atr_at(i)
        if atr is None:
            continue
        reentry = bool(ram.market_reentered_zone(
            enum_dir, float(zone_low), float(zone_high), float(limit),
            float(bar.close), atr, bar=bar))
        near = abs(float(limit) - float(bar.close)) <= prox_mult * float(atr)
        if reentry and near:
            return i, ("immediate" if i == int(proof_grid) else "deferred")
    return None, None


def evaluate_rule_kills(stats: dict) -> dict:
    """Design section 5, first-fired order 1..5, applied per rule."""
    killed = []
    if stats["median_gap_atr_p1"] >= KILL_MEDIAN_FAR:
        killed.append("FAIL_STILL_FAR")
    if stats["share_le_1_p1"] < KILL_NEAR_SHARE:
        killed.append("FAIL_NO_NEAR_MASS")
    fills_ok = stats["n_fills_evaluable"] >= EXPECTED_CONTROLS_FILL
    if fills_ok and stats["fill_overlap"] == 0:
        killed.append("FAIL_BASELINE")
    n_path = stats["n_paper_lifetime_path"]
    if n_path >= KILL_EXPIRED_MIN_N and stats["paper_expired_rate_path"] \
            is not None and stats["paper_expired_rate_path"] > KILL_EXPIRED_RATE:
        killed.append("FAIL_UNFILLABLE")
    if stats["data_gap_rate_p1"] is not None \
            and stats["data_gap_rate_p1"] > KILL_GAP_RATE:
        killed.append("INCONCLUSIVE")
    if killed:
        # design: first fired rule in order 1-5 names the verdict
        return {"verdict": killed[0], "killed": killed, "gate": None}
    return {"verdict": "PASS_MEASURE", "killed": [], "gate": None}


# --------------------------------------------------------------------------- #
# Base rows (reuse the frozen entry-representation study rows)
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
        return int(joins["rest_by_route"][base_row["route_id"]]) \
            if joins["rest_by_route"].get(base_row["route_id"]) not in (None, "") \
            else None
    val = joins["rest_by_episode"].get(base_row["episode_id"])
    return int(val) if val not in (None, "") else None


# --------------------------------------------------------------------------- #
# Row x rule evaluation
# --------------------------------------------------------------------------- #
def evaluate_row_rule(base: dict, bars, bars_dict, atr_lookup, rule: str,
                      rest_bars, joined: dict) -> dict:
    """One (episode, rule) row; fail-closed everywhere."""
    row = {f: "" for f in ROW_FIELDS}
    gaps: list[str] = []
    direction = ram.parse_direction(base["direction"])
    proof = int(base["proof_bar_grid"])
    arm = int(base["armed_bar_grid"]) if base["armed_bar_grid"] not in ("", None) else None
    zone_low = base["zone_low"] if base["zone_low"] not in ("", None) else None
    zone_high = base["zone_high"] if base["zone_high"] not in ("", None) else None
    control_limit = base["limit"] if base["limit"] not in ("", None) else None
    proximal_edge = er.proximal_edge_for(direction, zone_low, zone_high)
    if proximal_edge is None and direction is not None:
        gaps.append("missing_edge")

    proof_close = float(bars[proof].close)
    proof_high = float(bars[proof].high)
    proof_low = float(bars[proof].low)
    atr_proof = atr_lookup(proof)
    atr_arm = atr_lookup(arm) if arm is not None else None

    limit = None
    fallback = ""
    fallback_reason = ""
    present_bar = ""
    bars_to_present = ""

    if rule == RULE_CONTROL:
        limit = control_limit
        if limit is None:
            gaps.append("missing_control_limit")
    elif rule == RULE_RL1:
        if direction is None:
            gaps.append("missing_direction")
        elif atr_proof is None:
            gaps.append("atr_unavailable")
        else:
            shelf, reason = rl1_limit(direction, proof_close, atr_proof,
                                      zone_low, zone_high, proof_high,
                                      proof_low, K_SHELF)
            if shelf is None or reason == "missing_direction":
                gaps.append("rl1_undefined")
            elif reason is not None:
                fallback = "True"
                fallback_reason = reason
                limit = control_limit  # fail-closed fallback, disclosed
            else:
                limit = shelf
    elif rule == RULE_RL2:
        if direction is None or proximal_edge is None:
            gaps.append("rl2_missing_edge_or_direction")
        else:
            extreme, span_start = leg_extreme(bars, direction,
                                              float(proximal_edge), proof)
            if extreme is None:
                gaps.append("rl2_no_edge_touch_in_lookback")
            else:
                limit = rl2_limit(direction, float(proximal_edge), extreme)
    elif rule == RULE_RL3:
        limit = control_limit  # formula = CONTROL, verbatim
        if control_limit is None:
            gaps.append("missing_control_limit")
        elif rest_bars is None:
            gaps.append("missing_rest_bars")
        else:
            present, _kind = rl3_presentation(
                bars, direction, float(control_limit), zone_low, zone_high,
                proof, rest_bars, atr_lookup)
            if present is None:
                present_bar = ""
                bars_to_present = ""
            else:
                present_bar = present
                bars_to_present = present - proof
    else:
        raise SystemExit(f"unknown rule {rule}")

    # gaps vs the primary (true proof bar) and secondary (arm bar) refs
    gap_proof = gap_arm = None
    if limit not in (None, ""):
        gap_price = abs(float(limit) - proof_close)
        gap_proof = None if atr_proof is None else gap_price / atr_proof
        if arm is not None:
            arm_close = float(bars[arm].close)
            gap_arm = None if atr_arm is None \
                else abs(float(limit) - arm_close) / atr_arm
    if gap_proof is None and limit not in (None, ""):
        gaps.append("atr_unavailable")

    # paper path (disclosed secondary; lifetimes frozen per rule)
    paper = paper_path(base, bars_dict, direction, limit, rest_bars, rule,
                       present_bar, joined)
    row.update({
        "episode_id": base["episode_id"],
        "population": base["population"],
        "rule": rule,
        "direction": base["direction"],
        "trigger": base["trigger"],
        "matched_fill": base.get("matched_fill", ""),
        "rest_bars": rest_bars if rest_bars is not None else "",
        "fallback": fallback,
        "fallback_reason": fallback_reason,
        "limit": "" if limit is None else limit,
        "gap_atr_proof": "" if gap_proof is None else gap_proof,
        "gap_atr_arm": "" if gap_arm is None else gap_arm,
        "flag_le_1": "True" if gap_proof is not None and gap_proof <= 1.0 else "False",
        "flag_le_2": "True" if gap_proof is not None and gap_proof <= 2.0 else "False",
        "present_bar": present_bar,
        "bars_to_present": bars_to_present,
        "data_gap": "True" if gaps else "False",
        "data_gap_reasons": ";".join(gaps),
    })
    row.update(paper)
    return row


def paper_path(base: dict, bars_dict, direction, limit, rest_bars, rule: str,
               present_bar, joined: dict) -> dict:
    """Frozen near-miss paper semantics; SL/TP only where recorded (P0)."""
    out = {"paper_first_bar": "", "paper_fill_bar": "", "paper_outcome": "",
           "paper_note": ""}
    if limit in (None, "") or direction in (None, ""):
        out["paper_outcome"] = "DATA_GAP"
        return out
    proof = int(base["proof_bar_grid"])
    if base["population"] == "0" and base["matched_fill"] == "True" or \
            base["population"] == "0":
        # P0 routes carry recorded SL/TP + lifetime (candidates join)
        cand = joined["candidates_by_route"].get(base["route_id"])
        if cand is None or rest_bars is None:
            out["paper_outcome"] = "DATA_GAP"
            return out
        route = {
            "route_id": base["route_id"], "direction": direction,
            "entry": float(limit), "sl": cand["sl"], "tp": cand["tp"],
            "original_sl": cand["original_sl"],
            "present_bar": int(present_bar) if present_bar != "" else proof,
            "rest_bars": (rest_bars - (int(present_bar) - proof)
                          if rule == RULE_RL3 and present_bar != ""
                          else rest_bars),
            "anchor_kind": f"{rule}_reconstruction",
        }
        if rule == RULE_RL3 and (present_bar == "" or route["rest_bars"] <= 0):
            out["paper_outcome"] = "EXPIRED_NO_PRESENTATION"
            return out
        sim = nm.simulate_route(route, bars_dict)
        out["paper_first_bar"] = route["present_bar"]
        out["paper_fill_bar"] = sim.get("fill_index") or ""
        out["paper_outcome"] = sim.get("outcome") or "DATA_GAP"
        out["paper_note"] = (f"limit={rule}; "
                             + (sim.get("note") or ""))
        return out
    # P1: touch-only (SL/TP never invented)
    if rest_bars is None:
        out["paper_outcome"] = "DATA_GAP"
        out["paper_note"] = "missing lifetime"
        return out
    if rule == RULE_RL3:
        if present_bar == "":
            out["paper_outcome"] = "EXPIRED_NO_PRESENTATION"
            return out
        first = int(present_bar)
        last = min(first + (rest_bars - (first - proof)), len(bars_dict) - 1)
        out["paper_first_bar"] = first
    else:
        first = proof
        last = min(proof + rest_bars, len(bars_dict) - 1)
        out["paper_first_bar"] = first
    fill = nm.first_touch(direction, float(limit), bars_dict, first, last)
    if fill is None:
        out["paper_outcome"] = "EXPIRED_NO_FILL"
    else:
        out["paper_fill_bar"] = fill
        out["paper_outcome"] = "FILLED_NO_RESOLVE"  # no SL/TP invented
    return out


# --------------------------------------------------------------------------- #
# Aggregate + kills
# --------------------------------------------------------------------------- #
def aggregate_rule(rows_p1: list[dict], rows_p0: list[dict]) -> dict:
    def vals(sub, field):
        return [float(r[field]) for r in sub if r[field] != ""]

    gap_p1 = vals(rows_p1, "gap_atr_proof")
    gap_p1_arm = vals(rows_p1, "gap_atr_arm")
    le1 = sum(1 for r in rows_p1 if r["flag_le_1"] == "True")
    le2 = sum(1 for r in rows_p1 if r["flag_le_2"] == "True")

    def pct(n, d):
        return (n / d) if d else None

    fills = [r for r in rows_p0 if r["matched_fill"] == "True"]
    overlap = sum(1 for r in fills
                  if r["paper_outcome"] not in ("", "DATA_GAP",
                                                "EXPIRED_NO_FILL",
                                                "EXPIRED_NO_PRESENTATION"))
    path_rows = [r for r in rows_p1 if r["rest_bars"] != ""
                 and r["paper_outcome"] in ("EXPIRED_NO_FILL",
                                            "FILLED_NO_RESOLVE")]
    expired_path = sum(1 for r in path_rows
                       if r["paper_outcome"] == "EXPIRED_NO_FILL")
    exp_rate = (expired_path / len(path_rows)) if path_rows else None
    stats = {
        "n_p1": len(rows_p1),
        "median_gap_atr_p1": median(gap_p1) if gap_p1 else None,
        "p25_gap_atr_p1": er.pct(gap_p1, 0.25),
        "p75_gap_atr_p1": er.pct(gap_p1, 0.75),
        "median_gap_atr_p1_arm": median(gap_p1_arm) if gap_p1_arm else None,
        "share_le_1_p1": pct(le1, len(rows_p1)),
        "share_le_2_p1": pct(le2, len(rows_p1)),
        "data_gap_rate_p1": pct(sum(1 for r in rows_p1
                                    if r["data_gap"] == "True"), len(rows_p1)),
        "fallback_count_p1": sum(1 for r in rows_p1 if r["fallback"] == "True"),
        "fallback_reasons_p1": dict(Counter(r["fallback_reason"]
                                            for r in rows_p1
                                            if r["fallback"] == "True")),
        "n_fills_evaluable": sum(1 for r in fills
                                 if r["paper_outcome"] not in ("", "DATA_GAP")),
        "fill_overlap": overlap,
        "fill_rows": [{k: r[k] for k in ("episode_id", "limit", "gap_atr_proof",
                                         "paper_outcome")} for r in fills],
        "n_paper_lifetime_path": len(path_rows),
        "paper_expired_rate_path": exp_rate,
        "paper_outcome_mix_p1": dict(Counter(r["paper_outcome"]
                                             for r in rows_p1
                                             if r["paper_outcome"])),
        "rl3_presentation_rates": (
            {"presented": sum(1 for r in rows_p1 if r["present_bar"] != ""),
             "median_bars_to_present": (
                 median([int(r["bars_to_present"]) for r in rows_p1
                         if r["bars_to_present"] != ""])
                 if any(r["bars_to_present"] != "" for r in rows_p1) else None)}
            if rows_p1 and rows_p1[0]["rule"] == RULE_RL3 else None),
        "median_gap_atr_p0": median(vals(rows_p0, "gap_atr_proof"))
        if any(r["gap_atr_proof"] for r in rows_p0) else None,
    }
    return stats


def build_all() -> tuple[list[dict], dict]:
    base_rows, joins = load_base()
    cand = base_rows  # er rows.csv: first 10 rows are P0
    p0_base = [r for r in base_rows if r["population"] == "0"]
    p1_base = [r for r in base_rows if r["population"] == "1"]
    assert len(p0_base) == EXPECTED_P0, len(p0_base)
    assert len(p1_base) == EXPECTED_P1, len(p1_base)
    # candidates join for paper SL/TP (P0)
    with (REPO_ROOT / "06_RESEARCH" / "results" / "near_miss_counterfactual"
          / "candidates.csv").open(encoding="utf-8", newline="") as f:
        candidates = list(csv.DictReader(f))
    joins["candidates_by_route"] = {c["route_id"]: c for c in candidates}

    bars, offset = ram.load_series()
    assert offset == er.EXPECTED_WARMUP_OFFSET_SOURCE, offset
    atr_lookup = ram.atr_factory(bars)
    bars_dict = [{"timestamp": c.timestamp, "open": getattr(c, "open", None),
                  "high": c.high, "low": c.low, "close": c.close}
                 for c in bars]

    all_rows: list[dict] = []
    for rule in RULES:
        for base in p0_base:
            b = dict(base)
            b["matched_fill"] = base["matched_fill"]
            rest = rest_bars_for(base, joins)
            all_rows.append(evaluate_row_rule(b, bars, bars_dict,
                                              atr_lookup, rule, rest, joins))
        for base in p1_base:
            b = dict(base)
            b["matched_fill"] = base["matched_fill"]
            rest = rest_bars_for(base, joins)
            all_rows.append(evaluate_row_rule(b, bars, bars_dict,
                                              atr_lookup, rule, rest, joins))
    assert len(all_rows) == (EXPECTED_P0 + EXPECTED_P1) * len(RULES), len(all_rows)
    return all_rows, {"p0": p0_base, "p1": p1_base}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", default=None,
                        help="override artifact directory (determinism runs)")
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir) if args.out_dir else OUT_DIR

    t0 = time.perf_counter()
    all_rows, base_maps = build_all()

    per_rule: dict[str, dict] = {}
    for rule in RULES:
        r_p1 = [r for r in all_rows if r["rule"] == rule
                and r["population"] == "1"]
        r_p0 = [r for r in all_rows if r["rule"] == rule
                and r["population"] == "0"]
        stats = aggregate_rule(r_p1, r_p0)
        verdict = evaluate_rule_kills(stats)
        per_rule[rule] = {**stats, "kill_evaluation": verdict,
                          "verdict": verdict["verdict"]}

    out_dir.mkdir(parents=True, exist_ok=True)
    rows_path = out_dir / "rows.csv"
    with rows_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(ROW_FIELDS)
        for row in all_rows:
            writer.writerow([row.get(k, "") if row.get(k) is not None else ""
                             for k in ROW_FIELDS])
    meta = {
        "banner": BANNER,
        "logic_changed": "NO",
        "design": "00_LOCKED/ENTRY_REPRESENTATION_DESIGN.md (ACCEPTED 2026-10-14)",
        "frozen": {
            "k_shelf": K_SHELF, "retrace_fraction": RETRACE_FRACTION,
            "leg_span_lookback": LEG_SPAN_LOOKBACK,
            "present_prox_atr": PRESENT_PROX_ATR,
            "kill_thresholds": {"median_far": KILL_MEDIAN_FAR,
                                "near_share": KILL_NEAR_SHARE,
                                "expired_rate": KILL_EXPIRED_RATE,
                                "expired_min_n": KILL_EXPIRED_MIN_N,
                                "gap_rate": KILL_GAP_RATE},
            "primary_under_test": RULE_RL1,
            "stacking": "none (per architect default)",
            "tp_sl": "unchanged (limit only; recorded SL/TP for P0 paper)",
            "frame": "verified exec->grid (+6018) as entry-rep study",
            "fail_closed": "missing input -> DATA_GAP, limit undefined",
        },
        "per_rule": per_rule,
        "hypotheses_note": "PRIMARY verdict = RL-1; RULE_RL2/RULE_RL3 side-by-side",
    }
    summary_path = out_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str, ensure_ascii=False)

    rows_sha = hashlib.sha256(rows_path.read_bytes()).hexdigest()
    sum_sha = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    print(f"[rep-measure] rules={list(RULES)}", flush=True)
    for rule in RULES:
        s = per_rule[rule]
        print(f"[rep-measure] {rule}: median={s['median_gap_atr_p1']} "
              f"le1={s['share_le_1_p1']} gap_rate={s['data_gap_rate_p1']} "
              f"overlap={s['fill_overlap']}/{EXPECTED_CONTROLS_FILL} "
              f"expired_rate={s['paper_expired_rate_path']} "
              f"verdict={s['verdict']}", flush=True)
    print(f"[rep-measure] runtime={time.perf_counter() - t0:.1f}s", flush=True)
    print(f"[rep-measure] sha rows={rows_sha}", flush=True)
    print(f"[rep-measure] sha summary={sum_sha}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
