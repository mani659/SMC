# BRANCH C — DESIGN LOCK (Trigger C reachability, product path only)

**Status:** DESIGN LOCK — awaiting Architect option acceptance.
**`LOGIC_CHANGED: NO`** · **`CODE_CHANGED: NO`** (no production code in this task).
**Recommended option:** **C1 — observability-anchored validity window** (§5 below).
**Authority:** Lead Architect *BRANCH C — DESIGN LOCK ONLY*.
**Upstream evidence:** `06_RESEARCH/BRANCH_C_ROOT_CAUSE.md`,
`06_RESEARCH/BRANCH_C_E2E_REPORT.md` (verdict `DEFER_RECOMMENDED`, factual state
BLOCKED), `06_RESEARCH/PRODUCT_BRANCH_LIVENESS_REPORT.md` (C = DARK).
**Frozen window (re-used, not re-picked):** exec 2025-09-01 → 2025-11-30 UTC on
M5, warm-up 2025-08-01.

---

## 1. Problem

Trigger C is implemented, registered and routable, but it is **arithmetically
unreachable** on the only wiring it is allowed to use:

| Fact | Value | Code |
|---|---|---|
| Admissible tier | DAY only — D1 detection → **H1** confirmation | `product_menu_mtf.py:239-254` (`_DAY_TRIGGERS = tuple(TriggerType)`; `_TIER_ADF` excludes C) |
| Confirm-series swings | `detect_swings(confirm_series, ctf)` | `product_menu_mtf._swings_for` |
| Swing availability | fractal at `i` is reported only when `i ≤ len−1−N`; `N = N_BAR_HTF = 5` | `structural_swing_detector.py:59`; `locked_constants.py:167` |
| C validity window | `TRIGGER_C_EXPIRY_EXTRA = 3` from `diagonal.terminal_index` | `trigger_c_ending_diagonal.py:57-62`; `trigger_expiry.py:50,76`; `locked_constants.py:175` |
| Terminal index meaning | the §18 **base candle** of Wave 5 (`Swing.candle_index`) | `wave_structure.py` (`terminal_index=w5.index`) |

Required `bar ≤ terminal + 3`; achievable `bar ≥ terminal + 5`. The inequality
fails on **every** bar of **every** window, so `signal_expired` rejects every
candidate before the zone / reclaim gates matter.

**Measured (frozen window, 68 D1 arms reproduced):** 361 ending diagonals at H1,
minimum terminal age **5**, p10 6, median 12, max 37; **0** inside the window;
real `evaluate()` over **1,489 H1 bars × 68 POIs** with `from_bar = 0` = **0**
completions. Counterfactual with expiry ignored (instrumentation only): **3**
signals on 2025-11-25 09:00 UTC, terminal age **6**, **2 of 3 pass C3** — the
pattern, the zone context and the containment gate are all satisfiable; only
the expiry blocks them.

**This is a design conflict, not a data problem.** The locked text "sweep candle
+ 3" is implemented exactly, and `N_BAR_HTF = 5` is implemented exactly. Two
independently frozen rules are jointly unsatisfiable on the DAY/H1 wiring. A
patch that changes either number is a policy act, which is why no code was
written during the audit.

**What the design must decide:** measured from *what*, does Trigger C have a
finite validity window that a detection algorithm can actually observe?

---

## 2. Options

| # | Option | What becomes legal when | Frozen document edited | Blast radius | Reachable after? | Window evidence |
|---|---|---|---|---|---|---|
| **C1** | **Observability-anchored window** — C's window opens when the diagonal's terminal becomes **knowable** (present in the swing series), and keeps its frozen 3-bar life from there | `terminal + N(tf)` … `terminal + N(tf) + 3` | `LOCKED_DECISIONS` §24 (C row **anchor semantics** only; the number 3 untouched) | 3 source files, all inside the C path | **Yes** (age 5–8 legal; the 2025-11-25 age-6 case is inside) | 0 → **1–3** completions expected (upper bound = the 3 counterfactual signals) |
| C2 | **Confirm-TF change** — give C a shorter-N confirmation series (M15 or M5, N=3) on the DAY tier | any tier-table change legalises new (tf, trigger) cells | `PRODUCT_MENU_TIERS` (locked 2026-10-26) **+** the admission map | tier table, router population, both B/C/E exclusions, C3/ATR context on a different TF | Yes at N=3 (`terminal+3`) | same 3 signals move to a different TF; not measured on M15/M5 |
| C3 | **Product-OFF** — remove C from `_DAY_TRIGGERS`; state "not offered" on the card | nothing becomes legal; C stops being claimed | master card `§24a` claim + `_DAY_TRIGGERS` tuple | one tuple, one claim | **No** (by design) | 0, permanently |
| C4 | **Formula expiry tied to N** — `§24` C row becomes `N(tf) + 3` bars | `terminal` … `terminal + N(tf) + 3` | `LOCKED_DECISIONS` §24 (numeric formula) **+** `locked_constants` expression | 2 source files; couples §24 to §27 | **Yes** | identical set to C1 |

**C1 and C4 are arithmetically identical** (same legal bars, same expected
completions). They differ in *what is written down*: C1 changes the **anchor
meaning** and leaves the frozen number 3 alone; C4 changes the **number into a
formula**. C1 is recommended for that reason (§3).

**Rejected on principle (not offered as options):** raising
`TRIGGER_C_EXPIRY_EXTRA` to a value chosen to produce fills; lowering or
bypassing the global `N_BAR_HTF`; widening the §2 EQH tolerance; adding a C-only
C3 exemption or a C-only ATR band; force-routing a pattern the detector cannot
emit; extending the calendar window until C fills. Each converts a frozen
contract into a fill.

---

## 3. RECOMMENDED: C1 — observability-anchored validity window

**Statement.** A trigger's §24 life is meant to bound how long a pattern stays
**actionable**. For C the pattern is a 5-swing diagonal whose terminal is a
structural swing; on H1 such a swing does not exist as data until `N = 5` bars
after its fractal. The window should therefore start **when the pattern becomes
knowable**, not when its terminal candle printed. Under C1 the number 3 keeps its
locked meaning ("three bars of validity"), and the only thing that changes is
the instant the clock starts.

**Why C1 and not the alternatives**

1. **It resolves the contradiction instead of a symptom.** The defect is that
   the clock starts before the object it measures exists. C1 moves the start to
   knowability; C2 moves the object to a different timeframe; C3 deletes the
   object; C4 restates C1's arithmetic as a formula.
2. **It changes no frozen number.** `TRIGGER_C_EXPIRY_EXTRA = 3`,
   `N_BAR_HTF = 5`, `N_BAR_LTF = 3`, `MENU_EXPIRY_BARS = 20`, C3, sessions, EQH
   and the ATR band are all untouched. C2 edits the locked tier table; C4 edits
   a locked constant's expression. A §24 anchor clarification is the smallest
   possible policy edit.
3. **It matches a convention this repository already documents.** Swing-derived
   objects are treated as knowable at `known_at = max(pivot_index + N, §19
   confirmed_index)` in `06_RESEARCH/COUPLING_POLICY_DESIGN.md:72`. C1 applies
   the same knowability rule to a trigger clock that reads a swing. It is not a
   new concept, it is the existing one applied where it was missing.
4. **It keeps the pattern on the timeframe the tier was designed for.** C's
   entry geometry is a D1 zone's boundary sweep; confirming it on M15 (C2) would
   change what the trade is, not just when it may fire, and would leave C the
   only member of the DAY set confirmed away from H1.
5. **It is TF-correct by construction.** If C is ever wired to a shorter-N
   confirmation series, the anchor moves with it automatically (no new
   constant), which is exactly the failure mode C2 would reintroduce by hand.
6. **Blast radius is one trigger.** Three files, all inside the C path, with a
   single revert point. F (the only LIVE branch), A/B/D/E, the risk layer, the
   order book and the tier table are not touched.

**Why not C3 (product-OFF).** C3 is the cheapest option and is the correct
fallback **if the Architect declines to amend §24 at all**: it costs no code and
no risk. It is not recommended as primary because it abandons a trigger the
master card records as live (§24a "C — Ending diagonal — YES — measurement in
V1"), and because the evidence shows the detector works (361 diagonals; 3 would
complete; the essence v1 slice confirms 51 ED at N=3) — the branch is blocked by
a wiring arithmetic, not by an absent or unreliable pattern. Deleting C is a
claim decision, and the programme's stated intent is to unlock C as a single
strategy path.

---

## 4. Normative rules (what becomes legal when)

**R1 — Knowability anchor.** For `TriggerType.C_ENDING_DIAGONAL` the validity
clock starts at
`anchor = diagonal.terminal_index + N(confirm_tf)`, where `N(tf)` is the frozen
§27 confirmation window (`Timeframe.n_bar_confirmation(tf)`: 5 for D1/H4/H1, 3
for M30 and below). `diagonal.terminal_index` keeps its current meaning (the §18
base candle of Wave 5); it is **not** redefined.

**R1a — Conservative bound, stated.** `terminal_index + N` is the earliest bar
at which the terminal swing *can* be in the series. For a swing **high** it is
exact (base candle = fractal). For a swing **low** the §18 rule may place the
base candle one bar before the fractal, so the true observability is up to one
bar later; the anchor is then one bar early and the effective post-visibility
life is 2 bars instead of 3. This is accepted and recorded: it can only shorten
C's window, never lengthen it, and it never opens the window before the pattern
is knowable in the other direction (the trigger still cannot emit without
`find_ending_diagonal` returning the diagonal).

**R2 — Frozen life.** The window is still **3 bars** after the anchor
(`signal_expired(anchor, TRIGGER_C_EXPIRY_EXTRA, bar)`), i.e. C is legal on
`anchor … anchor + 3` and dead from `anchor + 4`. The constant and
`signal_expired`'s arithmetic are unchanged. On the product path at H1 this
means legal terminal ages **5, 6, 7, 8**.

**R3 — Admission unchanged.** C stays in `_DAY_TRIGGERS` and out of
`_TIER_ADF`; DAY stays D1 → H1; no new tier row, no new confirmation TF, no
router change, no matrix change. C is still chronological first-valid (§12) and
subject to the one-shot episode.

**R4 — Pre-pattern gates unchanged.** `bar ≥ context.from_bar` (episode sweep)
and `diagonal.terminal_index ≥ context.from_bar` hold exactly as now: a
diagonal whose terminal predates the sweep cannot be routed, regardless of the
new anchor.

**R5 — Geometry gates unchanged.** Zone context stays `zone.bottom − band ≤
terminal_level ≤ zone.top + band` with `band = 0.5 × ATR` (§13 multiplier); the
entry stays `boundary_touch_level`; the stop stays `terminal_level`; emission
still requires the **first** close back across the boundary (`reclaimed and not
earlier`).

**R6 — Completion semantics unchanged.** `completion_index` is the reclaim bar,
`expiry_bars` is still `window_bars_for(C) = 3`, and C3's `in_between` gate on
the completion close remains the product validity condition (no exemption, no
boundary case).

**R7 — Lookahead safety.** The anchor is a pure function of
`(terminal_index, N(tf))` — indices at or before the evaluation bar, index-count
only, no price, no future bar. It is never earlier than the current bar's
knowledge in any way that could let the trigger see a swing the series does not
contain: `find_ending_diagonal(swings, dir, bar)` still receives the swing list
built from the closed prefix, and `detect_swings(prefix)` cannot contain a
swing younger than `terminal + 5`. R1 only *delays* expiry; it never admits a
bar earlier than the current `bar ≥ terminal + 5` reality. No retro-dating, no
`bar` substitution, no reversal of the reclaim ordering.

**R8 — Nothing else moves.** A, B, D, E, F windows; `window_bars_for`;
`poi_give_up_bars()` (`TRIGGER_A_EXPIRY`); `MENU_EXPIRY_BARS`; §23 order expiry;
the risk/session/spread/ONE-STORY path; `PRODUCT_MENU_TIERS`; `_TIER_ADF`;
`locked_constants.py` values (including `TRIGGER_C_EXPIRY_EXTRA = 3` and
`N_BAR_HTF = 5`); EQH tolerance; TP age cap (production A); the F stop/target
path. All frozen.

**R9 — Instrumentation.** The emitted signal carries `known_at` (the anchor) in
`data` next to `terminal_index`, so a later audit can reconstruct the window
without re-deriving N. Report-only field; no behaviour depends on it.

**R10 — Documentation.** §24's C row gains a dated anchor clarification and
§24a's "C — YES — measurement in V1" gains the exact reading
"**routable and reachable; live = may fire on the DAY/H1 wiring**" only after
the implementation task, via the Architect's dated supersession in the §0
register. No card claim changes in this design task.

---

## 5. Non-goals

- **Do not widen or reinterpret the §2 EQH tolerance** (4.5 pips / 0.45 price
  units) for C or for anything else.
- **Do not touch sessions** (§2 20:00–24:00 gap), spread/news gates, or the
  risk envelope.
- **Do not change global `N_BAR_HTF` / `N_BAR_LTF`.** C adapts to §27; §27 does
  not adapt to C. No per-trigger `N` override is introduced.
- **Do not add a confirmation timeframe** to the DAY tier (that is C2, not
  chosen) and do not move C onto `_TIER_ADF`.
- **Do not loosen C3** (`in_between`), the 0.5×ATR zone band, the reclaim
  ordering, or the one-shot rule.
- **Do not touch the F path**, the TP age cap (`A_KEEP`), stop reference
  (`A_KEEP`), or any A/B/D/E behaviour.
- **No D volume proxy, no volume gate change** — D stays OFF.
- **No expectancy, PF, win-rate or edge claim**, and no success criterion
  expressed as money. Success is engineering-only (§7).
- **No threshold fishing**: the 3 bars is not to be raised, the anchor is not to
  be fitted to the three counterfactual signals, and no second constant is to be
  introduced to "make it work".
- **No sub-bot / plugin / multi-engine architecture** — C is one strategy path.

---

## 6. Implement sketch (files only — no code in this task)

| File | Change | Nature |
|---|---|---|
| `04_SRC/smc/triggers/trigger_expiry.py` | Add `ending_diagonal_anchor(terminal_index, timeframe) -> int` (§24 C knowability anchor, `+ N(tf)`), documented as R1/R1a. `window_bars_for`, `signal_expired`, `poi_give_up_bars` untouched. | additive helper |
| `04_SRC/smc/triggers/trigger_c_ending_diagonal.py` | Replace `signal_expired(diagonal.terminal_index, 3, bar)` with `signal_expired(anchor, 3, bar)` where `anchor = ending_diagonal_anchor(terminal_index, confirm_tf)`. Add `known_at` to `data`. Every other gate byte-identical. | 2-line seam |
| *no wiring change* (see trap below) | `trigger_router.evaluate_at` never passes `execution_timeframe` (`trigger_router.py:123-129`), so `TriggerContext.execution_timeframe` is **M5 even on an H1 series**. N must therefore be read from the confirmation swings' own `Swing.timeframe` (set by `detect_swings(share series, ctf)`) — `Timeframe.n_bar_confirmation(context.swings[-1].timeframe)` — **never** from `execution_timeframe`, or C would silently use N=3 on H1 and stay broken. Swings always exist when a diagonal was found (≥ 5 required), so no fallback is needed; a fail-loud assert covers the impossible case. | correctness trap, documented not wired |
| `04_SRC/tests/test_trigger_expiry.py` | Anchor arithmetic table for N=5 and N=3 (legal 0..3 relative to anchor, dead at +4); assert `TRIGGER_C_EXPIRY_EXTRA == 3` and `N_BAR_HTF == 5` are unchanged. | tests |
| `04_SRC/tests/test_trigger_c_ending_diagonal.py` | New reachability test built on **real** `detect_swings` output (today's fixtures inject swings younger than `detect_swings` can produce — that is why the defect was invisible); plus no-fire-before-knowability and dead-after-window tests. | tests |
| `00_LOCKED/LOCKED_DECISIONS.md` | §24 C row dated anchor clarification, §24a reading, §0 register row. Architect-signed dated block. | docs |
| `06_RESEARCH/scripts/branch_c_geometry.py` | Unchanged; re-run as the acceptance harness (its scan is a superset, so a completion there is not a product route). | no edit |

**Explicitly not edited:** `locked_constants.py`, `product_menu_mtf.py`,
`structural_swing_detector.py`, `wave_structure.py` (unless R9's `known_at`
needs the terminal swing's index — it does not; `terminal_index` suffices),
`compatibility_matrix.py`, any A/B/D/E/F trigger, any risk/execution module.

**Revert:** one seam in `trigger_c_ending_diagonal.py` restores today's exact
behaviour (0 completions). No data migration, no state, no config.

---

## 7. Test plan

**Success metrics (engineering only — no PF, no expectancy):**
- **S1 (required):** C completions on the **same frozen window** (exec
  2025-09-01 → 2025-11-30, warm-up 2025-08-01, same composition) **`> 0`**.
  Pre-registered expected range **1 ≤ completions ≤ 3**, because the audited
  expiry-ignored counterfactual produced exactly 3 and C1's legal set is a
  subset of it. `> 3` is a **fail-loud** signal that the anchor is wrong.
- **S2 (optional, reported not scored):** C routes / placed / fills on the same
  window. These pass through the unchanged menu window, risk, session, spread
  and C3 gates; **a completion with 0 routes is a valid outcome** and must not
  be "fixed".

**Tests**

1. **Anchor arithmetic** — table-driven: H1 (`N=5`) terminal `t` → legal
   `t+5…t+8`, dead `t+9`; M15 (`N=3`) terminal `t` → legal `t+3…t+6`, dead
   `t+7`. Includes the boundary pair (`anchor+3` legal, `anchor+4` dead).
2. **Reachability (the regression that matters)** — synthetic H1 series with a
   real ending diagonal detected by `detect_swings`; assert a signal is emitted
   at the first bar the terminal is knowable (age 5), i.e. exactly the state
   that is impossible today.
3. **No-fire-before-knowability** — assert no signal at any `bar` whose prefix
   `detect_swings(series[:bar+1])` does not contain the terminal swing; assert
   the trigger never reads a candle with index `> bar`.
4. **Finite window** — assert nothing fires after `anchor+3` (C does not become
   an unbounded seek).
5. **Pre-sweep gate preserved** — terminal before `from_bar` still yields
   `None` regardless of age.
6. **N-source trap** — evaluate C on an H1 series whose `TriggerContext.execution_timeframe` is left at its M5 default and assert the anchor uses **N=5** (a test that fails loudly if anyone reads `execution_timeframe`).
7. **Frozen pins** — `TRIGGER_C_EXPIRY_EXTRA == 3`, `N_BAR_HTF == 5`,
   `N_BAR_LTF == 3`, `MENU_EXPIRY_BARS == 20`, C stays in `_DAY_TRIGGERS`, C
   stays out of `_TIER_ADF`, C3 still rejects out-of-zone completions.
8. **Regression** — full suite green; A/B/D/E/F trigger tests unchanged and
   passing; `git diff` shows no edit outside the files listed in §6.
9. **Determinism** — the acceptance harness run twice produces identical
   completion counts and identical `(bar, poi, direction, entry)` identities.
10. **Lookahead audit (manual, recorded)** — the diff must contain no use of
   `bar + k`, no whole-series swing detection, and no price read at the anchor
   bar beyond `terminal_index + N` arithmetic. Prefix-only detection stays
   mandatory, as in the TP age-cap measure.

---

## 8. Open questions for Architect

1. **Anchor amendment scope.** Accept a §24 **anchor** clarification for C only
   (C1), or restate it as a numeric formula `N(tf) + 3` (C4)? They produce the
   same legal set; C1 leaves the locked 3 untouched. If the Architect prefers a
   numeric form, C4 is a drop-in.
2. **Conservative bound.** R1a accepts that a §18-rule swing low can lose up to
   one bar of post-visibility life. Accept, or require
   `max(terminal + N, §19 confirmed_index)` (needs the terminal swing's
   confirmed index carried on `Diagonal`, a small read-only addition to
   `wave_structure.py`)? Recommendation: accept R1a in the first cut — it can
   only shorten C, never lengthen it, and keeps the blast radius at three files.
3. **Generality.** Should the knowability anchor be declared a **principle** for
   swing-anchored triggers (B's window is also anchored on a swing chain, but
   30 ≫ 5 so nothing changes today), or scoped to C only? Recommendation: scope
   to C now; record the principle in the §24 note as a future reading.
4. **Card reading.** Approve the §24a wording "routable **and reachable**; live =
   may fire on the DAY/H1 wiring" for the implementation task, so
   `TRIGGER_C_LIVE: YES` stops being read as "can fire" without qualification.
5. **Success criterion.** Confirm `1 ≤ C completions ≤ 3` on the frozen window
   as the engineering acceptance criterion, with routes/fills reported but not
   required (S2). If the Architect wants a fill as the criterion, C must first
   pass the unchanged C3/risk/session gates — that is not guaranteed by C1.
6. **Fallback.** If §24 is not to be amended in this cycle, confirm **C3
   (product-OFF)** as the recorded disposition so the full-book claim stops
   implying a reachable C. C1 and C3 are the only two options that leave the
   tier table and §27 alone.

---

## 9. Governance

- This note is the deliverable; **no production code, no test, no constant and
  no tier table was changed** (`LOGIC_CHANGED: NO`).
- `SESSION_HANDOFF.md`, `POST_V1_ACTIVE_TODO.md`, `CHANGELOG.md` carry a
  design-lock-pending entry.
- **NEXT = Architect accept an option (C1 recommended, C3 fallback) → a separate
  IMPLEMENT task** with the §7 test plan and the same-window re-measure by
  `06_RESEARCH/scripts/branch_c_geometry.py`. No implementation is authorised by
  this note.
