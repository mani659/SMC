# SMC-R3-CR — Decision

**Date**: 2026-08-27
**Milestone**: SMC-R3-CR
**Decision**: B — SMC-R3 VALID WITH CONTROLLED AMENDMENT

---

## Decision

SMC-R3 is scientifically sound and methodologically deterministic. Two implementation-level issues require controlled amendment before SMC-R4.

---

## Blockers Found

### Blocker 1 — Cost/Payoff Inconsistency

R3 measured forward return from the next-bar open (the fill price) but also deducted 4 points of spread cost. If the next-bar open IS the fill price, the spread is already embedded. Double-counting.

**Amendment A**: Forward return from next-bar open, no additional cost deduction. The spread is already in the fill price.

### Blocker 2 — Stop/Payoff Role Ambiguity

R3 described the stop as "not part of the primary payoff" but explicitly used it to determine outcomes. The stop simultaneously functions as a filter, an outcome component, and a structural invalidation marker.

**Amendment B**: The stop IS part of the primary outcome. Stopped events contribute their stop-loss result to the mean. The primary metric is "mean net forward return" where stopped events are included.

---

## Non-Blocker Findings

| Finding | Severity | Action |
|---------|:---:|--------|
| MAX_WINDOW=20 is a design choice | Low | Reclassify as C (design choice) |
| Fill = next-bar open is a design choice | Low | Reclassify as C |
| Horizon = 120 bars is a design choice | Low | Reclassify as C |
| HAC lag=10 is a design choice | Low | Reclassify as C |
| OOS split role unclear | Low | Document as discipline preservation |
| "Zero parameters" claim partially misleading | Medium | Correct to "zero data-estimated parameters" |

---

## What Changes

1. Primary metric: forward return from fill price (next-bar open), no cost deduction
2. Stop: explicitly part of primary outcome measurement
3. Design choices: honestly classified as C (researcher selections)
4. OOS split: documented as discipline preservation

## What Does NOT Change

- The economic hypothesis
- The event chain
- The entry price (OB proximal edge)
- The stop reference (OB distal edge)
- The horizon (120 bars)
- The statistical test (one-sided t, HAC)
- The alpha (0.05)
- The chronological split date

---

## SMC-R4 Authorization Status

**NOT YET AUTHORIZED.**

SMC-R4 requires the control session to:
1. Review SMC-R3-CR findings
2. Accept or modify the controlled amendments
3. Confirm the corrected methodology is ready for execution

---

*This decision document records the SMC-R3-CR outcome. The controlled amendment is frozen and applies to SMC-R4.*
