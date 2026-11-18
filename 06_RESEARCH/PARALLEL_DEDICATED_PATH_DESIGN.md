# PARALLEL DEDICATED CONFIRMATION PATHS — DESIGN (proposal, no production change)

**Status: DESIGN ONLY — `LOGIC_CHANGED: NO`.** No production default menu change, no new live
trading code, no parallel engine, no threshold/SL/TP/matrix edit. `locked_constants.py` diff
empty; suite untouched. Every as-coded claim below is read from the shipped modules with file
+ line citations; every number is quoted from R0 / R1 / BCE probe, not invented.

**Inputs (read, not re-argued):** `06_RESEARCH/R0_TRIGGER_ADMISSION_MAP.md`,
`06_RESEARCH/R1_PURE_TAG_BOOKS_REPORT.md`, `06_RESEARCH/BCE_STARVATION_PROBE_REPORT.md`,
`04_SRC/smc/orchestration/product_menu_mtf.py`, `04_SRC/smc/backtest/pipeline_adapter.py`,
`04_SRC/smc/risk/risk_engine.py`, `04_SRC/smc/execution/order_manager.py`.

**One-sentence thesis:** the product is intended to be *multi-context* (a diagonal, a
divergence and a BOS/OB are different market contexts, not rival answers to one question), but
it is currently *single-winner* (one shared menu, one chronological winner, one shared story
slot) — so the fix is **dedicated confirmation paths that trade in parallel**, not a wider
alphabet on the same menu.

---

## 1. Problem restatement

Two mechanisms, both as-coded, produce the observed behaviour.

### 1.1 The admission gate (which tags are even evaluable)

`ProductMenuEngine` builds each tier's confirmation router from `tier.trigger_types`
(`04_SRC/smc/orchestration/product_menu_mtf.py` L228-235 `MenuTier`; tier table L238-250;
router construction via `_router_for` L375-378). Detection-TF → tier is `_TIER_BY_DETECTION`
(L262, read by `tier_for` L424); `register_armed` (L450-486) returns `False` for a POI whose
detection TF has no tier.

| Tier | Detection | Confirmation | Menu (as-coded) |
|---|---|---|---|
| `DAY` | D1 | H1 | A, B, C, D, E, F (`_DAY_TRIGGERS = tuple(TriggerType)`) |
| `H4` | H4 | M5, M15 | A, D, F (`_TIER_ADF`) |
| `H1` | H1 | M5, M1 | A, D, F |
| `M15` | M15 | M1 | A, D, F |

Consequence: **B, C and E exist only on the smallest tier.** Measured first gate
(`BCE_STARVATION_PROBE_REPORT.md` §2, §5): `MENU_TIER_EXCLUDED` = 173/218 POI-linked rows
(79.4 %) — B 144/185, C 10/12, E 19/21 — versus 0 `MATRIX_BLOCKED` (the §15 matrix never
blocks; grade is a same-bar tie-break only) and 0 reach-fills at the C3/place seam.

### 1.2 The chronological race (why a tag that *is* evaluable still loses)

Three layers, all frozen product law, all *single-winner by construction*:

1. **Inside one confirmation TF** the router evaluates bar-by-bar from the arm; the first bar
   at which any eligible trigger fires wins (`trigger_router.py` L1-18). Same-bar ties use the
   §15 grade, then earlier trigger letter.
2. **Across confirmation TFs of a tier**, `confirmation_order_key` picks truncation-order:
   earliest completion instant, then lower TF, then stable route id
   (`product_menu_mtf.py` L111-123, applied L589-606).
3. **POI consumption is one-shot.** A win consumes the episode and the POI (`_win`,
   `_consumed`), and one-story is claimed at intake
   (`backtest/pipeline_adapter.py` L324 `_duplicate_story`, L361 `queue_menu_candidate`,
   L656 `on_candidate_accepted`; claims follow the live book via
   `story_live_plans`, L249 `_live_story_keys`).

So A/D/F — the letters present on *every* tier — win chronologically against B/C/E even where
B/C/E are evaluable, and a sealed plan blocks an identical plan until it stops living. That is
the race: **fast, ubiquitous tags consume the episode slot before a context-specific tag can
confirm.**

### 1.3 Why "widen the alphabet" is the wrong fix

Adding B/C/E to `_TIER_ADF` would (a) be a production default change, and (b) merely inject
B/C/E into the *same* chronological race against A/F, on the same one-shot episode, with the
same single story slot. R1's controlled counterfactual shows the tags only realise confirmations
when alone: **B/MID 1,005 window wins from 0 in production**, while the fully-permissive DAY
tier completes B/C/E **0 times in 270 windows**. The gate is selection *between* tags, not
permission *for* a tag.

### 1.4 Expert intent (why "one winner" is wrong for this product)

The expert flowcharts describe independent multi-context setups: a leading diagonal (B), an
ending diagonal (C), an RSI divergence (E), a CHoCH (A) and a BOS+OB (F) are *different reasons
to be in the market*, tracked on different structure, often in opposite directions at different
times. Treating them as five candidates for one slot imports a single-hypothesis discipline into
a multi-hypothesis design. The product "functions as intended" when each context has its own
path and its own book, and only the risk *envelope* is common.

---

## 2. Evidence table — R0/R1 (pure MID vs production)

R1 method (`R1_PURE_TAG_BOOKS_REPORT.md` §2): runtime-only tier injection
(`MenuTier(..., trigger_types=(T,))`) into `ProductMenuEngine` per worker process, restored on
exit; shipped tier table and `locked_constants.py` untouched; 3,731 armed POIs; exec
2024-11-01 → 2025-10-31; two direction hypotheses per non-filled POI, true direction for the 239
filled POIs; one-story AS-CODED; trigger purity fail-loud `{T: 100%}`.

| Tag | Production fills (year) | D1-tier wins / routes / fills | **MID-tier wins / routes / fills** | MID fill detection-TF mix | Median hold (bars) |
|---|---|---|---|---|---|
| **B** | **0** | 0 / 0 / 0 | **1,005 / 838 / 264** | M15 168 · H1 67 · H4 29 | 1 |
| **C** | **0** | 0 / 0 / 0 | **945 / 795 / 219** | M15 156 · H1 54 · H4 9 | 0 |
| **E** | **0** | 0 / 0 / 0 | **780 / 646 / 183** | M15 116 · H1 54 · H4 13 | 1 |
| A (control) | 13 | 21 / 21 / 0 | 422 / 358 / 64 | M15 26 · H1 22 · H4 16 | 2 |
| F (control) | 226 | 107 / 98 / 14 | **1,270 / 1,034 / 374** | M15 250 · H1 70 · H4 54 | 0 |
| D | 0 (structurally dead: zero-volume feed) | — | — | — | — |

Also from R1:

- **Cross-tag leak: NO** — every pure book's filled-trade trigger mix was `{T: 100%}`.
- **One-story absorption is material and as-coded**: duplicate-story drops per MID book
  B 582 · C 566 · E 452 · A 302 · F 616 (summed over hypotheses). Under a *shared* guard this
  is exactly the cross-tag kill this design removes.
- **Anchor fidelity**: 237/239 production fills reproduced as fills in the LONG∪SHORT
  production replay; zero missing-without-window-win; the 2 remaining were blocked downstream
  (circuit breaker tripped by hypothesis artifacts; one identical-plan queue-order attribution).
- **Runtime hazard**: MID M1-confirmation rescan is super-linear in active episodes; single
  runs up to 14,500 s, 18.9 h wall for the full matrix. Any parallel-book runtime needs a
  budget/caching plan (§6 phase 2).
- **Data gap**: armed records export no `direction`; R1 inferred per hypothesis. A production
  parallel path needs the direction at the arm seam (open ruling R-J).
- Fill counts are **upper bounds** (two-hypothesis union) — the claim they support is
  *existence and magnitude of confirmable flow per tag*, not an expectancy.

**Reading:** every starved tag has a large, confirmable, structurally distinct flow that the
current single menu cannot reach. That is the design's justification; it is not an edge claim.

---

## 3. Target architecture

### 3.1 Book definition

A **book** is the unit of independence. Immutable, data-only, no logic:

```
Book = (symbol, tag, detection_tier_set, confirm_tf_map)
```

| Field | Meaning | Example |
|---|---|---|
| `symbol` | one instrument per book (single-symbol discipline preserved) | `XAUUSD` |
| `tag` | exactly ONE `TriggerType` — the book's confirmation letter | `B_LEADING_DIAGONAL` |
| `detection_tier_set` | which `MenuTier`s this book carries (subset of the four) | `{H4, H1, M15}` |
| `confirm_tf_map` | per detection tier, the confirmation TFs (must equal the shipped tier's `confirmation_tfs` for that tier — the book may not invent confirmation geometry) | H4→(M5,M15), H1→(M5,M1), M15→(M1) |

Book identity is `(symbol, tag)`; the tier set is a *configuration* of that book, so a book can
be re-scoped (e.g. add `DAY`) without minting a new book id. `expiry_bars` and every other
window parameter are inherited **as-coded** from `MenuTier` — the book does not carry its own
thresholds (see §5).

Constructed originally from the shipped tier table:

```text
Book(symbol, tag=T, detection_tier_set=S, confirm_tf_map={tier.detection_tf: tier.confirmation_tfs
                                                           for tier in PRODUCT_MENU_TIERS if tier in S})
```

and the per-book menu is the shipped `MenuTier` with `trigger_types=(T,)` — exactly the object
R1 injected, promoted from runtime patch to configuration.

### 3.2 Parallelism rules

1. **One menu instance per book.** `ProductMenuEngine` is already instance-scoped; each book
   owns its own episodes, armed map and `_consumed` set. No shared router.
2. **Independent intake queue per book.** Each book feeds its own
   `queue_menu_candidate`/intake path so one book's queue depth cannot starve another's.
3. **No cross-book episode arbitration.** Book A never sees book B's episodes: the
   `confirmation_order_key` race and the one-shot `_consumed` rule remain **inside** a book
   (they are correct there — one tag, one context) and are **structurally absent between** books.
4. **Shared clock and shared feed.** All books consume the same closed-bar feed and the same
   `now`. Parallelism is about *decision independence*, never about different market data.
5. **Deterministic bar order.** Within one execution bar, books are processed in a fixed
   order (stable `tag` order) so journals replay identically; the order must not influence
   risk outcomes (see §3.4).
6. **No parallel process per book for the first implementation.** One process, N book objects.
   A process-per-book design is explicitly out of scope (it would fragment the risk envelope
   and the heartbeat/liveness contract).

### 3.3 One-story scope — recommend **per-book**

**Recommendation: one-story is a per-book rule.** Justification:

1. **Intent.** One story = "this book already has this plan live". Two different tags holding
   the *same* plan are two different contexts confirming the same trade; that is a
   confluence, not a duplicate. Collapsing them across books restores the single-winner
   discipline the design exists to remove.
2. **Measured impact.** R1's shared, as-coded guard absorbed 302–616 duplicate winners *per
   MID book*. Under a global guard, the F book (1,270 wins) would consume the slot ahead of
   every other book by chronology — reproducing the production starvation inside the new
   architecture. Under per-book scope, each book keeps its own flow.
3. **Accounting.** Per-book claims make `duplicate_story_*` counters attributable per tag,
   which is what makes journals readable (§8).

**But per-book story scope does NOT mean per-book *tickets*.** Two books can, and in R1 do,
confirm the **identical executable plan** (same POI, direction, entry, SL, TP, instant). That
must not become two orders. The design therefore separates:

- **Story scope = per book** (decides whether *this* book may take *this* plan).
- **Plan identity de-duplication = cross-book** (decides whether the *account* may hold this
  plan twice). Reuse the existing plan-identity machinery (`story_key`/`same_story`) as a
  cross-book gate that either (a) suppresses the second ticket and records a
  `cross_book_duplicate` counter, or (b) allows it and sizes the aggregate — **open ruling
  R-H**.

### 3.4 Shared risk envelope

Risk is **one portfolio envelope**, not per-book tournaments. Recommended composition, all
existing components, no new thresholds:

| Component | Scope | Rationale |
|---|---|---|
| Circuit breaker (`risk_engine.py` L220, `record_result` L399) | **shared** | It models the account's losing streak, not a tag's; per-book breakers would multiply account risk by book count |
| Daily loss / max daily losses / max trades/day | **shared** | Account-level limits; F4 (risk-envelope ruling) still outstanding and is a *precondition*, not part of this design |
| Max DD cooldown, consecutive-loss backstop | **shared** | Same reason |
| Same-level / sweep guard (`risk/same_level_guard.py`, `risk/sweep_guard.py`) | **shared** | They are symbol-level price memory, not tag memory; splitting them would let two books take the same level twice |
| Sizing | **shared pool**, per-book attribution | One capital base; each book's exposure is reported, not separately funded |
| Magic / comment identity | **per book** (proposal) | Statements must show which context traded: magic offset `base + book_index` and a comment prefix `SMC-<TAG>-…` (`execution/order_manager.py` L65 `comment`, L93 `magic`) — **open ruling R-D**, because changing magic changes existing statement/EA expectations |

Ordering rule that keeps the envelope deterministic: **risk is evaluated in fixed book order
inside a bar, and the envelope is checked once per candidate against the post-previous-book
state**, so a bar's outcome does not depend on feed arrival order. Contention is counted
(`books_blocked_by_envelope`), never silently dropped.

### 3.5 Conflict policy — opposite direction, same symbol — **OPEN RULING**

Three defensible policies; the design does **not** choose:

| Policy | Behaviour | Cost |
|---|---|---|
| **ALLOW** | Both books hold opposite positions; each carries its own SL/TP | Maximum intent fidelity (different contexts genuinely disagree); maximum margin/hedging ambiguity on a netting account, and net exposure semantics differ by broker account type |
| **BLOCK** (second book blocked) | First book to place owns the symbol-direction; the other is recorded `blocked_opposite_direction` | Simple, deterministic, no hedging ambiguity; reintroduces a cross-book race — the thing this design removes — for the *minority* case of genuine disagreement |
| **NET** | Combine to the net direction and size | Cleanest accounting; destroys per-context identity and confuses the journal (which tag owns the ticket?) |

Recommendation to be ruled on: **ALLOW during demo flag stage, with the conflict counted and
journalled per book**, because blocking would silently reintroduce cross-tag arbitration while
the evidence base (R1) never measured opposite-direction coexistence. Netting is rejected for
identity reasons unless the broker account is netting-only, which is a broker-account ruling,
not a strategy one.

---

## 4. Mapping: current tiers → proposed menus

Shipped (do not change in this engagement): `_TIER_ADF = (A, D, F)` on H4/H1/M15;
`_DAY_TRIGGERS = tuple(TriggerType)` on DAY.

Proposed **book tier sets** (configuration, default OFF until Phase 3; derived from R1):

| Book | Proposed `detection_tier_set` | Confirmation TFs | Why this set |
|---|---|---|---|
| **B** | `{H4, H1, M15}` | M5+M15 / M5+M1 / M1 | 0 D1-tier wins in 270 windows; MID carries 264 fills, M15-heavy |
| **C** | `{H4, H1, M15}` | same | 0 D1-tier wins; MID 219 fills |
| **E** | `{H4, H1, M15}` | same | 0 D1-tier wins; MID 183 fills |
| **A** | `{H4, H1, M15}` (+ DAY only if R-E says so) | same | D1 tier: 21 wins, **0 fills**; MID 64 fills |
| **F** | `{DAY, H4, H1, M15}` | H1 / M5+M15 / M5+M1 / M1 | The only tag with a real D1-tier flow (107 wins → 14 fills); F is the one tag whose DAY participation is evidenced |
| **D** | *not proposed* | — | Structurally dead on the zero-volume feed (volume gate `engulfer.volume < engulfed.volume`, all volumes 0.0). A D book would be inert; admitting it needs a feed ruling (R-K) |

Notes:

- **Confirmation geometry is never re-invented.** A book reuses the shipped `MenuTier`
  `confirmation_tfs`; only `trigger_types` is narrowed to the single tag. That keeps every
  frozen rule (expiry, one-shot sweep gate, §5 state gate, C3) exactly as coded.
- **The single blended menu is not deleted.** The existing `PRODUCT_MENU_TIERS` path stays the
  production default until an architect ruling says otherwise (§5, §6).
- **Six books is a statement of intent, not a mandate**: it is acceptable to run three
  (e.g. B, C, F) in a first demo and add the rest later; the architecture is per-book, so the
  count is configuration.

---

## 5. Non-goals (explicit)

1. **No expectancy, no profitability, no edge claim.** R1 fills are counterfactual upper bounds.
2. **No SL/TP redesign.** SL/TP attachment stays as-coded; the 40–60-style P/L work stays
   deferred per owner intent.
3. **No silent expansion of production defaults.** `PRODUCT_MENU_TIERS`, `_TIER_ADF`,
   `_DAY_TRIGGERS` and every production config default stay unchanged in this engagement.
4. **No `locked_constants.py` edit**, no matrix cell change, no threshold, no expiry change.
5. **No parallel live trading code** in this engagement — design doc only; any spike must sit
   behind a dead-by-default flag and is Phase 2/3 work.
6. **No detection re-tuning, no new indicators, no new model tags.**
7. **No change to the F4 risk envelope** — it is a precondition (`POST_V1_ACTIVE_TODO` §18 F4).
8. **No account/broker policy choices** (netting vs hedging, magic ranges) beyond flagging them
   as rulings.

---

## 6. Implementation phases

| Phase | Deliverable | Gate | Production effect |
|---|---|---|---|
| **0 — Design (this doc)** | Book definition, rules, open rulings | Architect accept | **None** |
| **1 — Research multi-book harness** | Extend `06_RESEARCH/scripts/r1_pure_tag_books.py` to run N books **concurrently** against one shared risk envelope + cross-book plan dedupe; report contention, envelope blocks, conflict events, per-book story counters, wall time | Architect accept of multi-book metrics; runtime budget proven (R1 18.9 h single-tag matrix is the reference) | **None** (research only, gitignored results) |
| **2 — Demo flag (dead by default)** | Config-only `parallel_books: false` (default) with book list; when false the code path is the current single menu. Spike limited to wiring books → existing menu/adapter/risk; no new order code | Demo run with dry_run true, journals reviewed; flag false in every shipped config | Only if operator sets the flag |
| **3 — Demo as-is / default** | Architect ruling to enable in demo, then a separate ruling for default | Success criteria (§8) met on a defined window; F4 envelope ruled; direction export landed (R-J) | Governed change, separate engagement |

Hard sequencing constraints:

- **Phase 2 may not start** until R-A (story scope), R-B (conflict policy), R-D (identity) and
  R-H (cross-book dedupe) are ruled — the wiring changes shape per answer.
- **Phase 3 may not start** until R-J (direction at arm seam) is implemented, because a
  production book cannot infer direction per hypothesis the way R1 does.
- **Runtime budget** must be resolved in Phase 1: the M1-confirmation rescan is super-linear in
  active episodes; running six books multiplies episode load. Acceptable first step is a
  per-book active-episode cap or the swing-recompute caching seam — both are harness-side.

---

## 7. Open Architect rulings (all undecided)

| ID | Ruling needed | Options | Design's recommendation |
|---|---|---|---|
| **R-A** | One-story scope | global (as-coded) vs **per-book** | Per-book, with cross-book plan dedupe (see R-H) |
| **R-B** | Opposite-direction conflict, same symbol | allow / block / net | Allow during demo, counted + journalled |
| **R-C** | Capital & sizing split across books | shared pool / per-book quota / weighted per book | Shared pool (one envelope), per-book attribution only |
| **R-D** | Order identity | per-book magic offset / comment-only tag / shared magic | Comment prefix now, magic offset only with statement/EA sign-off |
| **R-E** | Does the `DAY` tier participate for any book? | yes for F only / yes for all / none | F only (only evidenced DAY flow) |
| **R-F** | Book count for first demo | 3 (B, C, F) / 5 (B, C, E, A, F) / 6 | 3 first, then extend |
| **R-G** | Runtime budget for N books | active-episode cap / caching fix / accept longer wall | Prove in Phase 1, do not ship a 20 h demo loop |
| **R-H** | Cross-book identical-plan handling | suppress second ticket / allow and aggregate size / first-wins | Suppress + `cross_book_duplicate` counter (identity stays clean) |
| **R-I** | Daily-loss / max-trades allocation | single shared limit / per-book quota with shared floor | Single shared limit |
| **R-J** | Direction at the arm seam | export `direction` on armed records / authoritative resolver | Export at arm seam (small product data change) before Phase 3 |
| **R-K** | `D` (Two-Bar Reversal) | exclude / include behind a feed-volume ruling | Exclude; feed has zero volume |
| **R-L** | First demo mode | shadow (no orders) / dry_run / demo orders | Shadow/dry_run only until the envelope is ruled |

---

## 8. Success criteria — "functioning product"

A book architecture is functioning when **all** of the following hold on a declared demo
window (no expectancy claim implied):

### 8.1 Paths fire (per book, not aggregate)

1. Every declared book produces at least one **route** and one **fill** in the window —
   the R1 existence claim, reproduced on the live seam rather than the replay harness.
2. **Tag purity**: each book's filled trades are `{tag: 100%}`; cross-tag leak = fail
   (fail-loud, mirroring R1's in-worker check).
3. Every book's wins that do not fill are attributed to a **named** reason
   (risk envelope, cross-book dedupe, session block, zone-place skip) — no unattributed gap.

### 8.2 Identity is clear

4. Each order carries its book identity (comment tag, and magic per R-D), so a statement line
   maps to exactly one book without log archaeology.
5. Journal lines are per book: `armed → episode → win → route → risk verdict → place/fill`,
   with the book id on every line and a per-book counter block alongside the existing
   `story_counters` / menu counters.
6. Two books acting on the same bar are distinguishable in the journal in bar order, and a
   cross-book duplicate is visible as a counted event, never as a silent second ticket.

### 8.3 The envelope is intact

7. Circuit breaker, daily-loss and max-trades limits are never exceeded in aggregate across
   books, and each block is attributed to the book that hit it.
8. Opposite-direction coexistence (if R-B = allow) is counted and journalled; if R-B = block,
   every block is counted with the owning book.
9. No book starves another: per-book fill counts are non-zero for every declared book in the
   window (the anti-starvation criterion this design exists to satisfy).

### 8.4 Governance

10. `locked_constants.py` diff empty; shipped tier table unchanged; parallel path off by
    default until a separate default-enable ruling.
11. Suite green with the flag both off (current behaviour byte-identical) and on (new book
    paths covered by focused tests).

---

## 9. Appendix — cited code paths

| Concern | Location |
|---|---|
| Tier dataclass, tier table, `_TIER_ADF`, `_DAY_TRIGGERS` | `04_SRC/smc/orchestration/product_menu_mtf.py` L228-250 |
| Detection→tier lookup, `menu_covers` | same, L262-272, L424 |
| Arming + one-shot consumption (F5 arm instant) | same, L450-486 |
| Cross-TF winner ordering (`confirmation_order_key`) | same, L111-123, L589-606 |
| One-story intake guard, plan identity, claims | `04_SRC/smc/backtest/pipeline_adapter.py` L249 `_live_story_keys`, L324 `_duplicate_story`, L361 `queue_menu_candidate`, L656 `on_candidate_accepted` |
| Live-book story liveness | `04_SRC/smc/backtest/runner.py` L630; `04_SRC/smc/paper/runner.py` L383 |
| Risk envelope (breaker, guards, daily rollover) | `04_SRC/smc/risk/risk_engine.py` L175 class, L220 breaker check, L399 record, L415 rollover |
| Same-level / sweep guards | `04_SRC/smc/risk/same_level_guard.py`, `04_SRC/smc/risk/sweep_guard.py` |
| Order identity (magic, comment) | `04_SRC/smc/execution/order_manager.py` L65, L93 |
| Evidence: admission map | `06_RESEARCH/R0_TRIGGER_ADMISSION_MAP.md` |
| Evidence: pure books | `06_RESEARCH/R1_PURE_TAG_BOOKS_REPORT.md` |
| Evidence: starvation probe | `06_RESEARCH/BCE_STARVATION_PROBE_REPORT.md` |

**NO ACTIONS BEYOND THIS DOCUMENT.** No production default changed, no parallel engine
shipped, suite untouched, `locked_constants.py` diff empty. NEXT = Architect accept/deny of
§7 rulings → Phase 1 research harness (multi-book) or demo-as-is.
