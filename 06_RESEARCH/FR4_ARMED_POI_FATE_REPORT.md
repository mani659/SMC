# FR-4 RESIDUAL CLOSEOUT — ARMED POI FATE LEDGER

**Date:** 2026-09-22 · **Authority:** Lead Architect ruling — FR-4 PASS, Foundation Fidelity Reset = COMPLETE_WITH_RESIDUALS; residuals closed by forensics only.
**Scope:** Every POI that reached ARMED in the FR-4 compliant October window (2025-10-01 00:00 → 2025-10-31 20:55 UTC, 6,324 M5 bars), plus the gate-ablation diag as counterfactual cross-reference.

> **Diagnostic only. No parameter changes.** No gate, displacement, pillar, TP/SL, or locked-constant value was touched. No strategy code changed — instrumentation is logging-only (runtime observation shims inside the script; production modules untouched). No edge claim is made or implied.

---

## 1. Method (forensics, zero strategy edits)

Read-only replay of the **identical frozen FR-4 config/window** with three **logging-only observation shims** (same module-attribute seam the FR-4 diag used; production code paths unchanged):

1. `engine.scan_route` wrapper — scan-call counter per POI (parity proof vs run1).
2. Trigger `evaluate` wrappers (A–F) — completed-signal counter per POI.
3. `trigger_f_bos_ob.entry_within_zone` pass-through recorder — FR-3 gate accept/reject events per POI (closes the "no gate-reject counter" residual).

**Parity + determinism proof (replay = compliant baseline):**
- `trades.csv` SHA-256 `ec885eef54e828be4a847c634c880db08370d56ecbd530bcdff1f16c43e47e63` — **byte-identical to run1**.
- `report.json` **byte-identical** to run1; summary identical ex-runtime.
- Funnel parity: **130 scan calls = 130**, **0 routes = 0**; books match run1 exactly.
- Funnel: 9,363 detected → 209 pillar-passed → **8 armed (4 M8)** → 130 scans → **0 routes → 0 trades**.

---

## 2. Armed-POI fate ledger (all 8)

| poi_id | TF | model tags | M8 | arm bar | arm time (UTC) | zone (low–high) | terminal state | fate class | fate bar | F signals | gate pass/rej |
|---|---|---|---|---:|---|---|---|---|---:|---:|---:|
| poi-000684 | H1 | M1 | no | 468 | 10-02 16:00 | 3878.835–3895.145 | tested | tested_after_arm | 711 | 0 | 0/0 |
| poi-000945 | H1 | M8 | **yes** | 648 | 10-03 08:00 | 3851.795–3874.615 | tested | tested_same_bar_as_arm | 648 | 0 | 0/0 |
| poi-002480 | H1 | M8 | **yes** | 1716 | 10-09 05:00 | 3961.555–3995.775 | tested | tested_after_arm | 1855 | 0 | **0/1 REJECT** |
| poi-002529 | H1 | M7+M8 | **yes** | 1752 | 10-09 08:00 | 4001.025–4049.385 | tested | tested_same_bar_as_arm | 1752 | 0 | 0/0 |
| poi-003164 | H4 | M7 | no | 2208 | 10-13 00:00 | 3717.348–3745.105 | fresh (end) | never_touched | — | 0 | 0/0 |
| poi-005293 | H1 | M8 | **yes** | 3612 | 10-20 02:00 | 4185.425–4247.355 | tested | tested_after_arm | 3652 | 0 | **0/1 REJECT** |
| poi-006270 | H4 | M1+M4 | no | 4284 | 10-22 12:00 | 4307.098–4381.298 | fresh (end) | never_touched | — | 0 | 0/0 |
| poi-007866 | H4 | M1+M7 | no | 5340 | 10-28 08:00 | 4099.965–4154.435 | fresh (end) | never_touched | — | 0 | 0/0 |

Every armed POI was scanned (§24 give-up retires each scan at arm+20; routability of TESTED POIs ends at touch+1). Totals: 130 scan calls, 0 completed F signals, **0 gate accepts / 2 gate rejects**, 0 candidates built then risk-rejected.

---

## 3. Classification counts (requested pivot)

| fate class | n | poi_ids |
|---|---:|---|
| same-bar TESTED (zone armed inside current price) | 2 | 000945, 002529 |
| tested after arm (touch, then terminal; no compliant signal) | 3 | 000684, 002480, 005293 |
| never touched in-window (FRESH at window end) | 3 | 003164, 006270, 007866 |
| expired §23 (time expiry) | **0** | — (structurally impossible: `expiry_bars_for` → None for H1+/HTF zones) |
| expired §24 give-up as terminal fate | 0 as fate* | *give-up fired on all 8 scans at arm+20 but never transitions state; for the 5 tested POIs touch preceded give-up |
| FR-3 zone/entry reject at trigger | **2 events** | 002480, 005293 (mechanism on tested_after_arm POIs) |
| no LTF trigger fired in window | 0 primary | all H1 POIs were F-evaluated; where F did not complete, no gate event occurred (failure upstream of gate — recorded observable, cause not attributed) |
| other | 0 | — |

| detection TF | armed | tested (any) | never touched | gate-rejected |
|---|---:|---:|---:|---:|
| H1 | 5 | 5 | 0 | 2 |
| H4 | 3 | 0 | 3 | 0 |

Pattern (fact): every H1 zone was revisited and tested in-window; **no H4 zone was ever revisited** (give-up retired their scans at arm+20; price never returned for the remaining 2,000–4,100 bars).

---

## 4. M8 subsection — why 4 M8-armed POIs produced 0 compliant routes/trades

All 4 M8 POIs (000945, 002480, 002529, 005293) are H1-detected; all 4 reached TESTED; **0 completed F signals**. Two mechanisms, both now attributed per-POI:

**(a) Same-bar terminality (2 POIs).** 000945 and 002529 armed with the zone already containing current price → first section-5 touch is the arm bar itself → immediately terminal. No routable window in which a compliant F signal could form (0 gate events — the gate was never reached).

**(b) FR-3 zone gate rejects the only two compliant-path evaluations (2 POIs).** For 002480 and 005293, F completed structural evaluation (BOS/OB found) and the entry gate **rejected 2/2**: entry price at the BOS/OB retest sat **above the zone high** — 4039.555 vs 3995.775 (**+43.78** outside) and 4263.855 vs 4247.355 (**+16.50** outside) respectively.

**Diag counterfactual cross-check (gate ablated, same frozen config):** the diag's exactly-2 trades originate from **exactly these two POIs**, at the **same structural bars** the compliant gate rejected:

| poi_id | compliant mode | diag (no gate) route → outcome |
|---|---|---|
| poi-002480 | F evaluates bar 1723/24 → **gate REJECT** (entry +43.78 above zone) | F@1723 → long 4039.555, M8, disp 1.315 ATR, **TP 4054.35 placed**, SL 4035.57 → stop_loss, −0.399 |
| poi-005293 | F evaluates bar 3615/16 → **gate REJECT** (entry +16.50 above zone) | F@3615 → long 4263.855, M8, disp 1.328 ATR, **TP 4294.79 placed**, SL 4256.25 → stop_loss, −0.761 |

This closes the residual with the full mechanism chain, per-POI: **M8 armed → touched → F structurally complete → FR-3 gate rejects entry geometry → 0 routes.** In the diag the gate's absence is the sole difference (2 routes → 2 TP-carrying placements → 2 SL closes; TP path live but not reached). Both zones were nonetheless *validated* later (touched at bars 1855 / 3652) — the tension is between F's structural entry location and the POI zone, not zone validity. Recorded as mechanism only; **no gate loosening, no F-timing work** (both hard-banned).

---

## 5. Built-then-rejected vs never-scanned (requested answer)

- **Never scanned: 0 POIs.** All 8 armed POIs had active scan windows (§24 give-up at arm+20; all 130 scan calls accounted for; funnel parity vs run1 exact).
- **Built then risk-rejected: 0.** No candidate ever reached the RiskEngine (0 routes upstream of risk) — rejections all happen earlier, at the FR-3 entry gate (2 events) or with no completed F signal at all (6 POIs).
- The compliant book is empty **by gate, not by silence**: the two evaluation attempts that occurred were both rejected by the frozen gate, and the diag proves the identical config minus the gate routes both.

---

## 6. Classification definitions and structural nuances

- `tested_same_bar_as_arm` — zone armed inside current price; terminal on the arm bar; no routable window.
- `tested_after_arm` — first section-5 touch at fate_bar (t+139 / t+40 / t+243 after arm); POI terminal from touch (one-touch rule); no compliant signal completed pre-terminality.
- `still_fresh_at_window_end_never_touched` — price never reached the zone for the whole remaining window; §24 give-up retired the *scan* at arm+20 without a state transition; §23 expiry structurally undefined for H1+ zones (`expiry_bars_for` → None); no order ever existed.
- Gate events are recorded only where F reached the entry check; 0/0 rows mean F never completed to the gate (upstream conditions or no routable bar) — the ledger records observables and does not attribute causes beyond them.

---

## 7. Artifacts

- Script: `06_RESEARCH/scripts/fr4_armed_poi_fate.py` (logging-only shims; byte-identity + funnel-parity gates; fails loudly on missing artifacts/empty lists)
- Ledger: `06_RESEARCH/results/fr4_fidelity/armed_poi_fate.csv` (8 rows; columns: poi_id, detection_tf, model_tags, is_m8, arm_bar, arm_time, zone_low, zone_high, terminal_state, fate_class, fate_bar, first_signal_bar, signal_events_n, gate_accept_n, gate_reject_n, giveup_bar, detail)
- Summary: `06_RESEARCH/results/fr4_fidelity/armed_poi_fate_summary.json` (pivots, M8 block, determinism block, fate definitions)
- Baseline + diag (unchanged): `06_RESEARCH/results/fr4_fidelity/run{1,2}/`, `06_RESEARCH/results/fr4_diag_nogate/`

**No parameter changes. No strategy-code changes. Diagnostic only.**
