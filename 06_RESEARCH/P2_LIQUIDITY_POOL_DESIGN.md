# P2 Liquidity Pool Design Lock — Ranking / Interaction

**Status:** DESIGN LOCK — pending Architect accept (no implementation)  
**Date:** 2026-11-11  
**Authority:** Lead Architect P2 design directive. `LOGIC_CHANGED: NO` — this document is design only; no code was written under `04_SRC/smc/**` and no `locked_constants.py` value changed.  
**Blocking rule:** no P2 implementation until this note is accepted.

---

## 1. Status / date / authority

- Design-lock artifact for the Stage 0A → Stage 1 seam: which liquidity levels form a **pool**, how they are identified and aged, how ranking is (or is not) frozen, and how a pool level hands off to sweep interaction.
- Everything below is a proposal for Architect decision. Where existing locked material does not settle a question, this note says so and asks (§11) rather than inventing a number.
- No expectancy, edge, frequency or optimisation claim is made anywhere in this document.

## 2. P1 inputs and R-EQH-C restatement

Architect P1 geometry rulings (2026-11-11) — the only accepted inputs to this design:

| Family | P1 decision | Eligible for P2 pool |
|---|---|---|
| PDH / PDL | PASS | YES |
| PWH / PWL | PASS | YES |
| Session H/L | PASS | YES |
| Structural swing | PASS | YES |
| EQH / EQL | HOLD | **NO — R-EQH-C** (research export only) |

**R-EQH-C (binding):** EQH/EQL is excluded from the P1/P2 pool entirely. It may still be produced by `detect_equal_levels` for research export, and it stays in the locked §2 classification table, but the P2 pool must not contain EQH or EQL members, must not rank them, and must not emit pool sweeps for them. Any future re-admission requires an explicit new Architect ruling.

Evidence base: `06_RESEARCH/P1_INDEPENDENT_VERIFY_NOTE.md`, `06_RESEARCH/P1_CHART_CONTRACT_AND_WRONG_EXTREME_AUDIT.md`, `06_RESEARCH/results/p1_rescore_pack/` (A/B/C scored).

## 3. Code survey (what exists, what is ABSENT)

Read-only survey; paths cited, no module names invented.

| Surface | Path | State |
|---|---|---|
| Level record | `04_SRC/smc/core/liquidity_level.py` | **PRESENT** — `LiquidityLevel(type, level, pool, timeframe, formed_at, swept_at)` + `is_swept`. One mutable `swept_at` (single-sweep record). |
| Level/pool enums | `04_SRC/smc/core/enums.py` | **PRESENT** — `LiquidityType` (8 §2 types), `PoolType` = BSL/SSL/MAJOR_STRUCTURAL/POI/EXTREME_ZONE/OB_EXTREME. Note `PoolType` is a *pool side*, not a registry. |
| Stage 0A emitter | `04_SRC/smc/detection/liquidity_scanner.py` | **PRESENT** — `scan(candles, timeframe, include)`, `ALL_FAMILIES = (session, periodic, equal, structural)`. Deliberately preserves overlapping levels; dedupe/confluence left to the POI layer. |
| PDH/PDL, PWH/PWL | `04_SRC/smc/detection/periodic_levels.py` | **PRESENT** — `detect_periodic_levels(candles, timeframe, as_of)`; prior *completed* day/week; weeks Monday-anchored; `formed_at` = extreme bar timestamp. |
| Session H/L | `04_SRC/smc/detection/session_levels.py` | **PRESENT** — per `(UTC day, session)` group using locked §2 windows; `formed_at` = extreme bar. |
| Structural swings | `04_SRC/smc/detection/structural_swing_detector.py` | **PRESENT** — `detect_swings(candles, timeframe, n=None)`; §27 N (5 HTF / 3 LTF); base candle + §19 validation; `Swing.timestamp` = **base candle** timestamp, `level` = N-bar swing candle extreme. |
| EQH/EQL | `04_SRC/smc/detection/eqh_eql_detector.py` | PRESENT but excluded by R-EQH-C. |
| Sweep detection | `04_SRC/smc/detection/sweep_detector.py` | **PRESENT** — `detect_sweep(candles, level, start_index=0)`, `detect_sweeps`; wick pierce + body close-back; scanning starts strictly **after** `level.formed_at` via `_first_after`. First sweep per level only. |
| Displacement | `04_SRC/smc/detection/displacement_checker.py` | **PRESENT** — `check_displacement(candles, direction, sweep_index, bos_level, atr_period, *, atr, fvgs)`. |
| ATR | `04_SRC/smc/utils/atr.py` | **PRESENT** — `atr_series(candles, period=14)` Wilder/MT5-compatible; `latest_atr`. |
| Stage 0 driver | `04_SRC/smc/orchestration/detection_driver.py` | **PRESENT** — `stage0()` = swings → `scan_liquidity` → `detect_sweeps` → FVGs → ATR → per-sweep displacement; `detect_pois()` passes `liquidity_levels` into all eight models; `attribute_displacement()` assigns the most recent same-direction displacement (recency = sweep index). |
| Product TF policy | `04_SRC/smc/orchestration/multi_tf_runtime.py` | **PRESENT** — `REQUIRED_DETECTION_TIMEFRAMES = (H4, H1)`; W1/D1 optional context; exec M5; `build_htf_prefixes()` enforces the closed-bar contract. |
| Sweep episodes | `04_SRC/smc/orchestration/sweep_episode_coordinator.py` | **PRESENT** — policy-driven closed-bar episodes; `SweepEpisodeKey(symbol, direction, source_timeframe, poi_identity, closed_sweep_timestamp)`; policies D1→H1, H4→M5/M15, H1→M1/M5, M15→M1. |
| Confluence tiers | `04_SRC/smc/poi/confluence_scorer.py` | **PRESENT** — tag-count tiers 1/2/3+ (§1), M8 overlap +0.10; merges overlapping POIs. Applies to **POIs**, not pool levels. |
| Risk sweep cooldown | `04_SRC/smc/risk/sweep_guard.py` | **PRESENT** — failed-sweep cooldown at the risk layer; not a ranking mechanism. |
| **Pool registry / active-pool query** | — | **ABSENT** — no `PoolLevel`, `LevelRegistry`, `active_pool()` or equivalent anywhere in `04_SRC/smc/**`. |
| **Ranking / priority scorer for levels** | — | **ABSENT** — `confluence_scorer` scores POIs by tag count; nothing orders competing liquidity levels. |
| **Directional / HTF bias module** | — | **ABSENT** — `Direction` enum exists for move direction; no market-bias state exists anywhere. |

Additional note: `04_SRC/smc/dumb/` and `04_SRC/smc/essence/` contain separate research runners with their own `is_sweep`/`is_confirm` rules. They are **not** the product path and are out of scope for the pool.

## 4. Normative pool membership

### 4.1 Members (exhaustive)

| Member | Side | Type enum | Source constructor | Source series |
|---|---|---|---|---|
| PDH | BSL | `PREVIOUS_DAY` | `detect_periodic_levels` | detection series (H4, H1) |
| PDL | SSL | `PREVIOUS_DAY` | same | same |
| PWH | BSL | `PREVIOUS_WEEK` | `detect_periodic_levels` | detection series (H4, H1) |
| PWL | SSL | `PREVIOUS_WEEK` | same | same |
| Asia session high / low | BSL / SSL | `SESSION` | `detect_session_levels` | **M5 execution series** (see §11 Q1) |
| London session high / low | BSL / SSL | `SESSION` | same | same |
| NY session high / low | BSL / SSL | `SESSION` | same | same |
| Structural swing high | BSL | `STRUCTURAL_SWING` | `detect_swings` filtered `is_valid` | H4 and H1 (N=5, §27) |
| Structural swing low | SSL | `STRUCTURAL_SWING` | same | same |

That is **9 member classes** (4 periodic + 6 session + 2 structural), all already implemented by locked constructors. No new detector is required.

### 4.2 Non-members (explicit)

- **EQH / EQL** — excluded by R-EQH-C (§2). Not ranked, not swept as pool levels.
- `POI_LEVEL`, `DEMAND_SUPPLY_BOUNDARY`, `ORDER_BLOCK_BOUNDARY` — the §2 rows 6–8 fallback sweep types. They are POI-layer concepts (OB/FVG/D-S zones) and would double-count against POI zones if admitted here. Excluded from the v1 pool (see §11 Q3 for v2).
- M8 HTF demand/supply zones — POI layer, not liquidity levels.
- Internal/minor fractals — never qualified (§2 "Only Structural Swings Considered"; §19 gate).

### 4.3 Timeframe scope (product Mode A)

Anchored to §4a (product detection policy): required detection = **H4 + H1**, optional W1/D1 context, execution = **M5**.

- Periodic levels: computed per detection series (H4 and H1) — same price, two provenance rows if both emit.
- Structural swings: H4 and H1, N=5 (§27). LTF (M5/M15/M30) structural levels are **not** pool members in Mode A; they belong to the LTF confirmation layer.
- Session levels: computed on M5 because H4 bars cannot resolve the 00:00–07:00 / 07:00–13:00 / 13:00–20:00 windows (an H4 bar straddles a session boundary). This is a deliberate provenance exception — the level is *published* into the pool with `source_tf = M5`. Architect decision requested (§11 Q1).
- Weekly (W1) and D1 series are context, not extra pool families beyond PWH/PWL.

### 4.4 Freshness — enter / exit

A pool level must never be usable before its extreme is knowable. This is the core lookahead rule.

| Member | `enter_at` (first usable) | `exit_at` |
|---|---|---|
| PDH / PDL | next UTC midnight after the day completes | next UTC midnight (superseded by the new PDH/PDL), or sweep |
| PWH / PWL | next Monday 00:00 UTC | next Monday 00:00 UTC (superseded), or sweep |
| Session H/L | session close (Asia 07:00, London 13:00, NY 20:00 UTC) | next occurrence of the same session (superseded), or sweep |
| Structural | the §19 confirmation bar close (NOT the base candle) | sweep only |

Notes:
- `LiquidityLevel.formed_at` is the **extreme bar**, which for PDH/PWH and structural is *earlier* than the moment the level is knowable. Reusing `formed_at` for pool freshness would hand the detector bars before publication — a real lookahead defect if reused naively (see §7.2).
- Exit on "superseded" needs no new number: each family has exactly one live level per side per period, so the successor's `enter_at` is the predecessor's `exit_at`.
- No age cap is proposed. An age limit would require a new number, which this task may not invent (§11 Q4).
- The only existing freshness rule in locked material is the POI one-touch rule (§5), which is about POIs, not pool levels. Pool levels additionally record `swept_at` (single sweep, matching `LiquidityLevel` and `detect_sweep`'s first-sweep-only semantics).

### 4.5 Level identity — no new magic numbers

Proposed key: **`level_id = (family, side, period_id)`**

- Exactly one high and one low exist per family per period, so price is *not* needed for identity (and using a price quantum would require inventing a bucketing tolerance).
- `period_id` formats reuse the P1 verification conventions already on disk:
  - PDH/PDL: `YYYY-MM-DD` (UTC day of the extreme)
  - PWH/PWL: `YYYY-MM-DD` (Monday of the week)
  - Session: `YYYY-MM-DD_{ASIA|LONDON|NEW_YORK}`
  - Structural: `{base_bar_iso}` (one swing per base candle per side)
- `price`, `source_tf`, `enter_at`, `exit_at`, `swept_at` are **attributes**, not identity.
- Consequence: the same price reached by a session high and a structural swing yields two ids — intentional, matching §1's "all models are equal tags, no suppression".

## 5. Level identity + lifecycle (summary)

`CREATED → ACTIVE → (SWEPT | SUPERSEDED | EXPIRED?)`

- `CREATED` at the period's completion (extreme known), `ACTIVE` from `enter_at`.
- `SWEPT` when `sweep_detector` confirms wick-pierce + body-close-back after `enter_at`; sets `swept_at` once (no re-arm — consistent with the existing single-sweep record).
- `SUPERSEDED` when the next same-family/same-side level enters.
- `EXPIRED` is deliberately **not** proposed; it needs a number (§11 Q4).

## 6. Ranking proposal

**RANKING_FROZEN: NO — measurement-first.**

Why a frozen ranking cannot be justified from existing material:

| Candidate input | Status | Verdict |
|---|---|---|
| Proximity to price, ATR-normalised | ATR exists (`atr_series`, period 14, Wilder) | **Admissible** — but the normalisation weight is unfrozen; used only as a measured descriptor |
| Family priority (PWH > PDH > Session > Structural) | No locked ordering exists anywhere; §2 treats the 8 types as a classification, and §1 makes models equal | **Not admissible as frozen** — inventing an order would be an unratified threshold |
| Recency / period freshness | `period_id` orders naturally; `enter_at` gives an exact age | Admissible as a descriptor |
| Side alignment with directional bias | **No bias module exists** (survey §3) | **OUT OF SCOPE** for P2 |
| Touch count | Pool levels are single-sweep; `LiquidityLevel.swept_at` holds one event; no multi-touch history exists | Not implementable without new state |
| ML / clustering / fitted weights | Forbidden by directive | Forbidden |

Proposed P2b measurement work (no freezing, no weights):

1. **Co-location census** — how often do 2/3/4 pool families sit within one ATR of each other? (uses existing ATR + level prices).
2. **Publication-order spread** — distribution of `enter_at` gaps when levels cluster, to see whether "which level is freshest" is even discriminating.
3. **Sweep attribution** — of levels in a co-located cluster, which one actually receives the first `detect_sweep` hit? This is the empirical basis any future priority order must rest on.

Only after (3) shows a stable, reproducible ordering should the Architect freeze a priority. This note deliberately reports no such result.

## 7. Sweep interaction contract (lookahead-safe)

### 7.1 "Level swept" definition

Reuse the existing detector unchanged (`04_SRC/smc/detection/sweep_detector.py`):

- BSL: `high > level` **and** `close < level`
- SSL: `low < level` **and** `close > level`

No new tolerance, no displacement requirement at this seam (displacement stays §3, downstream).

### 7.2 Lookahead safety (the important part)

`detect_sweep` bounds the scan at `level.formed_at`. For pool use that is **not** safe:

- PDH's `formed_at` is a bar *inside the prior completed day*, i.e. **before** the level is knowable at the next midnight.
- Structural `formed_at` is the **base candle**, which precedes §19 confirmation.

Therefore the pool seam must call `detect_sweep(candles, level, start_index=<index of first bar at/after enter_at>)`, using `start_index` explicitly. The scanner's existing behaviour must not be changed (no `04_SRC` edit); the pool passes the correct bound. This is a design requirement on the future implementation, not a code change now.

### 7.3 Output contract

```
PoolSweepHit:
    event_type      : "POOL_SWEEP"
    level_id        : (family, side, period_id)
    family          : family
    side            : BSL | SSL
    level_price     : float
    sweep_bar_ts    : datetime (bar open, UTC)
    sweep_bar_index : int
    direction       : LONG (SSL sweep) | SHORT (BSL sweep)
    source_tf       : detection timeframe of the level
```

Direction mapping matches `detection_driver._displacement_for_sweep` (SSL → LONG, BSL → SHORT), so the LTF seek handoff stays consistent with the current path.

### 7.4 Multiple levels swept on the same bar

Emit **all** hits for that bar, no arbitration. Rationale: any tie-break (by family priority, by depth, by freshness) is exactly the ranking decision that is not frozen (§6). Ordering within the list is deterministic by `(family, side, period_id)` only — a stable sort, not a priority. The consumer (POI seek / LTF confirmation) receives the full set; `sweep_episode_coordinator` already de-duplicates by `(symbol, direction, source_timeframe, poi_identity, closed_sweep_timestamp)`, so no new dedupe layer is needed.

## 8. Proposed read API (types only — not implemented)

```python
# Conceptual only. No such module exists today (survey §3: ABSENT).

@dataclass(frozen=True)
class PoolLevel:
    level_id: tuple[str, str, str]   # (family, side, period_id)
    family: str                      # previous_day | previous_week | session | structural_swing
    side: str                        # BSL | SSL
    price: float
    source_tf: Timeframe             # provenance; session = M5
    period_id: str
    formed_at: datetime              # extreme bar (as emitted by the constructor)
    enter_at: datetime               # first bar from which the level is usable
    exit_at: datetime | None         # supersession boundary
    swept_at: datetime | None

def active_pool(as_of: datetime) -> list[PoolLevel]:
    """Levels with enter_at <= as_of < exit_at and swept_at is None.
    Closed-bar only: as_of is a bar-close instant; no partial bar is consulted."""

def swept_levels(bar_close: datetime) -> list[PoolSweepHit]:
    """Pool sweeps confirmed on the bar that closed at bar_close."""

def pool_snapshot(as_of: datetime) -> tuple[list[PoolLevel], list[PoolLevel]]:
    """(active, swept_today) for diagnostics — no ranking applied."""
```

Design constraints on any implementation: `active_pool` must be pure over the prefix of closed bars (no future reads), must never return EQH/EQL, and must return levels ordered deterministically (not by priority).

## 9. Non-goals

- Not a liquidity-map UI or visualisation layer.
- Not EQH rehabilitation or re-admission (R-EQH-C stands).
- Not changing M8 / POI zone geometry, confluence scoring, or `merge_overlapping`.
- Not trade-frequency optimisation, expectancy, or edge measurement.
- Not Mode B (M15/M30 detection).
- Not trigger A–F redesign, fill/TP/SL policy, or risk-layer changes.
- Not a frozen ranking order.

## 10. Implementation plan for later (P2-impl)

Each phase must be independently testable and Architect-approved before the next.

| Phase | Scope | Testable exit criterion |
|---|---|---|
| **P2-impl-1** | Pool membership + lifecycle types (no ranking) | For a frozen window: exactly one live level per (family, side, period) at any `as_of`; no EQH/EQL present; `enter_at` never precedes period completion |
| **P2-impl-2** | Lookahead-safe sweep seam using `start_index = enter_at` | Prefix-trim test: a level formed inside day D is not sweepable on any bar `< enter_at`; results identical when the series is trimmed at `as_of` |
| **P2-impl-3** | Measurement reports (co-location, publication spread, sweep attribution) | Report reproduces deterministically; no weights, no ordering claims |
| **P2-impl-4** | Ranking admission — only if P2-impl-3 shows a stable order | Architect-frozen order with cited measurement; otherwise not implemented |

Bans carried forward: no `locked_constants` edits, no threshold fishing, no expectancy claims, no trigger/fill/TP/SL changes.

## 11. Open questions for Architect (8)

1. **Session series.** Session H/L cannot be resolved on H4 (bars straddle session boundaries). Confirm computing them on M5 and publishing into the pool with `source_tf=M5`, or specify another series.
2. **Structural `enter_at`.** Confirm entry at the §19 confirmation bar close rather than the base candle (recommended; the base candle is not knowable as a swing until confirmation).
3. **POI-family levels.** Are `POI_LEVEL` / `DEMAND_SUPPLY_BOUNDARY` / `ORDER_BLOCK_BOUNDARY` permanently out of the pool, or earmarked for a v2 after POI work?
4. **Age cap.** Should a pool level ever expire by age alone? If yes, an explicit number is needed (none is locked today).
5. **Same-bar multi-sweep.** Confirm "emit all, no arbitration until ranking is frozen" (§7.4).
6. **Directional bias.** Confirm side-alignment stays out of P2 (no bias module exists anywhere in `04_SRC/smc`).
7. **Touch history.** Is single-sweep (`swept_at` once, no re-arm) acceptable for pool levels, or is multi-touch state required before ranking?
8. **Duplicate provenance.** When H4 and H1 both emit the same PDH price, keep two levels (distinct `source_tf`) or collapse to one? Keeping two preserves provenance but doubles pool size.

## 12. Self-check

- **Bans:** no edits under `04_SRC/smc/**`; `locked_constants.py` untouched; no ranking/pool code; no detection changes; no EQH work; no trigger/fill/TP/SL changes; no expectancy claim.
- **Code:** zero production code in this task. Survey only, with paths cited.
- **EQH in pool:** NO (§4.2, R-EQH-C).
- **Ranking frozen:** NO — measurement-first, with the measurement plan in §6.
- **Numbers invented:** none. Every threshold referenced is cited to its locked source (§2 EQH tolerance not used here; §27 N-bar used only to describe existing swing behaviour; ATR period 14 is the existing function default).
- **ABSENT surfaces are named as ABSENT**, not as hypothetical modules.

`LOGIC_CHANGED: NO`
