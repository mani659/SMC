# COUPLING POLICY DESIGN — LOCKED DESIGN NOTE (docs only)

**Date:** 2026-10-28 · **Authority:** Lead Architect "COUPLING POLICY DESIGN-LOCK"
**Status:** DESIGN NOTE ONLY — ratified implementation engagement still required before any code.
`LOGIC_CHANGED: NO` · production strategy logic untouched · `locked_constants.py` diff: **EMPTY**.

> **OBSERVATION / DESIGN ONLY.** Nothing here is expectancy, an edge claim, or a
> promotion argument. Track A row counts are density observations, not evidence
> (Track A report §5). This note locks the CONTRACT the implementation must
> follow; it does not implement it.

---

## 1. Problem statement

The Architecture Alignment Audit (`06_RESEARCH/ARCHITECTURE_ALIGNMENT_AUDIT.md`,
"mixed alignment", §B4: "Locked coupling policy — **NO**"; §E overall path
integrity 3/5) identified the single largest misalignment: **event-level
observation and coupling are split across isolated tools** — dense ungated
events are offline-only, while live/paper product logic sees POIs/gates with no
locked generalized event-to-plan policy.

Three evidence poles, all mandatory inputs:

| Evidence | Path | Fact |
|---|---|---|
| Gated P1 too sparse | `06_RESEARCH/P1_OFFLINE_REPLAY_REPORT.md` (Track B + 2026-10-26 order-fix amendment) | **1 POI-linked sweep / 0 confirms → 0 episodes → 0 candidates** on the frozen 6m window; genuine sparsity of the H4-POI-only arm rule (sweep of a tracked M8 POI extreme only, once in 804 H4 bars) |
| Ungated observer too dense | `06_RESEARCH/TRACK_A_SWEEP_LEDGER_REPORT.md` | 12,454 sweeps in the frozen 3m window; Def-B (every FVG bound + every LAST_OPPOSITE wick bound) = 9,180 of 12,454 rows — density, **not** quality |
| Sample quality split | Architect Track A score (2026-10-28, 6-chart sample) | **PASS — 3 CORRECT / 3 PARTIAL / 0 WRONG; both Definition-A charts CORRECT**; Definition-B mixed CORRECT/PARTIAL (rule-true, often thin / FVG-edge), consistent with the Phase 0 pattern (`06_RESEARCH/PHASE0_EVENT_SCORE_SHEET.md`: H4 structure the cleanest family; M5/FVG tiers noisy observations) |

Supporting ledgers: `06_RESEARCH/UNGATED_EVENT_LEDGER_H4_REPORT.md` (H4: BOS 9,
CHOCH 4, OB-obs 9, FVG 87; 402 closed bars) and
`06_RESEARCH/UNGATED_EVENT_LEDGER_P1_REPORT.md` (H1 BOS 38 / CHOCH 22 / OB 38 /
FVG 328; M5 much denser; 1,488 H1 / 17,840 M5 closed bars).

**Therefore:** the coupling policy must widen the arm universe (POI extremes
alone are too sparse) while excluding raw Def-B density, keep the locked sweep
semantics verbatim, and feed ONE explicit setup/plan through the *existing*
candidate → risk → order seam.

```
eligible level → sweep/interaction → LTF confirmation → candidate plan
```

## 2. Eligible level families — decision table

Matches Architect constraint 1 verbatim (**IN default** vs **OUT of product
default**):

| # | Level family | Source machinery | Product default | Rationale |
|---|---|---|---|---|
| 1 | **Definition A — structural §18/§19 swing highs/lows** (`STRUCTURAL_SWING`) | `smc.detection.structural_swing_detector.detect_swings` via the ungated ledger machinery (Track A Def-A; TF-native N, causal `known_at`) | **IN** | Scored sample: A correct on H4 **and** H1; cleanest structural evidence family; sparse enough to stay meaningful |
| 2 | **Tracked product POI extremes** (M8 / validated POI path, armed/tracked by the product runtime) | existing detection → arm → tracked-set path (`multi_tf_runtime`, `policy_mtf_h4` refresh pattern) | **IN** | Existing product identity/freshness machinery; reuse keeps identity, freshness, and §5 lifecycle semantics |
| 3 | **Definition B raw density** — every FVG zone bound (`POI_LEVEL`) and every `LAST_OPPOSITE_BEFORE_BOS` wick bound (`ORDER_BLOCK_BOUNDARY`) | Track A Def-B (`06_RESEARCH/TRACK_A_SWEEP_LEDGER_REPORT.md` §2) | **OUT — RESEARCH annotation only** | 9,180 rows / 3m ≈ micro-scale; sample scored PARTIAL-leaning; remains research annotation unless a **later dated Architect ruling promotes a named subset** |

**Hard boundaries (locked):**
- `LAST_OPPOSITE_BEFORE_BOS` is **NOT** a product order block (Phase 0 boundary, retained).
- M5 FVG/BOS stay **noisy observation tiers**, not product signals (Phase 0 boundary, retained).
- B promotion requires a *named, dated ruling* naming the promoted subset explicitly — no silent widening, no "counts" argument.
- Eligible levels are frozen per this table; eligible swing levels are *unique by pivot identity* `(source_tf, pivot_index, side)`.

## 3. Sweep / interaction rule (detector path + causality)

**Detector:** `smc.detection.sweep_detector.detect_sweep/detect_sweeps` ONLY —
LOCKED_DECISIONS §2 wick pierces the level, body closes back; a close beyond is
a breakout, not a sweep; the `formed_at` bound prevents a level sweeping at its
forming bar; **one sweep per level**; no new pierce tolerances; no re-arm
invention; no subtypes.

**Causality (reuse, unchanged from Track A):**
- POI-tier levels: known/tracked per the existing tracked-set semantics; the sweep check must run against the tracked set **before** the detection refresh can retire a POI (the 2026-10-26 P1 order-fix ruling applies verbatim — a bar may not erase its own arming observation through refresh).
- Swing-tier levels: knowable at `known_at = max(pivot_index + N, §19 confirmed_index)` (§18/§19, TF-native `N_BAR_HTF=5` on H4/H1); nothing sweeps before knowability.
- A sweep is recorded **only** after the source bar is CLOSED; wall-clock/M1-count clocks are banned (P1/COMPLEX convention: detection-TF bar clocks).

## 4. Confirmation TFs + allowed trigger families

- **Mode A (current product frame):** after a qualifying closed H4 **and/or** H1 sweep, seek closed-bar confirmation on **M5** (M5 is the canonical execution series per `PRODUCT_RUNTIME_CONTRACT.md` §1).
- **Allowed confirm families (v1):** the subset the codebase already routes in the multi-TF confirmation policy — **A (CHOCH), D (Two-Bar Reversal), F (BOS+OB)** on closed M5 bars, exactly the P1 confirm set.
  - Trigger geometry: existing `smc/triggers/` bodies unchanged; **no new trigger types in this design**.
- **M15: NOT added.** P1's M15 stream exists only because the locked policy table lists it for the H4 tier; adding tiers requires a **dated PROPOSED + justification** in a ruling — non-goal here (see §9).
- H4 and H1 sweeps are independent episodes (per-TF source events); an H1 sweep does not cancel an H4 episode of the same level family, but the §6 one-shot identity within each (level, direction, sweep event) still applies.

## 5. Timing: arm, seek window, expiry — named constants only

| Phase | Rule | Constant (existing) |
|---|---|---|
| Arm | Sweep confirmed on the closed source bar → episode opens immediately (no grace, no lag) | §2 detector (no new number) |
| Seek window per trigger | Trigger may confirm only inside its own §24 window, counted from the trigger's own `completion_index` on M5 | `window_bars_for(trigger)` → `TRIGGER_A_EXPIRY=20`, `TRIGGER_D_EXPIRY=1`, `TRIGGER_F_EXPIRY=1` |
| Episode-wide expiry (**PROPOSED**) | No confirming trigger fired → episode expires at **sweep-bar + `poi_give_up_bars()` bars on the SOURCE TF** (H4 or H1), mirroring the locked policy table's "20 bars on detection TF" and the pipeline adapter's `arm_bar + poi_give_up_bars()` give-up clock | `poi_give_up_bars()` = `TRIGGER_A_EXPIRY` = 20; the *source-TF clock* application is PROPOSED (uses an existing constant, no new number) |
| Unfilled order expiry | Once a candidate is placed, §23 owns it (unchanged, state machine) | `M5_EXPIRY_BARS=12` / `M1_EXPIRY_BARS=30` |
| Terminal states | routed (candidate emitted) / expired / violated (level family invalidated — e.g. §19 structural invalidation wins over the clock, as in COMPLEX/DUMB) | (no new constants) |

**Any timing number not listed above = PROPOSED and requires a dated ruling.**
Trigger windows may only shorten the episode horizon, never extend it (§24 spirit, `trigger_expiry.py` docstring).

## 6. One-shot identity + multi-confirm precedence

- **Episode identity (deterministic, documented):**
  `(symbol, source_tf, level_family, level_id, direction, sweep_close_timestamp)`.
  - `level_family` ∈ {`swing` (Def-A), `poi` (tracked POI extreme)}.
  - `level_id`: swing → `(pivot_index, side)`; POI → existing POI id.
  - Identity suppression boundary: **identical identity only** — a later, distinct
    sweep (distinct timestamp or level) is a valid later episode; nothing is
    merged or dropped because direction/source matches (same anti-merge rule
    as `smc/orchestration/sweep_episode_coordinator.py` and the 2025-10-25
    sweep-episodes design; coordination of *concurrent* episodes is out of v1
    scope here — episodes are independent until they emit ≤1 plan each).
- **One-shot:** exactly one live plan per `(level, direction, sweep event)` until
  terminal. A won route consumes the episode AND the level's arming freshness for
  the episode horizon; `EXPIRED` leaves the level eligible to re-arm on a **fresh**
  sweep (distinct timestamp), matching P1's one-shot semantics.
- **Precedence when multiple triggers confirm the same episode:** **chronological
  first-valid wins** on closed M5 bars; an exact same-instant tie resolves by the
  existing trigger-router tie-break spirit (stable route id; M5 is the single
  confirm TF in Mode A, so no finer-TF arbitration exists in v1). First-win
  arbitration consumes the episode.

## 7. Output contract: CoupledSetup → existing candidate seam

`CoupledSetup` is a **data contract**, not a new runtime. Fields map 1:1 onto the
existing `CandidateEntry` (`04_SRC/smc/backtest/runner.py:86`) and are built via
`pipeline_bridge.candidate_from_route(route, ...)` whenever a real POI+signal
route exists (POI tier). Swing-tier episodes have no POI; their candidate is
constructed directly as a `CandidateEntry` at the **same** seam — no parallel
risk/order stack, no second sizing path.

| CoupledSetup field | CandidateEntry target | Source rule |
|---|---|---|
| `direction` | `direction` | sweep-side label of the swept level (BSL→SHORT / SSL→LONG) **validated by the winning trigger's own direction** |
| `entry_price` | `entry_price` | winning signal's contract price (limit contract frozen, §10 — never market) |
| `sl_price` | `sl_price` | `stop_reference` of the winning trigger / POI zone extreme; swing tier: the swept level's family-true invalidation reference (existing trigger geometry, no new math) |
| `tp_price` | `tp_price` | `resolve_take_profit` (structural else 4×ATR) — unchanged shared function |
| `score` | `score` | POI tier: §1 confluence tag count via route (unchanged). **Swing tier: PROPOSED-RATIFICATION ITEM** — no §1 tag model exists for bare swings; until ruled, swing-tier candidates carry the documented conservative default (`score=0`) rather than an invented quality number |
| `sweep_level` | `sweep_level` | the locked detector's swept `level.level` |
| `episode id` | `route_id` + `signal_data_json` | identity string `coupled_policy {tier, source_tf, confirm_tf, trigger, level_family, level_id, direction, route_id, episode_id, sweep_ts, swept_level}` (P1's `p1_policy{...}` pattern) |
| `pillar_path` | `pillar_path` | `COUPLED_MTF` (proposed name; see §8) |
| `zone_low/high` | `zone_low`,`zone_high` | POI tier: route POI zone; swing tier: `None` (never invented) |
| `entry_anchor`, `tp_source`, `disp_*` | same fields | pass-through of existing bridge provenance; `None` = unknown, never invented |
| `fvg_provider` | `fvg_provider` | bound by the existing bridge only (F-route) as today |

Invariants: the runner/risk/fill/trigger decision logic reads nothing new;
identity columns are logging/audit only (same provenance discipline as `entry_anchor`).

## 8. Target runtime path (named) — and what is NOT changed

**Primary target (named once):** documented addon / strategy mode **`COUPLED_MTF`** —
if later ratified for implementation, it would follow the `PolicyMtfH4Engine`
pattern (`smc/orchestration/policy_mtf_h4.py`): a closed-bar feed + episode
coordinator that emits candidates through the EXISTING
`candidate_from_route → BacktestRunner._process_entries / RiskEngine →
OrderManager` seam and the PaperRunner/LiveLoop candidate insertion points —
never a parallel risk/order stack and never a silent rewrite of defaults.

**Explicitly unchanged until a separate implementation engagement:**
- `COMPLEX` remains the frozen default `strategy_mode` (audited fact:
  `OperatorConfig.strategy_mode` defaults to `COMPLEX`).
- `config/live_demo.json` keeps selecting `DUMB_MTF_H4` — **this design does NOT
  claim the demo runs coupled policy.**
- `POLICY_MTF_H4` remains opt-in, byte-identical.
- DUMB-MTF (`smc/dumb/mtf*`) remains untouched comparison/selected-demo path.
- Observer ledgers remain research-only artifacts (no observer→risk routing).

## 9. Explicit non-goals

1. **No Mode B** (M15/M30 mid-TF scalp; stub `06_RESEARCH/MODE_B_MID_TF_SCALPING_STUB.md` stays a stub) in v1.
2. **No Track A row counts as promotion evidence** (density observations live in the Track A report §5 and are never cited as edge/hit-rate here).
3. **No expert-pack or paper P/L as design proof** — design proof is the ratification checklist (§11) + tests (§10).
4. **No merging ungated observer events into the risk path** inside this design doc beyond specifying the future seam (§7/§8).
5. No M15/M30/D1 tier expansion (§4); no new trigger types; no new timing numbers (§5); no B-subset promotion (§2); no locked_constants edits; no live config edits.

## 10. Test plan (fixture list only — no implementation in this engagement)

| Fixture | Must prove |
|---|---|
| `F1 synthetic_h4_swing_sweep_m5_confirm` | closed H4 swing-high sweep (locked detector semantics) → M5 trigger-D confirm → candidate at the seam with `COUPLED_MTF` identity intact |
| `F2 poi_tier_uses_existing_route` | tracked-POI sweep reuses `candidate_from_route` (zone fields populated; §1 score carried) |
| `F3 sweep_after_known_at_only` | nothing sweeps before `known_at`; POI tier honors the refresh-vs-check order rule (2026-10-26) |
| `F4 one_shot_identity_no_duplicates` | identical `(source_tf, level_id, direction, sweep_ts)` suppressed; distinct sweep timestamp re-arms |
| `F5 first_valid_precedence` | two M5 trigger signals, different completion bars/arbitrary ties → chronological first-valid wins; episode consumed |
| `F6 expiry_on_source_tf_clock` | no trigger before sweep_src+20 bars → EXPIRED; fresh sweep re-arms |
| `F7 breakout_is_not_sweep` | close-beyond level emits nothing (locked §2) |
| `F8 def_b_never_arms` | FVG-bound / OB-wick sweeps in scope produce research rows only; zero candidates |
| `F9 m15_not_seeking` | no M15 confirmation stream exists in Mode A v1 |
| `F10 same_level_guard_and_sweep_guard_applied` | existing `SAME_LEVEL_GUARD_*` / `SWEEP_GUARD_*` frozen thresholds still enforced downstream |

## 11. Architect ratification checklist (yes/no)

| # | Item | Y/N |
|---|---|---|
| 1 | Eligible level table (§2) matches Architect IN/OUT default (A + tracked POI in; B research-default-out) | ☐ |
| 2 | Locked detector reuse (§3) with zero semantic edits accepted | ☐ |
| 3 | Confirm M5-only + A/D/F families (§4) accepted for Mode A | ☐ |
| 4 | Source-TF expiry clock via `poi_give_up_bars()` (§5, PROPOSED item) accepted | ☐ |
| 5 | Episode identity + one-shot + first-valid precedence (§6) accepted | ☐ |
| 6 | CoupledSetup → `CandidateEntry` mapping incl. the **swing-tier score default** ratification item (§7) accepted | ☐ |
| 7 | `COUPLED_MTF` target name + "COMPLEX/DUMB_MTF_H4/POLICY_MTF_H4 unchanged" boundary (§8) accepted | ☐ |
| 8 | Non-goals (§9) accepted | ☐ |
| 9 | Test fixture list (§10) accepted as the future implementation's acceptance suite | ☐ |
| 10 | Implementation engagement may be scheduled ONLY after all-yes ratification | ☐ |

---

### Return block

```text
COUPLING_DESIGN_STATUS: PASS
ELIGIBLE_LEVELS: A+POI in; B research-default-out
CONFIRM_TFS: M5 closed bars only (M15 NOT added in this design)
TRIGGER_FAMILIES: A/D/F (existing, no new types)
TARGET_PATH: COUPLED_MTF (documented addon/strategy_mode; COMPLEX + DUMB_MTF_H4 + POLICY_MTF_H4 unchanged)
TRACK_A_SCORE_CITED: YES (3 CORRECT / 3 PARTIAL / 0 WRONG; both Def-A charts CORRECT)
LOGIC_CHANGED: NO
NOTE_PATH: 06_RESEARCH/COUPLING_POLICY_DESIGN.md
LOCKED_CONSTANTS_DIFF: empty
HANDOFF_UPDATED: YES
NEXT_READY: Architect ratify | revise design
```
