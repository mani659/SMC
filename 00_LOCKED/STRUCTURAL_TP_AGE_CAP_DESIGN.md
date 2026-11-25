# STRUCTURAL TP AGE-CAP — DESIGN NOTE (PHASE A: DEFINITION ONLY)

**Date:** 2026-11-25
**Authority:** Lead Architect directive (TP age-cap, Phase A)
**Role:** local implementer — draft from code + P4 evidence; the option letter belongs to the Architect
**Status:** **DRAFTED — AWAITING ARCHITECT OPTION LETTER** (`A` / `B` / `C` / `D`)
**Mode:** `LOGIC_CHANGED: NO` — no code path changed, no constant written, no default flipped, no bulk run

**Evidence base**
- `06_RESEARCH/F_TP_REPRESENTATION_DIAGNOSIS.md` (P4, 2026-11-24) + `06_RESEARCH/results/f_tp_representation/{fallback_inventory.csv,summary.json}`
- `06_RESEARCH/STRUCTURAL_TP_FEED_DESIGN.md` §3b + Architect Addendum (the bound's origin)
- Code read for this note: `pipeline_bridge.py`, `trigger_expiry.py`, `locked_constants.py`, `product_menu_mtf.py`, `pipeline_adapter.py`

**Fixed context (not re-opened here):** P0 `SUPERSET_OPEN_BOOK_SCOPE_ONLY`; P3 `STOP_REFERENCE: A_KEEP` (unchanged by this note).

---

## 1. Current behaviour (code-cited)

### 1.1 The seam

| Element | Location | Value / behaviour |
|---|---|---|
| The filter itself | `04_SRC/smc/backtest/pipeline_bridge.py:162-163` | `if placement_bar is not None and max_age_bars is not None and swing.candle_index < placement_bar - max_age_bars: continue` |
| Parameter default | `pipeline_bridge.py:111` | `max_age_bars: int \| None = None` — **off unless a caller passes it** |
| Value passed (menu) | `04_SRC/smc/orchestration/product_menu_mtf.py:1023` | `max_age_bars=poi_give_up_bars()` |
| Value passed (seek) | `04_SRC/smc/backtest/pipeline_adapter.py:766` | `max_age_bars=poi_give_up_bars()` |
| The supplier | `04_SRC/smc/triggers/trigger_expiry.py:57-63` | `return TRIGGER_A_EXPIRY` |
| The frozen number | `04_SRC/smc/config/locked_constants.py:173` | `TRIGGER_A_EXPIRY = 20  # A – CHOCH Reversal: 20 M5 bars` |

These are the **only two** call sites in the tree (`code_search max_age_bars` → 21 hits; no third production caller).

### 1.2 What "20" is, and what it is not

`poi_give_up_bars()` is the **POI-wide trigger give-up clock** (§24, Trigger A's window) — it answers *"how long may a POI wait for any trigger to fire?"*. It is **not** a take-profit constant and no locked document defines a TP search window. It entered the TP path as an interim CPU/age bound in `STRUCTURAL_TP_FEED_DESIGN.md` §3b, and the Architect addendum recorded the ruling verbatim:

> *"Reuse of `poi_give_up_bars()` as pre-arm swing tolerance — Accepted ONLY as an optional search bound (CPU/age cap), not a new market meaning. Primary rule remains: all §19-confirmed swings with `confirmed_index < placement_bar` on the place-time prefix; the `poi_give_up_bars()`-before-arm cap is a documented bound, never 'give-up semantics'."*

So the defect is **not** that the number is wrong. It is that a **M5-denominated** trigger clock was reintroduced as a **bar-denominated** search window on a path whose bars are not necessarily M5 bars.

### 1.3 Coordinate mismatch by call site

`candle_index` is an index into the series the swing was detected on. That series differs between the two call sites:

- **Seek path** (`pipeline_adapter.py:766`): swings come from the M5 `SeriesState` prefix → `20` means **20 M5 bars = 100 minutes**. Dimensionally coherent with §24. Unchanged by this note.
- **Menu path** (`product_menu_mtf.py:1023`): swings come from `_swings_for(tf)` (`product_menu_mtf.py:721-732`) = `detect_swings(self._confirm[ctf], ctf)` → `candle_index` is a **confirmation-TF** bar index, and `placement_bar` is the confirmation-TF completion index (`:1003-1006`). The integer `20` is therefore reinterpreted in whatever TF confirmed:

| Confirmation TF | Bar minutes | 20 bars of age = wall time |
|---|---:|---:|
| M1 | 1 | **20 min** |
| M5 | 5 | **100 min** |
| M15 | 15 | **300 min (5 h)** |
| H1 | 60 | **1,200 min (20 h)** |

Same integer, a 60× spread in wall time. Nothing in the locked text chooses any of those.

### 1.4 P4 census (restated, not re-measured)

Year Book F, 351 fills, S3 post-R1: **222 structural (63.25 %) / 129 atr_fallback (36.75 %)**. Of the 129 fallbacks:

- `SUPPRESSED_POLICY` **129/129 (100.0 %)** — dominant cause `SUPPRESSED_AGE_CAP_GT_20_BARS` (100 %);
- `UNAVAILABLE_FEED` **0/129 (0.0 %)**;
- with `max_age_bars=None` every one of the 129 resolves to a valid, finite, correctly-sided target;
- suppressed age, by confirmation TF (bars → wall time at that TF):

| TF | Fallback fills | Share | Median age | Min | Max |
|---|---:|---:|---:|---:|---:|
| M1 | 95 | 73.6 % | 45 bars (45 min) | 21 | 12,501 (≈8.7 days) |
| M5 | 23 | 17.8 % | 52 bars (260 min) | 21 | 509 |
| H1 | 8 | 6.2 % | 38 bars (38 h) | 22 | 84 |
| M15 | 3 | 2.3 % | 47 bars (705 min) | 32 | 87 |
| **All** | **129** | 100 % | 47 bars | 21 | 12,501 |

Overall age quartiles of the suppressed swing: Q1 31 · Q2 47 · Q3 173 bars. Minimum observed is **21** — one bar past the cutoff.

### 1.5 A selection fact that matters for every option

`structural_tp_target` ranks candidates by `key = (dist, -swing.candle_index)` (`pipeline_bridge.py:167-172`) and returns the **nearest in price**; recency is only the tie-break. Therefore the age cap does not merely *filter* — it can change *which* swing wins. Loosening the cap can replace a recent, slightly farther target with an older, nearer one. Any measurement that reports only "share of structural" would hide this.

---

## 2. Problem statement (non-rhetorical)

1. A structural target **exists on the place-time prefix** for 129/129 currently-fallback F fills; it is excluded by an age filter whose value was borrowed from a different question (trigger give-up) and whose units are borrowed from a different timeframe (M5).
2. The dual path **KEEP structural-else-4×ATR is not in question here.** The fallback stays; `resolve_take_profit` stays; `STRUCTURAL_TP_MIN_ATR` stays. This note concerns **only the search window of the structural branch**.
3. The cap is **not proven wrong**. It may be doing useful work (a 12,501-bar-old level is not "structure" in any useful sense). What is proven is that it is **unruled, TF-ambiguous, and decisive on 36.75 % of F fills**. The correct next step is a ruled window, not an unruled removal.

---

## 3. Options (enumerated; none chosen)

For each: code surface, what stays identical, main risk.

### A. KEEP — `max_age_bars = poi_give_up_bars()` on all confirmation TFs

- **Code surface:** none.
- **Unchanged:** everything; 20 bars per confirmation TF as today; 129 fallbacks remain fallbacks.
- **Risk:** the ambiguity persists — the same integer means 20 min on M1 and 20 h on H1, and it is documented in a TP path as a *trigger* clock. Also: the F fallback share (36.75 %) stays a permanent feature of the book, so every future TP observation is a mixed-branch observation.
- **Honest note:** A is a legitimate answer if the intent is that old levels are not targets. It just has to be *stated* as the intended window rather than inherited.

### B. SCALE_BY_TF — age expressed in bars chosen so wall time is comparable

Two formula candidates (no hidden magic number; the number must be named in the ruling):

- **B1 — 100-minute parity:** `bars(tf) = ceil(20 × 5 / tf_minutes)`

  | TF | Today's bars | B1 bars | B1 wall time |
  |---|---:|---:|---:|
  | M1 | 20 | **100** | 100 min |
  | M5 | 20 | 20 | 100 min |
  | M15 | 20 | **7** | 105 min |
  | H1 | 20 | **2** | 120 min |

  This conversion already exists in the repo for the same kind of M5→TF translation: `LA_M15_BARS = ceil(20 × 5 / 15) = 7` (`06_RESEARCH/scripts/ltf_confirmation_pack.py:24`, pinned in `test_ltf_confirmation_pack.py:112,147`). Cite it as precedent only — that one is a **look-ahead** window, this one is an **age** window; the direction of the reasoning is the same, the semantics are not.

- **B2 — single stated horizon `H`:** `bars(tf) = ceil(H / tf_minutes)`, `H` named in the ruling before any run (e.g. a 4-hourly or daily horizon). Loosens every TF when `H > 100 min`.

- **Code surface:** one small converter beside the selector (e.g. `structural_tp_max_age_bars(tf)` in `pipeline_bridge.py`) plus a TF argument at the two call sites; seek path can keep passing 20 (its series is M5 by construction) or route through the same converter with TF=M5.
- **Unchanged:** selector logic, ranking, noise guard, fallback.
- **Main risk (B1):** it is **not** a pure recovery option. B1 leaves M5 at 20 and *tightens* M15 (20→7) and H1 (20→2), so recovery is arithmetically confined to M1 (at most 73.6 % of fallbacks); M5/M15/H1 cannot recover at all. B2 avoids that only by choosing `H > 100 min` — which is a market-meaningful horizon that must be ruled, not fitted.
- **Second risk:** a formula in code becomes a de-facto constant. If adopted, it needs a named home and the same "PROPOSED → ruled" discipline `STRUCTURAL_TP_MIN_ATR` went through.

### C. SEPARATE_CONSTANT — `STRUCTURAL_TP_MAX_AGE_BARS` (**PROPOSED, not locked**)

- **Concept:** stop reusing the §24 clock for TP search; give the TP branch its own named window, so a future change to Trigger A cannot silently move take-profit behaviour.
- **Value:** **TBD — only after measurement.** No number is proposed here.
- **Code surface:** a module-level name (precedent: `STRUCTURAL_TP_MIN_ATR` was introduced the same way and is still module-level pending formal § lock), consumed at both call sites in place of `poi_give_up_bars()`.
- **Unchanged:** selector logic; fallback; §24 itself.
- **Main risk — this is the important one:** a **bare integer is TF-ambiguous**, which is the root defect of the current state. C is only a real fix if it is defined *in the right units* (per-TF bars via a stated conversion, or wall-clock minutes converted at use). A single integer constant would move the coin from Trigger A's pocket to a new pocket, not fix it. C and B are therefore not alternatives — **C is where B's answer lives.**

### D. NO_AGE_CAP — `max_age_bars = None`

- **Code surface:** pass `None` at the menu call site (one argument). Primary rule already enforced in the selector: `confirmed_index is not None and confirmed_index < placement_bar` (lookahead ban), plus sidedness and the `0.25 × ATR` noise guard.
- **Unchanged:** selector, ranking, noise guard, fallback, §24 (trigger expiry keeps its own clock everywhere else).
- **Main risk:** stale levels. P4 observed a suppressed target **12,501 M1 bars (≈8.7 days)** old; H1 cases sit at 38–84 bars (38–84 h). Because ranking is nearest-in-price, an old level can outrank a recent one — the option changes *which* target is chosen, not just *whether* one exists. No new guard is implied by any locked text to replace the cap; adopting D without one is an unruled widening.

### E. Other — only if already implied by locked docs

Nothing is implied. Checked: no locked document defines a TP search window, age horizon, or staleness rule (`LOCKED_DECISIONS.md`, `EXPERT_MASTER_CARD.md`, `STRUCTURAL_TP_FEED_DESIGN.md`). The only related frozen text is `STRUCTURAL_TP_MIN_ATR = 0.25` (a **distance** guard, not an age guard). Two constructions are therefore **excluded as inventions**: a per-TF cap list written into `locked_constants.py`, and a "max distance from entry" cap (a new market rule, out of scope for this engagement).

**Summary of the real choice:** A (state today's window) · B1 (100-minute parity; M1-only recovery, tightens M15/H1) · B2 (one ruled horizon) · D (no cap, stale-level risk) · C (naming/units decision that any of B/D must carry).

---

## 4. Measurement contract (PRE-REGISTERED before any bulk run)

### 4.1 Population (exact)

| Set | N | Artifact |
|---|---:|---|
| Book F year fills | **351** | `06_RESEARCH/results/entry_quality_f_b/universe_features.csv` (F rows) |
| Book F `tp_source = structural_swing` | **222** | same; cross-check `06_RESEARCH/results/o_block_year_read/o4_o5_fills_s3.csv` |
| Book F `tp_source = atr_fallback` (the subset) | **129** | `06_RESEARCH/results/f_tp_representation/fallback_inventory.csv` |

Reconstruction must reuse the accepted P4 harness method (place-time prefix, `confirmed_index < placement_bar` strictly, per-segment, all 12 segments). **No new selector is written**; the measurement calls the existing `structural_tp_target` with the option's argument only.

### 4.2 Primary metrics — DIAGNOSTIC ONLY

1. `structural_share` — share of the 351 whose TP branch is structural, per option vs baseline 222/351.
2. `recovery` — share of the **129** that gain a structural target under the option, split by confirmation TF.
3. `selected_age` — distribution (bars **and wall time**, per TF) of the swing that actually wins when structural wins.
4. `tp_distance_atr` — median `|TP − entry| / ATR` for structural vs fallback rows (**description only**).
5. `churn` — of the 222 current structural fills, how many get a **different** target level under the option (see §1.5).

### 4.3 Explicit limits

**This is a representation census, not a performance measurement.** No PF, no expectancy, no win rate, no R-multiple success criterion, no comparison of outcomes. No stop, entry, SL, book, or default is touched.

Pre-registered disclosure: for **D**, `recovery` is **already saturated at 129/129** by P4 §4.3. D's measurement power therefore lies entirely in `selected_age` and `churn`; a report that presents "100 % recovery" as the finding has measured nothing.

### 4.4 Kill / caution flags (pre-registered — no threshold fishing after numbers)

- **K1 NULL_RECOVERY.** If an option billed as loosening recovers **< 25 %** of the 129, report `NULL_RESULT` for that option. (B1 hits this by construction for M5/M15/H1: its caps are ≤ 20 there.)
- **K2 STALENESS CAUTION.** If **> 20 %** of newly-selected swings are older than **24 h** wall time, or any selected swing is older than **7 days**, report `STALE_CAUTION` and do **not** auto-adopt.
- **K3 CHURN ≠ RECOVERY.** If > 10 % of the 222 current structural targets change level, the option must be reported as a **selection change**, not as "recovering suppressed targets".
- **K4 NO FITTING.** The option's formula/horizon is fixed **before** the run. Changing it after seeing numbers requires a new pre-registration and a new run; the abandoned pass is reported, not overwritten.
- **K5 DETERMINISM.** Two runs, byte-identical CSV/md5; a diff is a FAIL.

---

## 5. Non-goals

- No stop-reference change — P3 `A_KEEP` stands.
- No zone-quality filter or score — P5 remains deferred.
- No change to `STRUCTURAL_TP_MIN_ATR`, the 4×ATR fallback, `resolve_take_profit`, entries, SL, risk, or exits.
- No product/superset claim — **book-scoped (Book F) only** (P0).
- No operator, config, default or `parallel_books` change in this phase.
- No implementation of B, C or D. No edit to `locked_constants.py`.

---

## 6. Architect decision template

```
TP_AGE_CAP:
  OPTION_LETTER:            # A | B1 | B2 | C | D
  SCOPE:                    # F only | all books
  PROPOSED_PARAM:           # if B2: H = <value + unit>  |  if C: <name + units>  |  if B1: formula as written
  RATIONALE:

  # If C is chosen, answer these or C is not a fix:
  UNITS:                    # per-TF bars (which conversion?) | wall-clock minutes
  HOME:                     # module-level interim | locked_constants (requires separate ruling)

  # Acknowledged in the ruling (tick to proceed):
  [ ] I have read §1.5 — loosening changes which target wins, not only whether one exists.
  [ ] I accept the P4 baseline 222/351 structural and 129/129 suppressed-by-age.
  [ ] Measurement remains diagnostic; no PF/expectancy claim will be made.
```

---

**STOP.** Note + governance only. Options B–D are not implemented; `locked_constants.py` is untouched; `product_menu_mtf.py` and `pipeline_bridge.py` behaviour is unchanged.
