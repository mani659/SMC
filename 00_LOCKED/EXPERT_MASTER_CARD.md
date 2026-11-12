# EXPERT MASTER CARD

**Status:** ACTIVE — signed 2026-11-12
**Authority:** Lead Architect EXPERT_MASTER_CARD directive (2026-11-12), built on the signed
questionnaire and `06_RESEARCH/EXPERT_DOCS_ALIGNMENT_AUDIT.md`.
**Supersedes:** the conflicting rows listed in `00_LOCKED/EXPERT_AMENDMENT_LIST_2026-11-12.md`
only. `ESSENCE_CONTRACT_V1.md` and `LOCKED_DECISIONS.md` bodies are NOT rewritten by this card.
**Logic:** documentation only — no strategy code, no threshold, no runtime change.

---

## 1. Story (one paragraph)

Structure timeframes supply **bias and location**: they mark the liquidity pools, the structural
swings and the POI zones where inventory was built. The sweep of a pool is **part of that story**,
not the trade. Price must then reach a POI zone, and only **while price is still inside the zone**
may an LTF trigger complete — that is the in-between entry, and it is the only way an entry becomes
valid. If price never gives an in-between entry, the already-documented boundary-sweep fallback
applies. There is **no** "HTF confirms, then LTF confirms again" second chain: M15/H1/H4/D1 define
zones; M1/M5 confirm and enter against them.

---

## 2. Information flow

```
STRUCTURAL TFs  M15 / H1 / H4 / D1   (+ W1 optional context if provisioned)
        │  bias + liquidity MAP + POI zones (OB / D-S / FVG / structural)
        ▼
POI ZONE (HTF location)  ── sweep story / boundary-sweep fallback
        │
        ▼
LTF CONFIRM  M1 / M5  — valid only IN-BETWEEN (inside zone high–low)
        │  trigger completes while price is still inside the zone
        ▼
DECISION ENGINE  (pillars 1–5, confluence score = ranking only)
        │
        ▼
ORDER → MANAGE  (existing Stage 4–5 risk shell, unchanged)
```

---

## 3. Frozen tables

### 3.1 POI inventory timeframes (V1)

| Role | Timeframes |
|---|---|
| Structural POIs (bias + zones) | **M15, H1, H4, D1** |
| Optional context | **W1** only if already provisioned; never required |
| Confirmation / entry only (never create POIs) | **M1, M5** |

### 3.2 Entry letter map (V1 LIVE — permanent dictionary)

| Letter | Pattern | Live |
|---|---|---|
| **A** | CHOCH Rule 1 / Rule 2 (body close) | YES |
| **B** | Leading diagonal (W2 / Fib golden-zone family per existing specs) | YES |
| **C** | Ending diagonal (W5 throw-under sniper) | YES — measurement in V1 |
| **D** | Two-bar reversal | YES |
| **E** | Double top/bottom + RSI divergence | YES |
| **F** | BOS + OB / continuation (color-free OB path) | YES |
| — | CHOCH Rule 3 (wick-only) | **NO — research only** |

Routing stays **chronological first-valid**; no new grade tie-break is invented here.

### 3.3 Pillars (exactly five)

| # | Pillar | Note |
|---|---|---|
| 1 | Refinement | unchanged |
| 2 | Displacement | unchanged |
| 3 | **Dealing Range** | product name; "Premium/Discount" is an accepted alias in notes |
| 4 | Freshness | unchanged |
| 5 | Inducement | soft modifier, not a hard kill |

**No sixth pillar.** Liquidity-prior lives in the Stage 0 liquidity MAP / sweep story.

### 3.4 In-between entry (binary)

| Condition | Required |
|---|---|
| Price inside the zone body (between zone high and zone low) | YES |
| A valid LTF trigger (A–F) completes while price is still inside | YES |
| Median of the zone | optional placement preference only — **not** a validity gate |
| No in-between entry | boundary-sweep fallback path (already documented) |

### 3.5 Swings, zones, TP/SL

| Topic | Rule |
|---|---|
| Valid swing | base-candle opposite extreme broken **and** body closed beyond it |
| OB / Demand-Supply | **color-free** identification; width = **single origin candle**, full OHLC + wicks; coupled to the displacement / FVG story |
| TP (product) | **first valid swing only** |
| SL (product) | existing **ATR-buffer** path |
| Benchmarks (not product) | 30-pip SL (MAE review), ESSENCE Model-8 1:5 TP profile, ESSENCE 2–5 pip M1 SL |
| Confluence score | ranking / quality only — **never** lot sizing |
| Risk band / lot policy | unchanged by this card (existing Stage 4–5 shell) |

### 3.6 Models (naming)

| Model | Definition |
|---|---|
| **M5** | Equal Highs Continuation — breakout continuation across predefined liquidity pools |
| **M7** | Equal Resistance Shelf — plane **FLIP**; repeated tests exhaust supply before decisive mitigation / flip |

M5 and M7 are distinct and must not be collapsed.

---

## 4. Explicit non-goals

- No dual HTF→LTF confirmation chain; structure TFs give zones/bias, LTF gives the entry.
- CHOCH Rule 3 is **not** a live trigger; body close is required for live CHOCH.
- Confluence score is not position sizing.
- 30-pip SL is **not** the product stop; the ATR buffer stays.
- The ESSENCE Model-8 1:5 TP profile and 2–5 pip M1 SL are benchmarks only.
- No new models, pillars, pip sizes, or thresholds are introduced by this card.

---

## 5. Open items deferred

None. All prior OPEN_DESIGN rows (entry-catalog mapping, entry timeframe/gate) are settled by
the signed authority above and recorded in the amendment list.

---

## 6. Return block

```text
MASTER_CARD_STATUS: PASS
PATH: 00_LOCKED/EXPERT_MASTER_CARD.md
AMENDMENT_LIST_PATH: 00_LOCKED/EXPERT_AMENDMENT_LIST_2026-11-12.md
M15_POI: YES
TRIGGER_C_LIVE: YES
LETTER_MAP: A=CHOCH_R1R2 B=LEADING_W2 C=ENDING_DIAG D=TWO_BAR E=DTDB_RSI F=BOS_OB
TP_PRODUCT: first_valid_swing
SL_PRODUCT: atr_buffer
BENCHMARKS: 30pip_sl, essence_1_5_tp, essence_2_5pip_sl
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
HANDOFF_UPDATED: YES
NEXT_READY: Architect accept card → implementation gap plan (no auto-code)
```
