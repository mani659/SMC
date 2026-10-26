from smc.config.timeframe import Timeframe
from smc.dumb.mtf import DumbMtfEpisodeKey, DumbMtfStateMachine, DumbMtfStatus


def _key(tf=Timeframe.H4, poi="h4-a", event="touch-a"):
    return DumbMtfEpisodeKey("XAUUSD", "LONG", tf, poi, event)


def test_h4_uses_m5_as_the_single_clock_owner():
    machine = DumbMtfStateMachine()
    episode, created = machine.start_primary(_key(), clock_bar=10)

    assert created
    assert episode.policy.clock_timeframe is Timeframe.M5
    assert episode.policy.confirmation_timeframes == (Timeframe.M5, Timeframe.M15)


def test_primary_expires_after_six_inclusive_clock_bars_then_fallback_only():
    machine = DumbMtfStateMachine()
    episode, _ = machine.start_primary(_key(), clock_bar=10)
    machine.advance_clock(Timeframe.M5, 16)
    assert episode.status is DumbMtfStatus.IN_ZONE_PRIMARY

    machine.advance_clock(Timeframe.M5, 17)
    assert episode.status is DumbMtfStatus.BOUNDARY_FALLBACK
    assert "EXPIRED_NO_ENTRY" in episode.history
    machine.confirm(episode.episode_id, Timeframe.M15, "too-early")
    assert episode.status is DumbMtfStatus.BOUNDARY_FALLBACK


def test_fallback_confirms_only_after_boundary_sweep_and_expires_after_16_bars():
    machine = DumbMtfStateMachine()
    episode, _ = machine.start_primary(_key(), clock_bar=0)
    machine.advance_clock(Timeframe.M5, 7)
    machine.record_boundary_sweep(episode.episode_id, clock_bar=7)
    machine.confirm(episode.episode_id, Timeframe.M15, "m15-route")

    assert episode.status is DumbMtfStatus.WON
    assert episode.winner_timeframe is Timeframe.M15

    later, _ = machine.start_primary(_key(poi="h4-b"), clock_bar=0)
    machine.advance_clock(Timeframe.M5, 7)
    machine.record_boundary_sweep(later.episode_id, clock_bar=7)
    machine.advance_clock(Timeframe.M5, 23)
    assert later.status is DumbMtfStatus.BOUNDARY_FALLBACK
    machine.advance_clock(Timeframe.M5, 24)
    assert later.status is DumbMtfStatus.EXPIRED_SWEEP_TIMEOUT


def test_distinct_same_timeframe_episodes_and_invalidation_are_independent():
    machine = DumbMtfStateMachine()
    first, _ = machine.start_primary(_key(poi="h4-a", event="touch-a"), 0)
    second, _ = machine.start_primary(_key(poi="h4-b", event="touch-b"), 0)
    machine.invalidate(first.episode_id, "close_through")
    machine.confirm(second.episode_id, Timeframe.M5, "m5-route")

    assert first.status is DumbMtfStatus.INVALIDATED_STRUCTURE
    assert second.status is DumbMtfStatus.WON
