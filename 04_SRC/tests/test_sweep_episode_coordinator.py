from datetime import datetime, timedelta, timezone

from smc.config.timeframe import Timeframe
from smc.orchestration.sweep_episode_coordinator import (
    ClosedSweep,
    EpisodeStatus,
    Confirmation,
    SweepEpisodeCoordinator,
    SweepEpisodeKey,
)


T0 = datetime(2026, 10, 25, 10, tzinfo=timezone.utc)


def _sweep(tf, poi="poi-a", at=T0):
    return ClosedSweep(
        SweepEpisodeKey("XAUUSD", "long", tf, poi, at),
        expires_at=at + timedelta(hours=8),
    )


def test_h4_and_h1_sweeps_are_independent_episodes():
    coordinator = SweepEpisodeCoordinator()
    h4, h4_new = coordinator.create_episode(_sweep(Timeframe.H4))
    h1, h1_new = coordinator.create_episode(_sweep(Timeframe.H1))

    assert h4_new and h1_new
    assert h4.episode_id != h1.episode_id
    assert len(coordinator.episodes()) == 2


def test_only_the_exact_source_event_is_deduplicated():
    coordinator = SweepEpisodeCoordinator()
    first, is_new = coordinator.create_episode(_sweep(Timeframe.H1))
    duplicate, duplicate_new = coordinator.create_episode(_sweep(Timeframe.H1))
    later, later_new = coordinator.create_episode(
        _sweep(Timeframe.H1, poi="poi-b", at=T0 + timedelta(hours=1))
    )

    assert is_new and not duplicate_new and later_new
    assert first is duplicate
    assert later.episode_id != first.episode_id


def test_h4_m5_m15_same_timestamp_uses_lower_timeframe_tie_break():
    coordinator = SweepEpisodeCoordinator()
    episode, _ = coordinator.create_episode(_sweep(Timeframe.H4))
    at = T0 + timedelta(minutes=30)

    winners = coordinator.resolve_confirmations([
        Confirmation(episode.episode_id, Timeframe.M15, at, "m15-route"),
        Confirmation(episode.episode_id, Timeframe.M5, at, "m5-route"),
    ])

    assert winners == [Confirmation(episode.episode_id, Timeframe.M5, at, "m5-route")]
    assert episode.status is EpisodeStatus.WON
    assert episode.winner is not None and episode.winner.timeframe is Timeframe.M5


def test_ineligible_confirmation_cannot_win_an_episode():
    coordinator = SweepEpisodeCoordinator()
    episode, _ = coordinator.create_episode(_sweep(Timeframe.M15))

    winners = coordinator.resolve_confirmations([
        Confirmation(episode.episode_id, Timeframe.M5, T0 + timedelta(minutes=5), "bad"),
    ])

    assert winners == []
    assert episode.status is EpisodeStatus.ACTIVE
    assert "ignored_ineligible_confirmation_tf" in episode.decisions


def test_expired_episode_cannot_win():
    coordinator = SweepEpisodeCoordinator()
    sweep = ClosedSweep(
        SweepEpisodeKey("XAUUSD", "short", Timeframe.H4, "poi-a", T0),
        expires_at=T0 + timedelta(minutes=10),
    )
    episode, _ = coordinator.create_episode(sweep)

    winners = coordinator.resolve_confirmations([
        Confirmation(episode.episode_id, Timeframe.M5, T0 + timedelta(minutes=11), "late"),
    ])

    assert winners == []
    assert episode.status is EpisodeStatus.EXPIRED
