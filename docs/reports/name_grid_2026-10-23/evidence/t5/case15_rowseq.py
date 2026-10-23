"""Mode0 (SYNTHETIC) vs baseline native: rowdraw (r0,r1,r2,r3,[sp]) sequence inside the constructor D1 window must match."""
import json
from t5lib import *
def window(run):
    b = parse_bp((R / 'runs' / run / 'bp.log').read_text().splitlines())
    i = [k for k, x in enumerate(b) if x['name'] == 'D1'][0]
    j = [k for k, x in enumerate(b) if x['name'] == 'RET_ABA2' and k > i][0]
    return [(x['r0'], x['r1'], x['r2'], x['r3']) for x in b[i:j] if x['name'] == 'rowdraw']
c = window('case15-mode0-SYNTHETIC'); n = window('case15-baseline-native'); m1 = window('case15-mode1')
res = {'candidate_mode0': [[f'{v:08x}' for v in t] for t in c], 'baseline_native': [[f'{v:08x}' for v in t] for t in n],
       'candidate_mode1': [[f'{v:08x}' for v in t] for t in m1],
       'mode0_equals_baseline': c == n and len(c) == 6, 'mode1_uses_private_rows': [t[3] for t in m1] == [0x08F7613C, 0x08F76160, 0x08F76184, 0x08F761A8, 0x08F761C0, 0x08F761D8]}
(R / 'case15-rowseq.json').write_text(json.dumps(res, indent=1)); print(json.dumps(res))
