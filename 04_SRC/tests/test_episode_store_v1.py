"""Tests for EpisodeStore V1 (Section 8 acceptance tests & Section 9a rulings).

Conforming to EPISODE_STORE_DESIGN.md + Architect rulings 2026-10-13.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import pytest

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, POIState
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.orchestration.engine import PipelineEngine, SeekPosture
from smc.orchestration.episode_store import (
    EpisodeEvent,
    EpisodeEventKind,
    EpisodeIdentityKey,
    EpisodeRecord,
    EpisodeState,
    EpisodeStore,
    TERMINAL_STATES,
)
from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime, ZoneDedup


def _make_poi(
    low: float,
    high: float,
    direction: Direction = Direction.LONG,
    tf: Timeframe = Timeframe.H4,
    models: list[ModelType] | None = None,
    m8_kind: str | None = None,
) -> POI:
    zone = Zone(top=high, bottom=low, direction=direction, timeframe=tf)
    p = POI(zone=zone, models=models or [ModelType.M1], m8_kind=m8_kind)
    p.state = POIState.FRESH
    return p


class TestEpisodeStoreIdentityAndRulings:
    """1) Unit tests: identity (H4 != M8<-H4), refinement parent+bounds adopt,
    overlap merge via ZoneDedup rule, EXPIRED_UNARMED transition,
    export stable column order, no decision API that returns 'should_arm'.
    """

    def test_h4_vs_m8_h4_separate_episodes(self):
        """H4 vs M8<-H4: SEPARATE episodes if detection_tf or m8_kind_class differs;
        overlap records related_episode link, never forced merge.
        """
        store = EpisodeStore()
        # Regular H4 POI
        poi_h4 = _make_poi(2000.0, 2010.0, Direction.LONG, Timeframe.H4, models=[ModelType.M1])
        # M8<-H4 POI with same geometry & direction
        poi_m8 = _make_poi(2000.0, 2010.0, Direction.LONG, Timeframe.H4, models=[ModelType.M8], m8_kind="ob")

        ts = datetime(2025, 10, 1, 12, 0, tzinfo=timezone.utc)
        ev1 = store.record_event("detected", poi=poi_h4, ts=ts, bar_index=10, tf="H4")
        ev2 = store.record_event("detected", poi=poi_m8, ts=ts, bar_index=10, tf="H4", m8_kind_class="ob")

        assert ev1.episode_id != ev2.episode_id, "H4 and M8<-H4 must be distinct episodes"
        rec_h4 = store.get(ev1.episode_id)
        rec_m8 = store.get(ev2.episode_id)
        assert rec_h4 is not None and rec_m8 is not None
        assert rec_h4.m8_kind_class == "n/a"
        assert rec_m8.m8_kind_class == "ob"
        # Overlap establishes related_episode link
        assert rec_m8.episode_id in rec_h4.related_episode_ids
        assert rec_h4.episode_id in rec_m8.related_episode_ids

    def test_refinement_parent_and_bounds_adopt(self):
        """Refinement: tighter armed box inside parent geometry = SAME episode;
        adopt armed bounds; parent link mandatory when that happens.
        """
        store = EpisodeStore()
        # Parent census POI: [2000.0, 2020.0]
        parent_poi = _make_poi(2000.0, 2020.0, Direction.LONG, Timeframe.H4)
        ts1 = datetime(2025, 10, 1, 12, 0, tzinfo=timezone.utc)
        store.record_event("detected", poi=parent_poi, ts=ts1, bar_index=10)

        ep = store.get_by_poi(parent_poi.id)
        assert ep is not None
        orig_id = ep.episode_id
        assert ep.zone_low == 2000.0
        assert ep.zone_high == 2020.0

        # Tighter box at arming: [2005.0, 2015.0]
        ts2 = datetime(2025, 10, 1, 13, 0, tzinfo=timezone.utc)
        store.record_event(
            "armed",
            episode_id=orig_id,
            ts=ts2,
            bar_index=15,
            data={
                "zone_low": 2005.0,
                "zone_high": 2015.0,
                "parent_episode_id": orig_id,
            },
        )

        rec = store.get(orig_id)
        assert rec.zone_low == 2005.0
        assert rec.zone_high == 2015.0
        assert rec.refinement is not None
        assert rec.refinement["present"] is True
        assert rec.refinement["parent_bounds"] == (2000.0, 2020.0)
        assert rec.refinement["refined_bounds"] == (2005.0, 2015.0)
        assert rec.parent_episode_id == orig_id
        assert len(rec.bounds_history) == 2

    def test_zonededup_sole_merge_authority_and_suppression(self):
        """ZoneDedup = sole merge authority; store records suppressions as facts."""
        store = EpisodeStore()
        poi1 = _make_poi(2000.0, 2010.0, Direction.LONG, Timeframe.H4)
        poi2 = _make_poi(2005.0, 2015.0, Direction.LONG, Timeframe.H4)  # overlapping same direction

        ts1 = datetime(2025, 10, 1, 10, 0, tzinfo=timezone.utc)
        ev1 = store.record_event("detected", poi=poi1, ts=ts1, bar_index=5)

        # Resolving poi2 against store resolves to same episode because of ZoneDedup overlap
        rec2, is_new = store.resolve_identity(
            direction="LONG",
            detection_tf="H4",
            m8_kind_class="n/a",
            zone_low=2005.0,
            zone_high=2015.0,
            poi_id=poi2.id,
        )
        assert not is_new, "Overlapping same-direction zone must resolve to existing episode"
        assert rec2.episode_id == ev1.episode_id

        # Record suppression as a fact
        ts2 = datetime(2025, 10, 1, 11, 0, tzinfo=timezone.utc)
        store.record_event(
            "suppressed_dedup",
            poi=poi2,
            ts=ts2,
            bar_index=10,
            data={"reason": "ZoneDedup_seen"},
        )
        rec = store.get(ev1.episode_id)
        assert rec.state == EpisodeState.SUPPRESSED_DEDUP
        assert poi2.id in rec.poi_ids

    def test_expired_unarmed_transition(self):
        """EXPIRED_UNARMED = first-class state (bookkeeping)."""
        store = EpisodeStore()
        poi = _make_poi(2000.0, 2010.0, Direction.LONG, Timeframe.H4)
        ts = datetime(2025, 10, 1, 10, 0, tzinfo=timezone.utc)
        store.record_event("validated", poi=poi, ts=ts, bar_index=5)

        ep = store.get_by_poi(poi.id)
        assert ep.state == EpisodeState.VALIDATED

        ts2 = datetime(2025, 10, 1, 12, 0, tzinfo=timezone.utc)
        store.record_event("expired_unarmed", poi=poi, ts=ts2, bar_index=20)
        assert ep.state == EpisodeState.EXPIRED_UNARMED
        assert ep.is_terminal is True
        assert ep.fate == EpisodeState.EXPIRED_UNARMED

    def test_export_stable_column_order(self, tmp_path):
        """Export: to_rows() / write_csv / write_json produce stable column order."""
        store = EpisodeStore()
        poi = _make_poi(2000.0, 2010.0, Direction.LONG, Timeframe.H4)
        ts = datetime(2025, 10, 1, 10, 0, tzinfo=timezone.utc)
        store.record_event("detected", poi=poi, ts=ts, bar_index=5)
        store.record_event("armed", poi=poi, ts=ts, bar_index=6, data={"zone_low": 2000.0, "zone_high": 2010.0})

        csv_file = tmp_path / "episodes.csv"
        json_file = tmp_path / "episodes.json"
        store.write_csv(csv_file)
        store.write_json(json_file)

        assert csv_file.exists()
        assert json_file.exists()

        with open(csv_file, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)
            expected_headers = [
                "episode_id",
                "direction",
                "detection_tf",
                "m8_kind_class",
                "zone_low",
                "zone_high",
                "state",
                "fate",
                "posture",
                "poi_ids",
                "route_ids",
                "parent_episode_id",
                "refinement_present",
                "event_count",
                "arm_t",
                "route_t",
                "place_t",
                "fill_t",
                "close_t",
            ]
            assert headers == expected_headers

        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)
            assert "funnel" in data
            assert "episodes" in data
            assert len(data["episodes"]) == 1

    def test_no_decision_api_that_returns_should_arm(self):
        """Store is append/query infrastructure only. No decision APIs."""
        store = EpisodeStore()
        assert not hasattr(store, "should_arm")
        assert not hasattr(store, "should_route")
        assert not hasattr(store, "should_place")
        assert not hasattr(store, "should_fill")
        assert not hasattr(store, "allow_trade")

    def test_one_shot_invariant_enforced(self):
        """One-shot invariant: at most one route per episode raises if violated."""
        store = EpisodeStore()
        poi = _make_poi(2000.0, 2010.0, Direction.LONG, Timeframe.H4)
        ts = datetime(2025, 10, 1, 10, 0, tzinfo=timezone.utc)
        store.record_event("armed", poi=poi, ts=ts, bar_index=10)
        store.record_event("route", poi=poi, route_id="poi-1:A@15", ts=ts, bar_index=15)

        with pytest.raises(ValueError, match="One-shot invariant violated"):
            store.record_event("route", poi=poi, route_id="poi-1:B@20", ts=ts, bar_index=20)

    def test_no_lookahead_query(self):
        """state_at(key, bar) never reports later facts."""
        store = EpisodeStore()
        poi = _make_poi(2000.0, 2010.0, Direction.LONG, Timeframe.H4)
        ts = datetime(2025, 10, 1, 10, 0, tzinfo=timezone.utc)
        store.record_event("detected", poi=poi, ts=ts, bar_index=5)
        store.record_event("armed", poi=poi, ts=ts, bar_index=10)
        store.record_event("route", poi=poi, route_id="r1", ts=ts, bar_index=15)

        ep = store.get_by_poi(poi.id)
        assert store.state_at(ep.episode_id, 4) is None
        assert store.state_at(ep.episode_id, 5) == EpisodeState.DETECTED
        assert store.state_at(ep.episode_id, 9) == EpisodeState.DETECTED
        assert store.state_at(ep.episode_id, 10) == EpisodeState.ARMED
        assert store.state_at(ep.episode_id, 14) == EpisodeState.ARMED
        assert store.state_at(ep.episode_id, 15) == EpisodeState.ROUTED

    def test_derived_counters_prevent_expired_zero_defect(self):
        """Derived counters: intent_expired_no_reentry count equals event count."""
        store = EpisodeStore()
        poi = _make_poi(2000.0, 2010.0, Direction.LONG, Timeframe.H4)
        ts = datetime(2025, 10, 1, 10, 0, tzinfo=timezone.utc)
        store.record_event("armed", poi=poi, ts=ts, bar_index=5)
        store.record_event("route", poi=poi, route_id="r1", ts=ts, bar_index=6)
        store.record_event("intent_armed", poi=poi, route_id="r1", ts=ts, bar_index=6)
        store.record_event("intent_expired_no_reentry", poi=poi, route_id="r1", ts=ts, bar_index=12)

        f = store.funnel()
        assert f["intent_armed"] == 1
        assert f["intent_expired_no_reentry"] == 1
        ep = store.get_by_poi(poi.id)
        assert ep.fate == EpisodeState.INTENT_EXPIRED


class TestMultiTFProductRuntimeIntegrationHook:
    """Test runtime wiring with EpisodeStore enabled vs disabled."""

    def test_runtime_with_episode_store_records_events(self):
        store = EpisodeStore()
        runtime = MultiTFProductRuntime(allow_single_tf_degraded=True, episode_store=store)
        engine = PipelineEngine(episode_store=store)
        assert runtime.episode_store is store
        assert engine.episode_store is store

    def test_parity_store_enabled_vs_disabled(self):
        """Parity proof: running batch with store enabled vs disabled produces identical reports."""
        from smc.core.candle import Candle

        base_ts = datetime(2025, 10, 1, 0, 0, tzinfo=timezone.utc)
        candles_h4 = [
            Candle(
                timestamp=base_ts + timedelta(hours=i * 4),
                open=2000.0 + i,
                high=2010.0 + i,
                low=1995.0 + i,
                close=2005.0 + i,
                volume=100.0,
            )
            for i in range(20)
        ]
        candles_h1 = [
            Candle(
                timestamp=base_ts + timedelta(hours=i),
                open=2000.0 + (i * 0.25),
                high=2005.0 + (i * 0.25),
                low=1998.0 + (i * 0.25),
                close=2003.0 + (i * 0.25),
                volume=50.0,
            )
            for i in range(80)
        ]
        series = {
            Timeframe.H4: candles_h4,
            Timeframe.H1: candles_h1,
        }

        # Run 1: Store OFF
        engine1 = PipelineEngine()
        runtime1 = MultiTFProductRuntime(allow_single_tf_degraded=False, episode_store=None)
        rep1 = runtime1.run_batch(engine=engine1, series_by_tf=series, arm_bar=10)

        # Run 2: Store ON
        store = EpisodeStore()
        engine2 = PipelineEngine(episode_store=store)
        runtime2 = MultiTFProductRuntime(allow_single_tf_degraded=False, episode_store=store)
        rep2 = runtime2.run_batch(engine=engine2, series_by_tf=series, arm_bar=10)

        # Assert report outputs are identical
        assert rep1.armed_count == rep2.armed_count
        assert len(rep1.duplicates) == len(rep2.duplicates)
        assert len(rep1.skipped_tracked) == len(rep2.skipped_tracked)
        assert rep1.summary() == rep2.summary()
        assert [p.id for p in rep1.armed] == [p.id for p in rep2.armed]
        assert [p.id for p in engine1.tracked_pois()] == [p.id for p in engine2.tracked_pois()]
