"""DUMB FLOWCHART V1 runner — bar loop over M5 + HTF zone feed → trades.

DUMB IMPLEMENTATION — DIAGNOSTIC — NOT EDGE.

Implements the accepted design lock (R1–R6,
`06_RESEARCH/DUMB_FLOWCHART_V1_DESIGN.md`). COMPLEX is untouched: this module
never imports or instantiates the pillars, the trigger matrix, seek/scan
postures, the episode store / ZoneDedup lifecycle, the structural TP feed, or
any COMPLEX risk hard filter. It reuses, READ-ONLY:

* `smc.orchestration.multi_tf_runtime.build_htf_prefixes` — the product's own
  honest-prefix discipline (bars with ``timestamp <= as_of``; the current
  FORMING HTF bar is included, future bars never are). DUMB advances the same
  condition incrementally (per-TF pointer over timestamps) — identical
  membership, no per-bar list rebuild.
* `smc.poi.models.m8_htf_demand_supply.M8HtfDemandSupply` — the product's own
  M8 HTF zone scan, called as a plain library over each honest prefix at the
  moment that prefix grows (design §5 seam option (1): zones enter DUMB as
  read-only emissions; nothing is armed through PipelineEngine).
* `smc.backtest.fill_model.evaluate_position_bar` — locked conservative exit
  semantics (touch = level, fill price = the level, same-bar SL+TP → SL
  wins). Exits are evaluated from the bar AFTER entry: the entry is the
  confirm bar's close, so there is no unknowable intra-bar window after it.
* `smc.utils.atr.atr_series` — Wilder ATR(14); the R5 buffer uses the ATR
  value at the confirm bar (data through that bar, no look-ahead).

Per-zone-episode state machine (one open position and one pending setup per
zone at a time, design §7.5 default "no extra cap"):

  UNSWEPT → SWEPT (R2, anchor = sweep extreme)
          → CONFIRMED (R3: first later bar with a strict mid-cross, within
            ``sweep_idx + 12`` inclusive; a confirm close OUTSIDE the zone is
            a skip that ends the episode — no chase)
          → TRADE OPEN (R4 market at that close; brackets from R5/R6)
          → closed by the fill model or at end-of-data.
  A NEWER sweep bar while a setup is pending re-anchors R5 to the newest
  sweep and resets the confirm clock (documented interpretation: the newest
  sweep is the operative liquidity event). A zone re-arms on the next sweep
  after its setup expires or its trade closes. A zone superseded by a newer
  same-family M8 emission is retired for NEW setups; its pending setup lives
  to its own confirm-or-expiry and its open trade runs normally.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from smc.backtest.fill_model import evaluate_position_bar
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.dumb.constants import DUMB_ATR_PERIOD, DUMB_CONFIRM_MAX_BARS
from smc.dumb.rules import compute_sl_tp, is_confirm, is_expired, is_sweep
from smc.dumb.types import DumbTrade
from smc.utils.atr import atr_series

__all__ = ["ZoneEntry", "DumbRunSummary", "run_dumb_flowchart",
           "M8LibraryZoneFeed", "StaticZoneFeed"]


@dataclass(slots=True)
class ZoneEntry:
    """One active emitted zone episode (R1)."""

    poi_id: str
    detection_tf: Timeframe
    zone: Zone
    kind: str
    valid_from_ts: object   # the M5 timestamp at which DUMB became aware
    bottom: float
    top: float


@dataclass(slots=True)
class _Pending:
    """A swept-but-unconfirmed setup attached to its zone entry."""

    entry: ZoneEntry
    sweep_idx: int           # index into the full M5 series
    sweep_ts: object
    sweep_extreme: float
    n_anchor_updates: int = 0


@dataclass(slots=True)
class DumbRunSummary:
    """Run counters (every gap is exposed, never hidden)."""

    n_m5_bars: int
    atr_missing_at_entry: int = 0
    n_zones_activated: int = 0
    n_zones_superseded: int = 0
    n_htf_rescans: int = 0
    n_setups_swept: int = 0
    n_setup_anchor_updates: int = 0
    n_confirmed: int = 0
    n_entry_skipped_outside_zone: int = 0
    n_expired: int = 0
    n_sweeps_zone_busy: int = 0
    n_trades: int = 0
    counters_by_tf: dict = field(default_factory=dict)
    counters_by_kind: dict = field(default_factory=dict)
    counters_by_direction: dict = field(default_factory=dict)


class StaticZoneFeed:
    """Test helper: pre-built ``(poi_id, tf, zone, valid_from_ts)`` tuples,
    released in ascending ``valid_from_ts`` (ties by poi_id)."""

    def __init__(self, zones):
        self._zones = sorted(zones, key=lambda z: (z[3], z[0]))
        self._ptr = 0

    def update(self, bar_ts) -> list[ZoneEntry]:
        out = []
        while self._ptr < len(self._zones) and self._zones[self._ptr][3] <= bar_ts:
            poi_id, tf, zone, _ts = self._zones[self._ptr]
            self._ptr += 1
            out.append(ZoneEntry(poi_id=poi_id, detection_tf=tf, zone=zone,
                                 kind="injected", valid_from_ts=bar_ts,
                                 bottom=zone.bottom, top=zone.top))
        return out


class M8LibraryZoneFeed:
    """R1 via honest-prefix library reuse of the product's own M8 scan.

    Per detection TF (W1/D1/H4 — M8's own ``HTF_TIMEFRAMES``), a per-TF
    pointer advances over the HTF series whenever a bar's ``timestamp <=``
    the current M5 bar time (the exact ``build_htf_prefixes`` condition,
    incremental). Pointer growth ⇒ an honest re-scan of ``series[:idx]`` via
    ``M8HtfDemandSupply.detect``; a (family, geometry) pair not seen before
    activates a fresh zone entry at this bar; an existing family whose
    emission returned the SAME geometry stays as is (no duplicate), and an
    existing family superseded by a NEW geometry retires the old zone.
    (The product's per-batch combined scan re-runs M8 per H1 close; DUMB
    rescans lazily per emitting TF bar — identical per-TF emission
    semantics, fewer identical re-runs. ``_flag_overlaps`` D1×H4 labelling
    is quality metadata DUMB deliberately ignores.)
    """

    def __init__(self, series_by_tf: dict[Timeframe, list[Candle]]):
        from smc.poi.models.m8_htf_demand_supply import HTF_TIMEFRAMES

        # Only M8's own emitting timeframes (W1/D1/H4) may feed rescans;
        # anything else (e.g. an M5 series handed along for convenience) is
        # inert for detect() and must not burn scans or counters.
        self._series = {tf: list(s) for tf, s in series_by_tf.items()
                        if s and tf in HTF_TIMEFRAMES}
        self._ptr = {tf: 0 for tf in self._series}
        self._by_key: dict[tuple, ZoneEntry] = {}
        self._by_family: dict[tuple, ZoneEntry] = {}
        self._seq = 0
        self.summary = DumbRunSummary(n_m5_bars=0)

    # ---------------------------------------------------------------- #
    def update(self, bar_ts) -> list[ZoneEntry]:
        from smc.poi.models.m8_htf_demand_supply import M8HtfDemandSupply

        activated: list[ZoneEntry] = []
        for tf in sorted(self._series):
            series = self._series[tf]
            p = self._ptr[tf]
            while p < len(series) and series[p].timestamp <= bar_ts:
                p += 1
            if p == self._ptr[tf]:
                continue                      # prefix unchanged for this TF
            self._ptr[tf] = p
            prefix = series[:p]
            self.summary.n_htf_rescans += 1

            model = M8HtfDemandSupply(tf, htf_candles={tf: prefix})
            pois = model.detect(prefix, [], [])
            for poi in pois:
                zone = poi.zone
                kind = getattr(poi, "m8_kind", "m8") or "m8"
                key = (tf.name, kind, zone.direction.name,
                       round(zone.bottom, 6), round(zone.top, 6))
                if key in self._by_key:
                    continue                    # already active, unchanged
                family = (tf.name, kind, zone.direction.name)
                old = self._by_family.get(family)
                if old is not None:
                    old_key = None
                    for k, v in self._by_key.items():     # O(k) — tiny
                        if v is old:
                            old_key = k
                            break
                    if old_key is not None:
                        del self._by_key[old_key]
                    del self._by_family[family]
                    self.summary.n_zones_superseded += 1
                self._seq += 1
                entry = ZoneEntry(
                    poi_id=f"dumb-{tf.name}-{kind}-{self._seq:06d}",
                    detection_tf=tf, zone=zone, kind=kind,
                    valid_from_ts=bar_ts, bottom=zone.bottom, top=zone.top)
                self._by_key[key] = entry
                self._by_family[family] = entry
                activated.append(entry)
        self.summary.n_zones_activated += len(activated)
        return activated


# ---------------------------------------------------------------------- #

def _sign(direction: Direction) -> float:
    return 1.0 if direction is Direction.LONG else -1.0


def run_dumb_flowchart(
    m5: list[Candle],
    series_by_tf: dict[Timeframe, list[Candle]] | None = None,
    *,
    zone_feed: M8LibraryZoneFeed | StaticZoneFeed | None = None,
    exec_from=None,
    exec_to=None,
    end_of_data_close: bool = True,
) -> tuple[list[DumbTrade], DumbRunSummary]:
    """Run R1–R6 bar by bar; return ``(closed trades, summary)``.

    ``m5`` is the FULL loaded M5 series (warm-up included) so ATR(14) has
    history at the first bar; ``exec_from``/``exec_to`` (optional datetimes,
    inclusive) restrict where setups may be created — bars outside are only
    allowed to serve open-trade exits (and end-of-data closes). Zones feed
    from the product's M8 scan (default) or the injected ``zone_feed``.
    """
    if zone_feed is None:
        zone_feed = M8LibraryZoneFeed(series_by_tf)

    atr = atr_series(m5, DUMB_ATR_PERIOD)
    live: dict[str, ZoneEntry] = {}
    pending: dict[str, _Pending] = {}
    open_trade: dict[str, DumbTrade] = {}
    done: list[DumbTrade] = []
    ticket = 0

    stats = DumbRunSummary(n_m5_bars=len(m5))
    by_tf: dict[str, dict[str, int]] = {}
    by_kind: dict[str, int] = {}
    by_dir: dict[str, int] = {}

    def bump(tf: Timeframe, key: str) -> None:
        rec = by_tf.setdefault(tf.name, {})
        rec[key] = rec.get(key, 0) + 1

    def in_exec(bar: Candle) -> bool:
        if exec_from is not None and bar.timestamp < exec_from:
            return False
        if exec_to is not None and bar.timestamp > exec_to:
            return False
        return True

    for i, bar in enumerate(m5):
        a = atr[i]

        # --- 0. exits first (bar AFTER entry; locked conservative model) -- #
        for poi_id, trade in list(open_trade.items()):
            if i <= trade.entry_idx:
                continue
            d = evaluate_position_bar(trade.direction, trade.sl_price,
                                      trade.tp_price, bar)
            if d.closed:
                trade.exit_idx = i
                trade.exit_ts = bar.timestamp
                trade.exit_price = d.price
                trade.close_kind = d.kind
                trade.bars_held = i - trade.entry_idx
                trade.pnl = (d.price - trade.entry_price) * _sign(trade.direction)
                done.append(trade)
                by_kind[d.kind] = by_kind.get(d.kind, 0) + 1
                del open_trade[poi_id]

        # --- 1. zone emissions (honest prefix) --------------------------- #
        for entry in zone_feed.update(bar.timestamp):
            entry.valid_from_ts = bar.timestamp
            live[entry.poi_id] = entry

        # Bars outside the exec window cannot create setups or confirm them.
        if not in_exec(bar):
            continue

        # --- 2. pending setups: confirm / expire on this bar -------------- #
        for poi_id in list(pending):
            p = pending[poi_id]
            zone = p.entry.zone
            if p.sweep_idx >= i:
                continue                       # sweep/anchor bar never confirms itself
            if is_expired(p.sweep_idx, i):
                stats.n_expired += 1
                bump(p.entry.detection_tf, "expired")
                del pending[poi_id]
                continue
            if is_confirm(bar, zone):
                stats.n_confirmed += 1
                bump(p.entry.detection_tf, "confirmed")
                del pending[poi_id]
                if not zone.contains(bar.close):
                    stats.n_entry_skipped_outside_zone += 1
                    bump(p.entry.detection_tf, "entry_skipped_outside_zone")
                    continue
                if a is None:
                    stats.atr_missing_at_entry += 1
                    bump(p.entry.detection_tf, "entry_skipped_no_atr")
                    continue
                sl, tp = compute_sl_tp(zone.direction, bar.close,
                                       p.sweep_extreme, a)
                ticket += 1
                trade = DumbTrade(
                    ticket=ticket,
                    zone_poi_id=poi_id,
                    detection_tf=p.entry.detection_tf,
                    zone_kind=p.entry.kind,
                    direction=zone.direction,
                    entry_idx=i,
                    entry_ts=bar.timestamp,
                    entry_price=bar.close,
                    zone=(zone.bottom, zone.top),
                    sweep_ts=p.sweep_ts,
                    confirm_ts=bar.timestamp,
                    sl_price=sl,
                    tp_price=tp,
                    r_stop=abs(bar.close - sl),
                    atr_at_entry=a,
                    close_kind="open_at_entry_bar",
                )
                open_trade[poi_id] = trade

        # --- 3. sweeps against live zones -------------------------------- #
        for poi_id, entry in live.items():
            if not in_exec(bar):
                break
            zone = entry.zone
            sw = is_sweep(bar, zone)
            if not sw:
                continue
            if poi_id in pending or poi_id in open_trade:
                stats.n_sweeps_zone_busy += 1
                continue
            pending[poi_id] = _Pending(
                entry=entry,
                sweep_idx=i,
                sweep_ts=bar.timestamp,
                sweep_extreme=(bar.low if zone.direction is Direction.LONG
                               else bar.high))
            stats.n_setups_swept += 1
            bump(entry.detection_tf, "swept")

        # --- 3b. re-anchor pending setups on newer sweep bars ------------- #
        for poi_id, p in list(pending.items()):
            zone = p.entry.zone
            if is_sweep(bar, zone) and p.sweep_idx != i:
                p.sweep_idx = i
                p.sweep_ts = bar.timestamp
                p.sweep_extreme = (bar.low if zone.direction is Direction.LONG
                                   else bar.high)
                p.n_anchor_updates += 1
                stats.n_setup_anchor_updates += 1
                bump(p.entry.detection_tf, "anchor_updates")

    # --- 4. end of window: close any position at the last EXEC bar -------- #
    end_idx = len(m5) - 1
    if exec_to is not None:
        while end_idx > 0 and m5[end_idx].timestamp > exec_to:
            end_idx -= 1
    if open_trade and m5:
        last = m5[end_idx]
        for poi_id, trade in list(open_trade.items()):
            trade.exit_idx = end_idx
            trade.exit_ts = last.timestamp
            trade.exit_price = last.close
            trade.close_kind = "end_of_data"
            trade.bars_held = end_idx - trade.entry_idx
            trade.pnl = (last.close - trade.entry_price) * _sign(trade.direction)
            done.append(trade)
            by_kind["end_of_data"] = by_kind.get("end_of_data", 0) + 1
            del open_trade[poi_id]

    # --- merge zone-feed diagnostics (feed-internal counters) ------------- #
    feed_summary = getattr(zone_feed, "summary", None)
    if feed_summary is not None:
        stats.n_htf_rescans = feed_summary.n_htf_rescans
        stats.n_zones_superseded = feed_summary.n_zones_superseded
        stats.n_zones_activated = feed_summary.n_zones_activated

    done.sort(key=lambda t: (t.entry_idx, t.zone_poi_id))
    stats.n_trades = len(done)
    stats.counters_by_tf = by_tf
    stats.counters_by_kind = by_kind
    for t in done:
        dkey = t.direction.name
        by_dir[dkey] = by_dir.get(dkey, 0) + 1
    stats.counters_by_direction = by_dir
    return done, stats
