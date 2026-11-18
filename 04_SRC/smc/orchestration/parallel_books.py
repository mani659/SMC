"""Parallel dedicated confirmation books — SPIKE (dead by default).

Design (accepted): ``06_RESEARCH/PARALLEL_DEDICATED_PATH_DESIGN.md``.
Evidence: ``R0_TRIGGER_ADMISSION_MAP.md``, ``R1_PURE_TAG_BOOKS_REPORT.md``,
``BCE_STARVATION_PROBE_REPORT.md``.

What this module is
-------------------
A **book** is ``(symbol, tag, detection_tier_set, confirm_tf_map)``. Each book
owns ONE :class:`~smc.orchestration.product_menu_mtf.ProductMenuEngine` whose
per-tier menus carry exactly one trigger letter (``trigger_types=(tag,)``) —
the same object R1 injected at runtime, promoted to configuration. The shipped
tier table is never edited: a book reuses the shipped tier geometry (detection
TF, confirmation TFs, expiry) and only NARROWS the trigger subset.

:class:`ParallelBookMenu` is a **drop-in multiplexer** with the public surface
the live loop, paper runner and adapters already use (``register_armed``,
``retire``, ``set_state_source``, ``on_execution_bar``, ``tier_for``,
``detection_timeframes``, ``confirmation_timeframes``, ``episodes``,
``counters``). It therefore needs NO change in the runtime wiring to run N
books: the operator config selects a book list and the same seam executes them.

Rules honoured by this spike (architect rulings)
-----------------------------------------------
* **R-A — one story PER BOOK**: each book is its own engine with its own
  armed map, its own episodes and its own one-shot ``_consumed`` set. A win in
  book B can never consume book F's POI or close its window. The adapter's
  existing plan-level story guard stays AS-CODED (it keys on trigger, so it
  never arbitrates between two different tags).
* **R-K — D excluded**: :data:`EXCLUDED_TAGS` refuses a ``D`` book loudly,
  for EVERY config shape (string presets AND dict ``BookConfig`` entries —
  the tag is resolved first, then refused).
* **Shared risk envelope**: this layer owns NO risk component. Books share one
  broker/runner/``RiskEngine`` (one breaker, one daily loss, one same-level and
  sweep memory per account) because they run through the same runner.
* **Cross-book identical plan**: two books confirming the SAME executable plan
  (same direction/entry/SL/TP, overlapping zone) are deduplicated — the second
  ticket is suppressed and counted with a machine-readable reason. Trigger is
  deliberately EXCLUDED from this identity: the whole point is that a
  different tag can reproduce the same order. The memory is a DURABLE
  session-scoped registry (:class:`CrossBookPlanRegistry`), not the menu
  window: a plan stays remembered until the plan stops being live
  (``release_plan`` from the adapter's liveness seam), so a second book
  confirming the same order after the first window closed is still one plan.
  The adapter carries an independent trigger-excluded backstop
  (``duplicate_story_cross_book``) over its resting/pending/in-flight claims.
* **No legacy fall-through (M-3)**: a POI whose detection tier NO book carries
  is NOT routed through the archived single-menu seek path; it is skipped and
  counted (``poi_outside_books``). Only the multiplexer opts in
  (``refuses_uncovered_tiers``); the shipped single menu is unchanged.
* **Identity**: every emitted candidate is stamped ``book_id`` / ``book_tag``
  on its ``product_menu`` stamp, which the order identity helpers turn into a
  comment prefix. A ``PROD`` book is stamped too but keeps today's comment.
* **R-J plumbing**: the winning route's direction rides on the candidate
  (``direction``), so the journal can attribute direction per book without
  re-inferring it.

Default behaviour
-----------------
``resolve_book_selection(None)`` / ``[]`` returns ``()``. The operator then
builds today's single :class:`ProductMenuEngine` — bit-equivalent to the
shipped menu. ``["PROD"]`` runs the SAME production tier table through this
layer (one book, production trigger subsets), which is behaviourally identical
because there is no second book to deduplicate against.

Non-goals: no default menu change, no locked-constant edit, no threshold/SL/TP
change, no order-placement change, no edge claim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace

from smc.config.timeframe import Timeframe
from smc.core.enums import TriggerType
from smc.orchestration.product_menu_mtf import (
    PRODUCT_MENU_TIERS,
    MenuTier,
    MenuWinner,
    ProductMenuEngine,
)
from smc.risk.story_guard import zones_overlap

__all__ = [
    "ALL_TIER_NAMES",
    "BookConfig",
    "CrossBookPlanKey",
    "CrossBookPlanRegistry",
    "EXCLUDED_TAGS",
    "MID_TIER_NAMES",
    "PROD_BOOK_ID",
    "ParallelBookMenu",
    "TAG_BOOK_TIER_SETS",
    "cross_book_plan_key",
    "resolve_book_selection",
    "same_cross_book_plan",
]

#: The production book id: production tier table, today's comments/magic.
PROD_BOOK_ID = "PROD"

#: Shipped tier names, shipped order (DAY, H4, H1, M15).
ALL_TIER_NAMES: tuple[str, ...] = tuple(tier.name for tier in PRODUCT_MENU_TIERS)

#: The three mid tiers R1 measured (M15→M1, H1→M5+M1, H4→M5+M15).
MID_TIER_NAMES: tuple[str, ...] = ("H4", "H1", "M15")

#: Proposed per-tag book tier sets (design §4, from R1 evidence).
#: F is the only tag with an evidenced DAY-tier flow; B/C/E/A are mid-only.
TAG_BOOK_TIER_SETS: dict[str, tuple[str, ...]] = {
    "A": MID_TIER_NAMES,
    "B": MID_TIER_NAMES,
    "C": MID_TIER_NAMES,
    "E": MID_TIER_NAMES,
    "F": ALL_TIER_NAMES,
}

#: R-K: excluded this engagement (structurally dead on the zero-volume feed).
EXCLUDED_TAGS: dict[str, str] = {
    "D": (
        "Two-Bar Reversal is structurally dead on the zero-volume feed "
        "(frozen volume gate); admitting it needs a feed ruling (R-K)"
    ),
}

_TIER_BY_NAME: dict[str, MenuTier] = {tier.name: tier for tier in PRODUCT_MENU_TIERS}

#: Trigger letter → enum (the book's tag is addressed by its letter).
_TRIGGER_BY_LETTER: dict[str, TriggerType] = {}
for _trigger in TriggerType:
    _raw = str(getattr(_trigger, "value", _trigger)).strip().upper()
    if _raw:
        _TRIGGER_BY_LETTER[_raw[0]] = _trigger
del _trigger, _raw


# --------------------------------------------------------------------------- #
# Book definition (data only — no logic, no thresholds)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class BookConfig:
    """One dedicated confirmation book.

    ``detection_tiers`` names SHIPPED tiers (``DAY``/``H4``/``H1``/``M15``); the
    confirmation TFs are therefore never re-invented — :attr:`confirm_tf_map`
    is read straight off the shipped ``MenuTier``. ``tag=None`` is the
    production book (production per-tier trigger subsets, not a pure book).
    """

    book_id: str
    tag: TriggerType | None = None
    detection_tiers: tuple[str, ...] = ()
    symbol: str = "XAUUSD"

    def __post_init__(self) -> None:
        book_id = str(self.book_id or "").strip().upper()
        if not book_id:
            raise ValueError("book_id must be a non-empty string")
        if self.tag is None and book_id != PROD_BOOK_ID:
            raise ValueError(
                f"book {book_id!r} has no tag: only {PROD_BOOK_ID} may carry "
                "the production (multi-trigger) menu"
            )
        names = tuple(self.detection_tiers) or (
            ALL_TIER_NAMES if self.tag is None else ()
        )
        if not names:
            raise ValueError(f"book {book_id!r} must name at least one tier")
        unknown = [n for n in names if str(n).strip().upper() not in _TIER_BY_NAME]
        if unknown:
            raise ValueError(
                f"book {book_id!r} names unknown tiers {unknown}; "
                f"shipped tiers are {list(ALL_TIER_NAMES)}"
            )
        # Normalise to shipped order so books are deterministic regardless of
        # how the config listed the tiers.
        normalised = tuple(n for n in ALL_TIER_NAMES if n in {
            str(x).strip().upper() for x in names
        })
        object.__setattr__(self, "book_id", book_id)
        object.__setattr__(self, "detection_tiers", normalised)
        object.__setattr__(self, "symbol", str(self.symbol or "XAUUSD"))

    @property
    def detection_timeframes(self) -> tuple[Timeframe, ...]:
        """Detection TFs of this book's tiers (shipped geometry, unchanged)."""
        return tuple(_TIER_BY_NAME[n].detection_tf for n in self.detection_tiers)

    @property
    def confirm_tf_map(self) -> dict[Timeframe, tuple[Timeframe, ...]]:
        """``{detection_tf: confirmation_tfs}`` read off the shipped tiers."""
        return {
            _TIER_BY_NAME[n].detection_tf: _TIER_BY_NAME[n].confirmation_tfs
            for n in self.detection_tiers
        }

    @property
    def tag_letter(self) -> str | None:
        """The book's trigger letter (``None`` for the production book)."""
        if self.tag is None:
            return None
        return str(getattr(self.tag, "value", self.tag)).strip().upper()[:1]

    def menu_tiers(self) -> tuple[MenuTier, ...]:
        """The book's menu tiers: shipped geometry, narrowed trigger subset.

        ``PROD`` returns the shipped tier objects verbatim (today's menu).
        """
        tiers = tuple(_TIER_BY_NAME[n] for n in self.detection_tiers)
        if self.tag is None:
            return tiers
        return tuple(replace(tier, trigger_types=(self.tag,)) for tier in tiers)


def _refuse_excluded(name) -> None:
    """R-K: refuse an excluded tag letter / book id, loudly (every form)."""
    key = str(name or "").strip().upper()
    if key in EXCLUDED_TAGS:
        raise ValueError(f"book {key} is excluded: {EXCLUDED_TAGS[key]}")


def _coerce_book(entry) -> BookConfig:
    """One selection entry → :class:`BookConfig` (loud on anything unknown).

    R-K is enforced on the RESOLVED tag (letters and dict entries alike) and
    on the book id, so no config shape can construct an excluded book.
    """
    if isinstance(entry, BookConfig):
        _refuse_excluded(entry.book_id)
        _refuse_excluded(entry.tag_letter)
        return entry
    if isinstance(entry, dict):
        raw_tag = entry.get("tag")
        tag = None
        if raw_tag is not None:
            letter = str(raw_tag).strip().upper()[:1]
            if letter not in _TRIGGER_BY_LETTER:
                raise ValueError(f"unknown book tag {raw_tag!r}")
            _refuse_excluded(letter)
            tag = _TRIGGER_BY_LETTER[letter]
        book_id = str(entry.get("book_id") or entry.get("id") or "")
        _refuse_excluded(book_id)
        return BookConfig(
            book_id=book_id,
            tag=tag,
            detection_tiers=tuple(entry.get("detection_tiers") or ()),
            symbol=str(entry.get("symbol") or "XAUUSD"),
        )
    name = str(entry or "").strip().upper()
    if not name:
        raise ValueError("empty book selection entry")
    if name == PROD_BOOK_ID:
        return BookConfig(PROD_BOOK_ID)
    _refuse_excluded(name)
    if name not in TAG_BOOK_TIER_SETS:
        raise ValueError(
            f"unknown book {name!r}; expected {PROD_BOOK_ID} or one of "
            f"{sorted(TAG_BOOK_TIER_SETS)}"
        )
    return BookConfig(
        book_id=name,
        tag=_TRIGGER_BY_LETTER[name],
        detection_tiers=TAG_BOOK_TIER_SETS[name],
    )


def resolve_book_selection(selection) -> tuple[BookConfig, ...]:
    """Config selection → books. Empty/None → ``()`` (today's single menu).

    Accepted forms: ``None``, ``[]``, ``"F"``, ``["F", "B"]``, ``["PROD"]``,
    a dict, or a :class:`BookConfig` (or a list of those).
    """
    if not selection:
        return ()
    if isinstance(selection, (str, BookConfig, dict)):
        entries = (selection,)
    else:
        entries = tuple(selection)
    books = tuple(_coerce_book(entry) for entry in entries)
    ids = [book.book_id for book in books]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate book ids in selection: {ids}")
    return books


# --------------------------------------------------------------------------- #
# Cross-book plan identity (R-H) — the SAME order, whichever tag found it
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class CrossBookPlanKey:
    """Executable-plan identity WITHOUT the trigger (see module docstring)."""

    direction: object
    entry_price: float
    sl: float
    tp: float | None
    zone_low: float | None
    zone_high: float | None


def _price(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def cross_book_plan_key(candidate) -> CrossBookPlanKey | None:
    """Plan identity of a candidate (``None`` when entry/SL are unknown)."""
    entry = _price(getattr(candidate, "entry_price", None))
    sl = _price(getattr(candidate, "sl_price", getattr(candidate, "sl", None)))
    if entry is None or sl is None:
        return None
    tp = _price(
        getattr(candidate, "tp_price", getattr(candidate, "tp", None))
    )
    return CrossBookPlanKey(
        direction=getattr(candidate, "direction", None),
        entry_price=entry,
        sl=sl,
        tp=tp,
        zone_low=_price(getattr(candidate, "zone_low", None)),
        zone_high=_price(getattr(candidate, "zone_high", None)),
    )


def same_cross_book_plan(
    a: CrossBookPlanKey | None, b: CrossBookPlanKey | None
) -> bool:
    """True when both keys are the SAME executable order (exact floats).

    Same direction, entry, SL and TP; zones must be known and overlap under
    the one shipped overlap rule. An unprovable key is never collapsed.
    """
    if a is None or b is None:
        return False
    if a.direction != b.direction:
        return False
    if a.entry_price != b.entry_price or a.sl != b.sl or a.tp != b.tp:
        return False
    if (
        a.zone_low is None
        or a.zone_high is None
        or b.zone_low is None
        or b.zone_high is None
    ):
        return False
    return zones_overlap(a.zone_high, a.zone_low, b.zone_high, b.zone_low)


class CrossBookPlanRegistry:
    """Durable, session-scoped memory of admitted cross-book plans (R-H).

    Unlike the menu window (``MenuWinner.window_end_ts``), this registry is
    NOT time scoped. An admitted plan stays remembered until the caller says
    the plan can no longer trade (``release``), which is the same liveness
    clock the ONE-STORY guard uses: resting order / open position / in-flight
    candidate. A second book confirming the same executable order after the
    first book's window closed is therefore still one plan.

    Identity is :class:`CrossBookPlanKey` (direction + entry/SL/TP + zone
    overlap, trigger EXCLUDED). Unknown geometry is never stored, so it can
    never collapse two orders.

    The registry is bookkeeping only: it owns no risk, no sizing and no
    decision besides "has another book already admitted this exact order".
    """

    def __init__(self) -> None:
        self._entries: list[dict] = []

    def __len__(self) -> int:
        return len(self._entries)

    def entries(self) -> tuple[dict, ...]:
        """Read-only snapshot of the remembered plans."""
        return tuple(self._entries)

    @staticmethod
    def route_key(book_id, poi_id) -> str:
        """Stable per-(book, POI) identity (two books never share a slot)."""
        return f"{book_id}|{poi_id}"

    def recall(
        self, key: CrossBookPlanKey | None, *, book_id: str | None = None
    ) -> dict | None:
        """The OTHER book already holding this exact plan (``None`` = free)."""
        if key is None:
            return None
        for entry in self._entries:
            if book_id is not None and entry["book_id"] == book_id:
                continue
            if same_cross_book_plan(key, entry["key"]):
                return entry
        return None

    def remember(
        self,
        key: CrossBookPlanKey | None,
        *,
        book_id: str,
        poi_id,
        window_end=None,
    ) -> dict | None:
        """Record one admitted plan (``None`` key → nothing to remember)."""
        if key is None:
            return None
        entry = {
            "key": key,
            "book_id": str(book_id),
            "poi_id": poi_id,
            "route_key": self.route_key(book_id, poi_id),
            # Reported for traceability only — NEVER a pruning clock.
            "window_end": window_end,
        }
        self._entries.append(entry)
        return entry

    def release(self, identity) -> int:
        """Forget the plan of ``identity`` (route key ``book|poi`` or POI id).

        Called from the adapter's liveness seam: a plan that can no longer
        trade (workflow dropped, window closed unplaced, zone violated, POI
        retired) must not suppress a later, genuinely new plan.
        """
        if identity is None:
            return 0
        wanted = str(identity)
        kept = [
            entry for entry in self._entries
            if entry["route_key"] != wanted and str(entry["poi_id"]) != wanted
        ]
        removed = len(self._entries) - len(kept)
        self._entries = kept
        return removed


# --------------------------------------------------------------------------- #
# Multiplexer — the drop-in menu surface
# --------------------------------------------------------------------------- #
class ParallelBookMenu:
    """N dedicated books on ONE symbol, sharing ONE risk envelope.

    Construction is explicit: nothing here is reachable unless a caller (the
    operator config or a research harness) passes a non-empty book list.
    """

    #: M-3: a POI whose tier no book carries must NOT fall back to the
    #: archived single-menu seek path. The adapter reads this flag.
    refuses_uncovered_tiers = True

    def __init__(
        self,
        books,
        *,
        symbol: str = "XAUUSD",
        same_bar_asof: bool = False,
        atr_period: int = 14,
    ) -> None:
        books = tuple(books)
        if not books:
            raise ValueError(
                "ParallelBookMenu needs at least one book; use "
                "ProductMenuEngine for the production single-menu path"
            )
        ids = [book.book_id for book in books]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate book ids: {ids}")
        self.books = books
        self.symbol = symbol
        self._by_id = {book.book_id: book for book in books}
        # ONE engine per book: separate armed map, episodes and one-shot set.
        # ``tiers=`` is honoured by ``tier_for`` for the instance, so no module
        # global is patched (the R1 harness patched it; that cannot isolate N
        # books in one process).
        self._engines: dict[str, ProductMenuEngine] = {
            book.book_id: ProductMenuEngine(
                symbol=symbol,
                same_bar_asof=same_bar_asof,
                atr_period=atr_period,
                tiers=book.menu_tiers(),
            )
            for book in books
        }
        # Fixed processing order (design §3.2-5): stable book id order, so a
        # bar's journal is reproducible and feed order never decides.
        self._order: tuple[str, ...] = tuple(
            book.book_id for book in sorted(books, key=lambda b: b.book_id)
        )
        self.detection_timeframes: tuple[Timeframe, ...] = tuple(
            dict.fromkeys(
                tf for book in books for tf in book.detection_timeframes
            )
        )
        self.confirmation_timeframes: tuple[Timeframe, ...] = tuple(
            dict.fromkeys(
                ctf
                for book in books
                for tier in book.menu_tiers()
                for ctf in tier.confirmation_tfs
            )
        )
        # Admitted cross-book plans (C-1). DURABLE: scoped by plan liveness,
        # not by the menu window — see :class:`CrossBookPlanRegistry`.
        self.cross_book_plans = CrossBookPlanRegistry()
        self._events: list[dict] = []
        self._stats: dict = {
            "cross_book_duplicates": 0,
            "cross_opposite_direction": 0,
            "book_winners": {bid: 0 for bid in self._order},
            "books_emitted": {bid: 0 for bid in self._order},
        }

    # ------------------------------------------------------------------ #
    # Read-only surface (the adapter/console duck-type)
    # ------------------------------------------------------------------ #
    def engine(self, book_id: str) -> ProductMenuEngine:
        """The book's own engine (read-only inspection for harnesses)."""
        return self._engines[str(book_id)]

    def book(self, book_id: str) -> BookConfig:
        return self._by_id[str(book_id)]

    @property
    def winners(self) -> list[MenuWinner]:
        """Every winner emitted so far, in book/processing order."""
        return [w for bid in self._order for w in self._engines[bid].winners]

    @property
    def sweeps_total(self) -> int:
        return sum(engine.sweeps_total for engine in self._engines.values())

    @property
    def _armed(self) -> dict:
        """Merged arming maps (adapter ``menu_covers_poi`` reads this)."""
        merged: dict = {}
        for bid in self._order:
            merged.update(self._engines[bid]._armed)
        return merged

    @property
    def _consumed(self) -> set:
        """Union of per-book consumed POIs (per book, union is read-only)."""
        consumed: set = set()
        for bid in self._order:
            consumed |= set(self._engines[bid]._consumed)
        return consumed

    @property
    def _episodes(self) -> list:
        return [ep for bid in self._order for ep in self._engines[bid].episodes()]

    def episodes(self) -> tuple:
        return tuple(self._episodes)

    def active_count(self) -> int:
        return sum(engine.active_count() for engine in self._engines.values())

    def tier_for(self, detection_tf: Timeframe) -> MenuTier | None:
        """First covering book's tier (``None`` when no book carries it)."""
        for bid in self._order:
            engine = self._engines[bid]
            if detection_tf in engine.detection_timeframes:
                return engine.tier_for(detection_tf)
        return None

    def counters(self) -> dict:
        """Aggregate + per-book funnel counters (measurement only)."""
        per_book = {bid: self._engines[bid].counters() for bid in self._order}
        aggregate: dict = {}
        for counters in per_book.values():
            for key, value in counters.items():
                if isinstance(value, int):
                    aggregate[key] = aggregate.get(key, 0) + value
        aggregate["cross_book_duplicates"] = self._stats["cross_book_duplicates"]
        aggregate["cross_opposite_direction"] = self._stats[
            "cross_opposite_direction"
        ]
        aggregate["cross_book_plans_live"] = len(self.cross_book_plans)
        aggregate["books"] = per_book
        aggregate["book_winner_counts"] = dict(self._stats["book_winners"])
        aggregate["book_emitted_counts"] = dict(self._stats["books_emitted"])
        return aggregate

    def book_stats(self) -> dict:
        """Per-book one-line stats for reports/journals."""
        return {
            bid: {
                "book_id": bid,
                "tag": self._by_id[bid].tag_letter,
                "tiers": list(self._by_id[bid].detection_tiers),
                "winners": self._stats["book_winners"][bid],
                "emitted": self._stats["books_emitted"][bid],
                "counters": self._engines[bid].counters(),
            }
            for bid in self._order
        }

    def cross_book_events(self) -> tuple[dict, ...]:
        """Machine-readable cross-book decisions (dedupe + direction conflicts)."""
        return tuple(self._events)

    def release_plan(self, identity) -> int:
        """C-1 liveness seam: the plan of ``identity`` no longer trades.

        ``identity`` is the adapter's route key (``<book>|<poi>``) or a plain
        POI id. Called by :class:`~smc.backtest.pipeline_adapter.PipelineAdapter`
        when a claim dies (workflow dropped, window closed unplaced, zone
        violated, POI retired) — the registry is bounded by liveness, never
        by a timer.
        """
        return self.cross_book_plans.release(identity)

    def tag_purity(self) -> dict[str, set]:
        """Trigger letters emitted per book (``{tag: 100%}`` expected)."""
        purity: dict[str, set] = {bid: set() for bid in self._order}
        for bid in self._order:
            for winner in self._engines[bid].winners:
                purity[bid].add(
                    str(getattr(winner.trigger, "value", winner.trigger)).upper()
                )
        return purity

    def assert_tag_purity(self) -> None:
        """Fail loud on a cross-tag leak (mirrors R1's in-worker check)."""
        for bid, seen in self.tag_purity().items():
            tag = self._by_id[bid].tag_letter
            if tag is None:
                continue  # production book legitimately carries many letters
            bad = sorted(seen - {tag})
            if bad:
                raise RuntimeError(
                    f"CROSS_TAG_LEAK in book {bid}: triggers {bad} emitted by a "
                    f"pure {tag} book"
                )

    # ------------------------------------------------------------------ #
    # Arming / lifecycle / state (fan-out)
    # ------------------------------------------------------------------ #
    def register_armed(self, poi, detection_tf: Timeframe,
                       armed_ts=None) -> bool:
        """Arm the POI in every book that carries this detection tier.

        Returns ``True`` when at least one book accepted it. A book that does
        not carry the tier is never asked, so a book can never arm a POI
        outside its own detection set.
        """
        accepted = False
        for bid in self._order:
            engine = self._engines[bid]
            if detection_tf not in engine.detection_timeframes:
                continue
            if engine.register_armed(poi, detection_tf, armed_ts=armed_ts):
                accepted = True
        return accepted

    def retire(self, poi_id) -> bool:
        """Drop the POI's arming bookkeeping in every book (F6)."""
        retired = False
        for bid in self._order:
            if self._engines[bid].retire(poi_id):
                retired = True
        return retired

    def set_state_source(self, resolver) -> None:
        """Wire the ONE §5 state resolver into every book (F6)."""
        for engine in self._engines.values():
            engine.set_state_source(resolver)

    # ------------------------------------------------------------------ #
    # Per-bar execution
    # ------------------------------------------------------------------ #
    def on_execution_bar(self, closed, *, as_of) -> list[MenuWinner]:
        """Run every book on the same closed feed and collect admitted winners.

        Books run in fixed order. Each winner is stamped with its book
        identity; an executable plan already admitted by ANOTHER book — at
        ANY earlier point of the session, not only inside its menu window —
        suppresses the second ticket (counter + event), so two tags
        confirming the same order can never double-lot.
        """
        emitted: list[MenuWinner] = []
        for bid in self._order:
            engine = self._engines[bid]
            book = self._by_id[bid]
            for winner in engine.on_execution_bar(closed, as_of=as_of):
                self._stats["book_winners"][bid] += 1
                candidate = self._stamp(winner.candidate, book)
                key = cross_book_plan_key(candidate)
                owner = self._duplicate_owner(key, bid)
                if owner is not None:
                    self._stats["cross_book_duplicates"] += 1
                    self._events.append({
                        "event": "cross_book_duplicate",
                        "book_id": bid,
                        "tag": book.tag_letter,
                        "poi_id": winner.poi_id,
                        "owner_book": owner["book_id"],
                        "owner_poi": owner["poi_id"],
                        "as_of": as_of.isoformat() if as_of else None,
                    })
                    continue
                self.cross_book_plans.remember(
                    key,
                    book_id=bid,
                    poi_id=winner.poi_id,
                    window_end=winner.window_end_ts,
                )
                self._note_direction_conflict(key, bid, winner, as_of)
                self._stats["books_emitted"][bid] += 1
                emitted.append(
                    replace(winner, candidate=candidate)
                )
        return emitted

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _stamp(self, candidate, book: BookConfig):
        """Attach ``book_id`` / ``book_tag`` to the candidate's menu stamp."""
        try:
            payload = json.loads(getattr(candidate, "signal_data_json", "") or "{}")
        except (TypeError, ValueError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        stamp = payload.get("product_menu")
        stamp = dict(stamp) if isinstance(stamp, dict) else {}
        stamp["book_id"] = book.book_id
        stamp["book_tag"] = book.tag_letter
        payload["product_menu"] = stamp
        return replace(
            candidate,
            signal_data_json=json.dumps(payload, sort_keys=True, default=str),
        )

    def _duplicate_owner(self, key: CrossBookPlanKey | None, book_id: str) -> dict | None:
        """The other book already holding this exact plan (``None`` = free)."""
        return self.cross_book_plans.recall(key, book_id=book_id)

    def _note_direction_conflict(self, key, book_id, winner, as_of) -> None:
        """Count opposite-direction coexistence (R-B left OPEN by design).

        The spike ALLOWS it and journals it: blocking would reintroduce
        cross-book arbitration, and R1 never measured this case.
        """
        if key is None:
            return
        for plan in self.cross_book_plans.entries():
            if plan["book_id"] == book_id:
                continue
            other = plan["key"]
            if other.direction == key.direction:
                continue
            if (
                key.zone_low is None
                or key.zone_high is None
                or other.zone_low is None
                or other.zone_high is None
            ):
                continue
            if not zones_overlap(
                key.zone_high, key.zone_low, other.zone_high, other.zone_low
            ):
                continue
            self._stats["cross_opposite_direction"] += 1
            self._events.append({
                "event": "cross_opposite_direction",
                "book_id": book_id,
                "poi_id": winner.poi_id,
                "other_book": plan["book_id"],
                "other_poi": plan["poi_id"],
                "as_of": as_of.isoformat() if as_of else None,
            })
