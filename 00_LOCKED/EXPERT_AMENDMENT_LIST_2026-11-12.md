# EXPERT AMENDMENT LIST — 2026-11-12

**Status:** ACTIVE record · **Authority:** Lead Architect EXPERT_MASTER_CARD directive (2026-11-12)
**Companion:** `00_LOCKED/EXPERT_MASTER_CARD.md` · **Audit:** `06_RESEARCH/EXPERT_DOCS_ALIGNMENT_AUDIT.md`

This list records **what the master card supersedes**, so no existing document is silently edited.

**Scope rules**
- `ESSENCE_CONTRACT_V1.md` and `LOCKED_DECISIONS.md` file bodies are **NOT rewritten** in this engagement.
- Formal §-level edits to `LOCKED_DECISIONS.md` are a **separate engagement** after the Architect accepts this list.
- Product runtime code is unchanged until an implementation-gap plan is ordered (no auto-code).
- Benchmark rows do not change product behaviour; they only fix the interpretation of the number.

**Dispositions:** `SUPERSEDE_BY_MASTER_CARD` · `BENCHMARK_ONLY` · `UNCHANGED`

| ID | Doc + section | Old claim (≤20 words) | New claim (master card) | Disposition |
|---|---|---|---|---|
| **A1** | `LOCKED_DECISIONS.md` §17 / §20 | "Rule 3 … Wick only … KEPT in the system. Valid signal at lowest strength"; entry at the wick-pierced level | CHOCH Rule 3 is research only; live CHOCH = Rule 1 / Rule 2 with body close | SUPERSEDE_BY_MASTER_CARD |
| **A2** | `LOCKED_DECISIONS.md` §22 / `MODEL_8_HTF_DEMAND_SUPPLY.md` §2 | Demand = "single last bearish candle"; supply = "single last bullish candle"; OB = last opposing candle | OB / Demand-Supply identification is **color-free**; width stays a single origin candle, full OHLC + wicks | SUPERSEDE_BY_MASTER_CARD |
| **A3** | `ESSENCE_CONTRACT_V1.md` §6 | TP = Model-8 profile with hard minimum 1:5; first swing listed as PENDING / not in v1 | Product TP = **first valid swing only** | SUPERSEDE_BY_MASTER_CARD (TP rule); 1:5 retained as BENCHMARK_ONLY |
| **A4** | `ESSENCE_CONTRACT_V1.md` §5; `ESSENCE_CONTRACT_V1_DRAFT.md` §5 | SL = 2–5 pips beyond M1 structure; ATR buffer "Not in v1"; 30-pip operator rule PENDING | Product SL = **existing ATR-buffer path**; 30 pips = MAE/review benchmark; 2–5 pip M1 SL = benchmark | SUPERSEDE_BY_MASTER_CARD (ATR); 30-pip and 2–5 pip = BENCHMARK_ONLY |
| **A5** | `LOCKED_DECISIONS.md` §16 (Stage 2 pillars) | "5 Pillars: Zone Refinement, Displacement, **Premium/Discount**, Freshness, Inducement" | Pillar 3 product name = **Dealing Range**; Premium/Discount is a note alias | SUPERSEDE_BY_MASTER_CARD (naming only) |
| **A6** | `LOCKED_DECISIONS.md` §8 / §23; `SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md` Model 7 | M7 = "Equal Resistance Shelf", reactive retest after expansion; no plane stated | M7 plane = **FLIP**; repeated tests exhaust supply before decisive mitigation/flip | SUPERSEDE_BY_MASTER_CARD |
| **A7** | `LOCKED_DECISIONS.md` §24 / §15; `ESSENCE_CONTRACT_V1.md` §3 | Letter set A–F exists but B = Leading Diagonal and the target set omits C from the v1 view | Permanent map: A=CHOCH R1/R2, B=Leading W2, C=Ending Diagonal (live), D=Two-bar, E=DT/DB+RSI, F=BOS+OB | SUPERSEDE_BY_MASTER_CARD |
| **A8** | `PRODUCT_RUNTIME_CONTRACT.md` §1; `LOCKED_DECISIONS.md` §21 | Detection POI TFs stated as H4+H1 required; Model 8 D1/H4; M15 not listed as a POI TF | POI inventory TFs = **M15, H1, H4, D1**; W1 optional; M1/M5 confirm only | SUPERSEDE_BY_MASTER_CARD (card scope; runtime code untouched) |
| **A9** | `ESSENCE_CONTRACT_V1.md` §0 / §4; `MODEL_8_HTF_DEMAND_SUPPLY.md` §3 | Wording implies an HTF confirmation followed by an LTF confirmation chain; signed entry TF = M1 sniper | Structure TFs give bias + zones; **no dual confirmation chain**; M1/M5 confirm and enter only inside the zone | SUPERSEDE_BY_MASTER_CARD (story wording); runtime TF choice unchanged pending the gap plan |
| **A10** | `ESSENCE_CONTRACT_V1.md` head | "This is the frozen one-page trade story. Every section is now SIGNED." | The page remains a signed record, but its TP/SL/entry-set rows are superseded by this card and list | SUPERSEDE_BY_MASTER_CARD (partial notice — no in-place rewrite) |

---

## What is NOT amended

- Liquidity MAP and sweep-as-story (audit T03/T04) — UNCHANGED.
- In-between binary entry and boundary-sweep fallback (T05/T06) — UNCHANGED.
- Single-origin-candle width (T08) — UNCHANGED; only the color rule is superseded (A2).
- Five-pillar count, freshness, inducement soft score (T10/T11) — UNCHANGED beyond A5 naming.
- M5 definition and the M5/M7 distinction (T12) — UNCHANGED.
- Confluence-score-never-sizing (T17) — UNCHANGED.
- Base-candle swing validity (T02) — UNCHANGED.
- Risk shell, news/breaker/Friday/PureRunner behaviour — UNCHANGED.

---

## Next formal step (separate engagement)

1. Architect accepts `EXPERT_MASTER_CARD.md` and this list.
2. A dated edit of `LOCKED_DECISIONS.md` §16/§17/§20/§22/§24 (and the ESSENCE notice header) folds
   these rows in — as one rule at a time, never by silent rewrite.
3. Only then an implementation-gap plan is ordered; no code changes are made by this engagement.
