#!/usr/bin/env python3
"""ENTRY-REPRESENTATION STUDY -- why do entry limits sit far from market?

> BANNER: DIAGNOSTIC -- NOT EDGE / NOT AUTHORIZATION TO SHIP.

Lead Architect directive, 2026-10-14. The reactive-admission measure is
CLOSED (VERDICT FAIL_TIGHT); this study does NOT re-run, re-verify or
re-discuss its verdict, does not soften any R*, and does not redesign
admission. It imports the frozen admission artifacts and grid helpers
(never forks them) to answer one question: WHY do candidate entry limits
sit far from the post-impulse market (near-miss ~26 units; admission R4
lost 138/268 on proximity)? Classification: MECHANICAL | LIFECYCLE |
BOTH | INCONCLUSIVE. Descriptive + stratified counts only -- no new
entry rule, no implement, no threshold fishing. LOGIC_CHANGED: NO.

FROZEN METHOD (fixed before the run; never tuned after seeing results):

* BAR FRAMES (verified before freezing -- see study note):
    All artifact bar columns used here (reactive ``proof_bar`` /
    ``armed_bar``, near-miss ``first_present_bar``, armed_records
    ``armed_bar``) are EXEC-frame indexes: true grid index = value +
    WARMUP_OFFSET (asserted 6018 by exact-timestamp checks).
    Verified, never assumed, per frozen input class:
      - P1 proof_ts / armed_ts vs grid[bar + offset]: exact match.
      - all 10 P0 routes: grid[first_present_bar + offset].timestamp ==
        parse(first_present_ts) (exact, all asserted at runtime).
    The closed admission measure's own ``presentation_bar`` /
    ``presentation_ts`` columns are NOT reused for gap math in this
    study (their frame provenance is the instrument residual the note
    discloses; the shifted-frame gap columns below quantify it without
    re-opening the verdict).

* Populations (frozen):
    P0 -- product routes on the frozen 6m book: the 10 near-miss
          candidates.csv rows (3 fills / 7 untaken).
    P1 -- armed + coincident: the 268 population-1 rows of the frozen
          reactive rows.csv (reused row-for-row).
    P2 -- report stratum: P1 rows that failed the admission's R4 only
          (r1/r2/r3 PASS, r4 fail, no gaps) -- counted, report-only.

* Gap definition (fail-closed; prices never invented):
    limit   = the frozen ``would_be_limit``: recorded route entry for
              routed rows, else the FR-3.1 proximal edge (LONG ->
              zone_high, SHORT -> zone_low). limit_source:
              recorded_route_entry | zone_proximal_<zone_source>.
    PRIMARY reference = close of the TRUE proof bar
              (grid[proof_bar + offset]).
    SECONDARY references = close of the true arm bar (grid[armed_bar +
              offset]); for P0 also the route's true first-presentation
              bar (same as its proof ref by the candidates frame).
    gap_price_ref = |limit - ref_close|
    gap_atr_ref   = gap_price_ref / ATR(true bar); ATR convention =
              SMA(TR, 14) ending AT the bar (the admission measure's
              disclosed convention; recomputed here with its frozen
              helper, never copied from instrument output).
    zone_width_atr = width / ATR(true proof bar).
    entry_vs_zone = on_edge (exactly the proximal edge), inside,
              beyond_zone, on_far_edge, outside -- or DATA_GAP.
    proof_before_arm = armed_bar > proof_bar (frame-consistent
              artifact-space compare; never inferred).
    DISCLOSURE columns: gap_atr_proof_shiftedframe = the identical gap
              computed at grid index = proof_bar WITHOUT the exec->
              grid conversion -- i.e. the frame the closed measure's
              market geometry actually fetched. Reported as an
              instrument-quality residual only (counts in the note);
              it never feeds any study decision.

* Verdict-family rule (frozen BEFORE the run):
    complete = share of P1 rows with computable gap_atr_proof (true
    frame). If complete < 0.70 -> INCONCLUSIVE on magnitude (complete
    subsets still tabled).
    Otherwise, over ALL computable P1 rows:
      mech = share with the MECH flag: limit exactly on the
             direction-proximal zone edge AND gap_atr_proof > 1.0.
      life = share with proof_before_arm True (over rows where both
             bar fields exist).
      BOTH        if mech >= 0.20 and life >= 0.20, or |mech-life| <= 0.05.
      MECHANICAL  if mech > life.
      LIFECYCLE   if life > mech.
      INCONCLUSIVE if both shares < 0.10 (no reading has mass).

* Mechanism counts (counts, not stories):
    M1_zone_edge_far    -- the MECH flag count (geometry of the limit
                           itself vs the market at the true proof bar).
    M2_reanchor         -- recoverable only on the 10 P0 route rows:
                           entry sits exactly on the proximal edge
                           (anchored into the zone edge by FR-3.1) vs
                           anything else. Not evaluable for unarmed
                           rows (no raw OB reference in artifacts) --
                           reported as not_evaluable, never inferred.
    M3_no_return_20     -- CITATION ONLY: the closed measure's
                           published R3 count (58). Not recomputed here;
                           disclosed with its instrument residual.
    M4_proof_after_arm  -- P1 rows with proof_before_arm True
                           (cross-check vs the published 64/268).

* Honesty rules honored:
    - No "move the limit to mid-zone" recommendation: representation
      changes live in a hypothesis list (max 5), each explicitly
      marked NOT implemented in this task.
    - Determinism: pure re-analysis of saved artifacts + one series
      load; stable column order; dual runs byte-identical (no
      wall-clock anywhere in rows.csv / summary.json).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
SCRIPTS_DIR = REPO_ROOT / "06_RESEARCH" / "scripts"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

# Import (never fork) the frozen admission-measure grid + helpers.
import reactive_admission_measure as ram  # noqa: E402

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "entry_representation"

BANNER = "DIAGNOSTIC -- NOT EDGE / NOT AUTHORIZATION TO SHIP"

EDGE_TOL = 1e-6          # limit "on the proximal edge" tolerance
GAP_ATR_NEAR = 1.0       # the R4-tied "near" threshold
COMPLETABLE_MIN = 0.70   # P1 gap completeness gate for a family verdict
BOTH_SHARE = 0.20        # both families >= this share -> BOTH
TIE_MARGIN = 0.05        # |mech - life| <= this -> BOTH
NO_MASS_SHARE = 0.10     # both shares below this -> INCONCLUSIVE
EXPECTED_P0 = 10
EXPECTED_P1 = 268
EXPECTED_COINCIDENT = 585
EXPECTED_WARMUP_OFFSET_SOURCE = ram.EXPECTED_WARMUP_OFFSET  # reuse, never re-pin
M3_PUBLISHED_R3_COUNT = 58   # citation only (closed measure, phantom frame)
M4_PUBLISHED_R1_COUNT = 64   # citation (armed-after-proof, 64/268)

ROW_FIELDS = [
    "episode_id", "population", "direction", "trigger", "detection_tf",
    "is_m8", "route_id", "arm_kind", "matched_fill",
    "armed_bar_exec", "proof_bar_exec", "presentation_bar_exec",
    "armed_bar_grid", "proof_bar_grid", "presentation_bar_grid",
    "arm_proof_bars", "proof_presentation_bars", "proof_before_arm",
    "zone_source", "zone_low", "zone_high", "zone_width_atr",
    "limit", "limit_source", "entry_vs_zone",
    "atr_proof", "atr_presentation", "atr_arm",
    "gap_price_proof", "gap_atr_proof", "close_proof",
    "gap_price_presentation", "gap_atr_presentation", "close_presentation",
    "gap_price_arm", "gap_atr_arm", "close_arm",
    "gap_atr_proof_shiftedframe",
    "mech_zone_edge_far", "r4_failed_only", "data_gap", "data_gap_reasons",
]


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #
def exec_to_grid(exec_bar, offset: int) -> int | None:
    """Exec-frame artifact index -> true grid index; None when unusable."""
    if exec_bar in (None, ""):
        return None
    idx = int(exec_bar)
    if idx < 0:
        return None
    return idx + offset


def proximal_edge_for(direction: str | None, zone_low, zone_high):
    """FR-3.1 proximal edge for the row's zone (None when unusable)."""
    return ram.proximal_edge(direction, zone_low, zone_high)


def limit_source_of(row: dict) -> tuple | None:
    """(limit, limit_source) for one frozen row; None -> caller gaps."""
    limit = row.get("limit")
    if limit is None or str(limit) == "":
        return None
    if row.get("route_id"):
        return limit, "recorded_route_entry"
    source = row.get("zone_source") or "unknown"
    return limit, f"zone_proximal_{source}"


def entry_vs_zone_state(limit, zone_low, zone_high, direction) -> str:
    """inside / on_edge / beyond_zone / on_far_edge / outside / DATA_GAP."""
    if limit in (None, "") or zone_low in (None, "") or zone_high in (None, ""):
        return "DATA_GAP"
    if direction not in ("long", "short"):
        return "DATA_GAP"
    low, high, px = float(zone_low), float(zone_high), float(limit)
    if not high >= low:
        return "DATA_GAP"
    edge = proximal_edge_for(direction, zone_low, zone_high)
    if abs(px - float(edge)) <= EDGE_TOL:
        return "on_edge"
    # the far edge is a distinct (degenerate) shape -- checked BEFORE
    # the plain inside test so that e.g. a LONG limit exactly at
    # zone_low is flagged, not swallowed by 'inside'
    on_far = abs(px - (low if direction == "long" else high)) <= EDGE_TOL
    if on_far:
        return "on_far_edge"
    if low <= px <= high:
        return "inside"
    beyond = (px > high) if direction == "long" else (px < low)
    return "beyond_zone" if beyond else "outside"


def gap_vs(bars, limit, grid_idx: int | None) -> dict:
    """gap(gap_price, gap_atr, close) at a true grid bar; fail-closed."""
    out = {"gap_price": None, "gap_atr": None, "close": None, "atr": None}
    if limit in (None, "") or str(limit) == "":
        out["reason"] = "missing_limit"
        return out
    if grid_idx is None:
        out["reason"] = "missing_bar_index"
        return out
    if not 0 <= int(grid_idx) < len(bars):
        out["reason"] = "bar_out_of_range"
        return out
    bar = bars[int(grid_idx)]
    atr = ram.sma_tr_atr(bars, int(grid_idx), 14)
    out["atr"] = atr
    out["close"] = float(bar.close)
    out["gap_price"] = abs(float(limit) - float(bar.close))
    if atr is None:
        out["reason"] = "atr_unavailable"
        return out
    out["gap_atr"] = out["gap_price"] / float(atr)
    out["reason"] = ""
    return out


def is_mech(row: dict, edge_tol: float = EDGE_TOL) -> str:
    """MECH mechanism flag (M1): 'on_edge_far' | 'near' | 'off_edge' | 'GAP'.

    on_edge_far: limit is exactly the proximal edge AND gap_atr_proof
    > 1.0 at the TRUE proof bar -- the anchored zone-edge limit far
    from the market by construction, not by drift. The state and the
    raw edge arithmetic must agree; anything missing -> GAP.
    """
    gap_atr = row.get("gap_atr_proof")
    if gap_atr in (None, ""):
        return "GAP"
    state = row.get("entry_vs_zone")
    edge = proximal_edge_for(row.get("direction"), row.get("zone_low"),
                             row.get("zone_high"))
    if state == "DATA_GAP" or edge is None:
        return "GAP"
    limit = row.get("limit")
    on_edge = state == "on_edge" and edge is not None and \
        abs(float(limit) - float(edge)) <= edge_tol
    if state in ("inside", "beyond_zone", "on_far_edge", "outside"):
        return "off_edge"
    if on_edge:
        return "on_edge_far" if float(gap_atr) > GAP_ATR_NEAR else "near"
    return "GAP"


def proof_before_arm(armed_bar_exec, proof_bar_exec) -> str:
    """"True"/"False"/"" -- artifact-space compare; never inferred."""
    if armed_bar_exec in (None, "") or proof_bar_exec in (None, ""):
        return ""
    return "True" if int(armed_bar_exec) > int(proof_bar_exec) else "False"


def pct(values, p: float):
    """Linear-interpolated percentile of a list; None if empty."""
    if not values:
        return None
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    k = (len(vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(vals) - 1)
    return vals[f] + (vals[c] - vals[f]) * (k - f)


def dist_summary(values) -> dict:
    """n / p25 / median / p75 for a list of floats."""
    return {"n": len(values), "p25": pct(values, 0.25),
            "median": median(values) if values else None,
            "p75": pct(values, 0.75)}


def classify_family(mech_share, life_share, complete_rate) -> str:
    """Frozen verdict-family rule (module docstring)."""
    if complete_rate is None or complete_rate < COMPLETABLE_MIN:
        return "INCONCLUSIVE"
    if mech_share is None or life_share is None:
        return "INCONCLUSIVE"
    if mech_share >= BOTH_SHARE and life_share >= BOTH_SHARE:
        return "BOTH"
    if mech_share < NO_MASS_SHARE and life_share < NO_MASS_SHARE:
        return "INCONCLUSIVE"
    if abs(mech_share - life_share) <= TIE_MARGIN:
        return "BOTH"
    return "MECHANICAL" if mech_share > life_share else "LIFECYCLE"


def share_le(values, threshold: float):
    if not values:
        return None
    return sum(1 for v in values if v <= threshold) / len(values)


def share(rows, pred):
    if not rows:
        return None
    return sum(1 for r in rows if pred(r)) / len(rows)


def strata(rows, key, value_field) -> dict:
    groups: dict[str, list] = {}
    for r in rows:
        groups.setdefault(str(r.get(key, "")), []).append(r.get(value_field))
    out = {}
    for k, vals in groups.items():
        usable = [float(v) for v in vals if v not in (None, "")]
        out[k] = {"n": len(vals), "n_usable": len(usable),
                  "median_gap_atr": median(usable) if usable else None,
                  "pct_le_1": share_le(usable, GAP_ATR_NEAR)}
    return out


# --------------------------------------------------------------------------- #
# Row construction
# --------------------------------------------------------------------------- #
def _truthy(v) -> bool:
    return str(v).strip().lower() == "true"


def build_p1_row(src: dict, offset: int, bars) -> dict:
    """One study row per P1 episode (armed + coincident) of the frozen
    reactive artifacts, with TRUE-frame proof/arm gaps (fail-closed)."""
    row = {f: "" for f in ROW_FIELDS}
    gaps: list[str] = []

    direction = ram.parse_direction(src.get("direction"))
    low, high = src.get("zone_low"), src.get("zone_high")
    _raw_limit = src.get("limit")
    if _raw_limit in (None, ""):
        _raw_limit = src.get("would_be_limit")  # reactive artifact column
    limit_ls = limit_source_of({
        "limit": _raw_limit,
        "route_id": src.get("route_id"),
        "zone_source": src.get("zone_source"),
    })
    if limit_ls is None:
        limit, limit_source = "", ""
        gaps.append("missing_limit")
    else:
        limit, limit_source = limit_ls
    state = entry_vs_zone_state(limit, low, high, direction)
    if state == "DATA_GAP" and limit not in (None, ""):
        gaps.append("zone_or_direction_unusable_for_state")

    armed_exec = exec_to_grid(src.get("armed_bar"), offset)
    proof_exec_value = src.get("proof_bar")
    proof_exec = exec_to_grid(proof_exec_value, offset)
    pb_arm = proof_before_arm(src.get("armed_bar"), proof_exec_value)
    if pb_arm == "":
        gaps.append("missing_arm_or_proof_bar")

    width = None
    atr_proof = None
    gap_proof = gap_vs(bars, limit, proof_exec)
    atr_proof = gap_proof["atr"]
    if gap_proof["reason"]:
        gaps.append(f"proof:{gap_proof['reason']}")
    if low not in (None, "") and high not in (None, "") and atr_proof:
        width = (float(high) - float(low)) / float(atr_proof)
    elif low not in (None, "") and high not in (None, ""):
        gaps.append("atr_unavailable_for_zone_width")

    gap_arm = gap_vs(bars, limit, armed_exec)
    if gap_arm["reason"]:
        gaps.append(f"arm:{gap_arm['reason']}")

    shifted = gap_vs(bars, limit, exec_to_grid(proof_exec_value, 0) if
                     proof_exec_value not in (None, "") else None)
    shifted_gap_atr = shifted["gap_atr"]  # disclosure only, never a decision

    row.update({
        "episode_id": src.get("episode_id", ""),
        "population": 1,
        "direction": src.get("direction", ""),
        "trigger": src.get("proof_trigger", ""),
        "detection_tf": src.get("detection_tf", ""),
        "is_m8": src.get("is_m8", ""),
        "route_id": src.get("route_id", ""),
        "arm_kind": "product",
        "matched_fill": "True" if _truthy(src.get("matched_fill")) else "False",
        "armed_bar_exec": src.get("armed_bar", ""),
        "proof_bar_exec": proof_exec_value if proof_exec_value not in (None, "") else "",
        "presentation_bar_exec": "",
        "armed_bar_grid": armed_exec if armed_exec is not None else "",
        "proof_bar_grid": proof_exec if proof_exec is not None else "",
        "presentation_bar_grid": "",
        "arm_proof_bars": (int(src["armed_bar"]) - int(proof_exec_value)
                           if pb_arm != "" else ""),
        "proof_presentation_bars": "",
        "proof_before_arm": pb_arm,
        "zone_source": src.get("zone_source", ""),
        "zone_low": low if low not in (None, "") else "",
        "zone_high": high if high not in (None, "") else "",
        "zone_width_atr": width if width is not None else "",
        "limit": limit,
        "limit_source": limit_source,
        "entry_vs_zone": state,
        "atr_proof": atr_proof if atr_proof is not None else "",
        "atr_presentation": "",
        "atr_arm": gap_arm["atr"] if gap_arm["atr"] is not None else "",
        "gap_price_proof": gap_proof["gap_price"] if gap_proof["gap_price"] is not None else "",
        "gap_atr_proof": gap_proof["gap_atr"] if gap_proof["gap_atr"] is not None else "",
        "close_proof": gap_proof["close"] if gap_proof["close"] is not None else "",
        "gap_price_presentation": "",
        "gap_atr_presentation": "",
        "close_presentation": "",
        "gap_price_arm": gap_arm["gap_price"] if gap_arm["gap_price"] is not None else "",
        "gap_atr_arm": gap_arm["gap_atr"] if gap_arm["gap_atr"] is not None else "",
        "close_arm": gap_arm["close"] if gap_arm["close"] is not None else "",
        "gap_atr_proof_shiftedframe": shifted_gap_atr if shifted_gap_atr is not None else "",
        "mech_zone_edge_far": is_mech({
            "limit": limit if limit not in (None, "") else None,
            "gap_atr_proof": gap_proof["gap_atr"],
            "entry_vs_zone": state,
            "direction": direction,
            "zone_low": low,
            "zone_high": high,
        }),
        "r4_failed_only": p2_flag(src),
        "data_gap": "True" if gaps else "False",
        "data_gap_reasons": ";".join(gaps),
    })
    return row


def p2_flag(src: dict) -> str:
    """Admission R4-only stratum flag (r1/r2/r3 pass, r4 fail, no gaps)."""
    if (str(src.get("population")) != "1"
            or _truthy(src.get("data_gap"))):
        return "False"
    if (src.get("r1_thesis") != "PASS" or src.get("r2_proof") != "PASS"
            or src.get("r3_timing") != "PASS"
            or src.get("r4_location") != "FAIL"):
        return "False"
    return "True"


def build_p0_row(cand: dict, episode: dict | None, armed_rec: dict | None,
                 offset: int, bars) -> dict:
    """One study row per product route (frozen near-miss candidate)."""
    row = {f: "" for f in ROW_FIELDS}
    gaps: list[str] = []

    direction = ram.parse_direction(cand.get("direction"))
    low, high = cand.get("zone_low"), cand.get("zone_high")
    limit = cand.get("entry")
    limit_source = "recorded_route_entry" if limit not in (None, "") else ""
    if limit in (None, ""):
        gaps.append("missing_limit")
    state = entry_vs_zone_state(limit, low, high, direction)
    if state == "DATA_GAP" and limit not in (None, ""):
        gaps.append("zone_or_direction_unusable_for_state")

    first_present_exec = cand.get("first_present_bar")
    proof_exec = exec_to_grid(first_present_exec, offset)
    # The route's first presentation IS its proof reference in P0
    # (disclosed); the closed measure's presentation columns are unused.
    gap_proof = gap_vs(bars, limit, proof_exec)
    if gap_proof["reason"]:
        gaps.append(f"proof:{gap_proof['reason']}")
    atr_proof = gap_proof["atr"]

    armed_value = None
    rec_value = (armed_rec or {}).get("armed_bar")
    if episode is not None and episode.get("armed_bar_exec") not in (None, ""):
        armed_value = int(episode["armed_bar_exec"])
        rec = rec_value if rec_value not in (None, "") else None
        if rec is not None and int(rec) != armed_value:
            raise SystemExit(f"policy: armed-bar disagreement for "
                             f"{cand['route_id']} "
                             f"(episode {armed_value} vs record {rec})")
    elif rec_value not in (None, ""):
        armed_value = int(rec_value)
    else:
        gaps.append("missing_armed_bar")
    armed_exec = exec_to_grid(armed_value, offset)
    gap_arm = gap_vs(bars, limit, armed_exec)
    if gap_arm["reason"]:
        gaps.append(f"arm:{gap_arm['reason']}")

    width = None
    if low not in (None, "") and high not in (None, "") and atr_proof:
        width = (float(high) - float(low)) / float(atr_proof)
    elif low not in (None, "") and high not in (None, ""):
        gaps.append("atr_unavailable_for_zone_width")

    pb_arm = proof_before_arm(armed_value, first_present_exec)
    if pb_arm == "":
        gaps.append("missing_arm_or_proof_bar")

    row.update({
        "episode_id": cand["route_id"],
        "population": 0,
        "direction": cand.get("direction", ""),
        "trigger": cand.get("trigger", ""),
        "detection_tf": cand.get("detection_tf", ""),
        "is_m8": cand.get("is_m8", ""),
        "route_id": cand.get("route_id", ""),
        "arm_kind": cand.get("arm", ""),
        "matched_fill": "True" if _truthy(cand.get("filled")) else "False",
        "armed_bar_exec": armed_value if armed_value is not None else "",
        "proof_bar_exec": first_present_exec if first_present_exec not in (None, "") else "",
        "presentation_bar_exec": first_present_exec if first_present_exec not in (None, "") else "",
        "armed_bar_grid": armed_exec if armed_exec is not None else "",
        "proof_bar_grid": proof_exec if proof_exec is not None else "",
        "presentation_bar_grid": proof_exec if proof_exec is not None else "",
        "arm_proof_bars": (armed_value - int(first_present_exec)
                           if pb_arm != "" else ""),
        "proof_presentation_bars": 0 if first_present_exec not in (None, "") else "",
        "proof_before_arm": pb_arm,
        "zone_source": "route_record",
        "zone_low": low if low not in (None, "") else "",
        "zone_high": high if high not in (None, "") else "",
        "zone_width_atr": width if width is not None else "",
        "limit": limit,
        "limit_source": limit_source,
        "entry_vs_zone": state,
        "atr_proof": atr_proof if atr_proof is not None else "",
        "atr_presentation": atr_proof if atr_proof is not None else "",
        "atr_arm": gap_arm["atr"] if gap_arm["atr"] is not None else "",
        "gap_price_proof": gap_proof["gap_price"] if gap_proof["gap_price"] is not None else "",
        "gap_atr_proof": gap_proof["gap_atr"] if gap_proof["gap_atr"] is not None else "",
        "close_proof": gap_proof["close"] if gap_proof["close"] is not None else "",
        "gap_price_presentation": gap_proof["gap_price"] if gap_proof["gap_price"] is not None else "",
        "gap_atr_presentation": gap_proof["gap_atr"] if gap_proof["gap_atr"] is not None else "",
        "close_presentation": gap_proof["close"] if gap_proof["close"] is not None else "",
        "gap_price_arm": gap_arm["gap_price"] if gap_arm["gap_price"] is not None else "",
        "gap_atr_arm": gap_arm["gap_atr"] if gap_arm["gap_atr"] is not None else "",
        "close_arm": gap_arm["close"] if gap_arm["close"] is not None else "",
        "gap_atr_proof_shiftedframe": "",
        "mech_zone_edge_far": is_mech({
            "limit": limit if limit not in (None, "") else None,
            "gap_atr_proof": gap_proof["gap_atr"],
            "entry_vs_zone": state,
            "direction": direction,
            "zone_low": low,
            "zone_high": high,
        }),
        "r4_failed_only": "",
        "data_gap": "True" if gaps else "False",
        "data_gap_reasons": ";".join(gaps),
    })
    return row


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def ga(row, field) -> float | None:
    v = row.get(field)
    return None if v in (None, "") else float(v)


def gap_vals(rows) -> list[float]:
    return [float(r["gap_atr_proof"]) for r in rows
            if r["gap_atr_proof"] not in (None, "")]


def aggregate(p0: list[dict], p1: list[dict], reactive: list[dict]) -> dict:
    stats: dict = {}

    stats["distribution_p0_gap_atr_proof"] = dist_summary(gap_vals(p0))
    stats["distribution_p1_gap_atr_proof"] = dist_summary(gap_vals(p1))
    stats["distribution_p0_gap_price_proof"] = dist_summary(
        [ga(r, "gap_price_proof") or 0 for r in p0
         if r["gap_price_proof"] != ""])
    stats["distribution_p1_gap_price_proof"] = dist_summary(
        [float(r["gap_price_proof"]) for r in p1
         if r["gap_price_proof"] != ""])
    stats["distribution_p1_gap_atr_arm"] = dist_summary(
        [float(r["gap_atr_arm"]) for r in p1 if r["gap_atr_arm"] != ""])
    stats["pct_p1_gap_atr_proof_le_1"] = share_le(gap_vals(p1),
                                                  GAP_ATR_NEAR)
    stats["p1_gap_complete_rate"] = (
        len(gap_vals(p1)) / len(p1)) if p1 else None

    # instrument disclosure: shifted-frame gap (closed measure's frame) ---- #
    both = [(ga(r, "gap_atr_proof"), ga(r, "gap_atr_proof_shiftedframe"))
            for r in p1]
    both = [(t, s) for t, s in both if t is not None and s is not None]
    stats["disclosure_shiftedframe_p1"] = {
        "n_both": len(both),
        "pct_true_le_1": share_le([t for t, _ in both], GAP_ATR_NEAR),
        "pct_shifted_le_1": share_le([s for _, s in both], GAP_ATR_NEAR),
        "n_side_changes": sum(1 for t, s in both
                              if (t <= GAP_ATR_NEAR) != (s <= GAP_ATR_NEAR)),
        "purpose": ("instrument residual quantification only -- the "
                    "closed measure's geometry frame; no study decision "
                    "or admission verdict flows from it"),
    }

    # strata ---------------------------------------------------------------- #
    stats["strata_limit_source_p1"] = strata(p1, "limit_source",
                                             "gap_atr_proof")
    stats["strata_trigger_class_p1"] = strata(
        [{"trigger_class": "F" if r["trigger"] == "F" else "other",
          "gap_atr_proof": r["gap_atr_proof"]} for r in p1],
        "trigger_class", "gap_atr_proof")
    stats["strata_proof_before_arm_p1"] = strata(p1, "proof_before_arm",
                                                 "gap_atr_proof")
    stats["strata_zone_source_p1"] = strata(p1, "zone_source",
                                            "gap_atr_proof")

    # P2 report stratum ------------------------------------------------------#
    stats["p2_stratum_n"] = sum(1 for r in p1 if r["r4_failed_only"] == "True")

    # zone width vs mechanism (hypothesis H5 input) -------------------------- #
    mech_rows = [r for r in p1 if r["mech_zone_edge_far"] != "GAP"]
    on_far = [r for r in mech_rows if r["mech_zone_edge_far"] == "on_edge_far"]
    not_far = [r for r in mech_rows
               if r["mech_zone_edge_far"] in ("near", "off_edge")]
    stats["zone_width_by_mech_p1"] = {
        "on_edge_far": dist_summary([ga(r, "zone_width_atr")
                                     or 0 for r in on_far
                                     if r["zone_width_atr"] != ""]),
        "not_on_edge_far": dist_summary([ga(r, "zone_width_atr")
                                         or 0 for r in not_far
                                         if r["zone_width_atr"] != ""]),
    }

    # mechanisms -------------------------------------------------------------#
    stats["mechanism_counts"] = {
        "m1_zone_edge_far_p1": len(on_far),
        "m1_near_p1": sum(1 for r in mech_rows
                          if r["mech_zone_edge_far"] == "near"),
        "m1_off_edge_p1": sum(1 for r in mech_rows
                              if r["mech_zone_edge_far"] == "off_edge"),
        "m1_gap_p1": sum(1 for r in p1
                         if r["mech_zone_edge_far"] == "GAP"),
        "m2_reanchor_p0_routes_on_edge": sum(
            1 for r in p0 if r["entry_vs_zone"] == "on_edge"),
        "m2_p0_not_evaluable": sum(1 for r in p0
                                   if r["entry_vs_zone"] != "on_edge"),
        "m3_no_return_20_citation": M3_PUBLISHED_R3_COUNT,
        "m4_proof_after_arm_p1": sum(1 for r in p1
                                     if r["proof_before_arm"] == "True"),
    }
    stats["mech_share_p1"] = share(mech_rows,
                                   lambda r: r["mech_zone_edge_far"] == "on_edge_far")
    stats["mech_share_denominator"] = len(mech_rows)
    life_rows = [r for r in p1 if r["proof_before_arm"] != ""]
    stats["life_share_p1"] = share(life_rows,
                                   lambda r: r["proof_before_arm"] == "True")
    stats["life_share_denominator"] = len(life_rows)
    stats["citation_crosschecks"] = {
        "m3_published": M3_PUBLISHED_R3_COUNT,
        "m3_recomputed": False,          # never recomputed by this study
        "m4_expected_64": M4_PUBLISHED_R1_COUNT,
        "m4_observed": stats["mechanism_counts"]["m4_proof_after_arm_p1"],
        "m4_matches_published": (
            stats["mechanism_counts"]["m4_proof_after_arm_p1"]
            == M4_PUBLISHED_R1_COUNT),
        "reactive_pop_split_respected": {
            "p1": len(p1), "asserted": EXPECTED_P1,
        },
    }

    # control fills -----------------------------------------------------------#
    stats["control_fills"] = [
        {"route_id": r["route_id"], "direction": r["direction"],
         "trigger": r["trigger"], "armed_bar_exec": r["armed_bar_exec"],
         "proof_bar_exec": r["proof_bar_exec"],
         "proof_before_arm": r["proof_before_arm"],
         "entry": r["limit"], "zone_low": r["zone_low"],
         "zone_high": r["zone_high"],
         "zone_width_atr": r["zone_width_atr"],
         "gap_price_proof": r["gap_price_proof"],
         "gap_atr_proof": r["gap_atr_proof"],
         "gap_atr_arm": r["gap_atr_arm"],
         "entry_vs_zone": r["entry_vs_zone"]}
        for r in p0 if r["matched_fill"] == "True"]

    stats["dominant_mechanism"] = classify_family(
        stats["mech_share_p1"], stats["life_share_p1"],
        stats["p1_gap_complete_rate"])
    stats["verdict_family"] = stats["dominant_mechanism"]
    return stats


# --------------------------------------------------------------------------- #
# Loaders / main
# --------------------------------------------------------------------------- #
def load_inputs() -> dict:
    reactive_csv = (REPO_ROOT / "06_RESEARCH" / "results"
                    / "reactive_admission_measure" / "rows.csv")
    cand_csv = (REPO_ROOT / "06_RESEARCH" / "results"
                / "near_miss_counterfactual" / "candidates.csv")
    armed_json = (REPO_ROOT / "06_RESEARCH" / "results"
                  / "poi_confirm_entry_path" / "replay_run1"
                  / "armed_records.json")
    for path in (reactive_csv, cand_csv, armed_json):
        if not path.exists():
            raise SystemExit(f"required input missing: {path}")
    with reactive_csv.open(encoding="utf-8", newline="") as f:
        reactive = list(csv.DictReader(f))
    with cand_csv.open(encoding="utf-8", newline="") as f:
        candidates = list(csv.DictReader(f))
    armed_records = json.loads(armed_json.read_text(encoding="utf-8"))
    episodes = {}
    for r in reactive:
        poi = r.get("armed_poi_id") or ""
        if poi and poi not in episodes:
            episodes[poi] = r
    return {"reactive": reactive, "candidates": candidates,
            "armed_records": armed_records, "episodes": episodes}


HYPOTHESES = [
    {"id": "H1",
     "claim": "MECHANICAL-ANCHOR: the FR-3.1 rule (LONG->zone_high / "
              "SHORT->zone_low) places every candidate's limit on the "
              "proximal edge reached on the IMPULSE leg, so on the "
              "retracement the limit starts far from the true proof close "
              "whenever the zone is displaced from price; count-driven "
              "evidence is the M1 share.",
     "support": "M1 share vs its near/off_edge companions; all P0 route "
                "entries sit exactly on_edge.",
     "refute": "a material share of rows with inside-zone limits that "
               "still show gap_atr > 1 at the true proof bar.",
     "NOT implemented in this task": True},
    {"id": "H2",
     "claim": "LIFECYCLE: shares of theses arm after their first "
              "coincident proof, so the reactive-eligibility question "
              "rarely coincides with the geometry question; evidence is "
              "the proof_before_arm share (publication-expected 64/268).",
     "support": "M4 count matches the published R1 count.",
     "refute": "M4 near zero or armed-before-proof rows uniformly "
               "passing the same geometry guard.",
     "NOT implemented in this task": True},
    {"id": "H3",
     "claim": "The gap is not lost data: the frozen artifacts carry "
              "limit/zone/ATR for essentially the whole P1 population, "
              "so any representation redesign has readable inputs.",
     "support": "p1_gap_complete_rate >= 0.70.",
     "refute": "gap completeness below the 0.70 gate.",
     "NOT implemented in this task": True},
    {"id": "H4",
     "claim": "DISCLOSURE: the closed admission measure's market "
              "geometry (R3/R4/R5 windows, ATR columns) was evaluated on "
              "grid indexes 6018 slots earlier than the artifact "
              "timestamps it published -- a frame residual "
              "(presentation bars in the warm-up; shifted-frame "
              "side-changes measured here). Resolving it needs its own "
              "dated re-run decision; this study does not re-open the "
              "verdict.",
     "support": "pct_true_le_1 vs pct_shifted_le_1 and side-changes in "
                "this study's disclosure columns.",
     "refute": "zero side changes between frames and presentation "
               "columns matching true-frame indexes.",
     "NOT implemented in this task": True},
    {"id": "H5",
     "claim": "Zone width in ATR conditions the far-gap: wide zones "
              "(relative to ATR) accompany on_edge_far rows while narrow "
              "zones do not -- mid-zone placement would be a geometry "
              "change, not a threshold tightening.",
     "support": "zone_width_by_mech_p1: width distribution of on_edge_far "
                "rows exceeds that of non-far rows.",
     "refute": "width distributions indistinguishable between the two "
               "strata.",
     "NOT implemented in this task": True},
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", default=None,
                        help="override artifact directory (determinism runs)")
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir) if args.out_dir else OUT_DIR

    t0 = time.perf_counter()
    inputs = load_inputs()
    assert len(inputs["reactive"]) == EXPECTED_COINCIDENT
    bars, offset = ram.load_series()
    assert offset == ram.EXPECTED_WARMUP_OFFSET, offset

    p1_srcs = [r for r in inputs["reactive"]
               if str(r.get("population")) == "1"]
    assert len(p1_srcs) == EXPECTED_P1, len(p1_srcs)

    # P1 rows (frozen artifacts, true-frame conversion asserted).
    p1_rows = [build_p1_row(src, offset, bars) for src in p1_srcs]

    # Frame assertion for P0: first_present ts must match the true grid bar
    # exactly for every route (verified, never assumed).
    for cand in inputs["candidates"]:
        ts = datetime.fromisoformat(cand["first_present_ts"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        grid_bar = exec_to_grid(int(cand["first_present_bar"]), offset)
        assert grid_bar < len(bars), (cand["route_id"], grid_bar)
        assert bars[grid_bar].timestamp == ts, (
            cand["route_id"], bars[grid_bar].timestamp, ts)

    p0_rows = [
        build_p0_row(cand, inputs["episodes"].get(cand["poi_id"]),
                     inputs["armed_records"].get(cand["poi_id"]),
                     offset, bars)
        for cand in inputs["candidates"]]
    assert len(p0_rows) == EXPECTED_P0, len(p0_rows)

    stats = aggregate(p0_rows, p1_rows, inputs["reactive"])

    meta = {
        "banner": BANNER,
        "logic_changed": "NO",
        "study": "entry representation -- why limits sit far from market",
        "window": {
            "grid": "admission measure's Step-3 M5 grid "
                    f"({len(bars)} bars)",
            "warmup_offset": offset,
        },
        "frozen": {
            "gap_reference_primary": "close of TRUE proof bar "
                                     "(grid[proof_bar_exec + offset]); "
                                     "P0 uses its own first_present_bar "
                                     "(ts-asserted) in the same frame",
            "secondary_refs": ["true arm bar close "
                               "(grid[armed_bar_exec + offset])",
                               "P0 route first presentation "
                               "(same as its proof ref)"],
            "atr_convention": "SMA(TR,14) ending AT the true bar "
                              "(admission measure convention, recomputed)",
            "limit_source_rule": "recorded route entry else FR-3.1 "
                                 "proximal edge (LONG->zone_high, "
                                 "SHORT->zone_low)",
            "mech_definition": f"limit exactly on proximal edge AND "
                               f"gap_atr_proof > {GAP_ATR_NEAR}",
            "family_rule": f"complete<{COMPLETABLE_MIN} -> INCONCLUSIVE; "
                           f"both>={BOTH_SHARE} or tie<={TIE_MARGIN} -> "
                           f"BOTH; both<{NO_MASS_SHARE} -> INCONCLUSIVE; "
                           "else dominant",
            "bar_frames": "artifact bar columns are exec-frame; grid "
                          "index = exec + offset (ts-verified)",
            "closed_measure_columns_not_reused": ["presentation_bar",
                                                  "presentation_ts"],
            "fail_closed": "missing field -> gap columns empty + DATA_GAP "
                           "(prices never invented)",
        },
        "stats": stats,
        "hypotheses": HYPOTHESES,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_path = out_dir / "rows.csv"
    with rows_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(ROW_FIELDS)
        for row in p0_rows + p1_rows:
            writer.writerow([row.get(k, "") if row.get(k) is not None else ""
                             for k in ROW_FIELDS])
    summary_path = out_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str, ensure_ascii=False)

    rows_sha = hashlib.sha256(rows_path.read_bytes()).hexdigest()
    sum_sha = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    print(f"[entry-rep] p0={len(p0_rows)} p1={len(p1_rows)} "
          f"complete={stats['p1_gap_complete_rate']:.3f} "
          f"frac_le1={stats['pct_p1_gap_atr_proof_le_1']:.3f} "
          f"mech={stats['mech_share_p1']:.3f} "
          f"life={stats['life_share_p1']:.3f} "
          f"family={stats['verdict_family']}", flush=True)
    print(f"[entry-rep] runtime={time.perf_counter() - t0:.1f}s", flush=True)
    print(f"[entry-rep] sha rows={rows_sha}", flush=True)
    print(f"[entry-rep] sha summary={sum_sha}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
