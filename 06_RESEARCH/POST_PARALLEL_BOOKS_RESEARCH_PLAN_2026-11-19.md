# POST-PARALLEL-BOOKS — RESEARCH & VALIDATION PLAN (2026-11-19)

**Status:** PROPOSED — needs the Architect's ratification before any step starts.
**Authority chain:** `PRODUCT_RUNTIME_CONTRACT.md` §11, `RESEARCH_PROOF_REGISTER_2026-10.md`
(PROVEN / TEXTURE_ONLY / SUPERSEDED), `LAYERED_FIDELITY_PLAN.md` (no phase starts before the
prior one has a written PASS/FAIL), `POST_V1_ACTIVE_TODO.md` (end-of-task git rule).
**Inputs:** `PROJECT_WIDE_AUDIT_2026-11-19.md` (what passed/failed and why),
`PARALLEL_BOOKS_FULL_BT_INFLIGHT.md` (the run in flight), `PARALLEL_BOOKS_DESIGN_IMPL_AUDIT.md`
(1 critical + 5 major, M-4 still open).
**Bans carried forward:** no expectancy/edge claim; no threshold movement to buy n; no
`locked_constants` edit outside a dated lock; `D` never enabled; no ML; no demo P/L as
evidence; no continuous re-run of a finished book.

---

## 0. The one sentence this plan exists to serve

*The product's scarcity is admission-gated (measured), the parallel-books run is the only
lever with a measured 3–5× fill effect (R1), and nothing downstream — entry representation,
OOS, paper, promotion — can be judged until the book has enough fills to be measurable.*

So the order is: **close the admission decision → re-baseline the book at the new density →
then, and only then, spend on strategy questions.** Not the reverse.

---

## 1. State on the day the backtest exits

| Fact | Value | Consequence for this plan |
|---|---|---|
| Runs done | 12/24 at last check | Remaining ≈12 runs; pace ≈1.5 h/run (estimate only, not a promise) |
| Verdict | no `verdict.json`, no `EXIT_CODE.txt` | **Nothing downstream is decided until both exist** |
| Gates the run already enforces | tag purity, 0 unattributed, 0 double-lots, `poi_outside_books == 0`, all five books exercised, per-segment anchor vs product_1y | Pass/fail is structural — it does **not** depend on PnL |
| Known open defect | **M-4** — risk blocks counted by reason only, not by book | Blocks the *shared-envelope* claim, not the fill census |
| Known instrument limit | Segmented tiling (12 months), armed counts not summable | Per-segment reading only; no year-total "armed" |
| Suite | 1,555 passed / 7 skipped (last full run) | Any code step must re-establish this |
| Production defaults | untouched; `parallel_books = ()` | Nothing has been promoted; this plan is what would change that |

---

## 2. Stage ladder — priority order and why

Each stage has: **why it is here** (dependency), **what it answers**, **entry precondition**,
**exit gate**, and **what happens on failure**. A stage never starts on a hunch; it starts on
the previous gate's written PASS.

### S0 — Verdict intake (hours, not days)

- **Why first:** the run's result can invalidate the rest of the ordering, and re-running a
  finished book is banned.
- **Do:** run `parallel_books_full_bt_status.py`; if complete, read `verdict.json` +
  `EXIT_CODE.txt` + per-run `summary.json`; write `PARALLEL_BOOKS_FULL_BT_REPORT.md` with
  per-book fills, trigger mix (must be `{T:100%}` per book), dedupe counts, anchor, runtime.
- **Gate G0:** `EXIT_CODE.txt == 0` **and** every verdict check true **and** report committed.
- **On failure:** report PARTIAL with the exact first failing check; resume from `.done`; never
  re-run finished segments; never relax a check to get green.

### S1 — Attribution closeout (M-4 + audit residuals)

- **Why here:** S2's ruling is about a *shared risk envelope*. Without per-book attribution you
  cannot say which book hit the breaker, so you cannot rule on carrying five books in one
  account. It is also cheap (stamp `book_id` on the risk verdict event + one counter test).
- **Do:** stamp `book_id` on `blocked_by_reason` events for book-stamped candidates; add a
  regression test; re-run a short slice **only** to prove the counter appears (not the year).
- **Gate G1:** suite green; per-book block counters non-zero where blocks occur; `trades.csv`
  on the proving slice byte-identical to the pre-change capture (attribution must not alter
  decisions).
- **On failure:** if stamping changes any decision, stop — the risk path is not pure and that
  is a finding of its own.

### S2 — The admission ruling (decision, not research)

- **Why here:** it is the project's central open question and it is already measured. Every
  later stage's n depends on the answer.
- **Question:** does the product carry **five dedicated books** (F,B,C,E,A), **one product
  menu**, or something in between — and if books, in which posture (research default-off /
  demo / live)?
- **Decision rule — structural only, never PnL:**
  1. S0 gates all true;
  2. S1 attribution present;
  3. runtime budget stated and measured (R-G: two books measured 1.34× a single-tag sum;
     five books is unproven — quote the measured ratio, do not extrapolate silently);
  4. no book's result depends on a cross-tag leak, a double-lot, or an unattributed fill;
  5. the year's per-book fill distribution is reported with denominators.
- **Gate G2:** a dated ruling block naming (a) the book set, (b) the posture, (c) the runtime
  evidence, (d) what would reopen it.
- **On failure (a book starved / a gate trips):** do **not** widen the gate. Record the
  finding; the counterfactual that a book is confirmable but did not fill is a *measurement*,
  not a licence.

### S3 — Re-baseline the book at the new density (the calibration run)

- **Why here:** every downstream question (entry representation, OOS, paper) is n-starved at
  3–11 fills/window. If S2 adds books, the book's density changes and **all old baselines
  become the wrong comparison point**.
- **Do:** one frozen-window census of the *ratified* composition — same window as product_1y
  (exec 2024-11-01 → 2025-10-31), dual-run, segmented tiling, one-story guard ON, costs per
  the V1 ledger. Report: fills by book, by trigger, by detection TF, exits, `tp_source`,
  duplicate winners dropped, per-segment determinism.
- **Gate G3:** determinism PASS every segment; fills reconcile exactly (segment sum = merged
  sum, unique timestamps); every fill attributed to a book + trigger + tier; no counter left
  aggregate-only.
- **On failure:** segmentation boundary losses or non-reconciling counters stop the run — fix
  the instrument first, never the strategy.
- **Why not continuous:** menu bookkeeping is quadratic (26.1 → 2.5 bars/s by bar 6,000).
  That is S5's job, not a reason to shrink the window silently here.

### S4 — The entry-representation program (the only open *strategy* question)

- **Why here, not earlier:** it is the one question the audit could not close — near-miss
  (`PLACEMENT_NOT_PRIMARY`) points at entry representation, and every candidate representation
  tried so far has failed (`STRUCT_UNAVAILABLE` 45.1%; broadened measure 100%
  `representation_coverage_failure`). It needs S3's n to be judgeable, and it needs a
  pre-registered design, not another probe.
- **Do (in this order, each with its own written PASS/FAIL):**
  1. **Anatomy pack first, no new rule:** characterise the fills that exist — signed distance
     from zone edge at fill, bars from impulse to fill, MFE/MAE in ATR before exit, time-to-
     extreme. Pure description, no candidate rule.
  2. **State the representation hypothesis in one sentence** (e.g. "entry should be placed at
     the post-confirmation retest rather than the zone edge"), with a **kill criterion
     written before the run** and the population fixed.
  3. **One offline counterfactual** on frozen artifacts (no product code), dual-run, same
     fill semantics as near-miss, disclosed BE/cost treatment.
  4. **Only if it survives** (pre-registered threshold met): a dated design, then a single-seam
     implementation behind a dead-by-default flag, then a bounded A/B.
- **Gate G4:** the counterfactual's kill criteria are stated in the note **before** the result
  table, and the verdict is one of the pre-registered strings. INCONCLUSIVE is an acceptable
  outcome and requires no follow-up action.
- **On failure:** the search stops at the failed hypothesis. No second candidate is invented
  in the same pack — a new hypothesis is a new pre-registered pack.

### S5 — Instrument investment: menu performance (needs explicit authorization)

- **Why here:** it is production code, it is the only thing that unblocks a *continuous* year,
  a 5-year census, and any walk-forward/OOS. It is deliberately late because it buys
  measurement, not edge, and because doing it earlier would pre-empt S2–S4 with a slow,
  unratified book.
- **Do:** profile the quadratic menu bookkeeping (full-series swing re-detection on M1/M5
  verify streams per bar + armed×episode scans); propose an exact-equivalence patch with a
  byte-identity proof, in the style of `series_state.py` and its equivalence test.
- **Gate G5:** 2-week slice, patch vs baseline `trades.csv` **byte-identical**; throughput
  measured (bars/s at bar 6,000 and 20,000); suite green; then, and only then, one continuous
  month.
- **On failure:** no partial patch ships. A "close enough" rewrite here would corrupt every
  later comparison.

### S6 — Out-of-sample discipline (the gate nobody has passed yet)

- **Why here:** every number in this repo is in-sample on one instrument and one feed. A
  frozen law with a measured density is finally testable OOS.
- **Do:** declared holdout partition (time-based, not random), frozen before the run; the
  ratified composition run on the holdout with **no** parameter change; report the same
  census counters, not a PnL claim. Then walk-forward and a block bootstrap on the frozen
  rule set — as diagnostics of stability, not as an edge proof.
- **Gate G6:** holdout partition and metrics frozen in a note before the run; results reported
  whatever they are; no rule changed between in-sample and holdout.
- **On failure:** if the holdout cannot be run (data/perf), that is recorded as a limitation —
  not skipped silently.

### S7 — Paper/demo soak (ops gates)

- **Why here:** code correctness and measurement plausibility are not the same as "runs
  unattended without hurting itself".
- **Do:** EA chart-attach; stale-heartbeat flatten drill (deliberately kill the heartbeat);
  two-week bounded paper session on the ratified composition; reconcile every ticket against
  the backtest's own decision trail.
- **Gate G7:** attach + drill observed on the GUI; paper session runs the full two weeks with
  0 unattributed tickets, 0 duplicate plans, 0 boundary-state warnings; every ticket traceable
  to a story.
- **On failure:** ops fixes only; no strategy change is allowed to "fix" an ops symptom.

### S8 — Promotion ruling (the only stage that touches defaults)

- **Why last:** defaults are the one thing that cannot be cheaply undone once testers run them.
- **Gate G8:** G0–G7 all PASS or explicitly waived in writing; installer rebuilt with a
  version bump; defaults changed only in the ruling's named keys; a rollback line exists.
- **Never:** promote on PnL; promote a flag whose measurement is INCONCLUSIVE; leave a
  dead-by-default flag undocumented.

---

## 3. Verdict branches at S0 (decide once, in writing)

| `verdict.json` outcome | What it licenses | What it forbids |
|---|---|---|
| **PASS** — all gates, all five books exercised, anchor intact, 0 double-lots | S1 → S2 with five books as the candidate | Treating fills as quality; skipping S3 |
| **PASS but one book starved** (e.g. E < a handful of fills despite coverage) | S1 → S2 with a *named* exclusion and its counterfactual recorded | Widening E's gate to make it fill; claiming "E does not work" |
| **FAIL — `CROSS_TAG_LEAK` / unattributed / double-lot** | S1 only; the books layer is not promotable | Any promotion discussion until the leak is fixed and re-measured |
| **FAIL — anchor loss > 0** | S1; the harness is suspect, not the books | Reading per-book numbers as evidence |
| **FAIL — `poi_outside_books != 0`** | S1; tier coverage is broken (the M-3 class of defect) | Any composition claim |
| **DEAD / incomplete** | resume from `.done`; report the first failing run | Re-running finished segments; changing the harness mid-resume |

---

## 4. How future research must be done (the doctrine this project earned the hard way)

The audit's failures were almost all instrument failures, so the doctrine is about instruments.

**D1 — Pre-registration.** Before a run: the question in one sentence, the population, the
frozen window, the labels, the verdict strings, and the kill criteria. Written in the note
*before* the result table. A study without stated kill criteria is not allowed to conclude.

**D2 — Composition parity gate.** A research harness is product code. It must reproduce a
known fingerprint before it measures anything new (e.g. the October seek fingerprint:
441 armed / 149 routes / 11 fills). P0-1 existed because this rule did not.

**D3 — Determinism.** Dual run, byte-identical `trades.csv` + `report.json`, or the run is
invalid. Every note quotes the hashes.

**D4 — Full detection set, asserted.** `(D1,H4,H1,M15)` supplied by
`lib/product_htf_series.py`; missing TFs raise by name. A funnel with an incomplete HTF map
is not evidence (this exact defect produced `htf_batches=0, batch_errors=2979` on 6m).

**D5 — No aggregate-only counters.** Every counter that matters carries its attribution key
(book, tier, trigger). M-4 exists because `blocked_by_reason` had none.

**D6 — Denominators travel with every rate.** "6.0% route" is meaningless without "of 585
armed coincidences". n ≤ ~30 is labelled TEXTURE_ONLY in the same sentence.

**D7 — One question per pack.** Compound studies hide which gate moved. If a pack needs a
rule change to answer, the rule change is a separate dated lock with its own measurement.

**D8 — Budget declared, not discovered.** State the runtime budget before launching; if it is
exceeded, stop and report. Never silently shrink the window (the 45-min menu kill was handled
correctly — that is the pattern).

**D9 — Failure is a result.** A pack that returns FAIL/INCONCLUSIVE is a successful pack; it
gets the same governance entry as a PASS. (`PLACEMENT_NOT_PRIMARY`, `FAIL_TIGHT`, the O1–O5
locks.)

**D10 — No threshold movement to buy n.** Restated because it is the failure mode this
project is most vulnerable to. Sample size is bought with longer windows and fragment
proxies, never with a looser gate.

**D11 — Artifacts are disposable, reports are not.** Results trees stay gitignored; the
report cites paths and hashes; anything a report's claim depends on is either in the report
or force-added.

**D12 — Governance at task end.** Commit + push per the standing rule; `LOGIC_CHANGED`,
suite counts, `locked_constants` diff in the commit body. No task ends with an unpushed
change or an unrecorded result.

---

## 5. Validation checklist — the gate every stage must pass

Run this before declaring any stage done. All boxes or it is not done.

**Technical**
- [ ] Suite green (`cd 04_SRC && PYTHONPATH=. python -m pytest -q`), count recorded.
- [ ] `git diff` empty for `04_SRC/smc/config`, `locked_constants.py`, and any strategy path
      the stage was not authorized to touch.
- [ ] Dual run byte-identical (or a written, evidenced reason it cannot be).
- [ ] No test skipped, weakened or deleted to make a gate pass.

**Measurement**
- [ ] Composition fingerprint reproduced (D2).
- [ ] Full detection set asserted (D4).
- [ ] Counters reconcile exactly (raw → merged → pass → arm → route → place → fill), no
      unnamed bucket, no aggregate-only counter (D5).
- [ ] Every rate has its numerator/denominator; TEXTURE_ONLY labelled where n is small (D6).
- [ ] Pre-registered verdict string emitted, and it is one of the strings written before the
      run (D1).

**Decision**
- [ ] The stage's question is answered *by the gate*, not by prose.
- [ ] Dissent recorded where the auditor and the Architect disagreed.
- [ ] Architect signature in the date line; the next stage named in one sentence.
- [ ] Nothing downstream started before the signature.

---

## 6. What is explicitly NOT in this plan

- Reopening O1–O5 without new data (they are locked status-quo).
- Re-enabling CHOCH Rule 3, color-coded D/S, or a boundary-sweep emitter.
- Widening pillars, seek span, R7 proximity or sessions to raise n.
- A 1:5 TP lock, a 30-pip stop, or any ratio/stop tuning.
- ML, a "brain", or a scoring model.
- Cross-book PF/expectancy comparison between the books (different admissible sets; the DUMB
  audit §6 rules apply unchanged).
- Demo/live PnL as validation.
- A 5-year product number before S5 makes a continuous run honest.

---

## 7. Rough effort (estimates only — never promises)

| Stage | Effort | Blocks |
|---|---|---|
| S0 | hours after exit; ~12 runs remaining at ≈1.5 h each | everything |
| S1 | ≤ 1 day (one stamp + one test + one short proving slice) | S2 |
| S2 | 1 ruling session (needs S0 + S1 artifacts) | S3, S4 |
| S3 | ≈ 1–3 days wall (12 segments × ratified books × 2 hypotheses) | S4, S6 |
| S4 | 1 anatomy pack + 1 pre-registered counterfactual (days each) | S8 |
| S5 | perf profile + patch + byte-identity proof (needs authorization) | continuous runs, 5y |
| S6 | holdout + WF/bootstrap (days of compute, days of write-up) | S8 |
| S7 | 2-week soak + drill | S8 |
| S8 | ruling + installer rebuild | testers |

---

## 8. The next three actions, in order

1. **On process exit:** S0 — status script, `verdict.json`, report, governance, commit. (Do not
   poll it in-session; the agent is not notified. Re-message when it should be read.)
2. **Then:** S1 — M-4 attribution stamp + regression test + byte-identity proof on a slice.
3. **Then:** S2 — the admission ruling, with the verdict artifacts on the table.

```text
PLAN_STATUS: PROPOSED (needs Architect ratification)
PATH: 06_RESEARCH/POST_PARALLEL_BOOKS_RESEARCH_PLAN_2026-11-19.md
ORDER: S0 verdict → S1 attribution(M-4) → S2 admission ruling → S3 re-baseline → S4 entry representation
       → S5 menu performance → S6 OOS → S7 paper soak → S8 promotion
WHY_THIS_ORDER: the measured lever (admission) is decided first; n is rebuilt before any strategy
                 question is judged; production code (perf) is authorized only after the book is ratified
GATES: G0 verdict green · G1 attribution without decision drift · G2 dated ruling · G3 reconciled
       census · G4 pre-registered kill criteria · G5 byte-identical perf patch · G6 frozen holdout
       · G7 two-week soak · G8 signed waiver chain
DOCTRINE: D1–D12 (pre-registration, parity fingerprint, determinism, full TF set, attributed
          counters, denominators, one question per pack, declared budget, failure is a result,
          no threshold movement, disposable artifacts, end-of-task governance)
PROD_DEFAULTS_CHANGED: NO
LOGIC_CHANGED: NO
```
