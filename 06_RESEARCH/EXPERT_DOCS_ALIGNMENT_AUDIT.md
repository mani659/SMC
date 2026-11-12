# EXPERT DOCS ALIGNMENT AUDIT

**Date:** 2026-11-12 · **Type:** READ-ONLY document audit · **Authority:** Lead Architect directive
**Comparison key:** signed human answers (target), not current LOCKED text.
**Scope:** documentation only — no master card, no strategy code, no LOCKED body edits.

---

## 1. Executive summary

- The docs are **not** aligned with the signed target as a whole: 10 of 20 topics match, **7 conflict**, 1 is missing, 2 are stale.
- The largest conflicts are **not** in old drafts — they are in the **SIGNED ESSENCE CONTRACT v1** (TP = Model-8 1:5 profile; SL = 2–5 pips beyond M1 structure; entry timeframe = M1 sniper) and in `LOCKED_DECISIONS.md` §17/§20 (CHOCH Rule 3 kept as a live-eligible signal).
- The signed target also reverses two long-standing zone rules: **color-free OB/D-S** and **first-valid-swing TP**, neither of which is written anywhere in 00_LOCKED.
- Structural strengths are real: the liquidity MAP, sweep definition, in-between entry binary, boundary-sweep fallback, single-origin-candle width, 5-pillar count, M5-vs-M7 separation, and confluence-score-not-sizing rule are all already documented correctly.
- Two topics need a human design choice before a master card can be final (entry-catalog letter mapping / whether Trigger C survives; M1-sniper vs M5 runtime entry TF).
- No master card was drafted in this engagement, and no LOCKED body text was modified.

**Counts:** ALIGNED 10 · CONFLICT 7 · MISSING 1 · STALE 2 (20 topics, HIGH severity 6).

---

## 2. Method

**Files read (17):**

| # | Path | How read |
|---|------|----------|
| 1 | `00_LOCKED/LOCKED_DECISIONS.md` | §1–§28 (multiple windows) |
| 2 | `00_LOCKED/CHOCH_TYPES_AND_SWING_VALIDITY.md` | rule sections + grep |
| 3 | `00_LOCKED/ESSENCE_CONTRACT_V1.md` | head, §4–§6, Appendix B |
| 4 | `00_LOCKED/ESSENCE_CONTRACT_V1_DRAFT.md` | grep (30-pip rows) |
| 5 | `00_LOCKED/MODEL_8_HTF_DEMAND_SUPPLY.md` | OB/D-S sections + grep |
| 6 | `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` | §1–§3 |
| 7 | `00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md` | head |
| 8 | `00_LOCKED/FOUNDATION_RESET_PLAN.md` | head |
| 9 | `00_LOCKED/SESSION_HANDOFF.md` | current top entries + grep |
| 10 | `00_LOCKED/POST_V1_ACTIVE_TODO.md` | current markers + grep |
| 11 | `00_LOCKED/SESSION_ROLES_AND_CONTINUITY.md` | §1–§2 |
| 12 | `00_LOCKED/LEAD_ARCHITECT_ROLE_AND_PROTOCOL.md` | head |
| 13 | `00_LOCKED/CHANGELOG.md` | targeted grep (policy A–E, TP/SL) |
| 14 | `00_LOCKED/SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md` | grep (M5/M7, D/S) |
| 15 | `00_LOCKED/DEVELOPMENT_PLAN.md` | grep (models, confluence) |
| 16 | `01_ARCHITECTURE/Flowcharts/v5_SMC_Locked_Decisions_Flowchart.md` | grep (M5/M7 rows) |
| 17 | `01_ARCHITECTURE/Flowcharts/SMC_Pure_Entry_Models_Flowchart.html` | grep (model/trigger summary) |

**DATA_GAP:** none of the mandatory set is missing. Not opened (deliberately out of scope):
`01_ARCHITECTURE/SMC_Pure_Entry_Models.md`, `02_KNOWLEDGE_BASE/**`, `04_SRC/**`.

**Comparison key (signed target, compressed):**

1. CHOCH R3 wick-only = research only, not live entry; body close required.
2. Five coded pillars only (Refinement, Displacement, Dealing Range, Freshness, Inducement); no 6th.
3. Model 7 = Equal Resistance Shelf, plane Flip.
4. M5 = Equal Highs Continuation across predefined pools; M7 = repeated tests exhaust supply before mitigation/flip.
5. V1 entry set: A, B (CHOCH R1/R2), leading W2, 2-bar, DT/DB+RSI, F; R3 excluded.
6. In-between entry = binary (inside zone high–low AND trigger fires inside); median optional.
7. 30 pips = review/benchmark metric only; ATR buffer stays in product.
8. TP = first valid swing only.
9. D/S zone width = single origin candle (full OHLC/wick range).
10. Confluence score = ranking only, never lot sizing.

**Code:** out of scope; no code archaeology performed. One-line observations only where a doc already
states an implementation claim.

---

## 3. Topic matrix (T01–T20)

| ID | Status | Evidence (doc § / quote) | Target summary | Disposition |
|---|---|---|---|---|
| **T01** | **CONFLICT** | `LOCKED_DECISIONS.md` §17: "Rule 3 … Wick only … KEPT in the system. Valid signal at lowest strength."; §20: "Entry at the wick-pierced level." | R3 is research-only; body close is required for live swing/CHOCH confirmation | SUPERSEDE_WITH_TARGET |
| **T02** | ALIGNED | §19: "A swing is ONLY valid if price breaks the Base Candle's OPPOSITE extreme and CLOSES beyond it." | Valid swing = break of base extreme + opposite-direction body close | — |
| **T03** | ALIGNED | §2 table: session H/L, PDH/PDL, PWH/PWL, EQH/EQL, structural swings, POI/boundary sweeps | Liquidity MAP (session, PDH/PDL, EQ, structural) | — |
| **T04** | ALIGNED | §2 "Master Liquidity Levels & Structural Sweep Architecture (Stage 0A)"; ESSENCE §2 sweep = wick pierce + close-back | Sweep is story, not the final trade | — |
| **T05** | ALIGNED | §25: "exists only when BOTH conditions are met: price enters the zone body … AND a valid LTF trigger fires while … inside" | In-between = binary inside-zone + trigger while inside | — |
| **T06** | ALIGNED | §2 rule 5: "does not give a clean mitigation entry … shifts focus to a boundary sweep"; §25 fallback | Boundary-sweep fallback when no in-between entry | — |
| **T07** | **CONFLICT** | §22: "single last bearish candle" (demand) / "single last bullish candle" (supply); `MODEL_8` §2 "Bullish = last bearish candle before rally" | OB / D-S are color-free | SUPERSEDE_WITH_TARGET |
| **T08** | ALIGNED | §22: "Drawn from the high to the low of that single opposing candle (full body + wicks)" | Single origin candle, full range | — |
| **T09** | ALIGNED | §21 OB = "Last opposing candle before strong impulse"; `MODEL_8` §2 impulse = "displacement > 1× ATR"; Trigger F = "BOS + OB" | OB coupled to displacement/FVG story | — |
| **T10** | **CONFLICT** | §16: "5 Pillars: Zone Refinement, Displacement, **Premium/Discount**, Freshness, Inducement" | Pillars 1–5; pillar 3 named **Dealing Range** | SUPERSEDE_WITH_TARGET |
| **T11** | ALIGNED | §2 is Stage 0A liquidity; §16 pillars contain no liquidity item; `DEVELOPMENT_PLAN` pillars list has none | Liquidity-prior belongs to Stage 0, not a pillar | — |
| **T12** | ALIGNED | §8: "Model 5 is proactive … Model 7 is reactive (bounce creates resistance shelf, then broken)" | M5 continuation vs M7 exhaustion shelf | — |
| **T13** | **MISSING** | §23/§8 name M7 "Equal Resistance Shelf" but no plane/Flip concept anywhere in 00_LOCKED | M7 plane = **Flip** | SUPERSEDE_WITH_TARGET |
| **T14** | **CONFLICT** | §24 table: A CHOCH, B Leading Diagonal, C Ending Diagonal, D Two-Bar, E RSI, F BOS+OB; ESSENCE §3 confirms the M8 set (ED primary, F/D/A alternates) | V1 set: A, B (CHOCH R1/R2), leading W2, 2-bar, DT/DB+RSI, F; R3 excluded | OPEN_DESIGN |
| **T15** | **CONFLICT** | ESSENCE §6: "take profit = D) Model 8 profile … minimum 1:5 risk:reward"; first swing listed as "PENDING" and "Not in v1" | TP = first valid swing only | SUPERSEDE_WITH_TARGET |
| **T16** | **CONFLICT** | ESSENCE §5: "2–5 pips beyond the M1 structure"; §16/`MODEL_8` SL tables "2–5 pips"; 30-pip recorded as PENDING operator rule | SL = ATR buffer in product; 30 pips = review/benchmark only | SUPERSEDE_WITH_TARGET |
| **T17** | ALIGNED | §21/§26: "+0.10 … quality-score bonus only … Do NOT change position size"; §1 score = f(tags) | Confluence = ranking only, never sizing | — |
| **T18** | **CONFLICT** | ESSENCE §4: "entry timeframe = A) M1 sniper" vs `PRODUCT_RUNTIME_CONTRACT` §1 "Execution timeframe — M5 primary" | HTF POI → LTF confirmation (TF not fixed by target) | OPEN_DESIGN |
| **T19** | **STALE** | ESSENCE head: "this is the frozen one-page trade story. Every section is now SIGNED"; its §5/§6/§4 differ from the target | Docs claiming FULLY LOCKED expert story | SUPERSEDE_WITH_TARGET (conflicting rows only) |
| **T20** | **STALE** | `SESSION_HANDOFF.md` top: NEXT ACTION = "Architect + human score of poi_kpi_pack charts/KPI"; no audit/master-card marker | Governance NEXT must place this audit before the master card | — (fixed by this engagement's governance update) |

---

## 4. Ranked action list (CONFLICT / MISSING only)

| Rank | ID | Severity | Item | Recommended disposition |
|---:|---|---|---|---|
| 1 | T01 | **HIGH** | LOCKED §17/§20 keep CHOCH Rule 3 as a valid lowest-strength live signal, with entry at the wick-pierced level and no extra gate | SUPERSEDE_WITH_TARGET (R3 research-only; body close for live) |
| 2 | T15 | **HIGH** | Signed ESSENCE TP is the Model-8 profile with a hard 1:5 gate; first-valid-swing is explicitly excluded ("PENDING") | SUPERSEDE_WITH_TARGET (first valid swing becomes V1 TP; 1:5 gate must be revisited in a dated amendment) |
| 3 | T16 | **HIGH** | Signed ESSENCE SL is 2–5 pips beyond M1 structure; 30-pip rule recorded as PENDING; ATR buffer marked "Not in v1" | SUPERSEDE_WITH_TARGET (ATR buffer in product; 30 pips = benchmark metric only) |
| 4 | T07 | **HIGH** | D/S and OB zone extraction is defined by candle color (demand = last bearish, supply = last bullish) | SUPERSEDE_WITH_TARGET (color-free identification; single origin candle retained) |
| 5 | T19 | **HIGH** | A SIGNED page presents the frozen trade story while its SL/TP/entry-set rows contradict the target | SUPERSEDE_WITH_TARGET for the conflicting rows only; rest of ESSENCE stands |
| 6 | T14 | **HIGH** | Entry catalog letters do not map to the target set: docs B = Leading Diagonal, target B = CHOCH R1/R2; docs include C (Ending Diagonal) which the target omits | OPEN_DESIGN (Architect to fix mapping + C retention) |
| 7 | T10 | MED | Pillar 3 is named Premium/Discount, target names it Dealing Range (count and other names match) | SUPERSEDE_WITH_TARGET (naming only) |
| 8 | T18 | MED | Two LOCKED docs disagree on the entry timeframe (M1 sniper vs M5 runtime); the target fixes neither | OPEN_DESIGN |
| 9 | T13 | MED | M7 "plane: Flip" is absent — the shelf is described only as a reactive retest | SUPERSEDE_WITH_TARGET (add plane Flip to the M7 definition) |
| 10 | T20 | LOW | Governance NEXT markers point at the POI KPI pack, not at this audit | Fixed by the governance update in this engagement |

**Note on T07/T08:** the single-origin-candle width rule (T08) is already correct and independent of the
color rule (T07). A master card must keep T08's geometry while removing the color dependency.

---

## 5. Non-goals of this engagement

- No master card text, outline, or draft.
- No edits under `04_SRC/smc/**`, no threshold changes, no strategy redesign.
- No `locked_constants.py` change (diff verified empty).
- No rewrite of `LOCKED_DECISIONS.md` body text or `PRODUCT_RUNTIME_CONTRACT` normative rules.
- No code archaeology; no expectancy, PF or profitability claim.
- No silent conflict resolution — every disposition above is a recommendation for a human ruling.

---

## 6. Recommendation to Architect

**MASTER_CARD_GATE: HOLD** — the audit is complete, but two rows are genuine design choices, not
wording drift, and one of them changes the trade set.

Minimum human decisions still required:

- **Entry catalog (T14):** confirm the letter↔pattern mapping (is B = CHOCH R1/R2, with the leading
  wave-2 as a separate item?) and decide whether **Trigger C (Ending Diagonal)** stays in V1 — it is
  signed into ESSENCE §3 but absent from the target set.
- **Entry timeframe (T18):** resolve M1 sniper (ESSENCE §4) vs M5 runtime (`PRODUCT_RUNTIME_CONTRACT` §1).
  The target requires HTF POI → LTF confirmation but does not name the TF.
- **Overwrite scope (T15/T16/T19):** confirm that the target's TP and SL rules supersede the SIGNED
  ESSENCE rows by dated amendment (one rule at a time), rather than by editing the signed page in place.

After those three ticks, the remaining CONFLICT rows (T01, T07, T10, T13) can be folded into the master
card directly as SUPERSEDE_WITH_TARGET.

---

## 7. Return block

```text
AUDIT_STATUS: PASS
FILES_READ: 17
TOPIC_ALIGNED: 10
TOPIC_CONFLICT: 7
TOPIC_MISSING: 1
TOPIC_STALE: 2
HIGH_SEVERITY: 6
MASTER_CARD_GATE: HOLD
REPORT_PATH: 06_RESEARCH/EXPERT_DOCS_ALIGNMENT_AUDIT.md
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
HANDOFF_UPDATED: YES
NEXT_READY: human pass on CONFLICT/OPEN_DESIGN rows → master card prompt
```
