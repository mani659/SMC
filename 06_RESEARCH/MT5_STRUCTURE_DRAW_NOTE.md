# MT5 STRUCTURE DRAW — TESTER NOTE (design lock 2026-10-22)

**Banner: VISUALIZATION ONLY — NOT A STRATEGY CHANGE.**

**MERGED 2026-10-22 — one EA, one compile, one attach:** the structure-draw
duty now lives INSIDE `SMC_Safety_Watchdog.mq5` (timer order: heartbeat
safety → markers → structure draw). The standalone `SMC_Structure_Draw.mq5`
is **DEPRECATED** — do not compile or attach it; it is kept only as the
reference source of the draw routine.

The owner (and any tester) can now SEE on ONE EA attach what the bot treats
as structure: POI zones, their sweeps, the armed state, and (when all three
levels exist) the planned entry / stop / target — while the same EA keeps
the heartbeat emergency protection unchanged.

Architecture, as locked: **Python OWNS levels — MQL5 ONLY draws.** No trading
logic, no thresholds, no entry decisions live in MQL5 beyond the EXISTING
watchdog emergency close/cancel (heartbeat-stale only). The draw duty cannot
place, modify, or close anything — zero trade calls in that code path.

---

## 1. Components

| Piece | Path | Role |
|---|---|---|
| Publisher | `04_SRC/smc/live/structure_publish.py` | Rewrites the full snapshot to `smc_structure_draw.txt` (atomic, fail-safe, never fatal to the session) |
| Operator wire | `04_SRC/smc/live/run_operator.py` (`_maybe_refresh_structure` → `_publish_structure_draw`) | Publishes on EVERY structure refresh; a batch change (arming) forces both the console board AND the draw file |
| Config | `04_SRC/smc/live/operator_config.py` | `structure_draw_enabled` (default `true`), `structure_draw_path` (default `""` = the heartbeat's EA-readable dir) |
| Draw + safety EA | `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` (v1.20) | ONE EA: heartbeat emergency duty (unchanged) + marker duty + structure-draw duty (reads the file every 1 s; clears `SMC_SD_` objects when file missing/stale/foreign — never an emergency) |
| Standalone draw EA | `05_MQL5_SAFETY/SMC_Structure_Draw.mq5` | **DEPRECATED 2026-10-22** — do not compile or attach; reference source only |
| Tests | `04_SRC/tests/test_structure_draw.py` | 17 tests, no MT5 import |

Transport is the same recipe as the heartbeat: one text file under the
terminal's `MQL5/Files/` sandbox (`<terminal_data_path>/MQL5/Files/`
authoritatively, else `<terminal_dir>/MQL5/Files/` from `terminal_path`, else
the session log dir with a loud warning). Resolution mirrors
`smc.live.heartbeat_path`; explicit `structure_draw_path` in the operator
config wins only when the data-folder/install-dir derivations are unavailable.

## 2. Schema v1 (normative — implemented exactly)

```
SMC_STRUCTURE_DRAW v1
ts_utc=2026-10-22T12:00:00Z symbol=XAUUSDm
POI|id|tf|side|zlow|zhigh|state
SWEEP|poi_id|side|price|atr_mult
SEEK|poi_id|state|posture
PLAN|poi_id|entry|sl|tp
```

* `POI.state` is `ARMED` or `UNARMED`.
* Cap: at most **40** POI records — armed first, then W1→D1→H4→H1 (console
  section order), so charts stay readable.
* **Documented derivation (deviation disclosed):** the sweep LINK in the
  snapshot carries side + magnitude only — no price (honest empties, L1
  design). As in the accepted marker writer (`smc_markers.csv`), a SWEEP
  record's price is the linked POI's zone edge on the swept side; absent
  either half → no SWEEP record. Never invented.
* `SEEK` records are emitted for armed POIs only (state + posture, posture
  pipes flattened). Empty snapshot → header-only file: the EA sees zero
  records and clears its prefix objects.
* `PLAN` rows are omitted unless entry, sl AND tp all exist (`plan` comes
  from the console snapshot's routed-workflow candidates; ≤4 drawn).

## 3. EA inputs (all defaulted — no Python edits, no code edits)

Structure-draw inputs live inside the merged watchdog (all defaulted — the
watchdog's own safety inputs are untouched):

| Input | Default | Meaning |
|---|---|---|
| `InpEnableStructureDraw` | `true` | Draw duty on/off (off → nothing painted) |
| `InpStructureFile` | `smc_structure_draw.txt` | Terminal `Files` dir file |
| `InpStructureSymbol` | `""` (chart symbol) | File must match this symbol or objects clear |
| `InpDrawPrefix` | `SMC_SD_` | Object prefix; must differ from `SMC_` (else duty auto-disables, logged at init) |
| `InpMaxStructureAgeSec` | `120` | File older → draw objects ONLY deleted |
| `InpDrawPOI/Sweep/Seek/Plan` | `true` | Per-layer on/off |
| `InpColorBull/Bear` | LimeGreen / Tomato | Zone rectangle colors |
| `InpColorSweep` | Orange | Sweep level line (dotted) |
| `InpColorPlanEntry/SL/TP` | DeepSkyBlue / Red / Lime | Plan level lines |
| `InpZoneWindowHours` | `36` | One display rectangle span (now − 36 h → now + 2 h) |

Drawn objects: `<id>_Z` zone rectangle, `<id>_L` `"<tf> <ARMED|UNARMED>"`
text at the zone's top edge (SEEK state appended to the zone tooltip),
`<id>_S` dotted sweep level, `<id>_PE/_PS/_PT` plan levels, `BANNER` corner
label. Orphan reconcile deletes objects their record no longer carries.

Fail-safe behavior (locked): unknown/foreign file, missing file, symbol
mismatch, or stale timestamp → `ObjectsDeleteAll(0, InpDrawPrefix)` — the
chart says nothing rather than showing old state. **Zero trade calls in the
draw duty** (the watchdog's only `OrderSend`s remain the pre-existing
heartbeat-stale emergency close/cancel, which the draw duty can never
trigger). On deinit ALL structure prefix objects are cleared (removal,
recompile, or parameter change). Ownership guard: the marker wipe skips
`SMC_SD_*` objects (a stale marker file can no longer delete fresh zones).
Banner sits at y=40 (the marker label owns y=22).

## 4. Setup — ONE EA, one compile, one attach (3 steps)

1. **Compile:** in MetaEditor, compile `SMC_Safety_Watchdog.mq5` (the merged
   companion EA) → attach it to the demo XAUUSD chart. ONE EA only —
   `SMC_Structure_Draw.mq5` is deprecated; do not attach it.
2. **Run the operator:** `run_live.bat` / the Python operator must be running
   — IT writes both files (heartbeat every beat; the draw file on every
   structure refresh; a batch change forces it immediately, same event that
   fixed the armed-mismatch case).
3. **Path:** `terminal_path` in the operator config must point at this
   terminal (same one paste as the heartbeat; both files land in that
   terminal's data-folder `MQL5/Files/` automatically — no symlink, no copy).

Screenshot check: armed POIs appear as green/red rectangles with a small
gold `MD HW armed`-style label; sweeps are dotted orange lines; if the
console board shows a plan, entry (blue) / stop (red) / target (green)
dotted lines appear; silver banner top-left says VISUALIZATION ONLY.

Stopping the operator → the draw file goes stale after 120 s → the boxes
clear themselves (banner too, fail-safe). NOTE: the HEARTBEAT keeps its own
5 s stale budget — stopping the operator still triggers the emergency
protection via `smc_heartbeat.txt`; that behavior is unchanged by design.

## 4b. OWNER MANUAL CHECKLIST (run on the owner's terminal before shipping)

- [ ] Compile merged EA (`SMC_Safety_Watchdog.mq5`) → `.ex5` — zero errors/warnings
- [ ] Attach to XAU demo chart (ONE EA only)
- [ ] Start Python operator (matching `terminal_path`)
- [ ] Zones appear; armed labels update after HTF batch
- [ ] Stop Python / delete heartbeat → emergency protection still fires
- [ ] Stop structure publish only / stale draw file → boxes clear, NO emergency
- [ ] Remove EA → objects cleared

Tip for the "stop structure publish only" step: set
`structure_draw_enabled=false` in the operator config (the heartbeat keeps
being published, so no emergency) or delete/age `smc_structure_draw.txt`
while the heartbeat stays fresh.

## 5. Verification (2026-10-22)

* Publisher/EA contract pinned by `04_SRC/tests/test_structure_draw.py`
  (17 passed): schema shape, cap+order, sweep-edge derivation, plan
  omission, header-only clear payload, atomic publish (+tmp residue check),
  unwritable-target fail-safe (returns `False`, never raises), path
  policy order, ASCII-only output, no-MT5-import discipline.
* Full suite: **1296 passed** (`locked_constants.py` untouched).
* EA: merged companion v1.20 line-reviewed this session — hard-ban greps
  clean (trade calls only in the two pre-existing emergency duties; the
  structure duty contains zero `Emergency`/`Alert`/trade calls); owner's
  first chart attach (checklist §4b) is the compile/visual proof.

## 6. Out of scope (locked)

Mode A/Essence thresholds, entry decisions, risk sizing, and any feedback of
drawings into decisions. The draw file is a leaf: writing it can never alter
a trading path, and its failure is logged (`STRUCTURE DRAW ... FAILED` in
`events.log`) without aborting the session.
