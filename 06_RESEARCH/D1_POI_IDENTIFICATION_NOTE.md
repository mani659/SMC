# Stage S1.D1 — Daily (D1) POI Identification Research Note

**Date:** 2026-10-04  
**Author:** SMC Local Agent  
**Status:** PASS — Pack Ready for Human Confirmation  
**Target:** `06_RESEARCH/results/structure_d1_poi_2025H2/`  

---

## 1. Scope & Execution Window
- **Exec Window:** 2025-06-01 00:00 UTC → 2025-11-30 23:59 UTC
- **Warm-up:** Loaded from 2025-03-01 00:00 UTC (resampled M1; exactly 235 D1 bars to prevent cold-start distortion)
- **Data Source:** `07_DATA/XAUUSD_M1.parquet` (SHA256: `e5d730eae5af8348ac38f46f31e9ee6e1a481cbeaaa57cda342b9e56fd17fee9`)
- **Detection Architecture:** Accepted product composition (`MultiTFProductRuntime` / `MultiTFDetectionDriver` with D1 in M8 HTF map)

---

## 2. Machine POI Census (Daily / D1)
- **Total Core POIs:** **114**
- **By Plain Tag:**
  - Order block (D1): **41**
  - Demand zone (D1): **33**
  - Supply zone (D1): **34**
  - Unlabeled POI (D1): **0**
  - Armed POI (D1): **6**
  - Merged POI (D1): **0** (D1 zones merge into H4/H1 batches; 0 D1-native merge episodes)
- **Separate Features:**
  - Fair value gap (D1): **43**
  - Liquidity level (D1): **501**
  - Liquidity sweep (D1): **362**
  - Displacement (D1): **104**

---

## 3. Artifact Manifest
All artifacts written to `06_RESEARCH/results/structure_d1_poi_2025H2/`:
1. `events_d1_poi.csv`: Exact schema table of all core D1 POIs
2. `d1_structure.csv`: Comprehensive D1 structural event ledger
3. `charts/`: 60 stratified verification PNG charts (all 6 armed + 18 OB + 18 Demand + 18 Supply)
4. `D1_POI_CONFIRMATION_REPORT.md` & `D1_POI_CONFIRMATION_REPORT.pdf`: Confirmation reports with index and scoring rubric
5. `summary.json`: Machine counts and build metadata

LOGIC_CHANGED: NO.
