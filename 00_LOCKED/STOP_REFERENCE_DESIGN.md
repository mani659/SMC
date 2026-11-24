# STOP-REFERENCE DESIGN LOCK — DEFINITION (DRAFT, AWAITING ARCHITECT)

**Date:** 2026-11-24 · **Status:** `P3A_DRAFT` — **definition not ruled; no measurement run**
**`LOGIC_CHANGED: NO`** · **`PRODUCT_CODE_CHANGED: NO`** · **`COUNTERFACTUAL_RUN: NO`**
**Phase order (mandatory):** this definition doc → **Architect ACCEPT + option letter** → only then
the offline counterfactual (`06_RESEARCH/STOP_REFERENCE_MEASURE.md`).
**Authority:** the definition text is the **Architect's**. This document assembles code facts,
vocabulary, the option set and a pre-registered measurement contract. It does **not** pick an
option and does **not** assert that a new rule is "what the card already said".

**Why this exists (audit A5):** 70 % of F stops sit **inside** the routed POI zone. Code and card
both describe that as compliant, so the ambiguity silently feeds every R-multiple, exit study and
target comparison. The audit's reframe is the frame used here: **the definition question and the
measurement question have different owners** — *"which zone does 'POI' mean for stop placement …
Architect rules; no measurement can answer it."*

---

## 1. CURRENT BEHAVIOUR (code-cited)

### 1.1 What `stop_reference` is today

`04_SRC/smc/triggers/trigger_f_bos_ob.py:85-98`:

```python
# FR-3.1: the resting limit is anchored INTO the routed POI zone at
# the DIRECTION-PROXIMAL edge (LONG -> zone high, SHORT -> zone
# low). The OB proximal edge stays the reference (on-zone OBs are
# bit-identical to the pre-FR-3.1 rule); a detached OB re-anchors
# to the proximal edge and the stop reference moves to the zone's
# distal edge so the stop remains on the protective side.
atr = context_atr(context, bar)
if is_long:
    reference = top                                    # OB proximal edge
    entry = zone_anchored_entry(zone.direction, zone.bottom, zone.top, reference)
    stop_reference = bottom if entry == top else zone.bottom
else:
    reference = bottom
    entry = zone_anchored_entry(zone.direction, zone.bottom, zone.top, reference)
    stop_reference = top if entry == bottom else zone.top
stop = structural_sl(stop_reference, zone.direction, atr)
```

- **Classic F entry** (`entry_anchor = "ob_proximal"`, entry at the OB proximal edge):
  `stop_reference` = **the origin OB's distal edge** (`bottom` for LONG, `top` for SHORT —
  `top/bottom` are the OB's own high/low, `trigger_f_bos_ob.py:69-71`).
- **Re-anchored F entry** (`entry_anchor = "zone_edge_reanchor"`, entry moved to the routed zone's
  proximal edge because the OB was detached from the zone): `stop_reference` = **the routed zone's
  distal edge** (`zone.bottom` for LONG, `zone.top` for SHORT).
- **B book is not this rule.** `trigger_b_leading_diagonal.py:89` uses
  `stop_reference=impulse.origin_level` (Wave-1 origin). B is carried in the measure only as a
  **same-lock observer**, never pooled with F.

### 1.2 Where the 0.3 × ATR buffer attaches

`04_SRC/smc/triggers/base_trigger.py:44, 96-110`:

```python
FR2_SL_BUFFER_ATR = 0.3   # structural stop buffer beyond the reference extreme

def structural_sl(reference_price, direction, atr, buffer_atr=FR2_SL_BUFFER_ATR):
    if atr is None or not atr > 0:
        return reference_price                      # guarded: no volatility -> raw edge
    buffer = buffer_atr * atr
    if direction is Direction.LONG:
        return reference_price - buffer
    return reference_price + buffer
```

The buffer is applied **once, inside the trigger**, on the reference extreme, in the adverse
direction. It is not re-applied downstream:

- `04_SRC/smc/backtest/pipeline_bridge.py:272` — `sl_price=signal.stop_reference`
- `04_SRC/smc/backtest/pipeline_bridge.py:290` — `original_sl=signal.stop_reference`
- `04_SRC/smc/orchestration/engine.py:121-124` — the limit request passes `route.signal.
  stop_reference` as `sl` with *"no buffer — broker stops-level/spread offset is a Phase 5
  execution concern"*.

So `original_sl` **is** the buffered placement stop, by construction (FR-2 note §3; BE modifies
never overwrite it, test-enforced). `FR2_SL_BUFFER_ATR` is **interim and not a locked constant**
(`base_trigger.py:41-43`: *"NOT frozen locked constants: do not import them as such, do not tune
them against backtests"*; FR-2 note §4 lists it as pending a formal §28 lock).

### 1.3 Why the stop can sit inside the routed POI zone

Because the reference is a **sub-zone edge**, not the zone boundary. The origin OB is a nested
element inside the routed POI:

- LONG: entry at the OB **proximal** (upper) edge → stop at the OB **distal** (lower) edge − 0.3 ATR.
  If the OB's distal edge lies **inside** the routed zone, the stop lands inside the zone.
- The routed zone is typically far taller than the OB: **zone height p50 12.2 ATR** (p25 5.1 /
  p75 25.0) against F risk of **p50 1.16 ATR**. A zone tens of ATR tall easily contains an
  OB-distal stop.
- Only when the OB is detached from the zone does FR-3.1 re-anchor the entry, and **then** the code
  already moves the stop to the zone distal edge — which is why the 19 re-anchored rows are the only
  F rows with a stop outside the routed zone (0/19 inside).

**What is NOT in the locked text.** Neither the master card nor `LOCKED_DECISIONS` requires the stop
to clear the routed POI zone. The complete product language is:

- `00_LOCKED/EXPERT_MASTER_CARD.md:96` — `| SL (product) | existing **ATR-buffer** path |`
- `00_LOCKED/EXPERT_MASTER_CARD.md:140` — `SL_PRODUCT: atr_buffer`
- `00_LOCKED/LOCKED_DECISIONS.md:604-606` (§21b, amendment A4) — *"**SL (product) = the existing
  ATR-buffer path** (structural extreme ± buffer). The **2–5 pip M1 SL** and the **30-pip** operator
  note are **benchmarks only** (MAE / review), not product stops."*
- `00_LOCKED/LOCKED_DECISIONS.md:98` — benchmarks row: *"30-pip SL (MAE review), ESSENCE Model-8 1:5
  TP profile, ESSENCE 2–5 pip M1 SL"*.

There is **no** "stop must be outside the POI" clause, no "never inside the zone" sentence and no
zone-clearance requirement of any kind. The only zone↔stop adjacency in locked text is unrelated:
R7's **place** guard (`FOUNDATION_RESET_PLAN.md:68`) compares the **market close at place time** to
the routed zone, not the stop. The closest *documented alternative* is an **open question**, not a
ruling: `00_LOCKED/ENTRY_REPRESENTATION_DESIGN.md:293-295` — *"Stop reference when the limit leaves
the zone edge: OB distal (FR-2 as-is) vs zone distal — which one governs … (the reference selection
is the open question)."*

Therefore: **"never inside POI" is a proposed rule, not a restatement of a contract.** Anyone
adopting it is adopting option B or C below, and must say so.

### 1.4 What is currently on disk (current-state facts only — no counterfactual)

`06_RESEARCH/results/entry_quality_f_b/universe_features.csv` (post-R1 year union, re-read today):

| Book | n | stop inside the routed zone | by anchor | depth of the stop inside the zone (ATR) | risk p50 (ATR) |
|---|---|---|---|---|---|
| **F** | 351 | **246 (70.1 %)** | `ob_proximal` 246/332 inside; `zone_edge_reanchor` **0/19** inside | p25 0.61 · **p50 1.44** · p75 2.73 | **1.16** |
| B (observer) | 241 | 137 (56.8 %) | B has no F anchor column (impulse-origin stop) | p25 1.81 · p50 3.56 · p75 8.00 | 2.90 |

Zone height p50: F **12.2 ATR**, B 15.4 ATR. The inside stops sit **nearer the far edge than deep
inside it** (median 1.44 ATR of a 12.2 ATR zone).

---

## 2. VOCABULARY (definitions only — no measurement)

```
LONG example, price descending down the page

  zone_high  ────────────────  routed POI zone TOP      (proximal edge for a LONG entry)
                    ▲
                    │  zone body  (height p50 ≈ 12.2 ATR)
                    │
   entry ───────────┼──────  limit at the OB proximal edge  (ob_proximal)
                    │
   OB low ──────────┼──────  OB DISTAL EDGE  ← today's stop reference for classic F
                    │
   stop ────────────┼──────  OB distal − 0.3×ATR   ← "inside POI" today (70.1 % of F)
                    │
  zone_low  ────────┴──────  routed POI zone BOTTOM      (distal edge for a LONG entry)
```

- **OB distal edge** — the origin OB's far boundary from the entry side: the OB's **low** for a
  LONG, its **high** for a SHORT (`trigger_f_bos_ob.py:69-71`, `top/bottom`). It is a **sub-zone**
  edge belonging to one element *inside* the POI.
- **Routed POI zone** — the zone of the POI the fill is attached to; exported per trade as
  `zone_low` / `zone_high`, read in code as `zone.bottom` / `zone.top`. This is the **HTF detection
  zone** (D1 / H4 / H1 / M15) that was armed and routed. In the current product path the "HTF
  structure zone" and the "routed POI zone" **coincide**; there is no second, wider structure zone
  in the stop decision.
- **HTF structure zone** — used here only as a synonym for the routed POI zone. Where a document
  means something else (e.g. ESSENCE §5's "M1-structure stop"), it is a different instrument path
  and is out of scope for this lock.
- **"Inside POI"** — ambiguous, and the ambiguity is the whole finding. The data column
  `sl_beyond_zone` measures exactly one of these: the stop lies **between the entry and the routed
  POI zone's far edge** (not beyond `zone_low` for a LONG, not beyond `zone_high` for a SHORT). It
  says nothing about the OB sub-zone (the stop is by definition at the OB distal edge). **This
  document therefore uses "inside POI" = "inside the routed POI zone", and only that.**

---

## 3. OPTIONS FOR THE ARCHITECT (enumerated, none picked)

`buffer` = `0.3 × ATR` at the completion bar (`FR2_SL_BUFFER_ATR`, interim). "Adverse" = further
from the entry in the stop's direction (lower for LONG, higher for SHORT).

| Option | Rule | Effect vs today | Rows it can change |
|---|---|---|---|
| **A — KEEP** | `stop = OB_distal ∓ buffer` (classic) · `stop = zone_distal ∓ buffer` (re-anchored) — i.e. **exactly today's code** | none | 0 |
| **B — REPLACE with the zone far edge** | `stop = zone_far_edge ∓ buffer` **for every F fill** (replaces the OB-distal reference, including where the OB distal is already further out) | clears the zone on all rows; **tightens** stops whose OB distal already sat beyond the far edge | up to 351 F rows (283 would move outward on current geometry) |
| **C — HYBRID (floor, widen-only)** | `stop = more adverse of {OB_distal ∓ buffer, zone_far_edge ∓ buffer}` — today's rule plus a floor at the zone's far edge | clears the zone on all rows; **never tightens** any stop; re-anchored rows unchanged (already at the floor) | 283 F rows would move outward |
| **D — DEFER / other** | no fourth rule exists in locked text. The only documented alternative pairing is the **open question** `ENTRY_REPRESENTATION_DESIGN.md:293-295` (OB distal vs zone distal), which is not a ruling | — | — |

Mechanical difference between B and C, stated so the choice is not ambiguous later: **B replaces**
the reference (so a stop already beyond the zone's far edge is pulled *in* to the far edge);
**C only widens** (max in the adverse direction), leaving those rows untouched. On current data both
clear the zone for the same inside rows, but they differ on the ~37 F rows already outside.

Not offered, because it would be a new rule invented here rather than a documented option: a
per-timeframe rule, a zone-width-scaled buffer, a volatility regime switch, or "clear the OB by N
ATR". If the Architect wants one of those, it must be written as its own option letter first.

**Projection for the Architect's cost picture (geometry, not a result):** option C's outward move
would take F median risk from **1.16 ATR to ≈2.7 ATR**; option B would additionally tighten stops
that are already clear. This is arithmetic from existing zone bounds and `original_sl` — **not** the
P3B measurement, which has not been run and which alone can speak to stop-out frequency.

---

## 4. EXPLICIT NON-GOALS

1. **Not a pip-rule revival.** O4 was re-read as `INPUTS_CHANGED` (P2): the 30-pip marker is a
   benchmark whose year population no longer resembles the n=11 October ruling. Nothing here
   proposes, imports or rescales a pip distance.
2. **Not a B-book change.** B is in scope **only as a same-lock observer**, reported separately,
   never pooled with F. B's stop reference is the Wave-1 impulse origin, a different object.
3. **Not product promotion.** Book-scoped under P0 `SUPERSET_OPEN_BOOK_SCOPE_ONLY`; the
   product-superset question stays OPEN and no book number becomes a product claim.
4. **Not a threshold exercise.** No buffer value, ATR multiplier, tolerance or zone-width cut is
   proposed or tuned here. `FR2_SL_BUFFER_ATR` stays interim and untouched.
5. **Not an entry or TP change.** Entries, C3, TP selection and the target are out of scope (P4
   owns the F target question, P5 the zone-quality metric).
6. **Not a live/paper step.** No `parallel_books`, config or default change; measurement is offline
   on frozen artifacts.

---

## 5. MEASUREMENT CONTRACT (pre-registered BEFORE any run — to execute only on ACCEPT)

**Trigger for execution:** Architect writes `ACCEPT` **and** an option letter (A / B / C / D). Until
then no counterfactual is computed.

**Population.** F fills with a recoverable routed zone and `original_sl`: **N = 351 / 351**
(`06_RESEARCH/results/entry_quality_f_b/universe_features.csv`, year union, post-R1). B (241) is
reported **separately as an observer**, never pooled. No segment-armed counts are summed.

**Counterfactual rule per option (price level only, one rule each, no search).**
- **A:** status quo — the baseline, no counterfactual.
- **B:** `sl' = zone_far_edge ∓ 0.3 × ATR` for every F fill (replacement).
- **C:** `sl' = more adverse of {current stop, zone_far_edge ∓ 0.3 × ATR}` (floor).
- ATR = the completion-bar ATR already carried in the export (derived as `|entry − sl| / risk_atr`
  where the raw ATR is not exported); the **same** ATR for before and after, so the buffer is held
  constant and only the reference moves.

**Path convention (identical to P2 §2.0, which is how this stays comparable).** Entry bar → exit bar
**inclusive**, on M1, where the exit bar is the whole M5 bucket `[exit_at, exit_at + 5 min)` because
trade stamps are M5 bucket opens. Stop-out under `sl'` = the path trades through `sl'` before it
trades through the current exit level; `DIAGNOSTIC_PNL: NOT PERFORMANCE` — no PnL, PF, expectancy or
ranking is computed or reported.

**Metrics (per book, per option, always with numerator/denominator).**
1. `moved_n` — rows whose stop price changes (and the share of N).
2. **Stop-out rate** under the re-priced stop, and the change in count/rate versus the current rule.
3. **Median risk in ATR** (current vs counterfactual), p25/p75.
4. **Share of stops inside the routed zone** after the rule (expected 0 % for B/C by construction —
   it is a check that the rule does what it says, not a finding).
5. **Fill rate: invariant by construction** (entries untouched). Reported as a verification line,
   never as a result. If the risk shell were applied, lot size would change; this measure stays at
   price level and states that sizing drift is not modelled.
6. TP ÷ R shift, using the existing TP (no TP re-selection).

**Kill criterion (from the audit, frozen here).** The design is **rejected for now, without
discussion**, if:
- `moved_n < 30` rows — too little population to say anything; **or**
- the **median risk of the moved rows exceeds 2.0 ATR** (current F median 1.16 ATR) — a widened stop
  at that scale is a risk-policy change, not a reference clarification; **or**
- the option moves **> 60 % of F fills** — it is a repricing of the book, not a targeted fix.

These are **measurement gates**, not product thresholds; they bind only this pack, and only an
explicit Architect override can set one aside (recorded in the measure note).

**Also reported, not gated:** how many rows the option would *tighten* (B only), and the count of
rows whose TP ÷ R falls below the existing structural target's ratio.

**Determinism:** dual run, byte-identical exports (repo convention for export-based measures).

---

## 6. WHAT THE ARCHITECT IS ASKED TO WRITE

A one-line decision, so the rule text can be locked verbatim:

```text
STOP_REFERENCE: <A_KEEP | B_REPLACE_ZONE_FAR_EDGE | C_FLOOR_ZONE_FAR_EDGE | D_DEFER>
SCOPE: F (classic ob_proximal) + re-anchored rows as today | F only | F + B observer
BUFFER: 0.3 x ATR unchanged (interim) | named alternative (requires its own ruling)
RATIONALE: <one sentence, in the Architect's words>
```

Anything that changes the buffer, adds a per-timeframe rule or scales by zone width is a **new
option** and needs its own letter before it can be measured.

---

## 7. STATUS / RETURN BLOCK (Phase A)

```text
P3A_STATUS: PASS (definition drafted; NOT ruled)
DESIGN_PATH: 00_LOCKED/STOP_REFERENCE_DESIGN.md
OPTIONS_LISTED: A_KEEP / B_REPLACE_ZONE_FAR_EDGE / C_FLOOR_ZONE_FAR_EDGE / D_DEFER
CODE_CITATIONS: YES (trigger_f_bos_ob.py:85-98, base_trigger.py:44,96-110, pipeline_bridge.py:272,290, engine.py:121-124)
LOCKED_TEXT_QUOTED: YES (EXPERT_MASTER_CARD.md:96,140; LOCKED_DECISIONS.md:98,604-606)
NO_OUTSIDE_POI_CLAUSE: CONFIRMED ABSENT (closest text is an open question, ENTRY_REPRESENTATION_DESIGN.md:293-295)
MEASURE_PREREGISTERED: YES (population, per-option rule, metrics, kill criterion, path convention)
COUNTERFACTUAL_RUN: NO
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
NEXT_READY: Architect ACCEPT + option letter
```
