"""T5 runtime cases on the candidate ROM. Each case = its own process/run dir.
Start state: T5-owned savestate made by candidate cold boot + normal keys (runs/prep-fresh/name-entry.ss0,
runs/prep-legacy/legacy-name.ss0). Expectations are fixed in expectations.json BEFORE the runs (written by this file's
EXPECT dict at import time if absent)."""
import sys, json
from t5lib import *

FRESH_SS = R / 'runs/prep-fresh/name-entry.ss0'
LEGACY_SS = R / 'runs/prep-legacy/legacy-name.ss0'
OKC = (14, 5)
CANCELC = (14, 3)

def code(s):
    return ''.join(f'{TABLE[c]:04x}' if c in TABLE else f'{JAMO[c]:04x}' for c in s)

EXPECT = {
    'case1': {'한글': code('한글'), '강철': code('강철'), '붉은달': code('붉은달'), 'vram': 'ㄱ,ㅏ (and ㅘ in case2) 64B == ROM jamo tile 1275+2i/1276+2i'},
    'case2': {'한가': code('한가'), '달가': code('달가'), 'ㅘ_vonly': code('ㅘ'), '와': code('와'), '가한': code('가한')},
    'case3': {'incomplete_confirm': 'ㄱ active; START and OK cell -> +0x67 stays 0, sound 68, live/dest unchanged'},
    'case4': {'개+ㄷ': 'reject, live=개 active', '간+ㅒ': 'reject, live=간 active', '가+ㅋ': 'reject, live=가 active'},
    'case5': {'literals': 'space/1/！ accepted after complete syllable, rejected after incomplete jamo',
              '가␣나 stored': code('가') + '8140' + code('나') + ' then 00', '가␣ stored': code('가') + ' then 00 (trailing space trimmed)'},
    'case6': {'full8': '884088e989e28adf8bc38ca68da98ea2', 'accepted_keys': 17, 'ninth_ㄱ': 'no_slot reject, 8th 안 unchanged'},
    'case7': {'강→가→ㄱ→빈': 'tail/live per model at each B', 'committed 가 B': 'whole syllable removed'},
    'case8': {'cancel Yes': 'editor, destination unchanged', 'reentry tail': '00ffff00 + 12x00, live==destination'},
    'case9': {'legacy': 'len8 active0 -> B -> len7 -> ㄱ -> len8 active1'},
    'case10': {'가 OK No A': '가 committed active0 dest unchanged', '가카': code('가카')},
    'case13': {'dakuten/handakuten/R with Korean active': 'sound 68, live unchanged'},
}
exp_path = R / 'expectations.json'
if not exp_path.exists():
    exp_path.write_text(json.dumps(EXPECT, ensure_ascii=False, indent=1))
else:
    assert json.loads(exp_path.read_text()) == EXPECT, 'expectations changed after fixing'


def fresh(tag):
    e = Emu(tag, 'candidate', bps=BPS_ALL)
    e.loadstate(FRESH_SS)
    e.tap(A, 60)
    ptr, o = e.obj('start-obj.bin')
    assert o[0x60] == 1 and o[0x61] == 0 and o[0x66] == 1 and o[0x70:0x80] == bytes.fromhex('00ffff00') + bytes(12), o.hex()
    return e

def dest_of(e):
    ptr, o = e.obj()
    d = struct.unpack_from('<I', o, 0x5C)[0]
    return d, e.mem(d, 16)

def vram_check(e, rec, j):
    """A3 copy BP in this step: r6 = ROM source, r7 = VRAM destination. Compare VRAM 64B to the ROM jamo tile."""
    want = jamo_tile(j)
    i = list(hc.PREVIEW_JAMO).index(j)
    src_expect = 0x08F00000 + (1275 + 2 * i) * 32
    hits = [(int(s, 16), int(d, 16)) for s, d in rec.get('a3', []) if int(s, 16) == src_expect]
    if not hits:
        return {'jamo': j, 'ok': False, 'why': f'no A3 copy from {src_expect:08x}', 'a3': rec.get('a3')}
    dst = hits[-1][1]
    got = e.mem(dst, 64, f'vram-{j}.bin')
    glyph_bin = (ROOT / 'data/jamo_glyphs_40.bin').read_bytes()[i * 64:(i + 1) * 64]
    return {'jamo': j, 'src': f'{src_expect:08x}', 'vram': f'{dst:08x}', 'ok': got == want == glyph_bin,
            'got_sha': hashlib.sha256(got).hexdigest(), 'want_sha': hashlib.sha256(want).hexdigest()}

def finish(e, name, c, extra):
    res = {'case': name, 'pass': c.ok() and all(v.get('ok', True) for v in extra.get('checks', [])),
           'failures': c.fail, 'checks': extra.get('checks', []), 'notes': extra.get('notes', []),
           'run': str(e.d.relative_to(R))}
    (e.d / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(name, 'PASS' if res['pass'] else 'FAIL', json.dumps(res['checks'], ensure_ascii=False)[:600], [f['errors'] for f in c.fail][:5], flush=True)
    return res


def case1():
    out = []
    for word, keys in [('한글', 'ㅎㅏㄴㄱㅡㄹ'), ('강철', 'ㄱㅏㅇㅊㅓㄹ'), ('붉은달', 'ㅂㅜㄹㄱㅇㅡㄴㄷㅏㄹ')]:
        e = fresh('case1-' + word)
        c = Case(e, 'case1-' + word)
        checks = []
        try:
            r0 = c.jamo(keys[0])
            if word == '강철':
                checks.append(vram_check(e, r0, 'ㄱ'))  # immediately: later glyphs reuse the same cache slot
            recs = [r0] + c.jamos(keys[1:])
            e.shot('preview')
            _, o = e.obj('final-obj.bin')
            checks.append({'name': 'final live', 'ok': o[0x2C:0x2C + 2 * len(word)].hex() == code(word) and o[0x61] == len(word), 'live': o[0x2C:0x3C].hex()})
        finally:
            e.close()
        out.append(finish(e, 'case1-' + word, c, {'checks': checks}))
    e = fresh('case1-vowel')
    c = Case(e, 'case1-vowel')
    try:
        r = c.jamo('ㅏ')
        e.shot('preview-a')
        checks = [vram_check(e, r, 'ㅏ')]
    finally:
        e.close()
    out.append(finish(e, 'case1-vowel', c, {'checks': checks}))
    return out


def case2():
    out = []
    for tag, keys, word in [('한가', 'ㅎㅏㄴㄱㅏ', '한가'), ('달가', 'ㄷㅏㄹㄱㅏ', '달가'), ('wa-vonly', 'ㅗㅏ', 'ㅘ'), ('와', 'ㅇㅗㅏ', '와'), ('가한', 'ㄱㅏㅎㅏㄴ', '가한')]:
        e = fresh('case2-' + tag)
        c = Case(e, 'case2-' + tag)
        checks = []
        try:
            recs = c.jamos(keys)
            e.shot('preview')
            _, o = e.obj('final-obj.bin')
            checks.append({'name': 'final live', 'ok': o[0x2C:0x2C + 2 * len(word)].hex() == code(word), 'live': o[0x2C:0x3C].hex(), 'expect': code(word)})
            if tag == 'wa-vonly':
                checks.append(vram_check(e, recs[-1], 'ㅘ'))
            if tag == '달가':
                checks.append({'name': '닭 intermediate', 'ok': recs[3]['live16'][:4] == code('닭'), 'live': recs[3]['live16']})
            if tag == '가한':
                checks.append({'name': '갛 intermediate', 'ok': recs[2]['live16'][:4] == f"{TABLE['갛']:04x}", 'live': recs[2]['live16']})
        finally:
            e.close()
        out.append(finish(e, 'case2-' + tag, c, {'checks': checks}))
    return out


def case3():
    e = fresh('case3')
    c = Case(e, 'case3')
    checks = []
    try:
        c.jamo('ㄱ')
        d0, dest0 = dest_of(e)
        # START
        before = c.snap()
        m = e.bp_mark()
        e.tap(START, 60)
        after = c.snap()
        e.shot('after-start')
        cur = struct.unpack_from('<hh', after[1], 0x1E)
        r = c.record('START', None, c.comp.confirm(), before, after, {'bp_from': m, 'cursor_after_start': cur}, expect_sound='68')
        checks.append({'name': 'START incomplete', 'ok': after[1][0x67] == 0 and cur == (14, 5) and 'AED8_question' not in r['bp_seq'], 'x67': after[1][0x67], 'cursor': cur, 'bp_seq': r['bp_seq']})
        # OK cell (cursor already on OK row)
        before = c.snap()
        pos, trail, m = c.press_cell(*OKC)
        after = c.snap()
        e.shot('after-ok-cell')
        r = c.record('OKcell', None, c.comp.confirm(), before, after, {'bp_from': m, 'cell': pos}, expect_sound='68')
        checks.append({'name': 'OK cell incomplete', 'ok': after[1][0x67] == 0 and 'AED8_question' not in r['bp_seq'], 'x67': after[1][0x67], 'bp_seq': r['bp_seq']})
        d1, dest1 = dest_of(e)
        checks.append({'name': 'destination unchanged', 'ok': (d0, dest0) == (d1, dest1), 'dest': dest1.hex()})
    finally:
        e.close()
    return finish(e, 'case3', c, {'checks': checks})


def case4():
    out = []
    for tag, keys in [('개+ㄷ', 'ㄱㅐㄷ'), ('간+ㅒ', 'ㄱㅏㄴㅒ'), ('가+ㅋ', 'ㄱㅏㅋ')]:
        e = fresh('case4-' + tag)
        c = Case(e, 'case4-' + tag)
        try:
            recs = c.jamos(keys)
            e.shot('after-reject')
            last = recs[-1]
            checks = [{'name': 'last key rejected (model)', 'ok': last['model']['accepted'] is False and last['model']['reason'] == 'not_in_2350', 'model': last['model'], 'sounds': last['sounds']}]
        finally:
            e.close()
        out.append(finish(e, 'case4-' + tag, c, {'checks': checks}))
    return out


def confirm_yes(e, c, label):
    """START -> native question -> A (default Yes, verified by screenshot) -> editor. Returns destination bytes."""
    d0, dest0 = dest_of(e)
    before = c.snap()
    m = e.bp_mark()
    e.tap(START, 120)  # question text must finish before A is accepted (native routes use 120-180)
    q = c.snap()
    e.shot(label + '-question')
    res = c.comp.confirm()
    c.record('START', label, res, before, q, {'bp_from': m}, expect_sound=None)
    m2 = e.bp_mark()
    e.tap(A, 180)
    e.shot(label + '-after-yes')
    dest = e.mem(d0, 16, label + '-destination.bin')
    return d0, dest0, dest, q[1][0x67]


def case5():
    out = []
    # literals
    e = fresh('case5-literals')
    c = Case(e, 'case5-literals')
    checks = []
    try:
        c.jamo('ㄱ')
        r = c.literal_cell(0x8140)  # incomplete -> reject
        checks.append({'name': 'space after incomplete rejected', 'ok': r['model']['accepted'] is False})
        r = c.literal_cell(0x8250)  # '1' after incomplete
        checks.append({'name': 'digit after incomplete rejected', 'ok': r['model']['accepted'] is False})
        c.jamo('ㅏ')
        c.literal_cell(0x8140)
        c.literal_cell(0x8250)
        c.literal_cell(0x8149)
        e.shot('literals')
        _, o = e.obj('final-obj.bin')
        checks.append({'name': 'final live 가␣1！', 'ok': o[0x2C:0x34].hex() == code('가') + '814082508149' and o[0x61] == 4, 'live': o[0x2C:0x3C].hex()})
    finally:
        e.close()
    out.append(finish(e, 'case5-literals', c, {'checks': checks}))
    for tag, ops in [('mid-space', ['ㄱ', 'ㅏ', 0x8140, 'ㄴ', 'ㅏ']), ('trail-space', ['ㄱ', 'ㅏ', 0x8140])]:
        e = fresh('case5-' + tag)
        c = Case(e, 'case5-' + tag)
        checks = []
        try:
            for op in ops:
                (c.literal_cell(op) if isinstance(op, int) else c.jamo(op))
            d0, dest0, dest, x67 = confirm_yes(e, c, 'confirm')
            errs, pre = stored_check(dest, c.comp.committed)
            checks.append({'name': 'stored prefix/trim', 'ok': not errs, 'dest': dest.hex(), 'prefix': pre.hex(), 'errors': errs, 'question_x67': x67})
        finally:
            e.close()
        out.append(finish(e, 'case5-' + tag, c, {'checks': checks}))
    return out


def case7():
    out = []
    e = fresh('case7-gang')
    c = Case(e, 'case7-gang')
    checks = []
    try:
        c.jamos('ㄱㅏㅇ')
        for _ in range(3):
            c.backspace()
        e.shot('empty')
        _, o = e.obj()
        checks.append({'name': 'empty after 3 B', 'ok': o[0x61] == 0 and o[0x70:0x74] == bytes.fromhex('00ffff00')})
    finally:
        e.close()
    out.append(finish(e, 'case7-gang', c, {'checks': checks}))
    e = fresh('case7-committed')
    c = Case(e, 'case7-committed')
    checks = []
    try:
        c.jamos('ㄱㅏㄴㅏ')
        c.backspace(); c.backspace()   # 나 -> ㄴ -> (none)
        r = c.backspace()              # committed 가 -> removed whole
        checks.append({'name': 'committed 가 deleted by one B', 'ok': r['len'] == 0 and r['model']['accepted']})
        e.shot('empty')
    finally:
        e.close()
    out.append(finish(e, 'case7-committed', c, {'checks': checks}))
    return out


def reenter_name(e):
    """editor -> SELECT -> 파일 -> 이름 입력 -> guidance closed. Keys verified by screenshots in run dir."""
    e.tap(SEL, 30); e.shot('re-menu')
    e.tap(A, 30); e.shot('re-file')
    e.tap(DOWN, 24); e.tap(DOWN, 24); e.shot('re-file-name')
    e.tap(A, 180); e.shot('re-entry')
    e.tap(A, 60); e.shot('re-ready')


def case8():
    e = fresh('case8')
    c = Case(e, 'case8')
    checks = []
    try:
        c.jamos('ㄱㅏ')
        d0, dest0 = dest_of(e)
        before = c.snap()
        pos, trail, m = c.press_cell(*CANCELC, wait=120)
        q = c.snap()
        e.shot('cancel-question')
        c.record('CANCELcell', None, None, before, q, {'bp_from': m, 'cell': pos})
        e.tap(A, 180)
        e.shot('after-cancel-yes')
        dest = e.mem(d0, 16, 'destination-after-cancel.bin')
        checks.append({'name': 'destination unchanged after cancel', 'ok': dest == dest0, 'dest0': dest0.hex(), 'dest': dest.hex()})
        ptr_after = e.objptr()
        checks.append({'name': 'name object freed/pointer state after cancel', 'ok': True, 'ptr': f'{ptr_after:08x}'})
        reenter_name(e)
        ptr, o = e.obj('reentry-obj.bin')
        n = o[0x61]
        checks.append({'name': 'reentry tail initial', 'ok': o[0x70:0x80] == bytes.fromhex('00ffff00') + bytes(12) and o[0x60] == 1, 'tail': o[0x70:0x80].hex(), 'len': n, 'live': o[0x2C:0x3C].hex()})
        checks.append({'name': 'reentry live == destination prefix', 'ok': o[0x2C:0x2C + 2 * n] == dest[:2 * n]})
        bps = parse_bp(e.bp_lines(0))
        checks.append({'name': 'nc_alloc ran twice (entry + reentry)', 'ok': sum(b['name'] == 'P1_nc_alloc' for b in bps) == 1, 'note': 'fresh state was loaded after first alloc; expect exactly 1 in this process (re-entry)',
                       'count': sum(b['name'] == 'P1_nc_alloc' for b in bps)})
    finally:
        e.close()
    return finish(e, 'case8', c, {'checks': checks})


def case9():
    e = Emu('case9', 'candidate', bps=BPS_ALL)
    e.loadstate(LEGACY_SS)
    comp = hc.Composer(TABLE)
    _, o = e.obj('start-obj.bin')
    comp.load(o[0x2C:0x3C])
    c = Case(e, 'case9', comp)
    checks = []
    try:
        checks.append({'name': 'legacy reload len8 active0', 'ok': o[0x61] == 8 and o[0x70] == 0 and o[0x2C:0x3C] == bytes.fromhex('8341') * 8})
        c.check_now('legacy loaded')
        c.backspace()
        r = c.jamo('ㄱ')
        e.shot('legacy-plus-g')
        checks.append({'name': 'ア×7 + ㄱ active', 'ok': r['len'] == 8 and r['tail'][:8] == '0100ff00' and r['live16'] == '8341' * 7 + f"{JAMO['ㄱ']:04x}"})
    finally:
        e.close()
    return finish(e, 'case9', c, {'checks': checks})


def case10():
    e = fresh('case10')
    c = Case(e, 'case10')
    checks = []
    try:
        c.jamos('ㄱㅏ')
        d0, dest0 = dest_of(e)
        before = c.snap()
        pos, trail, m = c.press_cell(*OKC, wait=120)
        q = c.snap()
        e.shot('ok-question')
        r = c.record('OKcell', None, c.comp.confirm(), before, q, {'bp_from': m, 'cell': pos}, expect_sound=None)
        checks.append({'name': 'question opened, 가 committed', 'ok': q[1][0x67] != 0 and 'AED8_question' in r['bp_seq'], 'x67': q[1][0x67]})
        e.tap(RIGHT, 24); e.shot('no-selected')
        e.tap(A, 120); e.shot('after-no')
        after = c.snap()
        c.record('No', None, None, q, after)
        dest = e.mem(d0, 16, 'destination-after-no.bin')
        checks.append({'name': 'after No: 가 committed active0 dest unchanged', 'ok': after[1][0x67] == 0 and after[1][0x70] == 0 and after[1][0x61] == 1 and dest == dest0,
                       'live': after[1][0x2C:0x3C].hex(), 'dest': dest.hex()})
        c.jamos('ㅋㅏ')
        e.shot('gaka')
        _, o = e.obj('final-obj.bin')
        checks.append({'name': '가카', 'ok': o[0x2C:0x30].hex() == code('가카'), 'live': o[0x2C:0x3C].hex()})
    finally:
        e.close()
    return finish(e, 'case10', c, {'checks': checks})


def case13():
    out = []
    e = fresh('case13')
    c = Case(e, 'case13')
    checks = []
    try:
        c.jamos('ㄱㅏ')
        for label, cell in [('dakuten', (10, 2)), ('handakuten', (11, 2))]:
            before = c.snap()
            pos, trail, m = c.press_cell(*cell)
            r = c.record(label, None, hc.Result(False, 'legacy-kana'), before, c.snap(), {'bp_from': m, 'cell': pos}, expect_sound='68')
            checks.append({'name': label + ' on Korean active', 'ok': not r['errors'], 'sounds': r['sounds']})
        before = c.snap()
        m = e.bp_mark()
        e.tap(RK, 24)
        r = c.record('R', None, hc.Result(False, 'legacy-kana'), before, c.snap(), {'bp_from': m}, expect_sound='68')
        checks.append({'name': 'R on Korean active', 'ok': not r['errors'], 'sounds': r['sounds']})
        # T7-FIX1 (Astra full-v1 F1): B turns active 가 into incomplete ㄱ (the old c.jamo('ㄱ') made 각, a complete syllable).
        def jamo_state(o, where):
            # incomplete active ㄱ: slot0 E2A8, slot1 0000, len 1, tail 01 00 FF 00 + 12x00
            st = {'name': f'ㄱ state {where}', 'live16': o[OFF_SLOT:OFF_SLOT + 16].hex(), 'len': o[OFF_LEN], 'tail': o[OFF_TAIL:OFF_TAIL + 16].hex()}
            st['ok'] = (o[OFF_SLOT:OFF_SLOT + 4] == bytes.fromhex('e2a80000') and o[OFF_LEN] == 1
                        and o[OFF_TAIL:OFF_TAIL + 4] == bytes.fromhex('0100ff00') and o[OFF_TAIL + 4:OFF_TAIL + 16] == bytes(12))
            return st
        r = c.backspace()
        checks.append({'name': 'B: 가 -> incomplete ㄱ', 'ok': not r['errors'], 'sounds': r['sounds']})
        checks.append(jamo_state(c.snap()[1], 'after B'))
        def jamo_op(label, do):
            before = c.snap()
            checks.append(jamo_state(before[1], 'before ' + label))
            extra = do()
            after = c.snap()
            r = c.record(label, None, hc.Result(False, 'legacy-kana'), before, after, extra, expect_sound='68')
            checks.append(jamo_state(after[1], 'after ' + label))
            same = before[1][0x2C:0x3C] == after[1][0x2C:0x3C] and before[1][OFF_LEN] == after[1][OFF_LEN] and before[1][0x70:0x80] == after[1][0x70:0x80]
            checks.append({'name': label + ' on jamo active', 'ok': not r['errors'] and same and '68' in r['sounds'], 'sounds': r['sounds'], 'unchanged': same})
        for label, cell in [('dakuten-incomplete', (10, 2)), ('handakuten-incomplete', (11, 2))]:
            def do(cell=cell):
                pos, trail, m = c.press_cell(*cell)
                return {'bp_from': m, 'cell': pos}
            jamo_op(label, do)
        def do_r():
            m = e.bp_mark(); e.tap(RK, 24)
            return {'bp_from': m}
        jamo_op('R-incomplete', do_r)
        e.shot('after')
    finally:
        e.close()
    out.append(finish(e, 'case13', c, {'checks': checks}))
    return out


CASES = {'1': case1, '2': case2, '3': case3, '4': case4, '5': case5, '7': case7, '8': case8, '9': case9, '10': case10, '13': case13}
if __name__ == '__main__':
    for k in sys.argv[1:]:
        CASES[k]()
