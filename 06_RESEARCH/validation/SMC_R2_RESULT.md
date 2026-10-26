Milestone: SMC-R2
Status: COMPLETE

Canonical dataset: XAUUSD M1 | 2021-04-12 to 2026-04-10 | 1,768,123 bars
Timeframe: M1
Timezone: UTC (MT5 export)
Duplicates: 0

Swing extraction:
  N parameter: 5
  Swing highs: 104,114
  Swing lows: 104,507
  Total swings: 208,621
  Confirmation: N bars after swing bar
  Deterministic: YES

FVG extraction:
  Bullish FVGs: 239,445
  Bearish FVGs: 232,030
  Total FVGs: 471,475
  Definition: candle[i+2].low > candle[i].high (bullish)
  Confirmation: candle[i+2] close
  Deterministic: YES

OB extraction:
  Bullish OBs: 239,445
  Bearish OBs: 232,030
  Total OBs: 471,475
  Definition: candle preceding FVG, color irrelevant
  Zone: [OB.low, OB.high]
  Deterministic: YES

BOS extraction:
  Bullish BOS: 100,507
  Bearish BOS: 96,458
  Total BOS: 196,965
  Definition: close beyond confirmed swing
  Confirmation: closing price
  Deterministic: YES

CHOCH extraction: DEFERRED to SMC-R3
Leading diagonal: DEFERRED — needs further formalization
Ending diagonal: DEFERRED — needs further formalization

Freshness state machine: DEFINED in R1, not yet applied to events
First-touch definition: DEFINED in R1, not yet applied to events

Event identity: First valid trigger per POI counts; subsequent triggers ignored
Event independence: Multiple FVGs per swing are distinct events; overlapping OBs tracked independently

M1/M5 boundary: Not yet tested (requires POI + LTF trigger infrastructure)

Lookahead audit: PASS — 0 issues
Leakage audit: PASS — no future information used
Timestamp audit: PASS — no duplicates, sorted, UTC
Reproducibility: PASS — identical results on re-run

Structural redundancy:
  Models 2/3/6 overlap (broken-level retests)
  Models BOS/CHOCH complementary (continuation vs reversal)
  Two-Bar/RSI can co-occur at same POI

Event-count summary:
  Raw bars: 1,768,123
  Swings: 208,621
  FVGs: 471,475
  OBs: 471,475
  BOS: 196,965
  Lookahead issues: 0

Critical ambiguities: None for Priority 1 and Priority 3 models

Highest-priority SMC-R3 candidates:
  1. BOS + OB Continuation — ready for extraction and testing
  2. Two-Bar Reversal — ready for extraction and testing
  3. RSI Divergence — ready for extraction and testing

Decision: EXTRACTION VALID — READY FOR SMC-R3

Next authorized milestone: SMC-R3 — Standalone Event Experiments
Authorization: PLANNED — NOT STARTED (requires control session review)

External API calls: 0
New data acquired: 0
Spend: $0.00

Repository files created:
  SMC_RESEARCH/scripts/smc_r2_event_extraction.py (NEW)
  SMC_RESEARCH/validation/SMC_R2_EVENT_EXTRACTION_VALIDATION.md (NEW)
  SMC_RESEARCH/validation/SMC_R2_RESULT.md (NEW)
  SMC_RESEARCH/validation/SMC_R2_extraction_summary.json (NEW)
  SMC_RESEARCH/validation/SMC_R2_swings.csv (NEW)
  SMC_RESEARCH/validation/SMC_R2_fvgs.csv (NEW)
  SMC_RESEARCH/validation/SMC_R2_obs.csv (NEW)
  SMC_RESEARCH/validation/SMC_R2_bos.csv (NEW)
