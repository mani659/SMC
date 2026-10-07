"""POST-V1 PHASE B — same-bar SL-first spot-check (plan §4 invariant).

The fill model's same-bar SL-FIRST rule is not covered by a funnel counter,
so the plan requires a hand spot-check on sampled bars. This script does it
over ALL closed trades (stronger than sampling):

For every closed trade, load the EXIT bar's OHLC from the canonical parquet
(sanctioned loader) and verify:
  1. close_kind == stop_loss  -> exit_price == SL exactly
  2. close_kind == take_profit -> exit_price == TP exactly
  3. AMBIGUOUS exit bars (single bar range touches both SL and TP) ->
     must resolve SL-first: exit at SL, never at TP
  4. exit bar timestamp matches the trade's exit_at (bookkeeping sanity)

Read-only; prints a per-check verdict and an overall PASS/FAIL.

Run from the repo root:
    python 06_RESEARCH/scripts/phase_b_sl_first_check.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

from smc.data.parquet_loader import load_ohlcv_parquet  # noqa: E402

RESULTS = REPO_ROOT / "06_RESEARCH" / "results"
DATA = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"

EPS = 1e-9  # price comparisons in gold (~3800); float-safe tolerance


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    df = load_ohlcv_parquet(DATA)  # list[smc.core.candle.Candle]
    candles = {str(c.timestamp): (float(c.open), float(c.high), float(c.low), float(c.close))
               for c in df}

    with open(RESULTS / "phase_b_run1" / "trades.csv", encoding="utf-8", newline="") as fh:
        trades = list(csv.DictReader(fh))

    fails: list[str] = []
    ambiguous_resolved_sl = 0
    kinds: dict[str, int] = {}

    for t in trades:
        tid = t["ticket"]
        kind = t["close_kind"]
        kinds[kind] = kinds.get(kind, 0) + 1

        entry = float(t["entry_price"])
        exit_ = float(t["exit_price"])
        sl = float(t["sl"]) if t["sl"] else None
        tp = float(t["tp"]) if t["tp"] else None
        long_dir = t["direction"] == "long"

        # 4. exit bar exists and is the recorded bar
        ts = t["exit_at"]
        if ts not in candles:
            fails.append(f"ticket {tid}: exit bar {ts} not in canonical series")
            continue
        o, h, l, c = candles[ts]

        # 1/2. price integrity per close kind
        if sl is not None and abs(exit_ - sl) < EPS:
            sl_hit = True
        else:
            sl_hit = (l - EPS <= sl <= h + EPS) if sl is not None else False
        tp_hit = (l - EPS <= tp <= h + EPS) if tp is not None else False

        if kind == "stop_loss" and sl is not None and abs(exit_ - sl) > EPS:
            fails.append(f"ticket {tid}: stop_loss close at {exit_} != SL {sl}")
        if kind == "take_profit" and tp is not None and abs(exit_ - tp) > EPS:
            fails.append(f"ticket {tid}: take_profit close at {exit_} != TP {tp}")

        # 3. same-bar SL-vs-TP ambiguity -> SL-first
        if sl_hit and tp_hit:
            ambiguous_resolved_sl += 1
            if abs(exit_ - (sl if sl is not None else exit_)) > EPS:
                fails.append(
                    f"ticket {tid}: AMBIGUOUS bar (SL {sl} and TP {tp} both in "
                    f"[{l}, {h}]) resolved at {exit_} — violates SL-first")

    print(f"trades checked: {len(trades)}")
    print(f"close kinds: {kinds}")
    print(f"ambiguous same-bar SL/TP bars (resolved SL-first): {ambiguous_resolved_sl}")
    if fails:
        print("FAILURES:")
        for f in fails:
            print(f"  - {f}")
        print("SPOT-CHECK: FAIL")
        return 1
    print("SPOT-CHECK: PASS (all trades, all checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
