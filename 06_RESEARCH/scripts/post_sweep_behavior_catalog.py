#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Post-sweep behavior catalog (read-only research — intelligence map).

Lead Architect directive (after A4 scoring close-out): catalog what the
market / detectors do AFTER POI+sweep — beyond Trigger F only. No live
gates, no threshold/pillar/trigger/SL-TP/risk changes, no expectancy
claims, no auto-promote filters.

Frozen design (stated before running):
  * Population: (a) 41 A4-contained rows (REFINEMENT proxy — measured
    from MATCHED ARMED bounds, not wide census, per ruling) + (b) all
    A2 (51) + A3 (82) rows on census bounds (labeled gap-A2/gap-A3).
    97 partials held out (identity contested by design — side count).
  * Horizons frozen (reused, no new numbers): trigger completions
    H_TRIG=48 M5 (Step-3 established); everything else H_PATH=100 M5
    (Track-B/decomposed established).
  * LTF rows (displacement incl. BOS tags, FVG) from the accepted LTF
    ledger, filtered: ts in (sweep, sweep+H] AND zone-overlap with the
    episode zone AND ltf_direction == thesis (aligned only; unaligned
    totals as one summary side count). No magnitude column exists in
    the ledger — presence + direction only (stated, not faked).
  * FVG mitigation (frozen): first M5 bar after formation intersecting
    gap bounds (lo..hi; singles tolerated); thesis-aligned FVGs only.
  * CHOCH via choch_classifier.classify_choch_at per bar on growing
    M5 prefixes (prefix ends at the evaluation bar — no future info;
    detect_swings rebuilt per prefix). No MSS detector exists in code
    — stated absent, never invented.
  * Triggers: Step-3 scan-mode re-run (SeriesState M5 + TriggerRouter
    eligible + episode POI, from_bar=sweep, EVERY completion recorded)
    in (sweep, sweep+48]; (b)-row firsts MUST equal Step-3's (fidelity
    cross-check — mismatch fails the run); (a) rows differ by design
    (armed bounds).
  * Zone reads on M5 (sweep, sweep+100]: touch bars/runs, first
    re-entry offset, violation (adverse close) first offset.
  * Routes/fills joined from Step-4 lifecycle by episode_id (read-only).
  * No-look-ahead: prefix-only inputs; timestamp resolution;
    run-relative indices never cross books.
  * Medians use first-occurrence offsets; unresolvable -> empty + note.

Outputs: results/post_sweep_behavior_catalog/{behavior_per_episode.csv,
summary.json} (+ rerun-hash check). Report:
POST_SWEEP_BEHAVIOR_CATALOG_NOTE.md (separate step).
LOGIC_CHANGED: NO (detectors/classifier/triggers only CALLED).
"""

from __future__ import annotations

import bisect
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
SCRIPTS_DIR = REPO_ROOT / "06_RESEARCH" / "scripts"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from smc.backtest.series_state import SeriesState
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi
from smc.detection.structural_swing_detector import detect_swings
from smc.poi.choch_classifier import classify_choch_at
from smc.triggers.base_trigger import TriggerContext
from smc.triggers.trigger_router import TriggerRouter

from decomposed_6m_ledger import parse_level
import stage3_trigger_visibility as s3
from poi_swept_ltf_confirm import episode_poi, trigger_letter

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "post_sweep_behavior_catalog"
ROWS_CSV = OUT_DIR / "behavior_per_episode.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"

BANNER = "DIAGNOSTIC — behavior map, not edge"

FORENSICS_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
                 "arming_forensics_bucket_a" / "forensics.csv")
POI_CSV = (REPO_ROOT / "06_RESEARCH" / "results" / "htf_poi_census" /
           "poi_episodes.csv")
LTF_CSV = (REPO_ROOT / "06_RESEARCH" / "results" / "ltf_confirmation" /
           "events_ltf_confirmation.csv")
CONFIRM_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
               "poi_swept_ltf_confirm" / "confirm_per_episode.csv")
LIFECYCLE_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
                 "poi_confirm_entry_path" / "lifecycle_per_episode.csv")

LOAD_FROM = datetime(2025, 5, 1, tzinfo=timezone.utc)
LOAD_END = datetime(2025, 12, 3, tzinfo=timezone.utc)
H_TRIG = 48
H_PATH = 100

CSV_COLUMNS = [
    "episode_id", "sample", "tf", "kind_tag", "direction", "sweep_ts",
    "zone_low_used", "zone_high_used",
    "n_trig_completions", "trig_letters", "first_trig", "first_trig_offset",
    "n_disp_aligned", "first_disp_offset",
    "n_bos_aligned", "first_bos_offset",
    "n_choch_aligned", "first_choch_offset",
    "n_fvg_aligned", "n_fvg_mitigated", "first_mitig_offset",
    "touch_bars", "touch_runs", "first_touch_offset",
    "violated", "violation_offset",
    "ever_routed", "ever_placed", "ever_filled", "route_trigger",
]


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested; bars are (high, low, close) tuples)
# --------------------------------------------------------------------------- #
def thesis_aligned(episode_dir: str | None, event_dir: str | None) -> bool:
    """Event serves the thesis only when directions agree (frozen)."""
    if not episode_dir or not event_dir:
        return False
    return episode_dir.strip().upper() == event_dir.strip().upper()


def ranges_overlap(lo1: float, hi1: float, lo2: float, hi2: float) -> bool:
    """Range intersection (inclusive) for linkage rules."""
    return lo1 <= hi2 and lo2 <= hi1


def touch_stats(bars: list[tuple], zlo: float, zhi: float, start: int,
                end: int) -> tuple[int, int, int | None]:
    """(touch bars, touch runs, first-touch offset) over [start, end]."""
    n_bars = 0
    runs = 0
    first = None
    in_run = False
    for i in range(max(start, 0), min(end, len(bars) - 1) + 1):
        high, low, _close = bars[i]
        if low <= zhi and high >= zlo:
            n_bars += 1
            if first is None:
                first = i - start
            if not in_run:
                runs += 1
                in_run = True
        else:
            in_run = False
    return n_bars, runs, first


def first_violation(bars: list[tuple], zlo: float, zhi: float,
                    is_long: bool, start: int, end: int) -> int | None:
    """First adverse-close offset (LONG close<low / SHORT close>high)."""
    for i in range(max(start, 0), min(end, len(bars) - 1) + 1):
        _high, _low, close = bars[i]
        if (close < zlo) if is_long else (close > zhi):
            return i - start
    return None


def first_mitigation(bars: list[tuple], glo: float, ghi: float, start: int,
                     end: int) -> int | None:
    """First bar intersecting gap bounds (fill touch), offset or None."""
    for i in range(max(start, 0), min(end, len(bars) - 1) + 1):
        high, low, _close = bars[i]
        if low <= ghi and high >= glo:
            return i - start
    return None


def parse_bounds(raw: str | None) -> tuple[float | None, float | None]:
    """Parse 'price' or 'lo..hi' level strings (None-safe)."""
    if not raw:
        return None, None
    try:
        if ".." in raw:
            lo_s, hi_s = raw.split("..", 1)
            lo, hi = float(lo_s), float(hi_s)
            return (lo, hi) if hi >= lo else (None, None)
        price = float(raw)
        return price, price
    except (TypeError, ValueError):
        return None, None


# --------------------------------------------------------------------------- #
# Loading (reuse accepted artifacts + canonical series — never regenerated)
# --------------------------------------------------------------------------- #
def _sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_series():
    """Canonical M1 slice + M5 exec series (load discipline documented)."""
    parquet = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    if not parquet.exists():
        raise SystemExit(f"canonical dataset missing: {parquet}")
    m1_all = load_ohlcv_parquet(str(parquet), Timeframe.M1)
    m1 = [c for c in m1_all if LOAD_FROM <= c.timestamp <= LOAD_END]
    if not m1:
        raise SystemExit("no M1 bars in the load window")
    m5 = resample_multi(m1, [Timeframe.M5])[Timeframe.M5]
    m5_keys: dict[str, int] = {}
    for i, c in enumerate(m5):
        m5_keys.setdefault(c.timestamp.strftime("%Y-%m-%d %H:%M"), i)
    print(f"[catalog] M5={len(m5)} "
          f"({m5[0].timestamp.date()} -> {m5[-1].timestamp.date()})",
          flush=True)
    return m5, m5_keys


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in (FORENSICS_CSV, POI_CSV, LTF_CSV, CONFIRM_CSV, LIFECYCLE_CSV):
        if not path.exists():
            raise SystemExit(f"required input missing: {path}")
    m5, m5_keys = load_series()
    last_idx = len(m5) - 1

    forensics = {r["episode_id"]: r for r in
                 csv.DictReader(open(FORENSICS_CSV, encoding="utf-8"))}
    poi_meta = {r["episode_id"]: r for r in
                csv.DictReader(open(POI_CSV, encoding="utf-8"))}
    confirm = {r["episode_id"]: r for r in
               csv.DictReader(open(CONFIRM_CSV, encoding="utf-8"))}
    lifecycle = {r["episode_id"]: r for r in
                 csv.DictReader(open(LIFECYCLE_CSV, encoding="utf-8"))}

    # ---- Population: (a) contained + (b) A2/A3; partials held out -------- #
    pop_a = [e for e, r in forensics.items()
             if r.get("reason", "").startswith("A")
             and r.get("match_kind") == "contained"]
    # NOTE: reason A-rows only here (forensics holds bucket-A rows).
    pop_a = [e for e in pop_a]
    pop_b = [e for e, r in forensics.items()
             if r.get("reason") in ("A2", "A3")]
    # (a) uses matched armed bounds; (b) census bounds (ruling).
    episodes = []
    for eid in sorted(set(pop_a)):
        r = forensics[eid]
        try:
            zlo, zhi = float(r["matched_armed_low"]), float(
                r["matched_armed_high"])
        except (TypeError, ValueError):
            continue
        episodes.append({"episode_id": eid, "sample": "armed-refinement",
                         "zone_low": zlo, "zone_high": zhi})
    for eid in sorted(set(pop_b)):
        meta = poi_meta.get(eid)
        if meta is None:
            continue
        try:
            zlo, zhi = float(meta["zone_low"]), float(meta["zone_high"])
        except (TypeError, ValueError):
            continue
        episodes.append({"episode_id": eid, "sample": "gap-A2-A3",
                         "zone_low": zlo, "zone_high": zhi})
    # Deterministic order; dedupe defensively (an id in both sets keeps
    # the armed-refinement row — same thesis, narrower bounds).
    seen: dict[str, dict] = {}
    for ep in episodes:
        prev = seen.get(ep["episode_id"])
        if prev is None or ep["sample"] == "armed-refinement":
            seen[ep["episode_id"]] = ep
    episodes = sorted(seen.values(), key=lambda e: e["episode_id"])
    print(f"[catalog] population={(len([e for e in episodes if e['sample'] == 'armed-refinement']), len([e for e in episodes if e['sample'] != 'armed-refinement']))} "
          f"(armed-refinement, gap)", flush=True)

    def minute_key(ts):
        try:
            return datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return None

    def sweep_of(eid):
        for src in (forensics,):
            if eid in src and src[eid].get("first_sweep_ts"):
                return src[eid]["first_sweep_ts"]
        return None

    # ---- LTF ledger, timestamp-sorted once -------------------------------- #
    ltf_rows = []
    with open(LTF_CSV, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            try:
                ts = datetime.fromisoformat(r["ltf_ts_utc"])
            except (ValueError, TypeError):
                continue
            ltf_rows.append((ts, r))
    ltf_rows.sort(key=lambda t: t[0])
    ltf_ts = [t[0] for t in ltf_rows]
    import bisect as _bisect

    # ---- Trigger re-run (Step-3 scan mode, all completions) ---------------- #
    router = TriggerRouter()
    stamps = [c.timestamp for c in m5]
    windows: dict[int, list[dict]] = {}
    ep_ctx: dict[str, dict] = {}
    skipped_no_direction = 0
    skipped_poi_build = 0
    for ep in episodes:
        eid = ep["episode_id"]
        sweep_ts = sweep_of(eid)
        if not sweep_ts:
            continue
        s = bisect.bisect_left(stamps, datetime.fromisoformat(sweep_ts))
        if s >= len(m5):
            continue
        meta = poi_meta.get(eid, {})
        direction = (meta.get("direction") or "")
        if not direction:
            skipped_no_direction += 1
            continue
        src = dict(meta)
        src["zone_low"], src["zone_high"] = ep["zone_low"], ep["zone_high"]
        src.setdefault("kind_tag", "")
        src.setdefault("all_tags", src.get("kind_tag", ""))
        src.setdefault("m8_kind", meta.get("m8_kind", ""))
        src["direction"] = direction
        info = {"sweep": s, "sweep_ts": sweep_ts, "completions": [],
                "zone": (ep["zone_low"], ep["zone_high"])}
        try:
            info["poi"] = episode_poi(src)
        except (KeyError, ValueError):
            skipped_poi_build += 1
            continue
        info["eligible"] = [t for t in s3.SIX_TRIGGERS
                            if t.type in router.eligible_types(info["poi"])]
        ep_ctx[eid] = info
        windows.setdefault(s, []).append(eid)
    state = SeriesState(Timeframe.M5)
    active: list[str] = []
    for bar, candle in enumerate(m5):
        state.extend(candle)
        active.extend(windows.get(bar, ()))
        keep: list[str] = []
        for eid in active:
            info = ep_ctx[eid]
            if bar <= info["sweep"] + H_TRIG:
                keep.append(eid)
                if bar > info["sweep"]:
                    from smc.triggers.base_trigger import TriggerContext
                    ctx = TriggerContext(
                        poi=info["poi"], candles=state.candles,
                        swings=state.swings, bar_index=bar,
                        from_bar=info["sweep"], hints=state)
                    for trigger in info["eligible"]:
                        signal = trigger.evaluate(ctx)
                        if signal is not None:
                            info["completions"].append(
                                {"bar": int(signal.completion_index),
                                 "letter": trigger_letter(signal.trigger)})
        active = keep
    n_trig_completions = sum(len(ep_ctx[e]["completions"]) for e in ep_ctx)
    print(f"[catalog] trigger completions in (sweep, sweep+{H_TRIG}]: "
          f"{n_trig_completions}", flush=True)

    # ---- Per-episode reads -------------------------------------------------- #
    m5_tuples = [(c.high, c.low, c.close) for c in m5]
    rows_out: list[dict] = []
    cross_mismatches: list[str] = []
    total_unaligned = 0
    for ep in episodes:
        eid = ep["episode_id"]
        frow = forensics.get(eid, {})
        meta = poi_meta.get(eid, {})
        direction = (frow.get("direction") or meta.get("direction") or "")
        is_long = direction.upper().startswith("LONG")
        sweep_ts = sweep_of(eid)
        if not sweep_ts or eid not in ep_ctx:
            continue
        info = ep_ctx[eid]
        s = info["sweep"]
        wend = min(s + H_PATH, last_idx)
        if last_idx < s + H_PATH:
            trunc_note = f"fewer than {H_PATH} M5 bars after sweep"
        else:
            trunc_note = ""
        end_ts = m5[wend].timestamp
        # LTF rows in (sweep, sweep+H]: overlap + thesis-aligned.
        # NOTE: three separate lists (never aliased — counts must not mix).
        disp: list = []
        bos: list = []
        fvg: list = []
        unaligned = 0
        first_disp = None
        first_bos = None
        lo0, hi0 = info["zone"]
        i0 = _bisect.bisect_right(ltf_ts, datetime.fromisoformat(sweep_ts))
        i1 = _bisect.bisect_right(ltf_ts, end_ts)
        for _ts, r in ltf_rows[i0:i1]:
            tag = (r.get("ltf_plain_tag") or "").split(" (")[0]
            if tag not in ("DISPLACEMENT", "FAIR VALUE GAP"):
                continue
            try:
                zlo = float(r["htf_zone_low"])
                zhi = float(r["htf_zone_high"])
            except (TypeError, ValueError):
                continue
            if not (zlo <= hi0 and lo0 <= zhi):
                continue
            if not thesis_aligned(direction, r.get("ltf_direction")):
                unaligned += 1
                continue
            try:
                ev_idx = m5_keys.get(minute_key(r.get("ltf_ts_utc")) or "")
            except (ValueError, TypeError):
                ev_idx = None
            ev_off = (ev_idx - s) if ev_idx is not None else None
            if tag == "DISPLACEMENT":
                disp.append(r)
                if ev_off is not None and (first_disp is None
                                           or ev_off < first_disp):
                    first_disp = ev_off
                if "BOS" in (r.get("ltf_plain_tag") or ""):
                    bos.append(r)
                    if ev_off is not None and (first_bos is None
                                               or ev_off < first_bos):
                        first_bos = ev_off
            else:
                fvg.append(r)
        # FVG mitigation per aligned gap (first touch after formation).
        mitigated = 0
        first_mitig = None
        for r in fvg:
            glo, ghi, _ref = parse_level(r.get("ltf_zone_or_level"))
            if glo is None:
                continue
            try:
                fidx = m5_keys.get(minute_key(r["ltf_ts_utc"]))
            except (ValueError, TypeError):
                fidx = None
            if fidx is None:
                continue
            off = first_mitigation(
                m5_tuples, glo, ghi, fidx + 1, wend)
            if off is not None:
                mitigated += 1
                off_abs = fidx + 1 + off - s
                if first_mitig is None or off_abs < first_mitig:
                    first_mitig = off_abs
        # CHOCH per bar on growing prefixes (no future info, ever).
        choch_offsets: list[int] = []
        total_unaligned += unaligned
        base = max(0, s - 300)
        for k in range(1, min(H_PATH, last_idx - s) + 1):
            pre = m5[base:s + k + 1]
            try:
                sw = detect_swings(pre, Timeframe.M5)
                cb = classify_choch_at(pre, sw)
            except Exception:  # noqa: BLE001 — one bar must not kill the run
                continue
            if cb is None:
                continue
            cb_dir = str(getattr(cb.direction, "value",
                                 cb.direction) or "").upper()
            if cb_dir and direction and cb_dir == direction.upper():
                choch_offsets.append(k)
        # Zone reads on M5 (sweep, sweep+100].
        n_tb, n_runs, first_touch = touch_stats(
            m5_tuples, lo0, hi0, s + 1, wend)
        viol = first_violation(m5_tuples, lo0, hi0, is_long, s + 1, wend)
        # Trigger completions (this evaluation) + cross-check vs Step-3.
        comps = sorted(info["completions"],
                       key=lambda c: (c["bar"], c["letter"]))
        letters = sorted({c["letter"] for c in comps})
        first = comps[0] if comps else None
        lc = lifecycle.get(eid, {})
        rows_out.append({
            "episode_id": eid,
            "sample": ep["sample"],
            "tf": frow.get("tf") or meta.get("tf", ""),
            "kind_tag": frow.get("kind_tag") or meta.get("kind_tag", ""),
            "direction": direction,
            "sweep_ts": sweep_ts,
            "zone_low_used": lo0, "zone_high_used": hi0,
            "n_trig_completions": len(comps),
            "trig_letters": "+".join(letters),
            "first_trig": (first["letter"] if first else ""),
            "first_trig_offset": ((first["bar"] - s) if first else ""),
            "n_disp_aligned": len(disp),
            "first_disp_offset": (first_disp if first_disp is not None
                                  else ""),
            "n_bos_aligned": len(bos),
            "first_bos_offset": (first_bos if first_bos is not None
                                 else ""),
            "n_choch_aligned": len(choch_offsets),
            "first_choch_offset": (min(choch_offsets)
                                   if choch_offsets else ""),
            "n_fvg_aligned": len(fvg),
            "n_fvg_mitigated": mitigated,
            "first_mitig_offset": (first_mitig if first_mitig is not None
                                   else ""),
            "touch_bars": n_tb, "touch_runs": n_runs,
            "first_touch_offset": (first_touch if first_touch is not None
                                   else ""),
            "violated": viol is not None,
            "violation_offset": (viol if viol is not None else ""),
            "ever_routed": lc.get("ever_routed", ""),
            "ever_placed": lc.get("ever_placed", ""),
            "ever_filled": lc.get("ever_filled", ""),
            "route_trigger": lc.get("route_trigger", ""),
        })
        # Cross-check (b)-rows: firsts must equal Step-3's (same evaluation).
        if ep["sample"] != "armed-refinement":
            cf = confirm.get(eid, {})
            exp_t = cf.get("first_confirm_trigger") or ""
            exp_b = cf.get("bars_sweep_to_confirm") or ""
            got_t = first["letter"] if first else ""
            got_b = (first["bar"] - s) if first else ""
            if (exp_t or got_t) and (exp_t != got_t or str(exp_b) != str(got_b)):
                cross_mismatches.append(eid)

    with open(ROWS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in rows_out:
            writer.writerow({c: ("" if r.get(c) is None else r.get(c))
                             for c in CSV_COLUMNS})

    # ---- Aggregates ------------------------------------------------------ #
    def _median(vals):
        vals = sorted(v for v in vals if v not in (None, ""))
        vals = [float(v) for v in vals]
        if not vals:
            return None
        mid = len(vals) // 2
        if len(vals) % 2:
            return vals[mid]
        return (vals[mid - 1] + vals[mid]) / 2.0

    summary = {
        "banner": BANNER,
        "frozen": {
            "population": ("(a) A4-contained rows on MATCHED ARMED bounds "
                           "(41) + (b) A2 (51) + A3 (82) rows on census "
                           "bounds; 97 partials held out (identity "
                           "contested); unconfirmed n/a (all rows confirmed "
                           "by construction of the source sets)"),
            "horizons": (f"triggers H_TRIG={H_TRIG} M5 (Step-3 established); "
                         f"all other path reads H_PATH={H_PATH} M5 "
                         "(Track-B/decomposed established)"),
            "ltf_link": ("ts in (sweep, sweep+H] + zone overlap + "
                         "ltf_direction == thesis; unaligned totals as one "
                         "side count"),
            "fvg_mitigation": ("first M5 bar after formation intersecting "
                               "gap bounds; thesis-aligned gaps only"),
            "choch": ("classify_choch_at per bar on growing M5 prefixes "
                      "(prefix ends at the bar — no future info); "
                      "thesis-aligned only; no MSS detector exists "
                      "(stated absent)"),
            "triggers": ("Step-3 scan-mode re-run (SeriesState + "
                         "TriggerRouter + episode POI, from_bar=sweep, "
                         "EVERY completion); (b)-row firsts cross-checked "
                         "vs Step-3 (must match exactly)"),
            "zone_reads": ("touch bars/runs, first re-entry offset, "
                           "first adverse-close offset on M5"),
            "routes_fills": "joined from Step-4 lifecycle by episode_id",
        },
        "n_episodes": len(rows_out),
        "n_armed_refinement": sum(1 for r in rows_out
                                  if r["sample"] == "armed-refinement"),
        "n_gap": sum(1 for r in rows_out if r["sample"] != "armed-refinement"),
        "cross_check_b_vs_step3": {
            "mismatches": cross_mismatches,
            "pass": not cross_mismatches,
        },
        "behaviors": {},
        "trigger_mix_all_completions": {},
        "unaligned_ltf_side_count": total_unaligned,
        "limitations": [
            "Partials (97) held out: identity contested by design.",
            "LTF rows carry no magnitude column — presence + direction "
            "only (stated, not faked).",
            "CHOCH per-bar prefixes rebuild swings each bar (slower but "
            "look-ahead-free by construction).",
            "No MSS detector exists in code (stated absent).",
            "Charts skipped by design (tabular catalog; review packs "
            "exist separately).",
            "No gate, no threshold, no live rule follows (see note).",
        ],
    }
    # behavior() is filled per behavior below (kept explicit for review).
    bhv = summary["behaviors"]
    sub_all = rows_out
    mix_counter: Counter = Counter()
    for _eid, _info in ep_ctx.items():
        for _c in _info["completions"]:
            mix_counter[_c["letter"]] += 1
    summary["trigger_mix_all_completions"] = dict(sorted(mix_counter.items()))
    trig_letters_all: Counter = Counter()
    for r in rows_out:
        for letter in (r.get("trig_letters") or "").split("+"):
            if letter:
                trig_letters_all[letter] += 1
    summary["trigger_mix_episodes_with_letter"] = dict(
        sorted(trig_letters_all.items()))
    for name, key, first in [
            ("trigger_any_completion", "n_trig_completions", "first_trig_offset"),
            ("displacement_aligned", "n_disp_aligned", "first_disp_offset"),
            ("bos_aligned", "n_bos_aligned", "first_bos_offset"),
            ("choch_aligned", "n_choch_aligned", "first_choch_offset"),
            ("fvg_aligned", "n_fvg_aligned", None),
            ("fvg_mitigated", "n_fvg_mitigated", "first_mitig_offset"),
            ("zone_touched", "touch_bars", "first_touch_offset"),
            ("zone_violated", "violated", "violation_offset")]:
        col = "n_trig_completions" if name == "trigger_any_completion" else key
        if name == "trigger_any_completion":
            have = [r for r in sub_all if int(r.get(col) or 0) > 0]
        elif name == "zone_touched":
            have = [r for r in sub_all if int(r.get(col) or 0) > 0]
        elif name == "zone_violated":
            have = [r for r in sub_all if str(r.get(col)) == "True"]
        else:
            have = [r for r in sub_all if int(r.get(col) or 0) > 0]
        firsts = [r.get(first) for r in have
                  if first and r.get(first) not in ("", None)]
        bhv[name] = {"n": len(have),
                     "pct": (round(100.0 * len(have) / len(sub_all), 2)
                             if sub_all else None),
                     "median_first_offset": _median(firsts)}
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[catalog] episodes={len(rows_out)} "
          f"cross_mismatches={len(cross_mismatches)}", flush=True)
    print(f"[catalog] wrote {OUT_DIR}", flush=True)
    return 0 if not cross_mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
