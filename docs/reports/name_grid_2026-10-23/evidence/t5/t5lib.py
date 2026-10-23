"""T5 runtime QA driver (temp only). Official mGBA 0.10.5 library + minimal r8-r11 BP-log harness copy.

Every run gets its own directory under runs/<tag> (must not exist). cwd/TMPDIR/AW_KOR_TEMP_DIR/log are inside it.
Saves are copied (O_EXCL) into the run dir; the harness itself works on a mkstemp copy (--read-only-save).
Keys: A=1 B=2 SELECT=4 START=8 RIGHT=16 LEFT=32 UP=64 DOWN=128 R=256 L=512.
"""
from pathlib import Path
import subprocess, os, json, struct, time, select, hashlib, sys, shutil
from PIL import Image

R = Path(__file__).resolve().parent
B = R.parent
ROOT = R.parents[2]
O = B / 'official-mgba'
HARNESS = R / 'harness' / 'mgbah-t5'
CAND = ROOT / 'output/game_wars_korean_namecompose_20261023.gba'
CAND_SHA = '1ac790a9bd173f14d7a4880be95b8ffe3983bc84dfd8f848faff9c5c4575e1eb'
BASE_SHA = 'ebbca0babca25e4ed9d77c88af0b159fab567c9e8d708bd69a46f281e38a3a8a'  # T4 REPORT baseline (actual shasum)
ORIG = ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba'
ORIG_SHA = 'a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c'
EIGHT_SAV = B / 'native-re/replay-normal/new-eight.sav'
EIGHT_SAV_SHA = 'd6e2651201c497139a4235034ed5d922816e1c2d2dd3c487ebf87d553ceeb481'
GPTR = 0x03004650
A, BB, SEL, START, RIGHT, LEFT, UP, DOWN, RK, LK = 1, 2, 4, 8, 16, 32, 64, 128, 256, 512
sys.path.insert(0, str(ROOT / 'tools'))
import hangul_compose as hc  # noqa: E402

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

ROMS = {'candidate': (CAND, CAND_SHA), 'original': (ORIG, ORIG_SHA),
        'baseline': (ROOT / 'output/game_wars_korean_namegrid_baseline_20261023.gba', BASE_SHA)}

# --- static facts from the actual candidate ROM / blob ---
_crom = None
def crom():
    global _crom
    if _crom is None:
        _crom = CAND.read_bytes()
        assert hashlib.sha256(_crom).hexdigest() == CAND_SHA
    return _crom

TABLE = hc.load_table()
def _load_jamo():
    raw = json.loads((ROOT / 'data/jamo_to_code_40.json').read_text())
    if 'codes' in raw:
        raw = raw['codes']
    out = {}
    for k, v in raw.items():
        if len(k) == 1:
            out[k] = int(v, 16) if isinstance(v, str) else int(v)
    assert len(out) == 40, len(out)
    return out
JAMO = _load_jamo()
CODE2JAMO = {v: k for k, v in JAMO.items()}
CODE2SYL = {v: k for k, v in TABLE.items()}
SEL_PRIV_FILE = 0xF76088
ROW_PRIV_FILE = 0xF7613C

def sel_grid():
    b = crom()[SEL_PRIV_FILE:SEL_PRIV_FILE + 180]
    return [[int.from_bytes(b[(y * 15 + x) * 2:(y * 15 + x) * 2 + 2], 'big') for x in range(15)] for y in range(6)]
GRID = sel_grid()
WIDE = {0x6262, 0x6363, 0x6565}

def cell_of(code, prefer=None):
    hits = [(x, y) for y in range(6) for x in range(15) if GRID[y][x] == code]
    assert hits, hex(code)
    if prefer and prefer in hits:
        return prefer
    return hits[0]

def jamo_cell(j):
    return cell_of(JAMO[j])

def jamo_tile(j):
    """64B top+bot as the candidate ROM stores it (A3 tail entry -> KOR_BASE)."""
    i = list(hc.PREVIEW_JAMO).index(j)
    r = crom()
    base = 0xF00000
    return r[base + (1275 + 2 * i) * 32: base + (1275 + 2 * i) * 32 + 32] + r[base + (1276 + 2 * i) * 32: base + (1276 + 2 * i) * 32 + 32]

def decode(code):
    return CODE2SYL.get(code) or CODE2JAMO.get(code) or {0x8140: '␣'}.get(code) or f'<{code:04X}>'

# --- process ledger ---
LEDGER = R / 'processes.jsonl'
def ledger(rec):
    with LEDGER.open('a') as f:
        f.write(json.dumps(rec) + '\n')


class Emu:
    def __init__(self, tag, rom='candidate', save=None, bps=None, nice=15):
        self.d = R / 'runs' / tag
        if self.d.exists():  # superseded run: keep as evidence, never delete
            sup = R / 'runs-superseded' / f'{tag}-{int(time.time())}'
            sup.parent.mkdir(exist_ok=True)
            self.d.rename(sup)
            ledger({'event': 'superseded', 'tag': tag, 'moved_to': str(sup.relative_to(R))})
        self.d.mkdir(parents=True, exist_ok=False)
        self.tag = tag
        romp, romsha = ROMS[rom]
        assert sha(romp) == romsha, rom
        self.rom = rom
        self.frame = 0
        self.steps = []
        args = ['nice', '-n', str(nice), str(HARNESS), str(romp), str(self.d / 'emulator.log')]
        self.save_in = None
        if save:
            save = Path(save)
            self.save_in = self.d / 'input.sav'
            with open(save, 'rb') as s, open(self.save_in, 'xb') as t:
                t.write(s.read())
            args += [str(self.save_in), '--read-only-save']
        self.env = dict(os.environ, TMPDIR=str(self.d) + '/', AW_KOR_TEMP_DIR=str(self.d),
                        DYLD_LIBRARY_PATH=str(O / 'build'), PYTHONDONTWRITEBYTECODE='1')
        meta = {'tag': tag, 'argv': args, 'cwd': str(self.d), 'rom': str(romp), 'rom_sha256': romsha,
                'save_source': str(save) if save else None, 'save_source_sha256': sha(save) if save else None,
                'harness_sha256': sha(HARNESS), 'library_sha256': sha(O / 'build/libmgba.dylib'),
                'env': {k: self.env[k] for k in ['TMPDIR', 'AW_KOR_TEMP_DIR', 'DYLD_LIBRARY_PATH']}}
        (self.d / 'launch.json').write_text(json.dumps(meta, indent=1))
        self.err = (self.d / 'stderr.log').open('w')
        self.p = subprocess.Popen(args, cwd=self.d, env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=self.err, text=True, bufsize=1)
        ledger({'event': 'start', 'tag': tag, 'pid': self.p.pid, 'time': time.time(), 'argv': args})
        self.bplog = self.d / 'bp.log'
        first = True
        for a in (bps or []):
            self.cmd(f'break {a:08x} ' + (str(self.bplog) if first else 'KEEP'))
            first = False
        self.has_bp = bool(bps)

    # raw command
    def cmd(self, s, timeout=120):
        t = time.monotonic()
        self.p.stdin.write(s + '\n')
        self.p.stdin.flush()
        if not select.select([self.p.stdout], [], [], timeout)[0]:
            raise TimeoutError(s)
        out = self.p.stdout.readline().strip()
        if s.startswith('frames '):
            self.frame += int(s.split()[1])
        with (self.d / 'commands.jsonl').open('a') as f:
            f.write(json.dumps({'frame': self.frame, 'command': s, 'output': out, 'sec': round(time.monotonic() - t, 3)}) + '\n')
        if not out or out.startswith('ERR') or (s.startswith(('loadstate ', 'savestate ')) and 'ok=1' not in out):
            raise RuntimeError((s, out))
        return out

    def frames(self, n):
        while n > 0:
            k = min(n, 600)
            self.cmd(f'frames {k}')
            n -= k

    def tap(self, k, wait=24, hold=1):
        self.cmd(f'keys {k}')
        self.cmd(f'frames {hold}')
        self.cmd('keys 0')
        self.frames(wait)

    def mem(self, addr, n, name=None):
        p = self.d / (name or '_scratch.bin')
        self.cmd(f'dumpmem {addr:08x} {n} {p}')
        return p.read_bytes()

    def objptr(self):
        return struct.unpack('<I', self.mem(GPTR, 4))[0]

    def obj(self, name=None):
        ptr = self.objptr()
        assert 0x02000000 <= ptr < 0x02040000, hex(ptr)
        return ptr, self.mem(ptr, 0x80, name)

    def cursor(self):
        _, o = self.obj()
        return struct.unpack_from('<hh', o, 0x1E)

    def shot(self, name):
        f = self.d / (name + '.raw')
        self.cmd('shot ' + str(f))
        b = f.read_bytes()
        w, h, c = struct.unpack('<HHB', b[:5])
        assert (w, h, c) == (240, 160, 4)
        Image.frombytes('RGBA', (w, h), b[5:]).convert('RGB').resize((720, 480), Image.Resampling.NEAREST).save(self.d / (name + '.png'))
        f.unlink()
        return self.d / (name + '.png')

    def savestate(self, name):
        self.cmd('savestate ' + str(self.d / name))
        return self.d / name

    def loadstate(self, path):
        path = Path(path).resolve()
        assert str(path).startswith(str(R)), 'only T5-owned candidate savestates'
        self.cmd('loadstate ' + str(path))

    def dumpsave(self, name):
        out = self.cmd('dumpsave ' + str(self.d / name))
        assert out.startswith('OK'), out
        return self.d / name

    def bp_mark(self):
        return self.bplog.stat().st_size if self.bplog.exists() else 0

    def bp_lines(self, start, end=None):
        if not self.bplog.exists():
            return []
        b = self.bplog.read_bytes()[start:end]
        return b.decode().splitlines()

    # navigation
    def move_to(self, tx, ty, wide_ok=None, max_taps=40):
        if wide_ok is None:
            wide_ok = GRID[ty][tx] in WIDE
        trail = []
        for _ in range(max_taps):
            x, y = self.cursor()
            trail.append((x, y))
            if y == ty and (x == tx or (wide_ok and 10 <= x <= 14 and GRID[y][x] == GRID[ty][tx])):
                return (x, y), trail
            if y != ty:
                k = DOWN if ty > y else UP
            else:
                k = RIGHT if tx > x else LEFT
            self.tap(k, 10)
            nx, ny = self.cursor()
            if (nx, ny) == (x, y):
                raise RuntimeError(f'cursor did not move from {(x, y)} key {k}')
        raise RuntimeError(f'could not reach {(tx, ty)} trail {trail}')

    def close(self):
        rc = None
        if self.p.poll() is None:
            try:
                self.cmd('quit', timeout=20)
            except Exception:
                pass
            self.p.stdin.close()
        try:
            rc = self.p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.p.terminate()
            rc = self.p.wait(timeout=10)
        self.err.close()
        (self.d / 'exit.json').write_text(json.dumps({'exit': rc, 'frames': self.frame}))
        ledger({'event': 'end', 'tag': self.tag, 'pid': self.p.pid, 'time': time.time(), 'exit': rc})
        # remove harness private save copies (mkstemp) if any remain
        for f in self.d.glob('mgbah_probe_save_*'):
            f.unlink()
        return rc


# --- oracle / live adapter (plan §1.4) ---
OFF_SLOT, OFF_LEN, OFF_TAIL = 0x2C, 0x61, 0x70

def live_expected(comp):
    slots = list(comp.committed)
    a = comp.active
    if a is not None:
        if a.complete:
            slots.append(TABLE[a.char])
        else:
            slots.append(JAMO[hc.L_LIST[a.L]] if a.L is not None else JAMO[hc.V_LIST[a.V]])
    tail = bytes([1 if a else 0,
                  a.L if a is not None and a.L is not None else 0xFF,
                  a.V if a is not None and a.V is not None else 0xFF,
                  a.T if a is not None else 0])
    return slots, tail

def live_check(o, comp):
    """prefix+terminator rule: slot[0:2n] == expected, n<8 -> slot[n]==0000; tail[0:4] exact, +74..+7F zero."""
    slots, tail = live_expected(comp)
    n = len(slots)
    errs = []
    exp = b''.join(c.to_bytes(2, 'big') for c in slots)
    if o[OFF_LEN] != n:
        errs.append(f'len {o[OFF_LEN]} != {n}')
    if o[OFF_SLOT:OFF_SLOT + 2 * n] != exp:
        errs.append(f'slots {o[OFF_SLOT:OFF_SLOT + 16].hex()} != {exp.hex()}')
    if n < 8 and o[OFF_SLOT + 2 * n:OFF_SLOT + 2 * n + 2] != b'\0\0':
        errs.append(f'terminator {o[OFF_SLOT + 2 * n:OFF_SLOT + 2 * n + 2].hex()}')
    if o[OFF_TAIL:OFF_TAIL + 4] != tail:
        errs.append(f'tail {o[OFF_TAIL:OFF_TAIL + 4].hex()} != {tail.hex()}')
    if o[0x74:0x80] != bytes(12):
        errs.append(f'tail74 {o[0x74:0x80].hex()}')
    return errs

def stored_check(dest16, committed):
    """native trim contract: prefix (trailing 8140 removed); 8 committed -> exact 16B; else next byte 0."""
    codes = list(committed)
    while codes and codes[-1] == 0x8140:
        codes.pop()
    pre = b''.join(c.to_bytes(2, 'big') for c in codes)
    errs = []
    if dest16[:len(pre)] != pre:
        errs.append(f'prefix {dest16.hex()} !startswith {pre.hex()}')
    if len(committed) == 8 and len(codes) == 8:
        if dest16 != pre:
            errs.append('full16 mismatch')
    elif len(pre) < 16 and dest16[len(pre)] != 0:
        errs.append(f'byte after prefix {dest16[len(pre)]:02x}')
    return errs, pre


def literal(comp, code):
    codes = comp.committed.copy()
    if comp.active is not None:
        if not comp.active.complete:
            return hc.Result(False, 'incomplete')
        codes.append(comp.table[comp.active.char])
    return comp._apply(codes + [code], None)


class Case:
    """Grid-key driver + oracle. Every op: move by RAM cursor, A, read obj, compare with Composer."""
    def __init__(self, emu, name, comp=None, results=None):
        self.e = emu
        self.name = name
        self.comp = comp or hc.Composer(TABLE)
        self.log = []
        self.fail = []
        self.results = results

    def snap(self):
        ptr, o = self.e.obj()
        return ptr, o

    def record(self, op, arg, res_model, before, after, extra=None, expect_sound='auto'):
        errs = live_check(after[1], self.comp)
        if expect_sound == 'auto':
            expect_sound = None if res_model is None else ('65' if res_model.accepted else '68')
            if op == 'B':
                expect_sound = '66'
        rec = {'case': self.name, 'op': op, 'arg': arg, 'model': {'accepted': res_model.accepted, 'reason': res_model.reason} if res_model else None,
               'obj_ptr': f'{after[0]:08x}', 'live16': after[1][OFF_SLOT:OFF_SLOT + 16].hex(), 'len': after[1][OFF_LEN],
               'tail': after[1][OFF_TAIL:OFF_TAIL + 16].hex(), 'preview': ''.join(decode(int.from_bytes(after[1][OFF_SLOT + 2 * i:OFF_SLOT + 2 * i + 2], 'big')) for i in range(min(8, after[1][OFF_LEN]))),
               'errors': errs, 'frame': self.e.frame}
        if res_model is not None and not res_model.accepted:
            if before[1][0x2C:0x3C] != after[1][0x2C:0x3C] or before[1][0x61] != after[1][0x61] or before[1][0x70:0x80] != after[1][0x70:0x80]:
                errs.append('rejected but live changed')
        if extra:
            rec.update(extra)
        if 'bp_from' in rec:
            bps = parse_bp(self.e.bp_lines(rec['bp_from']))
            rec['bp_seq'] = [b['name'] for b in bps if b['name'] not in ('A3_copy', 'rowdraw', 'RET_B428')]
            rec['sounds'] = [f"{b['r0']:02x}" for b in bps if b['name'] == 'sound']
            rec['a3'] = [(f"{b['r6']:08x}", f"{b['r7']:08x}") for b in bps if b['name'] == 'A3_copy']
            if expect_sound is not None and expect_sound not in rec['sounds']:
                errs.append(f"expected sound {expect_sound} got {rec['sounds']}")
        self.log.append(rec)
        if errs:
            self.fail.append(rec)
        with (self.e.d / 'steps.jsonl').open('a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        return rec

    def press_cell(self, x, y, wait=24):
        pos, trail = self.e.move_to(x, y)
        m = self.e.bp_mark()
        self.e.tap(A, wait)
        return pos, trail, m

    def jamo(self, j):
        x, y = jamo_cell(j)
        before = self.snap()
        pos, trail, m = self.press_cell(x, y)
        res = self.comp.press(j)
        return self.record('jamo', j, res, before, self.snap(), {'cell': pos, 'nav': trail, 'bp_from': m})

    def jamos(self, seq):
        return [self.jamo(j) for j in seq]

    def literal_cell(self, code, prefer=None):
        x, y = cell_of(code, prefer)
        before = self.snap()
        pos, trail, m = self.press_cell(x, y)
        res = self.comp.space() if code == 0x8140 else literal(self.comp, code)
        return self.record('literal', f'{code:04X}', res, before, self.snap(), {'cell': pos, 'nav': trail, 'bp_from': m})

    def backspace(self):
        before = self.snap()
        m = self.e.bp_mark()
        self.e.tap(BB, 24)
        res = self.comp.backspace()
        return self.record('B', None, res, before, self.snap(), {'bp_from': m})

    def check_now(self, label):
        return self.record('check', label, None, self.snap(), self.snap())

    def ok(self):
        return not self.fail

# --- breakpoint sets (Thumb even addresses) ---
BP_NAMES = {
    0x0834B0BC: 'S1', 0x0834B084: 'S2', 0x0834B20E: 'S3', 0x0834AB3C: 'D1', 0x08F75A80: 'P1_nc_alloc',
    0x08F75800: 'tramp_press', 0x08F758D4: 'tramp_confirm', 0x08F7594C: 'tramp_backspace', 0x08F759B0: 'tramp_display',
    0x08F75AB8: 'nc_press', 0x08F75EDC: 'nc_confirm', 0x08F75F68: 'nc_backspace',
    0x08F7584C: 'ret_nc_press', 0x08F758FC: 'ret_nc_confirm', 0x08F75974: 'ret_nc_backspace',
    0x0834B428: 'RET_B428', 0x0834B0C6: 'RET_B0C6', 0x0834B21A: 'RET_B21A', 0x0834AB44: 'RET_AB44', 0x0834ABA2: 'RET_ABA2',
    0x08315300: 'allocator', 0x08F75A8C: 'alloc_ret_in_nc', 0x08F75AA6: 'nc_alloc_epilogue',
    0x08314EB0: 'rowdraw', 0x0833BA34: 'sound', 0x0834AED8: 'AED8_question', 0x0834AE00: 'AE00_append',
    0x08F302D8: 'A3_copy',
}
BPS_ALL = sorted(BP_NAMES)
PC_SKEW = 2
import re as _re
_BP_RE = _re.compile(r'^(\d+) BP (.*)$')

def parse_bp(lines):
    out = []
    for l in lines:
        m = _BP_RE.match(l)
        if not m:
            continue
        regs = dict(kv.split('=') for kv in m.group(2).split())
        regs = {k: int(v, 16) for k, v in regs.items()}
        regs['n'] = int(m.group(1))
        # observed: logged pc = breakpoint address + PC_SKEW (determined empirically, see prep log)
        regs['addr'] = regs['pc'] - PC_SKEW
        regs['name'] = BP_NAMES.get(regs['addr'], f"pc{regs['pc']:08x}")
        out.append(regs)
    return out
