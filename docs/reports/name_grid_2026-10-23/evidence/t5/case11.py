"""Case 6 + 11: full8 by actual grid keys from power-on (no loadstate, no RAM writes), native confirm, native save,
dumpsave (O_EXCL), then a separate cold-boot process that reads only that cartridge save.
  11a: blank cartridge -> fresh route -> name -> full8 -> save to empty slot 1
  11b: T5 copy of new-eight.sav (ア×8 in slot 1) -> load map -> name re-entry -> B×8 -> full8 -> save slot 1 -> overwrite Yes
"""
import sys, json
from t5lib import *
from cases import confirm_yes, dest_of, finish

FULL8_KEYS = 'ㄱㅏㄴㅏㄷㅏㄹㅏㅁㅏㅂㅏㅅㅏㅇㅏㄴ'
FULL8 = bytes.fromhex('884088e989e28adf8bc38ca68da98ea2')
assert len(FULL8_KEYS) == 17

def route(name):
    t = (R / 'routes' / name).read_text().split()
    return [' '.join(t[i:i + 2]) for i in range(0, len(t), 2)]

def type_full8(e, c, checks, comp_loaded=False):
    recs = c.jamos(FULL8_KEYS)
    acc = sum(1 for r in recs if r['model']['accepted'])
    e.shot('full8')
    _, o = e.obj('full8-obj.bin')
    checks.append({'name': 'case6 17 keys accepted', 'ok': acc == 17 and all(r['sounds'] == ['65'] for r in recs), 'accepted': acc})
    checks.append({'name': 'case6 8th 아->안 edit (active 8th)', 'ok': recs[-2]['live16'][28:32] == f"{TABLE['아']:04x}" and recs[-1]['live16'][28:32] == f"{TABLE['안']:04x}" and recs[-1]['len'] == 8 and recs[-1]['tail'][:2] == '01'})
    r9 = c.jamo('ㄱ')
    _, o9 = e.obj('ninth-obj.bin')
    checks.append({'name': 'case6 9th ㄱ no_slot reject, 8th not overwritten', 'ok': r9['model']['reason'] == 'no_slot' and r9['sounds'] == ['68'] and o9[0x2C:0x3C] == FULL8 and o9[0x61] == 8, 'live': o9[0x2C:0x3C].hex()})
    d0, dest0, dest, x67 = confirm_yes(e, c, 'confirm')
    checks.append({'name': 'case6 stored 16B', 'ok': dest == FULL8, 'dest': dest.hex(), 'question_x67': x67})
    return d0

def save_slot1(e, overwrite):
    """editor -> SELECT -> 파일 -> 세이브 -> slot 1 -> (overwrite) Yes. Screens recorded; outcome judged from SRAM."""
    e.tap(SEL, 30); e.shot('sv-menu')
    e.tap(A, 30); e.shot('sv-file')
    e.tap(DOWN, 24); e.shot('sv-file-save')
    e.tap(A, 120); e.shot('sv-list')
    e.tap(A, 120); e.shot('sv-confirm')
    e.tap(LEFT, 24); e.shot('sv-yes-selected')
    e.tap(A, 240); e.shot('sv-done')

def find_all(b, pat):
    out, i = [], b.find(pat)
    while i >= 0:
        out.append(i); i = b.find(pat, i + 1)
    return out

def make_save(variant):
    tag = f'case11{variant}-save'
    if variant == 'a':
        e = Emu(tag, 'candidate', bps=BPS_ALL)
        pre = route('candidate-fresh-to-name.route')
    else:
        e = Emu(tag, 'candidate', save=EIGHT_SAV, bps=BPS_ALL)
        pre = route('legacy-cold-to-editor.route')
    c = Case(e, tag)
    checks, notes = [], []
    try:
        for x in pre:
            e.cmd(x)
        if variant == 'a':
            e.tap(A, 60)  # close guidance
        else:
            e.shot('editor-loaded')
            from cases import reenter_name
            reenter_name(e)
            _, o = e.obj('reentry-obj.bin')
            assert o[0x2C:0x3C] == bytes.fromhex('8341') * 8 and o[0x61] == 8, o.hex()
            c.comp.load(o[0x2C:0x3C])
            for _ in range(8):
                c.backspace()
        _, o = e.obj('start-obj.bin')
        checks.append({'name': 'name screen ready, empty', 'ok': o[0x61] == 0 and o[0x60] == 1 and o[0x66] == 1})
        type_full8(e, c, checks)
        save_slot1(e, variant == 'b')
        s = e.dumpsave(f'case11{variant}.sav')
        b = s.read_bytes()
        hits = find_all(b, FULL8)
        notes.append({'save_sha256': sha(s), 'size': len(b), 'full8_offsets': [hex(h) for h in hits]})
        if variant == 'b':
            old = (e.save_in).read_bytes()
            notes.append({'input_ア8_offsets': [hex(h) for h in find_all(old, bytes.fromhex('8341') * 8)],
                          'output_ア8_offsets': [hex(h) for h in find_all(b, bytes.fromhex('8341') * 8)],
                          'changed_ranges_count': sum(1 for i in range(len(b)) if b[i] != old[i])})
        checks.append({'name': 'case11 full8 pattern present in exported cartridge save', 'ok': bool(hits), 'offsets': [hex(h) for h in hits]})
        cmds = [json.loads(l)['command'] for l in (e.d / 'commands.jsonl').read_text().splitlines()]
        checks.append({'name': 'no loadstate/w8/w16 in save run', 'ok': not any(x.startswith(('loadstate', 'w8', 'w16')) for x in cmds)})
    finally:
        e.close()
    return finish(e, tag, c, {'checks': checks, 'notes': notes}), e.d / f'case11{variant}.sav'

def cold(variant, savefile):
    tag = f'case11{variant}-cold'
    e = Emu(tag, 'candidate', save=savefile, bps=BPS_ALL)
    c = Case(e, tag)
    checks, notes = [], []
    try:
        lines = [l for l in (B / 'native-re/replay-cold/route.txt').read_text().splitlines()]
        last_a = [i for i, l in enumerate(lines) if l == 'keys 1'][-1]
        for i, l in enumerate(lines):
            if l.startswith('shot '):
                e.shot(l.split()[1])
                if l.split()[1] == 'cold-list':
                    lst = e.mem(0x0200B204, 16, 'list-name-0200B204.bin')
                    checks.append({'name': 'cold load list name string 16B', 'ok': lst == FULL8, 'got': lst.hex()})
                continue
            if l.startswith(('dump', 'quit')):
                continue
            if i == last_a:
                # name re-entry reached, guidance closed: read before the route's final A (which presses ㄱ at 8 chars)
                _, o = e.obj('reentry-obj.bin')
                checks.append({'name': 'cold name re-entry live 16B/len8/active0', 'ok': o[0x2C:0x3C] == FULL8 and o[0x61] == 8 and o[0x70:0x74] == bytes.fromhex('00ffff00'), 'live': o[0x2C:0x3C].hex(), 'len': o[0x61], 'tail': o[0x70:0x80].hex()})
                d = struct.unpack_from('<I', o, 0x5C)[0]
                dest = e.mem(d, 16, 'reentry-destination.bin')
                checks.append({'name': 'cold destination 16B', 'ok': dest == FULL8, 'dest': dest.hex(), 'dest_addr': f'{d:08x}'})
                e.shot('reentry')
                c.comp.load(o[0x2C:0x3C])
                before = c.snap(); m = e.bp_mark()
            e.cmd(l)
        after = c.snap()
        r = c.record('jamo', 'ㄱ (route final A at 8 chars)', c.comp.press('ㄱ'), before, after, {'bp_from': m})
        checks.append({'name': 'final A at 8 committed rejected (no_slot), unchanged', 'ok': not r['errors'] and r['model']['reason'] == 'no_slot'})
        e.shot('reentry-after-a')
        cmds = [json.loads(l)['command'] for l in (e.d / 'commands.jsonl').read_text().splitlines()]
        checks.append({'name': 'cold run: no loadstate/w8/w16', 'ok': not any(x.startswith(('loadstate', 'w8', 'w16')) for x in cmds)})
    finally:
        e.close()
    return finish(e, tag, c, {'checks': checks, 'notes': notes})

if __name__ == '__main__':
    for v in sys.argv[1:]:
        res, sav = make_save(v)
        if sav.exists():
            cold(v, sav)
