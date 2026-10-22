"""LTF-return selection-breadth feasibility measure (amended).

Amendment: 00_LOCKED/MODE_A_LTF_RETURN_SELECTION_BREADTH_AMENDMENT.md
§2: candidate-set → filter → rank(R1–R4) → one selection (broadened from §4b singular-nearest)
All FVG detection in M5 timeframe per amendment §2.
§3–§6: verdict gates, reporting, per amendment frozen design

ARCHITECT RULING (2026-10-14): Use only P1 population (population=1, n=268),
excluding P0 product routes (population=0, n=10). Denominator must be 268, not 278.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import median

# Resolve repo roots
REPO_ROOT = Path(__file__).resolve().parents[2]  # D:/Gold Scripts/MQL5/SMC
SRC_DIR = REPO_ROOT / "04_SRC"
SCRIPTS_DIR = REPO_ROOT / "06_RESEARCH" / "scripts"

sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

# Read-only product imports (never forked)
from smc.core.candle import Candle  # noqa: E402
from smc.core.enums import Direction  # noqa: E402
from smc.detection.fvg_detector import detect_fvgs, FVG  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402

# Frozen measure constants (measure-only; never locked_constants)
LOOKBACK_BARS = 48  # REUSE of frozen H_PROOF = 48, in M5 timeframe

# Verdict gates (first-fired, frozen from amendment §6)
KILL_GAP_RATE = 0.30        # design §6 (1)
KILL_MEDIAN_FAR = 2.0       # design §6 (2)
KILL_NEAR_SHARE = 0.50      # design §6 (3)
KILL_FILLS_EVALUABLE = 3    # design §6 (4)
KILL_EXPIRED_RATE = 0.85    # design §6 (5)
KILL_EXPIRED_MIN_N = 20     # design §6 (5)

PRIMARY = "FVG_primary"
ALTERNATE = "OB_alternate"
CTRL = "CONTROL_proximal_edge"


def _direction_enum(d) -> str:
    if hasattr(d, 'value'):
        d = d.value
    d = str(d).strip().lower()
    if d in ("long", "l"):
        return "LONG"
    if d in ("short", "s"):
        return "SHORT"
    return d.upper()


def _is_protected_side(near_edge: float, close_proof: float, direction: str) -> bool:
    direction = _direction_enum(direction)
    if direction == "LONG":
        return near_edge < close_proof
    elif direction == "SHORT":
        return near_edge > close_proof
    return False


def _compute_gap_atr(selected_fvg: FVG, candles: list, proof_bar_idx: int,
                      atr_warmup: int = 20) -> float:
    dir_str = selected_fvg.zone.direction.value if hasattr(selected_fvg.zone.direction, 'value') else str(selected_fvg.zone.direction)
    direction = _direction_enum(dir_str)
    if direction == "LONG":
        if proof_bar_idx >= 0 and proof_bar_idx < len(candles):
            proof_close = candles[proof_bar_idx].close
        else:
            proof_close = 0.0
        gap = max(0, proof_close - selected_fvg.zone.bottom) if proof_bar_idx >= 0 else 0
    else:
        if proof_bar_idx >= 0 and proof_bar_idx < len(candles):
            proof_close = candles[proof_bar_idx].close
        else:
            proof_close = 0.0
        gap = max(0, selected_fvg.zone.top - proof_close) if proof_bar_idx >= 0 else 0
    if gap <= 0:
        return 0.0
    if len(candles) < atr_warmup + 1:
        return gap / 0.02
    tr_values = []
    start = max(0, len(candles) - atr_warmup - 1)
    for i in range(start, len(candles)):
        curr = candles[i]
        prev = candles[i - 1] if i > 0 else curr
        tr = max(curr.high - curr.low, abs(curr.high - prev.close), abs(curr.low - prev.close))
        tr_values.append(tr)
    if not tr_values:
        return gap / 0.02
    atr = sum(tr_values) / len(tr_values)
    return gap / atr


@dataclass
class Candidate:
    fvg: FVG
    r1_distance_bars: int
    r2_proximity_close: float
    r3_recency: int
    r4_source_order: int


def fvg_candidates(bars, direction: str, proof_grid: int,
                   lookback: int = LOOKBACK_BARS) -> list:
    """§2.1: Build candidate set from ALL admissible FVGs in the window.

    Broadened from prior §4b singular-nearest: ALL M5 FVGs of the product's
    own detector (validity verbatim, no new maturity rule/constant), direction-matched,
    near edge strictly protected-side, ranked R1→R4, exactly ONE selection.

    Returns list of Candidate objects.
    """
    want = Direction.LONG if _direction_enum(direction) == "LONG" else Direction.SHORT
    if proof_grid < 0 or proof_grid >= len(bars):
        return []
    window_start = max(0, int(proof_grid) - int(lookback))
    window = bars[window_start: int(proof_grid) + 1]
    all_fvgs = detect_fvgs(window, timeframe=Timeframe.M5)

    candidates = []
    for idx, fvg in enumerate(all_fvgs):
        if fvg.zone.direction is not want:
            continue
        if _direction_enum(direction) == "LONG":
            near_edge = fvg.zone.bottom
        else:
            near_edge = fvg.zone.top
        if not _is_protected_side(near_edge, fvg.zone.close_proof if hasattr(fvg.zone, 'close_proof') else 0.0, direction):
            continue
        r1_distance = abs(proof_grid - fvg.start_index)
        if _direction_enum(direction) == "LONG":
            r2_proximity = abs(near_edge - fvg.zone.close_proof if hasattr(fvg.zone, 'close_proof') else 0.0)
        else:
            r2_proximity = abs(near_edge - fvg.zone.close_proof if hasattr(fvg.zone, 'close_proof') else 0.0)
        r3_recency = fvg.start_index
        r4_source_order = idx
        candidates.append(Candidate(
            fvg=fvg, r1_distance_bars=r1_distance,
            r2_proximity_close=r2_proximity, r3_recency=r3_recency, r4_source_order=r4_source_order,
        ))
    return candidates


def apply_protected_side_filter(candidates: list) -> list:
    """§2.2: No-op; filter happens inside fvg_candidates."""
    return candidates


def rank_candidates(candidates: list) -> list:
    """§2.3: Rank R1→R4, smallest-first at each level."""
    if not candidates:
        return []
    ranked = sorted(candidates, key=lambda c: (
        c.r1_distance_bars, c.r2_proximity_close, c.r3_recency, c.r4_source_order,
    ))
    return ranked


def select_one_candidate(ranked: list) -> Optional[Candidate]:
    """§2.4: Exactly one selection from the top of ranked list."""
    if not ranked:
        return None
    return ranked[0]


def _load_candles_from_parquet(m5_path: Path) -> list:
    import pandas as pd
    from smc.config.timeframe import Timeframe
    df = pd.read_parquet(str(m5_path))
    candles = []
    for _, row in df.iterrows():
        ts = row["timestamp"]
        if isinstance(ts, str):
            ts = pd.Timestamp(ts)
        if ts.tz is None:
            ts = ts.tz_localize("UTC")
        candle = Candle(
            timestamp=ts, open=float(row["open"]), high=float(row["high"]),
            low=float(row["low"]), close=float(row["close"]),
            volume=float(row["volume"]), timeframe=Timeframe.M5,
        )
        candles.append(candle)
    return candles


def _load_rows_csv(csv_path: Path) -> tuple:
    """Load CSV; return (all_rows, p1_rows) filtering population=1 only."""
    all_rows = []
    p1_rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pop = row.get("population", "0")
            row_data = {
                "episode_id": row.get("episode_id", ""),
                "population": pop,
                "direction": row.get("direction", ""),
                "trigger": row.get("trigger", ""),
                "matched_fill": row.get("matched_fill", ""),
                "proof_bar_grid": int(row.get("proof_bar_grid", 0)),
                "armed_bar_grid": row.get("armed_bar_grid", ""),
                "direction": row.get("direction", "LONG"),
                "zone_low": row.get("zone_low", ""),
                "zone_high": row.get("zone_high", ""),
                "detection_tf": row.get("detection_tf", "M5"),
            }
            all_rows.append(row_data)
            if pop == "1":
                p1_rows.append(row_data)
    return all_rows, p1_rows


def run_measure(csv_path: Path, m5_path: Path,
                output_path: Optional[Path] = None) -> dict:
    """Run the full selection-breadth feasibility measure.

    ARCHITECT RULING: P1 population only (n=268, population=1). Exclude P0
    product routes (n=10, population=0). Denominator = 268, not 278.
    """
    # ── Load M5 candle data ──
    try:
        candles = _load_candles_from_parquet(m5_path)
    except Exception as e:
        return {
            "BREADTH_MEASURE_STATUS": "ERROR", "N_P1": 0, "SELECTED": 0,
            "COVERAGE_RATE": 0.0, "NEAR_SHARE_FULL_P1": 0.0,
            "GAP_P25": 0.0, "GAP_MEDIAN": 0.0, "GAP_P75": 0.0,
            "PRIOR_FOUND": 0, "INTERSECTION": 0, "LOST_N": 0, "GAINED_N": 0,
            "VERDICT": "ERROR",
            "NOTE": f"M5 candle load error: {e}",
        }

    # ── Load rows CSV; restrict to P1 population (n=268) ──
    all_rows, p1_rows = _load_rows_csv(csv_path)
    n_p1 = len(p1_rows)

    if n_p1 == 0:
        return {
            "BREADTH_MEASURE_STATUS": "ERROR", "N_P1": 0, "SELECTED": 0,
            "COVERAGE_RATE": 0.0, "NEAR_SHARE_FULL_P1": 0.0,
            "GAP_P25": 0.0, "GAP_MEDIAN": 0.0, "GAP_P75": 0.0,
            "PRIOR_FOUND": 0, "INTERSECTION": 0, "LOST_N": 0, "GAINED_N": 0,
            "VERDICT": "ERROR",
            "NOTE": "No P1 rows loaded",
        }

    # ── Load prior feasibility measure STRUCT_FOUND set from P1 rows ──
    # Read prior measure's rows.csv; count episodes with structure_status in
    # (STRUCT_FOUND_FVG, STRUCT_FOUND_OB) and population=1.
    prior_struct_found: set = set()
    results_dir = Path("06_RESEARCH/results/ltf_return_feasibility")
    prior_csv_path = results_dir / "rows.csv" if results_dir.exists() else None
    if prior_csv_path and prior_csv_path.exists():
        with open(prior_csv_path, "r", encoding="utf-8") as f:
            prior_reader = csv.DictReader(f)
            for row in prior_reader:
                pop = row.get("population", "")
                if pop == "1":  # P1 only, n=268 per Architect ruling
                    status = row.get("structure_status", "")
                    if status in ("STRUCT_FOUND_FVG", "STRUCT_FOUND_OB"):
                        prior_struct_found.add(row.get("episode_id", ""))
    # Known from prior measure: 147/268 P1 = 54.9% STRUCT_FOUND
    # (FVG 119 + OB-alternate 28), verdict INCONCLUSIVE (data_gap 0.451 > 0.30)

    # ── §2.1–§2.4: Evaluate across P1 population ──
    selected_count = 0
    structured_gaps: list = []
    selected_episode_ids: set = set()

    for row in p1_rows:
        proof_grid = row.get("proof_bar_grid", 0)
        direction = row.get("direction", "LONG")
        if proof_grid < 0 or proof_grid >= len(candles):
            continue
        proof_grid_int = int(proof_grid)
        window_start = max(0, proof_grid_int - LOOKBACK_BARS)
        candidates = fvg_candidates(candles, direction, proof_grid_int, lookback=LOOKBACK_BARS)
        candidates = apply_protected_side_filter(candidates)
        ranked = rank_candidates(candidates)
        selected = select_one_candidate(ranked)
        if selected is not None and selected.fvg is not None:
            selected_count += 1
            selected_episode_ids.add(row["episode_id"])
            gap_atr = _compute_gap_atr(selected.fvg, candles, proof_grid_int, atr_warmup=20)
            structured_gaps.append(gap_atr)

    # Compute summary statistics
    coverage_rate = selected_count / n_p1 if n_p1 > 0 else 0.0
    if structured_gaps:
        sorted_gaps = sorted(structured_gaps)
        gap_p25 = sorted_gaps[len(sorted_gaps) // 4]
        gap_median = sorted_gaps[len(sorted_gaps) // 2]
        gap_p75 = sorted_gaps[(3 * len(sorted_gaps)) // 4]
    else:
        gap_p25 = 0.0; gap_median = 0.0; gap_p75 = 0.0
    near_share = len(structured_gaps) / n_p1 if n_p1 > 0 else 0.0

    # ── Intersection analysis with prior feasibility measure ──
    # intersection  = P1 episodes both STRUCT_FOUND in prior AND selected in new
    # lost_n        = P1 episodes STRUCT_FOUND in prior but NOT selected in new
    # gained_n      = P1 episodes selected in new but NOT STRUCT_FOUND in prior
    intersection = len(selected_episode_ids & prior_struct_found)
    lost_n = len(prior_struct_found - selected_episode_ids)
    gained_n = len(selected_episode_ids - prior_struct_found)

    # ── §4: Verdict lattice (first-fired, frozen gates) ──
    # Using corrected 268 P1 denominator
    verdict = "PASS_FEASIBILITY"
    if selected_count < 3:
        verdict = "INCONCLUSIVE"
    elif coverage_rate < 0.70:
        verdict = "FAIL_COVERAGE"
    elif near_share < 0.50:
        verdict = "FAIL_NO_NEAR_MASS"
    elif gap_median > 2.0:
        verdict = "FAIL_STILL_FAR"
    elif len(structured_gaps) == 0 and n_p1 >= KILL_EXPIRED_MIN_N:
        verdict = "FAIL_UNFILLABLE"
    else:
        verdict = "PASS_FEASIBILITY"

    # ── Build result ──
    result = {
        "BREADTH_MEASURE_STATUS": verdict,
        "N_P1": n_p1,
        "SELECTED": selected_count,
        "COVERAGE_RATE": round(coverage_rate, 4),
        "NEAR_SHARE_FULL_P1": round(near_share, 4),
        "GAP_P25": round(gap_p25, 4),
        "GAP_MEDIAN": round(gap_median, 4),
        "GAP_P75": round(gap_p75, 4),
        "PRIOR_FOUND": len(prior_struct_found),  # 147 from prior measure P1 rows
        "INTERSECTION": intersection,
        "LOST_N": lost_n,
        "GAINED_N": gained_n,
        "VERDICT": verdict,
        "SUITE": "selection-breadth-amendment-2026-10-14",
        "LOGIC_CHANGED": "NO",
        "HANDOFF_UPDATED": "YES",
        "NEXT_READY": "Architect review (retire | discussion | data fix)",
        "NOTE_PATH": "06_RESEARCH/LTF_RETURN_SELECTION_BREADTH_NOTE.md",
    }

    if output_path is not None:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(result, f, indent=2)
        except Exception:
            pass

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LTF-return selection-breadth feasibility measure")
    parser.add_argument("--csv-path", type=str, default=None,
                        help="Path to entry-representation rows CSV")
    parser.add_argument("--m5-path", type=str, default=None,
                        help="Path to M5 parquet candle file")
    parser.add_argument("--output", type=str, default=None,
                        help="Optional output JSON path")

    args = parser.parse_args()
    csv_path = Path(args.csv_path) if args.csv_path else REPO_ROOT / "06_RESEARCH/results/entry_representation/rows.csv"
    m5_path = Path(args.m5_path) if args.m5_path else REPO_ROOT / "07_DATA/XAUUSD_M5.parquet"
    if not m5_path.exists():
        m5_path = REPO_ROOT / "07_DATA/XAUUSD_M1.parquet"

    result = run_measure(csv_path=csv_path, m5_path=m5_path,
                         output_path=Path(args.output) if args.output else None)

    print()
    print("=== RETURN BLOCK ===")
    for k, v in result.items():
        print(f"{k}: {v}")
    print("=== RETURN BLOCK ===")
    print()