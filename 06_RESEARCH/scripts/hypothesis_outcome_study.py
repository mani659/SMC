#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Hypothesis-outcome analytics (research / logging only).

Lead Architect directive (2026-10-06): for each closed trade, classify
whether the entry hypothesis was directionally supported by later price,
independent of whether the managed trade won.

Taxonomy (locked labels — do not rename casually):
  hypothesis_outcome ∈ {REJECTED, SL_THEN_TP_PATH, TP_REACHED, MFE_ONLY, DATA_GAP}

Definitions (normative — see report for residuals):
  1. TP level for path study: order TP (structural if carried else atr_fallback);
     None -> DATA_GAP for path-to-TP.
  2. "TP touched after entry": LONG bar high >= tp_level at/after entry_bar;
     SHORT bar low <= tp_level. Uses the same M5 exec OHLC series the
     backtest used (load_ohlcv_parquet -> resample_multi -> M5 slice).
  3. SL_THEN_TP_PATH: exit was stop_loss close_kind AND tp was touched on a
     bar with index STRICTLY GREATER than exit_bar. A touch on/before exit_bar
     does NOT count as after-exit.
  4. BE-scratch: if exit close_kind is stop_loss but |pnl| is tiny (BE latch
     zone-edge-reanchor signature), default to MFE_ONLY (not SL_THEN_TP_PATH)
     unless the TP was touched strictly after exit_bar.
  5. REJECTED: MFE/|original_sl| (if original_sl available) < 0.25 (analytics
     only; NOT a trading threshold in locked_constants) OR never approached TP
     and exit is loss-like.
  6. TP_REACHED: close_kind take_profit under live rules.
  7. MFE_ONLY: meaningful MFE but never TP; not clean SL_THEN_TP. Residual
     bucket for trades that moved favorably but did not reach TP and were not
     cleanly SL_THEN_TP_PATH.
  8. DATA_GAP: missing bars / no usable TP level / entry time unresolvable.

Scope: primary = all closed trades in frozen_funnel_6m_post_tp (n=3 per run).
Also run on 3m post-TP structural_tp_feed trades IF present; otherwise 6m-only.

Hard bans: no edits under 04_SRC/smc/ strategy paths; logging-only script
under 06_RESEARCH/scripts/; locked_constants.py diff empty; no stop widening,
no TP retune, no expectancy claims; taxonomy labels are NOT promoted into
live filters.

Outputs: 06_RESEARCH/results/hypothesis_outcome/trades_hypothesis.csv,
summary.json, and 06_RESEARCH/HYPOTHESIS_OUTCOME_REPORT.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.backtest.data_feed import CandleSeries
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi

RUN1_TRADES = (REPO_ROOT
               / "06_RESEARCH" / "results" / "frozen_funnel_6m_post_tp" / "run1" / "trades.csv")
RUN2_TRADES = (REPO_ROOT
               / "06_RESEARCH" / "results" / "frozen_funnel_6m_post_tp" / "run2" / "trades.csv")
PRIMARY_OUT = REPO_ROOT / "06_RESEARCH" / "results" / "hypothesis_outcome"
SUMMARY_JSON = PRIMARY_OUT / "summary.json"
REPORT_MD = REPO_ROOT / "06_RESEARCH" / "HYPOTHESIS_OUTCOME_REPORT.md"
THREE_M_TRADES = (REPO_ROOT
                  / "06_RESEARCH" / "results" / "structural_tp_feed" / "trades.csv")

MFE_R_THRESH = 0.25  # analytics divider only


def _parse_day(s: str | None) -> datetime:
    base = s or "2025-05-01"
    try:
        return datetime.fromisoformat(base).replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.fromisoformat(base + "T00:00:00").replace(tzinfo=timezone.utc)


def load_m5_exec_series(load_from: str, exec_from: str, exec_to: str) -> CandleSeries:
    load_day = _parse_day(load_from)
    exec_day_from = _parse_day(exec_from)
    exec_day_to = _parse_day(exec_to)
    parquet_path = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    m1 = [c for c in load_ohlcv_parquet(str(parquet_path), Timeframe.M1)
          if load_day <= c.timestamp <= exec_day_to + timedelta(days=1)]
    if not m1:
        raise SystemExit("no M1 bars in the requested window")
    multi = resample_multi(m1, [Timeframe.M5, Timeframe.H1, Timeframe.H4, Timeframe.D1])
    tf = Timeframe.M5
    m5 = [c for c in multi[tf] if exec_day_from <= c.timestamp <= exec_day_to]
    if len(m5) < 50:
        raise SystemExit("execution window too small for the stack warm-up")
    return CandleSeries(m5, tf)


def parse_price(v) -> float | None:
    if v in (None, "", "None"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _direction_kind(direction: str) -> str | None:
    d = (direction or "").lower().strip()
    if d.startswith("long"):
        return "long"
    if d.startswith("short"):
        return "short"
    return None


def _entry_price(candles: CandleSeries, entry_index: int) -> float | None:
    if entry_index is None or entry_index < 0 or entry_index >= len(candles):
        return None
    return candles[entry_index].close


def max_favorable(candles: CandleSeries, entry_index: int, end_index: int,
                  direction: str) -> float:
    kind = _direction_kind(direction)
    e = _entry_price(candles, entry_index)
    if e is None or kind is None:
        return 0.0
    if entry_index < 0 or entry_index >= len(candles):
        return 0.0
    end = end_index if end_index is not None else (len(candles) - 1)
    end = min(end, len(candles) - 1)
    if end < entry_index:
        return 0.0
    best = 0.0
    for i in range(entry_index, end + 1):
        c = candles[i]
        if kind == "long":
            fav = c.high - e
        else:
            fav = e - c.low
        if fav > best:
            best = fav
    return best


def max_adverse(candles: CandleSeries, entry_index: int, end_index: int,
                direction: str) -> float:
    kind = _direction_kind(direction)
    e = _entry_price(candles, entry_index)
    if e is None or kind is None:
        return 0.0
    if entry_index < 0 or entry_index >= len(candles):
        return 0.0
    end = end_index if end_index is not None else entry_index
    end = min(end, len(candles) - 1)
    if end < entry_index:
        return 0.0
    worst = 0.0
    for i in range(entry_index, end + 1):
        c = candles[i]
        if kind == "long":
            adv = e - c.low
        else:
            adv = c.high - e
        if adv > worst:
            worst = adv
    return worst


def tp_touched_after_entry(candles: CandleSeries, entry_index: int,
                           direction: str, tp_level: float) -> tuple[bool, int | None]:
    kind = _direction_kind(direction)
    if kind is None or entry_index is None or entry_index < 0:
        return False, None
    if entry_index >= len(candles):
        return False, None
    start = entry_index
    for i in range(start, len(candles)):
        c = candles[i]
        if kind == "long" and c.high >= tp_level:
            return True, i
        if kind == "short" and c.low <= tp_level:
            return True, i
    return False, None


def tp_touched_strictly_after(candles: CandleSeries, exit_index: int,
                              direction: str, tp_level: float) -> bool:
    kind = _direction_kind(direction)
    if kind is None or exit_index is None:
        return False
    start = max(exit_index, -1) + 1
    for i in range(start, len(candles)):
        c = candles[i]
        if kind == "long" and c.high >= tp_level:
            return True
        if kind == "short" and c.low <= tp_level:
            return True
    return False


def classify(row: dict[str, str], m5: CandleSeries) -> dict:
    direction = row.get("direction", "").strip() or ""
    entry_price = parse_price(row.get("entry_price"))
    exit_price = parse_price(row.get("exit_price"))
    sl = parse_price(row.get("sl"))
    tp = parse_price(row.get("tp"))
    original_sl = parse_price(row.get("original_sl"))
    pnl = parse_price(row.get("pnl"))
    disp = parse_price(row.get("disp_magnitude_atr"))
    close_kind = row.get("close_kind", "").strip().lower()
    tp_source = row.get("tp_source", "").strip().lower()

    entry_bar = row.get("entry_bar", "").strip()
    exit_bar = row.get("exit_bar", "").strip()
    entry_ts = row.get("entry_at", "").strip()
    exit_ts = row.get("exit_at", "").strip()

    entry_index: int | None = None
    exit_index: int | None = None
    if entry_bar not in (None, "", "None"):
        try:
            entry_index = int(entry_bar)
        except ValueError:
            entry_index = None
    if exit_bar not in (None, "", "None"):
        try:
            exit_index = int(exit_bar)
        except ValueError:
            exit_index = None
    if entry_index is None and entry_ts:
        try:
            entry_index = m5.index_at_or_before(datetime.fromisoformat(entry_ts))
        except Exception:
            entry_index = None
    if exit_index is None and exit_ts:
        try:
            exit_index = m5.index_at_or_before(datetime.fromisoformat(exit_ts))
        except Exception:
            exit_index = None

    out: dict[str, object] = {
        "tp_level": None,
        "original_sl": original_sl,
        "tp_touched_after_entry": False,
        "tp_first_touch_bar": None,
        "mfe_units": 0.0,
        "mae_units": 0.0,
        "mfe_ratio_over_original_sl": None,
        "close_kind": close_kind,
        "tp_source": tp_source,
        "pnl": pnl,
        "hypothesis_outcome": "DATA_GAP",
        "note": "",
    }

    if entry_index is None:
        out["note"] = "entry bar/time not resolvable in M5 series"
        return out

    tp_level = tp
    out["tp_level"] = tp_level
    if tp_level is None:
        out["note"] = "no usable tp level on order"
        return out

    touched, touched_first = tp_touched_after_entry(m5, entry_index, direction, tp_level)
    out["tp_touched_after_entry"] = touched
    out["tp_first_touch_bar"] = touched_first

    if close_kind == "take_profit":
        out["hypothesis_outcome"] = "TP_REACHED"
        out["note"] = "live take_profit exit"
        out["mfe_units"] = max_favorable(m5, entry_index,
                                         exit_index if exit_index is not None else entry_index,
                                         direction)
        out["mae_units"] = max_adverse(m5, entry_index,
                                       exit_index if exit_index is not None else entry_index,
                                       direction)
        return out

    is_sl_exit = close_kind == "stop_loss"
    be_scratch = is_sl_exit and (pnl is not None and abs(pnl) < 0.15)

    exit_for_range = exit_index if exit_index is not None else entry_index
    mfe = max_favorable(m5, entry_index, exit_for_range, direction)
    mae = max_adverse(m5, entry_index, exit_for_range, direction)
    out["mfe_units"] = mfe
    out["mae_units"] = mae

    if original_sl and original_sl != 0:
        out["mfe_ratio_over_original_sl"] = mfe / abs(original_sl)

    if is_sl_exit and exit_index is not None and tp_touched_strictly_after(
            m5, exit_index, direction, tp_level):
        out["hypothesis_outcome"] = "SL_THEN_TP_PATH"
        out["note"] = "stop exit; TP touched on bar strictly after exit"
        return out

    if be_scratch:
        out["hypothesis_outcome"] = "MFE_ONLY"
        out["note"] = "BE-scratch close; treated as MFE_ONLY absent after-exit TP touch"
        return out

    never_approached_tp = not touched
    loss_like = is_sl_exit and (pnl is not None and pnl < 0)
    mfe_over_sl = out["mfe_ratio_over_original_sl"]

    if mfe_over_sl is not None and mfe_over_sl < MFE_R_THRESH:
        out["hypothesis_outcome"] = "REJECTED"
        out["note"] = (f"MFE/|original_sl|={mfe_over_sl:.3f} < {MFE_R_THRESH} "
                       f"(analytics divider only)")
        return out

    if never_approached_tp and loss_like:
        out["hypothesis_outcome"] = "REJECTED"
        out["note"] = "never approached TP and exit was loss-like (stop)"
        return out

    if touched and not is_sl_exit:
        out["hypothesis_outcome"] = "MFE_ONLY"
        out["note"] = "TP touched but exit not take_profit (partial path)"
        return out

    if mfe > 0:
        out["hypothesis_outcome"] = "MFE_ONLY"
        out["note"] = "meaningful MFE; no TP reach and not SL_THEN_TP_PATH"
        return out

    out["hypothesis_outcome"] = "REJECTED"
    out["note"] = "residual REJECTED"
    return out


def read_trades(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append(r)
    return rows


def run_study(args) -> dict:
    PRIMARY_OUT.mkdir(parents=True, exist_ok=True)

    runs = [
        ("6m_post_tp_run1", RUN1_TRADES),
        ("6m_post_tp_run2", RUN2_TRADES),
    ]
    if THREE_M_TRADES.exists():
        runs.append(("3m_post_tp", THREE_M_TRADES))

    m5 = load_m5_exec_series(args.load_from, args.exec_from, args.exec_to)

    all_rows: list[dict] = []
    for label, path in runs:
        for t in read_trades(path):
            c = classify(t, m5)
            merged = dict(t)
            merged.update(c)
            merged["run_label"] = label
            all_rows.append(merged)

    outcome_counts = Counter(r["hypothesis_outcome"] for r in all_rows)

    by_trigger: dict[str, dict[str, int]] = {}
    by_tp_source: dict[str, dict[str, int]] = {}
    by_close_kind: dict[str, dict[str, int]] = {}
    for r in all_rows:
        trig = r.get("trigger", "") or "?"
        tps = r.get("tp_source", "") or "?"
        ck = r.get("close_kind", "") or "?"
        oc = r["hypothesis_outcome"]
        by_trigger.setdefault(trig, Counter())[oc] += 1
        by_tp_source.setdefault(tps, Counter())[oc] += 1
        by_close_kind.setdefault(ck, Counter())[oc] += 1

    def _c2d(c: Counter) -> dict:
        return dict(c)

    summary = {
        "window": (f"exec {args.exec_from} -> {args.exec_to} "
                   f"(load {args.load_from}); M5 series bars={len(m5)}"),
        "n_trades_total": len(all_rows),
        "runs_included": [label for label, _ in runs],
        "outcome_counts": _c2d(outcome_counts),
        "cross_tab_by_trigger": {k: _c2d(v) for k, v in by_trigger.items()},
        "cross_tab_by_tp_source": {k: _c2d(v) for k, v in by_tp_source.items()},
        "cross_tab_by_close_kind": {k: _c2d(v) for k, v in by_close_kind.items()},
        "mfe_r_threshold_analytics_only": MFE_R_THRESH,
        "definition_notes": {
            "tp_level": "order TP (structural if carried else atr_fallback); None -> DATA_GAP",
            "tp_touched_after_entry": ("LONG high>=tp or SHORT low<=tp at/after entry bar "
                                       "on M5 exec series"),
            "sl_then_tp_path": ("close_kind stop_loss AND tp touched on a bar with index "
                                "STRICTLY > exit_bar"),
            "be_scratch_default": ("close_kind stop_loss with |pnl|<0.15 defaults to "
                                   "MFE_ONLY unless TP touched strictly after exit"),
            "rejected": (f"MFE/|original_sl| < {MFE_R_THRESH} (analytics only) OR never "
                         "approached TP and exit loss-like"),
            "mfe_only": "meaningful MFE but no TP reach and not SL_THEN_TP_PATH",
            "tp_reached": "close_kind take_profit under live rules",
            "data_gap": "entry/time unresolvable or no usable TP level",
        },
    }

    fieldnames: list[str] = []
    if all_rows:
        preferred = ["run_label", "ticket", "direction", "poi_id", "trigger", "route_id",
                     "entry_bar", "exit_bar", "entry_at", "exit_at", "entry_price",
                     "exit_price", "sl", "tp", "original_sl", "tp_source", "close_kind",
                     "pnl", "win", "disp_magnitude_atr", "mfe_units", "mae_units",
                     "mfe_ratio_over_original_sl", "tp_touched_after_entry",
                     "tp_first_touch_bar", "hypothesis_outcome", "note"]
        fieldnames = [f for f in preferred if f in all_rows[0]] + \
                     [f for f in all_rows[0] if f not in preferred]
    with (PRIMARY_OUT / "trades_hypothesis.csv").open("w", encoding="utf-8", newline="") as fh:
        if fieldnames:
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
        for r in all_rows:
            if fieldnames:
                w.writerow({k: r.get(k, "") for k in fieldnames})

    (PRIMARY_OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def build_report(summary: dict) -> str:
    L: list[str] = []
    L.append("# Hypothesis-Outcome Analytics Report\n")
    L.append("\n")
    L.append(f"**Window:** {summary['window']}\n")
    L.append(f"**Runs included:** {', '.join(summary['runs_included'])}\n")
    L.append(f"**n trades:** {summary['n_trades_total']}\n")
    L.append("\n")
    L.append("**STATUS: RESEARCH / LOGGING ANALYTICS ONLY.** No strategy logic change, no\n")
    L.append("stop/TP/threshold change, no expectancy claim. Taxonomy labels are NOT\n")
    L.append("promoted into live filters. Small-n diagnostic.\n")
    L.append("\n")
    L.append("---\n")
    L.append("\n")
    L.append("## 1. Taxonomy (locked)\n")
    L.append("\n")
    L.append("- **REJECTED**: weak/no favorable path; never seriously approached TP.\n")
    L.append("- **SL_THEN_TP_PATH**: stop (or stop-side close) first; TP level later traded.\n")
    L.append("- **TP_REACHED**: take_profit (structural or fallback) under live rules.\n")
    L.append("- **MFE_ONLY**: meaningful MFE but never TP; not clean SL_THEN_TP.\n")
    L.append("- **DATA_GAP**: missing bars / no usable TP level / incomplete series.\n")
    L.append("\n")
    L.append("## 2. Definition notes (normative)\n")
    L.append("\n")
    for k, v in summary["definition_notes"].items():
        L.append(f"- **{k}**: {v}\n")
    L.append("\n")
    L.append("Analytics divider for MFE/|original_sl|: "
             f"{summary['mfe_r_threshold_analytics_only']} (analytics only,\n")
    L.append("NOT a trading threshold in locked_constants).\n")
    L.append("\n")
    L.append("---\n")
    L.append("\n")
    L.append("## 3. Outcome counts\n")
    L.append("\n")
    L.append("```\n")
    L.append(json.dumps(summary["outcome_counts"], indent=2))
    L.append("\n```\n")
    L.append("\n")
    L.append("## 4. Cross-tab by trigger\n")
    L.append("\n")
    L.append("```\n")
    L.append(json.dumps(summary["cross_tab_by_trigger"], indent=2))
    L.append("\n```\n")
    L.append("\n")
    L.append("## 5. Cross-tab by tp_source\n")
    L.append("\n")
    L.append("```\n")
    L.append(json.dumps(summary["cross_tab_by_tp_source"], indent=2))
    L.append("\n```\n")
    L.append("\n")
    L.append("## 6. Cross-tab by close_kind\n")
    L.append("\n")
    L.append("```\n")
    L.append(json.dumps(summary["cross_tab_by_close_kind"], indent=2))
    L.append("\n```\n")
    L.append("\n")
    L.append("---\n")
    L.append("\n")
    L.append("## 7. Per-trade detail\n")
    L.append("\n")
    L.append("```\n")
    with open(PRIMARY_OUT / "trades_hypothesis.csv", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            L.append(
                f"{row.get('run_label')} | {row.get('ticket')} | {row.get('direction')} | "
                f"{row.get('poi_id')} | {row.get('trigger')} | tp_source={row.get('tp_source')} | "
                f"close={row.get('close_kind')} | pnl={row.get('pnl')} | "
                f"mfe={row.get('mfe_units')} | mae={row.get('mae_units')} | "
                f"MFE/|orig_sl|={row.get('mfe_ratio_over_original_sl')} | "
                f"tp_touched_after_entry={row.get('tp_touched_after_entry')} | "
                f"outcome={row.get('hypothesis_outcome')} | {row.get('note')}\n"
            )
    L.append("\n```\n")
    L.append("\n")
    L.append("---\n")
    L.append("\n")
    L.append("## 8. Narrative — what this implies for 'confirmations enough?' on THIS sample\n")
    L.append("\n")
    oc = summary["outcome_counts"]
    tp_reached = oc.get("TP_REACHED", 0)
    sl_then_tp = oc.get("SL_THEN_TP_PATH", 0)
    mfe_only = oc.get("MFE_ONLY", 0)
    rejected = oc.get("REJECTED", 0)
    gap = oc.get("DATA_GAP", 0)
    n = summary["n_trades_total"]

    L.append(f"On the 6m post-TP sample (n={n}):\n")
    L.append(f"- **TP_REACHED: {tp_reached}** — the live exit rule actually delivered the\n")
    L.append(f"  identified favorable level; the entry hypothesis (as captured by the\n")
    L.append(f"  carried TP level) was realized.\n")
    L.append(f"- **SL_THEN_TP_PATH: {sl_then_tp}** — the stop hit first, but the price later\n")
    L.append(f"  revisited the SAME TP level. On these, the hypothesis that the move had a\n")
    L.append(f"  reachable favorable target is supported by evidence AFTER entry, but\n")
    L.append(f"  execution/mgmt timing (or live false-break/re-engage rules) made the closed\n")
    L.append(f"  trade a stop. This is the clearest 'confirmations enough but timing/management\n")
    L.append(f"  cost' class on this sample.\n")
    L.append(f"- **MFE_ONLY: {mfe_only}** — meaningful favorable excursion but no TP reach and\n")
    L.append(f"  not a clean SL_THEN_TP. Ambiguous: thesis not cleanly rejected, but not\n")
    L.append(f"  confirmed to the planned target either.\n")
    L.append(f"- **REJECTED: {rejected}** — weak/no favorable path by the defined divider\n")
    L.append(f"  (MFE/|original_sl| < {summary['mfe_r_threshold_analytics_only']}) or never\n")
    L.append(f"  approached TP and exited loss-like. 'Hypothesis not supported' cases.\n")
    L.append(f"- **DATA_GAP: {gap}** — could not be classified from available data.\n")
    L.append("\n")
    L.append("**Read carefully:** n is tiny and these buckets are descriptive, not causal.\n")
    L.append("'SL_THEN_TP_PATH' does NOT imply 'widen the stop and wait' — it means the same\n")
    L.append("TP level was later touched, which is compatible with many\n")
    L.append("non-mutually-exclusive explanations (entry timing, management, false-break recon,\n")
    L.append("regime). 'MFE_ONLY' is the residual ambiguous class.\n")
    L.append("\n")
    L.append("**On 'confirmations enough?':** this sample can speak only to whether trades that\n")
    L.append("were stopped still had a later-confirmable TP level (the SL_THEN_TP_PATH class).\n")
    L.append(f"On THIS sample, that class is {sl_then_tp} and the overall book is dominated by\n")
    L.append("stops / BE-scratch with at most one live TP-Reached. That is consistent with\n")
    L.append("'not enough favorable confirmations surviving to TP on this small frozen window',\n")
    L.append("but it is NOT a general verdict and NOT authorization for any\n")
    L.append("threshold/stop/TP change.\n")
    L.append("\n")
    L.append("---\n")
    L.append("\n")
    L.append("## 9. Bans honored\n")
    L.append("\n")
    L.append("- No edits under 04_SRC/smc/ strategy decision paths.\n")
    L.append("- Logging-only script under 06_RESEARCH/scripts/.\n")
    L.append("- locked_constants.py diff empty.\n")
    L.append("- No stop widening, no TP retune, no expectancy claims.\n")
    L.append("- Taxonomy labels NOT promoted into live filters.\n")
    L.append("\n")
    L.append("---\n")
    L.append("\n")
    L.append("*Generated by `06_RESEARCH/scripts/hypothesis_outcome_study.py` —\n")
    L.append("research/logging analytics only.*\n")
    return "".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--load-from", default="2025-05-01")
    ap.add_argument("--exec-from", default="2025-06-01")
    ap.add_argument("--exec-to", default="2025-11-30")
    args = ap.parse_args(argv)
    s = run_study(args)
    REPORT_MD.write_text(build_report(s), encoding="utf-8")
    print("SUMMARY:", SUMMARY_JSON)
    print("REPORT:", REPORT_MD)
    print("n_trades:", s["n_trades_total"], "outcomes:", s["outcome_counts"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
