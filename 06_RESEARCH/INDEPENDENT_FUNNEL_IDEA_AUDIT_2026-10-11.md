# INDEPENDENT AUDIT — IDEA / FUNNEL / DECOMPOSED FLOWCHART

**Date:** 2026-10-11 · **Role:** independent reviewer (senior quant + software architect + risk manager). I did not design the strategy and claim nothing about profit.
**AUDIT_STATUS: PASS** (review + measurement plan only).
**LOGIC_CHANGED: NO** — no code written, no constant touched, no threshold moved. All counts below are requoted or arithmetically derived from dated artifacts on disk (paths cited); no new runs were made.
**Standing banner:** nothing in this note supports or refutes edge, authorizes live capital, or licenses any gate/loosening. A losing or tiny book authorizes evidence review, nothing else.

---

## PART A — EXECUTIVE VERDICT

**What was built (idea vs coded product).** The idea is the expert's discretionary SMC stack — HTF POI (W1/D1/H4 context, M8 preferred) → liquidity sweep → displacement/FVG confirmation → LTF surgical trigger → risk-gated limit placement → managed exit — translated with unusual fidelity and governance discipline into a deterministic multi-timeframe machine (M5 execution, H4+H1 detection, M8 provisioned, structural TP feed, §5a seek, R7/R9 placement regime, V1 cost ledger, Track-B annotation carriage; 955 tests green; byte-identical determinism pairs). The coded product is that idea *plus* a long AND-chain of machine-checkable gates the expert never specified numerically (pillar cutoffs, seek windows, zone-proximity placement rules, session filters, one-shot/identity rules) — and it is the AND-chain, not the idea, that sets the observed frequency.

**Primary diagnosis: (b) over-strict AND-chain — with one crucial nuance.** The combined product completes ~3 fills per 6 months not because events are absent (they are abundant at every decomposed stage: 96k raw detections, 43k merged, 263 Stage-3 completions, 15k detector links in the same window) but because each conjunct multiplies attrition: pillars kill 95.3%, trigger-window/chronology kills 98% of scans, placement gates kill 60% of routes, expiry kills unfilled orders — leaving 3. **Secondary: (c) handoff frictions at specific gates** (seek-span collapse, measured and fixed by §5a; residual fill-or-expire on tight §24 windows; placed-vs-intent accounting ambiguity), **plus (d) data gaps** (all-zero volume structurally kills Trigger D; spread is reconstructed, not measured). Not (a): nothing at n = 3 can support "correct rare edge" either way, and the nuance matters — even a *perfect* downstream converts only ~30 unique zone-episodes per 6 months (~5/month), a normal institutional cadence that is simply unvalidatable in any 6-month book. The failure is not "too few trades to be a strategy"; it is "too few trades to *measure* while the fragments that would validate the idea go unmeasured because they never complete the chain." Hence the decomposed plan (Part C), not loosening.

**Scorecard (1–10, re-judged independently — convergence with the 10-08 quant audit where noted is agreement, not copying):**

| Layer | Score | One line |
|---|---|---|
| Idea clarity (expert process) | 8 | Coherent, documented, expert-backed; entry-timing economics unproven |
| Flowchart fidelity (as coded) | 7 | Stages faithful; breadth collapses to F+B in fills; M8 arms/routes but barely fills |
| Implementation (engineering) | 9 | Deterministic pairs, 955 tests, honest artifacts, disciplined governance |
| Measurability | 6 | Fragment packs are superb (labels, paths, horizons); the combined book (n=3) is unmeasurable; placed-vs-intent accounting is ambiguous |
| Economic evidence | 2 | Negative or n-tiny everywhere; the single measured bottleneck is entry-side |
| Ship readiness (ops) | 4 | Connector/heartbeat/watchdog/drills real; costs now on; demo P/L ≠ validation; no sustained unattended run |
| Overall idea→money translation | **4** | A stronger instrument than on 10-08 (costs, harness, 6m refresh all landed since) attached to the same unproven economics |

---

## PART B — FUNNEL FORENSICS (combined product)

### B1. Product 6m refresh, costs-on (35,725 M5 bars; `results/product_6m_refresh_track_b/`)

| Stage | In → Out | Death rate | Reading |
|---|---|---|---|
| Raw detections (H4 44,922 + H1 51,093) | 96,015 → 43,004 merged | 55% merged away | geographic-overlap merge — dedup, not rejection |
| Pillars (all merged validated) | 43,004 → 2,021 PASS | **95.3% killed** | **P2 kills 37,745 (87.8% of merged)**; P3 2,031; P1 1,207. P2 (FVG-absence first) is the single biggest gate in the machine |
| Arm (unique zones) | 2,021 passed → **30 armed** (+1,991 duplicates suppressed) | — | NOT rejection: the same ~30 zones re-detected ~67× across batches. The HTF side yields **~30 distinct episodes / 6 mo (~5/mo)** — the idea's natural cadence, arguably correct |
| Scan → route | 501 scans → **10 routes** (F 9, C 1; M8 10/10) | **98% of scans no-route** | chronological-first + trigger §24 windows + one-shot; completions exist downstream-unseen (see B3) |
| Route → place | 10 routes → **4 placed** (+7 R9 intents armed → 3 intent-placed) | **60% of routes never place** | R7 far-from-zone skips 14, sessions block 4 (per-event counts); order rests 12–30 bars then §24-expires |
| Place → fill | 4 placed → **3 fills** | ≥1 expired unfilled | limit-touch-or-die on tight windows |
| Exits | 3 trades | — | C TP win / F full-SL loss / F BE-scratch; costs $2.78 (~$0.93/trade, spread+slippage only) |

Nested 3-month check (same machine, Sep–Nov): 20,898 merged → 839 passed → 18 armed → 256 scanned → 9 routes → 2 placed → 2 fills. The 6m book is not 2× the 3m book (episodes cluster in time) — frequency is regime-lumpy, another reason short books can't validate.

### B2. Phase C 5y M1 baseline (1,768,123 bars; `results/phase_c_baseline_run1/`, zero-cost, pre-M8)

10,682,651 raw → 6,256,227 validated / 928,436 pass (**14.8%**) → 5,166 armed unique → 981 routes → 792 placed (one-shot; 0 violated_pulls) → **761 fills** (31 expired_give_up) → 754 SL + 7 Friday-EOD. Blocked: session 612, breaker 266; all other gates 0. Same shape at scale: pillars dominate early, trigger/route selectivity dominates mid-funnel, placement/fill frictions take the last ~4%. (Not the product baseline — M1 exec, zero-cost, pre-M8 — but the only large-n funnel on record, hence its forensic use.)

### B3. Binding constraints, named with counts (product 6m)

1. **Pillar 2 (FVG-absence first): kills 37,745/43,004 merged (87.8%).** Nothing else is within an order of magnitude. Whether FVG-absence predicts failure is *untestable* in the combined book (admitted-FVG rate vs kill-FVG rate was never split — Track R's open question, still open).
2. **Scan→route conversion: 10/501 scans (2.0%).** The lifecycle audit proved completions *form* (263 under the old contract in this same window) but the router's chronology + window rules admit ~10. §5a reclaimed scan span; routes did not follow proportionally — the constraint moved downstream, it did not dissolve.
3. **Route→fill conversion: 3/10 routes (30%).** R7 zone-proximity defers (14 skips → intents, 3 intent-placed), sessions block (4), §24 expiry kills resting orders that never touch.
4. **Episode cadence: ~30 unique zones / 6 mo.** Even a frictionless downstream caps at ~5 candidates/month — validation needs years, not windows.

### B4. "No event" vs "event but rejected by gate" (separated)

- No event at all: rare. Batches run clean (0 errors, 2,979/2,979); detectors fire continuously (96k raw/6mo).
- Event but rejected: the entire story. Every stage's mass dies *inside named gates with counts* (pillar histogram, blocked_by_reason, expired_give_up, violated_pulls=0). There is no silent drop anywhere in the measured path — the machine's honesty is not in question; its *selectivity calibration* is unmeasured (see Part D).

---

## PART C — DECOMPOSED FLOWCHART STUDY PLAN (read-only event ledger)

**Principle:** inventory each flowchart concept on the SAME 6m window (exec 2025-06-01 → 2025-11-30, M1 warm-up from 2025-05-01) **without requiring the full HTF→LTF→entry chain to complete**, then measure post-event price behavior with frozen horizons. Three of the five ledgers below substantially exist — the study is assembly + one post-event scan module, not greenfield detection. No production threshold is loosened, read, or re-run in this task; several rows are "reuse artifact X."

| # | Concept | Detection source in code (read-only) | Independence rule (no full arm required) | Post-event metrics (frozen horizon) |
|---|---|---|---|---|
| 1 | HTF POI / M8 zone appear | Accepted pack rows (`results/h4_poi_confirmation/events_h4_poi.csv` + D1 subset — already this window) **or** `DetectionDriver.detect_pois` per batch | Zone exists in the pack; arm state ignored | Zone fate over H_ZONE = 20 M5 (give-up scale): first touch / hold / violate + time-to-first-touch; excursion ±k×ATR from zone mid |
| 2 | Sweep of level | `liquidity_scanner` / `sweep_detector` stage-0 (**or** reuse `results/ltf_confirmation/events_ltf_confirmation.csv` sweep rows — same window, already linked to structures) | Timestamped sweep event only; no POI required | H_PATH = 100 M5 (Track-B consistent): displacement follow-through (BOS within H?), ±ATR excursion, sweep→continuation rate |
| 3 | Displacement / FVG | stage-0 detectors (**or** reuse the LTF ledger's displacement/FVG rows) | Event exists; pillar verdict ignored | FVG fill rate in H (filled / partial / unfilled — the R-question split the combined book cannot do); displacement continuation multiples |
| 4 | LTF trigger A–F completions | `TriggerRouter`/per-trigger `evaluate` in scan mode (**or** reuse `results/stage3_trigger_visibility/events_stage3_triggers.csv` — 263 rows, this window, ungated inventory) | Completion recorded ungated by §5 state (precedent: the visibility pack) | Same H_PATH read as the product study: MFE/MAE in ATR (no hypothetical SL → **ATR units, not R**), +1×/+2×ATR hit, reverse through invalidation, time-to-extreme |
| 5 | On-zone vs off-zone entries | Real fills only (n = 3, listed — no hypothetical placements, ever) | — | Carried for completeness; the combination test below replaces entry analysis at this n |

**Numeraires (frozen):** no hypothetical stop-loss may be invented, so non-trade events are measured in **ATR(14) units at the event bar** (MFE_ATR/MAE_ATR, +1/+2 ATR hits, adverse excursion past the invalidation level: zone far edge / sweep origin / trigger stop-reference where the trigger genuinely emits one). **Horizons frozen:** H_ZONE = 20 M5 (the product's own give-up scale — zone-fate question), H_PATH = 100 M5 (Track-B post-exit horizon — path question). Time-to-extreme in bars, both horizons.

**No-look-ahead rules (established pack practice, mandatory):** prefix-only computation — every detector input trimmed to bars with timestamp ≤ the decision bar (`as_of` trimming, as the LTF/Stage-3 packs do); resampling from the canonical parquet only; forward scans read-only; entry/exit/event indices resolved by timestamp, never by run-relative bar numbers across books; unique-event identity is geometry+timestamp (run-local uuids never participate).

**Ledger schema (per concept, one row per unique event):** `event_id` (deterministic geometry-derived, pack convention) · `concept` · `detection_tf` · `direction` · `ts_utc` · anchor fields (zone bounds / sweep level / trigger entry+stop-ref) · `htf_context` (nearest accepted HTF zone at event time + relation: inside/near/far — computed, for the combination test) · source pointer (artifact path or code path + config hash) · horizon used · post-event fields (MFE_ATR/MAE_ATR, hit flags, invalidation-breach flag, time-to-extreme, bars_held_equivalent) · `note` (degenerate/unknown cases named, never filled).

**Combination test (the core of Part C — no new trades, no thresholds):** stratify every isolated LTF event (concepts 2–4) by `htf_context` at event time — same detector, three contexts (inside / near / far from an accepted HTF zone). If HTF context separates post-event outcomes (non-overlapping intervals at stated n), the HTF-gating half of the combination earns its keep *as a measurement*; if not, HTF-gating is unproven and the combination reduces to LTF-only pending OOS. Mirror image: HTF zones with vs without a subsequent LTF trigger inside H_ZONE (the accepted packs + LTF ledger already hold both halves: 623 active vs silent structures). Both tests reuse recorded rows — zero new detection runs required for v1.

**What would falsify the current product combination (stated upfront so the study can fail):** (i) context-stratified isolated-LTF outcomes do not separate (HTF adds frequency cost without measured benefit); (ii) routed-trigger outcomes ≈ unrouted-completion outcomes on the same post-event read (routing selects nothing — chronology/first-valid is pure attrition); (iii) post-arm fill rate stays ~30% regardless of pillar path, confluence, or tp_source (placement/fill frictions dominate selectivity — the fix would be execution design, not entry filtering).

---

## PART D — COMBINATION HYPOTHESIS

**What the AND-chain assumes (each conjunct stated so it can be priced):** a tradeable event = HTF zone × sweep × displacement × FVG-present × pillars 1–5 × seek-window-open × trigger-completes-in-window × chronological-first × R7-zone-proximity × session-open × risk-sizeable × limit-touched-before-expiry × managed-exit-survived. The chain assumes every conjunct is *positively selective* (each multiplies edge, not just divides frequency) — an assumption no artifact has ever tested, because every measurement to date conditions on the chain completing.

**How to test "HTF context adds value" vs "LTF alone":** the Part C stratification — identical isolated LTF events, HTF context varied, post-event ATR readouts compared. Secondary: routed vs unrouted completions on the same read (tests the router); placed vs expired orders on fill-touch distance (tests R7/expiry as execution design, not selectivity).

**Cost of the question the other way:** the study must also report absolute post-event outcomes per fragment (not only separations) — a fragment can win the stratification contest and still be untradeable after costs (the V1 ledger applies per fill; fragments that never fill pay nothing but also earn nothing — both stated).

---

## PART E — PLAN TO MAKE IT WORK (prioritized, non-wishful)

**Tier 1 — measurement (no ruling needed beyond this audit's acceptance):**
1. Build the decomposed ledger (Part C table) on the frozen 6m window, assembling the three existing packs + one post-event scan module (frozen H_ZONE/H_PATH, ATR numeraires, prefix-only rules). One new research script, reusing pack loaders — the natural next coding step, explicitly **not** another product-only refresh.
2. Binding-gate report from *logged* reason codes only (pillar first-failure histogram, blocked_by_reason, expired_give_up, violated_pulls, intent lifecycle): marginal kill rate per gate **as observed**. No rerun with loosened gates — that would be threshold fishing, and it stays banned. (Placed-vs-intent accounting ambiguity from §B1 is fixed as part of this: disjoint counters with one definition each.)
3. Publish the combination test (stratified readouts + the three falsification checks) as a dated report with the diagnostic banner. Decision rule written before running: publish regardless of outcome.

**Tier 2 — design forks needing explicit Architect ruling (listed, not recommended, definitely not silent):**
- Continuous-run state carry for multi-year books (vs the accepted segmented limitation) — required before any 5y product number is more than staged evidence.
- Real commission schedule pin (costs are $0-commission until then — every net is provisional by ruling, not by oversight).
- Tick-reconstructed spread series as the cost source (vs the 0.26 fallback).
- Volume-bearing feed (resurrects Trigger D; re-opens the volume-confirmation question).
- M8 fill attribution once fills exist (routes already 10/10 M8-touched; fills unproven).
- Any funnel-loosening whatsoever (pillar bands, seek span, R7 proximity, sessions) — each a separate dated ruling with a pre-registered measurement, never a quiet tune.
- Phase E confidence harness (WF/bootstrap/MC) remains the standing requirement before any edge-shaped conclusion.

**Explicit non-goals:** no live late_chase gate; no TP fishing; no "3 trades prove edge" (or disprove anything); no Mode B; no treating demo P/L as evidence; no re-running the product-only refresh at any window until the decomposed ledger exists.

---

## Appendix — artifact paths cited (all on disk)

Product 6m refresh: `06_RESEARCH/results/product_6m_refresh_track_b/` (run1/run2 + `summary.json`) · report `06_RESEARCH/PRODUCT_6M_REFRESH_TRACK_B_REPORT.md` · pilot `results/product_baseline_pilot/` · Phase C `results/phase_c_baseline_run1/merged/trades.csv` (+ segments) · LTF pack `results/ltf_confirmation/` · Stage-3 pack `results/stage3_trigger_visibility/` + lifecycle `results/stage3_lifecycle_timing/` · F selectivity `results/f_selectivity_post_exit/` + `06_RESEARCH/F_SELECTIVITY_POST_EXIT_REPORT.md` · hypothesis/stop-structure/honest-R/r1-r4 notes + results dirs · quant audit `06_RESEARCH/QUANT_AUDIT_2026-10-08.md` · contract `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` (+ §5a in `LOCKED_DECISIONS.md`, design `06_RESEARCH/SEEK_SCAN_CONTRACT_REDESIGN_DESIGN.md`) · cost design/implementation notes · harness note.

```
AUDIT_STATUS: PASS
PRIMARY_DIAGNOSIS: (b) over-strict AND-chain — 96k detections → 43k merged → 30 unique armed episodes → 10 routes → 3 fills in 6mo, with mass dying inside named gates (P2 87.8% of merged; 98% of scans unrouted; 70% of routes unfilled); secondary (c) specific handoff frictions + (d) volume/spread data gaps; not (a) — n=3 can support no rarity claim either way, and ~5 episodes/mo would be a normal institutional cadence with a frictionless downstream
BINDING_GATES: [Pillar-2 FVG-absence (37,745/43,004 merged); scan→route conversion (10/501 scans); route→fill conversion incl. R7-proximity defers + §24 expiry (3/10 routes); ~30 unique zone-episodes per 6 months (cadence ceiling, not a gate)]
DECOMPOSED_STUDY_READY: YES (schemas, horizons H_ZONE=20/H_PATH=100 M5, ATR numeraires, prefix-only rules, combination test + three falsification checks specified above — implementable next as one research script reusing the three pack loaders)
TOP_3_NEXT: [1. build the decomposed 6m ledger + binding-gate report from logged reason codes (no loosening reruns); 2. run the HTF-context stratification + routed-vs-unrouted falsification checks; 3. fix placed-vs-intent accounting ambiguity, then Architect rules on Tier-2 forks (5y state carry, commission schedule, tick spreads, volume feed) before any long baseline]
REPORT_PATH: 06_RESEARCH/INDEPENDENT_FUNNEL_IDEA_AUDIT_2026-10-11.md
LOGIC_CHANGED: NO
```
