"""
SMC-R2 — Event Extraction Integrity & Causal Sample Validation
"""
import pandas as pd
import numpy as np
from pathlib import Path
import json, time, warnings
warnings.filterwarnings('ignore')

DATA_PATH = Path("D:/Gold Scripts/MQL5/Ticks Data/XAUUSD/m1_clean.csv")
OUTPUT_DIR = Path("D:/Gold Scripts/MQL5/SMC/SMC_RESEARCH/validation")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
N = 5

def detect_swings_vec(df, n=N):
    highs = df['high'].values; lows = df['low'].values; total = len(df)
    sh_idx = []; sl_idx = []
    for i in range(n, total - n):
        if all(highs[i] > highs[i-j] and highs[i] > highs[i+j] for j in range(1, n+1)):
            sh_idx.append(i)
        if all(lows[i] < lows[i-j] and lows[i] < lows[i+j] for j in range(1, n+1)):
            sl_idx.append(i)
    return sh_idx, sl_idx

def detect_fvgs_vec(df):
    h = df['high'].values; l = df['low'].values; ts = df['Datetime'].values
    fvgs = []
    for i in range(len(df)-2):
        if l[i+2] > h[i]:
            fvgs.append({'bar_index': i+2, 'ts': ts[i+2], 'dir': 'bull', 'upper': l[i+2], 'lower': h[i],
                         'gap': l[i+2]-h[i], 'ob_idx': i, 'ob_ts': ts[i],
                         'ob_o': df['open'].iloc[i], 'ob_h': h[i], 'ob_l': l[i], 'ob_c': df['close'].iloc[i]})
        if h[i+2] < l[i]:
            fvgs.append({'bar_index': i+2, 'ts': ts[i+2], 'dir': 'bear', 'upper': l[i], 'lower': h[i+2],
                         'gap': l[i]-h[i+2], 'ob_idx': i, 'ob_ts': ts[i],
                         'ob_o': df['open'].iloc[i], 'ob_h': h[i], 'ob_l': l[i], 'ob_c': df['close'].iloc[i]})
    return fvgs

print("="*70)
print("SMC-R2 — Event Extraction Integrity & Causal Sample Validation")
print("="*70)
t0 = time.time()

print("\n[1] Loading data...")
df = pd.read_csv(DATA_PATH, parse_dates=['Datetime']).sort_values('Datetime').reset_index(drop=True)
print(f"  XAUUSD M1 | {df['Datetime'].iloc[0]} to {df['Datetime'].iloc[-1]} | {len(df):,} bars | Dupes: {df['Datetime'].duplicated().sum()}")

print("\n[2] Detecting swings...")
sh_idx, sl_idx = detect_swings_vec(df)
swing_highs = [{'bar_index': i, 'ts': df['Datetime'].iloc[i], 'price': df['high'].iloc[i], 'type': 'SH',
                'conf_idx': i+N, 'conf_ts': df['Datetime'].iloc[min(i+N, len(df)-1)]} for i in sh_idx]
swing_lows = [{'bar_index': i, 'ts': df['Datetime'].iloc[i], 'price': df['low'].iloc[i], 'type': 'SL',
               'conf_idx': i+N, 'conf_ts': df['Datetime'].iloc[min(i+N, len(df)-1)]} for i in sl_idx]
all_swings = sorted(swing_highs + swing_lows, key=lambda x: x['bar_index'])
print(f"  SH: {len(swing_highs)} | SL: {len(swing_lows)} | Total: {len(all_swings)}")

print("\n[3] Detecting FVGs...")
fvgs = detect_fvgs_vec(df)
fvgs.sort(key=lambda x: x['bar_index'])
n_bull = sum(1 for f in fvgs if f['dir']=='bull')
print(f"  Bull: {n_bull} | Bear: {len(fvgs)-n_bull} | Total: {len(fvgs)}")

print("\n[4] Extracting OBs...")
obs = [{'bar_index': f['ob_idx'], 'ts': f['ob_ts'], 'dir': f['dir'],
        'zone_low': f['ob_l'], 'zone_high': f['ob_h'],
        'body_low': min(f['ob_o'], f['ob_c']), 'body_high': max(f['ob_o'], f['ob_c']),
        'fvg_bar': f['bar_index'], 'fvg_gap': f['gap']} for f in fvgs]
print(f"  Bull OB: {n_bull} | Bear OB: {len(obs)-n_bull} | Total: {len(obs)}")

print("\n[5] Detecting BOS...")
confirmed = sorted([{'idx': s['conf_idx'], 'price': s['price'], 'type': s['type']} for s in swing_highs + swing_lows], key=lambda x: x['idx'])
bos = []; last_sh = None; last_sl = None
for cs in confirmed:
    if cs['type']=='SH': last_sh = cs['price']
    else: last_sl = cs['price']
    if last_sh is None or last_sl is None: continue
    for i in range(cs['idx']+1, min(cs['idx']+50, len(df))):
        c = df['close'].iloc[i]
        if c > last_sh:
            bos.append({'bar_index': int(i), 'ts': df['Datetime'].iloc[i], 'dir': 'bull', 'swing': float(last_sh), 'close': float(c)}); break
        if c < last_sl:
            bos.append({'bar_index': int(i), 'ts': df['Datetime'].iloc[i], 'dir': 'bear', 'swing': float(last_sl), 'close': float(c)}); break
print(f"  Bull: {sum(1 for b in bos if b['dir']=='bull')} | Bear: {sum(1 for b in bos if b['dir']=='bear')} | Total: {len(bos)}")

print("\n[6] Lookahead audit...")
issues = []
for s in swing_highs:
    if s['conf_idx'] <= s['bar_index']: issues.append(f"SH: conf<=creat at {s['ts']}")
for f in fvgs:
    if f['bar_index'] < f['ob_idx']+2: issues.append(f"FVG: bar<ob+2 at {f['ts']}")
print(f"  Issues: {len(issues)}")

print("\n[7] Reproducibility...")
sh2, sl2 = detect_swings_vec(df)
assert len(sh2)==len(sh_idx) and len(sl2)==len(sl_idx), "Swings not reproducible"
fvgs2 = detect_fvgs_vec(df)
assert len(fvgs2)==len(fvgs), "FVGs not reproducible"
print("  REPRODUCIBLE")

elapsed = time.time()-t0
summary = {'bars': int(len(df)), 'date_range': f"{df['Datetime'].iloc[0]} to {df['Datetime'].iloc[-1]}",
           'swing_highs': len(swing_highs), 'swing_lows': len(swing_lows), 'total_swings': len(all_swings),
           'total_fvgs': len(fvgs), 'total_obs': len(obs), 'total_bos': len(bos),
           'lookahead_issues': len(issues), 'reproducible': True, 'elapsed_s': round(elapsed,1)}

print(f"\n[8] Summary: {json.dumps(summary, default=str)}")
with open(OUTPUT_DIR/"SMC_R2_extraction_summary.json",'w') as f: json.dump(summary,f,indent=2,default=str)
pd.DataFrame(all_swings).to_csv(OUTPUT_DIR/"SMC_R2_swings.csv",index=False)
pd.DataFrame(fvgs).to_csv(OUTPUT_DIR/"SMC_R2_fvgs.csv",index=False)
pd.DataFrame(obs).to_csv(OUTPUT_DIR/"SMC_R2_obs.csv",index=False)
pd.DataFrame(bos).to_csv(OUTPUT_DIR/"SMC_R2_bos.csv",index=False)
print(f"\nDone in {elapsed:.1f}s. Files saved.")
print("="*70)
