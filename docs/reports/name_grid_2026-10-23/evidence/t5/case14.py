"""Case 14 (original-ROM control) + case 13b (legacy kana conversion preserved on the candidate).
14: original ROM, blank cartridge, native fresh3 keys -> name -> A at (0,0) = ア (1 key control: harness/route valid)
    -> ア×7 + カ by grid keys -> native confirm -> save slot 1 (dumpsave O_EXCL)
    -> re-enter name -> dakuten cell, R, handakuten cell: record live after each (native reference).
13b: candidate cold boot with that save -> load map -> re-enter name -> same three inputs -> live must equal the original's.
"""
import json
from t5lib import *
from case11 import route, save_slot1, find_all
from cases import reenter_name

KANA = bytes.fromhex('8341') * 7 + bytes.fromhex('834a')
SEQ = [('dakuten', (10, 2)), ('R', None), ('handakuten', (11, 2))]

def live(e):
    _, o = e.obj()
    return o

def apply_seq(e, tag):
    rows = []
    for label, cell in SEQ:
        before = live(e)
        m = e.bp_mark()
        if cell:
            e.move_to(*cell)
            m = e.bp_mark()
            e.tap(A, 24)
        else:
            e.tap(RK, 24)
        o = live(e)
        bps = parse_bp(e.bp_lines(m))
        rows.append({'input': label, 'live16': o[0x2C:0x3C].hex(), 'len': o[0x61], 'tail': o[0x70:0x74].hex(),
                     'sounds': [f"{b['r0']:02x}" for b in bps if b['name'] == 'sound'], 'changed': before[0x2C:0x3C] != o[0x2C:0x3C]})
        e.shot(f'{tag}-{label}')
    return rows

def original_control():
    e = Emu('case14-original', 'original', bps=BPS_ALL)
    checks, notes = [], []
    try:
        for x in route('fresh3-keys.route'):
            e.cmd(x)
        e.shot('name-ready')
        e.tap(A, 60)  # guidance
        o0 = live(e)
        m = e.bp_mark()
        e.move_to(0, 0)
        e.tap(A, 24)
        o1 = live(e)
        bps = parse_bp(e.bp_lines(m))
        checks.append({'name': 'original 1-key control: ア appended via native S1/AE00', 'ok': o0[0x61] == 0 and o1[0x61] == 1 and o1[0x2C:0x2E] == bytes.fromhex('8341')
                       and 'S1' in [b['name'] for b in bps] and 'AE00_append' in [b['name'] for b in bps] and 'tramp_press' not in [b['name'] for b in bps],
                       'live': o1[0x2C:0x3C].hex(), 'bp': [b['name'] for b in bps if b['name'] not in ('A3_copy', 'rowdraw', 'RET_B428')]})
        e.shot('one-a')
        for _ in range(6):
            e.tap(A, 24)
        e.move_to(0, 1)
        e.tap(A, 24)
        o = live(e)
        e.shot('kana8')
        checks.append({'name': 'original ア×7カ typed', 'ok': o[0x2C:0x3C] == KANA and o[0x61] == 8, 'live': o[0x2C:0x3C].hex()})
        e.tap(START, 120); e.shot('confirm-question')
        e.tap(A, 180); e.shot('confirm-after-yes')
        dest = e.mem(0x0200B09C, 16, 'destination.bin')
        checks.append({'name': 'original destination', 'ok': dest == KANA, 'dest': dest.hex()})
        save_slot1(e, False)
        s = e.dumpsave('original-kana.sav')
        hits = find_all(s.read_bytes(), KANA)
        notes.append({'save_sha256': sha(s), 'offsets': [hex(h) for h in hits]})
        checks.append({'name': 'original save has ア×7カ', 'ok': bool(hits)})
        reenter_name(e)
        o = live(e)
        checks.append({'name': 'original re-entry name', 'ok': o[0x2C:0x3C] == KANA, 'live': o[0x2C:0x3C].hex()})
        rows = apply_seq(e, 'orig')
        notes.append({'sequence': rows})
    finally:
        e.close()
    res = {'case': 'case14-original', 'pass': all(c['ok'] for c in checks), 'checks': checks, 'notes': notes, 'run': str(e.d.relative_to(R))}
    (e.d / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print('case14-original', 'PASS' if res['pass'] else 'FAIL', json.dumps(checks, ensure_ascii=False)[:900], flush=True)
    return res, e.d / 'original-kana.sav', rows

def candidate_legacy(savefile, ref_rows):
    e = Emu('case13b-candidate-legacy-kana', 'candidate', save=savefile, bps=BPS_ALL)
    checks = []
    try:
        for x in route('legacy-cold-to-editor.route'):
            e.cmd(x)
        e.shot('editor-loaded')
        reenter_name(e)
        o = live(e)
        checks.append({'name': 'candidate legacy re-entry ア×7カ len8 active0', 'ok': o[0x2C:0x3C] == KANA and o[0x61] == 8 and o[0x70] == 0, 'live': o[0x2C:0x3C].hex()})
        rows = apply_seq(e, 'cand')
        for a, b in zip(rows, ref_rows):
            checks.append({'name': f"legacy kana {a['input']} == original", 'ok': a['live16'] == b['live16'] and a['len'] == b['len'] and a['sounds'] == b['sounds'],
                           'candidate': a, 'original': b})
        checks.append({'name': 'dakuten actually converted カ->ガ (not a no-op comparison)', 'ok': rows[0]['live16'][28:32] == '834b', 'live': rows[0]['live16']})
    finally:
        e.close()
    res = {'case': 'case13b-candidate-legacy-kana', 'pass': all(c['ok'] for c in checks), 'checks': checks, 'run': str(e.d.relative_to(R))}
    (e.d / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print('case13b', 'PASS' if res['pass'] else 'FAIL', json.dumps(checks, ensure_ascii=False)[:1500], flush=True)
    return res

if __name__ == '__main__':
    res, sav, rows = original_control()
    if sav.exists():
        candidate_legacy(sav, rows)
