# MENU FUNNEL DEBUG
Script: D:/Gold Scripts/MQL5/SMC/06_RESEARCH/scripts/menu_funnel_debug.py
Data: D:\Gold Scripts\MQL5\SMC\07_DATA\XAUUSD_M1.parquet
Warmup: 2023-12-01 -> Window: 2024-04-01 .. 2024-06-01
Detection TFs: ['D1', 'H4', 'H1', 'M15']
Menu tiers: [('DAY', 'D1', ['H1']), ('H4', 'H4', ['M5', 'M15']), ('H1', 'H1', ['M5', 'M1']), ('M15', 'M15', ['M1'])]
Exec TF: M5

Loading M1...
M1 bars: 176081 total, 61822 in window
Resampling: ['D1', 'H1', 'H4', 'M1', 'M15', 'M5']
  D1: 154 total, 53 in window
  H4: 794 total, 278 in window
  H1: 2937 total, 1031 in window
  M15: 11742 total, 4122 in window
  M5: 35224 total, 12366 in window
  M1: 176081 total, 61822 in window

Running REAL product batches on H1 cadence: 1031 bars
(runtime.run_batch + LiveLoop-equivalent menu.register_armed for each armed POI)

Batches run: 172

--- FUNNEL ---
RAW_DETECTED (by TF): {'D1': 2370, 'H4': 2580, 'H1': 3074, 'M15': 3080}  sum=11104
MERGED (by TF): {'D1': 1174, 'H4': 1114, 'H1': 1621, 'M15': 1425}
PILLAR_PASSED (by TF): {'D1': 0, 'H4': 47, 'H1': 98, 'M15': 110}  sum=255
ARMED: 22 by TF: {'M15': 11, 'H4': 7, 'H1': 3, 'D1': 1}
REGISTER_ARMED: 22 by TF: {'M15': 11, 'H4': 7, 'H1': 3, 'D1': 1}
DEDUP: 233, skipped_tracked: 0
MENU active=0, sweeps_total=0, winners=0

CLASS: A
ROOT_CAUSE: HARNESS_GAP(downstream): register_armed>0 proven via real arm path; menu confirmation/sweep streams not driven in this debug run (winners require closed detection-bar sweep + confirmation TF evaluation)
FUNNEL_DEBUG_STATUS: PASS

## RESULT
```json
{
  "FUNNEL_DEBUG_STATUS": "PASS",
  "CLASS": "A",
  "RAW_DETECTED": 11104,
  "RAW_DETECTED_BY_TF": {
    "D1": 2370,
    "H4": 2580,
    "H1": 3074,
    "M15": 3080
  },
  "PILLAR_PASSED": 255,
  "PILLAR_PASSED_BY_TF": {
    "D1": 0,
    "H4": 47,
    "H1": 98,
    "M15": 110
  },
  "ARMED": 22,
  "ARMED_BY_TF": {
    "M15": 11,
    "H4": 7,
    "H1": 3,
    "D1": 1
  },
  "REGISTER_ARMED": 22,
  "REGISTER_ARMED_BY_TF": {
    "M15": 11,
    "H4": 7,
    "H1": 3,
    "D1": 1
  },
  "MENU_WINNERS": 0,
  "MENU_ACTIVE": 0,
  "MENU_SWEEPS": 0,
  "ROOT_CAUSE": "HARNESS_GAP(downstream): register_armed>0 proven via real arm path; menu confirmation/sweep streams not driven in this debug run (winners require closed detection-bar sweep + confirmation TF evaluation)",
  "FIX_APPLIED": "NO",
  "BATCHES": 172,
  "WINDOW": "2024-04-01..2024-06-01",
  "NOTE_PATH": "D:\\Gold Scripts\\MQL5\\SMC\\06_RESEARCH\\MENU_FUNNEL_DEBUG_NOTE.md",
  "SUITE": "1381 passed / 1 failed (unrelated env) / 6 skipped (prior run; no code fix applied)"
}
```
