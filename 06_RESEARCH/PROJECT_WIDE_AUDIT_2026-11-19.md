# PROJECT-WIDE AUDIT — IDEA → EXECUTION (2026-11-19)

**Auditor:** independent read-only pass (Buffy).
**Method:** primary evidence only — frozen reports, summaries, governance ledgers, git history.
Prose is a claim; a count with an artifact path is evidence. `04_SRC` was not modified by
this audit.
**Standing bans honoured:** no expectancy/edge claim anywhere below; no gate was loosened,
no threshold moved, no default changed. Where a PnL number appears it is quoted from the
source report and labelled as the source labels it (diagnostic book-internal or accounting
residue, **not performance**).
**Not audited:** MT5/live behaviour (no terminal in this pass), the in-flight parallel-books
year run's result (it has no result yet — 12/24).

---

## 0. What the idea actually is

One sentence, as coded: *HTF POI zone (D1/H4/H1/M15) → liquidity sweep → displacement/FVG
confirmation → LTF trigger completion inside the zone (A–F) → risk-sized resting limit at
the zone edge → ATR stop + first-valid-swing TP (4×ATR fallback) → managed exit*, with
one-story/one-plan/one-order uniqueness at the adapter intake.

Everything that passes or fails below is a judgement about **how faithfully and how
measurably that sentence was turned into a machine**, not about whether gold trends.

The single most important structural fact this audit found: **the project repeatedly
confused "the idea does not work" with "the instrument cannot see the idea."** Nine of the
fourteen failures below are measurement-instrument failures, not strategy failures. The
recent program (R0/R1, Scan 1, BCE, PFE) is the correction of exactly that error.

---

## 1. Scoreboard

| Layer | Verdict | One-line basis |
|---|---|---|
| Concept clarity (expert SMC process) | **PASS** | Signed master card; every rule traceable to a beat |
| Idea → code fidelity | **PASS WITH DRIFT** | 7 aligned / 5 partial / 1 drift / 1 absent (PFE-1); drift and absent both closed by PFE-1.5 |
| Engineering discipline | **PASS (strong)** | 1,555 tests / 7 skipped; byte-identical dual runs; 0 TODO markers in src; locked-constants test-pinned |
| Measurement instrument | **PASS (recently), FAILED (historically)** | Historic funnels were composition-blind (P0-1); fixed 2026-11-14 |
| Signal existence | **PASS** | 2,497 LTF completions / 1,093 HTF theses per 6m — events are abundant |
| Admission selectivity | **PASS as fact, UNJUDGED as value** | The AND-chain, not the market, sets frequency; nobody has shown each conjunct is *positively* selective |
| Economics | **UNRESOLVED / unmeasurable at current n** | 3 fills/6m (seek-era), 239 fills/year (product_1y) all stop-dominated; no OOS, no expectancy permitted |
| Ops readiness | **PARTIAL** | Heartbeat path proven; EA attach, stale drill and an unattended soak never run |
| Live/default promotion | **NOT MET** | By ruling; defaults frozen, all books dead-by-default |

Roughly: **the concept passes, the code passes, the instrument just barely passes, the
economics has never been testable, and execution of the *concept* — i.e. "does this
filtration produce tradeable, measurable behaviour" — is still open.**

---

## 2. Ideas that PASSED in execution

### 2.1 Determinism + frozen-constants governance — PASS, load-bearing

Byte-identical dual runs on every ledger and baseline (phase C, 6m refresh, one-story, 12
monthly segments, parallel-book smoke). `locked_constants.py` is asserted against
`LOCKED_DECISIONS.md` by test, so an invented number is structurally hard to introduce.
This is why every other verdict in this document is arguable at all: without it, no A/B in
the repo would mean anything.

### 2.2 The detection/permission stack exists and is abundant — PASS

Post-sweep catalog (n=174): triggers 100%, displacement 78%, FVG formed+mitigated 87%, zone
touched 93%. Scan 1A: **2,497 LTF completions** on the product's own trigger code over the
year. The idea's ingredients are present in quantity. "The market never gave setups" is
falsified.

### 2.3 Funnel accounting honesty — PASS

Every stage's mass dies inside a **named** gate with a count: pillar histogram, 98.52%
`SKIP_DEDUP_EPISODE`, `blocked_by_reason`, `expired_give_up`, `violated_pulls = 0`. No
silent drop was found in any audit (`INDEPENDENT_FUNNEL_IDEA_AUDIT_2026-10-11` §B4). The
repo's honesty about where trades die is the reason the starvation question could later be
answered precisely.

### 2.4 ZoneDedup lifecycle fix — PASS (and it was the right fix)

Diagnosis `ARM_FILTER_IS_BOTTLENECK`: 2,021 passes → 30 arms, 98.52% suppressed by a registry
with **no removal API**; 49.8% of suppressions came from zones armed ≥30 days earlier
(median 29.5 d). Implementation: owner-attributed keys + retirement when no live obligation.
Result **30 → 606 armed**, dedup 1,991 → 1,415, `trades.csv` byte-identical, no double-arm.
A genuine architectural defect, correctly attributed, correctly repaired, honestly measured.

### 2.5 One-story → one-plan → one-order — PASS

The menu bridge produced 27 fills but only **8 distinct plans** (byte-identical
entry/SL/TP, different `poi_id`). The guard at adapter intake cut 14→4 in the Oct smoke and
27→9 over 6m, dropped 580 duplicate winners across the year, and **removed the circuit-breaker
trip caused by the F-spray** — a distinct A-plan placed only after the spray was gone. This
is the clearest case of "the idea was right but the execution duplicated it."

### 2.6 BCE starvation diagnosis — PASS, the audit's most valuable single result

B/C/E had 267/75/143 isolated completions and **zero fills all year**. The cause was not the
market and not the triggers: `ProductMenuEngine` builds each tier's confirmation router from
`tier.trigger_types`; M15/H1/H4 tiers carry `_TIER_ADF = (A,D,F)`. **173 of 218 (79.4%)**
POI-linked B/C/E rows sat on non-D1 POIs — structurally unconfirmable. On the 45 D1 rows, a
faithful offline replay over the whole year produced **0 B/C/E confirmations**. `MATRIX_BLOCKED = 0`
by construction (every §15 cell allowed) — so the trigger matrix was never reached, and the
"trigger arbitration is blocking us" hypothesis is dead by measurement.

### 2.7 R1 pure single-tag books — PASS, and it closes the starvation question

Runtime tier injection on the product_1y armed universe, real menu/adapter/runner:
**B/MID 264, C/MID 219, E/MID 183, A/MID 64, F/MID 374, F/D1 14 fills** vs **zero** in
production. Anchor gate **237/239** product fills union-reproduced, zero missing-without-a-
window-win; the two misses are probe-explained (replay-only breaker losses, one queue-order
case). Conclusion earned: *the starvation is ADMISSION-gated, not signal-absence* — and the
missing fills are recoverable without touching a single threshold.

### 2.8 The five open decisions O1–O5 — PASS as measurement, all closed status-quo

The program's real product is **five falsifications of "widen the gate" intuitions**:

| ID | Proposal tested | Measurement | Why it failed |
|---|---|---|---|
| O1 | C3 boundary-sweep fallback | 137/149 C3 rejects; **97.1% FAR**, median **35.9 ATR** outside; boundary population 2.2% | Rejects are price that left the zone, not edge near-misses |
| O2 | HTF sweep as hard stage | route rate S+ 29.3% vs S− 31.9%; fills 11 vs 0 on n=23 | No route separation; sweep is context, not admission |
| O3 | TF priority rule | any one-survivor rule drops **all 11 fills** and all 12 C3 passes | Overlap clusters chain the book; a priority rule is destructive, not selective |
| O4 | 30-pip pinned stop | product SL median **71.4 pips**, MAE **78.1**; MAE ≤30 pips on 1/11 | A 30-pip stop hits every loser **and** 2 of 3 winners |
| O5 | 1:5 ESSENCE target | structural 8/11 (0.91 R, 37.5% hit) vs fallback 3/11 (3.52 R, 0/3) | Both branches live; no branch is wrong-sided; no ratio lock |

### 2.9 Near-miss counterfactual — PASS, and it killed the project's own favourite hypothesis

7 untaken routes paper-traded under frozen fill semantics: **all 7 `EXPIRED_NO_FILL`**;
100-bar sensitivity adds exactly **one** TP. Verdict **PLACEMENT_NOT_PRIMARY**. The R9
intent book had already answered the same question independently (4 of 7 R7-skipped routes
expired with no re-entry). The study's own honest finding: entries are zone-edge limits left
a median **~26.6 units** behind post-impulse price — the constraint is *entry
representation*, not the placement window in front of it.

### 2.10 PFE sequence (1 → 1.5 → 2 → 3) — PASS

PFE-1 found the two findings that mattered: **P0-1** (research composition was seek-only
while live runs menu — every measurement since 2026-10-26 sampled the non-menu half) and
**P0-2** (menu winners silently always took the 4×ATR TP). Both closed by PFE-1.5 with
tests. PFE-2 then produced the first composition-parity book (seek 6m: 1,865 armed / 670
routes / 80 fills; menu bounded windows 97/23/14, 60/18/11, 170/3/2). PFE-3 produced a blind
56-chart expert pack. This is the correct order — audit fidelity, then measure, then ask a
human — and it is the reason the current numbers are trustworthy in a way the September ones
were not.

### 2.11 Parallel dedicated books — PASS at design/impl level (result pending)

Spike parity against the shipped single menu is exact (winners 22/22 L, 19/19 S; fills
11/11, 12/12); book isolation real; identity key correctly excludes the trigger. Audit found
**1 CRITICAL (window-scoped cross-book dedupe) + 5 MAJOR + 8 minor**; C-1/M-1/M-2/M-3/M-5 are
now closed with a liveness-scoped registry and a trigger-excluded backstop. **M-4 (risk
blocks not attributed per book) is still open.** The full-year measurement (F,B,C,E,A × 12
segments × 2 hypotheses) is in flight — as of this audit **12/24 runs, heartbeat fresh, 0
dupes on every finished run, no verdict yet.**

### 2.12 Ops hardening that actually held — PASS (partial scope)

Heartbeat path was *proven* (resolved to `MQL5\Files`, age 0.9 s, clean shutdown marker) after
the docs were found wrong; the watchdog is fail-closed; tester pack is single-folder and
leak-free. Not exercised: EA attach, stale-heartbeat drill, unattended soak.

---

## 3. Ideas that FAILED in execution — and the mechanism

Failure here means **the concept did not survive contact with its own measurement**. Several
are *productive* failures (they closed a question). Marked accordingly.

| # | Idea | Verdict | Mechanism of failure | Productive? |
|---|---|---|---|---|
| F1 | "Scarcity is caused by placement gates (R7/session/expiry)" | **FAIL** `PLACEMENT_NOT_PRIMARY` | All 7 untaken routes expired unfilled under frozen semantics; 1/7 in the 100-bar sensitivity. The gates remove untakeable paths | **YES** — redirected work to entry representation |
| F2 | "Reactive admission rule set (R1–R6)" | **FAIL_TIGHT** | Admitted **3** of 268 (< 8 threshold) and overlapped the product's 3 control fills **0 times** — it would replace the baseline, not extend it | YES — killed before any code |
| F3 | "LTF-return entry representation" (singular + broadened) | **FAIL / INCONCLUSIVE** | Singular measure: 45.1% `STRUCT_UNAVAILABLE` > 0.30 gate. Broadened measure: **100% `representation_coverage_failure`** — every direction-matched FVG failed the protected-side rule. The representation the idea needs does not exist in the product's own detector output | YES — but it leaves the entry-timing question open with no candidate |
| F4 | "Boundary-sweep fallback at C3 edges" | **FAIL as a hypothesis** (O1) | 97.1% of rejects are >1 ATR outside; median 35.9 ATR. Edge population 2.2% | YES |
| F5 | "HTF sweep as a hard product stage" | **FAIL as a hypothesis** (O2) | S+ 29.3% vs S− 31.9% route rate — no separation; the 11-vs-0 fill asymmetry is n=23 denominator noise | YES |
| F6 | "Any multi-zone priority rule" | **FAIL as a hypothesis** (O3) | Drops all 11 fills. D1 bodies chain the whole armed set into 5 clusters covering 441/441 arms | YES |
| F7 | "30-pip expert stop / 1:5 ESSENCE target" | **FAIL as product rules** (O4/O5) | 30 pips < MAE on 10/11; 1:5 fallback already is 3.52 R and hits 0/3 | YES |
| F8 | "B/C/E need a trigger or matrix fix" | **FAIL as a diagnosis** (BCE) | Not matrix (`MATRIX_BLOCKED=0`), not C3 (0 rejects reached). Tier-scoped router = structural exclusion | **YES — highest-value failure** |
| F9 | "Trigger D / volume confirmation" | **FAIL as implementable** | Feed has no volume; D is structurally dead, not disabled. Documented, never "fixed" | Neutral |
| F10 | "Coupled-MTF policy (H4 sweep → M5 A/D/F)" | **FAIL as a product candidate** | 32 tracked POIs → 1 sweep → 1 episode → **0 confirms** over 6m; sparsity accepted, no rule relaxed | YES (cheap kill) |
| F11 | "DUMB flowchart as 1:1 essence of the expert chart" | **FAIL as fidelity** | Shares only the M8 zone. Confirmation NONE (single mid-reclaim proxy vs pillar+matrix), TP NONE (2R vs structural). Density overshoots design band by an order: **4,364 vs 58 (75.2×)** W3, 2,874 vs 44 (65.3×) W2. The ≥70% rubric gate was never run | Partly — it is a usable scarcity diagnostic |
| F12 | "Episode store as the fix for X" | **PARTIAL / UNPROVEN** | V1 shipped observability-only (byte-identical parity, 25 states, geometric identity). It has since explained real defects (`expired 0` bug) but **answers no strategy question by itself**; the dissent that it should come third was right | Neutral |
| F13 | "Continuous multi-year menu replay" | **FAIL (performance)** | 26.1 → 7.1 → 2.5 bars/s by bar 6,000; <10% of the year in 45 min. Quadratic menu bookkeeping. Everything since is segmented tiling — **an instrument limit that silently shapes every conclusion** | Blocking; fix is production code, not authorized |
| F14 | "Mode T proves the expert's confirmations can be graded from tickets" | **PARTIAL, biased** | T2's gap gate (`|mid−close| ≤ 0.25 ATR` of the proof bar) samples only quiet completions; sharp retests can never place. Skips are logged, so grading is possible — but ticket-based grading is a biased sample | YES (documented) |
| F15 | "Counts as evidence of quality" | **FAIL (methodology)** | 75× density, 3 fills, 11 fills, 239 fills — each was at some point read near a conclusion. All were later downgraded to TEXTURE_ONLY. The proof register's PROVEN/TEXTURE/SUPERSEDED vocabulary exists because of this | YES (institutional fix) |
| F16 | "ML / loosening gates to get n" | **BANNED, correctly** | Manufacturing n destroys the measurement baseline; OOS does not exist | n/a |

---

## 4. Root causes — why the execution failed, in one place

### RC-1. The AND-chain was never priced (the founding error)

A trade requires zone × sweep × displacement × FVG × 5 pillars × seek window × trigger ×
chronology × R7 proximity × session × sizeable × fill-before-expiry × survive-management.
Every conjunct was assumed *positively selective*; none was ever shown to be. The 6m funnel:
**96,015 raw → 43,004 merged → 2,021 pass (P2 alone kills 87.8%) → 30 unique armed → 10
routes → 4 placed → 3 fills.** The idea's natural cadence is ~5 episodes/month; a 6-month
book cannot measure that, and no fragment was being measured because fragments never
completed the chain. This is the diagnosis the 2026-10-11 audit reached and it has held for
five weeks.

### RC-2. The instrument measured the wrong half of the product

P0-1: research ran seek-only while live ran menu+seek since 2026-10-26. P0-2: menu winners
silently took the 4×ATR TP. Both were invisible for ~3 weeks of measurement. Cause: the
harness composed `PipelineAdapter` directly instead of the shipped entry law. Fix: PFE-1.5
parity + contract §11. **Lesson encoded:** a measurement harness is product code and needs a
parity gate.

### RC-3. Tier scope was a hidden global filter

`_TIER_ADF` on three of four tiers removed three of six triggers from the product on those
tiers — not by a ruling, by an implementation detail of router construction. It produced
zero B/C/E fills for a year and was diagnosed twice (BCE, then R1) before anyone could see
it. Cause: per-tier defaults never surfaced in the admission map. Fix: R0 map + R1
counterfactual; the fix itself is still a **design choice, not applied**.

### RC-4. Duplicate plans masqueraded as a book

The menu path emitted 27 fills for 8 stories. Caught only because the window was small and
someone counted distinct plans. Cause: `poi_id` identity instead of plan identity. Fix:
story guard. **Generalisation:** every counter in this repo that is keyed by `poi_id` has
been, at some point, the source of a defect.

### RC-5. Runtime collapse silently caps study size

Quadratic menu bookkeeping makes the only honest year-scale test (continuous replay)
impossible. The sanctioned substitute is **segmented tiling**, whose known costs are: armed
counts restart (never summable), fresh risk state per segment, and replay-only breaker
artifacts (which is exactly how 2 of the 239 R1 anchor fills were lost). None of these
invalidates a per-segment reading; all of them invalidate a naive sum.

### RC-6. n was treated as an argument instead of a constraint

Three fills were once discussed as a "book"; 75× density once read near "opportunity";
11 fills once nearly locked a TP policy. The institutional answer (PROVEN / TEXTURE_ONLY /
SUPERSEDED, plus pre-registered kill criteria in every later study) is now working — the
near-miss, coincidence, reactive-admission and O1–O5 studies all **failed their own
hypotheses honestly**, which is the sign the instrument matured.

---

## 5. Where the concept now stands (as-coded, not as-hoped)

- **Signal: abundant.** 2,497 completions/yr, 1,093 HTF theses/6m, 585 with in-window LTF
  proof (**53.5%**). The thesis and the proof co-occur; the product simply does not route
  them (6.0% of armed coincidences route, 1.1% fill).
- **Admission: the whole story.** Fifteen of the sixteen failures above are admission or
  instrument failures. The one idea that survived every test is the one that changed
  *admission* without moving a threshold: **parallel dedicated books** (B/C/E confirmable
  when they get their own tier scope), currently being measured over a full year at 12/24.
- **Economics: still not measurable.** 239 fills/yr with SL 174 / TP 65 and no OOS is a
  census, not evidence; the repo is right to forbid expectancy language.
- **Ops: unproven where it matters.** Heartbeat verified; attach/drill/soak are not.

**Net verdict:** *concept PASS (coherent, faithfully coded, abundant signal), execution
PARTIAL (filtration is over-determined and one tier silently excluded three triggers),
evidence FAIL-AS-YET (no window in the project's history has produced a measurable
economics book).* The 2026-10-11 score of 4/10 for "idea→money translation" is still roughly
right; what has changed is that the *reason* is now localised to admission/tier scope rather
than to the idea or the code.

---

## 6. Open items this audit does not close

1. **Parallel-books year result** — 12/24, no verdict. Do not read until `verdict.json` +
   `EXIT_CODE.txt`.
2. **M-4** — risk blocks unattributed per book; the year run's skips cannot be assigned.
3. **The promotion decision the parallel books imply** — B/C/E starvation is admission-gated
   and recoverable (R1); whether the product should carry five books is an Architect ruling,
   not an audit conclusion.
4. **Entry representation** — near-miss and LTF-return both point here, and both candidate
   representations failed. This is the one genuinely open *strategy* question.
5. **Menu performance** — the blocker to any continuous year/5-year book; production code,
   unauthorized.
6. **PFE-3 expert scores / PFE-4 paper** — the human gate; not answered.
7. **Live ops** — EA attach + stale drill + soak never performed.

---

## 7. Return block

```
AUDIT_STATUS: PASS
AUDIT_PATH: 06_RESEARCH/PROJECT_WIDE_AUDIT_2026-11-19.md
CONCEPT: PASS
CODE_FIDELITY: PASS_WITH_DRIFT (drift + absent both closed by PFE-1.5)
ENGINEERING: PASS (1,555 passed / 7 skipped)
MEASUREMENT: PASS_NOW_FAILED_HISTORICALLY (P0-1 composition drift; fixed 2026-11-14)
ECONOMICS: UNRESOLVED (239 fills/yr census; no OOS; expectancy banned)
IDEAS_PASSED: 12 (determinism/constants, detection abundance, funnel accounting, ZoneDedup lifecycle,
  one-story guard, BCE diagnosis, R1 pure books, O1-O5 falsifications, near-miss, PFE sequence,
  parallel books impl, ops hardening)
IDEAS_FAILED: 16 (listed §3; F1-F16 with mechanisms)
SINGLE_ROOT_CAUSE: the AND-chain was priced nowhere and one tier silently carried only 3 of 6 triggers
SINGLE_MOST_VALUABLE_FAILURE: BCE/R1 — starvation is ADMISSION-gated, not signal-absence
IN_FLIGHT: parallel-books year BT 12/24 (PID 11652, heartbeat fresh, no verdict)
PROD_DEFAULTS_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
LOGIC_CHANGED: NO
NEXT_READY: parallel-books verdict on exit | Architect review of admission/tier ruling | entry-representation question
```
