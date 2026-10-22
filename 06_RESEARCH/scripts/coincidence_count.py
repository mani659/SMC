#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Coincidence count — HTF thesis ∩ LTF proof in-window (read-only).

Lead Architect owner plan 2026-10-13 (binding step 2) + proof register
BACKUP_NEXT: price the sequential-order constraint with COUNTS ONLY.
How often does an LTF proof (Stage-3 completion A-F) coincide, inside a
short frozen window, with an HTF zone thesis — including theses the
product never armed and never routed? No routing change, no gate change,
no episode store, no live rule. LOGIC_CHANGED: NO (detectors/triggers
only CALLED with frozen params, under 04_SRC + research tests).

Frozen design (stated before running):
  * Population = ALL 1,093 unique Step-1 episodes as carried by Step-2's
    sweeps_per_episode.csv (one source: swept flag, first_sweep_ts,
    zone + direction + tf + kind_tag for every episode).
  * LTF proof = product Stage-3 completion evaluated EXACTLY as Step 3
    (poi_swept_ltf_confirm: one SeriesState(M5) per bar, TriggerRouter
    matrix-eligible triggers, TriggerContext with the episode POI),
    imported rather than forked. Every completion is recorded ungated.
    Episode POI construction is Step-3's verbatim function on Step-2
    rows (no m8_kind enrichment — that would change the fidelity gate).
  * Reference anchor (frozen, one rule): ref_bar =
      - SWEEP           : first_sweep_ts (exact M5 bar), the same anchor
                          Step 3 used, for the 946 swept episodes;
      - PROXY_DAY_CLOSE : the LAST M5 bar of first_seen_date, for the 147
                          unswept episodes (first-seen dating is
                          day-granular; taking the day CLOSE is the
                          conservative no-look-ahead choice — the thesis
                          is treated as visible only at the day's end).
  * Coincidence window (frozen, no new magic numbers): a completion C
    coincides with episode E iff ref_bar(E) < C.bar <= ref_bar(E) + H.
    Primary H = 48 (Step-3 horizon). Sensitivity H in {20, 38, 58}
    (20 = the locked give-up scale; 38/58 = +/-20% of 48). Derived as
    subsets of one pass, never re-run.
  * One inventory pass with keep-window ref+58 (superset of every
    horizon); nested horizons are windowed subsets. Completion pairs are
    de-duplicated by (bar, letter) before counting, and the RAW
    (undeduplicated) totals are reported against Step 3 so any
    divergence is visible rather than hidden.
  * Stratification (columns, never filters):
      product_fate  : filled | routed | armed_never_routed |
                      armed_never_routed_zone_only | never_armed
                      (precedence in that order). filled/routed/joined
                      come from Step-4 lifecycle rows (490 confirmed);
                      zone_only is a direction-free containment probe
                      against the 30 armed POIs' zone bands (armed POIs
                      carry no direction field for 8/30, so no
                      directional join is invented); everything else is
                      never_armed.
      armed_at_ref / state at first coincidence : swept > armed_only >
                      proxy_first_seen.
      trigger letter of the first coincidence; TF / M8 group of E.

Kill criteria (frozen before the run; register BACKUP_NEXT):
  COINCIDENCE_N = episodes with >= 1 coincidence at H=48.
    < 10                              -> SEQUENCE_REDESIGN_MOOT
    >= 10 and |N38-N58|/N48 <= 0.25   -> COINCIDENCE_MASS_PRESENT
    otherwise                         -> INCONCLUSIVE
  (Transitional verdict, research only: no rule, gate or store follows.)

Outputs: results/coincidence_count/{episode_coincidence.csv,
pair_events.csv, summary.json}. Note: COINCIDENCE_COUNT_NOTE.md.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
SCRIPTS_DIR = REPO_ROOT / "06_RESEARCH" / "scripts"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from smc.backtest.series_state import SeriesState
from smc.config.timeframe import Timeframe
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi
from smc.triggers.base_trigger import TriggerContext
from smc.triggers.trigger_router import TriggerRouter

import stage3_trigger_visibility as s3
import poi_swept_ltf_confirm as step3

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "coincidence_count"
ROWS_CSV = OUT_DIR / "episode_coincidence.csv"
PAIRS_CSV = OUT_DIR / "pair_events.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"

BANNER = "DIAGNOSTIC — NOT EDGE"

SWEEPS_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
              "poi_linked_sweep_rate" / "sweeps_per_episode.csv")
LIFECYCLE_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
                 "poi_confirm_entry_path" / "lifecycle_per_episode.csv")
ARMED_JSON = (REPO_ROOT / "06_RESEARCH" / "results" /
              "poi_confirm_entry_path" / "replay_run1" / "armed_records.json")
TRADES_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
              "product_6m_refresh_track_b" / "run1" / "trades.csv")

# Step-3 series definition (imported, not re-typed): LOAD_FROM 2025-05-01,
# LOAD_END 2025-12-03 — the warm-up-inclusive M5 grid whose bar indices
# HORIZONS / Step-3 artifacts use.
H_PRIMARY = 48
H_SENS = (20, 38, 58)
MAX_H = max((H_PRIMARY,) + H_SENS)

# Exec-window origin of the replay's own M5 series (its bar indices index
# the warm-up series from this offset). Asserted, never assumed (see
# integrity.warmup_offset / trades cross-check).
EXEC_ORIGIN = datetime(2025, 6, 1, 22, 0, tzinfo=timezone.utc)

FATE_ORDER = ("filled", "routed", "armed_never_routed",
              "armed_never_routed_zone_only", "never_armed")
STATE_ORDER = ("swept", "armed_only", "proxy_first_seen")

CSV_COLUMNS = [
    "episode_id", "tf", "kind_tag", "direction", "product_fate",
    "ref_kind", "ref_bar", "ref_ts", "swept", "first_sweep_ts",
    "joined_poi_id", "armed_poi_id", "armed_bar_exec", "armed_ts",
    "armed_at_ref", "coincident_20", "coincident_38", "coincident_48",
    "coincident_58", "n_completions_48", "n_completions_58",
    "first_coinc_bar", "first_coinc_ts", "first_coinc_trigger",
    "bars_ref_to_first_coinc", "state_at_first_coinc",
    "armed_at_first_coinc", "ever_routed", "ever_filled", "gap_reason",
]

PAIR_COLUMNS = [
    "episode_id", "tf", "kind_tag", "direction", "product_fate",
    "ref_kind", "ref_bar", "ref_ts", "completion_bar", "completion_ts",
    "trigger_letter", "bars_after_ref", "within_20", "within_48",
]


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #
def within(completion_bar: int, ref_bar: int, horizon: int) -> bool:
    """Coincidence window: ref_bar < bar <= ref_bar + horizon (frozen).

    Strict-greater on the left excludes same-timestamp ambiguity (the
    reference bar itself is never a completion), inclusive on the right —
    identical to the Step-3 link rule.
    """
    return bool(ref_bar is not None and completion_bar is not None
                and ref_bar < int(completion_bar) <= ref_bar + int(horizon))


def dedupe_completions(completions: list[dict]) -> list[dict]:
    """Unique (bar, letter) completions, earliest occurrence kept.

    Defensive: the inventory loop's per-bar evaluation can in principle
    re-report a completion; counting a pair twice would inflate every
    table. Stable order (sorted by bar, then letter).
    """
    seen: dict[tuple, dict] = {}
    for c in completions:
        key = (int(c["bar"]), step3.trigger_letter(c["trigger"]))
        if key not in seen:
            seen[key] = c
    return [seen[k] for k in sorted(seen)]


def day_close_index(stamps: list, date_str: str) -> int | None:
    """Index of the LAST bar whose date part equals ``date_str``.

    ``date_str`` = "YYYY-MM-DD" (Step-1 first_seen_date). Returns None when
    the date has no bar. Deliberately the day CLOSE, not the open: a
    first-seen date is day-granular, so treating the thesis as visible
    only at the day's end is the conservative (no-look-ahead) proxy.
    """
    if not date_str:
        return None
    prefix = str(date_str)[:10]
    lo = bisect.bisect_left(stamps, prefix)
    hi = bisect.bisect_left(stamps, prefix + "\uffff")
    if lo >= hi:
        return None
    return hi - 1


def zone_inside(zone_low: float, zone_high: float,
                band_low: float, band_high: float) -> bool:
    """True when [zone_low, zone_high] lies inside [band_low, band_high].

    Direction-free containment (no tolerance invented). Used only for the
    disclosed ``armed_never_routed_zone_only`` stratum — never as a route
    or fill claim.
    """
    return bool(band_low <= zone_low and zone_high <= band_high)


def pick_container(candidates: list[tuple]) -> tuple | None:
    """Deterministic smallest-area container (Step-4 Tier-B discipline).

    ``candidates`` = [(poi_id, low, high, ...), ...]. Returns the narrowest
    band, ties broken by ``poi_id`` — never the arbitrary first match, so
    the armed-POI attribution of an episode nested in several armed zones
    is a property of the geometry, not of dict order.
    """
    if not candidates:
        return None
    return sorted(candidates, key=lambda b: (float(b[2]) - float(b[1]),
                                             str(b[0])))[0]


def fate_for(*, ever_filled: bool, ever_routed: bool, joined: bool,
             zone_only: bool) -> str:
    """Frozen fate precedence: filled > routed > joined > zone_only > none."""
    if ever_filled:
        return "filled"
    if ever_routed:
        return "routed"
    if joined:
        return "armed_never_routed"
    if zone_only:
        return "armed_never_routed_zone_only"
    return "never_armed"


def state_at(*, ref_is_sweep: bool, armed_at: bool) -> str:
    """Frozen state precedence: swept > armed_only > proxy_first_seen."""
    if ref_is_sweep:
        return "swept"
    if armed_at:
        return "armed_only"
    return "proxy_first_seen"


def kill_verdict(n48: int, n38: int, n58: int) -> str:
    """Pre-registered kill-criteria rule (register BACKUP_NEXT).

    < 10 episodes at the primary horizon -> the sequential-order
    constraint removes nothing measurable (SEQUENCE_REDESIGN_MOOT);
    >= 10 and window-stable (|N38-N58|/N48 <= 0.25) -> mass present;
    otherwise the definition is too fragile to carry.
    """
    if n48 < 10:
        return "SEQUENCE_REDESIGN_MOOT"
    if n48 and abs(n38 - n58) / float(n48) <= 0.25:
        return "COINCIDENCE_MASS_PRESENT"
    return "INCONCLUSIVE"


def is_m8_group(tf_name: str) -> bool:
    """M8-sourced episode (tf like ``M8-H4`` / ``M8-D1`` / ``M8-W1``)."""
    return str(tf_name).startswith("M8-")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str] | None = None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--until", default=None,
                   help="smoke mode: stop the bar loop at this date "
                        "(YYYY-MM-DD); artifacts go to the smoke dir")
    p.add_argument("--out-dir", default=None,
                   help="override the artifact directory")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out_dir) if args.out_dir else OUT_DIR
    if args.until and not args.out_dir:
        out_dir = OUT_DIR.parent / "coincidence_count_smoke"
    out_dir.mkdir(parents=True, exist_ok=True)
    smoke = bool(args.until)
    for path in (SWEEPS_CSV, LIFECYCLE_CSV, ARMED_JSON, TRADES_CSV):
        if not path.exists():
            raise SystemExit(f"required input missing: {path}")

    # ---- Series (Step-3 definition, imported constants) ------------------- #
    parquet = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    if not parquet.exists():
        raise SystemExit(f"canonical dataset missing: {parquet}")
    m1_all = load_ohlcv_parquet(str(parquet), Timeframe.M1)
    m1 = [c for c in m1_all
          if step3.LOAD_FROM <= c.timestamp <= step3.LOAD_END]
    if not m1:
        raise SystemExit("no M1 bars in the load window")
    m5 = resample_multi(m1, [Timeframe.M5])[Timeframe.M5]
    stamps = [c.timestamp for c in m5]
    iso = [s.isoformat() for s in stamps]
    minute_keys = [s.strftime("%Y-%m-%d %H:%M") for s in stamps]
    print(f"[coinc] M5={len(m5)} ({stamps[0]} -> {stamps[-1]})", flush=True)

    warmup_offset = bisect.bisect_left(stamps, EXEC_ORIGIN)
    assert stamps[warmup_offset] == EXEC_ORIGIN, stamps[warmup_offset]
    # Exec-index cross-check against the frozen run's own trade timestamps.
    trade_checks = []
    with open(TRADES_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            bar = int(row["entry_bar"])
            idx = warmup_offset + bar
            got = iso[idx] if idx < len(iso) else ""
            want = row["entry_at"].replace("+00:00", "")[:16]
            trade_checks.append({
                "ticket": row["ticket"], "entry_bar": bar,
                "expected": row["entry_at"], "resolved": got,
                "ok": bool(got and got.replace("T", " ").startswith(want)),
            })
    exec_bar_check_ok = all(c["ok"] for c in trade_checks)
    print(f"[coinc] warmup_offset={warmup_offset} "
          f"trade_bar_cross_check={exec_bar_check_ok}", flush=True)

    # ---- Inputs ----------------------------------------------------------- #
    with open(SWEEPS_CSV, encoding="utf-8", newline="") as f:
        population = list(csv.DictReader(f))
    life = {r["episode_id"]: r for r in
            csv.DictReader(open(LIFECYCLE_CSV, encoding="utf-8"))}
    armed = json.loads(ARMED_JSON.read_text(encoding="utf-8"))
    armed_bands = [(p["poi_id"], float(p["zone_low"]), float(p["zone_high"]),
                    int(p["armed_bar"]), str(p.get("routed") or "") == "true")
                   for p in armed.values()]
    print(f"[coinc] population={len(population)} lifecycle={len(life)} "
          f"armed={len(armed)}", flush=True)

    router = TriggerRouter()
    skipped_no_anchor = 0
    windows: dict[int, list[dict]] = {}
    for ep in population:
        swept = ep.get("swept") == "True"
        ref_kind, ref_bar = None, None
        if swept and ep.get("first_sweep_ts"):
            ref_bar = bisect.bisect_left(stamps, datetime.fromisoformat(
                ep["first_sweep_ts"]))
            ref_kind = "SWEEP"
        else:
            ref_bar = day_close_index(minute_keys,
                                      ep.get("first_seen_date") or "")
            ref_kind = "PROXY_DAY_CLOSE"
        if ref_bar is None or ref_bar >= len(m5):
            skipped_no_anchor += 1
            ep["_ref_bar"] = None
            continue
        ep["_swept"] = swept
        ep["_ref_kind"] = ref_kind
        ep["_ref_bar"] = ref_bar
        ep["_poi"] = step3.episode_poi(ep)
        ep["_eligible"] = [t for t in s3.SIX_TRIGGERS
                           if t.type in router.eligible_types(ep["_poi"])]
        ep["_completions"] = []
        windows.setdefault(ref_bar, []).append(ep)
    print(f"[coinc] anchored={len(population) - skipped_no_anchor} "
          f"skipped_no_anchor={skipped_no_anchor}", flush=True)

    # ---- Single inventory pass (Step-3 evaluation mode, keep ref+58) ------- #
    until_bar = None
    if args.until:
        until_bar = bisect.bisect_left(
            stamps, datetime.fromisoformat(args.until).replace(
                tzinfo=timezone.utc))
    active: list[dict] = []
    state = SeriesState(Timeframe.M5)
    last_bar = min(len(m5), until_bar if until_bar else len(m5))
    for bar in range(last_bar):
        state.extend(m5[bar])
        active.extend(windows.get(bar, ()))
        keep: list[dict] = []
        for ep in active:
            if bar <= ep["_ref_bar"] + MAX_H:
                keep.append(ep)
                if bar > ep["_ref_bar"]:
                    ctx = TriggerContext(
                        poi=ep["_poi"], candles=state.candles,
                        swings=state.swings, bar_index=bar,
                        from_bar=ep["_ref_bar"], hints=state)
                    for trigger in ep["_eligible"]:
                        signal = trigger.evaluate(ctx)
                        if signal is not None:
                            ep["_completions"].append(
                                {"bar": int(signal.completion_index),
                                 "trigger": trigger.type})
        active = keep
        if (bar + 1) % 10000 == 0:
            print(f"[coinc] bar {bar + 1}/{last_bar} "
                  f"active={len(active)}", flush=True)

    # ---- Per-episode resolution ------------------------------------------- #
    rows_out: list[dict] = []
    pairs_out: list[dict] = []
    step3_gate = {"swept_n": 0, "confirmed_48": 0,
                  "completions_48_raw": 0, "completions_48_dedup": 0,
                  "episode_flag_mismatches": []}
    for ep in population:
        ref_bar = ep.get("_ref_bar")
        swept = ep.get("_swept", False)
        lr = life.get(ep["episode_id"], {})
        ever_routed = lr.get("ever_routed") == "True"
        ever_filled = lr.get("ever_filled") == "True"
        joined = lr.get("join_tier") in ("exact", "containment")
        joined_poi_id = lr.get("joined_poi_id") or ""
        zl, zh = float(ep["zone_low"]), float(ep["zone_high"])
        band_join = next((b for b in armed_bands
                          if joined_poi_id and b[0] == joined_poi_id), None)
        band_zone = pick_container([b for b in armed_bands
                                    if zone_inside(zl, zh, b[1], b[2])])
        chosen = band_join or band_zone
        armed_poi_id = chosen[0] if chosen else ""
        armed_bar_exec = chosen[3] if chosen else ""
        armed_ts = (iso[min(warmup_offset + int(armed_bar_exec),
                            len(iso) - 1)] if chosen else "")
        zone_only = bool(joined is False and band_zone is not None)
        fate = fate_for(ever_filled=ever_filled, ever_routed=ever_routed,
                        joined=joined, zone_only=zone_only)

        raw = ep.get("_completions", []) if ref_bar is not None else []
        comps = dedupe_completions(raw)
        armed_full = (warmup_offset + int(armed_bar_exec)
                      if armed_bar_exec != "" else None)
        armed_at_ref = bool(armed_full is not None and ref_bar is not None
                            and armed_full <= ref_bar)
        flags: dict[int, bool] = {}
        for h in (H_PRIMARY,) + H_SENS:
            flags[h] = (ref_bar is not None
                        and any(within(c["bar"], ref_bar, h) for c in comps))
        first = (step3.first_confirmation(
            [c for c in comps if within(c["bar"], ref_bar, MAX_H)])
            if ref_bar is not None else None)
        first_bar = int(first["bar"]) if first else ""
        state_first = state_at(ref_is_sweep=bool(swept and ref_bar is not None),
                               armed_at=bool(armed_full is not None
                                             and first_bar != ""
                                             and armed_full <= first_bar))
        rows_out.append({
            "episode_id": ep["episode_id"], "tf": ep["tf"],
            "kind_tag": ep["kind_tag"], "direction": ep["direction"],
            "product_fate": fate,
            "ref_kind": ep.get("_ref_kind") or "",
            "ref_bar": "" if ref_bar is None else ref_bar,
            "ref_ts": iso[ref_bar] if ref_bar is not None else "",
            "swept": swept, "first_sweep_ts": ep.get("first_sweep_ts") or "",
            "joined_poi_id": joined_poi_id,
            "armed_poi_id": armed_poi_id, "armed_bar_exec": armed_bar_exec,
            "armed_ts": armed_ts, "armed_at_ref": armed_at_ref,
            "coincident_20": flags.get(20, False),
            "coincident_38": flags.get(38, False),
            "coincident_48": flags.get(48, False),
            "coincident_58": flags.get(58, False),
            "n_completions_48": sum(1 for c in comps
                                    if within(c["bar"], ref_bar, 48)),
            "n_completions_58": sum(1 for c in comps
                                    if within(c["bar"], ref_bar, 58)),
            "first_coinc_bar": first_bar,
            "first_coinc_ts": iso[first_bar] if first_bar != "" else "",
            "first_coinc_trigger": (step3.trigger_letter(first["trigger"])
                                    if first else ""),
            "bars_ref_to_first_coinc": (first_bar - ref_bar
                                        if first_bar != "" else ""),
            "state_at_first_coinc": state_first,
            "armed_at_first_coinc": bool(armed_full is not None
                                         and first_bar != ""
                                         and armed_full <= first_bar),
            "ever_routed": ever_routed, "ever_filled": ever_filled,
            "gap_reason": lr.get("gap_reason") or "",
        })
        for c in comps:
            letter = step3.trigger_letter(c["trigger"])
            pairs_out.append({
                "episode_id": ep["episode_id"], "tf": ep["tf"],
                "kind_tag": ep["kind_tag"], "direction": ep["direction"],
                "product_fate": fate,
                "ref_kind": ep.get("_ref_kind") or "",
                "ref_bar": "" if ref_bar is None else ref_bar,
                "ref_ts": iso[ref_bar] if ref_bar is not None else "",
                "completion_bar": int(c["bar"]),
                "completion_ts": (iso[int(c["bar"])]
                                  if 0 <= int(c["bar"]) < len(iso) else ""),
                "trigger_letter": letter,
                "bars_after_ref": (int(c["bar"]) - ref_bar
                                   if ref_bar is not None else ""),
                "within_20": (ref_bar is not None
                              and within(c["bar"], ref_bar, 20)),
                "within_48": (ref_bar is not None
                              and within(c["bar"], ref_bar, 48)),
            })

        # ---- Step-3 reconciliation (swept population @ the sweep anchor) --- #
        if swept and ref_bar is not None:
            step3_gate["swept_n"] += 1
            if flags.get(48):
                step3_gate["confirmed_48"] += 1
            windowed_raw = step3.completions_in_window(raw, ref_bar, 48)
            step3_gate["completions_48_raw"] += len(windowed_raw)
            step3_gate["completions_48_dedup"] += sum(
                1 for c in comps if within(c["bar"], ref_bar, 48))
            s3row = step3_rows.get(ep["episode_id"], {})
            want = s3row.get("confirmed_within_48")
            if want is not None and (want == "True") != bool(flags.get(48)):
                step3_gate["episode_flag_mismatches"].append(
                    {"episode_id": ep["episode_id"], "step3": want,
                     "this": bool(flags.get(48))})

    # ---- Artifacts -------------------------------------------------------- #
    for name, cols, data in (("episode_coincidence.csv", CSV_COLUMNS,
                              rows_out),
                             ("pair_events.csv", PAIR_COLUMNS, pairs_out)):
        with open(out_dir / name, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            for r in data:
                writer.writerow({c: ("" if r.get(c) is None else r.get(c))
                                 for c in cols})

    # ---- Aggregates ------------------------------------------------------- #
    def _count(key: str) -> int:
        return sum(1 for r in rows_out if r[key] is True)

    n48, n20, n38, n58 = (_count("coincident_48"), _count("coincident_20"),
                          _count("coincident_38"), _count("coincident_58"))
    pairs48 = sum(1 for p in pairs_out if p["within_48"])
    by_fate: dict[str, dict] = {}
    for fate in FATE_ORDER:
        sub = [r for r in rows_out if r["product_fate"] == fate]
        by_fate[fate] = {
            "n_episodes": len(sub),
            "coincident_48": sum(1 for r in sub if r["coincident_48"]),
            "coincident_20": sum(1 for r in sub if r["coincident_20"]),
            "routed": sum(1 for r in sub if r["ever_routed"]),
            "filled": sum(1 for r in sub if r["ever_filled"]),
        }
    by_group: dict[str, dict] = {}
    for g in ("H4", "H1", "M8-H4", "M8-D1", "M8-W1"):
        sub = [r for r in rows_out if r["tf"] == g]
        by_group[g] = {
            "n_episodes": len(sub),
            "coincident_48": sum(1 for r in sub if r["coincident_48"]),
            "coincident_48_rate": (round(sum(
                1 for r in sub if r["coincident_48"]) / len(sub), 4)
                if sub else None),
        }
    coinc_armed = [r for r in rows_out if r["coincident_48"]
                   and r["product_fate"] in
                   ("filled", "routed", "armed_never_routed",
                    "armed_never_routed_zone_only")]
    conversion = {
        "coincident_armed_geometry": len(coinc_armed),
        "of_those_routed": sum(1 for r in coinc_armed if r["ever_routed"]),
        "of_those_filled": sum(1 for r in coinc_armed if r["ever_filled"]),
    }
    verdict = kill_verdict(n48, n38, n58)

    summary = {
        "banner": BANNER,
        "frozen": {
            "population": ("all 1,093 unique Step-1 episodes carried by "
                           "Step-2 sweeps_per_episode.csv"),
            "ltf_proof": ("Stage-3 completions evaluated exactly as Step 3 "
                          "(poi_swept_ltf_confirm evaluation mode, imported "
                          "not forked); episode POI = Step-3's verbatim "
                          "function on Step-2 rows (no m8_kind enrichment)"),
            "anchor": ("SWEEP = first_sweep_ts (946 episodes); "
                       "PROXY_DAY_CLOSE = last M5 bar of first_seen_date for "
                       "the 147 unswept episodes (conservative, no "
                       "look-ahead)"),
            "window": ("ref_bar < completion_bar <= ref_bar + H; primary "
                       "H=48, sensitivity H in {20,38,58} derived from one "
                       "pass with keep-window ref+58"),
            "dedupe": ("pairs de-duplicated by (bar, letter); RAW Step-3 "
                       "totals also reported so divergence is visible"),
            "container": ("zone-band attribution = smallest-area containing "
                          "armed band, ties by poi_id (Step-4 Tier-B "
                          "discipline; 52 episodes nest in >1 band)"),
            "fate": ("filled > routed > armed_never_routed (Step-4 lifecycle "
                     "join) > armed_never_routed_zone_only (direction-free "
                     "containment in the 30 armed zone bands; no directional "
                     "join invented because 8/30 armed records carry no "
                     "direction) > never_armed; episodes outside the 490 "
                     "confirmed rows are never labeled routed/filled — the "
                     "time-qualified route/fill facts live only in the "
                     "Step-4 lifecycle"),
            "state": "swept > armed_only (armed_bar <= bar) > proxy_first_seen",
        },
        "integrity": {
            "warmup_offset": warmup_offset,
            "exec_bar_check_ok": exec_bar_check_ok,
            "trade_bar_checks": trade_checks,
            "step3_swept_n": step3_gate["swept_n"],
            "step3_confirmed_48": step3_gate["confirmed_48"],
            "step3_completions_48_raw": step3_gate["completions_48_raw"],
            "step3_completions_48_dedup": step3_gate["completions_48_dedup"],
            "step3_expectation": {"swept_n": 946, "confirmed_48": 490,
                                  "completions_48": 605},
            "step3_episode_flag_mismatches": (
                step3_gate["episode_flag_mismatches"][:20]),
            "step3_n_mismatches": len(step3_gate["episode_flag_mismatches"]),
            "skipped_no_anchor": skipped_no_anchor,
            "smoke_until": args.until,
            "smoke_last_bar": last_bar,
        },
        "n_population": len(rows_out),
        "n_coincident_48": n48,
        "n_coincident_20": n20,
        "n_coincident_38": n38,
        "n_coincident_58": n58,
        "n_pairs_48": pairs48,
        "n_pairs_total_recorded": len(pairs_out),
        "sensitivity": {
            "n_by_horizon": {"20": n20, "38": n38, "48": n48, "58": n58},
            "swing_38_58_over_48": (round(abs(n38 - n58) / float(n48), 4)
                                    if n48 else None),
        },
        "by_fate": by_fate,
        "by_group": by_group,
        "by_ref_kind": {
            k: {"n_episodes": sum(1 for r in rows_out
                                  if r["ref_kind"] == k),
                "coincident_48": sum(1 for r in rows_out
                                     if r["ref_kind"] == k
                                     and r["coincident_48"])}
            for k in ("SWEEP", "PROXY_DAY_CLOSE")},
        "by_trigger_first": dict(Counter(
            r["first_coinc_trigger"] for r in rows_out
            if r["first_coinc_trigger"])),
        "by_state_at_first_coinc": dict(Counter(
            r["state_at_first_coinc"] for r in rows_out
            if r["first_coinc_trigger"])),
        "armed_at_first_coinc_yes": sum(
            1 for r in rows_out if r["armed_at_first_coinc"]),
        "conversion": conversion,
        "kill_criteria": {
            "rule": ("COINCIDENCE_N = episodes with >=1 coincidence at H=48;"
                     " <10 -> SEQUENCE_REDESIGN_MOOT; >=10 and "
                     "|N38-N58|/N48 <= 0.25 -> COINCIDENCE_MASS_PRESENT; "
                     "otherwise INCONCLUSIVE"),
            "COINCIDENCE_N": n48,
            "n38": n38, "n58": n58,
            "swing": (round(abs(n38 - n58) / float(n48), 4) if n48 else None),
            "KILL_CRITERIA_VERDICT": verdict,
            "coincident_unarmed_stratum": by_fate["never_armed"][
                "coincident_48"],
        },
        "limitations": [
            "Counts only: no gate, threshold, routing change, episode "
            "store or live rule follows.",
            "Unswept episodes use a day-granular PROXY anchor (day close); "
            "their state is proxy_first_seen and they are reported as their "
            "own stratum, never inside the Step-3 reconciliation.",
            "armed_never_routed_zone_only is a direction-free containment "
            "probe against armed zone bands, not a lifecycle join.",
            "fate for episodes outside the 490 confirmed rows comes from "
            "lifecycle + zone-band probes; it is a stratification label, "
            "not a per-POI arming log (per-POI validation/arm logs do not "
            "exist).",
            "Completion bars index the warm-up-inclusive Step-3 M5 grid; "
            "armed_bar (replay exec index) is converted with the asserted "
            "warmup offset and cross-checked on the frozen run's trades.",
            "No expectancy, PnL, win-rate or edge claim exists anywhere in "
            "this artifact set.",
        ],
    }
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[coinc] n48={n48} n20={n20} n38={n38} n58={n58} "
          f"pairs48={pairs48} verdict={verdict}", flush=True)
    print(f"[coinc] step3 gate: swept={step3_gate['swept_n']} "
          f"confirmed48={step3_gate['confirmed_48']} "
          f"completions(raw)={step3_gate['completions_48_raw']} "
          f"(dedup)={step3_gate['completions_48_dedup']} "
          f"mismatches={len(step3_gate['episode_flag_mismatches'])}",
          flush=True)
    print(f"[coinc] wrote {out_dir}", flush=True)
    return 0


# Step-3 per-episode artifacts (read once at import-time of main; declared
# here so the reconciliation block above stays close to its use).
step3_rows: dict[str, dict] = {}
_s3_path = (REPO_ROOT / "06_RESEARCH" / "results" / "poi_swept_ltf_confirm"
            / "confirm_per_episode.csv")
if _s3_path.exists():
    with open(_s3_path, encoding="utf-8", newline="") as _f:
        step3_rows = {r["episode_id"]: r for r in csv.DictReader(_f)}


if __name__ == "__main__":
    raise SystemExit(main())
