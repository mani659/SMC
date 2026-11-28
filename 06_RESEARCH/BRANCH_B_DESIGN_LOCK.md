# BRANCH B — DESIGN LOCK (Trigger B routability, product path only)

**Status:** DESIGN LOCK — awaiting Architect option acceptance.
**`LOGIC_CHANGED: NO`** · **`CODE_CHANGED: NO`** (design only).
**Recommended option:** **B4 — DEFER product B, no code** (§5), because B1, B2 and
B3 are each **provably insufficient on the measured window** (§3).
**Authority:** Lead Architect *BRANCH B — DESIGN LOCK ONLY*.
**Upstream evidence:** `06_RESEARCH/BRANCH_B_ROOT_CAUSE.md`,
`06_RESEARCH/BRANCH_B_E2E_REPORT.md` (verdict `DEFER_RECOMMENDED`; 5 completions,
5 C3 rejects, 0 routes), `06_RESEARCH/PRODUCT_BRANCH_LIVENESS_REPORT.md` §3.2.
**Window (re-used, not re-picked):** exec 2025-09-01 → 2025-11-30 UTC on M5,
warm-up 2025-08-01.

---

## 1. Problem

B completes and never routes. The whole B path, in one table:

| Step | Code | What it decides |
|---|---|---|
| Tier | `product_menu_mtf.py:239-254` | B ∈ `_DAY_TRIGGERS`, excluded from `_TIER_ADF` → D1→H1 only |
| Pattern | `wave_structure.find_impulse` (+ `_alternating_chain`) | most recent alternating 5-swing chain in the POI's direction |
| Entry | `trigger_b_leading_diagonal.py:55-61` | `entry = wave5 ∓ FIB_MIN × height` (50 %), band 50–61.8 %, `FIB_MIN/MAX` marked **UNFROZEN** |
| Stop | same | `impulse.origin_level` (wave-1 origin) |
| Completion | same | **first close** back into the fib band |
| Validity | `in_between.py` → `pipeline_bridge.candidate_from_route` | C3: the **completion close** must sit inside the POI body (inclusive, no tolerance) |

Measured on the frozen window (one shared signal, five POIs, H1 index 1717):

| Fact | Value |
|---|---|
| Wave-5 / impulse origin | **4244.925** / **4096.845** |
| Height | 148.080 = **7.02 × ATR14** (21.084) |
| Fib band (61.8 % → 50 %) | **4153.412 → 4170.885** |
| Planned entry | **4170.885** |
| Completion close (C3 input) | **4157.639** |

Per POI (from `BRANCH_B_ROOT_CAUSE.md` §4):

| POI | Zone | Close − zone | Entry − zone | Band vs zone |
|---|---|---:|---:|---|
| `poi-004029` | 3940.685–3995.775 | **+161.864** | +175.110 | entirely 157.637 **above** |
| `poi-004092` | 3940.685–3995.775 | **+161.864** | +175.110 | entirely above |
| `poi-004154` | 3940.685–3995.775 | **+161.864** | +175.110 | entirely above |
| `poi-004759` | 4024.295–4137.448 | **+20.191** | +33.437 | entirely 15.964 **above** |
| `poi-004032` | 4127.555–4155.075 | **+2.564** | +15.810 | 1.663-unit **sliver** overlap |

Two anchors, one contract: **B's plan is owned by the impulse; C3's validity is
owned by the POI body.** The design question is therefore not "how do we get C3
to say yes", it is **"which geometry owns a B entry, and is that B still the
trigger R1 describes?"**

---

## 2. What the numbers force (before any option is compared)

Three independent facts decide the option space. All are arithmetic on the table
above; none is a preference.

**F1 — Moving the **entry** cannot satisfy C3.** C3 samples the **completion
bar's close** (`candidate_from_route(completion_price=…)`,
`in_between.py:trigger_in_between`). B's completion is the first close into the
fib band, which is a market fact the trigger cannot choose. Re-anchoring
`entry_price` to the zone changes the *limit*, not the *close*: the close stays
4157.639 / outside, so C3 still rejects 5/5. **B1 (entry re-anchor alone) is
therefore not a fix** — it would only change where a rejected plan would have
been placed.

**F2 — Moving the sampled price does not help either.** The failing prices are
not marginal: the **planned entry** is outside the body in **5/5** cases
(+175.110, +175.110, +175.110, +33.437, +15.810). A gate that compared entry
instead of close would still reject every completion. **B2 (planned-entry
containment) has no evidence base on this window**, and as a *global* rule it
would also weaken C3 for A/C/E/F — banned by the task and by engineering.

**F3 — Re-anchoring the entry would additionally invert the stop for 3 of 5
POIs.** The stop is `impulse.origin_level` = **4096.845**, above three of the
five LONG zones' tops (3995.775). A LONG entry at those zone tops would sit
**101.07 points below its own stop**. So B1 is not merely ineffective — for
`poi-004029/-004092/-004154` it produces an undefined-risk plan. Entry and stop
are a single impulse-owned pair; you cannot move one without the other.

**F4 — B's V1 extraction never checks R1's premise (separate finding, class
(b)).** R1 §7 B is "a 5-wave impulse forms **OUT OF THE POI**". `find_impulse`
takes the most recent alternating chain anywhere in the series; the only POI
link in the trigger is *direction* plus `wave5_index ≥ from_bar`. On this window
the impulse origin (4096.845) is **inside** only one of the five zones
(`poi-004759`, 4024.295–4137.448) and outside the other four — i.e. four B
signals describe an impulse that never started at the POI. That is a genuine
spec-vs-code gap, but fixing it **reduces** signals and cannot create a route
(§3). It is recorded here because it is the first rule any routable form of B
must carry.

---

## 3. Options

| # | Option | What changes | Would it route B on this window? | Verdict |
|---|---|---|---|---|
| **B1** | B-specific entry anchor into the POI zone (FR-3.1-style: `zone_anchored_entry`, entry = proximal edge) | entry only | **No.** C3 samples the close (F1), so 5/5 still reject; and 3/5 stops invert (F3) | **KILLED by evidence** |
| **B2** | C3 scope: containment of the planned entry instead of the completion close (B-only) | the gate's sampled price | **No.** The entry is outside the body in 5/5 (F2). Globally it weakens C3 for every branch | **KILLED by evidence** (and banned globally) |
| **B3** | Admission filter: require the fib band to intersect the POI body | which completions are emitted | **No.** Keeps only `poi-004032` (1.663-unit sliver), whose actual close still missed the body by **+2.564** → C3 rejects → 0 routes | **KILLED as a routability route** (valid as an admission filter, not a fix) |
| **B4** | **DEFER product B — no code**; record it as signal-only by construction and correct the claim | nothing | **No, by design** — and it stops asserting that B is a live product branch | **RECOMMENDED** (§5) |
| **OTHER — B5** | **Zone-owned B plan**: premise gate (origin at POI) + entry at the POI proximal edge + completion = first close inside the body + stop re-based | entry, stop, completion, premise — B's whole trade definition | **Possibly**, unmeasured; needs its own acceptance run | **Not recommended in this cycle** — it is a *new trade definition*, not a repair (§6) |

**Why B3 is still worth recording.** As an *admission filter* it is honest and
cheap: it would have suppressed 4 of the 5 plans that could never satisfy C3, at
the cost of nothing (it cannot create a fill). It belongs in B5's first rule, not
in this cycle's scope.

---

## 4. The decision principle used here

C1 was accepted because it repaired an **arithmetic contradiction between two
frozen rules without touching the trade**: same entry, same stop, same edge —
only the instant the validity clock starts. Its blast radius was one branch, and
its success metric (`completions > 0`) was a direct consequence of the repair.

B has **no such repair available**. Every option that makes B routable changes
*what B trades*:

- entry ownership moves from the impulse to the POI (and with it the whole
  risk/reward shape), or
- C3's validity contract changes for every branch, or
- B is replaced by a zone-retracement trigger that merely reuses its wave chain.

That is an **edge decision**, not an engineering one. It also cannot be
validated the way C1 was: C1's target (3 completions) was already known from the
audited counterfactual; B5 has **no measured route count** at all, so its success
would have to be measured *after* the definition is adopted — the wrong order for
a design lock.

---

## 5. RECOMMENDED: B4 — DEFER product B (no code)

**Statement.** B stays implemented, registered and evaluated exactly as today;
the programme stops treating it as a live product branch. It remains *signal-only
by construction*: on this window its completions are arithmetically outside the
POI body, and C3 rejects them for the reason the card requires.

**Normative rules (B4).**

- **R1 — No code.** `_DAY_TRIGGERS`, `_TIER_ADF`, `PRODUCT_MENU_TIERS`, the B
  trigger, `FIB_MIN/MAX` (UNFROZEN), C3, `in_between.py`,
  `candidate_from_route`, `ZONE_REFINEMENT_ATR`, sessions, EQH, risk and
  execution are all unchanged. Nothing in `04_SRC` is touched.
- **R2 — Claim correction.** Every product statement reads: B is *implemented and
  routable in principle*, **not** a filling branch; its 5 completions on the
  frozen window are rejected by the frozen C3 contract, and no B route or fill
  exists in it.
- **R3 — B stays evaluated.** Removing B from the DAY tier is **not** part of
  B4: a future completion whose close genuinely lands in the POI body (the
  `poi-004032` sliver class) may still route, and that remains correct behaviour.
  B4 forbids *claiming* it, not *running* it.
- **R4 — Optionality preserved.** If the Architect later wants a routable B, that
  is **B5**, commissioned as a new strategy-definition task with its own design
  lock, its own pre-registered window and its own success metric — never as a
  "repair" of this branch.
- **R5 — No gate is to be loosened now.** Not C3, not the fib numbers (already
  UNFROZEN), not the zone band, not the tier map, not the ONE-STORY rule.
- **R6 — F is untouched.** B4 is B-only; F stays LIVE with its 21 fills.
- **R7 — Reversal is trivial.** Because B4 changes nothing, "un-deferring" B is a
  documentation act, not a code revert.

**Lookahead safety:** **N/A** — B4 introduces no code and no sampled price, so
there is nothing that could read a future bar. (B5 §6 carries its own argument:
every new quantity would be a function of the completion bar and earlier.)

**Blast radius:** zero source lines. Interactions:

| Thing | Effect of B4 |
|---|---|
| C3 `in_between` | unchanged, still the single choke point, still rejects B 5/5 |
| One-shot episodes | unchanged — an earlier F win still consumes the POI (`_win` → `_consumed`) |
| F path | unchanged; B never competes with an F-won episode |
| A / C / E / D | unchanged (A DEFER, C REACHABLE_NOT_LIVE, E DARK_IN_WINDOW, D OFF) |
| Card / expert claims | **corrected** — this is the only deliverable |

**Success for B4** is documentary: the full-book claim stops implying a routable
B, and the record states the three measured reasons (F1/F2/F3) why the branch
cannot be routed without a new trade definition.

---

## 6. If the Architect later wants a routable B (B5 — sketch only, not authorised)

Recorded so the future task starts from the measurements, not from scratch. **Do
not implement.**

| Rule | Normative content | Reuses |
|---|---|---|
| R1 premise gate | `impulse.origin_level` must lie within `[zone.bottom − band, zone.top + band]`, `band = ZONE_REFINEMENT_ATR × ATR` (frozen §13) — enforces R1's "impulse forms **out of** the POI" (finding F4). On this window it would keep **1** of 5 (`poi-004759`) | `atr_band_half_width` (C/E/F already use it) |
| R2 entry ownership | entry = POI proximal edge (`zone_anchored_entry`): LONG → `zone.top`, SHORT → `zone.bottom` | frozen FR-3.1 helper, no new number |
| R3 completion | first close **inside the POI body** after Wave 5 (replaces "first close into the fib band") — makes C3 satisfiable **by construction** while leaving C3 itself untouched | `trigger_in_between` semantics |
| R4 stop | `structural_sl(impulse.origin_level)` when the origin is beyond the entry in the trade's direction; otherwise the POI distal edge with the same `FR2_SL_BUFFER_ATR = 0.3 × ATR` | both helpers already exist |
| R5 fib band | becomes **context only** (already exported in `signal.data`) | — |
| R6 expiry | `TRIGGER_B_EXPIRY = 30` from Wave 5, unchanged | §24 |

**Lookahead safety (B5):** every new quantity is a function of the completion bar
and earlier — origin level is a swing already in the closed-prefix list, the zone
is known at arm time, and the completion test reads `candles[bar].close`. No
`bar + k` read, no full-series detection.

**Honest cost of B5:** it is a *different trade*. Entry moves from the 50 %
retracement to the zone edge (up to 175.11 points deeper here), the stop's
reference changes for 4 of 5 POIs, and the fib band no longer places the order.
Its acceptance metric must be **B routes ≥ 1 on the frozen window with C3, the
tier map and F untouched**, and fills reported only — no PF/expectancy. It may
still measure 0 routes (the premise gate leaves one POI, whose close is not
guaranteed to land in the body), which is why it needs its own go/no-go ruling
before any code.

**Implement sketch for B5 (planning only):** `trigger_b_leading_diagonal.py`
(premise gate + zone entry + in-body completion + stop rebase), `04_SRC/tests/
test_trigger_b_leading_diagonal.py` (premise keep/reject, entry/stop geometry,
in-body completion, C3 agreement), `06_RESEARCH/scripts/branch_b_geometry.py`
(new rule → route count; fail-loud if C3 rejects a completion whose close is
inside the body), `LOCKED_DECISIONS` §22/§24c dated block, governance. **No
`locked_constants.py`, no C3, no tier edit.**

---

## 7. Non-goals

- **No `ZONE_REFINEMENT_ATR` widening** (0.5 stays), no new tolerance anywhere.
- **No deletion, scoping or loosening of C3** — not for B, not globally.
- **No B-only C3 exemption**, no `if trigger is B: skip` branch.
- **No change to `FIB_MIN`/`FIB_MAX`** (UNFROZEN ≠ free), no fib retune to move
  the band onto a zone.
- **No tier change** (no C2-style re-wiring; B stays DAY-only), no `_TIER_ADF`
  edit, no M15/M5 confirmation for B.
- **No expectancy, PF, win-rate or edge claim**; success is a route count.
- **No D volume proxy, no sub-bot / multi-engine architecture.**
- **No re-opening A, C, E or D** — C stays REACHABLE_NOT_LIVE, D OFF.
- **No counterfactual fills**, no force-routing of the five measured completions.

---

## 8. Open questions for Architect

1. **Accept B4 (defer + claim correction, no code)?** If not, B5 is the only
   construct that can route B, and it needs a definition ruling first (§6).
2. **Is B's intended trade the fib retracement (impulse-owned, signal-only under
   C3 by construction) or a POI retracement (zone-owned)?** The entire option
   space turns on this one sentence; R1 §7 says "50–61.8 % retracement", the POI
   contract says the zone owns the thesis.
3. **Finding F4** — should the premise gate (impulse originates at the POI) be
   repaired **independently** of routability? It is class (b) and would suppress
   4 of 5 measured signals. Recommendation: only inside B5, so it is not a
   standalone behaviour change now.
4. **Card wording** — approve: "B implemented and routable in principle;
   signal-only on the frozen window (5 completions, all C3-rejected)". This is
   the B4 deliverable.
5. **If B4 is accepted**, confirm the full-book line becomes
   **F LIVE · A DEFER · B SIGNAL_ONLY (deferred) · C REACHABLE_NOT_LIVE ·
   E DARK_IN_WINDOW · D OFF**.

---

## 9. Governance

- Deliverable: this note. **No production code, no test, no constant, no tier
  table, no C3 edit** (`LOGIC_CHANGED: NO`).
- `SESSION_HANDOFF.md`, `POST_V1_ACTIVE_TODO.md`, `CHANGELOG.md` carry a
  design-lock-pending entry.
- **NEXT = Architect accept B4 (or commission B5 as a new definition task) →
  then the formal D OFF note + full-book scorecard.** No B implementation is
  authorised by this note.
