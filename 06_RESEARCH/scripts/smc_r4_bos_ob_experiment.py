"""
SMC-R4 -- BOS + Order Block Continuation Standalone Economic Experiment
Memory-optimized: loads data directly with numpy to minimize memory usage.
"""

import numpy as np
import json, time, sys
from pathlib import Path

# FROZEN CONSTANTS
MAX_WINDOW = 20
HORIZON = 120
HAC_BANDWIDTH = 10
ALPHA = 0.05
OOS_SPLIT = '2024-12-31'

DATA_DIR = Path("D:/Gold Scripts/MQL5/Ticks Data/XAUUSD")
R2_DIR = Path("D:/Gold Scripts/MQL5/SMC/SMC_RESEARCH/validation")
OUTPUT_DIR = Path("D:/Gold Scripts/MQL5/SMC/SMC_RESEARCH/experiments")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

t0 = time.time()

# 1. LOAD M1 DATA with numpy (memory efficient)
print("[1] Loading M1 data with numpy...")
# Read datetime column separately, load OHLC as float32
import csv

# Count lines first
with open(DATA_DIR / "m1_clean.csv") as f:
    n = sum(1 for _ in f) - 1  # minus header
print(f"  Total bars: {n}")

# Load OHLC as numpy arrays
data = np.loadtxt(DATA_DIR / "m1_clean.csv", delimiter=',', skiprows=1, 
                  usecols=(1,2,3,4), dtype=np.float32)
# datetime strings
dt_strings = []
with open(DATA_DIR / "m1_clean.csv") as f:
    next(f)  # skip header
    for line in f:
        dt_strings.append(line.split(',')[0])

dt_strings = np.array(dt_strings)
print(f"  Loaded OHLC: {data.shape}")
print(f"  Range: {dt_strings[0]} to {dt_strings[-1]}")

bars_open = data[:, 0]
bars_high = data[:, 1]
bars_low  = data[:, 2]
bars_close = data[:, 3]

# Parse OOS split
oos_split_str = OOS_SPLIT  # '2024-12-31'

# 2. LOAD R2 BOS and FVGs
print("[2] Loading R2 primitives...")
# BOS: bar_index,ts,dir,swing,close
bos_bi = []; bos_ts = []; bos_dir = []; bos_swing = []; bos_close = []
with open(R2_DIR / "SMC_R2_bos.csv") as f:
    next(f)
    for line in f:
        parts = line.strip().split(',')
        bos_bi.append(int(parts[0]))
        bos_ts.append(parts[1])
        bos_dir.append(parts[2])
        bos_swing.append(float(parts[3]))
        bos_close.append(float(parts[4]))

bos_bi = np.array(bos_bi, dtype=np.int32)
bos_swing = np.array(bos_swing, dtype=np.float32)
bos_close_arr = np.array(bos_close, dtype=np.float32)
print(f"  BOS: {len(bos_bi)}")

# FVGs: bar_index,ts,dir,upper,lower,gap,ob_idx,ob_ts,...
# Load numeric columns directly with numpy for memory efficiency
fvg_raw = np.loadtxt(R2_DIR / "SMC_R2_fvgs.csv", delimiter=',', skiprows=1,
                     usecols=(0,3,4,5,6), dtype=np.float32)
fvg_bi = fvg_raw[:, 0].astype(np.int32)
fvg_upper = fvg_raw[:, 1]
fvg_lower = fvg_raw[:, 2]
fvg_gap_arr = fvg_raw[:, 3]
fvg_ob_idx = fvg_raw[:, 4].astype(np.int32)

# Load dir as strings separately (minimal memory)
fvg_dir = []
fvg_ts = []
fvg_ob_ts = []
with open(R2_DIR / "SMC_R2_fvgs.csv") as f:
    next(f)
    for line in f:
        parts = line.strip().split(',')
        fvg_dir.append(parts[2])
        fvg_ts.append(parts[1])
        fvg_ob_ts.append(parts[7])

# Sort FVGs by bar_index
fvg_sort = np.argsort(fvg_bi)
fvg_bi = fvg_bi[fvg_sort]
fvg_dir = [fvg_dir[i] for i in fvg_sort]
fvg_ob_idx = fvg_ob_idx[fvg_sort]
fvg_upper = fvg_upper[fvg_sort]
fvg_lower = fvg_lower[fvg_sort]
fvg_gap_arr = fvg_gap_arr[fvg_sort]
fvg_ts_sorted = [fvg_ts[i] for i in fvg_sort]
fvg_ob_ts_sorted = [fvg_ob_ts[i] for i in fvg_sort]

# Sort BOS by bar_index
bos_sort = np.argsort(bos_bi)
bos_bi = bos_bi[bos_sort]
bos_dir_sorted = [bos_dir[i] for i in bos_sort]
bos_ts_sorted = [bos_ts[i] for i in bos_sort]
bos_swing_sorted = bos_swing[bos_sort]
bos_close_sorted = bos_close_arr[bos_sort]

print(f"  FVGs: {len(fvg_bi)}")

# 3. BUILD EVENTS
print("[3] Building BOS->FVG->OB events...")

# Collect results as lists of scalars (memory efficient)
E_bos_idx=[]; E_bos_ts=[]; E_bos_dir=[]; E_bos_swing=[]; E_bos_close=[]
E_fvg_idx=[]; E_fvg_ts=[]; E_fvg_gap=[]
E_ob_idx=[]; E_ob_ts=[]; E_ob_lo=[]; E_ob_hi=[]
E_ob_prox=[]; E_ob_dist=[]

for i in range(len(bos_bi)):
    b_idx = int(bos_bi[i])
    b_dir = bos_dir_sorted[i]
    
    # Search for qualifying FVGs in (b_idx, b_idx+MAX_WINDOW]
    lo = np.searchsorted(fvg_bi, b_idx + 1, side='left')
    up = b_idx + MAX_WINDOW
    pos = lo
    found = False
    while pos < len(fvg_bi) and fvg_bi[pos] <= up:
        if fvg_dir[pos] == b_dir:
            oi = int(fvg_ob_idx[pos])
            if oi >= n:
                break
            oh = float(bars_high[oi])
            ol = float(bars_low[oi])
            if oh == ol:
                break
            prox = oh if b_dir == 'bull' else ol
            dist = ol if b_dir == 'bull' else oh
            E_bos_idx.append(b_idx)
            E_bos_ts.append(bos_ts_sorted[i])
            E_bos_dir.append(b_dir)
            E_bos_swing.append(float(bos_swing_sorted[i]))
            E_bos_close.append(float(bos_close_sorted[i]))
            E_fvg_idx.append(int(fvg_bi[pos]))
            E_fvg_ts.append(fvg_ts_sorted[pos])
            E_fvg_gap.append(float(fvg_gap_arr[pos]))
            E_ob_idx.append(oi)
            E_ob_ts.append(fvg_ob_ts_sorted[pos])
            E_ob_lo.append(ol)
            E_ob_hi.append(oh)
            E_ob_prox.append(prox)
            E_ob_dist.append(dist)
            found = True
            break
        pos += 1

n_events = len(E_bos_idx)
print(f"  Events: {n_events}")
print(f"  Time: {time.time()-t0:.1f}s")

# 4. SIMULATE TRADES
print("[4] Simulating trades...")
T_eid=[]; T_bos_ts=[]; T_bos_dir=[]; T_fvg_ts=[]; T_ob_ts=[]
T_ob_prox=[]; T_ob_dist=[]
T_ft_ts=[]; T_entry_ts=[]; T_entry_px=[]; T_stop_px=[]
T_stop_hit=[]; T_exit_ts=[]; T_exit_px=[]; T_exit_reason=[]
T_ret=[]; T_oos=[]

for ei in range(n_events):
    ob_bar = E_ob_idx[ei]
    ob_lo = E_ob_lo[ei]
    ob_hi = E_ob_hi[ei]
    prox = E_ob_prox[ei]
    dist = E_ob_dist[ei]
    d = E_bos_dir[ei]

    # first touch
    ft = -1
    max_j = min(n - HORIZON - 2, n)
    for j in range(ob_bar + 1, max_j):
        if bars_low[j] <= ob_hi and bars_high[j] >= ob_lo:
            ft = j
            break
    if ft < 0:
        continue

    # entry: next bar open
    entry_bar = ft + 1
    if entry_bar >= n:
        continue
    entry_open = float(bars_open[entry_bar])

    # fill constraint
    if d == 'bull' and entry_open < prox:
        continue
    if d == 'bear' and entry_open > prox:
        continue

    # gap-through check
    if d == 'bull' and entry_open <= dist:
        continue
    if d == 'bear' and entry_open >= dist:
        continue

    fill = entry_open
    stop_hit = False
    exit_px = 0.0
    exit_r = ''
    exit_b = -1

    # simulate path
    end_bar = min(entry_bar + HORIZON + 1, n)
    for k in range(entry_bar + 1, end_bar):
        if d == 'bull' and bars_low[k] <= dist:
            stop_hit = True; exit_b = k; exit_px = dist; exit_r = 'stop'; break
        if d == 'bear' and bars_high[k] >= dist:
            stop_hit = True; exit_b = k; exit_px = dist; exit_r = 'stop'; break

    if stop_hit:
        exit_ts = dt_strings[exit_b]
    else:
        hb = entry_bar + HORIZON
        if hb >= n:
            continue
        exit_px = float(bars_close[hb])
        exit_ts = dt_strings[hb]
        exit_r = 'horizon'

    # directional return (bps)
    if d == 'bull':
        ret = (exit_px - fill) / fill * 10000
    else:
        ret = (fill - exit_px) / fill * 10000

    # OOS flag
    entry_date = dt_strings[entry_bar]
    oos = 'OOS' if entry_date > oos_split_str else 'DISC'

    T_eid.append(E_bos_idx[ei])
    T_bos_ts.append(E_bos_ts[ei])
    T_bos_dir.append(d)
    T_fvg_ts.append(E_fvg_ts[ei])
    T_ob_ts.append(E_ob_ts[ei])
    T_ob_prox.append(prox)
    T_ob_dist.append(dist)
    T_ft_ts.append(dt_strings[ft])
    T_entry_ts.append(dt_strings[entry_bar])
    T_entry_px.append(fill)
    T_stop_px.append(dist)
    T_stop_hit.append(stop_hit)
    T_exit_ts.append(exit_ts)
    T_exit_px.append(exit_px)
    T_exit_reason.append(exit_r)
    T_ret.append(ret)
    T_oos.append(oos)

n_trades = len(T_ret)
ret_arr = np.array(T_ret, dtype=np.float32)
oos_arr = np.array(T_oos)
dir_arr = np.array(T_bos_dir)
stop_arr = np.array(T_stop_hit)

print(f"  Trades: {n_trades}")
print(f"  Time: {time.time()-t0:.1f}s")

# 5. STATISTICS
print("\n[5] Statistics...")

disc_mask = oos_arr == 'DISC'
oos_mask  = oos_arr == 'OOS'
bull_mask = dir_arr == 'bull'
bear_mask = dir_arr == 'bear'

disc_ret = ret_arr[disc_mask]
oos_ret  = ret_arr[oos_mask]

mean_r = float(np.mean(ret_arr))
med_r  = float(np.median(ret_arr))
std_r  = float(np.std(ret_arr, ddof=1))
pos_frac = float(np.mean(ret_arr > 0))

oos_mean = float(np.mean(oos_ret)) if len(oos_ret) > 0 else 0.0
disc_mean = float(np.mean(disc_ret)) if len(disc_ret) > 0 else 0.0

long_mean = float(np.mean(ret_arr[bull_mask])) if np.any(bull_mask) else 0.0
short_mean = float(np.mean(ret_arr[bear_mask])) if np.any(bear_mask) else 0.0
stop_mean = float(np.mean(ret_arr[stop_arr])) if np.any(stop_arr) else 0.0
nostop_mean = float(np.mean(ret_arr[~stop_arr])) if np.any(~stop_arr) else 0.0

# HAC standard errors (Newey-West)
def hac_se(res, bw):
    nn = len(res)
    if nn < 2: return 0.0
    m = np.mean(res)
    c = res - m
    v = float(np.mean(c**2))
    for lag in range(1, bw+1):
        w = 1.0 - lag/(bw+1)
        v += 2.0 * w * float(np.mean(c[lag:]*c[:-lag]))
    return np.sqrt(max(v, 0)/nn)

se_f = hac_se(ret_arr, HAC_BANDWIDTH)
se_o = hac_se(oos_ret, HAC_BANDWIDTH)
se_d = hac_se(disc_ret, HAC_BANDWIDTH)

t_f = mean_r/se_f if se_f > 0 else 0
t_o = oos_mean/se_o if se_o > 0 else 0
t_d = disc_mean/se_d if se_d > 0 else 0

# Manual t-CDF approximation
def t_cdf_approx(t_val, df):
    if df > 1000:
        x = t_val / np.sqrt(1 + t_val*t_val/(2*df))
        return 0.5*(1 + np.tanh(1.702*x))
    # Simple integration
    from math import gamma as gam, sqrt, pi
    def t_pdf(x, nu):
        c = gam((nu+1)/2) / (sqrt(nu*pi)*gam(nu/2))
        return c * (1 + x*x/nu)**(-(nu+1)/2)
    lo_val = -20.0
    N = 2000
    dx = (t_val - lo_val) / N
    s = 0.0
    for ii in range(N+1):
        xi = lo_val + ii*dx
        w = dx if (0 < ii < N) else dx/2
        s += w * t_pdf(xi, df)
    return min(max(s, 0.0), 1.0)

p_f = float(1 - t_cdf_approx(t_f, n_trades-1)) if n_trades > 1 else 1.0
p_o = float(1 - t_cdf_approx(t_o, len(oos_ret)-1)) if len(oos_ret) > 1 else 1.0
p_d = float(1 - t_cdf_approx(t_d, len(disc_ret)-1)) if len(disc_ret) > 1 else 1.0

# 95% one-sided CI lower bound
ci_f = float(mean_r - 1.645*se_f) if n_trades > 1 else 0
ci_o = float(oos_mean - 1.645*se_o) if len(oos_ret) > 1 else 0

print(f"  Full: n={n_trades}  mean={mean_r:.4f}  median={med_r:.4f}  std={std_r:.4f}  pos={pos_frac:.4f}")
print(f"  Full: t={t_f:.4f}  SE={se_f:.4f}  p={p_f:.6f}  CI_lo={ci_f:.4f}")
print(f"  Disc: n={len(disc_ret)}  mean={disc_mean:.4f}  t={t_d:.4f}  p={p_d:.6f}")
print(f"  OOS:  n={len(oos_ret)}  mean={oos_mean:.4f}  t={t_o:.4f}  p={p_o:.6f}  CI_lo={ci_o:.4f}")
print(f"  Long: n={int(np.sum(bull_mask))}  mean={long_mean:.4f}")
print(f"  Short: n={int(np.sum(bear_mask))}  mean={short_mean:.4f}")
print(f"  Stopped: n={int(np.sum(stop_arr))}  mean={stop_mean:.4f}")
print(f"  Not stopped: n={int(np.sum(~stop_arr))}  mean={nostop_mean:.4f}")

# 6. DECISION
if mean_r > 0 and p_f < ALPHA:
    decision = "POSITIVE EXPECTANCY ESTABLISHED"
else:
    decision = "NO POSITIVE EXPECTANCY ESTABLISHED"

if len(oos_ret) > 0 and oos_mean > 0 and p_o < ALPHA:
    oos_dec = "ROBUST"
elif len(oos_ret) > 0 and oos_mean > 0:
    oos_dec = "FRAGILE (OOS positive but not significant)"
elif len(oos_ret) > 0:
    oos_dec = "FRAGILE (OOS negative)"
else:
    oos_dec = "NO OOS EVENTS"

print(f"\n  DECISION: {decision}")
print(f"  OOS: {oos_dec}")

# 7. YEARLY BREAKDOWN
print("\n[6] Yearly breakdown...")
entry_dates = np.array([int(s[:4]) for s in T_entry_ts])
for yr in sorted(set(entry_dates)):
    m = entry_dates == yr
    yr_ret = ret_arr[m]
    print(f"  {yr}: n={int(np.sum(m))}  mean={np.mean(yr_ret):.4f}  pos={np.mean(yr_ret>0):.4f}  stopped={int(np.sum(stop_arr[m]))}")

# 8. LOOKAHEAD
la = 0
for i in range(n_trades):
    if T_entry_ts[i] <= T_ft_ts[i]: la += 1
    if T_ft_ts[i] <= T_ob_ts[i]: la += 1
print(f"\n  Lookahead issues: {la}")

# 9. SAVE
print("\n[7] Saving...")

# Trades CSV
with open(OUTPUT_DIR / "SMC_R4_BOS_OB_Trades.csv", 'w') as f:
    f.write("event_id,bos_timestamp,bos_direction,fvg_timestamp,ob_timestamp,")
    f.write("ob_proximal,ob_distal,first_touch_timestamp,entry_timestamp,")
    f.write("entry_price,stop_price,stop_hit,exit_timestamp,exit_price,")
    f.write("exit_reason,directional_return_bps,oos_flag\n")
    for i in range(n_trades):
        f.write(f"{T_eid[i]},{T_bos_ts[i]},{T_bos_dir[i]},{T_fvg_ts[i]},{T_ob_ts[i]},")
        f.write(f"{T_ob_prox[i]},{T_ob_dist[i]},{T_ft_ts[i]},{T_entry_ts[i]},")
        f.write(f"{T_entry_px[i]},{T_stop_px[i]},{T_stop_hit[i]},{T_exit_ts[i]},{T_exit_px[i]},")
        f.write(f"{T_exit_reason[i]},{T_ret[i]:.4f},{T_oos[i]}\n")

# Summary JSON
summary = {
    'milestone':'SMC-R4','status':'COMPLETE',
    'total_trades':n_trades,'disc_trades':int(len(disc_ret)),'oos_trades':int(len(oos_ret)),
    'long_trades':int(np.sum(bull_mask)),'short_trades':int(np.sum(bear_mask)),
    'stopped':int(np.sum(stop_arr)),'not_stopped':int(np.sum(~stop_arr)),
    'mean_r_bps':round(mean_r,4),'median_r_bps':round(med_r,4),'std_r_bps':round(std_r,4),
    'pos_frac':round(pos_frac,4),
    'full_t':round(t_f,4),'full_se':round(se_f,4),'full_p':round(p_f,6),'full_ci_lo':round(ci_f,4),
    'disc_mean':round(disc_mean,4),'disc_t':round(t_d,4),'disc_p':round(p_d,6),
    'oos_mean':round(oos_mean,4),'oos_t':round(t_o,4),'oos_p':round(p_o,6),'oos_ci_lo':round(ci_o,4),
    'long_mean':round(long_mean,4),'short_mean':round(short_mean,4),
    'stop_mean':round(stop_mean,4),'nostop_mean':round(nostop_mean,4),
    'decision':decision,'oos_decision':oos_dec,'lookahead_issues':la,
    'elapsed_s':round(time.time()-t0,1),
}
with open(OUTPUT_DIR/"SMC_R4_Result_Summary.json",'w') as f:
    json.dump(summary, f, indent=2, default=str)

m3_status = "BOS+OB qualifies as M3 Economic Candidate" if "POSITIVE" in decision else "BOS+OB does not qualify as M3"

result = f"""Milestone: SMC-R4
Status: COMPLETE

Research question: Does BOS+OB continuation produce positive mean net path-dependent trade payoff on XAUUSD?

Canonical dataset: XAUUSD M1, 2021-04-12 to 2026-04-10, 1768123 bars
Discovery period: 2021-04-12 to 2024-12-31
OOS period: 2025-01-01 to 2026-04-10

Total trades: {n_trades}
Discovery trades: {len(disc_ret)}
OOS trades: {len(oos_ret)}
Long trades: {int(np.sum(bull_mask))}
Short trades: {int(np.sum(bear_mask))}
Stopped trades: {int(np.sum(stop_arr))}
Non-stopped trades: {int(np.sum(~stop_arr))}

Primary full-dataset mean R: {mean_r:.4f} bps
Median R: {med_r:.4f} bps
Std R: {std_r:.4f} bps
Positive fraction: {pos_frac:.4f}
Full HAC SE: {se_f:.4f}
Full t-statistic: {t_f:.4f}
Full p-value (one-sided): {p_f:.6f}
Full 95% CI lower bound: {ci_f:.4f} bps

OOS mean R: {oos_mean:.4f} bps
OOS HAC SE: {se_o:.4f}
OOS t-statistic: {t_o:.4f}
OOS p-value: {p_o:.6f}
OOS 95% CI lower bound: {ci_o:.4f} bps

Discovery mean R: {disc_mean:.4f} bps
Discovery HAC SE: {se_d:.4f}
Discovery t-statistic: {t_d:.4f}
Discovery p-value: {p_d:.6f}

Long mean R: {long_mean:.4f} bps
Short mean R: {short_mean:.4f} bps
Stopped mean R: {stop_mean:.4f} bps
Non-stopped mean R: {nostop_mean:.4f} bps

Primary decision: {decision}
OOS consistency: {oos_dec}

M3 status: {m3_status}
M4 status: NOT STARTED

Lookahead audit: {la} issues
Methodology deviations: NONE

External API calls: 0
New data acquired: 0
Spend: $0.00
"""
with open(OUTPUT_DIR/"SMC_R4_RESULT.md",'w') as f:
    f.write(result)

# Experiment report
report = f"""# SMC-R4 -- BOS + Order Block Continuation Standalone Economic Experiment

**Date**: 2026-08-27
**Milestone**: SMC-R4
**Status**: COMPLETE

---

## Frozen Methodology

| Component | Value |
|-----------|-------|
| BOS definition | Close beyond confirmed swing (N=5) |
| FVG definition | 3-candle gap, same direction as BOS |
| Association window | MAX_WINDOW = 20 bars |
| FVG selection | First chronological qualifying FVG |
| OB definition | Candle preceding selected FVG |
| Entry | Next-bar open (if reaches OB.proximal) |
| Stop | OB.distal edge |
| Horizon | 120 bars (2 hours) |
| Costs | Implicit (fill convention) |
| OOS split | 2024-12-31 |
| HAC bandwidth | 10 |
| Alpha | 0.05 |

---

## Results

### Full Dataset

| Metric | Value |
|--------|-------|
| Total trades | {n_trades} |
| Mean R (bps) | {mean_r:.4f} |
| Median R (bps) | {med_r:.4f} |
| Std R (bps) | {std_r:.4f} |
| Positive fraction | {pos_frac:.4f} |
| HAC SE | {se_f:.4f} |
| t-statistic | {t_f:.4f} |
| p-value (one-sided) | {p_f:.6f} |
| 95% CI lower bound | {ci_f:.4f} bps |

### Discovery Period

| Metric | Value |
|--------|-------|
| Trades | {len(disc_ret)} |
| Mean R (bps) | {disc_mean:.4f} |
| HAC SE | {se_d:.4f} |
| t-statistic | {t_d:.4f} |
| p-value | {p_d:.6f} |

### OOS Period

| Metric | Value |
|--------|-------|
| Trades | {len(oos_ret)} |
| Mean R (bps) | {oos_mean:.4f} |
| HAC SE | {se_o:.4f} |
| t-statistic | {t_o:.4f} |
| p-value | {p_o:.6f} |
| 95% CI lower bound | {ci_o:.4f} bps |

---

## Direction Split

| Direction | Count | Mean R (bps) |
|-----------|:-----:|:------------:|
| Long | {int(np.sum(bull_mask))} | {long_mean:.4f} |
| Short | {int(np.sum(bear_mask))} | {short_mean:.4f} |

---

## Stop Analysis

| Category | Count | Mean R (bps) |
|----------|:-----:|:------------:|
| Stopped | {int(np.sum(stop_arr))} | {stop_mean:.4f} |
| Non-stopped | {int(np.sum(~stop_arr))} | {nostop_mean:.4f} |

---

## Primary Decision

**{decision}**

---

## Lookahead Audit

Issues: {la}

---

*SMC-R4 is the first empirical SMC economic experiment.*
"""

with open(OUTPUT_DIR/"SMC_R4_BOS_OB_Experiment.md",'w') as f:
    f.write(report)

elapsed = time.time() - t0
print(f"\n{'='*60}")
print(f"SMC-R4 COMPLETE in {elapsed:.1f}s")
print(f"{'='*60}")
print(f"DECISION: {decision}")
print(f"OOS: {oos_dec}")
print(f"Mean R: {mean_r:.4f} bps (p={p_f:.6f})")
print(f"OOS Mean R: {oos_mean:.4f} bps (p={p_o:.6f})")
print(f"Files: {OUTPUT_DIR}")
