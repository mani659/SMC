# MQL5 VISUAL ENTRY TWIN (OPTION A) & WATCHDOG ALERT QUIET NOTE

**Document Type:** Architectural Release & Operational Guidance  
**Authority:** Lead Architect  
**Date:** 2026-10-31  
**Status:** IMPLEMENTED & VERIFIED  
**UPDATE 2026-10-31 (unified EA):** the visual twin is now duty #(4) inside `SMC_Safety_Watchdog.mq5` v1.22 — **ONE EA** (`InpEnableVisualTwin`, default `false`, opt-in). The standalone `SMC_Visual_Entry_Twin.mq5` is **DEPRECATED** (kept for history, header-marked, do not use for new attaches). See §4 for the updated attach paths.

---

## 0. Unified EA (2026-10-31 merge) — quick reference

| Item | Value |
|---|---|
| Single file | `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` (v1.22; keep filename — existing attach instructions stay valid) |
| Frozen timer order | (1) heartbeat/Emergency safety → (2) `SMC_` markers → (3) `SMC_SD_` structure draw → (4) visual twin `VIS_IND_` (OPTIONAL) |
| Opt-in input | `InpEnableVisualTwin = false` (DEFAULT OFF — set `true` only on comparison/review charts) |
| Alerts | `InpEnableTerminalAlerts = false` (DEFAULT QUIET — unchanged) |
| Twin inputs | swing length, entries/labels/structure/OB/FVG toggles, colors, history bars, watermark — all under input group `=== 4. Visual twin duty ===` |
| Hard bans (visual duty) | NO `OrderSend`/trade calls from the visual path; visual failure = `Print` + skip **only** (never `Emergency()`/`Alert()`); `CleanChart` deletes `VIS_IND_*` ONLY (it can never delete `SMC_` markers or `SMC_SD_` structure objects); init-fail is fail-soft (EA still loads, safety unaffected) |
| Entry merge | Indicator-to-bot entry merge still **NOT_APPROVED** — display-only forever |
| Namespaces | heartbeat/log files `smc_heartbeat.txt` / `smc_watchdog.log` · markers `SMC_` · structure `SMC_SD_` · visual `VIS_IND_` (init rejects colliding prefixes) |

---

## 1. Executive Summary

The unified Expert Advisor fulfills three governed objectives:
1. **Safety Watchdog (always on):** fail-closed heartbeat protection — scoped position close + pending order cancel when `smc_heartbeat.txt` goes stale. Unchanged semantics, always timer-duty #(1).
2. **Official overlays (marker + structure draw):** Python state markers and `SMC_SD_` structure boxes, timer-duties #(2)/(3). Unchanged.
3. **Optional Visual Twin (duty #(4), DEFAULT OFF):** the deprecated standalone twin's indicator-style display — OB-touch BUY/SELL arrows, BOS/CHoCH lines/labels, OB/FVG boxes — under `VIS_IND_`, enabled per-chart via `InpEnableVisualTwin=true`. `Alert(...)` popups remain quarantined behind `InpEnableTerminalAlerts=false` (v1.21 quiet-logging ruling preserved 100%).

---

## 2. Part 1: Visual Entry Twin Details

### 2.1 Governance & Hard Bans
- **NO Order Execution:** Zero `OrderSend`, `OrderModify`, `OrderClose`, or trade transaction calls.
- **NO Strategy Coupling:** Completely uncoupled from Python's 5-pillar validation, Trigger Router (Triggers A/D/F), `RiskEngine`, and `order_manager`.
- **NO Shared Flags:** No shared "approve entry", state, or IPC bridge with the bot.
- **Distinct Namespace:** All objects are prefixed with `InpObjectPrefix` (default `VIS_IND_`), strictly forbidding `BOT_`, `PLAN_`, `ARMED_`, or `SMC_`.
- **Strategy Status:** Indicator-to-bot entry merge remains **NOT_APPROVED**.

### 2.2 What is Drawn on Chart

| Visual Element | Object Name Prefix | Type | Color (Default) | Description & Trigger Semantics |
|:---|:---|:---|:---|:---|
| **Visual BUY Arrow** | `VIS_IND_BUY_<time>` | `OBJ_ARROW` (Wingdings 233) | `clrLime` | Placed at `low - 0.3 * ATR` when candle enters active Bull OB and closes bullish ($body > 0.1 \times ATR$). |
| **Visual BUY Text** | `VIS_IND_BUY_TXT_<time>` | `OBJ_TEXT` | `clrLime` | Small "VIS BUY" label below arrow for immediate chart readability. |
| **Visual SELL Arrow** | `VIS_IND_SELL_<time>` | `OBJ_ARROW` (Wingdings 234) | `clrRed` | Placed at `high + 0.3 * ATR` when candle enters active Bear OB and closes bearish ($body > 0.1 \times ATR$). |
| **Visual SELL Text** | `VIS_IND_SELL_TXT_<time>` | `OBJ_TEXT` | `clrRed` | Small "VIS SELL" label above arrow. |
| **Bullish Order Block** | `VIS_IND_OB_B_<time>` | `OBJ_RECTANGLE` | `clrCornflowerBlue` | Zone formed by the last opposing candle prior to a bullish BOS/CHoCH. Extends forward `InpOBExtendBars` bars. |
| **Bearish Order Block** | `VIS_IND_OB_S_<time>` | `OBJ_RECTANGLE` | `clrLightCoral` | Zone formed by the last opposing candle prior to a bearish BOS/CHoCH. Extends forward `InpOBExtendBars` bars. |
| **Mitigated OB** | `VIS_IND_OB_*` | `OBJ_RECTANGLE` | `clrSilver` | Automatically turns silver when price closes beyond the opposing boundary. |
| **Structure Lines** | `VIS_IND_STR_L_*` | `OBJ_TREND` | Bull: `clrDodgerBlue`<br>Bear: `clrOrangeRed` | Dashed horizontal lines indicating confirmed BOS or CHoCH pivot breaks. |
| **Structure Labels** | `VIS_IND_STR_T_*` | `OBJ_TEXT` | Matching structure color | Text tags: "BOS" (trend continuation) or "CHoCH" (structural character shift). |
| **Fair Value Gaps** | `VIS_IND_FVG_*` | `OBJ_RECTANGLE` | Bull: `clrMediumSeaGreen`<br>Bear: `clrSalmon` | 3-bar imbalance boxes; recolors to silver upon mitigation. |
| **Watermark Banner** | `VIS_IND_BANNER` | `OBJ_LABEL` | `clrKhaki` | Upper-left chart banner: `"SMC VISUAL TWIN [DISPLAY ONLY — NO ORDERS]"`. |

### 2.3 What is NOT Linked to Python
1. **Independent Calculations:** The Visual Twin derives swings and OBs directly from MT5 bar data (`CopyRates`), completely independent of Python's multi-timeframe engine.
2. **No Awareness of Bot Orders:** It does not read `smc_markers.csv`, `smc_structure_draw.txt`, or `smc_heartbeat.txt`.
3. **No Execution Authority:** The arrows are painted purely for human visual inspection to observe how raw indicator entries compare to Python's institutional Trigger A/D/F entries.

---

## 3. Part 2: Watchdog Alert UX Quiet Details

### 3.1 Problem Addressed
When the Python runtime was stopped or undergoing maintenance, MT5 operators experienced repetitive, disruptive modal/popup alerts (`Alert(...)`) every 5 minutes. The operator required all alert popups silenced in favor of quiet logging.

### 3.2 Implemented Changes in `SMC_Safety_Watchdog.mq5` (v1.21)
1. **New Inputs Added:**
   ```mql5
   input bool   InpEnableTerminalAlerts = false;            // Terminal popup Alert() (default FALSE: quiet logging only)
   input bool   InpLogToFile            = true;             // Write watchdog events to MQL5/Files/
   input string InpWatchdogLogFile      = "smc_watchdog.log";// Watchdog log file (terminal Files dir)
   ```
2. **Emergency Path Modification:**
   - Popups disabled by default: `Alert(...)` only executes if `InpEnableTerminalAlerts == true`.
   - All emergency activations and heartbeat recoveries are logged via `PrintFormat` to the MT5 Experts log.
   - All events are optionally appended to `MQL5/Files/smc_watchdog.log` with UTC timestamps.
3. **Safety Logic Preserved:**
   - Fail-closed position closure (`CloseAllPositions()`) and pending order cancellation (`DeleteAllPendings()`) remain **100% active and unmodified**.
   - Scope filters (`InpMagicFilter`, `InpSymbolFilter`) remain enforced.
   - Heartbeat contract (`smc_heartbeat.txt` under `MQL5/Files/`) remains fully synchronized with Python's heartbeat publisher.

---

## 4. Operational Setup: How to Attach (UPDATED 2026-10-31 — unified EA)

> MT5 allows only **one Expert Advisor per chart window**. With the unified EA, the dual-EA juggling from 2026-10-31 morning is gone: attach `SMC_Safety_Watchdog.ex5` everywhere, and opt the visual twin in per-chart with `InpEnableVisualTwin=true`.

### Setup A — Single-EA comparison chart (RECOMMENDED, replaces dual-file setup)
- **Chart (`XAUUSD, M5` — Live System Chart):**
  - Attach `SMC_Safety_Watchdog.ex5`.
  - Settings: `InpEnableTerminalAlerts=false` (default quiet), `InpEnableStructureDraw=true`, **`InpEnableVisualTwin=true`** (comparison charts only; tuning inputs live under the visual twin input group).
  - Purpose: fail-closed safety + official Python overlays (`SMC_` markers, `SMC_SD_` zones/sweeps/plan lines) + indicator-style twin arrows (`VIS_IND_*`) on ONE chart. The frozen timer order guarantees safety always runs first; twin failure can never reach the safety path.
- **For long-running live sessions,** leave `InpEnableVisualTwin=false` (default) so the chart carries safety + official overlays only.

### Setup B — Standalone indicator review chart
- Attach `SMC_Safety_Watchdog.ex5` to any chart (M1, M5, M15, H1) with `InpEnableVisualTwin=true`.
- Can run with Python completely stopped: no heartbeat alive ⇒ the watchdog will treat the heartbeat as stale — that is the DESIGNED fail-closed behavior. If you do not want scoped close/delete running in that review context, the pre-existing scope inputs (`InpClosePositions`, `InpDeletePendings`, magic/symbol filters) apply exactly as before; the twin itself never reads the heartbeat and never triggers it.
- Prefer `M5`/`M1` charts for M5-native draw inputs; no window overlapping is needed since single-EA attach makes side-by-side trivial.

### Setup C — DEPRECATED dual-file path (history only)
- `SMC_Visual_Entry_Twin.mq5` / `.ex5` remains in `05_MQL5_SAFETY/` **for history only** (deprecated 2026-10-31, header-marked; do not delete without an Architect ruling). Do not attach it for new comparisons — the merged twin inside the watchdog is byte-equivalent logic with the frozen-duty ordering intact.

---

## 5. Build & Compilation Verification (UPDATED)

`05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` compiled with the local 64-bit MetaEditor compiler:
```text
C:\Program Files\MetaTrader 5 EXNESS\MetaEditor64.exe
```
- **2026-10-31 unified v1.22:** `SMC_Safety_Watchdog.mq5` → `SMC_Safety_Watchdog.ex5` — **0 errors, 0 warnings** (compile.log, 2,050 ms). Binary deployed to
  `AppData\Roaming\MetaQuotes\Terminal\6FE846653CB9AC4D5ACECF98EF447F40\MQL5\Experts\`.
- Historical: v1.21 watchdog + standalone twin v1.00 both compiled 0/0 (2026-10-31 morning); the standalone twin is now source-deprecated and is not part of the shipping path.
