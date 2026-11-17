# Diagnostic probe: capture per-candidate blocked_log for poi-005876 /
# poi-022439 in the aug25 PROD replays (won-but-missed anchor signature).
# Research-only, in-process; writes to _probe dir, never touches real runs.
import json
import sys
from pathlib import Path

REPO = Path(r'D:\Gold Scripts\MQL5\SMC')
sys.path.insert(0, str(REPO / '04_SRC'))
sys.path.insert(0, str(REPO / '06_RESEARCH' / 'scripts'))

import r1_pure_tag_books as r  # noqa: E402
from smc.backtest.runner import BacktestRunner  # noqa: E402

TARGETS = {'poi-005876', 'poi-022439'}
PROBE = r.OUT / '_probe'
CAPTURED: dict[str, list] = {}

_orig_result = BacktestRunner.result


def probe_result(self):
    # stash the full per-candidate block log before projection
    CAPTURED[id(self)] = [
        {'bar_index': b.bar_index, 'now': str(b.now), 'blocked_by': b.blocked_by,
         'poi_id': b.poi_id, 'trigger': getattr(b.trigger, 'value', b.trigger),
         'route_id': b.route_id}
        for b in getattr(self, 'blocked_log', [])]
    return _orig_result(self)


BacktestRunner.result = probe_result

seg = 'aug25'
lo, hi = r.SEGMENTS[seg]
series = r.segment_series(lo, hi)
armed = json.loads((r.SRC / seg / 'armed_records.json').read_text(encoding='utf-8'))
armed = [dict(rec, poi_id=pid) for pid, rec in armed.items()]
truth = r.load_truth_directions(seg)

out = {}
for hyp in ('LONG', 'SHORT'):
    rid = f'PROD_{hyp}'
    r.run_book(seg, series, armed, truth, letter=None, variant='PROD',
               hyp=hyp, run_id=rid, run_dir=PROBE / rid)
    blocks = CAPTURED.get(next(iter(CAPTURED)), []) if CAPTURED else []
    # CAPTURED keyed by runner id — take the LAST captured list (this run)
    latest = CAPTURED[list(CAPTURED.keys())[-1]] if CAPTURED else []
    out[hyp] = [b for b in latest if b['poi_id'] in TARGETS]
    CAPTURED.clear()

(PROBE / 'blocked_probe.json').write_text(
    json.dumps(out, indent=2, default=str), encoding='utf-8')
print('probe written:', json.dumps(out, indent=1), flush=True)
