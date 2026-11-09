# EA Structure Draw Visual Upgrade

**Authority:** Lead Architect, 2026-10-25  
**Status:** MQL draw change implemented; owner MetaEditor build and chart retest pending.  
**Scope:** Visualization only — not a strategy or signal change.

## Contract

- Data authority remains the Python-published `smc_structure_draw.txt` in the
  terminal `MQL5/Files` sandbox. The EA does not calculate POIs, FVGs, swings,
  BOS/CHoCH, EQH/EQL, or trade signals from chart bars.
- `SMC_STRUCTURE_DRAW v1`, symbol validation, and
  `InpMaxStructureAgeSec` remain in force. Missing, malformed, foreign,
  mismatched, or stale structure data clears only `InpDrawPrefix` objects.
- The heartbeat/emergency path, its file, and timer ordering are unchanged.
  Structure draw failures never trigger emergency protection.
- `SmartMoneyConcepts.mq5` is a visual-style reference only. Do not attach the
  standalone indicator; the merged `SMC_Safety_Watchdog` EA works from the
  Python structure file alone.

## POI rendering

Each valid retained `POI|id|tf|side|zlow|zhigh|state` row creates one native
`OBJ_RECTANGLE` and one `OBJ_TEXT` label under `SMC_SD_` (or the configured
`InpDrawPrefix`). The rectangle uses the row's exact low/high values, is filled
and drawn behind candles, with configurable muted bull/demand and bear/supply
colors. Translucency is approximate via filled back-rectangles and muted
colors; true per-pixel alpha, canvas, and bitmap rendering are out of scope.

Labels are concise, for example `DEMAND H4 ARMED` or `SUPPLY H1 UNARMED`.
Tooltips include the file prices and state. The current schema provides no
separate zone kind, so labels must not claim `FVG`; it also provides no
ephemeral flag.

**SEEK schema clarification:** the POI row's `state` field is `ARMED` or
`UNARMED`; SEEK is not a separate POI column. When emitted, SEEK is a separate
`SEEK|poi_id|state|posture` row. It enriches the linked POI tooltip only; it
does not create a separate chart object.

### Time extent and cap

The schema has no POI origin time. The header's `ts_utc` is only the snapshot
publication time and is never used as zone formation time or as the rectangle
left edge. Time extent is display-only:

> Time extent is display-only. Zone origin is not in the structure schema.
> Prices from the file are authoritative. Optional later enrich: Python
> publishes `origin_ts`/`start_ts` so the left edge can follow the file.

- Right edge: current chart bar time.
- Left edge: right edge minus `InpZoneExtendBars * PeriodSeconds(chart TF)`.
- `InpZoneExtendBars` default: **16**. No forward pad is applied.
- File prices remain authoritative; no chart-derived geometry is permitted.

The zone cap keeps the first `InpMaxZones` rows in publisher order (armed,
then W1→D1→H4→H1); no age-based eviction — creation time is not in the schema.
`InpMaxZones` defaults to **10**. Sweep and plan rows retain their existing
optional data-fed lines.

The renderer checks freshness each timer pass and performs a full prefix-only
clear/recreate when visual rows, chart period, or latest bar changes. The
header timestamp is excluded from the redraw key because it does not change
geometry. A valid snapshot with zero POI rows shows one status label:
`SMC bot: no active POI`. Missing/stale input clears the label as well.

## Owner verification

Use a controlled demo chart with the operator publishing to that terminal's
`MQL5/Files` directory. Do not use a live account for the heartbeat emergency
smoke.

1. **Header-only:** write a fresh, symbol-matching schema/header with no
   records. Confirm no `OBJ_RECTANGLE` exists and the status label appears.
2. **POI fixture:** add 2–3 valid POI rows with mixed BULL/BEAR directions,
   timeframes, and ARMED/UNARMED states. Use valid prices for the chart symbol.
   Confirm filled back-rectangles, short labels, and exact file price bounds.
   Add a linked SEEK row and confirm its state/posture appears only in the POI
   tooltip. Attach no standalone Dilber indicator.
3. **Stale and ownership:** keep heartbeat fresh, make the structure header
   older than `InpMaxStructureAgeSec`, and confirm all `InpDrawPrefix` objects
   clear without an emergency. Confirm an unrelated user object remains.
4. **Heartbeat smoke:** only on an empty, controlled demo account, stop the
   Python heartbeat publisher and confirm the existing watchdog emergency
   path still runs. Restore the publisher and confirm heartbeat recovery.

## Owner `.ex5` build checklist

1. Open `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` in MetaEditor for the target
   terminal.
2. Compile and confirm **0 errors / 0 warnings**.
3. Install the generated `.ex5` in that terminal's `MQL5/Experts`, refresh the
   Navigator, and attach only the merged watchdog EA.

## Change record

```text
DRAW_UPGRADE_STATUS: PASS
DILBER_DETECTION_PORTED: NO
OBJECT_TYPE: OBJ_RECTANGLE + labels
DATA_SOURCE: structure file only
PYTHON_CHANGED: NO
NOTE_PATH: 06_RESEARCH/EA_STRUCTURE_DRAW_VISUAL_UPGRADE_NOTE.md
OWNER_BUILD: compile .ex5 checklist (3 steps above)
NEXT_READY: owner chart retest with live/demo structure file
LOGIC_CHANGED: MQL draw only
```
