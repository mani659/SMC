# ESSENCE CONTRACT v1 (DRAFT) — **SUPERSEDED by ESSENCE_CONTRACT_V1.md**

> **SUPERSEDED by ESSENCE_CONTRACT_V1.md** (SIGNED 2026-10-21, Owner Salman
> + Architect). This draft is kept for history only — do not implement from
> it. The live, signed page is
> [`00_LOCKED/ESSENCE_CONTRACT_V1.md`](ESSENCE_CONTRACT_V1.md); the code
> mapping that follows the sign-off is
> `06_RESEARCH/ESSENCE_V1_CODE_MAPPING.md` (MAPPING — NOT FULL
> IMPLEMENTATION).

**Status:** SUPERSEDED — **NOT IMPLEMENTED — HISTORICAL DRAFT ONLY**
**Date:** 2026-10-21 · **Authority:** Architect 2026-10-21 (drafting task)
**Banner: SUPERSEDED DRAFT — HISTORICAL ONLY — SIGNED PAGE IS ESSENCE_CONTRACT_V1.md**

**Sources:** `06_RESEARCH/PRODUCT_FOUNDATION_INVENTORY.md` §5–§7 (SAFE +
UNRESOLVED) · `00_LOCKED/LOCKED_DECISIONS.md` §16/§21 (cited, not rewritten) ·
`00_LOCKED/MODEL_8_HTF_DEMAND_SUPPLY.md` · `00_LOCKED/CHOCH_TYPES_AND_SWING_VALIDITY.md` ·
expert KB (`02_KNOWLEDGE_BASE/`, `03_REFERENCE_CODE/expert_marked_charts/`).
DUMB (`06_RESEARCH/DUMB_FLOWCHART_V1_DESIGN.md` R1–R6) appears only as
contrast in Appendix C — **it is not this contract's default.**

**This draft does NOT claim that COMPLEX or DUMB already implements it.**
No strategy code, threshold, or `locked_constants.py` value was touched by
this document. Docs only.

> **How to use:** every section marked **OWNER_MUST_PICK** needs one written
> choice from the owner/expert. Sections marked **SAFE** are already sourced
> from locked/expert documents and can be signed as-is. **Implementation is
> blocked until every OWNER_MUST_PICK row in §9 is filled.**

---

## 0. Product loop (non-negotiable intent)

The bot opens and manages trades under exactly the rules below, producing a
**small readable sample** — not the maximum number of trades. Each closed
trade is scored by the expert against the five stages (**Level / Sweep /
Confirm / Entry / Manage**, §8). Changes to the contract happen **one rule at
a time**, as dated amendments, never silently. A trade that fails gets blamed
on the stage that failed — that is the whole point of keeping the story this
short.

## 1. Level (POI) — SAFE

**The level is a Higher-Timeframe institutional zone**: Demand/Supply or
Order Block or FVG on **D1 / H4 / H1** (W1 optional context only; M30/M15/M5/M1
are not level timeframes). Demand = the **single last bearish candle** before a
strong bullish impulse; Supply = the single last bullish candle before a strong
bearish impulse; the zone is that one candle's **full range, wicks included**.
A zone is tradeable once, on its **first touch** (strict 1-touch freshness).
*Source: `LOCKED_DECISIONS.md` §21/§22/§5; `MODEL_8_HTF_DEMAND_SUPPLY.md` §2;
`PRODUCT_FOUNDATION_INVENTORY.md` §7.*

## 2. Sweep — SAFE (with one pick)

**A sweep is a wick that pierces beyond the level and a candle that closes
back inside it.** A candle that *closes* beyond the level is a breakout, not a
sweep — it does not qualify. Only structural levels qualify (equal highs/lows
within ≤ 4.5 pips on gold; session/prior-day/prior-week extremes; validated
swing points). *Source: `LOCKED_DECISIONS.md` §2/§19; `SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md` §3.5.*

**OWNER_MUST_PICK — fallback boundary sweeps** (locked intent, not yet built):
**[ ] include later · [ ] out of v1** — when price blows through a zone
without an in-between entry, the locked rules say to watch for a sweep of the
zone extreme instead of invalidating (`LOCKED_DECISIONS.md` §2 rules 5–6).
Default for v1: **out of v1** (recorded, not silently forgotten).

## 3. Confirmation — OWNER_MUST_PICK

The full named-pattern set (18 patterns, CHOCH body-close strongest, ending
diagonal preferred at HTF zones) is inventoried with sources in
**Appendix A**. The owner picks which set is **mandatory** for v1 — this is
the most important blank on the page:

**OWNER_MUST_PICK — mandatory confirmation set for v1:**
- **[ ] A) Full 18-pattern set** (any Appendix A pattern confirms)
- **[ ] B) CHOCH + BOS + OB-reaction only** (three structural confirms)
- **[ ] C) M8 preferred set** (ending diagonal first; BOS / two-bar / CHOCH as alternates)
- **[ ] D) Other — owner writes it here:** __________________

*Never substituted silently:* DUMB's single "close through the zone mid" is a
research proxy and is **not** an acceptable product confirmation unless the
owner writes it in slot D by name (`DUMB_VS_COMPLEX_FLOWCHART_AUDIT.md` §4).

## 4. Entry — SAFE style, OWNER_MUST_PICK timeframe

**Style (SAFE): LIMIT order at the confirmation level, inside the zone —
never a market order.** If the limit is not filled within the resting window
(12 M5 bars), it expires and the idea is done. First valid confirmation in
time wins; one zone + one confirmation + one trade — no re-fires.
*Source: `LOCKED_DECISIONS.md` §9/§10/§12/§23.*

**OWNER_MUST_PICK — entry timeframe:**
- **[ ] A) M1 sniper** (Rev-5 Model 8 path, `LOCKED_DECISIONS.md` §21)
- **[ ] B) M5 runtime** (shipped product, `PRODUCT_RUNTIME_CONTRACT.md` §1)
- **[ ] C) Dual** — M5 plan, M1 fine-entry (owner writes the handoff rule): __________________

## 5. Stop loss — OWNER_MUST_PICK

- **[ ] A) 0.3 × ATR buffer beyond the structure/sweep extreme**
  (locked intent, Foundation Reset R5)
- **[ ] B) 2–5 pips beyond the M1 structure**
  (Model 8 sniper language, `MODEL_8_HTF_DEMAND_SUPPLY.md` §4)
- **[ ] C) 30 pips** (operator's verbatim rule, PENDING since 2026-10-05,
  `06_RESEARCH/EXPERT_CHART_SYSTEM_MATCH_NOTE.md` §5)

No blend unless the owner writes one here: __________________

## 6. Take profit / manage — OWNER_MUST_PICK

- **[ ] A) First swing high/low** (operator's verbatim rule, PENDING, same note §5)
- **[ ] B) Structural target, else 4 × ATR cap** (locked, currently unfed —
  `FOUNDATION_RESET_PLAN.md` R4)
- **[ ] C) Fixed R** — owner states R: ______
- **[ ] D) Model 8 profile** (macro HTF target, minimum 1:5)

**OWNER_MUST_PICK — break-even management:** **[ ] ON · [ ] OFF** for
essence v1. (ON = move stop to entry after a favorable 1.0 × ATR move, the
PureRunner rule, `LOCKED_DECISIONS.md` §28.1; OFF = every trade ends at its
original stop or target, which makes expert scoring of stages 5–6 much
cleaner. Recommendation is the owner's call, not this draft's.)

## 7. Explicitly OUT of essence v1 (unless the owner adds by name)

Five-pillar validation as hard vetoes · Trigger D while the feed has no
volume · seek/scan posture stack · Mode B · DUMB's mid-only confirm ·
spray-class multi-fire (many trades per zone) · news calendar gating ·
any D1-only or M30 "detection TF" role beyond the level set in §1.

## 8. Expert scoring rubric (mandatory)

Every closed trade is scored by the expert, stage by stage, **without looking
at PnL first**:

| stage | mark |
|---|---|
| 1. Level | CORRECT / PARTIAL / WRONG / UNCLEAR |
| 2. Sweep | CORRECT / PARTIAL / WRONG / UNCLEAR |
| 3. Confirm | CORRECT / PARTIAL / WRONG / UNCLEAR |
| 4. Entry (style **and TF**) | CORRECT / PARTIAL / WRONG / UNCLEAR |
| 5. Stop | CORRECT / PARTIAL / WRONG / UNCLEAR |
| 6. TP / manage | CORRECT / PARTIAL / WRONG / UNCLEAR |

**A wrong entry timeframe is a first-class WRONG mark** (example: "should be
M1, was M5") — it is scored, not tolerated. UNCLEAR is a legal answer and is
reported as itself, never rounded to CORRECT. Rubric scoring follows the
precedent of `06_RESEARCH/FLOWCHART_MATCH_NOTES.md` (conservative marks,
geometry unverifiable → PARTIAL/UNCLEAR, never visual-guessed CORRECT).

## 9. Sign-off block

```
Owner: ____________   Expert: ____________   Date: ____________

OWNER_MUST_PICK sheet (copy the checked boxes):
  entry TF:      A | B | C (+handoff rule)      ______
  SL:            A | B | C | blend-text          ______
  TP:            A | B | C(+R) | D               ______
  PureRunner BE: ON | OFF                        ______
  confirm set:   A | B | C | D(+text)            ______
  fallback sweep family: include-later | out     ______

Implementation is BLOCKED until every row above is filled and this
page is signed. Each later change = a dated amendment, one rule at a time.
```

---

## Appendix A — Confirmation pattern inventory (18 + sources)

| # | pattern | one-line | source |
|---|---|---|---|
| 1 | Liquidity sweep | wick pierces level, body closes back inside | LOCKED §2; R1 §3.5 |
| 2 | Displacement | BOS + FVG + move ≥ 1× ATR | LOCKED §3 |
| 3 | Base-candle swing validity | swing counts only after close beyond the base candle's opposite extreme | LOCKED §18/§19 |
| 4 | BOS | close beyond prior swing | R1 §3.3 |
| 5 | CHOCH Rule 1 (standard) | body close beyond the trend's last swing — strongest | LOCKED §17 |
| 6 | CHOCH Rule 2 (inside body) | body close beyond an intermediate level | LOCKED §17 |
| 7 | CHOCH Rule 3 (inside wick) | wick only — weakest, kept | LOCKED §17 |
| 8 | OB reaction | OB = candle before the FVG; entry on retest | R1 §3.1 |
| 9 | FVG | 3-candle imbalance; entry at 50% | R1 §3.2 |
| 10 | Quasimodo / QML | left-shoulder full-wick retest | LOCKED §14; R1 M4 |
| 11 | Equal highs/lows | double/triple peaks ≤ 4.5 pips | LOCKED §2 |
| 12 | Double top/bottom — neckline | broken neckline retest | R1 M6 |
| 13 | Double top/bottom + RSI divergence | pattern in zone + RSI divergence (version: owner) | R1 §7 E |
| 14 | Leading diagonal | 5 waves; entry at Fib 50–61.8% of wave 2 | R1 §7 B |
| 15 | Ending diagonal | wave-5 trendline throw-under/over at the zone — preferred at HTF zones | R1 §7 C; LOCKED §15 |
| 16 | Two-bar engulfing + volume | engulfing pair, bar-2 volume lower; limit at 50% body | LOCKED §10/§24 |
| 17 | BOS + OB continuation | trend BOS, retest of the origin OB, first touch | R1 §7 F |
| 18 | In-between entry | trigger fires inside the zone body | LOCKED §25 |

Expert-chart vocabulary worth owner attention (not yet locked rules): M5
double top/bottom, M1/M5 CHOCH, "Fib golden" area, ending diagonal at an H4
FVG — `03_REFERENCE_CODE/expert_marked_charts/` + `06_RESEARCH/EXPERT_MARKED_CHARTS_INDEX.md`.

## Appendix B — Conflicts table (from the inventory, unresolved)

| conflict | side 1 | side 2 | where it bites |
|---|---|---|---|
| Entry TF | M1 sniper (LOCKED §21 / MODEL_8) | M5 runtime (`PRODUCT_RUNTIME_CONTRACT` §1 / §4a) | §4 pick |
| Stop loss | 0.3×ATR buffer (R5) | 2–5 pips (M8) vs 30 pips (operator, PENDING) | §5 pick |
| Take profit | first swing (operator, PENDING) | structural-else-4×ATR (locked, unfed) vs 1:5 profile | §6 pick |
| Confirmation vocabulary | 18-pattern locked set | expert-chart patterns (double top/bottom, Fib golden) not in the coded trigger vocabulary | §3 pick |
| Fallback boundary sweeps | locked intent (§2 rules 5–6) | no emitter in code | §2 pick |
| Trigger D | locked pattern | dead on the volume-less feed | §7 (out unless added) |

## Appendix C — COMPLEX vs this contract vs DUMB (not 1:1)

| stage | this contract | COMPLEX (frozen product) | DUMB (research probe) |
|---|---|---|---|
| Level | HTF zone, first touch | same zone family + 5-pillar gates + dedup registry | same M8 zone, ungated |
| Sweep | wick + close-back | same discipline, plus displacement coupling | same rule at zone extremes |
| Confirm | **owner's mandatory set (§3)** | any of triggers A–F, first valid | single mid-reclaim only |
| Entry | LIMIT in zone, owner's TF | limit everywhere (matches) | market at confirm close |
| SL | **owner's pick (§5)** | structural + 0.3×ATR buffers + BE mutation | sweep extreme + 0.10 ATR, immutable |
| TP / manage | **owner's pick (§6)** | 4×ATR fallback (structural unfed) + full risk layer | fixed 2R, nothing else |

Neither COMPLEX nor DUMB currently implements this contract end-to-end; both
would converge on it only through their own dated paths. The comparison point
stays frozen at `b5e8c53` (`00_LOCKED/BASELINE_COMPLEX_V1_1_COMPARISON_POINT.md`).

---

## Return block

```
ESSENCE_DRAFT_STATUS: PASS
CONTRACT_PATH: 00_LOCKED/ESSENCE_CONTRACT_V1_DRAFT.md
SAFE_SECTIONS_FILLED: YES
OWNER_MUST_PICK_COUNT: 6
OWNER_MUST_PICK_LIST: [entry TF, SL rule, TP rule, PureRunner BE on/off, mandatory confirmation set, fallback boundary-sweep family]
IMPL_BLOCKED_UNTIL_SIGNOFF: YES
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
NEXT_READY: Owner/expert complete OWNER_MUST_PICK and sign
```

**Ledger cross-refs:** SESSION_HANDOFF 2026-10-21 (6) · CHANGELOG 2026-10-21 (6)
· `00_LOCKED/POST_V1_ACTIVE_TODO.md` draft entry.
