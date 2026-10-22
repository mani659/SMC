# ESSENCE V1 — EXPERT REVIEW BRIEF (one page)

**Banner: DIAGNOSTIC / EXPERT REVIEW PACK — NOT PERFORMANCE**

Dear expert — this pack is for **stage-scoring only**. It contains 7
mechanically-executed trades from a frozen rules system, and asks you to mark
**whether the machine found and handled the setup correctly at each stage** —
NOT whether the system made money.

---

## 1) What ESSENCE V1 is

A small vertical trading path (separate from the existing COMPLEX baseline)
with five signed stages, executed on **native M1 bars**:

1. **Zone (Level):** an M8 HTF institutional demand/supply zone on W1/D1/H4,
   detected and tracked per the signed model spec — the machine never invents a
   borrow price; the zone's edges are the level.
2. **Sweep:** price wicks through the zone's near edge and **closes back
   inside** (wick+close-back rule; a close *through* the edge is a
   breakout, not a sweep).
3. **Confirm (set C):** an **M1 ending diagonal** forming at the zone after the
   sweep (frozen expiry). No other trigger may fire an essence entry (no FVG,
   no BOS blocks, no DUMB mid-reclaim, none of sets B/E).
4. **Entry:** a **LIMIT order inside the zone** on the M1 confirm level, valid
   30 M1 bars, cancelled on breakout beyond the confirmed level or edge.
5. **Manage:** SL = 2 (min) to 5 (max) pips beyond the M1 structure (the
   ending-diagonal terminal wick); TP = the near edge of the nearest active
   opposite-direction HTF zone, **only taken if planning ≥ 1:5 RR** (otherwise
   the setup is blocked, never downgraded); PureRunner break-even ON at
   1.0×ATR profit, 100% runner (stop moves to entry + 0.1×ATR; nothing exits
   early beyond that).

## 2) What to mark — open the scorecard

`06_RESEARCH/results/essence_v1_slice/EXPERT_SCORECARD.csv` — one row per
trade, all facts filled (zone bounds, sweep time/extreme, entry/SL/TP, BE
flag, exit). Fill the EMPTY score columns with exactly:
**CORRECT / PARTIAL / WRONG / UNCLEAR**.

- `score_level` — is the exported zone a real HTF institutional zone at that
  time on its timeframe?
- `score_sweep` — is the exported sweep moment/extreme a genuine zone-edge
  sweep (not an inside-zone touch, not an innocent-through breakout)?
- `score_confirm` — would you accept this description as an M1 ending-diagonal
  confirmation at that place? (Charts show the confirm bar and the M1 context.)
- `score_entry` — is the LIMIT level correct M1 geometry for this setup
  (entry must be judged against **M1** structure, not the HTF close/retrace)?
- `score_sl` — is the initial stop's placement sane (it must sit ~2–5 pips
  beyond the M1 structure protecting the setup — on this sample that is the
  deeper of the sweep wick and the ending-diagonal terminal wick; the scorecard
  exports `sl_initial` and, when BE moved it, the post-move `sl_at_exit`)?
- `score_tp_manage` — is the TP choice (a 1:5 minimum RR toward an opposite
  HTF zone) an acceptable target, and is the BE handling acceptable?
- `notes` — anything worth knowing in your words (be blunt).

## 3) What NOT to judge

- **PnL** (`pnl_diag` is book-internal price units, 0 costs — meaningless as
  performance) and "price went our way afterwards" — out of scope: this is a
  rules-process audit, not a strategy pitch.
- Sample size (n=7 over the frozen 6-month window 2025-06-01 → 2025-11-30,
  after a deep gate funnel: 61,422 sweeps → 51 confirms → 34 blocked by the
  1:5 gate → 9 limits → 7 fills). No edge claim is made anywhere in this pack.
- System-internal code details (constants, fill models) — judge the
  trade-of-record exhibits, not the plumbing.

## 4) Exhibits

- Charts: `06_RESEARCH/results/essence_v1_slice/expert_charts/trade_<id>.png`
  — M1 context around each trade: blue band = HTF zone (its dashed edges);
  M = sweep marker; C = confirm bar; dashed level lines labelled TP / EXIT /
  ENTRY / BE stop / SL in the right margin; dotted verticals at the sweep,
  confirm, and fill bars.
- Determinism: the two capture runs are byte-identical (`determinism.json`).
- Full method note (what the machine did, funnel, residuals):
  `06_RESEARCH/ESSENCE_V1_SLICE_NOTE.md` · pre-pack audit:
  `06_RESEARCH/ESSENCE_V1_QUICK_AUDIT.md`.

Fill the `score_*` columns in the CSV and return the file; wording in `notes`
is free.
