"""Export/identity patch verification (Track R export item).

Short deterministic window proving the new identity fields reach the trade
export non-empty on real data. Mirrors the phase_b per-bar wiring
(DetectionDriver validate -> arm ONLY new POIs -> adapter -> BacktestRunner)
plus the new seam: adapter.note_route_context fed from each window's driver
results + displacement attribution (the same calls the live loop makes).

Window: 2026-... resolved at runtime — tries 2025-10-01..08, widens to
2025-10-01..15 when the first window yields no closed trade.

Asserts (fail loudly otherwise):
  - >= 1 closed trade with non-empty model_tags
  - >= 1 closed trade with disp_magnitude_atr not None
  - >= 1 closed trade with a PASS-prefixed pillar_path
Prints three sample exported rows for the patch note.

Frozen config mirrors phase_b (equity/risk/spread/sessions/timeframe M1).
No thresholds touched; the seam only ADDS log fields.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

from smc.backtest.bar_loop import BarLoop  # noqa: E402
from smc.backtest.data_feed import CandleSeries  # noqa: E402
from smc.backtest.export import to_csv, to_json  # noqa: E402
from smc.backtest.orders import PendingOrderBook  # noqa: E402
from smc.backtest.pipeline_adapter import PipelineAdapter  # noqa: E402
from smc.backtest.pipeline_bridge import pillar_path_summary  # noqa: E402
from smc.backtest.positions import PositionStore  # noqa: E402
from smc.backtest.reports import build_report  # noqa: E402
from smc.backtest.runner import BacktestRunner, RunnerConfig  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402
from smc.orchestration.detection_driver import DetectionDriver  # noqa: E402
from smc.orchestration.engine import PipelineEngine  # noqa: E402
from smc.risk.risk_engine import RiskEngine  # noqa: E402
from smc.utils.timestamps import Session  # noqa: E402

TF = Timeframe.M1
WINDOWS = [("2025-10-01", "2025-10-08"), ("2025-10-01", "2025-10-15")]
OUT_ROOT = REPO_ROOT / "06_RESEARCH" / "results" / "export_patch_verify"


def run_window(from_ts: str, to_ts: str, tag: str) -> dict:
    from smc.data.parquet_loader import load_ohlcv_parquet

    start = datetime.strptime(from_ts, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = (datetime.strptime(to_ts, "%Y-%m-%d").replace(tzinfo=timezone.utc)
           + timedelta(days=1) - timedelta(minutes=1))
    all_candles = load_ohlcv_parquet(REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet")
    candles = [c for c in all_candles if start <= c.timestamp <= end]
    assert len(candles) > 50, "window too small"

    engine = PipelineEngine()
    driver = DetectionDriver(TF)
    adapter = PipelineAdapter(engine, timeframe=TF)
    adapter.set_candles(candles)
    runner = BacktestRunner(
        risk_engine=RiskEngine(), order_book=PendingOrderBook(),
        position_store=PositionStore(),
        config=RunnerConfig(equity=10_000.0, risk_fraction=0.01,
                            pip_value_per_lot=10.0, min_lots=0.01,
                            lot_step=0.01, spread_price=0.0, news_events=[],
                            allowed_sessions=(Session.ASIA, Session.LONDON,
                                              Session.NEW_YORK),
                            timeframe=TF),
    )
    adapter.attach(runner)
    window_bars = 2880

    class Cycle:
        def __init__(self, inner):
            self.inner = inner

        def on_bar(self, bar, bar_index, clock) -> None:
            window = candles[max(0, bar_index - window_bars + 1): bar_index + 1]
            passed, results, run, _skipped, detected = driver.validate_window(
                window, engine=engine, merge_first=True)
            # New seam (mirrors LiveLoop._arm_new_pois): retain route-time
            # identity context for newly-passed POIs before arming.
            disp_map = driver.attribute_displacement(detected, run)
            results_by_id = {r.poi.id: r for r in results}
            for poi in passed:
                if engine.episode(poi) is None:
                    res = results_by_id.get(poi.id)
                    adapter.note_route_context(
                        poi.id, displacement=disp_map.get(poi.id),
                        pillar_path=(pillar_path_summary(res)
                                     if res is not None else None))
                    engine.arm_at(poi, arm_bar=bar_index)
            self.inner.on_bar(bar, bar_index, clock)

    stats = BarLoop(CandleSeries(candles, TF), Cycle(runner)).run()
    report = build_report(runner.result())
    out = OUT_ROOT / tag
    out.mkdir(parents=True, exist_ok=True)
    to_csv(report, out / "trades.csv")
    to_json(report, out / "report.json")
    return {"out": str(out), "bars": stats.bars_processed,
            "trades": report.trades}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", default=0, type=int)
    args = ap.parse_args()
    for i in range(args.window, len(WINDOWS)):
        res = run_window(*WINDOWS[i], tag=f"verify_w{i}")
        n = len(res["trades"])
        print(f"[verify] window {WINDOWS[i]}: {res['bars']} bars, {n} trades",
              flush=True)
        if n == 0:
            continue
        tags = sum(1 for t in res["trades"] if t.model_tags)
        disp = sum(1 for t in res["trades"]
                   if t.disp_magnitude_atr is not None)
        pillar = sum(1 for t in res["trades"]
                     if (t.pillar_path or "").startswith("PASS:"))
        print(f"[verify] non-empty model_tags={tags} disp={disp} "
              f"pillar_PASS={pillar} / {n}", flush=True)
        for t in res["trades"][:3]:
            print(f"[verify] row ticket={t.ticket} trigger={t.trigger} "
                  f"models={'+'.join(t.model_tags) if t.model_tags else ''} "
                  f"pillar={t.pillar_path} disp_atr={t.disp_magnitude_atr} "
                  f"pnl={t.pnl}", flush=True)
        assert tags > 0, "no trade carried model_tags"
        assert disp > 0, "no trade carried disp_magnitude_atr"
        assert pillar > 0, "no trade carried a PASS pillar_path"
        print(f"[verify] PASS — artifacts in {res['out']}", flush=True)
        return 0
    print("[verify] FAIL — no window produced a closed trade", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
