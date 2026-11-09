# EA Structure Draw Visual Upgrade — Design

## Status

Approved design for implementation planning. This is an EA chart-rendering
change only. Python remains the sole structure authority; the EA does not
detect or infer market structure.

## Purpose and authority

Upgrade the structure-draw duty inside
`05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` from hollow POI outlines to filled,
direction-colored zones with short labels. Adapt only the native
`OBJ_RECTANGLE` fill/color/tooltip and `OBJ_TEXT` presentation patterns from
`SmartMoneyConcepts.mq5`. Do not port its detection, swings, BOS/CHoCH, EQH/EQL,
or signal logic. The standalone indicator is not required.

The existing Python structure file remains the only source of POI identity,
direction, timeframe, state, and price bounds. Do not change Python,
`locked_constants`, thresholds, or strategy behavior.

## Input schema and display choices

Continue reading `smc_structure_draw.txt` from the terminal `MQL5/Files`
sandbox and parsing `SMC_STRUCTURE_DRAW v1` records. The current POI row is:

`POI|id|tf|side|zlow|zhigh|state`

It provides price bounds, timeframe, side, and state, but no POI origin time,
separate zone kind (such as FVG), or ephemeral flag. Do not infer those fields.
In particular, the header's `ts_utc` is the snapshot publication time, not a
zone-formation time.

Draw the first `InpMaxZones` valid POI rows in file order (default 10), without
EA-side re-ranking. The publisher already orders its POIs by priority. Any
rows beyond the cap are omitted; creation time is unavailable, so there is no
age-based eviction.

## Rendering

For each retained POI:

- Draw one native `OBJ_RECTANGLE` with top and bottom copied exactly from the
  file's high and low fields.
- Set `OBJPROP_FILL=true` and `OBJPROP_BACK=true`; use muted configurable bull
  and bear colors (Dilber-like defaults are acceptable), with a thin border.
  Native fill plus background placement is the intended translucent-style
  appearance. Do not add a canvas, bitmap, or alpha-blit renderer.
- Draw a short `OBJ_TEXT` label such as `DEMAND H4 ARMED` or `SUPPLY H1`.
  Include timeframe, side, and state from the row; include the exact file price
  bounds in the tooltip.
- Use a dedicated `InpDrawPrefix` namespace for all rectangle, label, status,
  sweep, and plan objects.

The time coordinates are display-only. Use the current chart bar time as the
right edge and set the left edge to:

`right_edge - InpZoneExtendBars * PeriodSeconds(chart timeframe)`

`InpZoneExtendBars` defaults to 16. Do not use `ts_utc` as the left edge,
derive origin time from chart structure, or change file prices. A forward pad
is not used.

Sweep and plan rows retain their existing optional line rendering and colors;
they remain data-fed, not chart-derived. SEEK state may be shown in the POI
label/tooltip only when present in the file.

## Refresh, empty, and stale behavior

Continue validating schema, symbol, and `InpMaxStructureAgeSec` on every
timer pass. Missing, malformed, foreign, symbol-mismatched, or stale files
clear only objects under `InpDrawPrefix`; they never affect heartbeat or
emergency decisions.

When render data changes, the symbol/timeframe changes, or the latest chart
bar changes, perform a complete prefix-scoped redraw: delete owned objects,
recreate the current zones and enabled auxiliary lines, then redraw the
visualization banner. The render-change key must exclude the header timestamp:
it is freshness metadata, not geometry. This avoids needless redraws when
only publication time changes while preserving stale-age checks.

When a valid snapshot has no active POIs (including a header-only file), clear
zone objects and show one prefix-owned `SMC bot: no active POI` status label.
Missing or stale files remain an honest empty chart, without a status claim
that a valid snapshot was received.

## Safety and scope boundaries

Keep `OnTimer` ordering and heartbeat/emergency functions unchanged. The draw
duty remains display-only: no `Alert`, emergency, order, position, or trade
calls. Keep the existing symbol guard, prefix ownership, and deinitialization
cleanup. The EA must not require `SmartMoneyConcepts.mq5` to be attached.

## Documentation and verification

The implementation must update:

- `06_RESEARCH/EA_STRUCTURE_DRAW_VISUAL_UPGRADE_NOTE.md`, including schema
  gaps, default 16-bar display extent, prefix and status behavior, the
  no-Dilber-attachment requirement, and the owner `.ex5` checklist.
- `00_LOCKED/CHANGELOG.md` and `00_LOCKED/SESSION_HANDOFF.md` with short
  entries stating `LOGIC_CHANGED: MQL draw only`, `PYTHON_CHANGED: NO`, and
  `DILBER_DETECTION_PORTED: NO`.

Verify with a valid header-only snapshot, a synthetic snapshot containing
2–3 mixed-direction/timeframe POIs (including an armed row), a stale snapshot,
and a prefix-isolation check. Confirm draw code makes no calls into heartbeat
or emergency behavior. The owner compiles the `.mq5` to `.ex5` and performs
the live/demo chart retest; no standalone Dilber indicator is attached.
