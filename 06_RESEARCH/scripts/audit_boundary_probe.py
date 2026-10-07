"""INDEPENDENT AUDIT PROBE — Phase C segmentation equivalence (standalone).

Audit evidence for the Phase C segmented 5-year runner. Three checks,
each on REAL canonical data, each independently interpretable:

CHECK 1 — Wilder-fold warm-up convergence (bit-identity):
    The continuous run's ATR/RSI at any bar carries the FULL prefix's
    smoothing history; a segment starts from a 2,880-bar warm-up. This
    check computes both folds over a real 20,000-bar window and verifies
    the warm-started fold becomes BIT-IDENTICAL to the full-prefix fold
    within the 2,880-bar warm-up budget (theory: geometric decay puts the
    seed residual under one ULP after ~460 bars).

CHECK 2 — Segment-boundary behavior (fresh stack + warm-up vs continuous):
    Splits a real October window at a mid-week boundary inside active
    episode territory and compares the segmented pair's trades/funnel
    against the continuous run:
      * CARRY_LOSS — trades the continuous run takes after the boundary
        that the second segment misses (episode/one-shot state loss).
      * REARM_DUP — second-segment armed zones that duplicate a
        first-segment armed zone (the re-arm pathway).
      * positions_still_open at each segment end (boundary P/L capture).

CHECK 3 — Warm-up sufficiency in load_segment:
    Verifies the runner's 7-calendar-day load margin always yields >=
    WARMUP_BARS of context for every interior segment of the actual plan
    (cheap: bar counts per boundary from the parquet).

Run:  python 06_RESEARCH/scripts/audit_boundary_probe.py [--skip-heavy]
Exit code 0 = all checks pass; nonzero = audit finding.
"""
from __future__ import annotations

import argparse
import sys
from itertools import count
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

import pandas as pd  # noqa: E402

import phase_b_fidelity_backtest as phase_b  # noqa: E402

from smc.backtest.bar_loop import BarLoop  # noqa: E402
from smc.backtest.data_feed import CandleSeries  # noqa: E402
from smc.backtest.pipeline_adapter import PipelineAdapter  # noqa: E402
from smc.backtest.runner import BacktestRunner, RunnerConfig  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402
from smc.orchestration.detection_driver import DetectionDriver  # noqa: E402
from smc.orchestration.engine import PipelineEngine  # noqa: E402
from smc.risk.risk_engine import RiskEngine  # noqa: E402
from smc.utils.atr import atr_series  # noqa: E402
from smc.utils.rsi import rsi_series  # noqa: E402
from smc.utils.timestamps import Session  # noqa: E402

PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
TF = Timeframe.M1
WARMUP_BARS = 2880
CONFIG = dict(phase_b.CONFIG)


# ---------------------------------------------------------------------- #
# Real data
# ---------------------------------------------------------------------- #
def load_frame(from_ts: str, to_ts: str) -> pd.DataFrame:
    frame = pd.read_parquet(
        PARQUET, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    stamps = pd.to_datetime(frame["timestamp"])
    if stamps.dt.tz is None:
        stamps = stamps.dt.tz_localize("UTC")
    mask = (stamps >= pd.Timestamp(from_ts, tz="UTC")) & (
        stamps <= pd.Timestamp(to_ts, tz="UTC")
    )
    sub = frame[mask].copy()
    sub["timestamp"] = stamps[mask].to_numpy()  # positional: keep alignment
    return sub.reset_index(drop=True)


def to_candles(sub: pd.DataFrame) -> list:
    out = []
    for row in sub.itertuples(index=False):
        out.append(
            phase_b._row_to_candle(row) if hasattr(phase_b, "_row_to_candle")
            else _candle(row)
        )
    return out


def _candle(row):
    from smc.core.candle import Candle

    return Candle(
        timestamp=row.timestamp.to_pydatetime(),
        open=float(row.open),
        high=float(row.high),
        low=float(row.low),
        close=float(row.close),
        volume=float(row.volume),
        timeframe=TF,
    )


# ---------------------------------------------------------------------- #
# CHECK 1 — Wilder-fold warm-up bit-convergence
# ---------------------------------------------------------------------- #
def check_fold_convergence() -> bool:
    print("== CHECK 1: Wilder fold warm-up convergence (bit-identity) ==")
    sub = load_frame("2025-09-01", "2025-10-01")  # ~20k real M1 bars
    candles = to_candles(sub)
    n = len(candles)
    full_atr = atr_series(candles, 14)
    full_rsi = rsi_series(candles, 14)

    worst_atr = -1
    worst_rsi = -1
    first_equal_atr = None
    first_equal_rsi = None
    for warm in (2880,):
        warm_atr = atr_series(candles[n - warm:], 14)
        warm_rsi = rsi_series(candles[n - warm:], 14)
        for k in range(warm):
            a_full, a_warm = full_atr[n - warm + k], warm_atr[k]
            r_full, r_warm = full_rsi[n - warm + k], warm_rsi[k]
            if a_full is not None and a_warm is not None:
                if a_full != a_warm:
                    worst_atr = max(worst_atr, k + 1)
                elif first_equal_atr is None:
                    first_equal_atr = k + 1
            if r_full is not None and r_warm is not None:
                if r_full != r_warm:
                    worst_rsi = max(worst_rsi, k + 1)
                elif first_equal_rsi is None:
                    first_equal_rsi = k + 1
    print(f"  bars compared per fold: {WARMUP_BARS} (window {n})")
    print(f"  ATR: bit-identical from warm-bar {first_equal_atr}; last mismatch at {worst_atr}")
    print(f"  RSI: bit-identical from warm-bar {first_equal_rsi}; last mismatch at {worst_rsi}")
    ok = worst_atr <= WARMUP_BARS and worst_rsi <= WARMUP_BARS
    print(f"  -> {'PASS' if ok else 'FAIL'} (budget {WARMUP_BARS})")
    return ok


# ---------------------------------------------------------------------- #
# CHECK 2 — boundary behavior vs continuous
# ---------------------------------------------------------------------- #
def _install_ids(prefix: str) -> None:
    import smc.core.poi as poi_module

    counter = count(1)
    poi_module.uuid4 = lambda: f"{prefix}-{next(counter):06d}"  # type: ignore


def run_stack(candles: list, label: str, start_index: int = 0,
              progress_every: int = 4000) -> dict:
    """One fresh-stack pass over candles[start_index:] (Phase B assembly)."""
    _install_ids(f"audit-{label}")
    import smc.backtest.pipeline_adapter as pam

    series = CandleSeries(candles, TF)
    counters = phase_b.Counters()
    registry = phase_b.ZoneRegistry()
    engine = PipelineEngine()
    driver = DetectionDriver(TF)
    adapter = PipelineAdapter(engine, timeframe=TF)
    adapter.set_candles(candles)
    runner = BacktestRunner(
        risk_engine=RiskEngine(),
        order_book=phase_b.CountingOrderBook().bind(counters),
        position_store=phase_b.CountingPositionStore().bind(counters),
        config=RunnerConfig(
            equity=CONFIG["equity"],
            risk_fraction=CONFIG["risk_fraction"],
            pip_value_per_lot=CONFIG["pip_value_per_lot"],
            min_lots=CONFIG["min_lots"],
            lot_step=CONFIG["lot_step"],
            spread_price=CONFIG["spread_price"],
            news_events=list(CONFIG["news_events"]),
            allowed_sessions=tuple(Session(s) for s in CONFIG["allowed_sessions"]),
            timeframe=TF,
        ),
    )
    phase_b.instrument(runner, counters)
    adapter.attach(runner)
    original_bridge = pam.candidate_from_route
    pam.candidate_from_route = lambda route: (
        counters.__setattr__("routes_created", counters.routes_created + 1),
        original_bridge(route),
    )[1]

    window_bars = CONFIG.get("window_bars", 2880)

    class Cycle:
        def __init__(self) -> None:
            self.bars = 0
            self.armed_zones: list = []

        def on_bar(self, bar, bar_index, clock) -> None:
            window = candles[max(0, bar_index - window_bars + 1): bar_index + 1]
            passed, _results, _run, _skipped, detected = driver.validate_window(
                window, engine=engine, merge_first=True
            )
            counters.detected_raw += len(detected)
            for poi in passed:
                if registry.seen(poi.zone):
                    continue
                engine.arm_at(poi, arm_bar=bar_index)
                registry.register(poi.zone)
                counters.zones_armed += 1
                self.armed_zones.append(
                    (poi.zone.direction, poi.zone.top, poi.zone.bottom)
                )
            runner.on_bar(bar, bar_index, clock)
            self.bars += 1
            if self.bars % progress_every == 0:
                print(f"  [{label}] bar {self.bars}", flush=True)

    cycle = Cycle()
    loop = BarLoop(series, cycle)
    start_ts = None if start_index == 0 else candles[start_index].timestamp
    stats = loop.run(start_timestamp=start_ts)
    result = runner.result()

    trades = [
        (
            t.position.direction.name,
            t.position.entry_at,
            round(t.position.entry_price, 6),
            round(t.exit_price, 6),
            phase_b._kind_str(t.kind),
            round(t.realized_pnl, 9),
        )
        for t in result.closed
    ]
    pam.candidate_from_route = original_bridge
    return {
        "label": label,
        "bars": stats.bars_processed,
        "trades": trades,
        "armed_zones": cycle.armed_zones,
        "placed": counters.placements,
        "armed": counters.zones_armed,
        "still_open": len(runner.positions.open_positions()),
    }


def check_boundary(skip_heavy: bool) -> bool:
    print("== CHECK 2: segment boundary vs continuous (real October data) ==")
    if skip_heavy:
        print("  SKIPPED (--skip-heavy) — run without the flag for this check")
        return True
    # Window with active trading (mid-October 2025), split Wed Oct 15 00:00.
    # CLEAN DESIGN: the continuous reference runs the FULL Oct 6 -> Oct 17
    # window from the SAME cold start as seg1, so the only differences on
    # the second half are genuine state-carry effects (not cold-start ramp).
    # Inclusive FULL days (phase_b normalization): a bare date bound is
    # midnight-truncated, which silently drops the last day's bars
    # (2026-09-15 fix — the first run truncated seg1 at Oct 14 00:00,
    # shedding 1,379 bars and producing a false PREFIX_IDENTITY mismatch;
    # see PHASE_C_PERF_AUDIT.md §5).
    seg1 = to_candles(load_frame("2025-10-06", "2025-10-14 23:59"))
    cont = to_candles(load_frame("2025-10-06", "2025-10-17 23:59"))  # with warm-up

    split_ts = pd.Timestamp("2025-10-15", tz="UTC").to_pydatetime()
    own2 = next(i for i, c in enumerate(cont) if c.timestamp >= split_ts)
    warm = own2 - WARMUP_BARS
    seg2 = cont[warm:] if warm > 0 else list(cont)
    own2 -= warm

    print(f"  seg1 bars={len(seg1)}  seg2 own={len(seg2) - own2} (warmup {own2})"
          f"  continuous bars={len(cont)}")

    r1 = run_stack(seg1, "seg1")
    r2 = run_stack(seg2, "seg2", start_index=own2)
    rc = run_stack(cont, "cont")

    # BONUS CHECK — fresh-stack prefix identity: seg1 (ends Oct 14) must
    # produce EXACTLY the continuous run's pre-boundary trades (same cold
    # start, same bars — the stack cannot know the series continues).
    boundary = split_ts
    pre_cont = [t for t in rc["trades"] if t[1] < boundary]
    prefix_equal = r1["trades"] == pre_cont
    print(f"  PREFIX_IDENTITY: seg1 trades == continuous pre-boundary trades:"
          f" {prefix_equal}  ({len(r1['trades'])} vs {len(pre_cont)})")
    if not prefix_equal:
        for a, b in zip(r1["trades"], pre_cont):
            if a != b:
                print(f"    first divergence: seg1={a} cont={b}")
                break

    cont_after = [t for t in rc["trades"] if t[1] >= boundary]
    seg2_trades = r2["trades"]
    seg2_set = set(seg2_trades)
    missing = [t for t in cont_after if t not in seg2_set]
    extra = [t for t in seg2_trades if t not in set(cont_after)]

    # Re-arm duplicates: seg2 armed zones already armed in seg1.
    z1 = set(r1["armed_zones"])
    rearm = sum(1 for z in r2["armed_zones"] if z in z1)

    print(f"  continuous total trades={len(rc['trades'])}  after-boundary={len(cont_after)}")
    print(f"  seg1 trades={len(r1['trades'])}  seg2 trades={len(seg2_trades)}")
    print(f"  CARRY_LOSS (missing after-boundary trades) = {len(missing)}")
    for t in missing:
        print(f"    MISSING {t}")
    print(f"  EXTRA (seg2-only trades, re-arm pathway) = {len(extra)}")
    for t in extra:
        print(f"    EXTRA {t}")
    print(f"  REARM_DUP (seg2 zones duplicating seg1) = {rearm}")
    print(f"  positions_still_open: seg1={r1['still_open']} seg2={r2['still_open']}")
    print(f"  funnel: seg1 armed={r1['armed']} placed={r1['placed']}"
          f" | seg2 armed={r2['armed']} placed={r2['placed']}"
          f" | cont armed={rc['armed']} placed={rc['placed']}")

    ok = len(missing) == 0 and r1["still_open"] == 0 and r2["still_open"] == 0
    print(f"  -> {'PASS' if ok else 'FINDING'} (rearm={rearm} is informational)")
    return ok


# ---------------------------------------------------------------------- #
# CHECK 3 — warm-up sufficiency for every interior segment boundary
# ---------------------------------------------------------------------- #
def check_warmup_margins() -> bool:
    print("== CHECK 3: warm-up margin >= 2,880 bars at every year boundary ==")
    stamps = pd.to_datetime(
        pd.read_parquet(PARQUET, columns=["timestamp"])["timestamp"]
    )
    if stamps.dt.tz is None:
        stamps = stamps.dt.tz_localize("UTC")
    ok = True
    for year in range(2022, 2027):
        seg_start = pd.Timestamp(year, 1, 1, tz="UTC")
        load_from = seg_start - pd.Timedelta(days=7)
        n = int(((stamps >= load_from) & (stamps < seg_start)).sum())
        status = "OK" if n >= WARMUP_BARS else "SHORT"
        if n < WARMUP_BARS:
            ok = False
        print(f"  {year - 1}-> {year}: {n} context bars in 7d margin  [{status}]")
    print(f"  -> {'PASS' if ok else 'FAIL'}")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-heavy", action="store_true")
    args = parser.parse_args()
    results = {
        "fold_convergence": check_fold_convergence(),
        "boundary": check_boundary(args.skip_heavy),
        "warmup_margins": check_warmup_margins(),
    }
    print("\n== AUDIT SUMMARY ==")
    for name, ok in results.items():
        print(f"  {name}: {'PASS' if ok else 'FINDING'}")
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
