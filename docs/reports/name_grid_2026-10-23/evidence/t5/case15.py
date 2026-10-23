"""Case 15: hook entry/return register & stack contracts from real breakpoints on the candidate ROM.
- contract checker over every candidate run's bp.log (accept/reject/backspace/confirm/alloc/D1 mode1 from normal-key runs)
- pending-constructor state (alloc done, constructor not yet run) captured by frame stepping from normal keys
- D1 mode1 with rw watch on the rowdraw stack-argument words
- SYNTHETIC mode0 probe: same pending state, RAM obj+0x60 := 0 (explicitly synthetic), then D1/S1/S3/S2 mode0 paths
"""
import json, sys, re as _re
from t5lib import *
from cases import FRESH_SS, CANCELC

BP_NAMES[0x083162A2] = 'P1_caller_ret'
BPS15 = sorted(BP_NAMES)
ROW_PRIV = [0x08F7613C, 0x08F76160, 0x08F76184, 0x08F761A8, 0x08F761C0, 0x08F761D8]
ROWDRAW_FN = 0x08314EB1
R4_WORD = struct.unpack_from('<I', crom(), 0x814FB0)[0]
NATIVE_ROW_TABLE = 0x0883FE40
CALLEE = ['r4', 'r5', 'r6', 'r7', 'r8', 'r9', 'r10', 'r11', 'sp', 'lr']
TRAMP = {'S1': 'tramp_press', 'S2': 'tramp_confirm', 'S3': 'tramp_backspace', 'D1': 'tramp_display'}
CFN = {'S1': ('nc_press', 'ret_nc_press'), 'S2': ('nc_confirm', 'ret_nc_confirm'), 'S3': ('nc_backspace', 'ret_nc_backspace')}
RETS = {'S1': {'RET_B428': 1, 'RET_B0C6': 0}, 'S2': {'RET_B428': None}, 'S3': {'RET_B21A': None}, 'D1': {'RET_ABA2': 1, 'RET_AB44': 0}}


def find(bps, i, names, stop=('S1', 'S2', 'S3', 'D1', 'P1_nc_alloc')):
    for j in range(i + 1, len(bps)):
        if bps[j]['name'] in names:
            return j
        if bps[j]['name'] in stop:
            return None
    return None


def check_log(bps, obj_ptr=None):
    events, errors = [], []
    for i, b in enumerate(bps):
        site = b['name']
        if site in TRAMP:
            ev = {'site': site, 'n': b['n'], 'checks': {}}
            ok = ev['checks']
            jt = find(bps, i, {TRAMP[site]})
            if jt is None:
                errors.append((site, b['n'], 'no trampoline')); continue
            t = bps[jt]
            ok['tramp_regs_equal'] = all(t[k] == b[k] for k in CALLEE + ['r1', 'r2'] if not (site == 'D1' and k == 'r3'))
            jr = find(bps, jt, set(RETS[site]))
            if jr is None:
                errors.append((site, b['n'], 'no return')); continue
            r = bps[jr]
            ev['ret'] = r['name']
            ev['mode'] = RETS[site][r['name']]
            if site in CFN:
                jc = find(bps, jt, {CFN[site][0]})
                if jc is not None and jc < jr:
                    c = bps[jc]
                    ev['mode'] = 1
                    ok['C_entry_sp_mod8'] = c['sp'] % 8 == 0
                    ok['C_entry_r0_obj'] = obj_ptr is None or c['r0'] == obj_ptr
                    ev['c_sp'] = f"{c['sp']:08x}"
                    ev['cell'] = f"{c['r1'] & 0xFFFF:04x}" if site == 'S1' else None
                    jcr = find(bps, jc, {CFN[site][1]})
                    if jcr is not None:
                        ev['c_ret'] = bps[jcr]['r0']
                        ok['C_ret_sp_same'] = bps[jcr]['sp'] == c['sp']
                        ok['C_ret_r0_in_01'] = bps[jcr]['r0'] in (0, 1)
                    else:
                        ok['C_ret_seen'] = False
                    if site == 'S2' and ev.get('c_ret') == 0:
                        ok['S2_accept_calls_AED8'] = find(bps, jcr, {'AED8_question'}) is not None
                else:
                    ev['mode'] = 0 if ev['mode'] is None else ev['mode']
                    if site == 'S1':
                        ok['mode0_calls_AE00'] = find(bps, jt, {'AE00_append'}) is not None
                    ev['cell'] = None
                ok['ret_mode_consistent'] = RETS[site][r['name']] in (None, ev['mode'])
            if site == 'D1':
                rows = [bps[k] for k in range(jt + 1, jr) if bps[k]['name'] == 'rowdraw' and 0x08F75800 <= bps[k]['lr'] < 0x08F77800]
                ev['rowdraw_calls'] = len(rows)
                if ev['mode'] == 1:
                    ok['six_rowdraw'] = len(rows) == 6
                    for k, rw in enumerate(rows):
                        ok[f'row{k}_args'] = (rw['r0'] == 6 and rw['r1'] == 6 + 2 * k and rw['r2'] == R4_WORD and rw['r3'] == ROW_PRIV[k]
                                              and rw['r3'] != ROWDRAW_FN and rw['r7'] == ROWDRAW_FN and rw['sp'] == b['sp'] - 16)
                    ev['rowdraw_sp'] = f"{rows[0]['sp']:08x}" if rows else None
                    ok['ret_r5_0_r6_8000'] = r['r5'] == 0 and r['r6'] == 0x8000
                    ok['ret_callee_equal'] = all(r[k] == b[k] for k in ['r4', 'r7', 'r8', 'r9', 'r10', 'r11', 'sp', 'lr'])
                else:
                    ok['no_private_rowdraw'] = len(rows) == 0
                    ok['ret_r2_r3_r6'] = r['r2'] == R4_WORD and r['r3'] == NATIVE_ROW_TABLE and r['r6'] == 0x8000
                    ok['ret_callee_equal'] = all(r[k] == b[k] for k in ['r4', 'r5', 'r7', 'r8', 'r9', 'r10', 'r11', 'sp', 'lr'])
            else:
                ok['ret_callee_equal'] = all(r[k] == b[k] for k in CALLEE)
                if site == 'S3' and ev['mode'] == 0:
                    pass
            ok['ret_pc_fixed'] = r['addr'] in (0x0834B428, 0x0834B0C6, 0x0834B21A, 0x0834AB44, 0x0834ABA2)
            ev['regs_entry'] = {k: f'{b[k]:08x}' for k in CALLEE}
            ev['regs_ret'] = {k: f'{r[k]:08x}' for k in CALLEE + ['r2', 'r3']}
            if not all(ok.values()):
                errors.append((site, b['n'], {k: v for k, v in ok.items() if not v}))
            events.append(ev)
        elif site == 'P1_nc_alloc':
            ev = {'site': 'P1', 'n': b['n'], 'checks': {}}
            ok = ev['checks']
            ja = find(bps, i, {'allocator'}, stop=())
            jr = find(bps, i, {'alloc_ret_in_nc'}, stop=())
            je = find(bps, i, {'nc_alloc_epilogue'}, stop=())
            jc = find(bps, i, {'P1_caller_ret'}, stop=())
            if None in (ja, jr, je):
                errors.append(('P1', b['n'], 'missing alloc chain')); continue
            a, rr, ep = bps[ja], bps[jr], bps[je]
            ok['allocator_r0_0x80'] = a['r0'] == 0x80 and a['lr'] == 0x08F75A8D and a['sp'] == b['sp'] - 8
            ok['alloc_ret_nonzero'] = rr['r0'] != 0
            ok['epilogue_sp'] = ep['sp'] == b['sp'] - 8
            ev['ptr'] = f"{rr['r0']:08x}"
            if jc is not None and bps[jc]['addr'] == (b['lr'] & ~1):
                c = bps[jc]
                ok['caller_ret_callee_equal'] = all(c[k] == b[k] for k in ['r4', 'r5', 'r6', 'r7', 'r8', 'r9', 'r10', 'r11', 'sp'])
                ok['caller_ret_r0_is_return_address_like_native_B970_frame'] = c['r0'] == b['lr']
                ev['caller_ret'] = f"{c['addr']:08x}"
            else:
                ev['caller_ret'] = None
            if not all(ok.values()):
                errors.append(('P1', b['n'], {k: v for k, v in ok.items() if not v}))
            events.append(ev)
    return events, errors


def parse_watch(lines):
    out = []
    for l in lines:
        m = _re.match(r'^(\d+) addr=(\w+) pc=(\w+) lr=(\w+) r0=(\w+) r1=(\w+) old=(\w+) new=(\w+)', l)
        if m:
            out.append({'n': int(m.group(1)), 'addr': int(m.group(2), 16), 'pc': int(m.group(3), 16), 'old': int(m.group(7), 16), 'new': int(m.group(8), 16)})
    return out


def make_pending():
    """fresh name -> cancel Yes -> editor -> menu on 이름 입력 -> A then frame-step until nc_alloc done but D1 not yet."""
    e = Emu('case15-pending', 'candidate', bps=BPS15)
    try:
        e.loadstate(FRESH_SS)
        e.tap(A, 60)
        e.move_to(*CANCELC)
        e.tap(A, 120)
        e.tap(A, 180)
        e.tap(SEL, 30); e.tap(A, 30); e.tap(DOWN, 24); e.tap(DOWN, 24)
        e.shot('before-entry')
        e.savestate('before-entry.ss0')
        m = e.bp_mark()
        e.cmd('keys 1'); e.cmd('frames 1'); e.cmd('keys 0')
        found = None
        for f in range(120):
            names = [x['name'] for x in parse_bp(e.bp_lines(m))]
            if 'D1' in names:
                found = ('D1_same_frame', f); break
            if 'P1_nc_alloc' in names and 'nc_alloc_epilogue' in names:
                ptr, o = e.obj('pending-obj.bin')
                e.savestate('pending.ss0')
                found = ('pending', f, f'{ptr:08x}', o[0x60]); break
            e.cmd('frames 1')
        print('PENDING', found, flush=True)
        return found
    finally:
        e.close()


def run_mode(mode):
    tag = f'case15-mode{mode}' + ('-SYNTHETIC' if mode == 0 else '')
    e = Emu(tag, 'candidate', bps=BPS15)
    notes = {'synthetic': mode == 0, 'ram_writes': []}
    try:
        e.loadstate(R / 'runs/case15-pending/pending.ss0')
        ptr, o = e.obj('pending-obj.bin')
        if mode == 0:
            e.cmd(f'w8 {ptr + 0x60:08x} 00')
            notes['ram_writes'].append(f'w8 {ptr + 0x60:08x} 00  (SYNTHETIC mode0)')
        sp_rows = 0x03007D28  # from normal-key D1 runs (rowdraw sp); verified again below
        e.cmd(f'watchaddr {sp_rows:08x} 8 a KEEP')
        e.frames(180)
        e.shot('constructed')
        ptr, o = e.obj('constructed-obj.bin')
        notes['mode_byte'] = o[0x60]
        closes = 0
        while e.obj()[1][0x66] != 1 and closes < 4:  # guidance pages (mode0 shows 2 pages): A until grid-active flag
            e.tap(A, 60); closes += 1
        notes['guidance_A_presses'] = closes
        e.shot('ready')
        o0 = e.obj()[1]
        e.move_to(0, 0)
        e.tap(A, 24); e.shot('after-a')
        o1 = e.obj('after-a-obj.bin')[1]
        e.tap(BB, 24); e.shot('after-b')
        o2 = e.obj('after-b-obj.bin')[1]
        e.tap(START, 120); e.shot('after-start')
        o3 = e.obj('after-start-obj.bin')[1]
        notes['steps'] = {'ready': (o0[0x61], o0[0x2C:0x34].hex()), 'A(0,0)': (o1[0x61], o1[0x2C:0x34].hex()),
                          'B': (o2[0x61], o2[0x2C:0x34].hex()), 'START': (o3[0x61], o3[0x67])}
        if mode == 0:
            notes['native_like'] = o1[0x61] == 1 and o1[0x2C:0x2E] == bytes.fromhex('8341') and o2[0x61] == 0 and o3[0x67] == 2
        else:
            notes['mode1_like'] = o1[0x61] == 1 and o1[0x2C:0x2E] == JAMO['ㄱ'].to_bytes(2, 'big') and o2[0x61] == 0 and o3[0x67] == 2  # empty name: nc_confirm 0 -> native AED8 question
    finally:
        e.close()
    (e.d / 'notes.json').write_text(json.dumps(notes, ensure_ascii=False, indent=1))
    print(tag, json.dumps(notes, ensure_ascii=False), flush=True)
    return e.d, notes


def analyze():
    report = {'runs': {}, 'totals': {}, 'errors': []}
    for d in sorted((R / 'runs').iterdir()):
        lj = d / 'launch.json'
        if not (d / 'bp.log').exists() or not lj.exists() or json.loads(lj.read_text())['rom_sha256'] != CAND_SHA:
            continue
        lines = (d / 'bp.log').read_text().splitlines()
        bps = parse_bp(lines)
        ev, err = check_log(bps, 0x02003010)
        report['runs'][d.name] = {'events': len(ev), 'errors': err,
                                  'by_site_mode': {}}
        for x in ev:
            k = f"{x['site']}/mode{x.get('mode')}" + (f"/c_ret{x.get('c_ret')}" if 'c_ret' in x else '')
            report['runs'][d.name]['by_site_mode'][k] = report['runs'][d.name]['by_site_mode'].get(k, 0) + 1
            report['totals'][k] = report['totals'].get(k, 0) + 1
        report['errors'] += [[d.name] + list(e) for e in err]
        if d.name.startswith('case15-mode'):
            w = parse_watch(lines)
            report['runs'][d.name]['stack_watch'] = [{'n': x['n'], 'addr': f"{x['addr']:08x}", 'pc': f"{x['pc']:08x}", 'old': f"{x['old']:08x}", 'new': f"{x['new']:08x}"}
                                                      for x in w if 0x08F75800 <= x['pc'] < 0x08F77800 or 0x08314E00 <= x['pc'] < 0x08315000][:80]
            report['runs'][d.name]['d1_events'] = [x for x in ev if x['site'] == 'D1']
    (R / 'case15-contracts.json').write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str))
    print('TOTALS', json.dumps(report['totals'], ensure_ascii=False))
    print('ERRORS', len(report['errors']), json.dumps(report['errors'][:10], default=str)[:2000])
    return report


if __name__ == '__main__':
    what = sys.argv[1:]
    if 'pending' in what:
        make_pending()
    if 'modes' in what:
        run_mode(1); run_mode(0)
    if 'analyze' in what:
        analyze()
