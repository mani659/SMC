# Hypothesis-Outcome Analytics Report

**Window:** exec 2025-06-01 -> 2025-11-30 (load 2025-05-01); M5 series bars=35713
**Runs included:** 6m_post_tp_run1, 6m_post_tp_run2
**n trades:** 6

**STATUS: RESEARCH / LOGGING ANALYTICS ONLY.** No strategy logic change, no
stop/TP/threshold change, no expectancy claim. Taxonomy labels are NOT
promoted into live filters. Small-n diagnostic.

---

## 1. Taxonomy (locked)

- **REJECTED**: weak/no favorable path; never seriously approached TP.
- **SL_THEN_TP_PATH**: stop (or stop-side close) first; TP level later traded.
- **TP_REACHED**: take_profit (structural or fallback) under live rules.
- **MFE_ONLY**: meaningful MFE but never TP; not clean SL_THEN_TP.
- **DATA_GAP**: missing bars / no usable TP level / incomplete series.

## 2. Definition notes (normative)

- **tp_level**: order TP (structural if carried else atr_fallback); None -> DATA_GAP
- **tp_touched_after_entry**: LONG high>=tp or SHORT low<=tp at/after entry bar on M5 exec series
- **sl_then_tp_path**: close_kind stop_loss AND tp touched on a bar with index STRICTLY > exit_bar
- **be_scratch_default**: close_kind stop_loss with |pnl|<0.15 defaults to MFE_ONLY unless TP touched strictly after exit
- **rejected**: MFE/|original_sl| < 0.25 (analytics only) OR never approached TP and exit loss-like
- **mfe_only**: meaningful MFE but no TP reach and not SL_THEN_TP_PATH
- **tp_reached**: close_kind take_profit under live rules
- **data_gap**: entry/time unresolvable or no usable TP level

Analytics divider for MFE/|original_sl|: 0.25 (analytics only,
NOT a trading threshold in locked_constants).

---

## 3. Outcome counts

```
{
  "SL_THEN_TP_PATH": 4,
  "TP_REACHED": 2
}
```

## 4. Cross-tab by trigger

```
{
  "F": {
    "SL_THEN_TP_PATH": 4
  },
  "C": {
    "TP_REACHED": 2
  }
}
```

## 5. Cross-tab by tp_source

```
{
  "atr_fallback": {
    "SL_THEN_TP_PATH": 4
  },
  "structural_swing": {
    "TP_REACHED": 2
  }
}
```

## 6. Cross-tab by close_kind

```
{
  "stop_loss": {
    "SL_THEN_TP_PATH": 4
  },
  "take_profit": {
    "TP_REACHED": 2
  }
}
```

---

## 7. Per-trade detail

```
6m_post_tp_run1 | 1 | short | poi-014146 | F | tp_source=atr_fallback | close=stop_loss | pnl=-2.910466549603325 | mfe=3.4700000000002547 | mae=33.202999999999975 | MFE/|orig_sl|=0.0010482108524644713 | tp_touched_after_entry=True | outcome=SL_THEN_TP_PATH | stop exit; TP touched on bar strictly after exit
6m_post_tp_run1 | 2 | short | poi-047805 | C | tp_source=structural_swing | close=take_profit | pnl=0.3851999999999862 | mfe=4.713999999999942 | mae=5.9099999999998545 | MFE/|orig_sl|= | tp_touched_after_entry=True | outcome=TP_REACHED | live take_profit exit
6m_post_tp_run1 | 3 | long | poi-073511 | F | tp_source=atr_fallback | close=stop_loss | pnl=0.0715385166170563 | mfe=20.390000000000327 | mae=24.519999999999527 | MFE/|orig_sl|=0.004881453510990001 | tp_touched_after_entry=True | outcome=SL_THEN_TP_PATH | stop exit; TP touched on bar strictly after exit
6m_post_tp_run2 | 1 | short | poi-014146 | F | tp_source=atr_fallback | close=stop_loss | pnl=-2.910466549603325 | mfe=3.4700000000002547 | mae=33.202999999999975 | MFE/|orig_sl|=0.0010482108524644713 | tp_touched_after_entry=True | outcome=SL_THEN_TP_PATH | stop exit; TP touched on bar strictly after exit
6m_post_tp_run2 | 2 | short | poi-047805 | C | tp_source=structural_swing | close=take_profit | pnl=0.3851999999999862 | mfe=4.713999999999942 | mae=5.9099999999998545 | MFE/|orig_sl|= | tp_touched_after_entry=True | outcome=TP_REACHED | live take_profit exit
6m_post_tp_run2 | 3 | long | poi-073511 | F | tp_source=atr_fallback | close=stop_loss | pnl=0.0715385166170563 | mfe=20.390000000000327 | mae=24.519999999999527 | MFE/|orig_sl|=0.004881453510990001 | tp_touched_after_entry=True | outcome=SL_THEN_TP_PATH | stop exit; TP touched on bar strictly after exit

```

---

## 8. Narrative — what this implies for 'confirmations enough?' on THIS sample

On the 6m post-TP sample (n=6):
- **TP_REACHED: 2** — the live exit rule actually delivered the
  identified favorable level; the entry hypothesis (as captured by the
  carried TP level) was realized.
- **SL_THEN_TP_PATH: 4** — the stop hit first, but the price later
  revisited the SAME TP level. On these, the hypothesis that the move had a
  reachable favorable target is supported by evidence AFTER entry, but
  execution/mgmt timing (or live false-break/re-engage rules) made the closed
  trade a stop. This is the clearest 'confirmations enough but timing/management
  cost' class on this sample.
- **MFE_ONLY: 0** — meaningful favorable excursion but no TP reach and
  not a clean SL_THEN_TP. Ambiguous: thesis not cleanly rejected, but not
  confirmed to the planned target either.
- **REJECTED: 0** — weak/no favorable path by the defined divider
  (MFE/|original_sl| < 0.25) or never
  approached TP and exited loss-like. 'Hypothesis not supported' cases.
- **DATA_GAP: 0** — could not be classified from available data.

**Read carefully:** n is tiny and these buckets are descriptive, not causal.
'SL_THEN_TP_PATH' does NOT imply 'widen the stop and wait' — it means the same
TP level was later touched, which is compatible with many
non-mutually-exclusive explanations (entry timing, management, false-break recon,
regime). 'MFE_ONLY' is the residual ambiguous class.

**On 'confirmations enough?':** this sample can speak only to whether trades that
were stopped still had a later-confirmable TP level (the SL_THEN_TP_PATH class).
On THIS sample, that class is 4 and the overall book is dominated by
stops / BE-scratch with at most one live TP-Reached. That is consistent with
'not enough favorable confirmations surviving to TP on this small frozen window',
but it is NOT a general verdict and NOT authorization for any
threshold/stop/TP change.

---

## 9. Bans honored

- No edits under 04_SRC/smc/ strategy decision paths.
- Logging-only script under 06_RESEARCH/scripts/.
- locked_constants.py diff empty.
- No stop widening, no TP retune, no expectancy claims.
- Taxonomy labels NOT promoted into live filters.

---

*Generated by `06_RESEARCH/scripts/hypothesis_outcome_study.py` —
research/logging analytics only.*
