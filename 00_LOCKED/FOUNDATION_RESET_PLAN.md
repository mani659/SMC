# FOUNDATION FIDELITY RESET PLAN

**Status:** ACTIVE
**Date:** 2026-09-21
**Authority:** subordinate to `00_LOCKED/LOCKED_DECISIONS.md`; process peer with `00_LOCKED/POST_V1_PLAN_OF_ACTION.md`.
**Evidence base:** `06_RESEARCH/FOUNDATION_RESET_QA_PACK.md` (36-question fidelity audit) + `06_RESEARCH/FLOWCHART_CODE_EVIDENCE_MAP.md` + Phase C baseline + Track R closeout.

---

## 1. Problem statement

V1 does not express Revision 5: the traded book is an M1-only trend-chase engine dominated by Trigger F (86.6%) with sub-ATR stops inside noise and zero take-profit capability (`tp_price=None` hardwired), while the flagship multi-TF Model 8 is completely dormant — so optimizing any surviving sub-path polishes an emergent distortion instead of the intended multi-timeframe SMC architecture.

## 2. Immediate stops (binding)

- F-survivor optimization as the main track (timing discriminators, chase filtering) — PAUSED.
- Monte Carlo / walk-forward on the Phase C book (broken book — confidence intervals would be meaningless).
- Synthetic fixed-R TP search on the 761-trade book (Track R2 settled this: entries fail on location, not exit math).
- Demo P/L as strategy evidence (Phase D remains infrastructure proof only).

## 3. Lead Architect rulings (recorded verbatim — not debated)

| # | Ruling |
|---|--------|
| **R1 — M8** | WIRE HTF feed for the next measurement window. M8 must not remain silent by accident. (Formal scope-out rejected for FR-1.) |
| **R2 — Detection TF minimum for FR-1** | H4 + H1. D1 optional when stable; not required for FR-1 exit. |
| **R3 — Execution TF for FR-1** | M5 primary; M1 allowed as execution/trigger TF only. Detection must NOT run as M1-only detect+exec. |
| **R4 — TP policy for FR-2 (record now, implement later)** | structural target if available, else 4×ATR cap. No fixed-R search on the old Phase C book. |
| **R5 — SL buffer intent for FR-2 (record now)** | sweep extreme ± 0.3×ATR where stage/trigger defines structural stop; no silent zero-buffer-only path without documented exception. |
| **R6 — F-research resume** | only after FR-4 fidelity re-baseline scorecard on cascade + M8 observed. |

## 4. Phased work

- **FR-0: roles + this plan** — DONE after this prompt (role protocol file + this plan accepted).
- **FR-1: multi-TF cascade + M8 feed + acceptance tests** — COMPLETE 2026-09-21 (resample.py + multi_tf.py + 11 tests + smoke: H4/H1 wired, M8 emitted 12, alarm live, suite 607; per-bar loop integration residual). Next: FR-2.
- **FR-2: structural SL/TP routing** — COMPLETE 2026-09-21 (shared helper + F/A/D/E buffered stops, B/C exempt documented; structural-else-4×ATR routing; interim constants listed; 10 new tests + 3 updated; suite 617).
- **FR-3: zone/entry geometry + M4 fidelity** — COMPLETE 2026-09-21 (F containment gate, M4 EQH domain split, 4 new tests + decoy + 3 fixture updates; suite 622). Next: FR-4.
- **FR-3: zone/entry geometry + M4 fidelity** — persist and verify zone containment, QML geometry requirements, entry-at-documented-point checks.
- **FR-4: fidelity re-baseline** — COMPLETE 2026-09-21 (October M5 month; determinism pair byte-identical; 8 armed incl. 4 M8, 0 compliant routes explained by zone-gate binding per diag ablation; verdict YES_WITH_RESIDUALS). Next: Lead Architect acceptance decision on the Reset.
- **Parallel: Phase D ops only** — EXNESS Copy terminal infrastructure proof (EA attach, drill, stability); never strategy validation while cascade is non-compliant.

## 5. FR-1 exit criteria (hard)

- Detection consumes H4 **and** H1 series (not M1-only) — proven by per-TF detection breakdowns.
- Execution on M5 primary (M1 as execution/trigger TF only) relative to detection.
- M8 emits >0 POIs when HTF data present (or loud fail — silence must be impossible by accident).
- Funnel/report breaks down detections by TF (per-TF counts in every report).
- Alarm if single-TF detect+exec is the sole path (acceptance test fails closed on M1-only configuration).

## 6. Non-goals

- No threshold fishing (no tuning loops against any baseline).
- No F-timing / chase-discriminator work as main track (PAUSED per R6).
- No Monte Carlo yet (deferred until FR-4 book exists).
- No TP implementation before FR-2 (R4 recorded, not built).
- No MQL5 strategy logic, ever.

## 7. Success definition for "reset done"

Derived from §5 exit criteria + QA scorecard re-audit (no separate prior-plan text on file — this derivation, not a quotation): reset is done when (a) all FR-1 exit criteria hold on a fresh measurement window, (b) the QA fidelity scorecard re-run shows zero SILENT rows and no DRIFTED rows on cascade-critical nodes (multi-TF detection, M8, TP routing, SL buffers), (c) FR-2 structural SL/TP routing is implemented per R4/R5, and (d) the Lead Architect accepts the FR-4 re-baseline. Until then, no optimization track opens.

## 8. FR fill-regime policy (2026-09-22, R7+R8)

Lead Architect rulings R7+R8 close the FR-4b fill-regime finding (routing healthy, fills 0/5). Implemented in `smc/risk/fill_regime_policy.py` (single source; backtest + paper import it):

- **R7 — place guard:** a risk-accepted candidate is NOT placed when its **market reference (bar close at place time)** sits outside the routed POI zone beyond the existing FR-3 band (`ZONE_REFINEMENT_ATR × ATR`; no new constant). Skip is machine-readable (`blocked_by=skip_place_far_from_zone`) and **retryable** — the one-shot burns only on accepted placement, matching news/session block semantics. Fails closed (no place) when zone is locatable and price is far; dormant (allow) when zone bounds are missing so M3-seam candidates keep flowing.
- **R8 — HTF resting bars:** pending lifetime = `rest_bars_for(detection_tf, is_m8)` in M5-bar units, matching the §23 inclusive convention (order placed on bar N is fill-eligible N+1..N+rest−1): M30/M5/M1/unknown-LTF → execution-TF §23 default (12 on M5); H1 → 36; H4/M8/D1 → 48. Never silently shortened below the execution TF's own §23 default. Give-up (20) stays an independent hard backstop — the book cancels at whichever threshold hits first; HTF rest is never raised by it.
- **Provenance:** `CandidateEntry`/`PendingOrder` carry `detection_tf` + `is_m8` (bridge pass-through); `_TrackedPending` mirrors on the paper path.
- **Smoke (FR-4b window, frozen config):** 10 R7 skips, 0 places, 0 fills — every FR-4b order's market close was +14.65 to +165.50 beyond the zone vs a 1.73–3.84 band, so the September-runaway class is now stopped at place time. R8 was separately proven live: the pre-correction smoke filled the first trade in the chain (zone-high re-anchor, BE-stop exit).
- **R9 — place-on-reentry intent (2026-09-22, supersedes the R7 silent drop):** an R7-skipped candidate arms a `PlaceIntent` (full accepted placement frozen at signal time); when the market re-enters the band or touches the limit within an R8-sized clock from signal, the pending order places with the REMAINING bars. Design lock: `00_LOCKED/R9_PLACE_ON_REENTRY_DESIGN.md` (§23 clock parity; DOA boundary — `remaining ≥ 3` or never placed; one intent per route, clock never refreshed; candidates-before-intents bar order so a same-bar re-proposal never doubles). Smoke (frozen FR-4b window): 5 intents armed, 4 expired naturally, **1 placed on re-entry → FILLED at the on-zone limit → BE-managed → closed +0.07** — the first complete arm→reentry→fill→manage→close chain under frozen rules. Note: `06_RESEARCH/R9_PLACE_ON_REENTRY_NOTE.md`.
- **Residual for Architect:** FR-3.1's zone-edge limit plus R7's market guard means fills now require the market to be near the zone at place time — a design question about limit placement/timing, not a threshold issue. R9 answers it by deferral: fills now also occur on later re-entry (proof: the poi-014750 chain); trend-runaway POIs (September class) still never re-enter and are now counted waits, not silent drops.

## 9. Next action

The Foundation Reset research path is **COMPLETE** (FR-1 → FR-4 → FR-4b → forensic → R7/R8 → R9, all PASS). The remaining product gap — wiring MultiTF into live/paper — is now closed by **Phase 0 + Phase 1 C1** (2026-09-23; contract `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md`, shared seam `smc/orchestration/multi_tf_runtime.py`; suite 698).

**Next action = Phase 2 — layer/pillar CONTRACT tests** (fixtures + rates; no long expectancy run). See the "Product completion path" section in `00_LOCKED/POST_V1_ACTIVE_TODO.md`. This plan is retained as the historical rulings record (R1–R9, §8); it is no longer the active headline program (that is now Product Runtime Unification, Phase 0–4).

**UPDATE 2026-09-24 — V1.1 RUNTIME BASELINE FROZEN:** the implementation baseline (Choice 1 Phase 0→4 + Track A + Phase D HTF probe) is recorded in `00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md`; rulings R1–R9 (§8) stand as frozen history. Reopening any of them, or editing locked_constants / thresholds, requires a dated ruling in the freeze file or `POST_V1_PLAN_OF_ACTION.md`.
