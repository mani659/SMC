"""Phase 0 + F1 + F2 closure — information-set fixes (Architect approved).

Locks the two contracts the 2026-11-09 audit found broken:

F1 (closed-bar HTF): a detection input is eligible only when it has CLOSED
(``timestamp + timeframe length <= as_of``). The runtime owns the trim, so
research, paper and live cannot disagree; a still-forming HTF bar can never
mint a zone. The pre-F1 cut (``timestamp <= as_of``) included the forming bar,
which in a resampled historical series is COMPLETE — up to one full future HTF
bar of information.

F2 (confirmation completeness): every eligible confirmation bar of a batch is
evaluated in ascending close order (locked policy: the FIRST valid
confirmation wins), the winner across a tier's confirmation TFs is the
EARLIEST completion instant (tie → lower TF → route id), and a confirmation
inside the one-shot window only. The pre-F2 branch evaluated just the batch
tail (M5 sampled 1-in-3, M1 1-in-15 on batched feeds).

Measurement only — no thresholds, tiers, triggers or OPT-B behaviour change.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.orchestration import multi_tf_runtime as runtime_module
from smc.orchestration.engine import PipelineEngine
from smc.orchestration.multi_tf import MultiTFDriverResult
from smc.orchestration.multi_tf_runtime import (
    MultiTFProductRuntime,
    build_htf_prefixes,
)
from smc.orchestration.product_menu_mtf import (
    MenuEpisode,
    ProductMenuEngine,
    confirmation_order_key,
)

T0 = datetime(2024, 4, 1, 0, 0, tzinfo=timezone.utc)


def _bars(tf: Timeframe, n: int, start: datetime = T0) -> list[Candle]:
    step = timedelta(minutes=tf.minutes)
    return [
        Candle(
            timestamp=start + step * i,
            open=100.0, high=101.0, low=99.0, close=100.0,
            volume=1.0, timeframe=tf,
        )
        for i in range(n)
    ]


def _closes(series: list[Candle]) -> list[datetime]:
    return [b.timestamp + timedelta(minutes=b.timeframe.minutes) for b in series]


# ---------------------------------------------------------------------- #
# F1 — closed-bar prefixes
# ---------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "tf", [Timeframe.D1, Timeframe.H4, Timeframe.H1, Timeframe.M15, Timeframe.M5]
)
def test_prefix_never_includes_an_unclosed_bar(tf):
    series = _bars(tf, 40)
    # Sweep the decision instant across the whole window, including bar opens,
    # mid-bar, and exact closes.
    for offset_min in (0, 1, 7, 13, 29, 30, 47, 59, 60, 61, 119):
        as_of = T0 + timedelta(minutes=offset_min)
        prefix = build_htf_prefixes({tf: series}, as_of)[tf]
        for bar in prefix:
            closes_at = bar.timestamp + timedelta(minutes=tf.minutes)
            assert closes_at <= as_of, (
                f"{tf.name} prefix delivered a bar that had not closed "
                f"({closes_at} > {as_of})"
            )


def test_prefix_excludes_the_forming_bar_at_a_midbar_instant():
    """The exact pre-F1 failure: an intra-day as_of must not see the day's bar."""
    d1 = _bars(Timeframe.D1, 30)
    forming = d1[10]                       # 2024-04-11: the day in progress
    as_of = forming.timestamp + timedelta(hours=5)
    prefix = build_htf_prefixes({Timeframe.D1: d1}, as_of)[Timeframe.D1]
    assert forming not in prefix
    assert prefix[-1].timestamp == d1[9].timestamp
    # At that bar's CLOSE it becomes eligible (inclusive).
    at_close = forming.timestamp + timedelta(minutes=Timeframe.D1.minutes)
    prefix2 = build_htf_prefixes({Timeframe.D1: d1}, at_close)[Timeframe.D1]
    assert prefix2[-1].timestamp == forming.timestamp


class _CapturingDriver:
    """Driver stand-in that records the series the runtime actually delivered."""

    captured: dict = {}

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def validate_multi(self, series, engine=None, return_details=False):
        _CapturingDriver.captured = {tf: list(v) for tf, v in series.items()}
        return MultiTFDriverResult(
            per_tf={}, single_tf_detect_exec=False, degraded=False,
            errors={}, details={},
        )


def test_run_batch_trims_to_closed_bars_and_reports_last_closed(monkeypatch):
    """The RUNTIME trims: a raw (forming-bar) series never reaches the driver."""
    monkeypatch.setattr(runtime_module, "MultiTFDetectionDriver", _CapturingDriver)
    h4 = _bars(Timeframe.H4, 30)
    h1 = _bars(Timeframe.H1, 120)
    d1 = _bars(Timeframe.D1, 10)
    as_of = T0 + timedelta(days=3, hours=5)     # mid H4/H1 bar, mid D1 bar

    report = MultiTFProductRuntime(
        detection_timeframes=(Timeframe.D1, Timeframe.H4, Timeframe.H1)
    ).run_batch(
        engine=PipelineEngine(),
        series_by_tf={Timeframe.D1: d1, Timeframe.H4: h4, Timeframe.H1: h1},
        as_of=as_of,
        arm_bar=0,
    )

    for tf, delivered in _CapturingDriver.captured.items():
        assert delivered, f"{tf.name} delivered empty"
        last_close = delivered[-1].timestamp + timedelta(minutes=tf.minutes)
        assert last_close <= as_of
    # The still-forming bar of each TF is absent from what the driver saw.
    assert h4[-1] not in _CapturingDriver.captured[Timeframe.H4]
    assert d1[-1] not in _CapturingDriver.captured[Timeframe.D1]
    # ...so it cannot mint a zone: detection only ever receives closed bars.
    assert set(report.last_closed_ts) == {"D1", "H4", "H1"}
    delivered_h1 = _CapturingDriver.captured[Timeframe.H1][-1]
    assert report.last_closed_ts["H1"] == (
        delivered_h1.timestamp + timedelta(minutes=Timeframe.H1.minutes))
    assert report.summary()["last_closed_ts"]["H1"] == (
        report.last_closed_ts["H1"].isoformat())


# ---------------------------------------------------------------------- #
# F2 — confirmation completeness and cross-TF order
# ---------------------------------------------------------------------- #
def _episode(det: list[Candle], sweep_index: int, tier_det=Timeframe.H4) -> MenuEpisode:
    menu = ProductMenuEngine()
    tier = menu.tier_for(tier_det)
    assert tier is not None
    poi = POI(
        zone=Zone(top=101.0, bottom=99.0, direction=Direction.LONG,
                  timeframe=tier_det),
        models=[ModelType.M1],
    )
    return MenuEpisode(
        episode_id="e1",
        poi=poi,
        tier=tier,
        sweep_index=sweep_index,
        sweep_ts=det[sweep_index].timestamp,
        sweep_close_ts=det[sweep_index].timestamp + timedelta(
            minutes=tier_det.minutes),
    )


class _RouterAt:
    """Returns one route at a chosen confirm index (None everywhere else)."""

    def __init__(self, target_index: int) -> None:
        self.target_index = target_index
        self.seen: list[int] = []

    def evaluate_at(self, poi, series, swings, index, from_index):
        self.seen.append(index)
        if index != self.target_index:
            return None
        return SimpleNamespace(
            route_id=f"route@{index}",
            signal=SimpleNamespace(completion_index=index),
        )


def test_every_new_confirmation_bar_is_evaluated_not_just_the_tail():
    """Batched feed: the early bar must win; the tail must not be the only one."""
    det = _bars(Timeframe.H4, 25)
    m5 = _bars(Timeframe.M5, 400)
    episode = _episode(det, 0)
    menu = ProductMenuEngine()
    menu._series[Timeframe.H4] = list(det)
    menu._confirm[Timeframe.M5] = list(m5)
    menu._closes[Timeframe.M5] = _closes(m5)
    menu._router = _RouterAt(target_index=52)
    menu._swings_for = lambda ctf: []      # no structural swings needed

    route = menu._route_for(episode, Timeframe.M5)

    assert route is not None and route.route_id == "route@52"
    first = next(i for i, c in enumerate(_closes(m5)) if c >= episode.sweep_close_ts)
    assert first < 52
    assert menu._router.seen == list(range(first, 53))   # every bar, in order
    assert menu._counters["confirm_bars_evaluated"] == len(menu._router.seen)
    # Progress is recorded: a second call never re-evaluates bar 52 or earlier.
    seen_before = len(menu._router.seen)
    menu._router.target_index = -1
    assert menu._route_for(episode, Timeframe.M5) is None
    resumed = menu._router.seen[seen_before:]
    assert resumed and min(resumed) > 52


def test_confirmation_after_the_one_shot_window_is_ineligible():
    """Window = ``expiry_bars`` DETECTION bars: later confirmations never count."""
    det = _bars(Timeframe.H4, 60)
    episode = _episode(det, sweep_index=30)
    tier = episode.tier
    end_index = 30 + tier.expiry_bars
    window_end = det[end_index].timestamp + timedelta(minutes=Timeframe.H4.minutes)
    # A confirmation stream long enough to run well past the window.
    m5 = _bars(Timeframe.M5, 4000)
    closes = _closes(m5)
    late = next(i for i, c in enumerate(closes) if c > window_end)
    assert late < len(m5)

    menu = ProductMenuEngine()
    menu._series[Timeframe.H4] = list(det)
    menu._confirm[Timeframe.M5] = list(m5)
    menu._closes[Timeframe.M5] = closes
    menu._router = _RouterAt(target_index=late)
    menu._swings_for = lambda ctf: []

    assert menu._route_for(episode, Timeframe.M5) is None
    assert late not in menu._router.seen
    # ...while a route inside the window is returned.
    first = next(i for i, c in enumerate(closes) if c >= episode.sweep_close_ts)
    assert closes[first] <= window_end
    episode._evaluated.clear()
    menu._router = _RouterAt(target_index=first)
    assert menu._route_for(episode, Timeframe.M5) is not None


def test_old_sweep_cannot_open_an_already_closed_window():
    """Batched/backfilled feed: only sweeps inside the live window may open."""
    det = _bars(Timeframe.H4, 60)
    swept = []
    for i, bar in enumerate(det):
        pierce = i in (5, 55)
        swept.append(Candle(
            timestamp=bar.timestamp, open=100.0, high=101.0,
            low=99.0 if pierce else 99.8, close=100.2, volume=1.0,
            timeframe=Timeframe.H4,
        ))
    menu = ProductMenuEngine()
    poi = POI(
        zone=Zone(top=100.5, bottom=99.5, direction=Direction.LONG,
                  timeframe=Timeframe.H4),
        models=[ModelType.M1],
    )
    assert menu.register_armed(poi, Timeframe.H4) is True

    menu.on_execution_bar({Timeframe.H4: swept}, as_of=_closes(swept)[-1])

    assert menu.sweeps_total == 2              # both zone sweeps were seen
    assert menu.counters()["sweeps_out_of_window"] == 1
    episodes = menu.episodes()
    assert len(episodes) == 1
    assert episodes[0].sweep_index == 55       # the only live-window sweep
    assert episodes[0].status.value == "active"


def test_confirmation_order_key_is_earliest_then_lower_tf_then_route_id():
    early = T0
    late = T0 + timedelta(minutes=5)
    assert confirmation_order_key(early, Timeframe.M15, "b") < \
        confirmation_order_key(late, Timeframe.M5, "a")
    assert confirmation_order_key(early, Timeframe.M1, "z") < \
        confirmation_order_key(early, Timeframe.M5, "a")
    assert confirmation_order_key(early, Timeframe.M5, "a") < \
        confirmation_order_key(early, Timeframe.M5, "b")


def test_cross_tf_winner_is_the_earliest_completion_not_tier_order():
    """H4 tier lists (M5, M15): an earlier M15 completion must win."""
    det = _bars(Timeframe.H4, 25)
    m5 = _bars(Timeframe.M5, 400)
    m15 = _bars(Timeframe.M15, 200)
    episode = _episode(det, 0)
    menu = ProductMenuEngine()
    menu._series[Timeframe.H4] = list(det)
    menu._episodes.append(episode)
    menu._armed[episode.poi_id] = (episode.poi, episode.tier)

    # M5 completes LATE, M15 completes EARLY — both in the same batch.
    m5_ts = _closes(m5)[120]
    m15_ts = _closes(m15)[39]
    assert m15_ts < m5_ts
    routes = {
        Timeframe.M5: SimpleNamespace(
            route_id="m5", signal=SimpleNamespace(completion_index=120)),
        Timeframe.M15: SimpleNamespace(
            route_id="m15", signal=SimpleNamespace(completion_index=39)),
    }

    def fake_route_for(ep, ctf):
        return routes.get(ctf)

    won: list = []
    menu._route_for = fake_route_for
    menu._win = lambda ep, route, ctf: won.append((route.route_id, ctf)) or "WIN"

    winners = menu.on_execution_bar(
        {Timeframe.M5: list(m5), Timeframe.M15: list(m15)},
        as_of=_closes(m5)[-1],
    )

    assert winners == ["WIN"]
    assert won == [("m15", Timeframe.M15)]
