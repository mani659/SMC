# DUMB FLOWCHART V1 — IMPLEMENTATION NOTE

**Banner: DUMB IMPLEMENTATION — DIAGNOSTIC — NOT EDGE.**

Authority: Architect 2026-10-21 (design lock ACCEPTED; this is the separate
implementation leg the lock required). Design: `06_RESEARCH/DUMB_FLOWCHART_V1_DESIGN.md`.
Baseline: `00_LOCKED/BASELINE_COMPLEX_V1_1_COMPARISON_POINT.md` (COMPLEX_V1_1 @
`b5e8c53` + the W1–W4 frozen books) — unchanged by this leg.

**Nothing was promoted.** DUMB is a parallel measurement mode; no product flag
was added, no runner of COMPLEX was touched, `locked_constants.py` diff is
**EMPTY**, and no edge claim is made or supported anywhere in this note.

---

## 1. What was built (and where)

| module | role |
|---|---|
| `04_SRC/smc/dumb/__init__.py` | package surface; DUMB-owned constants + pure rules re-exports |
| `04_SRC/smc/dumb/constants.py` | **All DUMB constants live here, DUMB-owned:** `DUMB_CONFIRM_MAX_BARS = 12` · `DUMB_SL_BUFFER_ATR = 0.10` · `DUMB_TP_R_MULTIPLE = 2.0` · `DUMB_ATR_PERIOD = 14` (`locked_constants.py` untouched; a test asserts the names are absent there) |
| `04_SRC/smc/dumb/rules.py` | pure functions: `is_sweep` (R2), `is_confirm` (R3), `is_expired` (R3), `compute_sl_tp` (R5+R6) |
| `04_SRC/smc/dumb/types.py` | `DumbTrade` record (per-trade decision trail) |
| `04_SRC/smc/dumb/runner.py` | the bar loop: honest-prefix M8 zone feed + sweep/confirm/entry state machine + fill-model exits + counters |
| `04_SRC/tests/test_dumb_flowchart.py` | **19 tests**: R2 boundary cases (strict inequalities, both directions), R3 mid-cross + inclusive bar-12 expiry, R4 outside-zone rejection, R5/R6 arithmetic (2R exact), integration single-trade bracket assertion, same-bar SL-wins, expiry→re-arm, and the isolation battery |
| `06_RESEARCH/scripts/dumb_flowchart_v1_capture.py` | measurement: parquet → resample (M5/H4/D1/W1) → runner → `trades.csv` + `summary.json` under `06_RESEARCH/results/dumb_flowchart_v1/` |
| artifacts | `results/dumb_flowchart_v1/{W3,W2}/run{1,2}/{trades.csv,run_meta.json}` · `{W}/summary.json` · `determinism.json` (gitignored) |

## 2. Seam choice (the survey's option (1): separate package, library reuse)

The COMPLEX decision spine has **zero DUMB branches** (a test scans every
`smc/**.py` outside `smc/dumb/**` for any `smc.dumb` reference — none exists).
DUMB reuses three locked products per R1 and the execution contract:

1. **Zones (R1):** `smc.poi.models.m8_htf_demand_supply.M8HtfDemandSupply`
   called as a plain library over **honest prefixes** — the prefix condition
   is the product's own `build_htf_prefixes` rule (bars with
   `timestamp <= as_of`, forming bar included, future bars never), advanced
   incrementally per detection TF (W1/D1/H4 only; the feed filters any other
   series out so non-emitting series cannot burn scans — that filter was
   added after the first capture exposed an inert-but-counted M5 series).
   Per-TF pointer growth ⇒ re-scan that TF's prefix ⇒ (family, geometry)
   emission ⇒ new zone activates at that M5 bar; an unchanged re-emission is
   a no-op; a superseded family retires the old zone. `_flag_overlaps`
   quality labelling is deliberately ignored (metadata, not a gate).
2. **Exits:** `smc.backtest.fill_model.evaluate_position_bar` — the locked
   conservative semantics (touch = level, fill price = the level,
   same-bar SL+TP → SL wins, inclusive touch). The choice documented for the
   architecture brief: DUMB runs a **thin dumb_backtest_loop** reusing `fill_model`
   for bracket evaluation rather than routing `DumbSignal`s through
   `PendingOrderBook` + the full runner chain, because the R4 entry is a
   market-at-close event, not a resting limit — there is nothing for the
   order book to hold. Entry executes at the confirm bar's close; bracket
   evaluation starts from the **next** bar (a market-at-close entry has no
   unknowable intra-bar window after it — the COMPLEX "entry+SL same bar →
   SL wins" case cannot arise by construction; it is covered by the fill
   model for the resting-order case and asserted separately in tests for the
   next-bar case).
3. **ATR (R5):** `smc.utils.atr.atr_series` — Wilder, period 14 (the
   codebase's standard period, reused; the buffer value is DUMB-owned).

## 3. Documented interpretive choices (all visible, none tuned)

Brief-required disclosure — these were decisions the lock left to the
implementer; each is unit-visible and deterministic:

- **Re-anchor on newer sweeps (R2+R3):** while a setup is pending, a later
  sweep bar on the same zone updates the R5 anchor to the newest sweep
  extreme and resets the confirm clock to that bar. Rationale: the newest
  sweep is the operative liquidity event. It is counted
  (`n_setup_anchor_updates`).
- **Supersession:** a zone replaced by a newer same-family M8 emission stops
  admitting NEW setups but its pending setup lives to its own
  confirm-or-expiry and its open trade runs normally on the recorded geometry.
- **One open position and one pending setup per zone** (design §7.5 default
  "none" = sequential per zone; across zones/TFs positions may overlap).
  Rejected admissions are counted, never merged.
- **Exec-window gating:** zones known at exec start are live; sweeps,
  confirms, and entries occur only on exec-window bars; the warm-up segment
  serves history for ATR and zone formation only. End-of-window open trades
  close at the last exec bar's close (`end_of_data`).
- **W3/W2 warm-up** = exec start − 30 days (2025-05-01 / 2024-11-01),
  mirroring the composition's 1-month warm-up convention.

## 4. First measurement (same windows as the COMPLEX diagnostics)

**Banner applies to every number below: DIAGNOSTIC — NOT EDGE.** Counts are
count comparisons only (design §6); PnL/PF are book-internal price units
(costs 0, market-at-close entries — NOT a trading result and NOT comparable
to COMPLEX's PnL).

| | W3 `2025-06-01 → 2025-11-30` | W2 `2024-12-01 → 2025-05-31` |
|---|---|---|
| DUMB trades (n) | **4364** | **2874** |
| COMPLEX fills (frozen book) | 58 | 44 |
| fill ratio vs COMPLEX | **75.2 ×** | **65.3 ×** |
| setups swept (R2) | 16 018 | 9 330 |
| anchor updates | 28 105 | 16 073 |
| confirmed (R3) | 7 100 | 4 411 |
| entry skipped (close outside zone) | 2 736 | 1 537 |
| expired (no confirm ≤12 bars) | 8 908 | 4 915 |
| exits | SL 2958 · TP 1406 | SL 1927 · TP 945 · EOD 2 |
| zones activated / superseded | 957 / 941 | 926 / 909 |
| M8 rescans (honest prefixes) | 1 163 | 1 131 |
| trades by zone TF | H4 4058 · D1 306 | H4 2647 · D1 218 · W1 9 |
| long / short | 2272 / 2092 | 1757 / 1117 |
| net PnL (price units) / PF | −974.88 / 0.966 | +618.30 / 1.038 |
| runtime per run | ≈73 s | ≈70 s |
| **determinism (run1 vs run2)** | **PASS — trades.csv byte-identical** (`0a8ecb45…`) | **PASS — byte-identical** (`555d1c8f…`) |

Counter arithmetic reconciles exactly in both windows: setups = confirmed + expired + (trades pending at window end: 10 in W3, 2 EOD exits in W2), confirms − outside-zone skips = entries = n_trades.

## 5. The headline finding is the counts, stated plainly

The locked rules as written produce **~65–75× COMPLEX's fill count** on the
same windows — the design §6 guidance asked for a **readable sample of
roughly 3–10×** and counts above the band trigger "tightening rather than
celebration". Nothing was tightened: the leg reports the rules as locked and
hands the two load-bearing interpretation levers back to the Architect:

- the **§7.5 per-zone cap fork** — sequential sweep→confirm→trade chains on
  the same zone produce most of the volume (33 308 sweep events in W3 hit a
  busy zone);
- the **re-anchor interpretation** — newer sweeps reset the confirm clock
  (28 105 anchor updates in W3), which extends setup lifetimes materially;
  treating consecutive sweep bars as ONE sweep (anchor only when the wick
  extends deeper) would shorten them.

## 6. Suite + isolation evidence

- Full suite: **1255 passed** (1 236 prior + 19 new), EXIT=0.
- `locked_constants.py`: diff **EMPTY**; no DUMB_* name in it (test-pinned).
- COMPLEX diff surface from this leg: `smc/dumb/**` (new) +
  `04_SRC/tests/test_dumb_flowchart.py` (new) — **nothing else**. The other
  modified files visible in git status (`smc/live/*`, `smc/data/mt5_connector.py`,
  `05_MQL5_SAFETY/*`, `config/live_demo.json`) are the pre-existing, dated
  live-path residual documented in the 2026-10-20 (7) handoff entry; mtimes
  (Oct 15–19) predate this leg and none of them contains a DUMB reference
  (the scan test also proves this at source level).
- COMPLEX path smoke: `PipelineEngine()` and `TriggerRouter()` (six default
  triggers, matrix present) construct cleanly in the suite.

## 7. Residuals / next hooks (for the Architect, not silent follow-ups)

1. **Volume band** — DUMB V1 as first measured is far above the §6 readable
   sample; the cap fork (§7.5) and the re-anchor interpretation above are the
   two named levers. Any change to them is a dated design amendment, not tuning.
2. **Traceability leg (§6.2)** — the ≥70 % PARTIAL+ chart-rubric gate is NOT
   yet run: it needs the expert sample (rubric + procedure were left to the
   implementation review; the rubric drafting remains an open call).
3. **W1/W4 (and full-book parity)** — not captured (W3 primary + W2 optional
   only, per brief); W1/W4 are a cheap extension of the same script if wanted.
4. **Live/EA**: nothing live; broker-realism (spread, slippage, session
   guard, circuit breaker, Friday EOD) is deliberately absent and each entry
   above is unrealistic against live fills until a dated realism leg adds
   them (design §4: log-only, never silently).
5. **No promotion path**: DUMB is default-OFF by construction (separate
   package, no product flag); promotion would need a dated Architect ruling
   plus the §6 criteria (count + rubric).
