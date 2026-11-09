# Product Policy — Multi-TF Sweep → LTF Confirmation
**Status:** LOCKED for implementation planning  
**Date:** 2026-10-26  
**Authority:** Lead Architect / owner (expert-fidelity goal)

## Purpose
Encode the expert flowchart as-is: HTF structure/sweep, then surgical LTF
confirmation triggers. Primary success metric is **expert-recognizable demo
setups**, not expectancy. DUMB / DUMB-MTF are non-default experiments only.

## Sweep tiers (v1 — no H2)

| Tier | Detection TF | Confirmation TFs | Expiry | Confirm triggers |
|------|--------------|------------------|--------|------------------|
| DAY  | D1           | H1               | 20 bars on **D1** | H1: A,B,C,D,E,F |
| H4   | H4           | M5, M15          | 20 bars on **H4** | M15/M5: A,D,F |
| H1   | H1           | M1, M5           | 20 bars on **H1** | M1/M5: A,D,F |
| M15  | M15          | M1               | 20 bars on **M15**| M1: A,D,F |

- **H2:** out of scope until the expert explicitly uses it.
- Expiry is counted in **detection-TF bars**, not wall-clock alone.

## Normative rules
1. POI/structure is established on the **detection TF**.
2. A **sweep** of that POI arms a one-shot confirmation window.
3. Confirmation runs **only** on that tier’s confirmation TFs, using the
   trigger subset above (existing A–F implementations).
4. **First valid confirmation** across allowed confirm TFs wins; sweep is
   consumed (one-shot).
5. Entry candidate → **existing** risk / order path (demo-capable).
6. Default live product mode = this policy engine when implemented.
   `DUMB_MTF_H4` / baseline DUMB = park / compare only — not the expert promise.
7. Expert validation (charts + trade identity) precedes optimization research.

## Build order
1. **P1 — H4 tier only** (detect H4, confirm M5+M15, triggers A/D/F).
2. Expert review pack on H4 stream.
3. Then H1 tier → D1 tier → M15 tier (same pattern).

## Explicit non-goals (this policy)
- H2 tier, Mode B scalping, expectancy optimization, replacing expert discretion.
- Changing locked risk constants without a dated ruling.

## Deferred ops (recorded, not this sprint)
- **Chart structure markers not visible** while running DUMB-MTF / TF switches
  (H4, H1, M30): probe later (publisher path, EA draw `.ex5`, file sandbox,
  symbol/age guards) **after** product P1 spine is in place.