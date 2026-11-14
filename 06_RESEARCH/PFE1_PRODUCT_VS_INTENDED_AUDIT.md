# PFE-1 — PRODUCT VS INTENDED DRIFT AUDIT

**Date:** 2026-11-14 · **Program:** Product Fidelity & Evidence (PFE), step 1
**Status:** COMPLETE · **`LOGIC_CHANGED: NO`** · **product code unmodified**
**Mode:** read-only audit (no strategy edits, no threshold change, no re-runs)
**Auditor:** local research agent (independent of the strategy's authorship in this session)

**Authority read (in order):**
`00_LOCKED/LEAD_ARCHITECT_ROLE_AND_PROTOCOL.md` · `00_LOCKED/LOCKED_DECISIONS.md`
(§0, §1–§5a, §16/§16a, §17a, §20a, §21/§21a–c, §22/§22a, §25, §27, §28) ·
`00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` · `00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md` ·
`00_LOCKED/PRODUCT_POLICY_MULTI_TF_CONFIRMATION.md` (LOCKED 2026-10-26) ·
`00_LOCKED/MODE_A_LTF_RETURN_ENTRY_DESIGN.md` · `00_LOCKED/R9_PLACE_ON_REENTRY_DESIGN.md` ·
`06_RESEARCH/AS_CODED_ARCHITECTURE_FLOWCHART.md` · `06_RESEARCH/OPEN_DECISIONS_RESEARCH_AGENDA.md`
(O1–O5 CLOSED) · `04_SRC/smc/**` (read only).

---

## 1. Executive verdict

**Mostly aligned, with one material drift and one silent absence — both in the same
seam.** The detection → pillar → trigger → risk spine is faithfully implemented: the
multi-TF runtime, the closed-bar prefix contract, the five pillars, C3 in-between as a
hard gate, §5a seek/scan, R7/R8/R9 and the §28 risk gates all match their locked text,
and the two most commonly doubted pieces (C3 and structural TP) are genuinely wired,
not merely present. The drift is **which entry law the product runs**: since
2026-10-26 `PRODUCT_POLICY_MULTI_TF_CONFIRMATION.md` makes the *sweep → LTF confirmation
menu* the default live product mode (`run_operator.py`, `PRODUCT_V1` → `ProductMenuEngine`),
while the research/backtest composition used for every measurement since (Phase 3,
`frozen_funnel_6m_*`, O1–O5) runs the **seek/adapter** path and never constructs a menu.
The silent absence lives on that same menu path: it bridges through
`candidate_from_route(..., atr=atr)` **without** `structural_target=`, so every
menu-confirmed entry takes the 4×ATR TP — the §21b "first valid swing" rule holds only on
the seek path, and nothing in the code or docs says so. A 6-month run on today's research
composition would therefore measure a machine that is *not* the default live machine, and
would understate structural TP coverage on the path the product actually ships.

---

## 2. Audit matrix

| # | Stage / concept | Intended (cite) | Code path (file/symbol) | Evidence | Class | Notes |
|---|---|---|---|---|---|---|
| A | HTF structure map — POI inventory (OB / D-S / FVG) | §1 tags M1–M8; §4b inventory = M15, H1, H4, D1 (W1 optional); §22 D/S definition | `orchestration/multi_tf.py` `M8_HTF_TIMEFRAMES`; `orchestration/product_menu_mtf.py` `MenuTier` (D1/H4/H1/M15); `poi/model_registry.py`; `poi/models/m8_htf_demand_supply.py` | `multi_tf_runtime.py:338` accepts `{D1,H4,H1,M15}`; `product_menu_mtf.py:245-248`; M8 `HTF_TIMEFRAMES=(W1,D1,H4)` | **ALIGNED** | M8 scans W1/D1/H4 while generic detection adds H1/M15 — matches §4b + §21. |
| B | Sweep / liquidity (Stage 0) | §2 levels (session/PDH-PDL/PWH-PWL/EQH-EQL/structural swings/POI bounds); §2.5–2.6 fallbacks | `detection_driver.py` (`scan_liquidity` → `detect_sweeps` → per-POI `attribute_displacement`); `detection/sweep_detector.py`; `orchestration/sweep_episode_coordinator.py` | `detection_driver.py:10-16,124-145`; menu R2 sweep in `product_menu_mtf.py` | **PARTIAL** | Sweeps are detected and used as Pillar-2 attribution + menu arm condition, but **no candidate carries `sweep_level`** (`pipeline_bridge.candidate_from_route` never sets it) ⇒ §28.6 sweep guard is inert. Consistent with O2 "sweep is context, not stage", but then §28.6 should be recorded as unreachable. |
| C | Displacement + FVG context | §3 (≥1×ATR, BOS + FVG; hard fail <0.5×ATR) | `detection/displacement_checker.py`; `engine.validate(displacement_map=...)` → Pillar 2; `fvg_context_for_route` | `engine.py:7-12,219-238`; `pipeline_bridge.py:295+` | **ALIGNED** | FVG context only from Trigger F's own signal — honest `None` otherwise (no invented geometry). |
| D | Model tags M1–M8 + merge / confluence | §1 equal tags, no hierarchy; §26 M8 overlap +0.10 | `poi/models/m1..m8`; `engine.merge_overlapping` before Pillar 1; `poi/confluence_scorer.py` | `engine.py:7`; `m8_htf_demand_supply.py:198-200` | **ALIGNED** | Merge precedes validation exactly as §1 requires; score = tag count (matches §28.5 amended tiers). |
| E | Five pillars + arm | §16 Stage 2; §16a Pillar 3 = Dealing Range (naming); §6 45/55 reject | `validation/pillar_1..5`; `engine.validate`; `engine.arm_at` | `pillar_3_premium_discount.py:1-12` (45/55 hard reject, sole owner) | **PARTIAL** | Behaviour correct; **A5 naming not carried into code** (module/docstring still "Premium / Discount"). Cosmetic, but an expert reading the tree sees the superseded name. |
| F | Multi-TF runtime / HTF prefixes / no lookahead | Contract §1–§3; closed-bar contract (F1) | `orchestration/multi_tf_runtime.py` (`build_htf_prefixes`, `MissingHtfSeriesError`, `ZoneDedup`); live + paper wired | `multi_tf_runtime.py:132-160` (cutoff = `as_of − tf.minutes`); loud-fail at construction | **ALIGNED** | Closed-bar-only is the single contract for research/paper/live — one genuine improvement over the pre-F1 cut. |
| G | LTF Stage 3 triggers A–F | §24a letter map; §24 expiry windows | `triggers/trigger_a..f`; `trigger_router.py`; `compatibility_matrix.py` | `trigger_d_two_bar.py:56-78` (requires `engulfer.volume < engulfed.volume`) | **PARTIAL** | Trigger D is volume-gated: it silently never fires on a series without a real volume column (resampled bars propagate volume, so XAUUSD parquet is fine, but a synthetic/zero-volume feed kills D without a diagnostic). |
| H | Seek/scan contract §5a | §5a postures, span, terminators, one-shot | `orchestration/engine.py` (`scan_route`); `backtest/pipeline_adapter.py` (`_scan_cursor`, `menu_covers_poi`) | `pipeline_adapter.py:400-470` | **ALIGNED** | Cursor resume (never restart), one-shot per POI, give-up span from `poi_give_up_bars()`. |
| I | C3 in-between gate | §25 + 2026-11-12 clarification (close inside body, `not_in_between`) | `triggers/in_between.py`; enforced in `candidate_from_route(completion_price=)`; **both** entry paths pass the completion close | `pipeline_bridge.py:248-252`; `pipeline_adapter.py:405-415`; `product_menu_mtf.py:999-1005,897` | **ALIGNED** | Rejection resumes the scan rather than killing the POI — matches §5a §6 note (a later in-between completion may win). |
| J | R7/R8/R9 place-on-reentry / intent | `R9_PLACE_ON_REENTRY_DESIGN.md`; FR fill-regime R7/R8 | `risk/fill_regime_policy.py`; `backtest/intents.py`; `paper/runner.py` R9 steps | `paper/runner.py:291,644-647`; `fill_regime_policy.py:6-17` | **ALIGNED** | Intent-level place-on-reentry is wired in the paper/backtest book; R9 remains an intent (not a live send), as designed. |
| K | Risk gates + SL/TP resolution | §28.1–§28.8; §21b SL = ATR buffer, TP = first swing else 4×ATR | `risk/risk_engine.py` (news/session/breaker/same-level/sweep/spread + Friday EOD); `pipeline_bridge.resolve_take_profit`; SL from `signal.stop_reference` | `risk_engine.py:207-230`; `pipeline_bridge.py:72-107` | **PARTIAL** | SL path aligned (ATR-buffer, `original_sl` = placement SL). TP: structural branch is live **only where `structural_target=` is passed** — `pipeline_adapter.py:448` yes, `product_menu_mtf.py:999` no. News calendar empty and `spread_price=0.0` shipped ⇒ those gates remain diagnostic (documented). |
| L | Backtest vs paper vs live "same machine" | Contract §1–§2 one-driver rule; POLICY doc rule 6 "default live product mode = this policy engine" | live: `run_operator.py` `PRODUCT_V1` → `ProductMenuEngine` **plus** seek adapter; research: `phase3_structure_funnel.py` constructs `PipelineAdapter` only | `run_operator.py:487-525`; `phase3_structure_funnel.py:154` (no `ProductMenuEngine`); `live/loop.py:404-450` drives the menu | **DRIFT** | Two entry laws are shipped. Live runs menu **and** seek (adapter skips menu-covered POIs); the research/backtest composition runs seek only. Every measurement since 2026-10-26 (Phase 3, frozen funnel, O1–O5) therefore samples the non-menu half of the live book. The contract (pre-menu) and the POLICY doc (post-menu) were never reconciled. |
| M | Operator console / structure boards | Ops fidelity; `MODE_T_CONSOLE_MARKER_DESIGN.md` | `live/operator_console.py`, `live/structure_console.py`, `live/pool_board.py`, `live/structure_publish.py`, `live/heartbeat.py` | files present, wired in `run_operator.py`; console mode `event` default | **PARTIAL** | Boards/log streaming exist; the MQL5 watchdog **chart-attach** remains GUI-blocked (`V1_1_RUNTIME_BASELINE_FREEZE.md` §5) and no chart-overlay proof exists. |
| N | TP provenance coverage across entry paths | §21b "TP = first valid swing", dual fallback | `pipeline_bridge.structural_tp_target` called from adapter only | `pipeline_adapter.py:448`; **absent** in `product_menu_mtf.py:999-1002` | **ABSENT** | Silent: no doc, comment or test states that menu confirmations are fallback-only. Consequence: O5's 8/11 structural share describes the seek book, not the menu book; on the menu path structural share is structurally 0%. |

**Counts:** ALIGNED **7** · PARTIAL **5** · DRIFT **1** · ABSENT **1** ·
DEFERRED (documented, expected) **3** — news calendar (§11), boundary-sweep emitter (§2
Rule 5), watchdog chart-attach.

---

## 3. Silent absences (registered or implied, never fed)

1. **Structural TP on the menu path** (row N) — the only genuinely *undocumented* absence
   found. `structural_target` is never computed there, though the menu's POIs carry the
   same §19 swing state the adapter uses.
2. **`sweep_level` on any candidate** — `candidate_from_route` builds a `CandidateEntry`
   without it, so `RiskEngine`'s §28.6 sweep guard (`risk/sweep_guard.py`) and
   `SweepGuard` state updates can never fire from a pipeline candidate. The contract calls
   this DEFERRED; the code makes it *unreachable*, which is a stronger statement than the
   document makes.
3. **Trigger D without a volume column** — the frozen confirmation is volume-based; a
   zero/absent volume series disables D with no reason token surfaced to the console.
4. **M8's M15 tier** — §4b adds M15 to the POI inventory, and the menu has an M15 tier,
   but M8's own `HTF_TIMEFRAMES` remains `(W1, D1, H4)`, so M15 POIs are only ever generic
   M1–M7 detections. Consistent with §21 (M8 = HTF only); flagged because "M15 in the
   inventory" is easy to misread as "M15 M8 zones".
5. **News calendar / `spread_price`** — documented DEFERRED / operator-supplied; shipped
   configs stay diagnostic.

**Known accepted residuals** (unchanged by this audit): segment boundaries in the frozen
windows; n≈11 fills; `product_menu_mtf.py` recovered from a corruption event with no
byte-parity claim; HTF live depth 300 bars; cold start anchors to the latest bar.

**O1–O5 remain CLOSED status-quo.** Nothing in this audit is evidence to reopen them: the
one drift found is about *which law the evidence was gathered under*, not about whether
C3, upstream-only sweep, first-armed dedup, ATR SL or dual TP are right.

---

## 4. Ranked observations (observation only — no fixes in this engagement)

| Rank | Item | Why it matters for PFE-2 | Link |
|---|---|---|---|
| **P0-1** | Research composition runs seek only; live `PRODUCT_V1` runs menu + seek | A 6m run on today's research path measures a machine the product does not fully ship — the "wrong machine" failure mode | L |
| **P0-2** | Menu confirmations never receive a structural target (silent) | §21b's headline TP rule is false on the default live path; O5's structural share is path-specific | N, K |
| **P1-1** | §28.6 sweep guard unreachable from pipeline candidates | A locked risk gate is inert; either feed it or record it as unreachable | B |
| **P1-2** | Trigger D volume dependency has no diagnostic | A–F coverage silently shrinks to A–C/E–F on volume-less feeds | G |
| **P1-3** | Contract §1 vs POLICY doc rule 6 unreconciled | Two "product laws" in `00_LOCKED`; future agents will pick one at random | L |
| **P2-1** | Pillar 3 naming (A5) not carried into code | Expert reading friction only | E |
| **P2-2** | Watchdog chart-attach / console overlay unproven | Ops fidelity, not strategy | M |
| **P2-3** | News calendar / boundary-sweep emitter | Already documented deferred; no action implied | — |

No fix is proposed here. Any change to rows L/N would be a product ruling with its own
dated record, not a research side-effect.

---

## 5. What the 6-month backtest IS allowed to claim after this audit

- Funnel **volume and labelling** on the frozen product law: armed POIs, routes, C3
  rejects, placements, fills, duplicates suppressed, HTF batches, gaps — per window, per
  detection TF.
- **Path and structure evidence**: zone geometry, pillar paths, trigger mix, TP source mix,
  SL/MAE geometry, hold times — the same vocabulary O1–O5 used, at 6× the sample.
- **Determinism**: byte-identical artifacts across a dual run of the *same* composition.
- **Coverage statements** that name the law explicitly, e.g. "on the seek composition
  (adapter), 6m: …" or "on the menu composition (POLICY default), 6m: …".

## 6. What it must NOT claim

- Edge, expectancy, profitability, PF, "works", "validated" — at any n, and especially
  from one window.
- That the seek-composition run *is* the product, or that the menu-composition run
  supersedes the O1–O5 evidence (different law, not better law).
- Any comparison of the two compositions framed as a winner; they differ by construction
  (menu requires a sweep and consumes it; seek does not), so a volume difference is a
  definition, not a finding.
- Any re-litigation of O1–O5, any threshold/constant proposal, any 30-pip or 1:5 product
  rule.

---

## 7. Recommended PFE-2 window and composition

**Window (pre-registered):** load 2025-05-01; exec **2025-05-01 → 2025-10-31 UTC**
(six calendar months, the same data file `07_DATA/XAUUSD_M1.parquet`, same
`resample_multi`, same closed-bar prefix contract). One window, no segmentation, no
per-month cherry-picking; October re-appears only as a consistency check against the
frozen O1–O5 artifacts (funnel invariants: armed 441 / routes 149 / fills 11 for Oct).

**Composition — run BOTH, in this order, as separate named runs:**
- **PFE-2a — seek composition (comparable to O1–O5):** `PipelineAdapter` + `MultiTFProductRuntime`,
  no menu. Cheap (≈6.5 min per month at ~17 bars/s ⇒ budget hours, run background),
  byte-deterministic, directly continuous with the closed evidence.
- **PFE-2b — menu composition (POLICY default):** `ProductMenuEngine` driven per closed
  execution bar exactly as `LiveLoop._drive_menu_confirmation` does, winners queued into
  the same adapter and risk seam. This is the run that represents shipped `PRODUCT_V1`.
  Higher cost (menu evaluates A/D/F per tier window); still deterministic.

**Report shape:** one funnel table per composition, never merged; `tp_source` reported
per composition; a short "what each law produced" note with **no** cross-law ranking.

**Explicit non-goals for PFE-2:** no fix for P0-1/P0-2 (those are rulings, PFE-3 input at
most), no PnL analysis, no parameter search, no reopen of O1–O5.

---

## 8. Return block

```text
PFE1_STATUS: PASS
VERDICT: Mostly aligned; one DRIFT (research runs seek-only while live PRODUCT_V1 runs the sweep→confirmation menu) and one silent ABSENT (menu confirmations never get a structural TP)
ALIGNED_COUNT: 7
PARTIAL_COUNT: 5
DRIFT_COUNT: 1
ABSENT_COUNT: 1
TOP_P0: P0-1 seek-only research composition vs menu live law; P0-2 structural TP absent on menu path
REPORT_PATH: 06_RESEARCH/PFE1_PRODUCT_VS_INTENDED_AUDIT.md
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
HANDOFF_UPDATED: YES
NEXT_READY: PFE-2 frozen 6m product backtest prompt
```
