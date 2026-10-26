# PRODUCT BASELINE V2 — PLAN (TIER-1 DESIGN LOCK)

**Date:** 2026-10-11 · **Authority:** Lead Architect Tier-1 directive (design lock before any long re-run or optimization).
**Status:** PLAN ONLY — no run launched, no code written, no constant touched.
**Plan status:** PROPOSED — requires Architect acceptance (and the cost-model dependency in §6) before any baseline compute is spent.
**Evidence base:** `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` (canonical runtime); `06_RESEARCH/PHASE_C_BASELINE_REPORT.md` (frozen M1 config, fingerprints, 77.4 compute-h anchor, segmented limitation); `06_RESEARCH/STRUCTURAL_TP_FEED_IMPLEMENTATION_NOTE.md` (TP feed as-wired, diagnostic-only); `06_RESEARCH/QUANT_AUDIT_2026-10-08.md` §5-Tier-1 item 4 (one clean 5y baseline on shipped product config); `06_RESEARCH/COST_MODEL_DESIGN.md` (companion Tier-1 note).

Standing rule (from the directive): the historical 5y baseline was M1, zero-cost, pre-M8 — it **must NOT be treated as the product baseline**. Baseline V2 is the first measurement taken in the product's own configuration.

---

## 1. Exact product config snapshot (frozen at plan time — any drift re-stamps this section)

| Item | V2 value | Source |
|---|---|---|
| Execution timeframe | **M5** (`RunnerConfig.timeframe=M5`) | LOCKED §21/§22; `backtest/runner.py:161-166` |
| Detection timeframes | **H4 + H1 required**, construction-enforced loud fail (`MissingHtfSeriesError`), degraded opt-in only | `orchestration/multi_tf_runtime.py:61,250-263`; contract §3 |
| Optional context | D1 supplied (→ M8 when available); W1 context tier; H4 always shared | contract §1; `multi_tf_runtime.py:376-387` (`supply_d1_to_m8=True`) |
| M8 | **provisioned** (D1/H4/W1 forwarded to M8) | `orchestration/multi_tf.py:43`; contract §1 |
| Detection cadence | one multi-TF batch per new H1 close | contract §1 |
| Structural TP | feed **as wired 2026-10-05**: `structural_tp_target` on the place-time §19-confirmed prefix (age bound `poi_give_up_bars()`), `resolve_take_profit` structural-vs-4×ATR-fallback, `tp_source` ∈ {`structural_swing`, `atr_fallback`} audit-only (never read by risk/fill/BE) | implementation note; `backtest/pipeline_bridge.py:71-176,179-282`; `backtest/pipeline_adapter.py:193-211` |
| SL policy | FR-2 structural SL (+0.3×ATR buffer); `original_sl` exported; BE latch + FVG invalidation as coded | `triggers/base_trigger.py:44-45,96-111` |
| Lot sizing | single §28.7 path: 1% risk band clamped, `LOT_MAX_SAFETY = 0.10`, `min_lots = 0.01`, `lot_step = 0.01` — **cap-binds on this book (recorded, not fixed here)** | `execution/lot_sizing.py`; `risk/lot_sizing.py`; audit M5 |
| Account | `equity = 10_000.0`, `pip_value_per_lot = 10.0` | `backtest/runner.py:154-156` |
| Sessions | ASIA + LONDON + NEW_YORK combined 00:00–20:00 UTC; Friday EOD 20:00 UTC force-close | shipped research configs; §28.4 |
| Spread gate | §28.5 wired, value from cost-model config (until then: declared diagnostic) | contract §8 table |
| News / sweep-guard | `news_events=[]` (DEFERRED); sweep guard dormant (no trigger emits `sweep_level`) | contract §8 |
| `dry_run` | **N/A** — `dry_run` is a live/paper operator concept (`live/config.py`, `paper/runner.py`); the backtest baseline has no `dry_run` flag | — |
| Trigger D | compiled, structurally unfireable on the volume-less dataset (A5 ruling stands); per-trigger tables will show 0 | data acceptance A5 |
| Determinism aids | deterministic-id injection for byte-identity (Phase C practice); manifest fingerprint (config hash, data hash `e5d730ea…`, script hash) | Phase C §2–§3 |

Frozen-for-V2 account/cost values (commission schedule, slippage points, spread fallback) are **not** snapshotted here — they arrive with the merged cost model (§6) and are pinned in the run manifest at launch.

## 2. Data window options + estimated runtime from Phase C

Canonical data: `07_DATA/XAUUSD_M1.parquet` (1,768,123 bars, 2021-04-12 11:00 → 2026-04-10 20:59 UTC), resampled to M5 exec (~353.6k M5 bars) + H1/H4/D1 detection prefixes. No new data stack; no volume resurrection (Trigger D stays 0 by ruling).

| Option | Window | Character |
|---|---|---|
| **A — staged pilot (RECOMMENDED first)** | e.g. full year 2025 (≈354k M1 → ≈71k M5 bars) on the exact §1 config | validates the product-config composition + costed export end-to-end before committing to 5y; a pilot anomaly costs hours, not days |
| **B — full 5y, segmented** | 2021-04-12 → 2026-04-10 in calendar-year segments with checkpoint/resume (Phase C pattern: 6 segments, per-segment warm-up, manifest fingerprint) | same accepted limitation as Phase C (fresh engine per segment, no cross-segment state carry — documented, not silent); directly comparable to the historical baseline's window |
| **C — full 5y, continuous** | same window, single run | requires cross-segment state carry — new machinery, out of scope unless explicitly ruled; NOT proposed for V2 |

**Runtime estimate, anchored to Phase C (not invented):** Phase C recorded **77.4 compute-hours at ≈6.3 bars/s (≈159 ms/bar)** for 1,768,123 M1 bars, segmented 6× with one interruption + supervisor relaunch. For V2 planning: the M5 exec bar count is ≈1/5 of M1 (≈353.6k bars), but per-bar work differs (multi-TF batch per each of ≈43.8k H1 closes + trigger scans per M5 bar), so linear scaling is **not** claimed. Measured short-window anchor: the C1 parity smoke ran 2,761 M5 bars through the product seam in ≈27 s (≈102 bars/s) — a throughput upper bound on fresh-cache short windows, not a 5y projection. **Required step before committing to option B: run option A (or a 1-month calibration) and measure steady-state bars/s, then project; publish the projection in the launch note.** Budget for the determinism pair (×2) plus merge/verify time. Checkpoint/resume is mandatory for any run longer than the pilot (Phase C pattern).

## 3. Determinism pair requirement (non-negotiable, Phase C discipline)

Every baseline V2 run ships as a **pair** (run1/run2, identical config + data + code), and the verdict requires all of:

1. `bars_processed` equal in both runs, covering the full declared window;
2. `trades.csv` **byte-identical** (SHA-256 match);
3. `report.json` **byte-identical** (SHA-256 match);
4. summary identical excluding runtime fields;
5. invariants `OK` (no non-OK key), Trigger D trades = 0;
6. costed columns included in the byte-identity (net + breakdown columns are deterministic outputs, not annotations).

Single-run numbers are progresso reports, never baselines. Verdict script + re-stamp procedure follow the Phase C closeout pattern (`phase_c_verdict.py` lineage).

## 4. Metrics to report (diagnostic; costs-on headline)

Per run-pair, reported from the merged artifacts:

- **Book:** trade count, win rate, profit factor, net PnL (costs-on), max drawdown (closed-trade equity curve, existing `_max_drawdown` definition), gross-vs-net attribution bridge (total commission / spread / slippage paid).
- **Splits:** per-trigger (A/B/C/E/F + unrouted-funnel counts), per `tp_source` (`structural_swing` vs `atr_fallback` — the first honest read of the TP feed's contribution), per-year segment, per-direction.
- **Funnel:** pois detected → validated → armed → routes → placed → filled → closed, with `blocked_by_reason` histogram (same shape as Phase C §4, so the two baselines' funnels are comparable stage-by-stage).
- **Costs-on vs costs-off:** both columns published for every aggregate; costs-on is the headline, costs-off is labeled upper-bound attribution. Cheap by construction (one run, two columns — §3 of the cost note).
- **Config appendix:** full canonical config JSON + manifest fingerprints (config/data/script hashes) so any table is reproducible.

## 5. Explicit: diagnostic until CI/WF exists; no edge claims

Baseline V2 is a **diagnostic reference point for the product-config frozen stack** — the same binding language as Phase C: not an edge claim, not a tuning target, not an authorization to redesign, scale, or trade live capital. Every artifact (report, CSV, JSON, charts) carries the diagnostic stamp. Walk-forward / Monte Carlo / bootstrap confidence (Phase E) does not exist yet; until it does, **no number from V2 supports or refutes the concept with statistical confidence**, and the report states that in its own §1 rather than in a footnote. A losing costed baseline authorizes evidence review, nothing else; a positive one authorizes Phase E validation, nothing else.

## 6. Dependencies: cost model merged first

Launch order is strict:

1. Architect accepts `COST_MODEL_DESIGN.md` (rulings on its §8 as needed — unanswered questions may narrow V2 scope but must not silently zero any cost);
2. cost model implemented per the accepted design (`cost_model.py` + seams + export columns + `bars_held`);
3. unit tests per its §7 green; full suite green; `locked_constants.py` diff empty;
4. cost model merged to the baseline branch;
5. **only then** pilot (option A) → measured projection → full V2 (option B) on acceptance of the pilot.

A product baseline launched on the zero-cost stack after this lock would re-baseline the exact defect this Tier exists to kill — it is prohibited by this plan, not merely discouraged.

## 7. Out of scope (named follow-ons, not V2)

- **Phase E (confidence harness):** walk-forward / block bootstrap / Monte Carlo / benchmark suite (buy-&-hold XAU, random-entry-same-exit, naive BOS) — the audit's Tier-1 item 1 alongside costs; V2 produces the book Phase E will validate, it does not implement Phase E.
- **Continuous-run state carry** (option C machinery) unless explicitly ruled.
- **Volume-bearing feed / Trigger D resurrection; tick-spread work beyond the cost model's needs; Mode B** (registered future track, untouched).
- **F entry-selectivity program, stop-band studies, M8 contribution measurement, funnel-selectivity splits** — Tier-2 research that consumes V2's book; none of it runs inside the baseline.
- **Live capital, demo-P/L-as-evidence, threshold tuning of any kind.**

---

## Appendix S — Spread-grade scale mismatch: two ruling options only (NO code change)

Standing fact (audits agree, still present): `score_poi` returns tag-count scale (1, 2, 3, …) while `SPREAD_GRADE_SCORE_THRESHOLDS = {"A+": 8, "A": 5, "B": 3, "C": 0}` is written for a 0–10 quality scale — A/A+ tolerance is effectively unreachable as coded, so every spread-sensitivity conclusion is shifted down a tier (quant audit M4; independent audit #2; `POST_V1_ACTIVE_TODO.md:298`).

Two ruling options are recorded — **documented only; no code change in or after this note**:

- **Option (a) — remap the thresholds to the tag-count scale.** Keep `score_poi` as-is; re-rule `SPREAD_GRADE_SCORE_THRESHOLDS` onto the 1–3 observable range (illustrative shape only, e.g. tiers keyed to tag counts 1/2/3+ — exact values by dated ruling). Touches a locked constant → requires a dated Lead Architect ruling. Narrowest blast radius; concedes the 0–10 scale was aspirational.
- **Option (b) — feed a true 0–10 quality score.** Keep the thresholds; build a real 0–10 POI quality scorer (new design note + implementation + tests required) and feed it to `grade_for_score`. Preserves the design intent; larger surface (new scorer = new code to govern).

Sequencing vs the cost model: **independent tracks.** The cost model charges spread per fill regardless of grade; the grade scale governs only the §28.5 entry block. Either track may land first; neither may silently assume the other. If the M4 ruling lands before V2 launch, V2 snapshots the ruled values in §1 and reports the gate's `blocked_by=spread` histogram against them — no re-baselining of already-published numbers without a new dated ruling.

---

```
BASELINE_V2_PLAN_STATUS: PROPOSED (acceptance + cost-model merge required before compute)
HISTORICAL_M1_BASELINE_IS_PRODUCT_BASELINE: NO (explicit)
DIAGNOSTIC_UNTIL_PHASE_E: YES (no edge claims from V2)
LOCKED_CONSTANTS_DIFF: empty (none proposed)
NEXT: Architect acceptance → cost model implement+merge → pilot (option A) → measured projection → full 5y (option B)
```
