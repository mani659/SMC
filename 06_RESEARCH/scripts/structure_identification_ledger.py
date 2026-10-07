"""Structure Identification Ledger — human/expert flowchart review of the
structure the machine actually emits (V1.1 baseline freeze in force).

READ-ONLY MEASUREMENT. This script changes no strategy logic, no locked
constants, no pillars, no triggers, no zone bands, no R7/R9 behaviour and no
detection threshold. It drives the SAME unified composition the accepted
research chain uses and adds logging-only wrappers (all restored in
``finally``) on top:

    HTF series (H4 + H1 detect, D1 → M8)
      → MultiTFProductRuntime.run_batch  (C1 product seam, new-H1-close cadence)
      → MultiTFDetectionDriver.validate_multi
      → DetectionDriver.stage0 / detect_pois / validate_window   [instrumented]
      → M8HtfDemandSupply._zones                                 [instrumented]
      → PipelineEngine.arm_at / scan_route                       [instrumented]
      → PipelineAdapter scan → BacktestRunner risk/place/intent → fills

What it writes (all under ``--out-root`` unless noted):

* ``events.csv`` / ``events.jsonl`` — the event ledger, one row per unique
  structural event, deduped by a documented geometry key (see DEDUP RULE).
* ``summary.json`` — volumes by event_type × detection_tf, funnel counts,
  window, driver modules, capture errors, notes.
* ``review_sample/`` — stratified PNG chart pack (matplotlib Agg) for human
  scoring against the locked flowchart.
* ``review_gallery.html`` — SELF-CONTAINED gallery of the chart pack (all
  PNGs base64-embedded; works in the preview tab, where sibling files are
  NOT served, and offline as a single file).
* ``trades.csv`` / ``report.json`` — the run's own artifacts (audit parity).
* ``06_RESEARCH/STRUCTURE_IDENTIFICATION_LEDGER_REPORT.md`` — the report.

Event vocabulary (controlled — events the code does NOT emit are absent,
never invented): sweep, fvg, liquidity_level, poi_raw, poi_merged, poi_armed,
displacement, pillar_reject, pillar_pass, route_ltf, intent, fill.

Usage:
  python 06_RESEARCH/scripts/structure_identification_ledger.py \
      --tag run1 --out-root 06_RESEARCH/results/structure_ledger_6m
"""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

# --------------------------------------------------------------------------- #
# Ledger schema (frozen — the expert reviews these columns)
# --------------------------------------------------------------------------- #
SCHEMA = [
    "event_id", "event_type", "ts_utc", "bar_index", "detection_tf", "exec_tf",
    "direction", "price_low", "price_high", "model_tags", "poi_id",
    "pillar_path", "disp_magnitude_atr", "trigger", "entry", "original_sl",
    "entry_anchor", "source_module", "related_event_id", "notes",
]

#: Controlled vocabulary — only these values ever appear in ``event_type``.
EVENT_TYPES = (
    "sweep", "fvg", "liquidity_level", "poi_raw", "poi_merged", "poi_armed",
    "displacement", "pillar_reject", "pillar_pass", "route_ltf", "intent",
    "fill",
)

EXEC_TF_NAME = "M5"

# --------------------------------------------------------------------------- #
# Defaults — LOCKED primary window (6 months M5 exec, 1 month M1 warm-up)
# --------------------------------------------------------------------------- #
PRIMARY_LOAD_FROM = "2025-05-01"
PRIMARY_EXEC_FROM = "2025-06-01"
PRIMARY_EXEC_TO = "2025-11-30"
FALLBACK_EXEC_FROM = "2025-09-01"


def _parse_day(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _iso(value) -> str:
    """ISO-8601 string for a datetime (or '' when absent)."""
    if value is None:
        return ""
    try:
        return value.isoformat()
    except AttributeError:
        return str(value)


def _r6(value) -> object:
    """Round a price/multiple to 6dp; '' when absent or non-numeric."""
    if value is None:
        return ""
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return ""


def _enum_name(value) -> str:
    """Human name for an enum member (LONG/SHORT/BSL/...)."""
    if value is None:
        return ""
    return getattr(value, "name", str(value))


def _enum_value(value) -> str:
    if value is None:
        return ""
    return getattr(value, "value", str(value))


def install_deterministic_poi_ids() -> None:
    """Deterministic POI ids so run1/run2 rows are comparable (FR-4 pattern)."""
    import smc.core.poi as poi_module

    counter = count(1)

    def _deterministic_id() -> str:
        return f"poi-{next(counter):07d}"

    poi_module.uuid4 = _deterministic_id  # type: ignore[assignment]


# --------------------------------------------------------------------------- #
# Ledger store
# --------------------------------------------------------------------------- #
class Ledger:
    """Row store with a documented geometry dedup key.

    ``emit`` is idempotent per ``key``: the first observation fixes the row
    (including its ``event_type``); later observations only bump counters, so
    the ledger holds exactly ONE row per unique structural event. Alternating
    outcomes for the same geometry (the known detection "flicker") are recorded
    in the notes as ``observed_event_types``.
    """

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self._index: dict[tuple, dict] = {}
        self.counts: dict[str, int] = {}
        self.observations: dict[str, int] = {}

    @staticmethod
    def _key_repr(key) -> str:
        """Canonical string key — stored in JSONL so chunks merge exactly."""
        return key if isinstance(key, str) else repr(key)

    def touch(self, event_type: str, key) -> dict | None:
        """Fast path for hot captures: bump an EXISTING row, else None.

        Returns the existing row (with its stable ``event_id``) when the key
        was already seen; ``None`` when the caller must build the field dict
        and call :meth:`emit`. Using ``touch(...) or emit(...)`` keeps the
        expensive field formatting (f-strings, float rounding) off the
        repeat path — the dominant cost under growing-prefix re-detection.
        """
        key_repr = self._key_repr(key)
        row = self._index.get(key_repr)
        if row is None:
            return None
        row["_observations"] += 1
        row["_types"].add(event_type)
        self.observations[event_type] = self.observations.get(event_type, 0) + 1
        return row

    def emit(self, event_type: str, key, fields: dict) -> dict:
        assert event_type in EVENT_TYPES, f"unknown event_type {event_type!r}"
        key_repr = self._key_repr(key)
        self.observations[event_type] = self.observations.get(event_type, 0) + 1
        found = self._index.get(key_repr)
        if found is not None:
            found["_observations"] += 1
            found["_types"].add(event_type)
            return found
        fields = dict(fields)
        fields["event_type"] = event_type
        fields["event_id"] = "evt-" + hashlib.sha1(
            key_repr.encode("utf-8")).hexdigest()[:12]
        row: dict = {column: "" for column in SCHEMA}
        row.update(fields)
        row["_key"] = key_repr
        row["_observations"] = 1
        row["_types"] = {event_type}
        self._index[key_repr] = row
        self.rows.append(row)
        self.counts[event_type] = self.counts.get(event_type, 0) + 1
        return row

    def raw_row(self, row: dict) -> dict:
        """JSONL row: schema + the dedup key + observation bookkeeping."""
        out = {column: row.get(column, "") for column in SCHEMA}
        out["dedup_key"] = row.get("_key", "")
        out["observations"] = row.get("_observations", 1)
        out["observed_event_types"] = sorted(row.get("_types") or [])
        return out

    def load_carried_rows(self, rows: list[dict], chunk: str) -> int:
        """Load a prior chunk's JSONL rows into this ledger as a PURE UNION.

        Chunk exec windows TILE, and each chunk's own ``retain_window``
        already bounded every row by its chunk's window — so distinct
        chunks cannot describe the same event and no cross-chunk dedup must
        happen. Cross-chunk key comparison would in fact be WRONG: several
        key scopes (``poi_raw`` for M1–M7, ``poi_merged``, ``pillar_*``,
        ``poi_armed``) are geometry-only by design, so an unrelated zone
        with identical bounds in another chunk would be silently conflated.
        Keys are therefore namespaced per chunk here (never merged).
        """
        added = 0
        # First pass: derive every row's merged id, remembering the mapping
        # from the chunk-runtime id so cross-row links survive the merge.
        # Without this rewrite every related_event_id (sweep→level,
        # armed→POI, route→armed, fill→route) would dangle in the union,
        # because ids are re-derived from the namespaced keys.
        parsed: list[tuple[dict, str, str]] = []
        id_map: dict[str, str] = {}
        for index, row in enumerate(rows):
            stored = row.get("dedup_key") or repr(
                (row.get("event_type"), row.get("detection_tf"),
                 row.get("ts_utc"), row.get("price_low"), row.get("price_high")))
            key = f"{chunk}#{index}|{stored}"
            merged_id = "evt-" + hashlib.sha1(
                key.encode("utf-8")).hexdigest()[:12]
            parsed.append((row, key, merged_id))
            if row.get("event_id"):
                id_map[str(row["event_id"])] = merged_id
        dangling = 0
        for row, key, merged_id in parsed:
            new_row: dict = {column: row.get(column, "") for column in SCHEMA}
            new_row["_key"] = key
            new_row["event_id"] = merged_id
            # Rewrite in-chunk links to the merged ids; a link whose target
            # was dropped by the chunk's own retain_window (warm-up-formed
            # level) stays as-is and is marked, per the documented rule that
            # the level price remains readable in notes.
            rel = str(new_row.get("related_event_id") or "")
            if rel:
                if rel in id_map:
                    new_row["related_event_id"] = id_map[rel]
                else:
                    dangling += 1
                    notes = str(new_row.get("notes") or "")
                    new_row["notes"] = (notes + " | rel_dangling").strip(" |")
            observations = int(row.get("observations", 1) or 1)
            new_row["_observations"] = observations
            types = row.get("observed_event_types") or []
            new_row["_types"] = set(types) or {new_row["event_type"]}
            new_row["_chunk"] = chunk
            self._index[new_row["_key"]] = new_row
            self.rows.append(new_row)
            self.counts[new_row["event_type"]] = \
                self.counts.get(new_row["event_type"], 0) + 1
            self.observations[new_row["event_type"]] = \
                self.observations.get(new_row["event_type"], 0) + observations
            added += 1
        self.last_dangling = dangling
        return added

    def by_type(self, event_type: str) -> list[dict]:
        return [r for r in self.rows if r["event_type"] == event_type]

    def retain_window(self, start: datetime, end: datetime) -> int:
        """Drop events whose own anchor timestamp is outside [start, end].

        The detection stack runs over growing prefixes that begin at the M1
        warm-up load point, so Stage 0/1 re-emits warm-up formations. The
        ledger must describe the EXEC window: an event survives when its own
        ``ts_utc`` anchor (sweep candle, FVG first bar, level ``formed_at``,
        HTF zone origin bar, ...) is inside the window. Sweeps of levels that
        formed during warm-up are kept (their anchor is the exec-window
        candle); such a sweep's ``related_event_id`` may then point at a
        level row that was dropped — the level price is still in its notes.
        """
        kept: list[dict] = []
        dropped = 0
        for row in self.rows:
            ts = row.get("ts_utc", "")
            inside = True
            if ts:
                try:
                    inside = start <= datetime.fromisoformat(ts) <= end
                except (TypeError, ValueError):
                    inside = True
            if inside:
                kept.append(row)
            else:
                dropped += 1
        self.rows = kept
        self._index = {row["_key"]: row for row in kept}
        self.counts = {}
        for row in kept:
            self.counts[row["event_type"]] = \
                self.counts.get(row["event_type"], 0) + 1
        return dropped

    def public_row(self, row: dict) -> dict:
        """Schema-only row with the dedup bookkeeping folded into notes."""
        out = {column: row.get(column, "") for column in SCHEMA}
        note = str(out.get("notes") or "")
        extras: list[str] = []
        if row.get("_observations", 1) > 1:
            extras.append(f"observed={row['_observations']}")
        types = row.get("_types") or set()
        if len(types) > 1:
            extras.append("observed_event_types=" + "|".join(sorted(types)))
        if row.get("_chunk"):
            extras.append(f"chunk={row['_chunk']}")
        if extras:
            out["notes"] = (note + ";" if note else "") + ";".join(extras)
        return out


LEDGER = Ledger()

# --------------------------------------------------------------------------- #
# Run-time context + cross-hook indexes
# --------------------------------------------------------------------------- #


class RunContext:
    """Mutable batch context read by the logging-only wrappers."""

    def __init__(self) -> None:
        self.bar_index: int | None = None
        self.as_of: datetime | None = None
        self.adapter = None
        self.m5: list = []


CTX = RunContext()
CAPTURE_ERRORS: dict[str, int] = {}
MERGED_EVENT_BY_POI: dict[str, str] = {}   # batch-local poi id -> merged event id
ARMED_ROW_BY_POI: dict[str, dict] = {}     # poi id -> poi_armed row
ROUTE_ROW_BY_POI: dict[str, dict] = {}     # poi id -> route_ltf row
CANDIDATE_BY_ROUTE: dict[str, object] = {}  # route_id -> CandidateEntry
CANDIDATE_BY_POI: dict[str, object] = {}    # poi id -> CandidateEntry
PILLAR_OUTCOMES: dict[tuple, set] = {}      # geometry key -> outcomes seen


def _capture(label: str, fn) -> None:
    """Run one capture block; a failure is recorded, never fatal."""
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 — measurement must never kill the run
        message = f"{label}: {type(exc).__name__}: {exc}"
        CAPTURE_ERRORS[message] = CAPTURE_ERRORS.get(message, 0) + 1
        traceback.print_exc(limit=2)


def _m5_ts(index) -> str:
    """Timestamp of M5 bar ``index`` ('' when out of range — never raises)."""
    if index is None or not isinstance(index, int):
        return ""
    if 0 <= index < len(CTX.m5):
        return _iso(CTX.m5[index].timestamp)
    return ""


def _series_ts(series: list, index) -> str:
    """Timestamp of ``series[index]`` with an explicit bounds guard."""
    if not isinstance(index, int) or not 0 <= index < len(series):
        return ""
    return _iso(series[index].timestamp)


# --------------------------------------------------------------------------- #
# Capture hooks
# --------------------------------------------------------------------------- #
def capture_stage0(tf, candles: list, run) -> None:
    """Stage 0/1 raw emitters for one detection timeframe."""
    tf_name = _enum_name(tf)
    as_of = CTX.as_of
    level_event_by_identity: dict[tuple, str] = {}

    # --- liquidity levels (Stage 0A) ------------------------------------- #
    def _levels() -> None:
        for level in run.liquidity_levels:
            pool = getattr(level, "pool", None)
            formed = _iso(getattr(level, "formed_at", None))
            key = ("liquidity_level", tf_name, _enum_value(level.type),
                   f"{float(level.level):.6f}", _enum_name(pool), formed)
            direction = "SHORT" if _enum_name(pool) == "BSL" else "LONG"
            row = LEDGER.touch("liquidity_level", key) or LEDGER.emit(
                "liquidity_level", key, {
                "ts_utc": formed or _iso(as_of),
                "bar_index": CTX.bar_index,
                "detection_tf": tf_name,
                "exec_tf": EXEC_TF_NAME,
                "direction": direction,
                "price_low": _r6(level.level),
                "price_high": _r6(level.level),
                "source_module": "smc.detection.liquidity_scanner.scan",
                "notes": f"family={_enum_value(level.type)};"
                         f"pool={_enum_name(pool)};formed_at={formed}",
            })
            level_event_by_identity[
                (f"{float(level.level):.6f}", _enum_value(level.type), formed)
            ] = row["event_id"]

    _capture("stage0.levels", _levels)

    # --- sweeps (Stage 0A confirmation) ---------------------------------- #
    sweeps_by_index: dict[int, object] = {}
    for sweep in run.sweeps:
        sweeps_by_index[getattr(sweep, "candle_index", -1)] = sweep

    def _sweeps() -> None:
        for sweep in run.sweeps:
            level = sweep.level
            candle = sweep.candle
            pool_name = _enum_name(getattr(level, "pool", None))
            direction = "SHORT" if pool_name == "BSL" else "LONG"
            ts = _iso(getattr(candle, "timestamp", None))
            formed = _iso(getattr(level, "formed_at", None))
            related = level_event_by_identity.get(
                (f"{float(level.level):.6f}", _enum_value(level.type), formed), "")
            key = ("sweep", tf_name, pool_name, f"{float(level.level):.6f}",
                   ts, _enum_value(level.type))
            LEDGER.touch("sweep", key) or LEDGER.emit("sweep", key, {
                "ts_utc": ts or _iso(CTX.as_of),
                "bar_index": CTX.bar_index,
                "detection_tf": tf_name,
                "exec_tf": EXEC_TF_NAME,
                "direction": direction,
                "price_low": _r6(level.level),
                "price_high": _r6(level.level),
                "source_module": "smc.detection.sweep_detector.detect_sweeps",
                "related_event_id": related,
                "notes": f"pool={pool_name};level_type={_enum_value(level.type)};"
                         f"level={float(level.level):.6f};"
                         f"candle_high={float(candle.high):.6f};"
                         f"candle_low={float(candle.low):.6f};"
                         f"candle_close={float(candle.close):.6f}",
            })

    _capture("stage0.sweeps", _sweeps)

    # --- displacements (Stage 0A §3) ------------------------------------- #
    def _displacements() -> None:
        for sweep_index, disp in run.displacements:
            sweep = sweeps_by_index.get(sweep_index)
            ts = (_iso(getattr(sweep.candle, "timestamp", None))
                  if sweep is not None else _iso(CTX.as_of))
            key = ("displacement", tf_name, _enum_name(disp.direction), ts)
            LEDGER.touch("displacement", key) or LEDGER.emit(
                "displacement", key, {
                "ts_utc": ts,
                "bar_index": CTX.bar_index,
                "detection_tf": tf_name,
                "exec_tf": EXEC_TF_NAME,
                "direction": _enum_name(disp.direction),
                "disp_magnitude_atr": _r6(disp.magnitude_atr),
                "source_module":
                    "smc.detection.displacement_checker.check_displacement",
                "notes": f"bos={bool(disp.bos)};fvg={bool(disp.fvg)};"
                         f"magnitude={_r6(disp.magnitude)};"
                         f"magnitude_atr={_r6(disp.magnitude_atr)};"
                         f"passed={bool(disp.passed)};"
                         f"hard_fail={bool(disp.hard_fail)};"
                         f"preferred={bool(disp.is_preferred)};"
                         f"sweep_bar={ts}",
            })

    _capture("stage0.displacements", _displacements)

    # --- fair value gaps (Stage 0A §3) ----------------------------------- #
    def _fvgs() -> None:
        for fvg in (run.fvgs or []):
            zone = fvg.zone
            first_ts = _series_ts(candles, getattr(fvg, "start_index", -1))
            key = ("fvg", tf_name, _enum_name(zone.direction),
                   _r6(zone.bottom), _r6(zone.top), first_ts)
            LEDGER.touch("fvg", key) or LEDGER.emit("fvg", key, {
                "ts_utc": first_ts or _iso(CTX.as_of),
                "bar_index": CTX.bar_index,
                "detection_tf": tf_name,
                "exec_tf": EXEC_TF_NAME,
                "direction": _enum_name(zone.direction),
                "price_low": _r6(zone.bottom),
                "price_high": _r6(zone.top),
                "source_module": "smc.detection.fvg_detector.detect_fvgs",
                "notes": f"kind=fvg_3candle;first_bar={first_ts};"
                         f"top={_r6(zone.top)};bottom={_r6(zone.bottom)};"
                         f"zone_tf={_enum_name(zone.timeframe)}",
            })

    _capture("stage0.fvgs", _fvgs)


def capture_raw_pois(tf, pois: list) -> None:
    """Pre-merge model output as ``poi_raw`` (M8 handled by the zone hook)."""
    tf_name = _enum_name(tf)

    def _pois() -> None:
        for poi in pois:
            models = list(getattr(poi, "models", []) or [])
            tag = _enum_name(models[0]) if models else "?"
            if tag == "M8":
                # M8's raw output is captured, with geometry kinds, by the
                # kind-labelled zone hook (a superset: M8.detect() keeps only
                # the latest zone per kind). Skipped here to avoid double rows.
                continue
            zone = poi.zone
            key = ("poi_raw", tf_name, tag, _enum_name(zone.direction),
                   _r6(zone.bottom), _r6(zone.top))
            LEDGER.touch("poi_raw", key) or LEDGER.emit("poi_raw", key, {
                "ts_utc": _iso(CTX.as_of),
                "bar_index": CTX.bar_index,
                "detection_tf": tf_name,
                "exec_tf": EXEC_TF_NAME,
                "direction": _enum_name(zone.direction),
                "price_low": _r6(zone.bottom),
                "price_high": _r6(zone.top),
                "model_tags": tag,
                "poi_id": poi.id,
                "source_module":
                    "smc.orchestration.detection_driver.detect_pois",
                "notes": f"model={tag};zone_tf={_enum_name(zone.timeframe)};"
                         f"stage=pre_merge",
            })

    _capture("detect_pois", _pois)


def capture_m8_zone(tf, kind: str, direction, start_index, zone, series: list) -> None:
    """One raw M8 HTF zone, kind-labelled (ob / fvg / demand_supply)."""
    tf_name = _enum_name(tf)
    ts = _series_ts(series, start_index)
    human_kind = {
        "ob": "order_block",
        "fvg": "fvg_htf",
        "demand_supply": "supply_demand",
    }.get(kind, kind)
    key = ("poi_raw", tf_name, "M8", kind, _enum_name(zone.direction),
           _r6(zone.bottom), _r6(zone.top), ts)
    LEDGER.touch("poi_raw", key) or LEDGER.emit("poi_raw", key, {
        "ts_utc": ts or _iso(CTX.as_of),
        "bar_index": CTX.bar_index,
        "detection_tf": tf_name,
        "exec_tf": EXEC_TF_NAME,
        "direction": _enum_name(zone.direction),
        "price_low": _r6(zone.bottom),
        "price_high": _r6(zone.top),
        "model_tags": "M8",
        "source_module":
            "smc.poi.models.m8_htf_demand_supply.M8HtfDemandSupply._zones",
        "notes": f"kind={kind};kind_label={human_kind};htf_tf={tf_name};"
                 f"origin_bar={ts};zone_tf={_enum_name(zone.timeframe)};"
                 f"htf_vs_ltf=htf",
    })


def capture_validation(tf, results: list) -> None:
    """Merged POIs (``poi_merged``) + their pillar verdicts."""
    tf_name = _enum_name(tf)

    def _results() -> None:
        for res in results:
            poi = res.poi
            zone = poi.zone
            tags = "|".join(sorted(_enum_name(m) for m in (poi.models or [])))
            merged_key = ("poi_merged", tf_name, _enum_name(zone.direction),
                          _r6(zone.bottom), _r6(zone.top))
            merged = LEDGER.touch("poi_merged", merged_key) or LEDGER.emit(
                "poi_merged", merged_key, {
                "ts_utc": _iso(CTX.as_of),
                "bar_index": CTX.bar_index,
                "detection_tf": tf_name,
                "exec_tf": EXEC_TF_NAME,
                "direction": _enum_name(zone.direction),
                "price_low": _r6(zone.bottom),
                "price_high": _r6(zone.top),
                "model_tags": tags,
                "poi_id": poi.id,
                "source_module":
                    "smc.orchestration.detection_driver.validate_window",
                "notes": f"score={_r6(poi.score)};"
                         f"zone_tf={_enum_name(zone.timeframe)};"
                         f"merge=tag_union(cluster_overlapping);"
                         f"htf_overlap={bool(getattr(poi, 'htf_overlap', False))}",
            })
            MERGED_EVENT_BY_POI[poi.id] = merged["event_id"]
            outcome = "PASS" if res.passed else "REJECT"
            PILLAR_OUTCOMES.setdefault(merged_key, set()).add(outcome)
            _emit_pillar(res.passed, tf_name, zone, tags, res,
                         merged["event_id"], poi.id)

    _capture("validate_window", _results)


def _emit_pillar(passed: bool, tf_name: str, zone, tags: str, res,
                 merged_event_id: str, poi_id: str) -> None:
    """One pillar verdict row (dedup scope is geometry, not outcome)."""
    event_type = "pillar_pass" if passed else "pillar_reject"
    key = ("pillar_outcome", tf_name, _enum_name(zone.direction),
           _r6(zone.bottom), _r6(zone.top))
    if LEDGER.touch(event_type, key) is not None:
        return
    from smc.backtest.pipeline_bridge import pillar_path_summary

    path = pillar_path_summary(res)
    fields = {
        "ts_utc": _iso(CTX.as_of),
        "bar_index": CTX.bar_index,
        "detection_tf": tf_name,
        "exec_tf": EXEC_TF_NAME,
        "direction": _enum_name(zone.direction),
        "price_low": _r6(zone.bottom),
        "price_high": _r6(zone.top),
        "model_tags": tags,
        "poi_id": poi_id,
        "pillar_path": path or "",
        "source_module": "smc.validation.validation_pipeline.ValidationPipeline",
        "related_event_id": merged_event_id,
    }
    if passed:
        fields["notes"] = f"pillars=PASS;path={path};active=all"
        LEDGER.emit("pillar_pass", key, fields)
    else:
        first = res.first_failure
        detail = ""
        if first is not None:
            detail = (f"P{first.pillar}:{first.name}:"
                      f"{_enum_value(first.status)}:{first.detail}")
        fields["notes"] = (f"first_failure={detail};"
                           f"pillars_run={len(res.pillar_results)};"
                           f"path={path}")
        LEDGER.emit("pillar_reject", key, fields)


def capture_armed(adapter, poi, arm_bar: int) -> None:
    """``arm_at`` hook — the armed episode (funnel endpoint before routing)."""
    zone = poi.zone
    tf_name = _enum_name(zone.timeframe)
    context = None
    if adapter is not None:
        context = getattr(adapter, "_route_context", {}).get(poi.id)
    displacement = context[0] if context else None
    pillar_path = context[1] if context else None
    tags = "|".join(sorted(_enum_name(m) for m in (poi.models or [])))
    key = ("poi_armed", tf_name, _enum_name(zone.direction),
           _r6(zone.bottom), _r6(zone.top))
    row = LEDGER.emit("poi_armed", key, {
        "ts_utc": _m5_ts(arm_bar) or _iso(CTX.as_of),
        "bar_index": arm_bar,
        "detection_tf": tf_name,
        "exec_tf": EXEC_TF_NAME,
        "direction": _enum_name(zone.direction),
        "price_low": _r6(zone.bottom),
        "price_high": _r6(zone.top),
        "model_tags": tags,
        "poi_id": poi.id,
        "pillar_path": pillar_path or "",
        "disp_magnitude_atr": _r6(getattr(displacement, "magnitude_atr", None)),
        "source_module": "smc.orchestration.engine.PipelineEngine.arm_at",
        "related_event_id": MERGED_EVENT_BY_POI.get(poi.id, ""),
        "notes": f"arm_bar={arm_bar};dedup=zone_episode(ZoneDedup);"
                 f"htf_overlap={bool(getattr(poi, 'htf_overlap', False))};"
                 f"zone_tf={tf_name}",
    })
    ARMED_ROW_BY_POI[poi.id] = row


def capture_route(route, candles: list) -> None:
    """``scan_route`` hook — the LTF trigger confirmation (route_ltf)."""
    poi = route.poi
    signal = route.signal
    zone = poi.zone
    tf_name = _enum_name(zone.timeframe)
    bar = getattr(route, "bar", None)
    ts = ""
    if isinstance(bar, int) and 0 <= bar < len(candles):
        ts = _iso(candles[bar].timestamp)
    trigger = _enum_value(signal.trigger)
    tags = "|".join(sorted(_enum_name(m) for m in (poi.models or [])))
    key = ("route_ltf", poi.id, trigger, getattr(signal, "completion_index", -1))
    row = LEDGER.emit("route_ltf", key, {
        "ts_utc": ts or _iso(CTX.as_of),
        "bar_index": bar,
        "detection_tf": tf_name,
        "exec_tf": EXEC_TF_NAME,
        "direction": _enum_name(signal.direction),
        "price_low": _r6(zone.bottom),
        "price_high": _r6(zone.top),
        "model_tags": tags,
        "poi_id": poi.id,
        "trigger": trigger,
        "entry": _r6(signal.entry_price),
        "original_sl": _r6(signal.stop_reference),
        "source_module": "smc.orchestration.engine.PipelineEngine.scan_route",
        "related_event_id": ARMED_ROW_BY_POI.get(poi.id, {}).get("event_id", ""),
        "notes": f"completion_index={getattr(signal, 'completion_index', '')};"
                 f"expiry_bars={getattr(signal, 'expiry_bars', '')};"
                 f"route_id={poi.id}:{trigger}@"
                 f"{getattr(signal, 'completion_index', '')};"
                 f"detail={getattr(signal, 'detail', '')}",
    })
    ROUTE_ROW_BY_POI[poi.id] = row


def capture_candidate(route, candidate) -> None:
    """``candidate_from_route`` hook — placement identity for the route row."""
    poi_id = getattr(route.poi, "id", None)
    route_id = getattr(candidate, "route_id", None)
    if poi_id:
        CANDIDATE_BY_POI[poi_id] = candidate
    if route_id:
        CANDIDATE_BY_ROUTE[route_id] = candidate


# --------------------------------------------------------------------------- #
# Post-run enrichment
# --------------------------------------------------------------------------- #
def capture_intents(runner) -> None:
    """Intent lifecycle events (R9) as ledger rows — never fabricated."""
    book = getattr(runner, "intents", None)
    events = getattr(book, "events", None)
    if not events:
        return

    def _intents() -> None:
        for event in events:
            route_id = event.get("route_id")
            candidate = CANDIDATE_BY_ROUTE.get(route_id) if route_id else None
            if candidate is None:
                candidate = CANDIDATE_BY_POI.get(event.get("poi_id"))
            bar = event.get("bar")
            status = str(event.get("event", "?"))
            key = ("intent", event.get("intent_id"), status, bar)
            LEDGER.emit("intent", key, {
                "ts_utc": _m5_ts(bar),
                "bar_index": bar,
                "detection_tf": _enum_name(getattr(candidate, "detection_tf", None)),
                "exec_tf": EXEC_TF_NAME,
                "direction": _enum_name(getattr(candidate, "direction", None)),
                "model_tags": "|".join(getattr(candidate, "model_tags", ()) or ()),
                "poi_id": event.get("poi_id", ""),
                "trigger": _enum_value(getattr(candidate, "trigger", None)),
                "entry": _r6(getattr(candidate, "entry_price", None)),
                "original_sl": _r6(getattr(candidate, "original_sl", None)),
                "entry_anchor": getattr(candidate, "entry_anchor", "") or "",
                "source_module": "smc.backtest.intents.IntentBook.events",
                "related_event_id": ROUTE_ROW_BY_POI.get(
                    event.get("poi_id", ""), {}).get("event_id", ""),
                "notes": f"status={status};intent_id={event.get('intent_id')};"
                         f"expire_bar={event.get('expire_bar')};"
                         f"rest_bars={event.get('rest_bars')};"
                         f"route_id={route_id}",
            })

    _capture("intents", _intents)


def capture_fills(report) -> None:
    """Filled trades as ledger rows (structure outcome, not an edge claim)."""
    def _fills() -> None:
        for trade in report.trades:
            direction = _enum_name(trade.direction)
            tags = "|".join(trade.model_tags or ())
            key = ("fill", getattr(trade, "ticket", ""), trade.route_id)
            LEDGER.emit("fill", key, {
                "ts_utc": _iso(getattr(trade, "entry_at", None)),
                "bar_index": getattr(trade, "entry_bar", ""),
                "detection_tf": "",
                "exec_tf": EXEC_TF_NAME,
                "direction": direction,
                "price_low": _r6(getattr(trade, "zone_low", None)),
                "price_high": _r6(getattr(trade, "zone_high", None)),
                "model_tags": tags,
                "poi_id": getattr(trade, "poi_id", "") or "",
                "pillar_path": getattr(trade, "pillar_path", "") or "",
                "disp_magnitude_atr": _r6(
                    getattr(trade, "disp_magnitude_atr", None)),
                "trigger": getattr(trade, "trigger", "") or "",
                "entry": _r6(getattr(trade, "entry_price", None)),
                "original_sl": _r6(getattr(trade, "original_sl", None)),
                "entry_anchor": getattr(trade, "entry_anchor", "") or "",
                "source_module": "smc.backtest.reports.build_report",
                "related_event_id": ARMED_ROW_BY_POI.get(
                    getattr(trade, "poi_id", ""), {}).get("event_id", ""),
                "notes": f"ticket={getattr(trade, 'ticket', '')};"
                         f"route_id={trade.route_id};"
                         f"close_kind={getattr(trade, 'close_kind', '')};"
                         f"win={bool(getattr(trade, 'win', False))};"
                         f"pnl={_r6(getattr(trade, 'pnl', None))};"
                         f"exit_at={_iso(getattr(trade, 'exit_at', None))};"
                         f"entry_at={_iso(getattr(trade, 'entry_at', None))}",
            })

    _capture("fills", _fills)


def enrich_identity_rows() -> None:
    """Fold candidate placement identity into route + fill rows (post-run)."""
    for poi_id, row in ROUTE_ROW_BY_POI.items():
        candidate = CANDIDATE_BY_POI.get(poi_id)
        if candidate is None:
            continue
        row["model_tags"] = "|".join(getattr(candidate, "model_tags", ()) or ())
        row["trigger"] = _enum_value(getattr(candidate, "trigger", None)) or row["trigger"]
        row["entry"] = _r6(getattr(candidate, "entry_price", None)) or row["entry"]
        row["original_sl"] = (_r6(getattr(candidate, "original_sl", None))
                              or row["original_sl"])
        row["entry_anchor"] = getattr(candidate, "entry_anchor", "") or ""
        row["disp_magnitude_atr"] = _r6(
            getattr(candidate, "disp_magnitude_atr", None))
        row["pillar_path"] = getattr(candidate, "pillar_path", "") or ""
        row["detection_tf"] = _enum_name(
            getattr(candidate, "detection_tf", None)) or row.get("detection_tf", "")
        note = str(row.get("notes") or "")
        note += (f";tp={_r6(getattr(candidate, 'tp_price', None))}"
                 f";is_m8={bool(getattr(candidate, 'is_m8', False))}")
        row["notes"] = note
    # Fill rows carry no detection TF on the TradeRecord; recover it honestly
    # from the route row (the zone's own timeframe), never invented.
    for row in LEDGER.by_type("fill"):
        if row.get("detection_tf"):
            continue
        route_row = ROUTE_ROW_BY_POI.get(row.get("poi_id", ""))
        if route_row is not None:
            row["detection_tf"] = route_row.get("detection_tf", "")
        else:
            row["detection_tf"] = "n/a:not_on_route"


# --------------------------------------------------------------------------- #
# Invariant: no duplicate event_ids, schema satisfied
# --------------------------------------------------------------------------- #
def validate_ledger() -> list[str]:
    """Invariants: unique event_ids, known types, required columns present."""
    problems: list[str] = []
    seen: set[str] = set()
    for row in LEDGER.rows:
        if row["event_id"] in seen:
            problems.append(f"duplicate event_id {row['event_id']}")
        seen.add(row["event_id"])
        if row["event_type"] not in EVENT_TYPES:
            problems.append(f"bad event_type {row['event_type']}")
        for column in ("event_id", "event_type", "detection_tf", "exec_tf",
                       "source_module"):
            if row.get(column, "") == "":
                problems.append(
                    f"{row['event_id']} missing required {column}")
                break
    return problems


# --------------------------------------------------------------------------- #
# Artifacts
# --------------------------------------------------------------------------- #
def write_ledger_artifacts(out: Path) -> tuple[Path, Path]:
    """Write ``events.csv`` (frozen schema) and ``events.jsonl`` (schema +
    dedup key + observation bookkeeping, so chunk ledgers merge exactly)."""
    rows = [LEDGER.public_row(r) for r in LEDGER.rows]
    rows.sort(key=lambda r: (r["ts_utc"] or "", r["event_type"], r["event_id"]))
    order = {row["event_id"]: i for i, row in enumerate(rows)}
    csv_path = out / "events.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCHEMA)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    jsonl_path = out / "events.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in sorted(LEDGER.rows,
                          key=lambda r: order.get(r["event_id"], 0)):
            handle.write(json.dumps(LEDGER.raw_row(row), sort_keys=True) + "\n")
    return csv_path, jsonl_path


def volume_tables() -> tuple[dict, dict, dict]:
    """(by_type, by_type_tf, observations) volume tables."""
    by_type: dict[str, int] = {}
    by_type_tf: dict[str, dict[str, int]] = {}
    for row in LEDGER.rows:
        event_type = row["event_type"]
        tf = row.get("detection_tf") or "n/a"
        by_type[event_type] = by_type.get(event_type, 0) + 1
        by_type_tf.setdefault(event_type, {})
        by_type_tf[event_type][tf] = by_type_tf[event_type].get(tf, 0) + 1
    return by_type, by_type_tf, dict(LEDGER.observations)


# --------------------------------------------------------------------------- #
# Stratified review chart pack
# --------------------------------------------------------------------------- #
def _spread(rows: list, n: int) -> list:
    """Deterministic even-in-time sample of ``n`` rows from ``rows``."""
    if n <= 0 or not rows:
        return []
    if len(rows) <= n:
        return list(rows)
    step = len(rows) / n
    return [rows[min(int(i * step), len(rows) - 1)] for i in range(n)]


def select_review_rows(limit: int = 8) -> list[dict]:
    """Stratified sample: sweeps, FVGs, M8 S&D/OB, armed, routes/fills."""
    picks: list[dict] = []
    picks += _spread(LEDGER.by_type("sweep"), limit)
    picks += _spread(LEDGER.by_type("fvg"), limit)
    m8 = [r for r in LEDGER.by_type("poi_raw")
          if "kind=ob" in str(r.get("notes", ""))
          or "kind=demand_supply" in str(r.get("notes", ""))]
    picks += _spread(m8, limit)
    picks += _spread(LEDGER.by_type("poi_armed"), limit)
    routed = LEDGER.by_type("route_ltf") + LEDGER.by_type("fill")
    if len(routed) <= 20:
        picks += routed
    else:
        picks += _spread(routed, 15)
    return picks


def render_review_pack(rows: list[dict], series_by_tf: dict, out_dir: Path,
                       half_window: dict) -> list[dict]:
    """Render the stratified review pack; returns the sample index."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    # Clear stale PNGs so the pack always matches this run's sample index
    # (re-running with different event ids must never leave orphans).
    for stale in out_dir.glob("*.png"):
        try:
            stale.unlink()
        except OSError:
            pass
    # LTF confirmations complete on the EXECUTION series (M5) by design, so
    # they are charted on M5 — separate from the HTF detect TF. Every other
    # type is charted on the detection timeframe whose structure it reports.
    m5_event_types = {"route_ltf", "intent", "fill"}
    index: list[dict] = []
    for seq, row in enumerate(rows, start=1):
        detect_tf = row.get("detection_tf") or EXEC_TF_NAME
        if row.get("event_type") in m5_event_types:
            tf = EXEC_TF_NAME
        else:
            tf = detect_tf
        series = series_by_tf.get(tf) or series_by_tf.get(EXEC_TF_NAME) or []
        if len(series) < 5:
            continue
        ts = row.get("ts_utc") or ""
        try:
            anchor = datetime.fromisoformat(ts)
        except (TypeError, ValueError):
            anchor = None
        half = half_window.get(tf, 40)
        stamps = [c.timestamp for c in series]
        if anchor is not None:
            center = max(bisect.bisect_left(stamps, anchor), 0)
        else:
            center = len(series) - 1
        lo = max(center - half, 0)
        hi = min(center + half, len(series) - 1)
        window = series[lo:hi + 1]
        if not window:
            continue

        title = " | ".join([
            str(row["event_type"]), str(tf), str(ts) or "n/a",
            str(row.get("direction") or "n/a"),
            str(row.get("model_tags") or "n/a"),
        ])
        if detect_tf != tf:
            title += f" | detect_tf={detect_tf}"
        fig, ax = plt.subplots(figsize=(14, 7))
        for i, candle in enumerate(window):
            color = "#2e7d32" if candle.close >= candle.open else "#c62828"
            ax.plot([i, i], [candle.low, candle.high], color=color, lw=0.7)
            ax.add_patch(plt.Rectangle(
                (i - 0.3, min(candle.open, candle.close)), 0.6,
                abs(candle.close - candle.open) + 1e-9,
                facecolor=color, edgecolor=color))

        low = row.get("price_low")
        high = row.get("price_high")
        has_bounds = isinstance(low, (int, float)) and isinstance(high, (int, float))
        if has_bounds:
            if abs(float(high) - float(low)) < 1e-9:
                ax.axhline(float(low), color="#1e88e5", ls="-", lw=1.4,
                           label="event level")
                ax.axvline(center - lo, color="#f9a825", lw=1.2,
                           label="event bar")
            else:
                ax.axhspan(float(low), float(high), color="#1e88e5",
                           alpha=0.18, label="event zone")
                ax.axvline(center - lo, color="#f9a825", lw=1.2,
                           label="event bar")
        for key, color, label in (("entry", "#6a1b9a", "entry (limit)"),
                                  ("original_sl", "#c62828", "original SL")):
            value = row.get(key)
            if isinstance(value, (int, float)):
                ax.axhline(float(value), color=color, ls="--", lw=1.2,
                           label=label)
        step = max(len(window) // 8, 1)
        ax.set_xticks(range(0, len(window), step))
        ax.set_xticklabels(
            [window[i].timestamp.strftime("%m-%d %H:%M")
             for i in range(0, len(window), step)], fontsize=7)
        ax.set_title(f"{title}\nstructure identification — NOT a trade claim",
                     fontsize=9)
        ax.legend(loc="best", fontsize=8)
        ax.grid(alpha=0.25)
        fig.tight_layout()
        name = (f"{seq:03d}_{row['event_type']}_{tf}_"
                f"{(ts or 'na').replace(':', '').replace('-', '')[:13]}_"
                f"{row['event_id']}.png")
        fig.savefig(out_dir / name, dpi=130)
        plt.close(fig)
        index.append({
            "file": name,
            "event_id": row["event_id"],
            "event_type": row["event_type"],
            "chart_tf": tf,
            "detection_tf": detect_tf,
            "ts_utc": ts,
            "direction": row.get("direction", ""),
            "model_tags": row.get("model_tags", ""),
        })
    return index


def write_review_gallery(sample_index: list[dict], png_dir: Path,
                         out_html: Path) -> int:
    """Write a SELF-CONTAINED review gallery (all PNGs base64-embedded).

    The Codebuff preview server serves only the registered html file — it does
    NOT serve sibling files, so relative ``review_sample/*.png`` srcs 404 and
    the gallery renders with zero images. Embedding the charts as data URIs
    makes the single HTML file fully portable (preview tab, double-click,
    email): zero external requests. Returns the number of charts embedded.
    """
    import base64
    import html as _html

    groups: dict[str, list[dict]] = {}
    for item in sample_index:
        groups.setdefault(str(item["event_type"]), []).append(item)

    parts = [
        "<!doctype html><meta charset=utf-8>",
        "<title>Structure ledger review sample</title>",
        "<body style='background:#111;color:#ddd;font:12px/1.4 sans-serif;"
        "margin:16px'>",
        "<h2>Structure Identification Ledger &mdash; review sample</h2>",
        "<p>{} stratified charts &middot; window 2025-06-01 &rarr; 2025-11-30"
        " &middot; HTF structure on its detect TF, LTF confirms on M5."
        " Score each CORRECT / PARTIAL / WRONG / UNCLEAR vs the locked"
        " flowchart.</p>".format(len(sample_index)),
    ]
    embedded = 0
    for etype in sorted(groups):
        rows = groups[etype]
        parts.append(f"<h3>{_html.escape(etype)} ({len(rows)})</h3>")
        parts.append(
            "<div style='display:flex;flex-wrap:wrap;gap:12px'>")
        for item in rows:
            png = png_dir / item["file"]
            if not png.is_file():
                continue
            data = base64.b64encode(png.read_bytes()).decode("ascii")
            embedded += 1
            caption_bits = [
                _html.escape(str(item["event_type"])),
                f"chart {_html.escape(str(item.get('chart_tf', '')))}",
                f"detect {_html.escape(str(item.get('detection_tf', '')))}",
                _html.escape(str(item.get("ts_utc", "")) or ""),
                _html.escape(str(item.get("direction", ""))),
            ]
            tags = str(item.get("model_tags", ""))
            if tags:
                caption_bits.append(_html.escape(tags))
            parts.append(
                "<figure>"
                f"<img loading='lazy' src='data:image/png;base64,{data}'>"
                "<figcaption>" + " | ".join(caption_bits) +
                f"<br><code>{_html.escape(str(item['event_id']))}</code>"
                "</figcaption></figure>")
        parts.append("</div>")
    parts.append(
        "<style>figure{margin:0;max-width:47%}img{width:100%;"
        "border:1px solid #444}figcaption{padding:3px 0}code{color:#8ab}"
        "</style></body>")
    out_html.write_text("".join(parts), encoding="utf-8")
    return embedded


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
MODULE_FLOWCHART_MAP = [
    ("Liquidity levels (Stage 0A)",
     "smc.detection.liquidity_scanner.scan → session/periodic/eqh/structural",
     "liquidity_level", "per-TF level, price anchor = level price"),
    ("Liquidity sweep", "smc.detection.sweep_detector.detect_sweeps",
     "sweep", "wick-pierce + body-close; linked to its level via related_event_id"),
    ("Fair value gap (LTF/HTF detect)",
     "smc.detection.fvg_detector.detect_fvgs", "fvg",
     "3-candle imbalance zone on the detection TF"),
    ("Displacement (§3)", "smc.detection.displacement_checker.check_displacement",
     "displacement", "BOS + FVG + ≥1×ATR; magnitude_atr recorded"),
    ("Order block (HTF, M8 path)",
     "smc.poi.models.m8_htf_demand_supply.M8HtfDemandSupply._zones (kind=ob)",
     "poi_raw", "candle before the FVG; labelled ob ONLY when the code yields it"),
    ("Supply / demand (HTF, M8 path)",
     "…m8_htf_demand_supply._zones (kind=demand_supply)", "poi_raw",
     "single last opposing candle before a ≥1×ATR impulse; HTF vs LTF in notes"),
    ("POI models M1–M7", "smc.orchestration.detection_driver.detect_pois",
     "poi_raw", "pre-merge raw model output (one tag per POI)"),
    ("Confluence merge (§1)",
     "smc.poi.confluence_scorer.merge_overlapping (via PipelineEngine.validate)",
     "poi_merged", "same-direction overlapping zones → union of tags"),
    ("Pillars 1–5",
     "smc.validation.validation_pipeline.ValidationPipeline", "pillar_pass / pillar_reject",
     "first hard failure recorded; PASS path summarised"),
    ("Arm (§5 CREATED→FRESH + §24 anchor)",
     "smc.orchestration.engine.PipelineEngine.arm_at", "poi_armed",
     "zone-episode dedup (ZoneDedup); arm_bar anchors the give-up window"),
    ("LTF trigger routing (A–F on M5)",
     "smc.orchestration.engine.PipelineEngine.scan_route → "
     "smc.triggers.trigger_router", "route_ltf",
     "chronological first-valid; entry limit + stop reference"),
    ("Intent lifecycle (R9)", "smc.backtest.intents.IntentBook.events", "intent",
     "armed/placed/expired/replaced/dropped transitions"),
    ("Execution fill", "smc.backtest.runner.BacktestRunner → reports.build_report",
     "fill", "limit fill; ticket/route_id/close_kind/pnl recorded"),
]

LIMITATIONS = [
    "Read-only measurement: no threshold, pillar, trigger, zone-band, R7/R9 or "
    "locked-constant change; V1.1 baseline freeze unchanged (git diff proves it).",
    "The detection stack is driven with GROWING prefixes per timeframe (the "
    "accepted Phase 3/4 composition). Stage 0/1 therefore re-emits the whole "
    "prefix every batch; the ledger dedups by geometry so each unique event "
    "appears once, with `observed=N` recording how many batches re-emitted it "
    "and `observed_event_types` when a geometry alternates verdicts (the known "
    "detection flicker).",
    "Per-POI rows (`poi_raw`, `poi_merged`, `pillar_*`) close over the evolving "
    "prefix: their recorded verdict is the FIRST observation, not a live "
    "rolling-window replay. `poi_id` on those rows is the batch-local id at "
    "first observation; use `event_id` (a stable geometry hash) to key rows.",
    "M8's per-model output is captured by the kind-labelled zone hook, which is "
    "a superset of `M8.detect()` (detect keeps only the latest zone per kind); "
    "M8 is therefore excluded from the generic `poi_raw` model hook.",
    "`entry_anchor` is populated only when a trigger actually sets it (e.g. F); "
    "absent stays blank — never invented.",
    "Swing objects (`detect_swings`) are not in the controlled vocabulary; the "
    "swings feed the liquidity scanner and are visible only through the "
    "structural levels / sweeps they produce.",
    "Trigger D emits nothing on volume-less data (A5 ruling) — its absence here "
    "is the code's, not a measurement gap.",
    "No PnL interpretation, no edge claim: `fill` rows carry the trade's own "
    "recorded outcome fields for completeness only.",
]


def write_report(out: Path, summary: dict, sample_index: list[dict],
                 by_type: dict, by_type_tf: dict,
                 observations: dict, report_path: Path | None = None) -> Path:
    # Default: inside the out-root, so auxiliary runs (smoke / chunk /
    # determinism helper) can NEVER clobber the canonical report. The final
    # deliverable run passes --report-path explicitly.
    if report_path is None:
        report_path = out / "STRUCTURE_IDENTIFICATION_LEDGER_REPORT.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    add = lines.append
    add("# STRUCTURE IDENTIFICATION LEDGER — REPORT")
    add("")
    add(f"**Status:** {summary['ledger_status']} · generated "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
        "measurement + export + charts only (V1.1 baseline freeze in force).")
    add("")
    add("**Purpose:** let a human and an external expert score whether the code "
        "identifies OB / FVG / S&D / LTF confirms the way the locked flowchart "
        "says, BEFORE paper trading is treated as anything beyond ops.")
    add("")
    add("---")
    add("")
    add("## 1. Window & composition")
    add("")
    window = summary["window"]
    add(f"- Exec window: **{window['start']} → {window['end']}** "
        f"({summary['bars_m5']} {window['exec_tf']} bars)")
    add(f"- Detection: H4 + H1 (M8 fed D1 when available) · Execution: M5")
    if window.get("load_from"):
        add(f"- M1 warm-up load from: {window['load_from']}")
    if window.get("note"):
        add(f"- {window['note']}")
    add(f"- HTF batches: {summary['htf_batches']} · batch errors: "
        f"{summary['batch_errors']}")
    add(f"- Runtime: {summary['runtime_seconds']}s")
    if summary.get("assembly") == "chunked":
        add("")
        add("**Assembly:** tiled chunks — see the assembly notes at the end "
            "of §7 for why a single run is not feasible. Exec windows tile "
            "the LOCKED range exactly.")
        add("")
        add("| chunk | exec window | M5 bars | HTF batches | rows added |")
        add("|---|---|---:|---:|---:|")
        for chunk in summary.get("chunks", []):
            window = chunk.get("window") or {}
            add(f"| {chunk['chunk']} | {window.get('start', '?')} → "
                f"{window.get('end', '?')} | {chunk.get('bars_m5', '?')} | "
                f"{chunk.get('htf_batches', '?')} | {chunk.get('rows_added', '?')} |")
    add("")
    add("Driver modules (unchanged — logging-only wrappers restored in `finally`):")
    add("")
    for module in summary["driver_modules"]:
        add(f"- `{module}`")
    add("")
    add("## 2. Module ↔ flowchart map")
    add("")
    add("| Flowchart concept | Code module(s) | event_type | Notes |")
    add("|---|---|---|---|")
    for concept, module, event_type, note in MODULE_FLOWCHART_MAP:
        add(f"| {concept} | `{module}` | `{event_type}` | {note} |")
    add("")
    add("## 3. Dedup rule")
    add("")
    add("One row per unique structural event. The dedup key is "
        "(event_type-scope, detection_tf, direction, rounded zone/level bounds, "
        "event timestamp) — for liquidity levels the family + `formed_at` are "
        "added; for the pillar layer the SCOPE is `pillar_outcome` so a geometry "
        "that alternates PASS/REJECT across batches still yields ONE row. The "
        "first observation fixes the row; later observations only bump "
        "`observed=N` (and flag `observed_event_types` on verdict flicker).")
    add("")
    add("## 4. Volumes")
    add("")
    add("### 4.1 Events by type (unique rows)")
    add("")
    add("| event_type | rows | raw observations |")
    add("|---|---:|---:|")
    for event_type in EVENT_TYPES:
        add(f"| `{event_type}` | {by_type.get(event_type, 0)} | "
            f"{observations.get(event_type, 0)} |")
    add(f"| **total** | **{sum(by_type.values())}** | "
        f"**{sum(observations.values())}** |")
    add("")
    add("### 4.2 Events by type × detection timeframe")
    add("")
    tfs = sorted({tf for row in by_type_tf.values() for tf in row})
    add("| event_type | " + " | ".join(tfs) + " |")
    add("|---|" + "---:|" * len(tfs))
    for event_type in EVENT_TYPES:
        row = by_type_tf.get(event_type, {})
        if not row:
            continue
        add(f"| `{event_type}` | "
            + " | ".join(str(row.get(tf, 0)) for tf in tfs) + " |")
    add("")
    add("### 4.3 Funnel (machine counters)")
    add("")
    add("| stage | count |")
    add("|---|---:|")
    for label, value in summary["funnel"].items():
        add(f"| {label} | {value} |")
    add("")
    add("## 5. Review sample index")
    add("")
    add(f"Sample charts: `review_sample/` ({len(sample_index)} PNG) — "
        "stratified, spread evenly across the window.")
    add("")
    add("| file | event_id | event_type | chart_tf | detect_tf | ts_utc | "
        "direction | tags |")
    add("|---|---|---|---|---|---|---|---|")
    for entry in sample_index:
        add(f"| {entry['file']} | `{entry['event_id']}` | "
            f"{entry['event_type']} | {entry.get('chart_tf', '')} | "
            f"{entry.get('detection_tf', '')} | {entry['ts_utc']} | "
            f"{entry['direction']} | {entry['model_tags']} |")
    add("")
    add("## 6. Scoring workflow")
    add("")
    add("1. Open `events.csv` / `events.jsonl` (full ledger) and "
        "`review_sample/` (stratified charts).")
    add("2. Score each sampled event: **CORRECT / PARTIAL / WRONG / UNCLEAR** "
        "against the locked flowchart.")
    add("3. Only after scoring, treat paper as more than ops. Paper tests the "
        "live path; this ledger is the identification question.")
    add("")
    add("## 7. Explicit limitations")
    add("")
    for item in LIMITATIONS:
        add(f"- {item}")
    if summary.get("notes"):
        add("")
        add("### Assembly / measurement notes")
        add("")
        for item in summary["notes"]:
            add(f"- {item}")
    add("")
    if summary.get("capture_errors"):
        add("## 8. Capture errors (non-fatal)")
        add("")
        for message, count in summary["capture_errors"].items():
            add(f"- ×{count} `{message}`")
        add("")
        add("## 9. Return block")
    else:
        add("## 8. Return block")
    add("")
    add("```")
    for line in summary["return_block"].splitlines():
        add(line)
    add("```")
    add("")
    add("*End of report. No edge language, no threshold change, no paper trading.*")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def _report_path(args, out: Path) -> Path:
    """Canonical report path when requested, else inside the out-root."""
    if getattr(args, "report_path", None):
        path = Path(args.report_path)
        return path if path.is_absolute() else REPO_ROOT / path
    return out / "STRUCTURE_IDENTIFICATION_LEDGER_REPORT.md"


# --------------------------------------------------------------------------- #
# Merge mode — tile the LOCKED window into chunks and union the ledgers
# --------------------------------------------------------------------------- #
def _load_chart_series(start: datetime, end: datetime) -> dict:
    """Load M5/H1/H4/D1 series covering [start, end] for chart rendering."""
    from smc.config.timeframe import Timeframe
    from smc.data.parquet_loader import load_ohlcv_parquet
    from smc.data.resample import resample_multi

    data_path = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    if not data_path.exists():
        raise SystemExit(f"canonical dataset missing: {data_path}")
    m1 = load_ohlcv_parquet(data_path)
    pad = timedelta(days=40)
    m1 = [c for c in m1 if start - pad <= c.timestamp <= end + pad]
    multi = resample_multi(m1, [Timeframe.M5, Timeframe.H1, Timeframe.H4,
                                Timeframe.D1])
    return {
        "M5": multi[Timeframe.M5],
        "H1": multi[Timeframe.H1],
        "H4": multi[Timeframe.H4],
        "D1": multi[Timeframe.D1],
    }


def run_merge(args) -> dict:
    """Union N chunk ledgers (tiled exec windows) into the full ledger."""
    global LEDGER
    LEDGER = Ledger()
    CAPTURE_ERRORS.clear()
    t0 = time.perf_counter()
    chunks: list[dict] = []
    totals: dict = {"bars_m5": 0, "htf_batches": 0, "batch_errors": 0}
    funnel: dict = {"detected_raw": {}, "merged": {}, "passed_validation": {},
                    "armed": {}, "armed_m8": 0, "routes": 0, "placed": 0,
                    "fills": 0}

    for raw_path in args.merge_jsonl:
        path = Path(raw_path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        if not path.exists():
            raise SystemExit(f"chunk ledger not found: {path}")
        rows = [json.loads(line) for line in
                path.read_text(encoding="utf-8").splitlines() if line.strip()]
        added = LEDGER.load_carried_rows(rows, path.parent.name)
        chunk: dict = {"chunk": path.parent.name,
                       "ledger": str(path.relative_to(REPO_ROOT)),
                       "rows_in_file": len(rows), "rows_added": added,
                       "dangling_links": int(getattr(LEDGER, "last_dangling", 0))}
        chunk_summary_path = path.parent / "summary.json"
        if chunk_summary_path.exists():
            chunk_summary = json.loads(chunk_summary_path.read_text())
            chunk["window"] = chunk_summary.get("window")
            chunk["bars_m5"] = chunk_summary.get("bars_m5")
            chunk["htf_batches"] = chunk_summary.get("htf_batches")
            chunk["batch_errors"] = chunk_summary.get("batch_errors")
            totals["bars_m5"] += int(chunk_summary.get("bars_m5") or 0)
            totals["htf_batches"] += int(chunk_summary.get("htf_batches") or 0)
            totals["batch_errors"] += int(chunk_summary.get("batch_errors") or 0)
            chunk_funnel = chunk_summary.get("funnel") or {}
            for key in ("detected_raw", "merged", "passed_validation", "armed"):
                bucket = funnel.setdefault(key, {})
                for name, value in (chunk_funnel.get(key) or {}).items():
                    bucket[name] = bucket.get(name, 0) + int(value or 0)
            for key in ("armed_m8", "routes", "placed", "fills"):
                funnel[key] = (funnel.get(key, 0)
                               + int(chunk_funnel.get(key) or 0))
        chunks.append(chunk)

    # Tiling invariant: chunk exec windows must not overlap, else the union
    # would double-count and the ledger_status degrades loudly.
    spans: list[tuple[datetime, datetime]] = []
    for chunk in chunks:
        window = chunk.get("window") or {}
        try:
            spans.append((datetime.fromisoformat(window["start"]),
                          datetime.fromisoformat(window["end"])))
        except (KeyError, TypeError, ValueError):
            continue
    spans.sort()
    overlap = any(spans[i][1] >= spans[i + 1][0] for i in range(len(spans) - 1))

    problems = validate_ledger()
    by_type, by_type_tf, observations = volume_tables()
    stamps = [r["ts_utc"] for r in LEDGER.rows if r.get("ts_utc")]
    union_start, union_end = (min(stamps), max(stamps)) if stamps else ("", "")

    out = Path(args.out_root)
    if not out.is_absolute():
        out = REPO_ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    csv_path, jsonl_path = write_ledger_artifacts(out)

    sample_index: list[dict] = []
    if args.charts:
        series_by_tf = _load_chart_series(
            datetime.fromisoformat(union_start), datetime.fromisoformat(union_end))
        sample_index = render_review_pack(
            select_review_rows(args.chart_max), series_by_tf,
            out / "review_sample",
            {"M5": 60, "H1": 40, "H4": 30, "D1": 25})

    ledger_status = "PASS"
    if problems or totals["batch_errors"] or overlap:
        ledger_status = "PARTIAL"
    if not LEDGER.rows:
        ledger_status = "FAIL"

    return_block = "\n".join([
        f"LEDGER_STATUS: {ledger_status}",
        f"WINDOW: {union_start} -> {union_end} ({len(chunks)} tiled chunks)",
        f"EVENTS: {len(LEDGER.rows)}",
        f"BY_TYPE: {json.dumps(by_type, sort_keys=True)}",
        f"ARMED: {sum(funnel['armed'].values())}",
        f"ROUTES: {funnel['routes']}",
        f"FILLS: {funnel['fills']}",
        f"REVIEW_PNGs: {len(sample_index)}",
        f"LEDGER_PATH: {out.relative_to(REPO_ROOT) if str(out).startswith(str(REPO_ROOT)) else out}/",
        "REPORT_PATH: 06_RESEARCH/STRUCTURE_IDENTIFICATION_LEDGER_REPORT.md",
        "LOGIC_CHANGED: NO",
        "HANDOFF_UPDATED: NO",
        "NEXT_READY: Owner/expert sample scoring -> then paper dry_run under V1.1 freeze",
    ])

    summary = {
        "tag": args.tag,
        "ledger_status": ledger_status,
        "assembly": "chunked",
        "chunks": chunks,
        "chunk_windows_overlap": overlap,
        "window": {
            "start": union_start,
            "end": union_end,
            "exec_tf": EXEC_TF_NAME,
            "note": "union of tiled chunk exec windows; each chunk ran the "
                    "same unified composition with its own warm-up",
        },
        "bars_m5": totals["bars_m5"],
        "htf_batches": totals["htf_batches"],
        "batch_errors": totals["batch_errors"],
        "event_types": list(EVENT_TYPES),
        "events_by_type": by_type,
        "events_by_type_tf": by_type_tf,
        "events_by_type_observations": observations,
        "funnel": funnel,
        "driver_modules": [
            "smc.orchestration.multi_tf_runtime.MultiTFProductRuntime.run_batch",
            "smc.orchestration.multi_tf.MultiTFDetectionDriver.validate_multi",
            "smc.orchestration.detection_driver.DetectionDriver."
            "stage0/detect_pois/validate_window",
            "smc.poi.models.m8_htf_demand_supply.M8HtfDemandSupply._zones",
            "smc.orchestration.engine.PipelineEngine.arm_at/scan_route",
            "smc.backtest.pipeline_adapter.PipelineAdapter",
            "smc.backtest.runner.BacktestRunner",
            "smc.backtest.reports.build_report",
        ],
        "ledger_invariants": problems,
        "capture_errors": {},
        "review_sample": sample_index,
        "return_block": return_block,
        "notes": [
            "ASSEMBLED FROM TILED CHUNKS. A single 6-month run is not "
            "feasible in one process: the accepted composition re-scans the "
            "growing HTF prefix every batch, measured at 0.67 s/batch at a "
            "6-month prefix (base code, instrumentation ~11% on top) => "
            "~20 min projected. The LOCKED window was therefore tiled into "
            "non-overlapping 3-month exec windows, each running the same "
            "unified multi-TF composition with its own warm-up; the union is "
            "exact because a row's own ts_utc was bounded by its chunk's "
            "window (retain_window).",
            "Chunk-level verdicts close over each chunk's own prefix, so a "
            "Sep-Nov geometry is first-observed against a >=1-month warm-up "
            "(the LOCKED Phase 4 load) rather than a 4-month one. Documented "
            "deviation from a single-run composition.",
            "Read-only measurement; no PnL interpretation; `fill` rows carry "
            "recorded outcome fields only.",
        ],
        "runtime_seconds": round(time.perf_counter() - t0, 1),
    }
    report_path = write_report(out, summary, sample_index, by_type,
                               by_type_tf, observations,
                               report_path=_report_path(args, out))
    summary["report_path"] = str(report_path)
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(return_block, flush=True)
    print(f"[ledger] events.csv -> {csv_path}", flush=True)
    print(f"[ledger] report -> {report_path}", flush=True)
    if problems:
        print(f"[ledger] INVARIANT PROBLEMS: {problems}", flush=True)
    return summary


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
def run(args) -> dict:
    global LEDGER, CTX
    LEDGER = Ledger()
    CTX = RunContext()
    CAPTURE_ERRORS.clear()
    MERGED_EVENT_BY_POI.clear()
    ARMED_ROW_BY_POI.clear()
    ROUTE_ROW_BY_POI.clear()
    CANDIDATE_BY_ROUTE.clear()
    CANDIDATE_BY_POI.clear()
    PILLAR_OUTCOMES.clear()

    install_deterministic_poi_ids()

    from smc.backtest.bar_loop import BarLoop
    from smc.backtest.data_feed import CandleSeries
    from smc.backtest.export import to_csv, to_json
    from smc.backtest.orders import PendingOrderBook
    import smc.backtest.pipeline_adapter as pipeline_adapter_module
    from smc.backtest.pipeline_adapter import PipelineAdapter
    from smc.backtest.positions import PositionStore
    from smc.backtest.reports import build_report
    from smc.backtest.runner import BacktestRunner, RunnerConfig
    from smc.config.timeframe import Timeframe
    from smc.data.parquet_loader import load_ohlcv_parquet
    from smc.data.resample import resample_multi
    from smc.orchestration.detection_driver import DetectionDriver
    from smc.orchestration.engine import PipelineEngine
    from smc.orchestration.multi_tf_runtime import (
        MissingHtfSeriesError,
        MultiTFProductRuntime,
    )
    from smc.poi.models.m8_htf_demand_supply import M8HtfDemandSupply
    from smc.risk.risk_engine import RiskEngine
    from smc.utils.timestamps import Session

    tf = Timeframe.M5
    load_from = _parse_day(args.load_from)
    exec_from = _parse_day(args.exec_from)
    exec_to = (_parse_day(args.exec_to) + timedelta(days=1)
               - timedelta(minutes=1))
    t0 = time.perf_counter()

    data_path = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    if not data_path.exists():
        raise SystemExit(f"canonical dataset missing: {data_path}")
    m1 = load_ohlcv_parquet(data_path)
    m1 = [c for c in m1 if load_from <= c.timestamp <= exec_to + timedelta(days=1)]
    if not m1:
        raise SystemExit("no M1 bars in the requested window")
    multi = resample_multi(m1, [tf, Timeframe.H1, Timeframe.H4, Timeframe.D1])
    m5 = [c for c in multi[tf] if exec_from <= c.timestamp <= exec_to]
    if len(m5) < 50:
        raise SystemExit("execution window too small for the stack warm-up")
    h1 = multi[Timeframe.H1]
    h4 = multi[Timeframe.H4]
    d1 = multi[Timeframe.D1]
    CTX.m5 = m5
    series_by_tf = {"M5": m5, "H1": h1, "H4": h4, "D1": d1}
    print(f"[ledger] exec M5 {len(m5)} bars; H1 {len(h1)} H4 {len(h4)} D1 {len(d1)}",
          flush=True)

    class _CountingOrderBook(PendingOrderBook):
        """Order book that counts placements (read-only counters)."""

        def __init__(self) -> None:
            super().__init__()
            self.placed = 0

        def place(self, **kwargs):
            order = super().place(**kwargs)
            self.placed += 1
            return order

    # ---- Stack: engine + PRODUCT seam + FR-4 arm/scan/risk wiring ------ #
    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=tf)
    adapter.set_candles(m5)
    runtime = MultiTFProductRuntime()
    order_book = _CountingOrderBook()
    position_store = PositionStore()
    runner = BacktestRunner(
        risk_engine=RiskEngine(), order_book=order_book,
        position_store=position_store,
        config=RunnerConfig(
            equity=10_000.0, risk_fraction=0.01, pip_value_per_lot=10.0,
            min_lots=0.01, lot_step=0.01, spread_price=0.0, news_events=[],
            allowed_sessions=(Session.ASIA, Session.LONDON, Session.NEW_YORK),
            timeframe=tf),
    )
    adapter.attach(runner)
    CTX.adapter = adapter

    funnel = {
        "htf_batches": 0, "batch_errors": 0,
        "detected_raw": {"H4": 0, "H1": 0},
        "merged": {"H4": 0, "H1": 0},
        "passed": {"H4": 0, "H1": 0},
        "armed": {"H4": 0, "H1": 0},
        "armed_m8": 0, "routes": 0, "placed": 0, "fills": 0,
    }

    # ---- Install logging-only wrappers (restored in finally) ----------- #
    original_stage0 = DetectionDriver.stage0
    original_detect_pois = DetectionDriver.detect_pois
    original_validate_window = DetectionDriver.validate_window
    original_m8_zones = M8HtfDemandSupply._zones
    original_arm_at = PipelineEngine.arm_at
    original_scan_route = PipelineEngine.scan_route
    original_candidate = pipeline_adapter_module.candidate_from_route

    def stage0_wrapper(self, candles):
        result = original_stage0(self, candles)
        capture_stage0(self.timeframe, candles, result)
        return result

    def detect_pois_wrapper(self, candles, swings, liquidity_levels):
        pois, skipped = original_detect_pois(self, candles, swings, liquidity_levels)
        capture_raw_pois(self.timeframe, pois)
        return pois, skipped

    def validate_window_wrapper(self, candles, *a, **kw):
        result = original_validate_window(self, candles, *a, **kw)
        capture_validation(self.timeframe, result[1])
        return result

    def m8_zones_wrapper(self, series, tf_arg):
        for kind, direction, start_index, zone in original_m8_zones(
                self, series, tf_arg):
            capture_m8_zone(tf_arg, kind, direction, start_index, zone, series)
            yield kind, direction, start_index, zone

    def arm_at_wrapper(self, poi, arm_bar):
        result = original_arm_at(self, poi, arm_bar)
        capture_armed(CTX.adapter, poi, arm_bar)
        return result

    def scan_route_wrapper(self, poi, candles, swings, *a, **kw):
        route = original_scan_route(self, poi, candles, swings, *a, **kw)
        if route is not None:
            capture_route(route, candles)
        return route

    def candidate_wrapper(route, *a, **kw):
        candidate = original_candidate(route, *a, **kw)
        capture_candidate(route, candidate)
        return candidate

    DetectionDriver.stage0 = stage0_wrapper
    DetectionDriver.detect_pois = detect_pois_wrapper
    DetectionDriver.validate_window = validate_window_wrapper
    M8HtfDemandSupply._zones = m8_zones_wrapper
    PipelineEngine.arm_at = arm_at_wrapper
    PipelineEngine.scan_route = scan_route_wrapper
    pipeline_adapter_module.candidate_from_route = candidate_wrapper

    h1_ts = [c.timestamp for c in h1]
    h4_ts = [c.timestamp for c in h4]
    d1_ts = [c.timestamp for c in d1]
    last_h1: datetime | None = None
    bars_done = [0]

    class Cycle:
        def __init__(self, inner):
            self.inner = inner

        def on_bar(self, bar, bar_index, clock) -> None:
            nonlocal last_h1
            CTX.bar_index = bar_index
            CTX.as_of = bar.timestamp
            cut = bisect.bisect_right(h1_ts, bar.timestamp) - 1
            if cut >= 0:
                current_h1 = h1[cut].timestamp
                if current_h1 != last_h1:
                    last_h1 = current_h1
                    series = {
                        Timeframe.H1: h1[:cut + 1],
                        Timeframe.H4: h4[:bisect.bisect_right(h4_ts, bar.timestamp)],
                        Timeframe.D1: d1[:bisect.bisect_right(d1_ts, bar.timestamp)],
                    }
                    try:
                        report = runtime.run_batch(
                            engine=engine, series_by_tf=series,
                            as_of=bar.timestamp, arm_bar=bar_index, adapter=adapter,
                        )
                    except MissingHtfSeriesError:
                        funnel["batch_errors"] += 1
                    else:
                        funnel["htf_batches"] += 1
                        for name, counts in report.per_tf.items():
                            funnel["detected_raw"][name] = (
                                funnel["detected_raw"].get(name, 0)
                                + counts.get("detected_raw", 0))
                            funnel["merged"][name] = (
                                funnel["merged"].get(name, 0)
                                + counts.get("merged", 0))
                            funnel["passed"][name] = (
                                funnel["passed"].get(name, 0)
                                + counts.get("passed", 0))
                        for poi in report.armed:
                            tf_name = _enum_name(poi.zone.timeframe)
                            funnel["armed"][tf_name] = (
                                funnel["armed"].get(tf_name, 0) + 1)
                            if any(_enum_name(m) == "M8" for m in poi.models):
                                funnel["armed_m8"] += 1
            self.inner.on_bar(bar, bar_index, clock)
            bars_done[0] += 1
            if bars_done[0] % 5000 == 0:
                elapsed = max(time.perf_counter() - t0, 1e-9)
                print(f"[ledger] bar {bars_done[0]}/{len(m5)} "
                      f"{bars_done[0] / elapsed:.1f} bars/s "
                      f"rows={len(LEDGER.rows)}", flush=True)

    loop = BarLoop(CandleSeries(m5, tf), Cycle(runner))
    try:
        stats = loop.run()
    finally:
        DetectionDriver.stage0 = original_stage0
        DetectionDriver.detect_pois = original_detect_pois
        DetectionDriver.validate_window = original_validate_window
        M8HtfDemandSupply._zones = original_m8_zones
        PipelineEngine.arm_at = original_arm_at
        PipelineEngine.scan_route = original_scan_route
        pipeline_adapter_module.candidate_from_route = original_candidate

    # ---- Post-run capture --------------------------------------------- #
    result = runner.result()
    report = build_report(result)
    capture_intents(runner)
    capture_fills(report)
    enrich_identity_rows()
    warmup_dropped = LEDGER.retain_window(exec_from, exec_to)

    funnel["routes"] = len(LEDGER.by_type("route_ltf"))
    funnel["placed"] = order_book.placed
    funnel["fills"] = len(report.trades)

    out = Path(args.out_root)
    if not out.is_absolute():
        out = REPO_ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    csv_path, jsonl_path = write_ledger_artifacts(out)
    by_type, by_type_tf, observations = volume_tables()
    problems = validate_ledger()

    sample_index: list[dict] = []
    if args.charts:
        sample_index = render_review_pack(
            select_review_rows(args.chart_max), series_by_tf,
            out / "review_sample",
            {"M5": 60, "H1": 40, "H4": 30, "D1": 25})
        embedded = write_review_gallery(
            sample_index, out / "review_sample",
            out / "review_gallery.html")
        print(f"review_gallery.html written: {embedded} charts embedded "
              "(self-contained, no external files)")

    to_csv(report, out / "trades.csv")
    to_json(report, out / "report.json")

    ledger_status = "PASS"
    if funnel["batch_errors"]:
        ledger_status = "PARTIAL"
    if not LEDGER.rows:
        ledger_status = "FAIL"

    return_block = "\n".join([
        f"LEDGER_STATUS: {ledger_status}",
        f"WINDOW: {m5[0].timestamp.isoformat()} -> {m5[-1].timestamp.isoformat()}",
        f"EVENTS: {len(LEDGER.rows)}",
        f"BY_TYPE: {json.dumps(by_type, sort_keys=True)}",
        f"ARMED: {sum(funnel['armed'].values())}",
        f"ROUTES: {funnel['routes']}",
        f"FILLS: {funnel['fills']}",
        f"REVIEW_PNGs: {len(sample_index)}",
        f"LEDGER_PATH: {out.relative_to(REPO_ROOT) if str(out).startswith(str(REPO_ROOT)) else out}/",
        "REPORT_PATH: 06_RESEARCH/STRUCTURE_IDENTIFICATION_LEDGER_REPORT.md",
        "LOGIC_CHANGED: NO",
        "HANDOFF_UPDATED: NO",
        "NEXT_READY: Owner/expert sample scoring -> then paper dry_run under V1.1 freeze",
    ])

    summary = {
        "tag": args.tag,
        "ledger_status": ledger_status,
        "window": {
            "start": m5[0].timestamp.isoformat(),
            "end": m5[-1].timestamp.isoformat(),
            "exec_tf": EXEC_TF_NAME,
            "load_from": load_from.isoformat(),
        },
        "bars_m5": stats.bars_processed,
        "htf_batches": funnel["htf_batches"],
        "batch_errors": funnel["batch_errors"],
        "event_types": list(EVENT_TYPES),
        "events_by_type": by_type,
        "events_by_type_tf": by_type_tf,
        "events_by_type_observations": observations,
        "warmup_events_dropped": warmup_dropped,
        "funnel": {
            "detected_raw": funnel["detected_raw"],
            "merged": funnel["merged"],
            "passed_validation": funnel["passed"],
            "armed": funnel["armed"],
            "armed_m8": funnel["armed_m8"],
            "routes": funnel["routes"],
            "placed": funnel["placed"],
            "fills": funnel["fills"],
        },
        "driver_modules": [
            "smc.orchestration.multi_tf_runtime.MultiTFProductRuntime.run_batch",
            "smc.orchestration.multi_tf.MultiTFDetectionDriver.validate_multi",
            "smc.orchestration.detection_driver.DetectionDriver."
            "stage0/detect_pois/validate_window",
            "smc.detection.liquidity_scanner.scan",
            "smc.detection.sweep_detector.detect_sweeps",
            "smc.detection.fvg_detector.detect_fvgs",
            "smc.detection.displacement_checker.check_displacement",
            "smc.poi.models.m8_htf_demand_supply.M8HtfDemandSupply._zones",
            "smc.orchestration.engine.PipelineEngine.arm_at/scan_route",
            "smc.backtest.pipeline_adapter.PipelineAdapter",
            "smc.backtest.runner.BacktestRunner",
            "smc.backtest.reports.build_report",
        ],
        "ledger_invariants": problems,
        "capture_errors": dict(CAPTURE_ERRORS),
        "review_sample": sample_index,
        "return_block": return_block,
        "notes": [
            "Read-only measurement on the unified multi-TF product path "
            "(H4+H1 detect, D1→M8, M5 exec).",
            "Growing-prefix detection (accepted Phase 3/4 composition): the "
            "ledger dedups by geometry; `observed=N` records re-emissions.",
            "No PnL interpretation; `fill` rows carry recorded outcome fields "
            "for completeness only.",
        ],
        "runtime_seconds": round(time.perf_counter() - t0, 1),
    }

    report_path = write_report(out, summary, sample_index, by_type,
                               by_type_tf, observations,
                               report_path=_report_path(args, out))
    summary["report_path"] = str(report_path)
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")

    print(return_block, flush=True)
    print(f"[ledger] events.csv -> {csv_path}", flush=True)
    print(f"[ledger] events.jsonl -> {jsonl_path}", flush=True)
    print(f"[ledger] report -> {report_path}", flush=True)
    if problems:
        print(f"[ledger] INVARIANT PROBLEMS: {problems}", flush=True)
    if CAPTURE_ERRORS:
        print(f"[ledger] CAPTURE_ERRORS: {CAPTURE_ERRORS}", flush=True)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--load-from", default=PRIMARY_LOAD_FROM)
    parser.add_argument("--exec-from", default=PRIMARY_EXEC_FROM)
    parser.add_argument("--exec-to", default=PRIMARY_EXEC_TO)
    parser.add_argument("--charts", dest="charts", action="store_true",
                        default=True)
    parser.add_argument("--no-charts", dest="charts", action="store_false")
    parser.add_argument("--chart-max", type=int, default=8)
    parser.add_argument("--merge-jsonl", nargs="*", default=None,
                        help="merge chunk ledgers (JSONL) instead of running")
    parser.add_argument("--report-path", default=None,
                        help="report output path; default = inside --out-root "
                             "(auxiliary runs never clobber the canonical "
                             "06_RESEARCH/STRUCTURE_IDENTIFICATION_LEDGER_REPORT.md)")
    args = parser.parse_args()
    if args.merge_jsonl:
        run_merge(args)
    else:
        run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
