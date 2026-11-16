# BCE STARVATION PROBE — why B, C, E never become filled plans

**Status: measurement only — DIAGNOSTIC PROBE, NOT a fix and NOT a trade claim.**
No strategy edit; no matrix/threshold/C3/TP/SL/pillar/trigger change;
`locked_constants.py` read-only (diff empty). Production code imported, never
reimplemented. D is out of scope except one line: **D (Two-Bar Reversal) is
structurally dead on the zero-volume feed** (frozen volume gate
`engulfer.volume < engulfed.volume` with every bar volume = 0.0 — see Scan 1 §2).

---

## 1. Window + method + enum definitions

**Window:** exec 2024-11-01 → 2025-10-31 UTC (full days, phase3 exec-to
convention), load from 2024-09-01 — identical to Scan 1 / product_1y.

**Method (join-first, replay where the artifacts are silent):**
1. **POI-linked B/C/E completions** reused from Scan 1B events
   (185 B / 12 C / 21 E = 218 occurrence rows over 3,731 armed POIs) — no
   full re-detection.
2. **Gate 1 — menu tier scope (static, code-verified):** each armed record's
   `detection_tf` selects the menu tier; the tier's confirmation router is
   built from `tier.trigger_types`. M15/H1/H4 tiers carry
   `_TIER_ADF = (A, D, F)`; **only the DAY tier (D1 detection → H1
   confirmation) carries all six triggers** (`_DAY_TRIGGERS`). B/C/E
   completions on non-D1 POIs are structurally unconfirmable.
3. **Gate 2..5 — D1-subset replay:** for the D1-detected POIs hosting B/C/E
   completions, the product menu machinery is replayed offline per involved
   segment with the EXACT product_1y wiring: `ProductMenuEngine`
   `same_bar_asof=False`, **no §5 state resolver (verified — the product_1y
   harness never wires one)**, `MENU_WARMUP_BARS = 300` warmup cursor,
   closed-prefix feed per M5 execution bar, DAY-tier streams (D1 detection +
   H1 confirmation; other tiers' streams are never read by a D1 episode, so
   their omission is state-identical). The DAY router carries ALL SIX
   production triggers behind an evaluate-logging wrapper. Armed D1 POIs are
   registered with real zone bounds and `armed_ts` from the armed records.
   - **Direction:** armed records export no direction and the sweep predicate
     plus every trigger read `zone.direction` — each segment is replayed TWICE
     (LONG / SHORT hypotheses). A reason that agrees across both is
     direction-robust; disagreement is `DIRECTION_AMBIGUOUS`, never guessed.
   - **Upper bound:** with no state resolver the replay cannot be blocked by
     §5 state — it is an UPPER BOUND on menu confirmations; the product could
     only confirm fewer.
4. **1A-only rows:** every Scan 1A B/C/E completion NOT matched (exact
   `trigger + direction + bar_time_utc` join) to any Scan 1B POI-linked row is
   `NO_POI_LINK` — expected by construction (no armed window contains it).

**Primary-reason enum (fixed; product gate order; one reason per row):**

| Reason | Definition |
|---|---|
| `MATRIX_BLOCKED` | §15 matrix forbids the (model, trigger) pair — **impossible by construction**: every frozen cell is allowed (grade = same-bar tie-break only). Reported as 0 with the per-row grade as a secondary tag. |
| `MENU_TIER_EXCLUDED` | B/C/E absent from the detection tier's confirmation router (M15/H1/H4 tiers = `_TIER_ADF`). First hard gate for non-D1 POIs. |
| `NO_SWEEP_NO_EPISODE` | No post-arm R2 zone sweep opened a one-shot window within `MENU_EXPIRY_BARS = 20` D1 bars (includes F5 pre-arm blocks and F2 stale-window blocks — noted). |
| `EPISODE_NO_CONFIRMATION` | Window opened; **no B/C/E completion on H1** inside it (the M5 completion is never read by the menu — M5 geometry ≠ H1 confirmation geometry). |
| `CONFIRMED_OTHER_TRIGGER` | Window WON by A/D/F — the POI is consumed (one-shot); B/C/E never completed, or completed and was C3-rejected first (then `BCE_C3_REJECTED` wins precedence). |
| `BCE_C3_REJECTED` | A B/C/E route reached `_win` and the frozen C3 in-between gate rejected it (`candidate_from_route` returned None; episode stayed ACTIVE). |
| `BCE_WON_NO_FILL` | Replay produced a B/C/E winner but the product never filled that POI — downstream one-story/submit/place seam; **per-POI placement flags are not exported** (guard drop vs submitted-unplaced vs placed-unfilled indistinguishable; 580/33/13 aggregate). |
| `DIRECTION_AMBIGUOUS` | LONG/SHORT replay hypotheses disagree — DATA_GAP class, never guessed. |
| `NO_POI_LINK` | 1A-only completion outside every armed window (counted separately from the POI-linked main table). |
| `OTHER_DATA_GAP` | Anything unmappable — must carry a note; kept rare. |

## 2. Headline table: B/C/E × primary_reason (POI-linked only)

218 POI-linked occurrence rows (B 185 / C 12 / E 21), one primary reason each:

| Reason | B | C | E | Total |
|---|---|---|---|---|
| `MATRIX_BLOCKED` | 0 | 0 | 0 | 0 (impossible by construction) |
| `MENU_TIER_EXCLUDED` | **144** | **10** | **19** | **173 (79.4%)** |
| `NO_SWEEP_NO_EPISODE` | 27 | 0 | 1 | 28 |
| `EPISODE_NO_CONFIRMATION` | 3 | 0 | 0 | 3 |
| `CONFIRMED_OTHER_TRIGGER` | 3 | 0 | 0 | 3 |
| `BCE_C3_REJECTED` | 0 | 0 | 0 | 0 |
| `BCE_WON_NO_FILL` | 0 | 0 | 0 | 0 |
| `DIRECTION_AMBIGUOUS` | 8 | 2 | 1 | 11 |
| **Total** | **185** | **12** | **21** | **218** |

- `MATRIX_BLOCKED` = 0 BY CONSTRUCTION: every §15 (model, trigger) cell is
  allowed; the grade only breaks same-bar ties. Secondary grades observed:
  structural 167 / uncommon 41 / preferred 10 (the preferred cells are
  M8 × C — the expert's preferred pairing — which still never confirms).
- `BCE_C3_REJECTED` and `BCE_WON_NO_FILL` = **0 across the entire year**: not
  once did a B/C/E completion become an H1-level confirmation on the DAY tier
  for any of the 43 POIs hosting them. The C3 gate and the post-menu seam
  were never even reached by B/C/E.
- The 11 `DIRECTION_AMBIGUOUS` rows sit entirely inside the D1 subset (the
  replay outcome depends on the unexported direction). Direction-robust meta
  conclusion: under BOTH hypotheses, no B/C/E confirmation materialized —
  direction only decides WHICH upstream gate fired (sweep vs window-win).

## 3. 1A-only share (NO_POI_LINK) — expected vs surprising

356 of the 485 1A B/C/E completions (73.4%) match no armed-POI window:

| Trigger | 1A completions | NO_POI_LINK | Share | POI-linked occurrences |
|---|---|---|---|---|
| B | 267 | 170 | 63.7% | 185 |
| C | 75 | 63 | 84.0% | 12 |
| E | 143 | 123 | 86.0% | 21 |

- **Expected:** most M5 structure fires where no product zone story is armed —
  the product arms only validated stories (3,731 armed POIs over a year of
  70,885 M5 bars), so the majority of detector activity necessarily has no
  POI link. This is the baseline condition, not a defect.
- **Surprising (the real finding):** even the linked minority — completions
  that DID land inside an accepted zone story's confirmation horizon —
  produced **zero fills**, and §2 shows why: they were admitted to no
  confirmation machinery at all.

## 4. Dominant gate per letter

- **B — MENU_TIER_EXCLUDED (144/185, 77.8%).** B is confirmable only on the
  DAY tier (D1 detection → H1 confirmation); the H4/H1/M15 tiers' routers
  carry A/D/F only. For the 41 B rows that DID sit on D1 POIs: 27 windows
  never opened (no post-arm R2 sweep — includes F5 pre-arm blocks), 3 opened
  but saw no B completion on H1, 3 were won chronologically by A/F, and 8
  were direction-ambiguous — **zero B confirmations on H1 anywhere**.
- **C — MENU_TIER_EXCLUDED (10/12, 83.3%).** The two D1 rows are
  direction-ambiguous (no C confirmation under either hypothesis).
- **E — MENU_TIER_EXCLUDED (19/21, 90.5%).** The two D1 rows: one window
  never opened, one direction-ambiguous. No E confirmation on H1.

The same M5 geometry that fires freely without a POI (1A) is, once attached
to a product story, almost always parked on a detection tier whose
confirmation router does not contain the trigger at all.

## 5. Matrix vs lifecycle vs fill — which family dominates

| Family (gates) | Rows | Share of 218 |
|---|---|---|
| **Admission (matrix + menu tier scope)** | 173 | **79.4%** |
| **Lifecycle (sweep/episode → H1 confirmation)** | 34 | 15.6% |
| **Fill seam (C3, post-menu guard/place)** | 0 | 0.0% |
| Direction-ambiguous (inside D1 subset) | 11 | 5.0% |

The starvation is an **admission gate, not a fill seam**: B/C/E die before
confirmation machinery ever evaluates them. The contrast with the triggers
that DO fill — confirmable on every tier — makes the mechanism plain:

| Trigger | POI-linked occurrences by POI detection tier | Confirmable tiers | Fills (detection TF) |
|---|---|---|---|
| F | D1 572 / H1 547 / H4 387 / M15 600 | **all four** | 226 (M15 157 / H1 30 / H4 33 / D1 6) |
| A | D1 55 / H1 31 / H4 41 / M15 29 | **all four** | 13 (M15 4 / H1 7 / H4 2 / D1 0) |
| B/C/E | D1 only (41 / 2 / 2) | **DAY only** | 0 |

F and A spread their confirmations across every detection tier; B/C/E can
only ever ride the smallest tier (6 of 239 fills are D1-detected, all F) —
and even there they lost every window to chronological A/F completions or
never completed on H1. The §15 matrix never blocked anything (grade is a
tie-break only); the tier router construction is where B/C/E are excluded.

## 6. Samples

13 narrative timelines (≤15 cap) covering every observed (trigger, reason)
combination, in `06_RESEARCH/results/bce_starvation/samples/` (JSON; D1-subset
samples carry `arm_ts` and, where a window opened, `sweep_ts`):

| Sample | Trigger | Reason | What it shows |
|---|---|---|---|
| 01 / 04 / 06 | B / C / E | `MENU_TIER_EXCLUDED` | M15/H1/H4-detected POIs — the tier's confirmation router carries only A/D/F; the completion is structurally unconfirmable regardless of direction. |
| 02 / 07 | B / E | `NO_SWEEP_NO_EPISODE` | D1 POIs whose zone never produced a post-arm R2 sweep inside the 20-D1-bar expiry (F5 pre-arm blocks included). |
| 03 | B | `EPISODE_NO_CONFIRMATION` | Window opened (sweep 2024-11-26) but no B completion on H1 inside it — the M5-level B completion is not the menu's confirmation geometry. |
| 05 | B | `CONFIRMED_OTHER_TRIGGER` | Window opened (sweep 2024-12-20) and was WON on H1 by another trigger — the POI is consumed one-shot. |
| 08 / 09 / 10 | B / E / C | `DIRECTION_AMBIGUOUS` | Replay hypotheses disagree on which gate fired; under BOTH hypotheses no B/C/E confirmation materialized. |
| 11 / 12 / 13 | C / E / B | `NO_POI_LINK` | 1A-only geometry — no armed window contains the completion (baseline condition). |

Full row-level evidence: `starvation_rows.csv` (574 rows: 218 POI-linked +
356 1A-only, with grade, detection TF, model tags, arm/sweep timestamps where
applicable). Counters and per-segment replay metadata:
`summary.json`.

**Residuals (documented, not assumed away):**
- The claim "no B/C/E confirmation on H1" is measured over the 43 target
  POIs' opened windows (the menu only evaluates confirmations inside opened
  windows) — not a global H1 census of B/C/E geometry.
- `m8_kind` is not exported by the armed records; replay POIs carry
  `m8_kind=None`. The §15 grade (secondary tag) is unaffected; no trigger
  `evaluate` reads `m8_kind`.
- Per-POI placement flags are not exported by product_1y artifacts, so a
  replay B/C/E winner could not be split guard-drop / submitted-unplaced /
  placed-unfilled — moot at 0 winners, stated for completeness.
- `NO_SWEEP_NO_EPISODE` does not split F5 pre-arm blocks from genuinely
  absent sweeps per row (menu counters are aggregate; the replay counters
  show F5 pre-arm blocks dominate the blocked-sweep class).
- Charts: none produced — every observed gate is structural/static (tier
  router composition, sweep absence, window won by another trigger); no
  chart clarifies them beyond the timeline samples.

## 7. Explicit non-goals

This probe makes **no fix, no expectancy claim, no ship recommendation**, and
changes nothing: no production `smc/` code, no compatibility matrix cell, no
threshold, no TP/SL, no filled-trade fabrication, tests untouched. The tier
scope (`_TIER_ADF` / `_DAY_TRIGGERS`), the R2 sweep discipline, C3, the
one-story guard, and `MENU_EXPIRY_BARS` are LOCKED product law — observed
here, never loosened.

**D footnote (one line):** D = Two-Bar Reversal is structurally dead on the
zero-volume feed (frozen volume gate; every bar volume = 0.0) — it can never
fill anywhere and is excluded from this probe.

**NEXT = Architect review → Scan 2 stop/MAE autopsy on the 239 fills → demo.**
