"""ESSENCE contract v1 runner — M1 bar loop: HTF zone → sweep → set-C confirm →
LIMIT in zone → signed SL band → macro target 1:5 → PureRunner BE.

ESSENCE V1 SLICE — NOT FULL COMPLEX REWRITE.

Implements the SIGNED contract (`00_LOCKED/ESSENCE_CONTRACT_V1.md`) as a
PARALLEL product path under the 2026-10-21 runtime-contract amendment
(M1 execution authorized for essence only; COMPLEX is untouched). This
module reuses, READ-ONLY:

* the product's honest-prefix discipline (per-TF pointer: an HTF bar joins
  the prefix when ``timestamp <=`` the current M1 bar time — the FORMING bar
  included, future bars never) driving zone re-scans exactly like the DUMB
  feed's condition;
* ``smc.poi.models.m8_htf_demand_supply.M8HtfDemandSupply`` — the product's
  own M8 HTF zone scan over each honest prefix (level set = M8's own
  W1/D1/H4; H1 is signed but has no emitter — mapping follow-up F11);
* ``smc.detection.structural_swing_detector.detect_swings`` (once, causal)
  + ``smc.triggers.wave_structure.find_ending_diagonal`` + the frozen
  Trigger-C terminal-expiry constant — the signed set-C primary confirm,
  read on M1;
* ``smc.backtest.fill_model`` — the locked conservative fill semantics
  (touch = limit, fill price = the limit, same-bar SL+TP → SL wins);
* ``smc.risk.pure_runner.PureRunner`` — the locked §28.1 BE-at-ATR manager
  with the per-trade latch, driven on M1 ATR.

Per-zone-episode state machine (one limit OR one position per zone at a
time — §0 "one zone one confirmation one trade", no spray):

  UNSWEPT → SWEPT (§2, sweep extreme recorded, confirm clock started)
          → CONFIRMED (§3: first later M1 bar whose ending-diagonal boundary
            reclaim completes within the frozen M1 resting window; an
            intermediate close-through breakout invalidates the pending
            setup — §2 "breakout ≠ sweep")
          → LIMIT RESTING (§4: LIMIT at the confirm boundary inside the
            zone; expires after the §23 M1 window — 30 M1 bars — unfilled)
          → TRADE OPEN (filled at the touch; brackets = §5 SL band +
            §6 macro target with the hard 1:5 gate)
          → managed by PureRunner BE (§6: 1.0 × ATR to BE, 100 % runner)
          → closed by the fill model or at end-of-data.

Conservative bar ordering (documented, no intra-bar reconstruction):
exits are evaluated with the CURRENT stop/target BEFORE the BE probe, so a
BE move proposed from one bar's favourable extreme takes effect on LATER
bars only (no same-bar rescue). The fill bar itself is subject to the same
conservative evaluations — entry+SL on one bar → SL wins (locked rule).

Swing causality note: swings are precomputed once over the full M1 series
by the product's own ``detect_swings`` (§27 N-bar confirmation, M1 → N=3).
A swing becomes eligible at bar ``i`` only when its confirmation window has
fully passed (``base_index + N <= i``) — no future information beyond the
§27 confirmation delay this product already accepts is used.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from smc.backtest.fill_model import (
    CloseKind,
    evaluate_position_bar,
    fill_price,
    limit_filled,
)
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.config.locked_constants import N_BAR_LTF
from smc.detection.structural_swing_detector import detect_swings
from smc.essence.constants import (
    ESSENCE_CONFIRM_KIND_ED,
    ESSENCE_LIMIT_EXPIRY_BARS,
)
from smc.essence.rules import (
    confirm_kind_allowed,
    essence_stop,
    essence_target,
    find_ed_confirm,
    is_zone_sweep,
    is_zone_violation,
    m1_atr_series,
    rr_gate_ok,
    risk_reward,
)
from smc.essence.types import EssenceZoneEntry, EssenceTrade
from smc.risk.pure_runner import PureRunner, PureRunnerState
from smc.triggers.trigger_expiry import signal_expired

__all__ = [
    "EssenceZoneFeed",
    "StaticZoneFeed",
    "EssenceRunSummary",
    "run_essence_v1",
]


# ---------------------------------------------------------------------- #
# Zone feed
# ---------------------------------------------------------------------- #

@dataclass(slots=True)
class ZoneStep:
    """One feed step: zones activated now + poi ids retired by supersession."""

    activated: list
    removed_poi_ids: list[str]


class _FeedBase:
    """Tiny shared surface: static counters default to zero for test feeds."""

    n_htf_rescans: int = 0
    n_zones_activated: int = 0
    n_zones_superseded: int = 0


class EssenceZoneFeed(_FeedBase):
    """Level feed: honest-prefix library reuse of the product's M8 scan.

    Per detection TF (W1/D1/H4 — M8's own ``HTF_TIMEFRAMES``), a per-TF
    pointer advances over the HTF series whenever a bar's ``timestamp <=``
    the current M1 bar time. Pointer growth ⇒ an honest re-scan of
    ``series[:idx]`` via ``M8HtfDemandSupply.detect``. A (family, geometry)
    pair not seen before activates a fresh zone entry at this bar; an
    existing family superseded by a NEW geometry retires the old zone and
    the retirement id is reported to the runner.
    """

    def __init__(self, series_by_tf: dict[Timeframe, list[Candle]] | None = None):
        from smc.poi.models.m8_htf_demand_supply import HTF_TIMEFRAMES

        self._series = {tf: list(s) for tf, s in (series_by_tf or {}).items()
                        if s and tf in HTF_TIMEFRAMES}
        self._ptr = {tf: 0 for tf in self._series}
        self._by_key: dict[tuple, EssenceZoneEntry] = {}
        self._by_family: dict[tuple, EssenceZoneEntry] = {}
        self._seq = 0

    # ------------------------------------------------------------------ #
    def update(self, bar_ts: datetime, _tick=None) -> ZoneStep:
        from smc.poi.models.m8_htf_demand_supply import M8HtfDemandSupply

        activated: list[EssenceZoneEntry] = []
        removed: list[str] = []
        for tf in sorted(self._series):
            series = self._series[tf]
            p = self._ptr[tf]
            while p < len(series) and series[p].timestamp <= bar_ts:
                p += 1
            if p == self._ptr[tf]:
                continue                      # prefix unchanged for this TF
            self._ptr[tf] = p
            prefix = series[:p]
            self.n_htf_rescans += 1

            model = M8HtfDemandSupply(tf, htf_candles={tf: prefix})
            pois = model.detect(prefix, [], [])
            for poi in pois:
                zone = poi.zone
                kind = getattr(poi, "m8_kind", "m8") or "m8"
                key = (tf.name, kind, zone.direction.name,
                       round(zone.bottom, 6), round(zone.top, 6))
                if key in self._by_key:
                    continue                  # already active, unchanged
                family = (tf.name, kind, zone.direction.name)
                old = self._by_family.get(family)
                if old is not None:
                    old_key = None
                    for k, v in self._by_key.items():   # O(k) — tiny
                        if v is old:
                            old_key = k
                            break
                    if old_key is not None:
                        del self._by_key[old_key]
                        removed.append(old_key)
                    del self._by_family[family]
                    self.n_zones_superseded += 1
                self._seq += 1
                entry = EssenceZoneEntry(
                    poi_id=f"essence-{tf.name}-{kind}-{self._seq:06d}",
                    detection_tf=tf, zone=zone, kind=kind,
                    valid_from_ts=bar_ts, bottom=zone.bottom, top=zone.top)
                self._by_key[key] = entry
                self._by_family[family] = entry
                activated.append(entry)
        self.n_zones_activated += len(activated)
        return ZoneStep(activated, removed)

    def active(self) -> list[EssenceZoneEntry]:
        """All currently active zone entries (macro-target lookup + sweeps)."""
        return list(self._by_key.values())


class StaticZoneFeed(_FeedBase):
    """Test helper: pre-built ``EssenceZoneEntry`` objects released in order."""

    def __init__(self, entries: list[EssenceZoneEntry]):
        self._entries = sorted(entries, key=lambda e: (e.valid_from_ts, e.poi_id))
        self._ptr = 0

    def update(self, bar_ts: datetime, _tick=None) -> ZoneStep:
        out: list[EssenceZoneEntry] = []
        while (self._ptr < len(self._entries)
               and self._entries[self._ptr].valid_from_ts <= bar_ts):
            e = self._entries[self._ptr]
            self._ptr += 1
            out.append(e)
        return ZoneStep(out, [])

    def active(self) -> list[EssenceZoneEntry]:
        return list(self._entries[: self._ptr])


# ---------------------------------------------------------------------- #
# Runner state
# ---------------------------------------------------------------------- #

@dataclass(slots=True)
class _Setup:
    """A swept-but-unconfirmed setup attached to one zone."""

    entry: EssenceZoneEntry
    sweep_idx: int
    sweep_ts: datetime
    sweep_extreme: float
    n_anchor_updates: int = 0


@dataclass(slots=True)
class _Resting:
    """A confirmed setup whose LIMIT still rests inside the zone."""

    entry: EssenceZoneEntry
    setup: _Setup
    candidate: object            # rules.EdCandidate
    sl_price: float
    sl_pips: float
    tp_price: float
    target_ref: tuple[str, float]
    rr_planned: float
    placed_idx: int
    confirm_ts: datetime
    blocked_reason: str = ""


@dataclass(slots=True)
class EssenceRunSummary:
    """Run counters — every funnel gap exposed, never hidden."""

    n_m1_bars: int = 0
    n_htf_rescans: int = 0
    n_zones_activated: int = 0
    n_zones_superseded: int = 0
    n_setups_swept: int = 0
    n_setup_anchor_updates: int = 0
    n_sweeps_zone_busy: int = 0
    n_pending_invalidated_breakout: int = 0
    n_pending_expired: int = 0
    n_zone_removed_cleanup: int = 0
    n_confirmed: int = 0
    n_entry_skipped_outside_zone: int = 0
    n_blocked_no_atr: int = 0
    n_blocked_risk_invalid: int = 0
    n_blocked_missing_target: int = 0
    n_blocked_rr_below_1x5: int = 0
    n_limits_placed: int = 0
    n_limits_expired: int = 0
    n_limits_cancelled_breakout: int = 0
    n_filled: int = 0
    n_be_moves: int = 0
    n_trades: int = 0
    exits_by_kind: dict = field(default_factory=dict)
    by_tf: dict = field(default_factory=dict)
    by_kind: dict = field(default_factory=dict)
    by_direction: dict = field(default_factory=dict)
    confirm_kinds_seen: dict = field(default_factory=dict)


def _sign(direction: Direction) -> float:
    return 1.0 if direction is Direction.LONG else -1.0


class _CausalSwings:
    """Precomputed M1 swings + a §27-causal per-bar view pointer.

    The view is capped to the most recent ``_VIEW_SPAN`` swings. The consumer
    (`wave_structure._alternating_chain`) walks BACKWARDS from the most recent
    swing of the terminal polarity and stops once it has 5 alternating
    extremes — a bounded recent window therefore returns exactly the chain
    the unlimited view would (the walk can never consume more than a few dozen
    swings for a 5-extreme alternating chain). The cap only bounds the
    per-scan cost; it does not change any returned diagonal.
    """

    _VIEW_SPAN = 120

    def __init__(self, m1: list[Candle]):
        self._swings = detect_swings(m1, Timeframe.M1)   # N = 3 (frozen §27)
        self._sorted = sorted(self._swings, key=lambda s: s.candle_index)
        self._ptr = 0

    def view(self, bar_index: int) -> list:
        """Last-N swings with ``base_index + N <= bar_index`` (§27-causal)."""
        gate = bar_index - N_BAR_LTF
        while (self._ptr < len(self._sorted)
               and self._sorted[self._ptr].candle_index <= gate):
            self._ptr += 1
        return self._sorted[max(0, self._ptr - self._VIEW_SPAN): self._ptr]


# ---------------------------------------------------------------------- #
# The bar loop
# ---------------------------------------------------------------------- #

def run_essence_v1(
    m1: list[Candle],
    series_by_tf: dict[Timeframe, list[Candle]] | None = None,
    *,
    zone_feed=None,
    exec_from=None,
    exec_to=None,
    on_progress=None,
) -> tuple[list[EssenceTrade], EssenceRunSummary]:
    """Run the SIGNED essence rules bar by bar over the M1 execution series.

    ``m1`` is the FULL M1 series (warm-up included) so M1 ATR(14) has
    history, swings precompute once, and in-flight limits can expire/close.
    ``exec_from``/``exec_to`` (inclusive datetimes) restrict where new
    setups may be created; bars outside only serve exits. Returns
    ``(closed trades, summary)``; ``pnl`` is book-internal price units,
    DIAGNOSTIC ONLY.
    """
    from smc.essence.rules import zone_band_half_width  # noqa: F401 (doc parity)

    if zone_feed is None:
        zone_feed = EssenceZoneFeed(series_by_tf)

    atr = m1_atr_series(m1)
    causal = _CausalSwings(m1)
    pure_runner = PureRunner(state=PureRunnerState())

    live: dict[str, EssenceZoneEntry] = {}
    pending: dict[str, _Setup] = {}
    resting: dict[str, _Resting] = {}
    open_trade: dict[str, EssenceTrade] = {}
    done: list[EssenceTrade] = []
    ticket = 0

    stats = EssenceRunSummary(n_m1_bars=len(m1))
    by_tf: dict[str, dict[str, int]] = {}
    by_kind: dict[str, int] = {}
    by_dir: dict[str, int] = {}
    _no_callback = None

    def bump(tf_name: str, key: str) -> None:
        rec = by_tf.setdefault(tf_name, {})
        rec[key] = rec.get(key, 0) + 1

    def in_exec(bar: Candle) -> bool:
        if exec_from is not None and bar.timestamp < exec_from:
            return False
        if exec_to is not None and bar.timestamp > exec_to:
            return False
        return True

    def close_trade(trade: EssenceTrade, i: int, kind: str, price: float) -> None:
        trade.exit_idx = i
        trade.exit_ts = bar.timestamp
        trade.exit_price = price
        trade.close_kind = kind
        trade.bars_held = i - trade.entry_idx
        trade.pnl = (price - trade.entry_price) * _sign(trade.direction)
        done.append(trade)
        stats.exits_by_kind[kind] = stats.exits_by_kind.get(kind, 0) + 1
        del open_trade[trade.zone_poi_id]

    def maybe_place(zone_poi_id: str, setup: _Setup, cand, i: int, bar: Candle,
                    atr_value) -> None:
        """Money-rule funnel for one confirmed setup: §4 → §5 → §6."""
        zone = setup.entry.zone
        # §4 — the LIMIT must rest INSIDE the zone (no chase outside).
        if not zone.contains(cand.boundary):
            stats.n_entry_skipped_outside_zone += 1
            bump(setup.entry.detection_tf.name, "entry_skipped_outside_zone")
            return
        # §5 — SL beyond the M1 structure inside the signed band.
        try:
            sl_price, sl_pips = essence_stop(zone.direction, cand.terminal_level)
        except ValueError:
            stats.n_blocked_risk_invalid += 1
            bump(setup.entry.detection_tf.name, "blocked_risk_invalid")
            return
        if zone.direction is Direction.LONG and sl_price >= bar.close:
            stats.n_blocked_risk_invalid += 1
            bump(setup.entry.detection_tf.name, "blocked_risk_invalid")
            return
        if zone.direction is Direction.SHORT and sl_price <= bar.close:
            stats.n_blocked_risk_invalid += 1
            bump(setup.entry.detection_tf.name, "blocked_risk_invalid")
            return
        # §6 — macro HTF target from the active opposite-direction zones.
        refs = [(e.bottom, e.top, e.zone.direction) for e in zone_feed.active()
                if e.poi_id != zone_poi_id]
        target, target_ref = essence_target(refs, zone.direction, cand.boundary)
        if target is None:
            stats.n_blocked_missing_target += 1
            bump(setup.entry.detection_tf.name, "blocked_missing_target")
            return
        rr = risk_reward(zone.direction, cand.boundary, sl_price, target)
        if not rr_gate_ok(rr):
            stats.n_blocked_rr_below_1x5 += 1
            bump(setup.entry.detection_tf.name, "blocked_rr_below_1x5")
            return
        resting[zone_poi_id] = _Resting(
            entry=setup.entry, setup=setup, candidate=cand,
            sl_price=sl_price, sl_pips=sl_pips, tp_price=target,
            target_ref=(target_ref, target), rr_planned=rr,
            placed_idx=i, confirm_ts=bar.timestamp)
        stats.n_limits_placed += 1
        bump(setup.entry.detection_tf.name, "limit_placed")

    for i, bar in enumerate(m1):
        if on_progress is not None and i % 50000 == 0:
            on_progress(i, len(m1))
        a = atr[i]

        # --- 1. exits first, with the CURRENT bracket (before the BE probe) -- #
        for zone_poi_id in list(open_trade):
            trade = open_trade[zone_poi_id]
            if i <= trade.entry_idx:
                continue
            d = evaluate_position_bar(trade.direction, trade.sl_price,
                                      trade.tp_price, bar)
            if d.closed:
                close_trade(trade, i, d.kind, d.price)
                continue
            # 1b. PureRunner BE (§28.1, per-trade latch, M1 ATR).
            if a is not None:
                probe = bar.high if trade.direction is Direction.LONG else bar.low
                be = pure_runner.be_moved_sl(
                    entry_price=trade.entry_price,
                    direction=trade.direction,
                    atr=float(a),
                    current_price=probe,
                    current_sl=trade.sl_price,
                    trade_key=trade.ticket,
                )
                if be is not None:
                    trade.sl_price = be
                    trade.be_applied = True
                    pure_runner.mark_be_applied(trade_key=trade.ticket)
                    stats.n_be_moves += 1
                    bump(trade.detection_tf.name, "be_moves")

        # --- 2. zone feed (honest prefix + supersession cleanup) ---------- #
        step = zone_feed.update(bar.timestamp, _no_callback)
        for entry in step.activated:
            live[entry.poi_id] = entry
        for removed_id in step.removed_poi_ids:
            live.pop(removed_id, None)
            stats.n_zone_removed_cleanup += 1
            bump("feed", "zone_removed")
            pending.pop(removed_id, None)
            resting.pop(removed_id, None)

        if not in_exec(bar):
            continue

        # --- 3. resting limits: expiry / breakout-cancel / touch fill ----- #
        for zone_poi_id in list(resting):
            r = resting[zone_poi_id]
            if signal_expired(r.placed_idx, ESSENCE_LIMIT_EXPIRY_BARS, i):
                del resting[zone_poi_id]
                stats.n_limits_expired += 1
                bump(r.entry.detection_tf.name, "limit_expired")
                continue
            if is_zone_violation(bar, r.entry.zone):
                del resting[zone_poi_id]
                stats.n_limits_cancelled_breakout += 1
                bump(r.entry.detection_tf.name, "limit_cancelled_breakout")
                continue
            entry_level = r.candidate.boundary
            if limit_filled(r.entry.zone.direction, entry_level, bar):
                del resting[zone_poi_id]
                entry_price = fill_price(r.entry.zone.direction,
                                         r.candidate.boundary, bar)
                ticket += 1
                trade = EssenceTrade(
                    ticket=ticket,
                    zone_poi_id=zone_poi_id,
                    detection_tf=r.entry.detection_tf,
                    zone_kind=r.entry.kind,
                    direction=r.entry.zone.direction,
                    zone=(r.entry.bottom, r.entry.top),
                    sweep_ts=r.setup.sweep_ts,
                    sweep_extreme=r.setup.sweep_extreme,
                    confirm_kind=ESSENCE_CONFIRM_KIND_ED,
                    confirm_idx=r.candidate.confirm_idx,
                    confirm_ts=r.confirm_ts,
                    entry_level=r.candidate.boundary,
                    terminal_idx=r.candidate.terminal_idx,
                    entry_idx=i,
                    entry_ts=bar.timestamp,
                    entry_price=entry_price,
                    sl_price=r.sl_price,
                    sl_pips_buffer=r.sl_pips,
                    tp_price=r.tp_price,
                    target_ref=r.target_ref,
                    rr_planned=r.rr_planned,
                    r_stop=abs(entry_price - r.sl_price),
                    atr_at_entry=float(a) if a is not None else 0.0,
                    limit_placed_idx=r.placed_idx,
                    limit_expiry_bars=ESSENCE_LIMIT_EXPIRY_BARS,
                )
                open_trade[zone_poi_id] = trade
                stats.n_filled += 1
                bump(trade.detection_tf.name, "filled")
                # Conservative same-bar evaluation with the placement brackets
                # (entry+SL same bar → SL wins, locked fill-model rule).
                d2 = evaluate_position_bar(trade.direction, trade.sl_price,
                                           trade.tp_price, bar)
                if d2.closed:
                    close_trade(trade, i, d2.kind, d2.price)

        # --- 4. pending setups: confirm / invalidate / expire ------------- #
        for zone_poi_id in list(pending):
            setup = pending[zone_poi_id]
            zone = setup.entry.zone
            if setup.sweep_idx >= i:
                continue                       # the sweep bar never confirms itself
            if signal_expired(setup.sweep_idx, ESSENCE_LIMIT_EXPIRY_BARS, i):
                del pending[zone_poi_id]
                stats.n_pending_expired += 1
                bump(setup.entry.detection_tf.name, "pending_expired")
                continue
            if is_zone_violation(bar, zone):
                del pending[zone_poi_id]
                stats.n_pending_invalidated_breakout += 1
                bump(setup.entry.detection_tf.name, "pending_invalidated_breakout")
                continue
            if zone_poi_id in resting:
                del pending[zone_poi_id]       # first confirm wins the zone
                continue
            cand = find_ed_confirm(zone, i, m1, causal.view(i), a)
            if cand is None:
                continue
            stats.n_confirmed += 1
            kind = ESSENCE_CONFIRM_KIND_ED
            if not confirm_kind_allowed(kind):
                continue                       # unreachable by construction (guard)
            stats.confirm_kinds_seen[kind] = stats.confirm_kinds_seen.get(kind, 0) + 1
            bump(setup.entry.detection_tf.name, "confirmed")
            del pending[zone_poi_id]
            maybe_place(zone_poi_id, setup, cand, i, bar, a)

        if not in_exec(bar):
            continue

        # --- 5. sweeps against live zones (create / busy / re-anchor) ----- #
        for zone_poi_id, entry in list(live.items()):
            zone = entry.zone
            if not is_zone_sweep(bar, zone):
                continue
            if zone_poi_id in pending:
                stats.n_sweeps_zone_busy += 1
                continue
            if zone_poi_id in resting or zone_poi_id in open_trade:
                stats.n_sweeps_zone_busy += 1
                continue
            pending[zone_poi_id] = _Setup(
                entry=entry, sweep_idx=i, sweep_ts=bar.timestamp,
                sweep_extreme=(bar.low if zone.direction is Direction.LONG
                               else bar.high))
            stats.n_setups_swept += 1
            bump(entry.detection_tf.name, "swept")

        # 5b. re-anchor pending setups on newer sweep bars (newest event wins).
        for zone_poi_id, setup in list(pending.items()):
            if zone_poi_id in live:
                zone = live[zone_poi_id].zone
                if is_zone_sweep(bar, zone) and setup.sweep_idx != i:
                    setup.sweep_idx = i
                    setup.sweep_ts = bar.timestamp
                    setup.sweep_extreme = (bar.low if zone.direction is Direction.LONG
                                           else bar.high)
                    setup.n_anchor_updates += 1
                    stats.n_setup_anchor_updates += 1
                    bump(setup.entry.detection_tf.name, "anchor_updates")

    # --- 6. end of window: close remaining positions at the last exec bar - #
    end_idx = len(m1) - 1
    if exec_to is not None:
        while end_idx > 0 and m1[end_idx].timestamp > exec_to:
            end_idx -= 1
    if open_trade and m1:
        last = m1[end_idx]
        for zone_poi_id in list(open_trade):
            trade = open_trade[zone_poi_id]
            trade.exit_idx = end_idx
            trade.exit_ts = last.timestamp
            trade.exit_price = last.close
            trade.close_kind = "end_of_data"
            trade.bars_held = end_idx - trade.entry_idx
            trade.pnl = (last.close - trade.entry_price) * _sign(trade.direction)
            done.append(trade)
            stats.exits_by_kind["end_of_data"] = stats.exits_by_kind.get("end_of_data", 0) + 1
            del open_trade[zone_poi_id]

    # --- merge feed counters ---------------------------------------------- #
    stats.n_htf_rescans = getattr(zone_feed, "n_htf_rescans", 0)
    stats.n_zones_activated = getattr(zone_feed, "n_zones_activated", 0)
    stats.n_zones_superseded = getattr(zone_feed, "n_zones_superseded", 0)

    done.sort(key=lambda t: (t.entry_idx, t.zone_poi_id))
    stats.n_trades = len(done)
    stats.by_tf = by_tf
    stats.by_kind = by_kind
    for t in done:
        dkey = t.direction.name
        by_dir[dkey] = by_dir.get(dkey, 0) + 1
    stats.by_direction = by_dir
    return done, stats
