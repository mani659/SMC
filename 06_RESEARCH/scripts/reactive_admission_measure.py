#!/usr/bin/env python3
"""REACTIVE ADMISSION — OFFLINE COUNTERFACTUAL MEASURE (research only)

> BANNER: DIAGNOSTIC -- NOT EDGE / NOT AUTHORIZATION TO SHIP.

Authority chain (this task): 00_LOCKED/REACTIVE_ADMISSION_DESIGN.md
(DESIGN_LOCK accepted 2026-10-13, R1-R6 + kill criteria) applied as a
**counterfactual classifier** on the frozen 6m book / coincidence artifacts,
BEFORE any product code. LOGIC_CHANGED: NO -- research scripts + tests only,
no admission wiring, no locked_constants edits, no live/paper changes.

FROZEN METHOD (fixed before the run; do not tune after seeing results):

* Populations (from the coincidence study's own artifacts, no re-detection):
    - Population 1 (PRIMARY): coincident @ H=48 (coincident_48 True) AND
      product_fate in {filled, routed, armed_never_routed,
      armed_never_routed_zone_only}  -- armed + coincident (268 expected).
    - Population 2 (report only): coincident @ 48 AND product_fate
      never_armed AND episode appears in the 474 decomposition with
      in_accepted_packs True (208 expected).
    - Population 3 (report only): every other coincident episode (109
      expected). 585 = 268 + 208 + 109 (asserted, never softened).
  Populations 2-3 are REPORT ONLY -- not Phase-1 pass/fail.

* Row = one coincident episode; its candidate proof = the FIRST
  coincidence within H=48 (first_coinc_* fields -- the coincidence
  study's own de-duplicated choice). One proposed candidate per episode
  (episode-level one-shot, R6).

* Rule evaluation:
    R1 thesis  : Phase-1 = episode armed in the product run (armed facts
                 present) AND armed at/before the proof bar (reactive
                 path only). Armed facts missing -> DATA_GAP fail-closed.
                 Pop-2/3 rows get R1=fail (scope: unarmed thesis) and a
                 report-only would_admit_phase2 column (R2-R6 outcome).
    R2 proof   : directional Stage-3 completion exists (the candidate
                 proof) AND the episode direction parses. Completion
                 proofs are evaluated against the episode's own POI
                 (Step-3 construction) so alignment is inherent;
                 missing direction/trigger -> DATA_GAP fail-closed.
    R3 timing  : R3a = proof inside H_PROOF=48 of the thesis anchor
                 (ref; the coincident_48 flag itself). R3b = the market
                 returns to the zone band (proximal-edge touch,
                 inclusive; fill_model touch semantics) within
                 H_RETURN=20 M5 bars of the proof INCLUDING the proof
                 bar itself (a market already at structure when the
                 proof completes is IN-ZONE at presentation, not a
                 failure). No re-entry in the window -> R3 fail.
                 Missing zone bounds -> DATA_GAP fail-closed.
    R4 location: presentation bar = first bar in the R3b window whose
                 evaluation satisfies the design's NAMED rule
                 market_reentered_zone (band path on close OR limit
                 touch), imported from smc.risk.fill_regime_policy.
                 Proximity guard: |would_be_limit - close| <=
                 PROX_ATR_MULT * ATR at that bar (1.0) -> else fail
                 (the near-miss quantified representation failure).
    R5 filters : (a) late-chase at the presentation bar: range >
                 CHASE_RANGE_ATR_MULT * ATR (1.5) AND closing beyond the
                 zone away from entry (LONG: close > zone_high; SHORT:
                 close < zone_low).  (b) session: is_allowed_session
                 with the product's allowed sessions (ASIA/LONDON/
                 NEW_YORK).  (c) adverse invalidation: the ENGINE's own
                 §5 semantics over (thesis_anchor, presentation] — a
                 full adverse gap VIOLATES only when the zone was never
                 touched before it (a touched zone is TESTED, and the
                 engine never violates a TESTED zone).
    R6 one-shot: a product route that presented STRICTLY BEFORE the
                 presentation bar consumed the episode one-shot -> fail
                 (route presented at/after the presentation bar is the
                 episode's own proposal; that is the overlap population).

* Measure constants (NOT locked_constants; frozen for this study only):
    H_PROOF=48, H_RETURN=20, PROX_ATR_MULT=1.0, CHASE_RANGE_ATR_MULT=1.5,
    baseline proximity guard only -- NO grid search.
  ATR convention: SMA(14) of true range ending AT the bar (inclusive),
  computed on the Step-3 M5 grid; disclosed as a measure convention
  (the product path uses SeriesState ATR).

* Zone bounds priority: armed record (refined armed box, 30 armed POIs)
  -> census episode bounds. Route records supply entry/sl/tp only (and
  the would-be limit for routed episodes).

* Fail-closed: any missing field -> would_admit=False + data_gap flag +
  gap reason. Prices/times are never invented.

* Paper outcome (secondary, disclosed): frozen near-miss fill semantics
  via the near-miss script's helpers (imported, not re-derived): route
  rows simulate with their recorded entry/sl/tp; zone-edge rows test
  the would-be limit touch over the product rest lifetime
  (rest_bars_for) and label EXPIRED_NO_FILL / FILLED_NO_RESOLVE (SL/TP
  not reconstructable for unarmed candidates -- never invented).

* Determinism: pure re-analysis of saved artifacts + one series load;
  stable column order; dual run must be byte-identical.

Kill criteria (design section 5.3, verbatim thresholds):
  1 N_would_admit(Pop1) < 8                          -> FAIL_TIGHT
  2 N_would_admit >= 25 AND paper EXPIRED_NO_FILL
    rate > 85% among evaluable would-admits          -> FAIL_REPRESENTATION
  3 0 overlap with the 3 control fills (evaluable)   -> FAIL_BASELINE
  4 N_would_admit > 150                              -> FAIL_FLOOD
  DATA_GAP rate on Pop-1 > GAP_INCONCLUSIVE_RATE (0.20) -> INCONCLUSIVE
  otherwise                                          -> PASS_MEASURE
PASS_MEASURE does NOT authorize live wiring -- it only unlocks
Architect review of a possible implement prompt.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
SCRIPTS_DIR = REPO_ROOT / "06_RESEARCH" / "scripts"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from smc.config.timeframe import Timeframe          # noqa: E402
from smc.data.parquet_loader import load_ohlcv_parquet  # noqa: E402
from smc.data.resample import resample_multi        # noqa: E402
# IMPORTANT: import a backtest module BEFORE fill_regime_policy — the
# product's own import order (series_state / runner first) resolves the
# backtest <-> fill_regime_policy import cycle; importing the risk module
# standalone deadlocks mid-cycle.
import smc.backtest.series_state                    # noqa: E402,F401
from smc.core.enums import Direction                # noqa: E402
from smc.risk.fill_regime_policy import (           # noqa: E402
    market_reentered_zone,
    rest_bars_for,
)
from smc.execution.session_filter import is_allowed_session  # noqa: E402

import near_miss_counterfactual as nm               # noqa: E402 (frozen helpers)
import poi_swept_ltf_confirm as step3               # noqa: E402 (grid constants)

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "reactive_admission_measure"
ROWS_CSV = OUT_DIR / "rows.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"

BANNER = "DIAGNOSTIC -- NOT EDGE / NOT AUTHORIZATION TO SHIP"

# Frozen inputs (all published artifacts; no re-detection anywhere).
COINC_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "coincidence_count"
EPISODE_CSV = COINC_DIR / "episode_coincidence.csv"
CENSUS_CSV = (REPO_ROOT / "06_RESEARCH" / "results" / "htf_poi_census"
              / "poi_episodes.csv")
DECOMP_CSV = (REPO_ROOT / "06_RESEARCH" / "results" / "confirm_never_routed_474"
              / "decomposition.csv")
CAND_CSV = (REPO_ROOT / "06_RESEARCH" / "results" / "near_miss_counterfactual"
            / "candidates.csv")
NM_OUTCOMES_CSV = (REPO_ROOT / "06_RESEARCH" / "results" / "near_miss_counterfactual"
                   / "outcomes.csv")
ARMED_JSON = (REPO_ROOT / "06_RESEARCH" / "results" / "poi_confirm_entry_path"
              / "replay_run1" / "armed_records.json")
PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"

# Frozen measure constants (measure-only; never locked_constants).
H_PROOF = 48          # M5 bars, coincidence study primary horizon
H_RETURN = 20         # M5 bars, design R3 return window
PROX_ATR_MULT = 1.0   # design R4 proximity guard
CHASE_RANGE_ATR_MULT = 1.5  # design R5a chase texture
GAP_INCONCLUSIVE_RATE = 0.20
EXPECTED_POP = {1: 268, 2: 208, 3: 109}
EXPECTED_COINCIDENT = 585

# Exec-window origin of the replay's own grid (asserted, never assumed --
# same assertion the coincidence study used and passed 3/3 on its trades).
EXEC_ORIGIN = datetime(2025, 6, 1, 22, 0, tzinfo=timezone.utc)
EXPECTED_WARMUP_OFFSET = 6018
EXPECTED_GRID_BARS = 42296

ARMED_FATES = frozenset({"filled", "routed", "armed_never_routed",
                         "armed_never_routed_zone_only"})

ROW_FIELDS = [
    "episode_id", "tf", "kind_tag", "direction", "population", "product_fate",
    "ref_kind", "ref_bar", "ref_ts", "first_sweep_ts",
    "proof_bar", "proof_ts", "proof_trigger", "proof_stage3_bar",
    "armed_poi_id", "armed_bar", "armed_ts",
    "route_poi_id", "route_id", "route_present_bar",
    "zone_source", "zone_low", "zone_high", "would_be_limit",
    "is_m8", "detection_tf", "rest_bars", "atr_at_proof",
    "r1_thesis", "r1_reason", "r2_proof", "r2_reason",
    "r3_timing", "r3_reason", "r4_location", "r4_reason",
    "r5_exclusion", "r5_reason", "r6_one_shot", "r6_reason",
    "data_gap", "data_gap_reasons",
    "would_admit", "would_admit_phase2",
    "presentation_bar", "presentation_ts", "session_ok", "chase",
    "zone_violated", "closest_approach_return",
    "paper_touched", "paper_fill_bar", "paper_outcome", "paper_note",
    "matched_route_id", "matched_fill",
]


# --------------------------------------------------------------------------- #
# Small frozen helpers (pure, unit-tested)
# --------------------------------------------------------------------------- #
def parse_direction(raw) -> str | None:
    """'short'/'long' in near-miss helper space; None when unknown."""
    if raw is None:
        return None
    text = str(raw).strip().upper()
    if text == "LONG":
        return "long"
    if text == "SHORT":
        return "short"
    return None


def parse_tf_fields(tf_raw) -> tuple[str | None, bool]:
    """census tf -> (detection_tf_name, is_m8); None name -> gap."""
    text = str(tf_raw or "").strip().upper()
    if not text:
        return None, False
    if text.startswith("M8"):
        parts = text.split("-", 1)
        if len(parts) != 2:
            return None, True
        return parts[1], True
    return text, False


def proximal_edge(direction: str | None, zone_low, zone_high):
    """Design R4 fallback limit: the zone edge the market reaches first.

    LONG enters through the zone top; SHORT enters through the zone
    bottom. Missing bounds -> None (fail-closed upstream).
    """
    if direction is None or zone_low in (None, "") or zone_high in (None, ""):
        return None
    try:
        low, high = float(zone_low), float(zone_high)
    except (TypeError, ValueError):
        return None
    if direction == "long":
        return high
    return low


def sma_tr_atr(bars, bar_index: int, period: int = 14):
    """SMA(period) of true range ending AT ``bar_index`` (inclusive).

    None before the period is available (fail-closed upstream). This is
    a measure convention, disclosed in the note.
    """
    if bar_index is None or bar_index < 0 or bar_index >= len(bars):
        return None
    if bar_index < period:
        return None
    total = 0.0
    for i in range(bar_index - period + 1, bar_index + 1):
        bar = bars[i]
        prev = bars[i - 1]
        prev_close = getattr(prev, "close", None)
        high = getattr(bar, "high", None)
        low = getattr(bar, "low", None)
        if prev_close is None or high is None or low is None:
            return None
        tr = max(float(high) - float(low),
                 abs(float(high) - float(prev_close)),
                 abs(float(low) - float(prev_close)))
        total += tr
    return total / period


def classify_population(fate: str, in_packs: bool | None) -> int | None:
    """Frozen population split (coincident rows are checked upstream)."""
    if fate in ARMED_FATES:
        return 1
    if fate == "never_armed":
        if in_packs:
            return 2
        return 3
    return None


def violated_since(direction: str, zone_low, zone_high, bars, start: int,
                   end: int) -> bool:
    """True §5 engine semantics over (start, end] (exclusive start).

    Mirrors the engine's FRESH-state machine: walking bar order, an
    adverse full-gap close (LONG: high < zone_low; SHORT: low >
    zone_high) VIOLATES only if no zone touch has happened yet — a
    touched (TESTED) zone never violates in the engine, and the reactive
    design's R5.3 means the engine's own condition, not any stricter
    artifact-level proxy.
    """
    if direction is None or zone_low in (None, "") or zone_high in (None, ""):
        return False  # caller fails closed separately on missing bounds
    low, high = float(zone_low), float(zone_high)
    for i in range(start + 1, min(end, len(bars) - 1) + 1):
        bar = bars[i]
        b_high, b_low = float(bar.high), float(bar.low)
        if direction == "long":
            if b_high < low:
                return True   # full gap below the zone, never touched
            if b_high >= low and b_low <= high:
                return False  # touch first -> TESTED; engine never violates after
        else:
            if b_low > high:
                return True
            if b_low <= high and b_high >= low:
                return False
    return False


def to_direction_enum(direction: str | None):
    """The design's NAMED rule compares direction by ENUM identity
    (``direction is Direction.LONG``); a plain string silently disables
    its limit-touch path. Convert once, explicitly (None -> None so the
    caller's fail-closed path still fires)."""
    if direction == "long":
        return Direction.LONG
    if direction == "short":
        return Direction.SHORT
    return None


def first_presentation_bar(bars, direction, zone_low, zone_high, limit,
                           proof_bar: int, max_window: int, atr_lookup):
    """First bar in [proof, proof+max_window] satisfying the design's named
    re-entry rule (band path on close OR limit touch). None when absent.

    The proof bar itself is included: the design's return window is
    'within H_return of the proof event', and a market already at the
    structure when the proof completes is IN-ZONE at presentation, not a
    rule failure.
    """
    if not isinstance(direction, Direction):
        if direction is None:
            return None
        direction = to_direction_enum(direction)  # string tolerance (tests)
    if direction is None or zone_low in (None, "") or zone_high in (None, ""):
        return None
    low, high = float(zone_low), float(zone_high)
    last = min(proof_bar + max_window, len(bars) - 1)
    for i in range(proof_bar, last + 1):
        bar = bars[i]
        atr = atr_lookup(i)
        if market_reentered_zone(direction, low, high, limit,
                                 float(bar.close), atr, bar=bar):
            return i
    return None


def evaluate_r_rules(row: dict, bars, atr_lookup) -> dict:
    """Evaluate R1-R6 for one row. Fail-closed; returns flag/reason dict.

    Every St evaluate fills a (status, reason) pair with status in
    PASS|FAIL|GAP; ``data_gap`` aggregates GAP states; would_admit
    requires every rule PASS and no GAP.
    """
    out: dict = {
        "presentation_bar": None, "presentation_ts": None,
        "session_ok": None, "chase": None, "zone_violated": None,
        "closest_approach_return": None,
    }
    data_gap_reasons: list[str] = []

    direction = parse_direction(row.get("direction"))
    # NOTE: ``direction`` stays the lowercase-string form ('long'/'short')
    # for OUR helpers (violated_since / chase); only the NAMED product rule
    # needs the enum, and first_presentation_bar converts it internally.
    zone_low = row.get("zone_low")
    zone_high = row.get("zone_high")
    proof_exec = row.get("proof_bar")  # exec index (None when unusable)
    limit = row.get("would_be_limit")

    def flag(rule: str, status: str, reason: str = "") -> None:
        out[f"{rule}"] = status
        out[f"{rule[0:2]}_reason"] = reason  # r1-r6 matching reason column

    # ---- R2 first (it only needs census facts; needed for phase2 report) --- #
    trigger = row.get("proof_trigger")
    if direction is None:
        flag("r2_proof", "GAP", "missing_direction")
        data_gap_reasons.append("r2:missing_direction")
    elif trigger in (None, ""):
        flag("r2_proof", "GAP", "missing_trigger")
        data_gap_reasons.append("r2:missing_trigger")
    else:
        flag("r2_proof", "PASS", "")

    # ---- R1 (Phase-1 scope) ---------------------------------------------- #
    if row["population"] == 1:
        if row.get("armed_poi_id") in (None, "") or row.get("armed_bar") is None:
            flag("r1_thesis", "GAP", "missing_armed_facts")
            data_gap_reasons.append("r1:missing_armed_facts")
        elif proof_exec is None:
            flag("r1_thesis", "GAP", "missing_proof_bar")
            data_gap_reasons.append("r1:missing_proof_bar")
        elif int(row["armed_bar"]) <= int(proof_exec):
            flag("r1_thesis", "PASS", "")
        else:
            flag("r1_thesis", "FAIL", "thesis_not_armed_at_proof")
    else:
        flag("r1_thesis", "FAIL", "phase1_scope_unarmed")

    # ---- zone sanity (used by R3/R4/R5) ---------------------------------- #
    bounds_ok = (direction is not None and zone_low not in (None, "")
                 and zone_high not in (None, ""))
    if not bounds_ok:
        data_gap_reasons.append("r3:missing_zone_bounds")
    if limit is None:
        data_gap_reasons.append("r4:missing_limit")

    # ---- R3 timing -------------------------------------------------------- #
    return_bar = None
    if proof_exec is None:
        flag("r3_timing", "GAP", "missing_proof_bar")
        data_gap_reasons.append("r3:missing_proof_bar")
    elif not bounds_ok or limit is None:
        flag("r3_timing", "GAP", "missing_zone_or_limit")
    else:
        return_bar = first_presentation_bar(
            bars, direction, zone_low, zone_high, limit,
            int(proof_exec), H_RETURN, atr_lookup)
        if return_bar is None:
            flag("r3_timing", "FAIL", "no_return_in_window")
        else:
            flag("r3_timing", "PASS", "")

    # ---- R4 location ------------------------------------------------------ #
    prove_grad = False
    if return_bar is None:
        if out["r3_timing"] == "PASS":
            flag("r4_location", "GAP", "fatal")
        else:
            flag("r4_location", "FAIL", "no_presentation_in_window")
    else:
        bar = bars[return_bar]
        atr = atr_lookup(return_bar)
        distance = abs(float(limit) - float(bar.close))
        out["presentation_bar"] = return_bar
        out["presentation_ts"] = getattr(bar, "timestamp", None)
        out["closest_approach_return"] = distance
        if atr is None:
            flag("r4_location", "GAP", "atr_unavailable_at_presentation")
            data_gap_reasons.append("r4:atr_unavailable")
        elif distance <= PROX_ATR_MULT * float(atr):
            flag("r4_location", "PASS", "")
        else:
            flag("r4_location", "FAIL", "limit_far_from_market")

    # ---- R5 exclusions ---------------------------------------------------- #
    if return_bar is None:
        flag("r5_exclusion", "FAIL", "no_presentation_in_window")
    elif not bounds_ok:
        flag("r5_exclusion", "GAP", "missing_zone_bounds")
    else:
        bar = bars[return_bar]
        atr = atr_lookup(return_bar)
        range_val = float(bar.high) - float(bar.low)
        chase = (atr is not None and range_val > CHASE_RANGE_ATR_MULT * atr
                 and ((direction == "long" and float(bar.close) > float(zone_high))
                      or (direction == "short" and float(bar.close) < float(zone_low))))
        session_ok = is_allowed_session(getattr(bar, "timestamp", None))
        anchor = row.get("armed_bar")
        anchor = int(anchor) if anchor is not None else int(proof_exec)
        violated = violated_since(direction, zone_low, zone_high, bars,
                                  anchor, return_bar)
        out["chase"] = chase
        out["session_ok"] = session_ok
        out["zone_violated"] = violated
        reasons = []
        if chase:
            reasons.append("late_chase")
        if not session_ok:
            reasons.append("session_out")
        if violated:
            reasons.append("zone_violated")
        if reasons:
            flag("r5_exclusion", "FAIL", "+".join(reasons))
        else:
            flag("r5_exclusion", "PASS", "")

    # ---- R6 one-shot ------------------------------------------------------ #
    route_present = row.get("route_present_bar")
    if return_bar is None:
        flag("r6_one_shot", "FAIL", "no_presentation_in_window")
    elif route_present in (None, ""):
        flag("r6_one_shot", "PASS", "")
    elif int(route_present) < int(return_bar):
        flag("r6_one_shot", "FAIL", "one_shot_consumed_by_route")
    else:
        flag("r6_one_shot", "PASS", "")

    statuses = [out["r1_thesis"], out["r2_proof"], out["r3_timing"],
                out["r4_location"], out["r5_exclusion"], out["r6_one_shot"]]
    out["data_gap"] = "True" if any(s == "GAP" for s in statuses) else "False"
    out["data_gap_reasons"] = ";".join(data_gap_reasons)
    out["would_admit"] = ("True" if statuses == ["PASS"] * 6 else "False")
    out["would_admit_phase2"] = (
        "True" if statuses[1:] == ["PASS"] * 5 else "False")
    return out


def evaluate_paper_outcome(row: dict, bars, pop: int) -> dict:
    """Secondary paper outcome under frozen near-miss semantics.

    Route rows simulate the recorded placement outright. Zone-edge rows
    ask whether the would-be limit was touched within the product rest
    lifetime (touch only -- SL/TP are never invented).
    """
    out = {"paper_touched": None, "paper_fill_bar": None,
           "paper_outcome": None, "paper_note": ""}
    admit = row.get("would_admit") == "True" or row.get("would_admit_phase2") == "True"
    presentation = row.get("presentation_bar")
    if not admit or presentation is None:
        out["paper_outcome"] = "NOT_ADMITTED"
        return out
    direction = parse_direction(row["direction"])
    limit = row.get("would_be_limit")
    evidence = row.get("rest_bars")
    if evidence is None or direction is None or limit is None:
        out["paper_outcome"] = "DATA_GAP"
        out["paper_note"] = "missing lifetime/direction/limit"
        return out
    entry = row.get("route_entry")
    sl = row.get("route_sl")
    tp = row.get("route_tp")
    if entry not in (None, "") and sl not in (None, "") and tp not in (None, ""):
        route = {
            "route_id": row.get("route_id") or row["episode_id"],
            "direction": direction, "entry": entry, "sl": sl, "tp": tp,
            "original_sl": row.get("route_original_sl") or sl,
            "present_bar": int(presentation),
            "rest_bars": int(evidence),
            "anchor_kind": row.get("anchor_kind") or "route_reconstruction",
        }
        sim = nm.simulate_route(route, bars)
        out["paper_touched"] = "True" if sim.get("fill_index") is not None else "False"
        out["paper_fill_bar"] = sim.get("fill_index")
        out["paper_outcome"] = sim.get("outcome") or "DATA_GAP"
        out["paper_note"] = sim.get("note") or ""
        return out
    first, last = nm.eligible_window(int(presentation), int(evidence), len(bars))
    if last < first:
        out["paper_outcome"] = "DATA_GAP"
        out["paper_note"] = "empty eligible window"
        return out
    fill_bar = nm.first_touch(direction, float(limit), bars, first, last)
    if fill_bar is None:
        out["paper_touched"] = "False"
        out["paper_outcome"] = "EXPIRED_NO_FILL"
        closest = nm.closest_approach(direction, float(limit), bars, first, last)
        out["paper_note"] = (f"closest={closest:.3f}" if closest is not None
                             else "no range data")
    else:
        out["paper_touched"] = "True"
        out["paper_fill_bar"] = fill_bar
        out["paper_outcome"] = "FILLED_NO_RESOLVE"  # SL/TP never invented
    return out


def evaluate_kill_criteria(stats: dict) -> dict:
    """Design section 5.3 thresholds, verbatim; frozen order 1-4."""
    n = int(stats["n_would_admit_pop1"])
    expired_rate = stats.get("expired_no_fill_rate_pop1")
    gap_rate = stats.get("data_gap_rate_pop1")
    overlap_fills = stats.get("overlap_fills", 0)
    fills_evaluable = stats.get("fills_evaluable", False)

    killed = []
    if gap_rate is not None and gap_rate > GAP_INCONCLUSIVE_RATE:
        return {"verdict": "INCONCLUSIVE", "killed": [],
                "gate": f"data_gap_rate {gap_rate:.3f} > {GAP_INCONCLUSIVE_RATE}"}
    if n < 8:
        killed.append(f"kill1_under_selective (n={n} < 8)")
    if n >= 25 and expired_rate is not None and expired_rate > 0.85:
        killed.append(f"kill2_representation (expired rate {expired_rate:.3f} > 0.85)")
    if fills_evaluable and overlap_fills == 0:
        killed.append("kill3_zero_control_overlap")
    if n > 150:
        killed.append(f"kill4_flood (n={n} > 150)")
    if killed:
        label = {
            "kill1_under_selective": "FAIL_TIGHT",
        }
        # Freeze: first fired rule in design order names the verdict.
        first = killed[0]
        if first.startswith("kill1_under_selective"):
            verdict = "FAIL_TIGHT"
        elif first.startswith("kill2_representation"):
            verdict = "FAIL_REPRESENTATION"
        elif first.startswith("kill3_zero_control_overlap"):
            verdict = "FAIL_BASELINE"
        else:
            verdict = "FAIL_FLOOD"
        return {"verdict": verdict, "killed": killed, "gate": None}
    return {"verdict": "PASS_MEASURE", "killed": [], "gate": None}


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #
def load_artifacts() -> dict:
    required = (EPISODE_CSV, CENSUS_CSV, DECOMP_CSV, CAND_CSV,
                NM_OUTCOMES_CSV, ARMED_JSON)
    for path in required:
        if not path.exists():
            raise SystemExit(f"required input missing: {path}")
    with EPISODE_CSV.open(encoding="utf-8", newline="") as f:
        episodes = {r["episode_id"]: r for r in csv.DictReader(f)}
    with CENSUS_CSV.open(encoding="utf-8", newline="") as f:
        census = {r["episode_id"]: r for r in csv.DictReader(f)}
    with DECOMP_CSV.open(encoding="utf-8", newline="") as f:
        decomp = {r["episode_id"]: r for r in csv.DictReader(f)}
    with CAND_CSV.open(encoding="utf-8", newline="") as f:
        routes = list(csv.DictReader(f))
    routes_by_poi: dict[str, dict] = {}
    for r in routes:
        routes_by_poi.setdefault(r["poi_id"], r)
    armed = json.loads(ARMED_JSON.read_text(encoding="utf-8"))
    return {"episodes": episodes, "census": census, "decomp": decomp,
            "routes_by_poi": routes_by_poi, "armed": armed}


def load_series() -> tuple[list, int]:
    """Step-3 M5 grid + asserted exec offset (never assumed)."""
    if not PARQUET.exists():
        raise SystemExit(f"canonical dataset missing: {PARQUET}")
    m1_all = load_ohlcv_parquet(str(PARQUET), Timeframe.M1)
    m1 = [c for c in m1_all if step3.LOAD_FROM <= c.timestamp <= step3.LOAD_END]
    if not m1:
        raise SystemExit("no M1 bars in the load window")
    m5 = resample_multi(m1, [Timeframe.M5])[Timeframe.M5]
    stamps = [c.timestamp for c in m5]
    offset = bisect.bisect_left(stamps, EXEC_ORIGIN)
    assert stamps[offset] == EXEC_ORIGIN, stamps[offset]
    assert offset == EXPECTED_WARMUP_OFFSET, offset
    assert len(m5) == EXPECTED_GRID_BARS, len(m5)
    return m5, offset


def atr_factory(bars):
    cache: dict[int, float | None] = {}

    def lookup(idx: int):
        if idx not in cache:
            cache[idx] = sma_tr_atr(bars, idx, 14)
        return cache[idx]
    return lookup


# --------------------------------------------------------------------------- #
# Row build → evaluate → write
# --------------------------------------------------------------------------- #
def build_rows(artifacts: dict, offset: int, bars, atr_lookup,
               bars_dict=None) -> list[dict]:
    """One row per coincident episode, evaluated fail-closed.

    ``bars`` = Candle list for the measure's own geometry helpers;
    ``bars_dict`` = dict mirror for the imported near-miss paper helpers
    (they read ``bar["low"]``/``bar["high"]``). Same grid, same indices.
    """
    if bars_dict is None:
        raise SystemExit("internal: bars_dict required for paper helpers")
    rows: list[dict] = []
    census = artifacts["census"]
    decomp = artifacts["decomp"]
    routes_by_poi = artifacts["routes_by_poi"]
    armed = artifacts["armed"]
    coincident = [r for r in artifacts["episodes"].values()
                  if r["coincident_48"] == "True"]
    for ep in coincident:
        eid = ep["episode_id"]
        cen = census.get(eid, {})
        in_packs = (decomp.get(eid, {}).get("in_accepted_packs") == "True"
                    if eid in decomp else False)
        population = classify_population(ep["product_fate"], in_packs)
        assert population in (1, 2, 3), (eid, ep["product_fate"], in_packs)

        proof_exec = int(ep["first_coinc_bar"]) - offset
        assert proof_exec >= 0, (eid, ep["first_coinc_bar"])

        armed_poi = ep.get("armed_poi_id") or ep.get("joined_poi_id") or ""
        armed_rec = armed.get(armed_poi) if armed_poi else None
        route = routes_by_poi.get(armed_poi or ep.get("joined_poi_id") or "")

        zone_source, zone_low, zone_high = "census", cen.get("zone_low"), cen.get("zone_high")
        if armed_rec is not None and armed_rec.get("zone_low") not in (None, ""):
            zone_source = "armed_record"
            zone_low, zone_high = armed_rec["zone_low"], armed_rec["zone_high"]

        detection_tf, is_m8 = parse_tf_fields(cen.get("tf"))
        rest_bars = None
        if detection_tf is not None:
            try:
                rest_bars = rest_bars_for(Timeframe[detection_tf], is_m8,
                                          Timeframe.M5)
            except KeyError:
                rest_bars = None

        if route is not None:
            limit = route["entry"]
        else:
            limit = proximal_edge(parse_direction(cen.get("direction")),
                                  zone_low, zone_high)

        row = {f: "" for f in ROW_FIELDS}
        row.update({
            "episode_id": eid,
            "tf": cen.get("tf", ep.get("tf", "")),
            "kind_tag": cen.get("kind_tag", ep.get("kind_tag", "")),
            "direction": cen.get("direction", ep.get("direction", "")),
            "population": population,
            "product_fate": ep["product_fate"],
            "ref_kind": ep["ref_kind"],
            "ref_bar": ep["ref_bar"],
            "ref_ts": ep["ref_ts"],
            "first_sweep_ts": ep["first_sweep_ts"],
            "proof_bar": proof_exec,
            "proof_ts": ep["first_coinc_ts"],
            "proof_trigger": ep["first_coinc_trigger"],
            "armed_poi_id": armed_poi,
            "armed_bar": (int(ep["armed_bar_exec"])
                          if ep.get("armed_bar_exec") not in (None, "") else None),
            "armed_ts": ep.get("armed_ts", ""),
            "route_poi_id": (route["poi_id"] if route else ""),
            "route_id": (route["route_id"] if route else ""),
            "route_present_bar": (int(route["first_present_bar"]) if route else None),
            "zone_source": zone_source,
            "zone_low": zone_low,
            "zone_high": zone_high,
            "would_be_limit": limit,
            "is_m8": "True" if is_m8 else "False",
            "detection_tf": detection_tf or "",
            "rest_bars": rest_bars,
            "atr_at_proof": atr_lookup(proof_exec),
            "matched_route_id": (route["route_id"] if route else ""),
            "matched_fill": "True" if ep["ever_filled"] == "True" else "False",
        })
        rules = evaluate_r_rules(row, bars, atr_lookup)
        row.update({k: v for k, v in rules.items() if k in ROW_FIELDS})
        paper = evaluate_paper_outcome(row, bars_dict, population)
        row.update(paper)
        row["is_m8"] = "True" if is_m8 else "False"
        row["population"] = population
        rows.append(row)
    return rows


def write_outputs(rows: list[dict], meta: dict, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_path = out_dir / "rows.csv"
    summary_path = out_dir / "summary.json"
    with rows_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(ROW_FIELDS)
        for row in rows:
            writer.writerow([row.get(k, "") for k in ROW_FIELDS])
    summary = {
        "banner": BANNER,
        "logic_changed": "NO",
        **meta,
    }
    # NOTE: no wall-clock field lands in summary.json -- dual runs must be
    # byte-identical (runtime is reported on the console only).
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str, ensure_ascii=False)
    return {"sha256_rows": hashlib.sha256(rows_path.read_bytes()).hexdigest(),
            "sha256_summary": hashlib.sha256(
                summary_path.read_bytes()).hexdigest()}


def aggregate(rows: list[dict], artifacts: dict) -> dict:
    pop1 = [r for r in rows if r["population"] == 1]
    pop2 = [r for r in rows if r["population"] == 2]
    pop3 = [r for r in rows if r["population"] == 3]

    def admit(sub):
        return [r for r in sub if r["would_admit"] == "True"]

    def admit_phase2(sub):
        return [r for r in sub if r["would_admit_phase2"] == "True"]

    pop1_admit = admit(pop1)
    pop1_gaps = [r for r in pop1 if r["data_gap"] == "True"]

    # Funnel over Pop-1 in pre-registered rule order (each stage shows the
    # surviving subset; rows leave the funnel at their first failing rule).
    funnel = {
        "armed_at_proof": 0,
        "returned_in_window": 0,
        "presentation_proximity_pass": 0,
        "exclusions_pass": 0,
        "one_shot_pass": 0,
    }
    first_fail = Counter()  # first failing rule in R1..R6 order
    first_fail_reason = Counter()
    for r in pop1:
        if r["data_gap"] == "True":
            continue
        if r["r1_thesis"] != "PASS":
            first_fail["r1_thesis"] += 1
            first_fail_reason[f"r1:{r['r1_reason']}"] += 1
            continue
        funnel["armed_at_proof"] += 1
        if r["r3_timing"] != "PASS":
            first_fail["r3_timing"] += 1
            first_fail_reason[f"r3:{r['r3_reason']}"] += 1
            continue
        funnel["returned_in_window"] += 1
        if r["r4_location"] != "PASS":
            first_fail["r4_location"] += 1
            first_fail_reason[f"r4:{r['r4_reason']}"] += 1
            continue
        funnel["presentation_proximity_pass"] += 1
        if r["r5_exclusion"] != "PASS":
            first_fail["r5_exclusion"] += 1
            first_fail_reason[f"r5:{r['r5_reason']}"] += 1
            continue
        funnel["exclusions_pass"] += 1
        if r["r6_one_shot"] != "PASS":
            first_fail["r6_one_shot"] += 1
            first_fail_reason[f"r6:{r['r6_reason']}"] += 1
            continue
        funnel["one_shot_pass"] += 1
    assert funnel["one_shot_pass"] == len(pop1_admit), (
        funnel["one_shot_pass"], len(pop1_admit))

    # Paper fill stats over evaluated would-admits (touch semantics only).
    evaluable = [r for r in pop1_admit
                 if r["paper_outcome"] in ("EXPIRED_NO_FILL", "FILLED_NO_RESOLVE",
                                           "TP_HIT", "SL_HIT", "OPEN_UNRESOLVED")]
    expired = [r for r in evaluable if r["paper_outcome"] == "EXPIRED_NO_FILL"]
    expired_rate = (len(expired) / len(evaluable)) if evaluable else None

    # Kill-criterion-3 "evaluable": the 3 control-fill rows had enough data
    # to KNOW whether the rule set would have admitted them (no DATA_GAP on
    # identity fields). NOT admitted is a legitimate evaluable outcome --
    # zero overlap under that condition is exactly what the baseline kill
    # exists to catch (design 5.3.3).
    fill_rows = [r for r in pop1 if r["matched_fill"] == "True"]
    fills_evaluable = (len(fill_rows) == 3
                       and all(r["data_gap"] == "False" for r in fill_rows))
    stats = {
        "population_n": {"1": len(pop1), "2": len(pop2), "3": len(pop3)},
        "n_would_admit_pop1": len(pop1_admit),
        "n_would_admit_pop2_phase2_report": len(admit_phase2(pop2)),
        "n_would_admit_pop3_phase2_report": len(admit_phase2(pop3)),
        "data_gap_rate_pop1": (len(pop1_gaps) / len(pop1)) if pop1 else None,
        "n_paper_evaluable_pop1": len(evaluable),
        "expired_no_fill_rate_pop1": expired_rate,
        "overlap_routes": len({r["matched_route_id"] for r in pop1_admit
                               if r["matched_route_id"]}),
        "overlap_route_ids": sorted({r["matched_route_id"] for r in pop1_admit
                                     if r["matched_route_id"]}),
        "overlap_fills": sum(1 for r in pop1_admit if r["matched_fill"] == "True"),
        "overlap_fill_ids": sorted(r["episode_id"] for r in pop1_admit
                                   if r["matched_fill"] == "True"),
        "fills_evaluable": fills_evaluable,
        "fill_rows_status": [
            {"episode_id": r["episode_id"],
             "rules": [r[k] for k in ("r1_thesis", "r2_proof", "r3_timing",
                                      "r4_location", "r5_exclusion", "r6_one_shot")],
             "would_admit": r["would_admit"],
             "gap": r["data_gap_reasons"]}
            for r in fill_rows],
        "funnel_pop1": funnel,
        "failure_mode_counts_first_fail": dict(first_fail),
        "failure_mode_reasons_first_fail": dict(first_fail_reason),
        "zone_source_counts_pop1": dict(Counter(r["zone_source"] for r in pop1)),
        "armed_after_proof_count": sum(1 for r in pop1
                                       if r["r1_reason"] == "thesis_not_armed_at_proof"),
        "paper_outcome_mix_pop1": dict(Counter(r["paper_outcome"] for r in pop1_admit)),
    }
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", default=None,
                        help="override artifact directory (determinism runs)")
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir) if args.out_dir else OUT_DIR

    t0 = time.perf_counter()
    artifacts = load_artifacts()
    bars, offset = load_series()
    atr_lookup = atr_factory(bars)
    print(f"[adm] grid bars={len(bars)} warmup_offset={offset}", flush=True)

    rows = build_rows(artifacts, offset, bars, atr_lookup,
                      bars_dict=[{
                          "timestamp": c.timestamp,
                          "open": getattr(c, "open", None),
                          "high": getattr(c, "high", None),
                          "low": getattr(c, "low", None),
                          "close": getattr(c, "close", None),
                      } for c in bars])
    assert len(rows) == EXPECTED_COINCIDENT, len(rows)
    stats = aggregate(rows, artifacts)

    from collections import Counter as _C
    pop_check = {k: v for k, v in stats["population_n"].items()}
    assert {k: int(v) for k, v in pop_check.items()} == {
        str(k): v for k, v in EXPECTED_POP.items()}, pop_check
    verdict = evaluate_kill_criteria(stats)

    meta = {
        "design": "00_LOCKED/REACTIVE_ADMISSION_DESIGN.md",
        "window": {
            "grid": f"{step3.LOAD_FROM.date()} .. {step3.LOAD_END.date()} M5",
            "exec_origin": EXEC_ORIGIN.isoformat(),
            "warmup_offset": offset,
            "grid_bars": len(bars),
        },
        "frozen": {
            "h_proof": H_PROOF, "h_return": H_RETURN,
            "prox_atr_mult": PROX_ATR_MULT,
            "chase_range_atr_mult": CHASE_RANGE_ATR_MULT,
            "atr_convention": "SMA(14) of TR ending at bar (inclusive)",
            "rest_rule": "smc.risk.fill_regime_policy.rest_bars_for",
            "reentry_rule": "smc.risk.fill_regime_policy.market_reentered_zone",
            "fill_semantics": "near_miss_counterfactual frozen helpers (imported)",
            "fail_closed": "missing field -> would_admit=False + DATA_GAP",
            "populations_2_3": "REPORT ONLY (not Phase-1 pass/fail)",
        },
        "stats": stats,
        "kill_criteria": verdict,
        "verdict": verdict["verdict"],
    }
    hashes = write_outputs(rows, meta, out_dir)
    print(f"[adm] rows={len(rows)} would_admit(Pop1)={stats['n_would_admit_pop1']} "
          f"verdict={verdict['verdict']}", flush=True)
    print(f"[adm] runtime={time.perf_counter() - t0:.1f}s", flush=True)
    print(f"[adm] sha rows={hashes['sha256_rows']}", flush=True)
    print(f"[adm] sha summary={hashes['sha256_summary']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
