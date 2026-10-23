"""Case 12: Versus user-map list with a name made by the new feature (normal keys).
build: candidate + T5 save case11b.sav (full8 typed by grid keys, same original map as list-link-re used)
       -> list-link-re/candidate-map.route (existing normal keys: load, HQ/factory placement, native save/overwrite)
       -> dumpsave (O_EXCL)
cold : separate process with only that save -> list-link-re/candidate-cold-fixed.route (Versus, category cycling)
       -> category5 design-map list: screenshot + A3 glyph copies for all 8 syllables of the stored name.
"""
import json
from t5lib import *
from case11 import FULL8, find_all

def expand(path):
    out = []
    for l in Path(path).read_text().splitlines():
        a = l.split()
        if not a:
            continue
        if a[0] == 'tap':
            out += [f'keys {a[1]}', 'frames 1', 'keys 0', f'frames {a[2] if len(a) > 2 else 24}']
        elif a[0] in ('keys', 'frames', 'shot'):
            out.append(l)
    return out

def a3_src(code):
    r = crom()
    start, end = struct.unpack_from('<II', r, 0xF30308)
    hits = [i for i in range(start - 0x08000000, end - 0x08000000, 6) if r[i:i + 2] == code.to_bytes(2, 'big')]
    assert len(hits) == 1
    top = struct.unpack_from('<H', r, hits[0] + 2)[0]
    return 0x08F00000 + (top & 0x7FFF) * 32

def build():
    src = R / 'runs/case11b-save/case11b.sav'
    e = Emu('case12-build', 'candidate', save=src, bps=[0x08F302D8])
    checks = []
    try:
        for l in expand(B / 'list-link-re/candidate-map.route'):
            if l.startswith('shot '):
                e.shot(l.split()[1])
            else:
                e.cmd(l)
        s = e.dumpsave('case12-valid.sav')
        b = s.read_bytes()
        checks.append({'name': 'full8 name kept in saved valid map', 'ok': bool(find_all(b, FULL8)), 'offsets': [hex(x) for x in find_all(b, FULL8)], 'sha256': sha(s)})
    finally:
        e.close()
    return e, checks

def cold(savefile):
    e = Emu('case12-cold-versus', 'candidate', save=savefile, bps=[0x08F302D8])
    checks = []
    want = {a3_src(int.from_bytes(FULL8[i:i + 2], 'big')): ch for i, ch in zip(range(0, 16, 2), '가나다라마바사안')}
    try:
        m = None
        for l in expand(B / 'list-link-re/candidate-cold-fixed.route'):
            if l.startswith('shot '):
                n = l.split()[1]
                if n == 'category5':
                    m0 = e.bp_mark()
                e.shot(n)
                if n == 'category4':
                    m = e.bp_mark()
                if n == 'category5':
                    got = {b['r6'] for b in parse_bp(e.bp_lines(m)) if b['name'] == 'A3_copy'}
                    checks.append({'name': 'category5: A3 glyph copies for all 8 syllables after switching to category 5',
                                   'ok': set(want) <= got, 'missing': [want[x] for x in set(want) - got], 'copies_in_window': len(got)})
                    e.tap(A, 180); e.shot('selected')  # select the user map (route stops cycling here)
                    break
            else:
                e.cmd(l)
    finally:
        e.close()
    return e, checks

if __name__ == '__main__':
    import sys
    eb, cb = build() if 'cold-only' not in sys.argv else (type('x',(),{'d':R/'runs/case12-build'})(), json.loads((R/'case12-result.json').read_text())['build'])
    res = {'case': 'case12', 'build': cb, 'run_build': 'runs/case12-build'}
    sav = eb.d / 'case12-valid.sav'
    if sav.exists():
        ec, cc = cold(sav)
        res['cold'] = cc
        res['run_cold'] = 'runs/case12-cold-versus'
    res['pass_automatic'] = all(c['ok'] for c in cb + res.get('cold', []))
    res['needs_visual'] = ['runs/case12-build/valid-map.png (two HQ + factories)', 'runs/case12-cold-versus/category5.png (가나다라마바사안 in design-map list)']
    (R / 'case12-result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False))
