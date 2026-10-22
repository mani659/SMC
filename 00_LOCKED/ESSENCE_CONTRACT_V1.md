# ESSENCE CONTRACT v1 (SIGNED)

**Status:** SIGNED 2026-10-21 — **implementation mapping authorized**
**Date:** 2026-10-21 · **Authority:** Owner Salman + Architect 2026-10-21
**Banner: SIGNED ESSENCE CONTRACT v1 — implementation mapping authorized (mapping only; no runtime behaviour changed by this document)**
**Supersedes:** `00_LOCKED/ESSENCE_CONTRACT_V1_DRAFT.md` (2026-10-21 draft, kept for history)

**Sources:** `06_RESEARCH/PRODUCT_FOUNDATION_INVENTORY.md` §5–§7 (SAFE +
UNRESOLVED) · `00_LOCKED/LOCKED_DECISIONS.md` §16/§21 (cited, not rewritten) ·
`00_LOCKED/MODEL_8_HTF_DEMAND_SUPPLY.md` · `00_LOCKED/CHOCH_TYPES_AND_SWING_VALIDITY.md` ·
expert KB (`02_KNOWLEDGE_BASE/`, `03_REFERENCE_CODE/expert_marked_charts/`).
DUMB (`06_RESEARCH/DUMB_FLOWCHART_V1_DESIGN.md` R1–R6) appears only as
contrast in Appendix C — **it is not this contract's default.**

**This contract does NOT claim that COMPLEX or DUMB already implements it.**
No strategy code, threshold, or `locked_constants.py` value was touched by
this document. Docs only. The code mapping that follows the sign-off lives in
`06_RESEARCH/ESSENCE_V1_CODE_MAPPING.md` and is explicitly **MAPPING — NOT
FULL IMPLEMENTATION**.

> **How to use:** this is the frozen one-page trade story. Every section is
> now **SIGNED** — there are no blanks. Any change is a **dated amendment, one
> rule at a time**, recorded in `00_LOCKED/CHANGELOG.md`; nothing changes
> silently.

---

## 0. Product loop (non-negotiable intent)

The bot opens and manages trades under exactly the rules below, producing a
**small readable sample** — not the maximum number of trades. Each closed
trade is scored by the expert against the five stages (**Level / Sweep /
Confirm / Entry / Manage**, §8). Changes to the contract happen **one rule at
a time**, as dated amendments, never silently. A trade that fails gets blamed
on the stage that failed — that is the whole point of keeping the story this
short.

## 1. Level (POI) — SIGNED (SAFE)

**The level is a Higher-Timeframe institutional zone**: Demand/Supply or
Order Block or FVG on **D1 / H4 / H1** (W1 optional context only; M30/M15/M5/M1
are not level timeframes). Demand = the **single last bearish candle** before a
strong bullish impulse; Supply = the single last bullish candle before a strong
bearish impulse; the zone is that one candle's **full range, wicks included**.
A zone is tradeable once, on its **first touch** (strict 1-touch freshness).
*Source: `LOCKED_DECISIONS.md` §21/§22/§5; `MODEL_8_HTF_DEMAND_SUPPLY.md` §2;
`PRODUCT_FOUNDATION_INVENTORY.md` §7.*

## 2. Sweep — SIGNED (SAFE)

**A sweep is a wick that pierces beyond the level and a candle that closes
back inside it.** A candle that *closes* beyond the level is a breakout, not a
sweep — it does not qualify. Only structural levels qualify (equal highs/lows
within ≤ 4.5 pips on gold; session/prior-day/prior-week extremes; validated
swing points). *Source: `LOCKED_DECISIONS.md` §2/§19; `SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md` §3.5.*

**SIGNED — fallback boundary sweeps: INCLUDE LATER (not in the v1 build).**
When price blows through a zone without an in-between entry, the locked rules
say to watch for a sweep of the zone extreme instead of invalidating
(`LOCKED_DECISIONS.md` §2 rules 5–6). The owner signed **include later**: the
family is **OUT of the essence v1 build**, recorded, not silently forgotten.
It enters only by a dated amendment, and it needs an emitter first (there is
none in the product path today — see the mapping).

## 3. Confirmation — SIGNED: option C (M8 preferred set)

The full named-pattern set (18 patterns, CHOCH body-close strongest, ending
diagonal preferred at HTF zones) is inventoried with sources in
**Appendix A**. The owner picked the **mandatory confirmation set for v1**:

**SIGNED — mandatory confirmation set for v1 = C) M8 preferred set:**
- **Primary: ending diagonal (Trigger C)** — wave-5 throw-under/over at the
  zone, the M8-preferred trigger (`LOCKED_DECISIONS.md` §15 ✓★).
- **Alternates in the same set: BOS + OB continuation (Trigger F), two-bar
  engulfing (Trigger D), CHOCH (Trigger A).**
- The set is used at the **M1 surgical timeframe** (see §4).

**Banned as a product confirmation:** DUMB's single "close through the zone
mid" is a research proxy, **not** one of the signed patterns, and must never
be substituted silently (`DUMB_VS_COMPLEX_FLOWCHART_AUDIT.md` §4). Also out:
volume-dependent Trigger D is not a v1 confirmation (the feed carries no
volume), the expert-chart-only vocabulary (M5 double top/bottom, "Fib golden"
area) has **no locked rule** and is not confirmed by this contract, and the
18-pattern inventory in Appendix A is **reference**, not a v1 allow-list — only
the four patterns named above are in v1.

*Never substituted silently:* any confirmation that is not one of the four
named patterns requires a dated amendment to this page.

## 4. Entry — SIGNED: option A (M1 sniper), LIMIT style

**Style (SIGNED, SAFE): LIMIT order at the confirmation level, inside the zone
— never a market order.** If the limit is not filled within the resting
window, it expires and the idea is done. First valid confirmation in time
wins; one zone + one confirmation + one trade — no re-fires.
*Source: `LOCKED_DECISIONS.md` §9/§10/§12/§23.*

**SIGNED — entry timeframe = A) M1 sniper** (Rev-5 Model 8 path,
`LOCKED_DECISIONS.md` §21). The confirmation of §3 is read on **M1**, the
limit rests inside the HTF zone, and the stop of §5 is an M1-structure stop.

> **Implementation note (Architect, 2026-10-21 — a reading aid, not a rule
> change):** the frozen §23 unfilled-expiry is **per execution timeframe** —
> M5 = 12 bars, M1 = 30 bars (`M5_EXPIRY_BARS` / `M1_EXPIRY_BARS`). The draft's
> "12 M5 bars" wording described the M5 runtime; on the signed M1 execution
> timeframe the resting window is 30 M1 bars. The M1 execution itself is a
> **dated runtime-contract amendment** and is tracked as a REQUIRED FOLLOW-UP
> in `06_RESEARCH/ESSENCE_V1_CODE_MAPPING.md` — it is **not** silently
> applied by this page.

## 5. Stop loss — SIGNED: option B (2–5 pips beyond M1 structure)

**SIGNED — stop loss = B) 2–5 pips beyond the M1 structure** (Model 8 sniper
language, `MODEL_8_HTF_DEMAND_SUPPLY.md` §4; `locked_constants.M8_SL_MIN_PIPS`
= 2.0 / `M8_SL_MAX_PIPS` = 5.0). The stop sits beyond the M1 structure that
produced the confirmation (the M1 swing extreme / the wave-5 terminal wick),
not beyond a higher-timeframe extreme and not at a fixed pip count.

**Not in v1:** the 0.3 × ATR buffer rule (locked FR-2 intent) and the
operator's 30-pip rule (PENDING since 2026-10-05,
`06_RESEARCH/EXPERT_CHART_SYSTEM_MATCH_NOTE.md` §5) are **superseded for v1
trades**; the per-route buffer change is listed as a REQUIRED FOLLOW-UP in
the mapping (never a silent constant edit).

## 6. Take profit / manage — SIGNED: option D (Model 8 profile, min 1:5) + PureRunner BE ON

**SIGNED — take profit = D) Model 8 profile:** the macro HTF target with a
**minimum 1:5 risk:reward** (`locked_constants.M8_MIN_RR` = 5.0;
`MODEL_8_HTF_DEMAND_SUPPLY.md` §4). A trade whose target cannot reach 1:5 is
**not taken** — the 1:5 is a hard gate, not a hint. A structural/HTF target
source must therefore be fed; without one, the trade is blocked, never
silently downgraded to a shorter target.

**Not in v1:** first-swing-high/low (operator's verbatim rule, PENDING) and the
structural-else-4×ATR cap (locked, currently unfed) are **not** the v1 target
rule; the 4×ATR fallback is explicitly **not** a substitute for a 1:5 target.

**SIGNED — PureRunner break-even management = ON** (1.0 × ATR move to
break-even, **100% runner** — no partial closes, the position runs to its
target). This is the locked §28.1 rule (`PURE_RUNNER_BE_ATR` = 1.0,
`PURE_RUNNER_BE_BUFFER_ATR` = 0.10) and is the v1 manage rule. A break-even
move still allows the trade to reach its 1:5 target; it never shortens the
target itself.

## 7. Explicitly OUT of essence v1 (unless the owner adds by name)

Five-pillar validation as hard vetoes · Trigger D while the feed has no
volume · seek/scan posture stack · Mode B · DUMB's mid-only confirm ·
spray-class multi-fire (many trades per zone) · news calendar gating ·
any D1-only or M30 "detection TF" role beyond the level set in §1 ·
**the fallback boundary-sweep family (§2, signed "include later")**.

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

## 9. Sign-off block (FILLED — SIGNED 2026-10-21)

```
Owner: Salman              Expert: —            Date: 2026-10-21
Architect: (Architect role)                      Date: 2026-10-21

SIGNED OWNER_MUST_PICK sheet (copy of the checked boxes):
  entry TF:      A (M1 sniper)                 [X]   → §4
  SL:            B (2-5 pips beyond M1 structure) [X] → §5
  TP:            D (Model 8 profile, min 1:5)   [X]   → §6
  PureRunner BE: ON                              [X]   → §6
  confirm set:   C (M8 preferred set)            [X]   → §3
  fallback sweep family: include later           [X]   → §2

Implementation is AUTHORIZED for MAPPING (2026-10-21). The mapping lives in
06_RESEARCH/ESSENCE_V1_CODE_MAPPING.md. Each later change = a dated
amendment, one rule at a time.
```

---

## Appendix A — Confirmation pattern inventory (18 + sources)

*(Reference inventory. For v1 only the four patterns named in §3 are
mandatory: ending diagonal (C), BOS+OB (F), two-bar engulfing (D), CHOCH (A).)*

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
None of these is a v1 confirmation unless it is one of the four in §3.

## Appendix B — Conflicts table (from the inventory) + how the signature resolved each

| conflict | side 1 | side 2 | signed resolution |
|---|---|---|---|
| Entry TF | M1 sniper (LOCKED §21 / MODEL_8) | M5 runtime (`PRODUCT_RUNTIME_CONTRACT` §1 / §4a) | **A — M1 sniper** (§4); the M5 runtime remains the shipped product until a dated runtime-contract amendment lands (mapping REQUIRED FOLLOW-UP) |
| Stop loss | 0.3×ATR buffer (R5) | 2–5 pips (M8) vs 30 pips (operator, PENDING) | **B — 2–5 pips beyond M1 structure** (§5) |
| Take profit | first swing (operator, PENDING) | structural-else-4×ATR (locked, unfed) vs 1:5 profile | **D — M8 profile, min 1:5** (§6) |
| Confirmation vocabulary | 18-pattern locked set | expert-chart patterns (double top/bottom, Fib golden) not in the coded trigger vocabulary | **C — M8 preferred set** (§3): ending diagonal primary; F/D/A alternates; expert-chart-only vocabulary out |
| Fallback boundary sweeps | locked intent (§2 rules 5–6) | no emitter in code | **include later** — out of the v1 build (§2) |
| Trigger D | locked pattern | dead on the volume-less feed | out of v1 (§7) — D stays in the §3 set only as the *two-bar engulfing* rule, which never required volume; the volume-dependent variant is excluded |

## Appendix C — COMPLEX vs this contract vs DUMB (not 1:1)

| stage | this contract (SIGNED) | COMPLEX (frozen product) | DUMB (research probe) |
|---|---|---|---|
| Level | HTF zone, first touch | same zone family + 5-pillar gates + dedup registry | same M8 zone, ungated |
| Sweep | wick + close-back on structural levels | same discipline, plus displacement coupling | same rule at zone extremes |
| Confirm | **ending diagonal / F / D / A (§3)** | any of triggers A–F, first valid | single mid-reclaim only |
| Entry | LIMIT in zone, **M1** (§4) | limit everywhere, M5 execution | market at confirm close |
| SL | **2–5 pips beyond M1 structure (§5)** | structural + 0.3×ATR buffers + BE mutation | sweep extreme + 0.10 ATR, immutable |
| TP / manage | **M8 profile, min 1:5 + BE ON (§6)** | 4×ATR fallback (structural unfed) + full risk layer | fixed 2R, nothing else |

Neither COMPLEX nor DUMB currently implements this contract end-to-end; both
would converge on it only through their own dated paths. The comparison point
stays frozen at `b5e8c53` (`00_LOCKED/BASELINE_COMPLEX_V1_1_COMPARISON_POINT.md`).

---

## Return block

```
ESSENCE_SIGN_OFF_STATUS: PASS
CONTRACT_PATH: 00_LOCKED/ESSENCE_CONTRACT_V1.md
DRAFT_SUPERSEDED: 00_LOCKED/ESSENCE_CONTRACT_V1_DRAFT.md (header marked SUPERSEDED)
OWNER_MUST_PICK_COUNT: 0 (all 6 filled: entry TF=A, SL=B, TP=D, PureRunner BE=ON, confirm set=C, fallback sweep=include later)
IMPL_AUTHORIZED: MAPPING ONLY (06_RESEARCH/ESSENCE_V1_CODE_MAPPING.md)
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
NEXT_READY: Essence v1 implement prompt (Architect) after the mapping's REQUIRED FOLLOW-UP list is ruled on
```

**Ledger cross-refs:** SESSION_HANDOFF 2026-10-21 (7) · CHANGELOG 2026-10-21 (7)
· `00_LOCKED/POST_V1_ACTIVE_TODO.md` sign-off entry.
