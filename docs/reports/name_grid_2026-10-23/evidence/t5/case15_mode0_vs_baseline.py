"""Semantic control for the SYNTHETIC mode0 probe: baseline ROM (same build, no name composer) normal name screen
via the same candidate fresh route keys -> guidance closed -> A at (0,0). Compare screen/RAM/BP path with candidate mode0."""
import json
from t5lib import *
from case11 import route
from PIL import ImageChops
e = Emu('case15-baseline-native', 'baseline', bps=BPS_ALL)
res = {}
try:
    for x in route('candidate-fresh-to-name.route'):
        e.cmd(x)
    closes = 0
    while e.obj()[1][0x66] != 1 and closes < 4:
        e.tap(A, 60); closes += 1
    res['guidance_A_presses'] = closes
    e.shot('ready')
    m = e.bp_mark()
    e.move_to(0, 0); m = e.bp_mark(); e.tap(A, 24)
    e.shot('after-a')
    ptr, o = e.obj('after-a-obj.bin')
    res['obj'] = f'{ptr:08x}'; res['mode'] = o[0x60]; res['len'] = o[0x61]; res['live'] = o[0x2C:0x34].hex()
    res['bp_path'] = [b['name'] for b in parse_bp(e.bp_lines(m)) if b['name'] not in ('A3_copy', 'rowdraw', 'RET_B428')]
finally:
    e.close()
a = Image.open(R / 'runs/case15-mode0-SYNTHETIC/after-a.png').convert('RGB')
b = Image.open(e.d / 'after-a.png').convert('RGB')
res['screen_identical_to_candidate_mode0'] = ImageChops.difference(a, b).getbbox() is None
res['screen_diff_bbox'] = ImageChops.difference(a, b).getbbox()
cand = parse_bp((R / 'runs/case15-mode0-SYNTHETIC/bp.log').read_text().splitlines())
i = [k for k, x in enumerate(cand) if x['name'] == 'S1'][0]
res['candidate_mode0_S1_path'] = [x['name'] for x in cand[i:i + 12] if x['name'] not in ('A3_copy', 'rowdraw', 'RET_B428')]
co = (R / 'runs/case15-mode0-SYNTHETIC/after-a-obj.bin').read_bytes()
res['ram_0x00_0x6F_equal_except_ptr_fields'] = [hex(k) for k in range(0x70) if co[k] != o[k]]
res['pass'] = res['screen_identical_to_candidate_mode0'] and res['live'] == co[0x2C:0x34].hex() and res['len'] == co[0x61]
(e.d / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
print(json.dumps(res, ensure_ascii=False))
