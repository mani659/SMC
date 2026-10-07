"""AS-CODED architecture renderer (matplotlib only — no new deps).

Emits two PNGs under ``06_RESEARCH/results/architecture_audit/``:

* ``as_coded_architecture.png`` — the coded end-to-end architecture:
  data load → multi-TF detection batch (H4/H1, refreshed on new H1 close)
  → per-M5-bar execution loop (runner steps 1–7 + adapter scan/workflow +
  R7 / R9 placement path) → fills → management → reporting.
* ``as_coded_bar_loop.png`` — the exact ``BacktestRunner.on_bar`` order of
  operations as coded in ``04_SRC/smc/backtest/runner.py`` (with the R9
  step-5.5/7 position and the intent book lifetime).

Every box/arrow is sourced from code read during the audit; file paths are
annotated on the boxes so the picture can be checked against the code
without trusting the prose. Runs headless (Agg).

Usage:
    python 06_RESEARCH/scripts/render_as_coded_architecture.py
"""

from __future__ import annotations

import os
import textwrap

import matplotlib
matplotlib.use("Agg")  # headless — no display dependency

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_DIR = os.path.join(REPO_ROOT, "06_RESEARCH", "results", "architecture_audit")

# Palette (semantic, stable across both figures).
C_DATA = "#e8f0fe"      # data / IO
C_DETECT = "#e6f4ea"    # detection & POI construction
C_VALID = "#fff4e5"     # validation / state machine
C_TRIGGER = "#f3e8fd"   # triggers / routing
C_RISK = "#fde8e8"      # risk decisions (pure)
C_MUTATE = "#e0f2f1"    # stores / mutations
C_REPORT = "#f5f5f5"    # reporting
EDGE = "#37474f"


def _box(ax, x, y, w, h, title, body, color, fontsize=8.0, title_size=9.0):
    """One rounded box with a bold title and wrapped body text."""
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.008,rounding_size=0.012",
        linewidth=1.1, edgecolor=EDGE, facecolor=color, mutation_aspect=1.0,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h - 0.035, title, ha="center", va="top",
            fontsize=title_size, fontweight="bold", color="#1a237e")
    if body:
        wrapped = "\n".join(textwrap.wrap(body, width=max(18, int(w * 118))))
        ax.text(x + w / 2, y + h - 0.115, wrapped, ha="center", va="top",
                fontsize=fontsize, color="#263238")
    return patch


def _arrow(ax, p0, p1, label=None, color=EDGE, style="-|>", lw=1.2,
           rad=0.0, label_size=7.2, label_offset=(0.0, 0.012)):
    arrow = FancyArrowPatch(
        p0, p1, arrowstyle=style, mutation_scale=11, linewidth=lw,
        color=color, connectionstyle=f"arc3,rad={rad}", shrinkA=1.5, shrinkB=1.5,
    )
    ax.add_patch(arrow)
    if label:
        mx = (p0[0] + p1[0]) / 2 + label_offset[0]
        my = (p0[1] + p1[1]) / 2 + label_offset[1]
        ax.text(mx, my, label, ha="center", va="bottom", fontsize=label_size,
                color="#455a64",
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none",
                          alpha=0.85))


def render_architecture(path: str) -> None:
    fig, ax = plt.subplots(figsize=(19.5, 13.0))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.5, 0.985, "AS-CODED ARCHITECTURE — SMC BOT V1 (from live 04_SRC/smc/ code)",
            ha="center", va="top", fontsize=17, fontweight="bold", color="#0d47a1")
    ax.text(0.5, 0.958,
            "Every box cites its module; the shipped research chain (fr4_fidelity_baseline.py / "
            "r9_place_on_reentry_smoke.py) is the caller that drives this stack.",
            ha="center", va="top", fontsize=9.5, color="#37474f")

    # ---------------- Lane labels ----------------
    lane = dict(fontsize=11, fontweight="bold", color="#37474f", rotation=90,
                va="center", ha="center")
    ax.text(0.018, 0.815, "A. DATA + DETECTION CASCADE (multi-TF batch)", **lane)
    ax.text(0.018, 0.545, "B. VALIDATION → ARM (batch boundary)", **lane)
    ax.text(0.018, 0.235, "C. PER-M5-BAR EXECUTION / MANAGEMENT", **lane)

    # =============== LANE A — data + detection ===============
    y = 0.775
    h = 0.155
    _box(ax, 0.045, y, 0.115, h, "M1 source",
         "07_DATA/XAUUSD_M1.parquet → load_ohlcv_parquet()\n"
         "04_SRC/smc/data/parquet_loader.py",
         C_DATA)
    _box(ax, 0.180, y, 0.135, h, "Resample multi-TF",
         "resample_multi → M5 exec + H1/H4/D1 HTF\n"
         "04_SRC/smc/data/resample.py",
         C_DATA)
    _box(ax, 0.335, y, 0.150, h, "HTF batch cadence",
         "new H1 close detected by caller Cycle wrapper\n"
         "(bisect on h1 timestamps) — fr4_fidelity_baseline.py L207-236",
         C_DATA)
    _box(ax, 0.505, y, 0.165, h, "MultiTFDetectionDriver.validate_multi",
         "per-TF DetectionDriver for (H4, H1); one shared PipelineEngine;\n"
         "M8 htf map auto-shared from H1/H4 series · multi_tf.py L100-166",
         C_DETECT)
    _box(ax, 0.690, y, 0.150, h, "DetectionDriver.stage0",
         "detect_swings · scan liquidity (ALL_FAMILIES) · detect_sweeps ·\n"
         "detect_fvgs · atr_series · check_displacement per sweep\n"
         "detection_driver.py L109-169",
         C_DETECT)
    _box(ax, 0.858, y, 0.135, h, "M1–M8 models",
         "build_registry().all() → model.detect(); raising model is\n"
         "SKIPPED (skipped_models) · model_registry.py L70-106",
         C_DETECT)

    # =============== LANE B — validation ===============
    yb = 0.545
    hb = 0.155
    _box(ax, 0.045, yb, 0.135, hb, "Merge overlapping",
         "score_poi.merge_overlapping (same-direction, tag union)\n"
         "poi/confluence_scorer.py L82-127",
         C_VALID)
    _box(ax, 0.198, yb, 0.185, hb, "5-Pillar validation",
         "P1 zone refinement · P2 displacement (injected map; absent →\n"
         "UNAVAILABLE=reject) · P3 premium/discount · P4 freshness\n"
         "(state-based) · P5 inducement (soft) · validation_pipeline.py",
         C_VALID)
    _box(ax, 0.400, yb, 0.140, hb, "Confluence score",
         "score_poi on PASS when poi.score == 0.0\n"
         "poi/confluence_scorer.py L67-81",
         C_VALID)
    _box(ax, 0.557, yb, 0.150, hb, "ARM (batch bar)",
         "engine.arm_at → POIStateMachine.arm CREATED→FRESH;\n"
         "episode.arm_bar anchors §24 give-up · engine.py L171-190",
         C_VALID)
    _box(ax, 0.724, yb, 0.135, hb, "Caller dedup",
         "ZoneRegistry.seen(poi.zone) drops duplicates; adapter.\n"
         "note_route_context(disp, pillar_path) — fr4 L168-186",
         C_VALID)
    _box(ax, 0.876, yb, 0.118, hb, "State owner",
         "POIStateMachine per-POI dict; poi.state mirrored\n"
         "· validation/state_machine.py",
         C_MUTATE)

    # =============== LANE C — execution ===============
    yc = 0.285
    hc = 0.165
    _box(ax, 0.045, yc, 0.165, hc, "BacktestRunner.on_bar",
         "BarLoop → on_bar(bar, bar_index, clock):\n"
         "1 day reset · 2 Friday EOD · 3 news cancel · 3b ATR/spread feed\n"
         "3c §23 expiry + intent expiry · 4 exits · 5 fills · 6 entries\n"
         "· 7 intent re-entry places · I4 prune · runner.py L239-306",
         C_TRIGGER)
    _box(ax, 0.228, yc, 0.165, hc, "PipelineAdapter.generate_candidates",
         "per tracked POI: scan_route (cursor, to_bar=now, no lookahead)\n"
         "→ workflow one-shot per POI; §5 feed AFTER scan;\n"
         "VIOLATED → cancel_pending_for_poi · adapter L145-260",
         C_TRIGGER)
    _box(ax, 0.411, yc, 0.155, hc, "TriggerRouter.scan",
         "matrix-eligible A–F evaluated per bar; first fire wins;\n"
         "same-bar tie: grade then earlier letter · trigger_router.py",
         C_TRIGGER)
    _box(ax, 0.584, yc, 0.150, hc, "candidate_from_route",
         "signal → CandidateEntry (limit = FR-3.1 zone_anchored_entry by\n"
         "trigger; SL stop_reference; TP 4×ATR) + zone/detection_tf/is_m8\n"
         "· pipeline_bridge.py",
         C_TRIGGER)
    _box(ax, 0.752, yc, 0.150, hc, "Risk gate (pure)",
         "RiskEngine.evaluate_entry: news→session→breaker→same-level→\n"
         "sweep→spread→clamp+sized_lots · risk/risk_engine.py L196-258",
         C_RISK)
    _box(ax, 0.920, yc, 0.074, hc, "Verdict",
         "ENTER\nor\nHOLD\n(blocked_log)",
         C_RISK)

    yd = 0.075
    hd = 0.150
    _box(ax, 0.045, yd, 0.150, hd, "R7 place guard",
         "zone_place_allowed(market close, zone, ATR): outside\n"
         "FR-3 band → skip_place_far_from_zone · fill_regime_policy.py",
         C_RISK)
    _box(ax, 0.213, yd, 0.155, hd, "R9 IntentBook",
         "far → arm PlaceIntent (full accepted placement, R8 clock);\n"
         "re-entry (band OR limit touch) → place with REMAINING bars ·\n"
         "backtest/intents.py",
         C_MUTATE)
    _box(ax, 0.386, yd, 0.150, hd, "Place pending limit",
         "_place_accepted → PendingOrderBook.place (ticket seq,\n"
         "rest_bars R8, identity/context maps) · orders.py",
         C_MUTATE)
    _box(ax, 0.554, yd, 0.150, hd, "Fill model",
         "limit_filled + fill_price on bar range; on fill →\n"
         "PositionStore.open + risk.on_trade_opened; SL-first same-bar\n"
         "· fill_model.py / positions.py",
         C_MUTATE)
    _box(ax, 0.722, yd, 0.150, hd, "Exit management",
         "evaluate_exit: FVG invalidation (closed close) then PureRunner\n"
         "BE MOVE_SL; physical SL/TP via PositionStore.apply_bar;\n"
         "Friday EOD closes all",
         C_RISK)
    _box(ax, 0.890, yd, 0.104, hd, "Reporting",
         "_record_close → risk latches;\n"
         "runner.result() →\n"
         "reports.build_report →\n"
         "export.to_csv/json",
         C_REPORT)

    # ---------------- Arrows ----------------
    # Lane A internal
    _arrow(ax, (0.160, y + h / 2), (0.180, y + h / 2))
    _arrow(ax, (0.315, y + h / 2), (0.335, y + h / 2))
    _arrow(ax, (0.485, y + h / 2), (0.505, y + h / 2))
    _arrow(ax, (0.670, y + h / 2), (0.690, y + h / 2))
    _arrow(ax, (0.840, y + h / 2), (0.858, y + h / 2))
    # A → B (models feed validation)
    _arrow(ax, (0.60, y), (0.24, yb + hb), "detected POIs (pre-merge)")
    # Lane B internal
    _arrow(ax, (0.180, yb + hb / 2), (0.198, yb + hb / 2))
    _arrow(ax, (0.383, yb + hb / 2), (0.400, yb + hb / 2))
    _arrow(ax, (0.540, yb + hb / 2), (0.557, yb + hb / 2))
    _arrow(ax, (0.707, yb + hb / 2), (0.724, yb + hb / 2))
    _arrow(ax, (0.859, yb + hb / 2), (0.876, yb + hb / 2), style="<|-|>")
    # B → C (armed POIs consumed by adapter scans)
    _arrow(ax, (0.30, yb), (0.30, yc + hc), "armed FRESH POIs (tracked_pois)")
    # Lane C internal
    _arrow(ax, (0.210, yc + hc / 2), (0.228, yc + hc / 2))
    _arrow(ax, (0.393, yc + hc / 2), (0.411, yc + hc / 2))
    _arrow(ax, (0.566, yc + hc / 2), (0.584, yc + hc / 2))
    _arrow(ax, (0.734, yc + hc / 2), (0.752, yc + hc / 2))
    _arrow(ax, (0.902, yc + hc / 2), (0.920, yc + hc / 2))
    _arrow(ax, (0.957, yc), (0.957, yd + hd), "ENTER")
    _arrow(ax, (0.12, yc), (0.12, yd + hd), "no-place", rad=-0.25)
    # Lane D internal
    _arrow(ax, (0.195, yd + hd / 2), (0.213, yd + hd / 2), "far")
    _arrow(ax, (0.368, yd + hd / 2), (0.386, yd + hd / 2), "re-entry")
    _arrow(ax, (0.536, yd + hd / 2), (0.554, yd + hd / 2))
    _arrow(ax, (0.704, yd + hd / 2), (0.722, yd + hd / 2))
    _arrow(ax, (0.872, yd + hd / 2), (0.890, yd + hd / 2))

    # Feedback loops (as coded)
    _arrow(ax, (0.94, yd), (0.99, yd), style="-", lw=1.0)
    ax.text(0.968, yd + 0.03, "closed\nP/L →\nequity", fontsize=7.0,
            ha="center", color="#455a64")

    ax.text(0.5, 0.012,
            "Dashed reading: lanes A→B run ONLY on a new H1 close (batch); lane C runs on EVERY closed M5 bar. "
            "R7/R9 live inside runner._process_entries / _place_due_intents (runner.py L445-590).",
            ha="center", va="bottom", fontsize=9, color="#37474f")

    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def render_bar_loop(path: str) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 15.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.5, 0.985, "AS-CODED BAR LOOP — BacktestRunner.on_bar (runner.py L239-306)",
            ha="center", va="top", fontsize=14, fontweight="bold", color="#0d47a1")
    ax.text(0.5, 0.958,
            "Exact order of operations as coded, top → bottom, one closed M5 bar per call.",
            ha="center", va="top", fontsize=9, color="#37474f")

    steps = [
        ("0. clock", "BarClock injected by BarLoop; no wall clock anywhere in backtest core.", C_DATA),
        ("1. day reset", "evaluate_friday_close is step 2; _maybe_reset_day on UTC date change → risk.reset_day().", C_MUTATE),
        ("2. Friday EOD", "risk.evaluate_friday_close(now) → close EVERYTHING at bar close, cancel all pendings, intents.drop_all(...friday). RETURN.", C_RISK),
        ("3. §11 news cancel", "risk.hard_cancel_pending(now, news_events) → cancel all pendings + intents.drop_all(...news). (news_events=[] in shipped runs — dormant.)", C_RISK),
        ("3b. feed ATR + spread", "adapter.current_atr(bar_index) → set_atr (honest prefix, no lookahead); set_spread_price(config.spread_price).", C_DATA),
        ("3c. §23 expiry", "orders.expired_by_section23(bar, timeframe) + expired_by_give_up(bar): per-order rest_bars (R8) else §23 default; adapter.notify_order_expired → POI TESTED.", C_MUTATE),
        ("3c-i. intent expiry", "intents.expire_due(bar_index): ARMED intent with bar >= expire_bar → EXPIRED (intent_expired_no_reentry) BEFORE any re-entry.", C_MUTATE),
        ("4. exits", "per open position: risk.evaluate_exit(FVG invalidation on closed close, then PureRunner BE) → EXIT via positions.close or MOVE_SL (improve check, then on_be_applied latch).", C_RISK),
        ("5. fills", "_apply_fills: orders.active() in placement order → limit_filled/fill_price → PositionStore.open; route/sweep/FVG context moves ticket→ticket; risk.on_trade_opened().", C_MUTATE),
        ("5b. physical closes", "_apply_physical_closes: PositionStore.apply_bar (SL/TP on range, SL first) → _record_close.", C_MUTATE),
        ("6. entries", "adapter.generate_candidates(bar, i, now) [scan_route → workflow → submit_entry] then _process_entries: risk.evaluate_entry → R7 guard → arm intent (R9) OR _place_accepted (order placed, workflow consumed). Blocked → blocked_log only, one-shot intact.", C_TRIGGER),
        ("7. intent re-entry places", "_place_due_intents: AFTER entries (same-bar re-proposal supersedes intent) and AFTER fills (bar-B place cannot fill on B); remaining >= 3 required.", C_TRIGGER),
        ("7b. prune", "adapter.prune_terminal_pois(retain = order/position poi_ids, bar_index) — I4 bookkeeping release; workflow-live + first-touch-window POIs retained.", C_MUTATE),
        ("8. close bookkeeping", "_record_close: risk.record_result / record_sl_close / record_failed_sweep (only when sweep_level present), equity += pnl × pip_value, route id retained for reporting.", C_REPORT),
    ]
    n = len(steps)
    top = 0.935
    gap = 0.0215
    box_h = 0.050
    for i, (title, body, color) in enumerate(steps):
        y = top - i * (box_h + gap) - box_h
        _box(ax, 0.06, y, 0.88, box_h, title, body, color,
             fontsize=8.2, title_size=9.2)
        if i < n - 1:
            _arrow(ax, (0.50, y), (0.50, y - gap), lw=1.3)
    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    arch = os.path.join(OUT_DIR, "as_coded_architecture.png")
    loop = os.path.join(OUT_DIR, "as_coded_bar_loop.png")
    render_architecture(arch)
    render_bar_loop(loop)
    print("wrote", arch)
    print("wrote", loop)


if __name__ == "__main__":
    main()
