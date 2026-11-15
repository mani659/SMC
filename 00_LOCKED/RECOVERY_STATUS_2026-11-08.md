# RECOVERY STATUS — 2026-11-08 FILE CORRUPTION EVENT

**Status:** FINAL for this event — nothing below will be reconstructed without a fresh,
separately pre-registered engagement.
**Authority:** owner reconciliation request 2026-11-15 ("commit the live work, delete what is
dead, mark what is unreconstructed").
**Purpose:** one tracked home for the truth about what was lost, so no reader has to
reconstruct it from scattered banners.

---

## 1. Lost and marked as lost (6 files)

All six fail loud rather than silently re-running a harness or a suite. None sits on the
shipped product path (`PRODUCT_V1`), which they never imported.

| # | File | Type of marker | Present state |
|---|---|---|---|
| 1 | `04_SRC/smc/orchestration/coupled_mtf.py` | module-level recovery notice, `ScriptLost` on use | stub |
| 2 | `04_SRC/tests/test_coupled_mtf.py` | skipped with corruption reason | 1 skipped |
| 3 | `04_SRC/tests/test_policy_mtf_h4.py` | skipped; surviving assertions target the retired `DUMB_MTF_H4` mode id | 1 skipped |
| 4 | `06_RESEARCH/scripts/confirm_vs_zone_opt1_smoke.py` | raises `ScriptLost` on import | stub |
| 5 | `06_RESEARCH/scripts/confirm_vs_zone_opt4_smoke.py` | raises `ScriptLost` on import | stub |
| 6 | `06_RESEARCH/scripts/coupled_mtf_full_menu_diagnostic.py` | raises `ScriptLost` on import | stub |

Surviving fragments (outside git, preserved verbatim):
`ARCHIVE/RECOVERY_FRAGMENTS_2026-11-08/`.

## 2. Partial survivors (documented gaps, not lost)

- `04_SRC/tests/test_blocked_reason_surface.py` — board half of the surface.
- `06_RESEARCH/scripts/poi_timing_early_late_study.py` — frozen timing label intact, harness incomplete.
- `06_RESEARCH/PHASE0_EVENT_SCORE_SHEET.md` — verdict rows absent (checkpoint record only).
- `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` — ~118 post-checkpoint lines not reconstructed.

## 3. Unchanged by this reconciliation

No strategy, gate, threshold, composition or locked constant was touched. The only file moves
were archival: the deprecated `SMC_Visual_Entry_Twin.mq5` moved out of the shipping folder
(`05_MQL5_SAFETY/`) into `ARCHIVE/MQL5_HISTORY/`, because `AUTO_BUILD_RELEASE.py` copies every
`.mq5`/`.ex5` in `05_MQL5_SAFETY/` into the tester pack and that EA is deprecated ("keep for
history, do not ship").
