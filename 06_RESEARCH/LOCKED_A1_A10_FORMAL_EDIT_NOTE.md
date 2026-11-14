# LOCKED_DECISIONS § EDITS — EXPERT AMENDMENTS A1–A10

**Date:** 2026-11-14 · **Scope:** DOCS ONLY · **Status:** PASS
**Authority:** `00_LOCKED/EXPERT_MASTER_CARD.md` (signed 2026-11-12),
`00_LOCKED/EXPERT_AMENDMENT_LIST_2026-11-12.md` (rows A1–A10).
**`LOGIC_CHANGED: NO`** — no `04_SRC/**` edit, no `locked_constants.py` edit, no
strategy/threshold change, no reliance on the October diagnostic as edge.

---

## 1. Method / files read

- `00_LOCKED/EXPERT_MASTER_CARD.md` — §1 story, §3.1–§3.6 frozen tables, §4 non-goals.
- `00_LOCKED/EXPERT_AMENDMENT_LIST_2026-11-12.md` — the authoritative A1–A10 rows
  (their real subjects are A1 Rule 3, A2 color-free D/S, A3 TP, A4 SL, A5 Pillar-3
  naming, A6 M7 plane, A7 letter map, A8 POI TFs, A9 no dual chain, A10 ESSENCE
  notice; the prompt's sketch mapped differently, so **the file was followed**).
- `00_LOCKED/LOCKED_DECISIONS.md` (696 → 800 lines) — §4/§4a, §8, §16, §17, §20,
  §21, §22, §24, §25.
- `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` §1 (D0) — M15 in the shipped product set.
- Implementation records already shipped: `C2A_CHOCH_R3_LIVE_OFF_NOTE.md`,
  `C3_IN_BETWEEN_GATE_NOTE.md`, `C2B_COLOR_FREE_DS_NOTE.md`.

Method: **dated amendment blocks added**, never silent deletion. Every block names
the paragraph it supersedes; the original text stays for audit history. A new **§0
register** maps A1–A10 to the block that carries each rule.

---

## 2. Per-amendment table

| ID | Requirement (from the amendment list) | Edit / record | Status |
|---|---|---|---|
| **A1** | CHOCH Rule 3 is research only; live CHOCH = Rule 1 / Rule 2 body close | **§17a** supersedes "Strength: Lowest — KEPT… Valid signal" and sub-variant 3c "Valid signal"; **§20a** retires the Rule 3 wick-pierced entry. Cites C2a (`is_live_choch`) and keeps classifier geometry. | AMENDED |
| **A2** | OB / Demand-Supply identification color-free; width = single origin candle, full OHLC + wicks | **§22a** supersedes the color predicates and §22 step 3; **§21a** carries the Model-8 table rows. Width, `DISPLACEMENT_MIN_ATR`, `N_BAR_LTF` unchanged. Cites C2b. | AMENDED |
| **A3** | Product TP = first valid swing only; ESSENCE 1:5 = benchmark | **§21b** supersedes "RR Target: Minimum 1:5" for product intent; keeps the ATR fallback and labels 1:5 a benchmark. | AMENDED |
| **A4** | Product SL = existing ATR buffer; 30-pip and 2–5 pip M1 SL = benchmarks | **§21b** supersedes "SL: … (2–5 pips typical)"; 30-pip recorded as MAE/review benchmark only. | AMENDED |
| **A5** | Pillar 3 product name = Dealing Range; Premium/Discount is an alias | **§16a** (naming only; five pillars unchanged, no sixth pillar). | AMENDED |
| **A6** | M7 plane = FLIP; repeated tests exhaust supply before decisive mitigation/flip | **§8a** adds the plane definition; M5 vs M7 distinction preserved. | AMENDED |
| **A7** | Permanent letter map A=CHOCH R1/R2, B=Leading W2, C=Ending Diagonal **live**, D, E, F | **§24a** records the permanent dictionary and C's live status; §15/§24 tables already consistent, §12 chronological routing unchanged. | AMENDED |
| **A8** | POI inventory TFs = M15, H1, H4, D1; W1 optional; M1/M5 confirm only | **§4b** supersedes §4/§21 where M15 is missing; aligns with the D0 runtime contract `(D1,H4,H1,M15)`; §4a floor unchanged. | AMENDED |
| **A9** | No dual HTF→LTF confirmation chain; structure TFs give bias/zones, LTF enters inside the zone | **§21c** clarifies the 3-step wording as zone → approach → entry (not two confirmations); runtime TF choice unchanged. | AMENDED |
| **A10** | ESSENCE signed page stays a record; TP/SL/entry rows superseded by the card | ESSENCE header notice already added in D0; **§0 register** records the pointer. No LOCKED body conflict remained. | ALREADY_ALIGNED |

Additional (not an A-row, shipped behaviour already in code): **§25 clarification**
— the in-between condition is **REQUIRED** entry validity, the shipped gate uses the
completion bar's **close** inside the inclusive zone body (C3), median-of-zone stays
placement-only, and the boundary-sweep fallback remains design-only (no emitter).

**Dangerous-leftover sweep** (`grep` over LOCKED_DECISIONS): "KEPT in the system",
"Valid signal at lowest strength", "single last bearish candle", "2–5 pips typical",
"RR Target: Minimum 1:5", "Premium/Discount" (as a pillar name) all still exist **as
historical text and are explicitly superseded by the named block** — no undated
residual standing rule. M1 is never stated as the sole structural TF; §4b fixes the
M15 omission.

---

## 3. New § amendment headers added

- §0 Expert master card amendment register (2026-11-12)
- §4b POI inventory timeframes include M15 (A8)
- §8a Model 7 plane = FLIP (A6)
- §16a Pillar 3 product name = Dealing Range (A5)
- §17a CHOCH Rule 3 is research-only (A1)
- §20a Rule 3 entry placement is not a product entry (A1)
- §21a Model 8 zones are color-free (A2)
- §21b TP and SL product rules (A3, A4)
- §21c no dual confirmation chain (A9)
- §22a Demand/Supply identification is color-free (A2)
- §24a permanent entry letter map (A7)
- §25 dated clarification (C3 in-between gate; not an A-row)

---

## 4. Explicit non-edits

- **`04_SRC/**` untouched** (`git diff -- 04_SRC` empty) — no code, no behaviour.
- **`locked_constants.py` untouched** (diff empty); no new number anywhere.
- **ESSENCE body untouched** (only the D0 header notice, already committed).
- No C3 softening (in-between remains REQUIRED), no R3 re-enable, no D/S recolor,
  no boundary-sweep implementation, no DEVELOPMENT_PLAN bulk edit.
- No performance/edge claim; the October diagnostic is not cited as validation.

---

## 5. Return block

```text
LOCKED_EDIT_STATUS: PASS
AMENDMENTS_ADDRESSED: 10/10
AMENDED: 9
ALREADY_ALIGNED: 1
DEFERRED: 0
SECTIONS_TOUCHED: §0, §4b, §8a, §16a, §17a, §20a, §21a, §21b, §21c, §22a, §24a, §25
NOTE_PATH: 06_RESEARCH/LOCKED_A1_A10_FORMAL_EDIT_NOTE.md
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
SRC_DIFF: empty
HANDOFF_UPDATED: YES
NEXT_READY: Harness M15 product-diagnostic hygiene | boundary-sweep design | Architect pick
```
