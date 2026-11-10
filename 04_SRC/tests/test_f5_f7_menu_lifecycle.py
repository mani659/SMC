"""F5-F7 menu lifecycle tests (t_arm integrity, §5 reconciliation, retries).

Pins the three lifecycle defects closed in one change:

* F5 — a menu window may only open on a sweep that closed AFTER the POI's arm
  instant (``register_armed(..., armed_ts=...)``). A backfilled/batched feed
  must never attach a pre-arm sweep to a POI that did not exist yet, and a
  missing arm instant is counted, never guessed.
* F6 — the menu evaluates ONLY POIs whose §5 state is live (FRESH / TESTED),
  read from the pipeline's ONE state machine through the wired resolver, and
  drops arming bookkeeping when the engine retires a POI.
* F7 — a confirmed menu winner whose placement is blocked is resubmitted each
  bar until it is accepted, bounded by the menu window itself; the claim is
  released when the window closes unplaced, and every step is counted.

Diagnostic/behavioural tests only — no thresholds, tiers or tiers' TFs move.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from smc.backtest.pipeline_adapter import PipelineAdapter
from smc.backtest.runner import CandidateEntry
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, POIState, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.orchestration.engine import PipelineEngine
from smc.orchestration.product_menu_mtf import (
    MENU_EXPIRY_BARS,
    ProductMenuEngine,
)
from smc.paper.runner import PaperRunner
from smc.triggers.base_trigger import Trigger, TriggerContext, TriggerSignal
from smc.triggers.trigger_router import TriggerRouter

BASE = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
H4_CLOSE = BASE + timedelta(hours=4)
ZONE_LOW = 2490.0
ZONE_HIGH = 2500.0


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
class StubTrigger(Trigger):
    type = TriggerType.A_CHOCH

    def __init__(self, fire: bool = True) -> None:
        self.calls = 0
        self.fire = fire

    def evaluate(self, context: TriggerContext) -> TriggerSignal | None:
        self.calls += 1
        if not self.fire:
            return None
        candle = context.candles[context.bar_index]
        return TriggerSignal(
            trigger=TriggerType.A_CHOCH,
            direction=Direction.LONG,
            entry_price=candle.close + 0.5,
            stop_reference=candle.low - 1.0,
            completion_index=context.bar_index,
            expiry_bars=10,
            detail="stub-fire",
            data={},
        )


def _bar(tf: Timeframe, offset_minutes: float, *, low=2485.0, high=2505.0,
         close=2500.0, open_=2496.0) -> Candle:
    return Candle(
        timestamp=BASE + timedelta(minutes=offset_minutes),
        open=open_, high=high, low=low, close=close, timeframe=tf,
    )


def _sweep(tf: Timeframe, offset_minutes: float = 0.0) -> Candle:
    """LONG sweep of the 2490..2500 demand zone."""
    return _bar(tf, offset_minutes, low=2485.0, high=2498.0, close=2492.0)


def _confirm(tf: Timeframe, offset_minutes: float) -> Candle:
    return _bar(tf, offset_minutes, low=2491.0, high=2499.0, close=2497.0)


def _poi(tf: Timeframe = Timeframe.H4, poi_id: str = "poi-1") -> POI:
    zone = Zone(top=ZONE_HIGH, bottom=ZONE_LOW, direction=Direction.LONG,
                timeframe=tf)
    return POI(
        zone=zone, models=[ModelType.M8], score=3.0, state=POIState.CREATED,
        m8_kind="demand_supply", id=poi_id,
    )


def _menu(*, fire: bool = True) -> ProductMenuEngine:
    engine = ProductMenuEngine(symbol="TEST")
    engine._router = TriggerRouter(triggers=[StubTrigger(fire=fire)])
    return engine


class _RecordingRunner:
    """Runner stub that advertises F7 outcome reporting."""

    supports_candidate_outcomes = True

    def __init__(self) -> None:
        self.submitted: list[CandidateEntry] = []
        self.adapter = None

    def submit_entry(self, candidate: CandidateEntry) -> None:
        self.submitted.append(candidate)

    def set_pipeline_adapter(self, adapter) -> None:
        self.adapter = adapter


def _candidate(poi_id="poi-1", *, window_end_ts=None, sweep_ts=None,
               detection_tf="H4") -> CandidateEntry:
    stamp = {"armed_ts": BASE.isoformat(), "tier": "H4",
             "detection_tf": detection_tf}
    if window_end_ts is not None:
        stamp["window_end_ts"] = window_end_ts.isoformat()
    if sweep_ts is not None:
        stamp["sweep_ts"] = sweep_ts.isoformat()
    return CandidateEntry(
        direction=Direction.LONG,
        entry_price=2495.0,
        sl_price=2489.0,
        poi_id=poi_id,
        route_id="H4:A_CHOCH@0",
        signal_data_json=json.dumps({"product_menu": stamp}),
    )


# --------------------------------------------------------------------------- #
# F5 — t_arm / window integrity
# --------------------------------------------------------------------------- #
def test_sweep_closed_at_or_before_arm_instant_cannot_open_a_window():
    """F5: a pre-arm sweep is refused and counted, never attached."""
    menu = _menu()
    poi = _poi()
    assert menu.register_armed(poi, Timeframe.H4, armed_ts=H4_CLOSE) is True

    # This sweep bar CLOSES exactly at the arm instant → pre-arm.
    menu.on_execution_bar(
        {Timeframe.H4: [_sweep(Timeframe.H4, 0)]}, as_of=H4_CLOSE
    )
    assert menu.active_count() == 0
    assert menu.counters()["sweeps_pre_arm"] == 1
    assert menu.sweeps_total == 0


def test_sweep_closing_after_arm_instant_opens_and_stores_armed_ts():
    """F5: the first post-arm sweep opens, and the episode keeps t_arm."""
    menu = _menu()
    poi = _poi()
    assert menu.register_armed(poi, Timeframe.H4, armed_ts=H4_CLOSE) is True

    menu.on_execution_bar(
        {Timeframe.H4: [_sweep(Timeframe.H4, 0)]}, as_of=H4_CLOSE
    )
    assert menu.active_count() == 0  # still pre-arm

    # A later H4 bar sweeping the same zone closes 08:00 > 04:00 arm instant.
    later = _sweep(Timeframe.H4, 240)
    menu.on_execution_bar({Timeframe.H4: [later]}, as_of=later.timestamp
                          + timedelta(hours=4))
    assert menu.active_count() == 1
    episode = menu._episodes[0]
    assert episode.armed_ts == H4_CLOSE
    assert episode.sweep_ts == later.timestamp


def test_arm_without_timestamp_keeps_guard_inactive_and_is_counted():
    """F5: no arm instant is never guessed — it disables the guard, counted."""
    menu = _menu()
    poi = _poi()
    assert menu.register_armed(poi, Timeframe.H4) is True
    assert menu.counters()["armed_without_ts"] == 1

    # Guard inactive: the old sweep still opens (documented fallback).
    menu.on_execution_bar(
        {Timeframe.H4: [_sweep(Timeframe.H4, 0)]}, as_of=H4_CLOSE
    )
    assert menu.active_count() == 1
    assert menu._episodes[0].armed_ts is None


def test_rearming_adopts_a_late_arm_instant_and_keeps_the_original():
    """F5: idempotent re-arm; the ORIGINAL instant wins, a late one is adopted."""
    menu = _menu()
    poi = _poi()
    menu.register_armed(poi, Timeframe.H4)
    assert menu.register_armed(poi, Timeframe.H4, armed_ts=H4_CLOSE) is True
    assert menu.counters()["armed_without_ts"] == 0
    assert menu._armed["poi-1"][2] == H4_CLOSE

    # A different instant never rewrites the stored one.
    assert menu.register_armed(poi, Timeframe.H4, armed_ts=BASE) is True
    assert menu._armed["poi-1"][2] == H4_CLOSE


def test_arming_book_stores_the_poi_and_tier():
    """F5: ``_armed`` is (poi, tier, armed_ts) — the tuple shape consumers see."""
    menu = _menu()
    poi = _poi()
    menu.register_armed(poi, Timeframe.H4, armed_ts=BASE)
    stored_poi, tier, armed_ts = menu._armed["poi-1"]
    assert stored_poi is poi
    assert tier.name == "H4"
    assert armed_ts == BASE


# --------------------------------------------------------------------------- #
# F6 — §5 reconciliation
# --------------------------------------------------------------------------- #
def test_dead_poi_never_opens_a_window_and_is_counted():
    """F6: a VIOLATED POI is not evaluated — the window never opens."""
    menu = _menu()
    poi = _poi()
    menu.set_state_source(lambda _p: POIState.VIOLATED)
    menu.register_armed(poi, Timeframe.H4, armed_ts=BASE)

    menu.on_execution_bar(
        {Timeframe.H4: [_sweep(Timeframe.H4, 0)]}, as_of=H4_CLOSE
    )
    assert menu.active_count() == 0
    assert menu.sweeps_total == 0
    assert menu.counters()["menu_blocked_by_state"] >= 1


def test_poi_dying_mid_window_blocks_the_confirmation():
    """F6: a POI that dies after arming cannot still win its window."""
    menu = _menu()
    poi = _poi()
    state = {"value": POIState.FRESH}
    menu.set_state_source(lambda _p: state["value"])
    menu.register_armed(poi, Timeframe.H4, armed_ts=BASE)

    menu.on_execution_bar(
        {Timeframe.H4: [_sweep(Timeframe.H4, 0)]}, as_of=H4_CLOSE
    )
    assert menu.active_count() == 1

    state["value"] = POIState.VIOLATED
    confirm = _confirm(Timeframe.M5, 245)
    winners = menu.on_execution_bar(
        {Timeframe.M5: [confirm]}, as_of=confirm.timestamp + timedelta(minutes=5)
    )
    assert winners == []
    assert menu.counters()["menu_blocked_by_state"] >= 1
    assert menu.winners == []


def test_live_poi_still_confirms_with_the_gate_wired():
    """F6 control: FRESH/TESTED POIs are allowed — the gate is not a blanket stop."""
    for allowed in (POIState.FRESH, POIState.TESTED):
        menu = _menu()
        poi = _poi()
        menu.set_state_source(lambda _p, _s=allowed: _s)
        menu.register_armed(poi, Timeframe.H4, armed_ts=BASE)
        menu.on_execution_bar(
            {Timeframe.H4: [_sweep(Timeframe.H4, 0)]}, as_of=H4_CLOSE
        )
        confirm = _confirm(Timeframe.M5, 245)
        winners = menu.on_execution_bar(
            {Timeframe.M5: [confirm]},
            as_of=confirm.timestamp + timedelta(minutes=5),
        )
        assert len(winners) == 1
        assert winners[0].poi_id == "poi-1"


def test_unwired_state_source_leaves_the_gate_off():
    """F6: no resolver (stub/research) → no invented block."""
    menu = _menu()
    poi = _poi()
    menu.register_armed(poi, Timeframe.H4, armed_ts=BASE)
    menu.on_execution_bar(
        {Timeframe.H4: [_sweep(Timeframe.H4, 0)]}, as_of=H4_CLOSE
    )
    assert menu.active_count() == 1
    assert menu.counters()["menu_blocked_by_state"] == 0


def test_faulty_resolver_never_fakes_a_block():
    """F6: a resolver fault degrades to 'unknown', not to a block."""
    menu = _menu()
    poi = _poi()

    def _boom(_poi):
        raise RuntimeError("resolver down")

    menu.set_state_source(_boom)
    assert menu._poi_state(poi) is None
    menu.register_armed(poi, Timeframe.H4, armed_ts=BASE)
    menu.on_execution_bar(
        {Timeframe.H4: [_sweep(Timeframe.H4, 0)]}, as_of=H4_CLOSE
    )
    assert menu.active_count() == 1
    assert menu.counters()["menu_blocked_by_state"] == 0


def test_retire_drops_arming_but_never_revives_a_consumed_poi():
    """F6: retire bounds the arming book; consumed stays one-shot."""
    menu = _menu()
    poi = _poi()
    menu.register_armed(poi, Timeframe.H4, armed_ts=BASE)
    assert menu.counters()["armed_pois"] == 1
    assert menu.retire("poi-1") is True
    assert menu.counters()["armed_pois"] == 0
    assert menu.retire("poi-1") is False

    # A different POI that already won cannot be re-armed by a retire+arm.
    other = _poi(poi_id="poi-2")
    menu.register_armed(other, Timeframe.H4, armed_ts=BASE)
    menu.on_execution_bar(
        {Timeframe.H4: [_sweep(Timeframe.H4, 0)]}, as_of=H4_CLOSE
    )
    confirm = _confirm(Timeframe.M5, 245)
    menu.on_execution_bar(
        {Timeframe.M5: [confirm]}, as_of=confirm.timestamp + timedelta(minutes=5)
    )
    assert len(menu.winners) == 1
    menu.retire("poi-2")
    assert menu.register_armed(other, Timeframe.H4, armed_ts=BASE) is False


def test_adapter_binds_the_pipeline_state_machine_as_the_state_source():
    """F6: exactly ONE §5 store — the pipeline engine's state machine."""
    engine = PipelineEngine()
    menu = _menu()
    PipelineAdapter(engine, timeframe=Timeframe.M5, menu_confirmation=menu)
    assert menu._state_source is not None

    poi = _poi()
    engine.arm_at(poi, 0)
    resolver_state = menu._poi_state(poi)
    assert resolver_state == engine.state_machine.current(poi)
    assert resolver_state in {POIState.FRESH, POIState.TESTED,
                              POIState.CREATED}


def test_adapter_prune_retires_the_menu_arming_record():
    """F6: the engine's prune path is the menu's retire path."""
    engine = PipelineEngine()
    menu = _menu()
    adapter = PipelineAdapter(
        engine, timeframe=Timeframe.M5, menu_confirmation=menu
    )
    poi = _poi()
    menu.register_armed(poi, Timeframe.H4, armed_ts=BASE)
    assert "poi-1" in menu._armed

    engine.prune_terminal = lambda retain=None: ["poi-1"]
    adapter.prune_terminal_pois()
    assert "poi-1" not in menu._armed


# --------------------------------------------------------------------------- #
# F7 — retryable blocked menu winners
# --------------------------------------------------------------------------- #
def test_queue_registers_a_pending_confirmation_with_its_deadline():
    menu = _menu()
    engine = PipelineEngine()
    runner = _RecordingRunner()
    adapter = PipelineAdapter(
        engine, timeframe=Timeframe.M5, menu_confirmation=menu
    )
    adapter.attach(runner)

    deadline = H4_CLOSE + timedelta(hours=20)
    candidate = _candidate(window_end_ts=deadline)
    adapter.queue_menu_candidate(candidate)

    assert adapter.menu_counters()["menu_pending"] == 1
    assert adapter.menu_counters()["menu_submitted"] == 1
    assert adapter._menu_pending["poi-1"]["deadline"] == deadline
    assert len(runner.submitted) == 0  # the bar's cycle owns the first submit

    adapter._resubmit_menu_pending(H4_CLOSE)
    assert len(runner.submitted) == 1
    assert adapter.menu_counters()["menu_resubmitted"] == 0  # first attempt


def test_blocked_winner_is_resubmitted_until_accepted():
    """F7: a risk block no longer destroys the confirmation."""
    menu = _menu()
    engine = PipelineEngine()
    runner = _RecordingRunner()
    adapter = PipelineAdapter(
        engine, timeframe=Timeframe.M5, menu_confirmation=menu
    )
    adapter.attach(runner)

    candidate = _candidate(window_end_ts=H4_CLOSE + timedelta(hours=20))
    adapter.queue_menu_candidate(candidate)

    # The confirmation bar's own cycle submits it once.
    adapter._resubmit_menu_pending(H4_CLOSE)
    assert len(runner.submitted) == 1

    adapter.notify_candidate_outcome(candidate, accepted=False, reason="news")
    counters = adapter.menu_counters()
    assert counters["menu_retry_blocked"] == 1
    assert counters["menu_accepted"] == 0
    assert counters["menu_pending"] == 1

    adapter._resubmit_menu_pending(H4_CLOSE + timedelta(minutes=5))
    assert len(runner.submitted) == 2
    assert adapter.menu_counters()["menu_resubmitted"] == 1

    adapter.notify_candidate_outcome(candidate, accepted=True, reason="placed")
    counters = adapter.menu_counters()
    assert counters["menu_accepted"] == 1
    assert counters["menu_pending"] == 0
    assert adapter._menu_pending == {}


def test_runner_cycle_submits_a_confirmation_at_most_once_per_bar():
    """F7: the queue does not submit, and no bar ever submits twice.

    Mirrors the live ordering: ``_drive_menu_confirmation`` queues the winner
    BEFORE ``run_one_cycle``, and ``generate_candidates`` (which owns the
    submission) runs BEFORE the runner drains its entry queue.
    """

    class _CycleRunner(_RecordingRunner):
        def __init__(self):
            super().__init__()
            self.cycles = 0

        def run_one_cycle(self, bar):
            before = len(self.submitted)
            self.adapter.generate_candidates(bar, self.cycles, bar.timestamp)
            self.cycles += 1
            for cand in self.submitted[before:]:  # the risk gate blocks it
                self.adapter.notify_candidate_outcome(
                    cand, accepted=False, reason="news"
                )

    menu = _menu()
    adapter = PipelineAdapter(
        PipelineEngine(), timeframe=Timeframe.M5, menu_confirmation=menu
    )
    runner = _CycleRunner()
    adapter.attach(runner)

    bar = _bar(Timeframe.M5, 250)
    adapter.queue_menu_candidate(_candidate(
        window_end_ts=H4_CLOSE + timedelta(hours=20)
    ))
    runner.run_one_cycle(bar)
    assert len(runner.submitted) == 1, "queued + first cycle must not double-submit"

    runner.run_one_cycle(_bar(Timeframe.M5, 255))
    assert len(runner.submitted) == 2  # exactly one retry, on the next bar
    counters = adapter.menu_counters()
    assert counters["menu_submitted"] == 1     # confirmations queued
    assert counters["menu_resubmitted"] == 1   # retries submitted
    assert counters["menu_retry_blocked"] == 2  # one block per attempt


def test_expired_window_releases_the_claim_and_counts_it():
    """F7: past the menu window the confirmation dies and the claim frees."""
    menu = _menu()
    engine = PipelineEngine()
    runner = _RecordingRunner()
    adapter = PipelineAdapter(
        engine, timeframe=Timeframe.M5, menu_confirmation=menu
    )
    adapter.attach(runner)

    deadline = H4_CLOSE + timedelta(hours=20)
    candidate = _candidate(window_end_ts=deadline)
    adapter.queue_menu_candidate(candidate)
    adapter._resubmit_menu_pending(H4_CLOSE)
    adapter.notify_candidate_outcome(candidate, accepted=False, reason="breaker")
    assert "poi-1" in adapter._menu_claimed_pois

    adapter._resubmit_menu_pending(deadline + timedelta(minutes=1))
    counters = adapter.menu_counters()
    assert counters["menu_expired_unplaced"] == 1
    assert counters["menu_pending"] == 0
    assert len(runner.submitted) == 1  # no submit past the window
    assert "poi-1" not in adapter._menu_claimed_pois
    assert "poi-1" not in adapter._routed


def test_stub_runner_without_outcome_support_keeps_one_submit_semantics():
    """F7: research submit-captures are untouched (no retry, no counters)."""

    class _StubRunner:
        def __init__(self):
            self.submitted = []

        def submit_entry(self, candidate):
            self.submitted.append(candidate)

        def set_pipeline_adapter(self, adapter):
            pass

    menu = _menu()
    adapter = PipelineAdapter(
        PipelineEngine(), timeframe=Timeframe.M5, menu_confirmation=menu
    )
    runner = _StubRunner()
    adapter.attach(runner)
    candidate = _candidate(window_end_ts=H4_CLOSE)
    adapter.queue_menu_candidate(candidate)
    adapter._resubmit_menu_pending(H4_CLOSE)
    assert len(runner.submitted) == 1
    assert adapter.menu_counters()["menu_pending"] == 0
    assert adapter.menu_counters()["menu_resubmitted"] == 0


def test_no_window_stamp_means_no_retry_and_no_invented_deadline():
    """F7: without a menu window stamp the confirmation is not retried."""
    menu = _menu()
    runner = _RecordingRunner()
    adapter = PipelineAdapter(
        PipelineEngine(), timeframe=Timeframe.M5, menu_confirmation=menu
    )
    adapter.attach(runner)
    candidate = _candidate()  # no window_end_ts, no sweep_ts
    adapter.queue_menu_candidate(candidate)
    assert adapter._menu_pending == {}
    adapter._resubmit_menu_pending(H4_CLOSE)
    assert len(runner.submitted) == 1


def test_deadline_falls_back_to_the_locked_expiry_when_unstamped():
    """F7: sweep_ts + locked expiry over the stamped detection TF."""
    menu = _menu()
    adapter = PipelineAdapter(
        PipelineEngine(), timeframe=Timeframe.M5, menu_confirmation=menu
    )
    candidate = _candidate(sweep_ts=BASE, detection_tf="H4")
    expected = BASE + timedelta(
        minutes=(Timeframe.H4.minutes * MENU_EXPIRY_BARS) + Timeframe.H4.minutes
    )
    assert adapter._menu_deadline(candidate) == expected


def test_dead_poi_pending_is_dropped_by_prune():
    """F7: a retired POI's pending confirmation dies with it (counted)."""
    menu = _menu()
    engine = PipelineEngine()
    runner = _RecordingRunner()
    adapter = PipelineAdapter(
        engine, timeframe=Timeframe.M5, menu_confirmation=menu
    )
    adapter.attach(runner)
    candidate = _candidate(window_end_ts=H4_CLOSE + timedelta(hours=20))
    adapter.queue_menu_candidate(candidate)
    adapter.notify_candidate_outcome(candidate, accepted=False, reason="news")
    assert adapter.menu_counters()["menu_pending"] == 1

    engine.prune_terminal = lambda retain=None: ["poi-1"]
    adapter.prune_terminal_pois()
    counters = adapter.menu_counters()
    assert counters["menu_pending"] == 0
    assert counters["menu_dropped_poi_retired"] == 1
    assert "poi-1" not in adapter._menu_claimed_pois


def test_paper_runner_advertises_and_forwards_outcomes():
    """F7: the live paper runner is the only adapter runner that reports."""
    assert PaperRunner.supports_candidate_outcomes is True

    class _RecordingAdapter:
        def __init__(self):
            self.calls = []

        def notify_candidate_outcome(self, candidate, *, accepted, reason=None):
            self.calls.append((candidate, accepted, reason))

    runner = PaperRunner.__new__(PaperRunner)
    runner.adapter = _RecordingAdapter()
    candidate = _candidate(window_end_ts=H4_CLOSE)
    runner._notify_candidate_outcome(candidate, accepted=False, reason="news")
    runner._notify_candidate_outcome(candidate, accepted=True, reason="dry_run")
    assert runner.adapter.calls == [
        (candidate, False, "news"),
        (candidate, True, "dry_run"),
    ]


def test_paper_runner_notification_is_optional_for_stub_adapters():
    """F7: an adapter without the seam must not raise."""

    class _BareAdapter:
        pass

    runner = PaperRunner.__new__(PaperRunner)
    runner.adapter = _BareAdapter()
    runner._notify_candidate_outcome(_candidate(), accepted=True, reason="dry_run")


def test_winner_stamps_the_window_end_for_the_retry_bound():
    """F5/F7: the winner and its candidate carry the menu window end."""
    menu = _menu()
    poi = _poi()
    menu.register_armed(poi, Timeframe.H4, armed_ts=BASE)
    menu.on_execution_bar(
        {Timeframe.H4: [_sweep(Timeframe.H4, 0)]}, as_of=H4_CLOSE
    )
    confirm = _confirm(Timeframe.M5, 245)
    winners = menu.on_execution_bar(
        {Timeframe.M5: [confirm]}, as_of=confirm.timestamp + timedelta(minutes=5)
    )
    assert len(winners) == 1
    winner = winners[0]
    # No detection bar past the sweep has closed yet → nominal window end
    # (sweep bar close 04:00 + the locked expiry over the H4 detection TF).
    expected = H4_CLOSE + timedelta(
        minutes=Timeframe.H4.minutes * MENU_EXPIRY_BARS
    )
    assert winner.window_end_ts == expected
    payload = json.loads(winner.candidate.signal_data_json)
    assert payload["product_menu"]["window_end_ts"] == expected.isoformat()
    assert payload["product_menu"]["armed_ts"] == BASE.isoformat()
