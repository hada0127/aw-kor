#!/usr/bin/env python3
"""1편 이름 조합(Phase C) 코어·표 생성기 테스트 — PLAN B T2a 케이스 ①–⑤.

① max=8: 1편 tables.h(NC_MAX_SLOTS = obj[0x62])로 host 컴파일한 core.c 가 Part 2 tables.h 빌드와
   랜덤 20,000(seed 20261023)·11,172 전수에서 rc·버퍼까지 같고 오라클(hangul_compose)과도 일치.
② max=6: 6번째 active 편집 허용 · 7번째 no_slot(len·슬롯 불변) · 7번째를 요구하는 종성 이동 원자 거부
   · 랜덤 20,000 오라클(hc.MAX_SLOTS=6 임시 교체) 일치 · slot[6..] 이후 바이트 불변.
③ core.c 에서 NC_MAX_SLOTS 사용 위치가 commit(obj,…) 본문 2곳뿐(매크로 전제).
④ 사설 선택표 90셀 = 생성 grid_p1.inc 바이트 = 1편 native 표(원본 0xDF9F5C)와 동작 코드 분류 동일.
⑤ 표시행 6개: 1편 형식·길이(40/40/40/28/28/28)·쌍 매핑·host 치환·native 행과 x≥10 동일·사전 수록.
T0 값(host/placeholder/CONFIG) 대조는 T0Values — p1_config.json 이 없으면 skip(PENDING T0).
T2b(p1.c, -DNC1_HOST 로 가짜 확장표·사전 캐시·VRAM 배열에 연결) — P1Helpers:
  ⑥ nc1_pad 경계(len=0/3/max, max 6/8, +0x2C+max*2 밖 불변) ⑦ 한글/비한글 치환(i≥len·bit15 아님·표 없음은 원 코드)
  ⑧ placeholder 재사용(같은 칸 두 번) ⑨ 캐시 부재 시 치환 안 함·VRAM 무변경 ⑩ 업로드 바이트 = KOR_BASE 원본(리맵 없음)
  ⑪ host 33 자모 업로드·tail 초기화·max>8 절단.
ROM 삽입·실게임 동작은 범위 밖(T3~T6).
"""
import contextlib
import ctypes
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(TOOLS, 'name_compose_p1'))
sys.path.insert(0, os.path.join(TOOLS, 'name_compose'))
sys.path.insert(0, TOOLS)

import hangul_compose as hc  # noqa: E402
import gen_tables  # noqa: E402
import gen_tables_p1 as g1  # noqa: E402
from gen_jamo_assets import dense_table, load_jamo_codes  # noqa: E402

ORIGINAL = os.path.join(ROOT, 'original', 'Game Boy Wars Advance 1+2 (Japan).gba')
CORE_C = os.path.join(TOOLS, 'name_compose', 'core.c')
T0_CONFIG = os.path.join(ROOT, 'temp', 'fix_20261104', 'p1compose', 't0', 'p1_config.json')
P1_SEL_FILE = 0xDF9F5C                          # 1편 native 선택표 (P1_NAME_RE §2.3)
SPACE = hc.SPACE_CODE
LITERALS = (0x824F, 0x8250, 0x8251, 0x8252, 0x8253, 0x8254, 0x8255, 0x8256, 0x8257, 0x8258,
            0x8145, 0x8149, 0x8148)
OFF_SLOT, OFF_LEN, OFF_MAX, OFF_TAIL = 0x2C, 0x61, 0x62, 0x70
SEED, RANDOM_OPS = 20261023, 20000


def literal(comp, code):
    """space() 와 같은 규칙의 리터럴 셀 — test_name_compose_core.literal 과 동일."""
    codes = comp.committed.copy()
    if comp.active is not None:
        if not comp.active.complete:
            return hc.Result(False, 'incomplete')
        codes.append(comp.table[comp.active.char])
    return comp._apply(codes + [code], None)


@contextlib.contextmanager
def oracle_max(n):
    saved = hc.MAX_SLOTS
    hc.MAX_SLOTS = n
    try:
        yield
    finally:
        hc.MAX_SLOTS = saved


def sentinel_buffer():
    return bytearray((i * 37 + 11) & 0xFF for i in range(128))


def build_lib(workdir, tables_h, dense_c, name):
    d = os.path.join(workdir, name)
    os.makedirs(d)
    with open(os.path.join(d, 'tables.h'), 'wb') as f:
        f.write(tables_h)
    lib = os.path.join(d, 'libnc.so')
    subprocess.run(['clang', '-std=c99', '-O2', '-fPIC', '-shared', '-Wall', '-Wextra', '-Werror',
                    '-I', d, CORE_C, dense_c, '-o', lib], check=True, capture_output=True)
    cdll = ctypes.CDLL(lib)
    for fn, args in (('nc_press', [ctypes.c_char_p, ctypes.c_uint16]),
                     ('nc_confirm', [ctypes.c_char_p]), ('nc_backspace', [ctypes.c_char_p])):
        getattr(cdll, fn).argtypes = args
        getattr(cdll, fn).restype = ctypes.c_int
    return cdll


def call(lib, buf, fn, *args):
    cbuf = ctypes.create_string_buffer(bytes(buf), 128)
    rc = getattr(lib, fn)(cbuf, *args)
    buf[:] = cbuf.raw[:128]
    return rc


class Harness:
    def __init__(self, table, codes, max_slots):
        self.table, self.codes, self.max = table, codes, max_slots
        self.decode = {v: k for k, v in table.items()}
        self.decode.update({v: k for k, v in codes.items()})

    def fresh(self, committed=()):
        buf = sentinel_buffer()
        buf[OFF_SLOT:OFF_SLOT + 2 * self.max] = bytes(2 * self.max)
        for i, c in enumerate(committed):
            buf[OFF_SLOT + 2 * i:OFF_SLOT + 2 * i + 2] = c.to_bytes(2, 'big')
        buf[OFF_LEN] = len(committed)
        buf[OFF_MAX] = self.max
        buf[OFF_TAIL:OFF_TAIL + 16] = bytes([0, 0xFF, 0xFF, 0]) + bytes(12)
        comp = hc.Composer(self.table)
        if committed:
            comp.load(list(committed))
        return buf, comp

    def expected(self, comp):
        slots = list(comp.committed)
        a = comp.active
        if a is not None:
            if a.complete:
                slots.append(comp.table[a.char])
            else:
                slots.append(self.codes[hc.L_LIST[a.L]] if a.L is not None else self.codes[hc.V_LIST[a.V]])
        data = b''.join(c.to_bytes(2, 'big') for c in slots).ljust(2 * self.max, b'\0')
        tail = bytes([1 if a else 0,
                      a.L if a is not None and a.L is not None else 0xFF,
                      a.V if a is not None and a.V is not None else 0xFF,
                      a.T if a is not None else 0]) + bytes(12)
        return data, len(slots), tail

    def check(self, tc, buf, comp, note=''):
        data, length, tail = self.expected(comp)
        end = OFF_SLOT + 2 * self.max
        tc.assertEqual(bytes(buf[OFF_SLOT:end]), data, note)
        tc.assertEqual(buf[OFF_LEN], length, note)
        tc.assertEqual(buf[OFF_MAX], self.max, note)
        tc.assertEqual(bytes(buf[OFF_TAIL:OFF_TAIL + 16]), tail, note)
        ref = sentinel_buffer()
        for i in list(range(0, OFF_SLOT)) + list(range(end, OFF_LEN)) + list(range(OFF_MAX + 1, OFF_TAIL)):
            if buf[i] != ref[i]:
                tc.fail(f'{note}: byte +0x{i:02X} changed (max={self.max})')

    def preview(self, buf):
        return ''.join(self.decode.get(int.from_bytes(buf[OFF_SLOT + 2 * i:OFF_SLOT + 2 * i + 2], 'big'), '?')
                       for i in range(buf[OFF_LEN]))

    def op(self, lib, buf, comp, kind, arg=None):
        if kind == 'jamo':
            return call(lib, buf, 'nc_press', self.codes[arg]), comp.press(arg)
        if kind == 'space':
            return call(lib, buf, 'nc_press', SPACE), comp.space()
        if kind == 'literal':
            return call(lib, buf, 'nc_press', arg), literal(comp, arg)
        if kind == 'backspace':
            return call(lib, buf, 'nc_backspace'), comp.backspace()
        if kind == 'confirm':
            return call(lib, buf, 'nc_confirm'), comp.confirm()
        raise ValueError(kind)


def random_op(rng):
    r = rng.random()
    if r < 0.70:
        return 'jamo', rng.choice(hc.SELECTABLE_JAMO)
    if r < 0.80:
        return 'backspace', None
    if r < 0.86:
        return 'confirm', None
    if r < 0.91:
        return 'space', None
    if r < 0.96:
        return 'literal', rng.choice(LITERALS)
    if r < 0.98:
        return 'reload', None
    return 'reset', None


def standard_keys(n):
    L, V, T = n // 588, (n // 28) % 21, n % 28
    vowel = hc.V_LIST[V]
    keys = [hc.L_LIST[L]] + list(next((a + b for (a, b), r in hc.COMPOUND_VOWELS.items() if r == vowel), vowel))
    if T:
        final = hc.T_LIST[T]
        keys += list(next((a + b for (a, b), r in hc.FINAL_CLUSTERS.items() if r == final), final))
    return keys


@unittest.skipUnless(shutil.which('clang'), 'host clang unavailable')
class CoreP1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = hc.load_table()
        cls.codes = load_jamo_codes()
        os.makedirs(os.path.join(ROOT, 'temp'), exist_ok=True)
        cls.tmp = tempfile.mkdtemp(dir=os.path.join(ROOT, 'temp'), prefix='name_compose_p1_host_')
        dense = dense_table(cls.table)
        values = [int.from_bytes(dense[i:i + 2], 'little') for i in range(0, len(dense), 2)]
        dense_c = os.path.join(cls.tmp, 'dense_host.c')
        with open(dense_c, 'w') as f:
            f.write('#include <stdint.h>\nconst uint16_t nc_dense[11172] = {\n')
            f.write(',\n'.join(','.join(str(v) for v in values[i:i + 28]) for i in range(0, len(values), 28)))
            f.write('\n};\n')
        # tables.h 는 hc.MAX_SLOTS 를 바꾸기 전에 만든다(Part 2 줄 = 8u).
        cls.p2 = build_lib(cls.tmp, gen_tables.tables_h(cls.codes), dense_c, 'p2')
        cls.p1 = build_lib(cls.tmp, g1.tables_h_p1(cls.codes), dense_c, 'p1')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # --- ① max=8: 매크로화가 동작을 바꾸지 않음 -------------------------------------------------
    def test_1_max8_random_identical_to_part2_build(self):
        h = Harness(self.table, self.codes, 8)
        rng = random.Random(SEED)
        b1, comp = h.fresh()
        b2 = bytearray(b1)
        applied = rejected = 0
        for i in range(RANDOM_OPS):
            kind, arg = random_op(rng)
            if kind in ('reload', 'reset'):
                b1, comp = h.fresh(tuple(comp.committed) if kind == 'reload' else ())
                b2 = bytearray(b1)
                continue
            rc, res = h.op(self.p1, b1, comp, kind, arg)
            rc2 = {'jamo': lambda: call(self.p2, b2, 'nc_press', self.codes[arg]),
                   'space': lambda: call(self.p2, b2, 'nc_press', SPACE),
                   'literal': lambda: call(self.p2, b2, 'nc_press', arg),
                   'backspace': lambda: call(self.p2, b2, 'nc_backspace'),
                   'confirm': lambda: call(self.p2, b2, 'nc_confirm')}[kind]()
            self.assertEqual(rc, rc2, f'op {i} {kind} {arg!r}')
            self.assertEqual(bytes(b1), bytes(b2), f'op {i} {kind} {arg!r}')
            self.assertEqual(rc == 0, res.accepted, f'op {i} {kind} {arg!r} model={res}')
            h.check(self, b1, comp, f'op {i}')
            applied += 1
            rejected += rc != 0
        print(f'max8 random={RANDOM_OPS} seed={SEED} applied={applied} rejected={rejected} p1==p2')
        self.assertGreater(rejected, 0)

    def test_1_max8_exhaustive_11172_identical_to_part2_build(self):
        h = Harness(self.table, self.codes, 8)
        reached = 0
        unreached = []
        for n in range(11172):
            ch = chr(0xAC00 + n)
            b1, comp = h.fresh()
            b2 = bytearray(b1)
            ok = True
            for k in standard_keys(n):
                before = bytes(b1)
                rc, res = h.op(self.p1, b1, comp, 'jamo', k)
                rc2 = call(self.p2, b2, 'nc_press', self.codes[k])
                self.assertEqual((rc, bytes(b1)), (rc2, bytes(b2)), (ch, k))
                self.assertEqual(rc == 0, res.accepted, (ch, k))
                if rc:
                    self.assertEqual(bytes(b1), before, (ch, k))
                    ok = False
                    break
                h.check(self, b1, comp, ch)
            if ok and h.preview(b1) == ch and b1[OFF_LEN] == 1:
                reached += 1
            elif ch in self.table:
                unreached.append(ch)
        print(f'max8 exhaustive=11172 reached={reached} supported_unreachable={"".join(sorted(unreached))}')
        self.assertEqual(reached, 2345)
        self.assertEqual(sorted(unreached), sorted('뢨썅쏀쓩쭁'))

    # --- ② max=6 -----------------------------------------------------------------------------
    def keys6(self, h, buf, comp, keys, note):
        out = []
        for k in keys:
            kind, arg = {'!': ('confirm', None), '<': ('backspace', None), '_': ('space', None)}.get(k, ('jamo', k))
            before = bytes(buf)
            rc, res = h.op(self.p1, buf, comp, kind, arg)
            self.assertEqual(rc == 0, res.accepted, f'{note}: {k} C={rc} model={res}')
            if rc:
                self.assertEqual(bytes(buf), before, f'{note}: rejected {k} changed buffer')
            h.check(self, buf, comp, note)
            out.append(rc)
        return out

    def test_2_max6_sixth_active_edit_seventh_no_slot(self):
        with oracle_max(6):
            h = Harness(self.table, self.codes, 6)
            buf, comp = h.fresh()
            self.assertEqual(self.keys6(h, buf, comp, 'ㄱㅏㄴㅏㄷㅏㄹㅏㅁㅏㅂㅏ', '6'), [0] * 12)
            self.assertEqual((buf[OFF_LEN], h.preview(buf)), (6, '가나다라마바'))
            self.assertEqual(self.keys6(h, buf, comp, 'ㄴ', '6th T'), [0])            # 6번째 active 편집
            self.assertEqual(h.preview(buf), '가나다라마반')
            snap = bytes(buf)
            self.assertEqual(self.keys6(h, buf, comp, 'ㄱ', '7th'), [1])             # no_slot
            self.assertEqual(bytes(buf), snap)
            self.assertEqual(buf[OFF_LEN], 6)
            self.assertEqual(self.keys6(h, buf, comp, 'ㅏ', 'move'), [1])            # 종성 이동 → 7번째 필요
            self.assertEqual(bytes(buf), snap)
            self.assertEqual(self.keys6(h, buf, comp, '<', 'edit back'), [0])
            self.assertEqual(h.preview(buf), '가나다라마바')
            self.assertEqual(self.keys6(h, buf, comp, '!', 'confirm'), [0])
            self.assertEqual(bytes(buf[OFF_SLOT:OFF_SLOT + 12]).hex(),
                             ''.join(f'{self.table[c]:04x}' for c in '가나다라마바'))
            self.assertEqual(self.keys6(h, buf, comp, '_', 'space full'), [1])
            buf, comp = h.fresh()                                                    # 받침 붙은 6번째 + 겹받침
            self.assertEqual(self.keys6(h, buf, comp, 'ㄱㅏ!ㄱㅏ!ㄱㅏ!ㄱㅏ!ㄱㅏ!ㄷㅏㄹㄱ', 'cluster'), [0] * 19)
            self.assertEqual(h.preview(buf), '가가가가가닭')
            self.assertEqual(self.keys6(h, buf, comp, 'ㅏ', 'cluster move'), [1])

    def test_2_max6_random_matches_oracle(self):
        with oracle_max(6):
            h = Harness(self.table, self.codes, 6)
            rng = random.Random(SEED)
            buf, comp = h.fresh()
            applied = rejected = full = 0
            for i in range(RANDOM_OPS):
                kind, arg = random_op(rng)
                if kind in ('reload', 'reset'):
                    buf, comp = h.fresh(tuple(comp.committed) if kind == 'reload' else ())
                    h.check(self, buf, comp, f'{kind} {i}')
                    continue
                before = bytes(buf)
                rc, res = h.op(self.p1, buf, comp, kind, arg)
                self.assertEqual(rc == 0, res.accepted, f'op {i} {kind} {arg!r} model={res}')
                if rc:
                    self.assertEqual(bytes(buf), before, f'op {i}')
                h.check(self, buf, comp, f'op {i}')
                self.assertLessEqual(buf[OFF_LEN], 6)
                applied += 1
                rejected += rc != 0
                full += buf[OFF_LEN] == 6
            print(f'max6 random={RANDOM_OPS} seed={SEED} applied={applied} rejected={rejected} at_max={full}')
            self.assertGreater(full, 0)


# --- ③ 매크로 전제 --------------------------------------------------------------------------------
class MacroPremise(unittest.TestCase):
    def test_3_nc_max_slots_only_in_commit_body(self):
        with open(CORE_C, encoding='utf-8') as f:
            src = f.read()
        m = re.search(r'^static int commit\(uint8_t \*obj,[^)]*\)\n\{\n(.*?)^\}\n', src, re.S | re.M)
        self.assertIsNotNone(m, 'commit(uint8_t *obj, ...) not found')
        body = m.group(1)
        self.assertEqual(len(re.findall(r'\bNC_MAX_SLOTS\b', body)), 2)
        self.assertEqual(len(re.findall(r'\bNC_MAX_SLOTS\b', src)), 2, 'NC_MAX_SLOTS used outside commit')
        self.assertNotRegex(body, r'\bobj\s*=', 'commit must not rebind obj')

    def test_3_tables_h_p1_differs_by_one_line(self):
        codes = load_jamo_codes()
        a = gen_tables.tables_h(codes).decode().splitlines()
        b = g1.tables_h_p1(codes).decode().splitlines()
        self.assertEqual(len(a), len(b))
        diff = [(x, y) for x, y in zip(a, b) if x != y]
        self.assertEqual(diff, [('#define NC_MAX_SLOTS 8u', '#define NC_MAX_SLOTS ((unsigned)obj[0x62])')])

    def test_part2_sources_untouched(self):
        import part2_name_compose_blob as blob
        self.assertEqual(blob.check_sources(), [])


def parse_inc(text):
    """생성 .inc 에서 라벨별 .byte 바이트."""
    out, cur = {}, None
    for line in text.splitlines():
        m = re.match(r'^(\w+):', line)
        if m:
            cur = m.group(1)
            out[cur] = bytearray()
            continue
        m = re.match(r'^\t\.byte (.*?)(\t@.*)?$', line)
        if m and cur:
            out[cur] += bytes(int(v, 16) for v in m.group(1).split(', '))
    return {k: bytes(v) for k, v in out.items()}


def rom_dictionary(rom):
    codes = []
    for addr, n in zip(g1.DICT_LISTS, g1.DICT_COUNTS):
        lst = [int.from_bytes(rom[addr + 2 * i:addr + 2 * i + 2], 'big') for i in range(n + 1)]
        assert lst[-1] == 0 and 0 not in lst[:-1], hex(addr)
        codes.append(lst[:-1])
    return codes


class GridP1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codes = load_jamo_codes()
        cls.grid = gen_tables.selection_grid(cls.codes)
        cls.inc = parse_inc(g1.grid_inc_p1(cls.codes).decode('utf-8'))
        cls.rows = [cls.inc[f'nc_row_priv_{y}'] for y in range(6)]
        cls.rom = None
        if os.path.exists(ORIGINAL):
            with open(ORIGINAL, 'rb') as f:
                cls.rom = f.read()

    def test_host_placeholder_constraints(self):
        g1.check_codes(self.codes)
        self.assertEqual(set(g1.HOST_OF), set(hc.SELECTABLE_JAMO))
        jamo0 = self.codes['ㄱ']
        bad = list(g1.HOST_CODES)
        for wrong in (jamo0, 0x6363, 0x3131, 0x824F, SPACE, g1.PLACEHOLDERS[0], 0x8840):
            bad[0] = wrong
            with self.assertRaises(ValueError, msg=hex(wrong)):
                g1.check_codes(self.codes, tuple(bad))

    @unittest.skipUnless(os.path.exists(ORIGINAL), 'original ROM absent')
    def test_hosts_and_placeholders_in_native_dictionary(self):
        lists = rom_dictionary(self.rom)
        self.assertEqual([len(x) for x in lists], list(g1.DICT_COUNTS))
        allc = {c for x in lists for c in x}
        self.assertEqual(len(allc), 113)
        self.assertTrue(set(g1.PLACEHOLDERS) <= set(lists[3]), 'placeholders must be hidden-kanji codes')
        self.assertTrue(set(g1.HOST_CODES) <= set(lists[2]) | set(lists[3]), 'hosts must be dakuon/hidden kanji')

    def test_4_private_selection_emitted_bytes(self):
        sel = self.inc['nc_sel_priv']
        self.assertEqual(len(sel), 180)
        self.assertEqual([int.from_bytes(sel[i:i + 2], 'big') for i in range(0, 180, 2)],
                         [c for row in self.grid for c in row])

    @unittest.skipUnless(os.path.exists(ORIGINAL), 'original ROM absent')
    def test_4_classification_identity_with_part1_native(self):
        native = self.rom[P1_SEL_FILE:P1_SEL_FILE + 180]
        sel = self.inc['nc_sel_priv']
        same = 0
        for i in range(90):
            n, p = native[2 * i:2 * i + 2], sel[2 * i:2 * i + 2]
            if n[0] in gen_tables.ACTION_LEADS:
                self.assertEqual(p, n, f'cell {i} (x={i % 15},y={i // 15}) action code must stay native')
                same += 1
            else:
                self.assertNotIn(p[0], gen_tables.ACTION_LEADS, f'cell {i}')
        self.assertEqual(same, 17)
        # 숫자·・！？ 리터럴도 native 와 같은 좌표·코드
        for y, x in [(0, x) for x in range(10, 15)] + [(1, x) for x in range(10, 15)] + [(2, 12), (2, 13), (2, 14)]:
            i = y * 15 + x
            self.assertEqual(sel[2 * i:2 * i + 2], native[2 * i:2 * i + 2], (x, y))

    def test_5_display_rows_format_and_host_substitution(self):
        self.assertEqual([len(r) for r in self.rows], list(g1.row_lengths_p1()))
        self.assertEqual(g1.row_lengths_p1(), (40, 40, 40, 28, 28, 28))
        self.assertEqual(self.rows, g1.display_rows_p1(self.grid, self.codes))
        host_by_code = {self.codes[j]: h for j, h in g1.HOST_OF.items()}
        jamo_codes = set(self.codes.values())
        for y, row in enumerate(self.rows):
            self.assertEqual(row[:2], b'\x0A\x09', y)
            self.assertEqual(row[-4:], b'\x0A\x00\x00\x00', y)
            pairs = [int.from_bytes(row[2 + 2 * i:4 + 2 * i], 'big') for i in range((len(row) - 6) // 2)]
            self.assertEqual(len(pairs), gen_tables.ROW_PAIR_COUNT[y])
            for p in pairs:
                self.assertNotIn(p >> 8, (0x00, 0x0A), (y, hex(p)))
                self.assertNotIn(p & 0xFF, (0x00, 0x0A), (y, hex(p)))
                self.assertNotIn(p, jamo_codes, 'jamo code leaked into display row')
            mapping = gen_tables.WIDE_ROW_PAIRS if len(pairs) == 17 else gen_tables.NARROW_ROW_PAIRS
            for x, p in enumerate(mapping):
                cell = self.grid[y][x]
                want = g1.DISPLAY_OVERRIDE_P1.get((x, y), host_by_code.get(cell, cell))
                self.assertEqual(pairs[p], want, (x, y))
            for g in ((5, 11) if len(pairs) == 17 else (5,)):
                self.assertEqual(pairs[g], SPACE, (y, g))
        host_tab = self.inc['nc1_host_tab']
        self.assertEqual(len(host_tab), 4 * 33)
        for i, j in enumerate(hc.SELECTABLE_JAMO):
            e = host_tab[4 * i:4 * i + 4]
            self.assertEqual((e[0], e[1], int.from_bytes(e[2:], 'little')),
                             (hc.PREVIEW_JAMO.index(j), 0, g1.HOST_OF[j]), j)
        ph = self.inc['nc1_placeholders']
        self.assertEqual([int.from_bytes(ph[i:i + 2], 'little') for i in range(0, 16, 2)], list(g1.PLACEHOLDERS))

    @unittest.skipUnless(os.path.exists(ORIGINAL), 'original ROM absent')
    def test_5_display_rows_match_native_and_dictionary(self):
        lists = rom_dictionary(self.rom)
        dictionary = {c for x in lists for c in x}
        for y, (addr, row) in enumerate(zip(g1.NATIVE_ROW_ADDRS, self.rows)):
            nat = self.rom[addr - 0x08000000:addr - 0x08000000 + len(row)]
            self.assertEqual((nat[:2], nat[-4:]), (row[:2], row[-4:]), y)    # 같은 길이에서 같은 종단
            npairs = [nat[2 + 2 * i:4 + 2 * i] for i in range((len(nat) - 6) // 2)]
            ppairs = [row[2 + 2 * i:4 + 2 * i] for i in range((len(row) - 6) // 2)]
            self.assertNotIn(0x0A, [p[0] for p in npairs])
            mapping = gen_tables.WIDE_ROW_PAIRS if len(ppairs) == 17 else gen_tables.NARROW_ROW_PAIRS
            used = set(mapping)
            for p in range(len(npairs)):
                if p not in used:
                    self.assertEqual(ppairs[p], npairs[p], (y, p))
            for x, p in enumerate(mapping):
                if x >= 10:
                    self.assertEqual(ppairs[p], npairs[p], (x, y))
            for p in ppairs:                                # 공백 8140 외에는 compact 사전에서 그려짐
                if int.from_bytes(p, 'big') != SPACE:
                    self.assertIn(int.from_bytes(p, 'big'), dictionary, (y, p.hex()))


class ConfigP1(unittest.TestCase):
    FULL = dict(g1.CONFIG, cache_bank=1, cache_list_off=6 + 510, cache_tile_off=0x60E, cache_code_order='be',
                vram_charblock=0x06000000, tbl_end=0x08F20000 + 2926 * 6, pal_remap=None)

    def test_config_h_from_full_config(self):
        h = g1.config_h(self.FULL).decode()
        self.assertIn('#define NC1_OBJ_PTR 0x03004690u', h)
        self.assertIn('#define NC1_CACHE_CODE_BE 1u', h)
        self.assertIn('#define NC1_PAL_REMAP 0u', h)
        self.assertIn('#define NC1_TILEMAP_LIT 0x08BE7280u', h)
        h2 = g1.config_h(dict(self.FULL, pal_remap=list(range(15, -1, -1)))).decode()
        self.assertIn('#define NC1_PAL_REMAP_TABLE { 15, 14', h2)
        with self.assertRaises(ValueError):
            g1.config_h(dict(self.FULL, cache_code_order='x'))

    def test_pending_config_refuses_generation(self):
        if not g1.T0_PENDING:
            self.skipTest('T0 values filled')
        with self.assertRaisesRegex(ValueError, 'pending'):
            g1.config_h()


def _int(v):
    return int(v, 16) if isinstance(v, str) else v


class T0Values(unittest.TestCase):
    """gen_tables_p1 의 한 곳 정본이 T0 p1_config.json 과 같은지. JSON 이 없으면 PENDING."""

    def setUp(self):
        if not os.path.exists(T0_CONFIG):
            self.skipTest(f'PENDING T0: {os.path.relpath(T0_CONFIG, ROOT)} absent')
        with open(T0_CONFIG, encoding='utf-8') as f:
            self.cfg = json.load(f)

    def test_t0_flag_cleared(self):
        self.assertFalse(g1.T0_PENDING, 'T0 output exists but gen_tables_p1.T0_PENDING is still True')

    def test_hosts_placeholders_match_t0(self):
        hosts = self.cfg.get('host_of') or self.cfg.get('hosts')
        ph = self.cfg.get('placeholders')
        self.assertIsNotNone(hosts, 'p1_config.json has no host_of/hosts')
        self.assertIsNotNone(ph, 'p1_config.json has no placeholders')
        if isinstance(hosts, dict):
            self.assertEqual({k: _int(v) for k, v in hosts.items()}, g1.HOST_OF)
        elif hosts and isinstance(hosts[0], dict):            # T0 형식: [{jamo, jamo_index, host, host_tile}]
            self.assertEqual({h['jamo']: _int(h['host']) for h in hosts}, g1.HOST_OF)
            self.assertEqual([h['jamo'] for h in hosts], list(hc.SELECTABLE_JAMO))
            for h in hosts:
                self.assertEqual(h['jamo_index'], hc.PREVIEW_JAMO.index(h['jamo']), h['jamo'])
        else:
            self.assertEqual(tuple(_int(v) for v in hosts), g1.HOST_CODES)
        self.assertEqual(tuple(_int(v) for v in ph), g1.PLACEHOLDERS)

    @unittest.skipUnless(os.path.exists(ORIGINAL), 'original ROM absent')
    def test_t0_tiles_match_dictionary_order(self):
        """T0 host_tile/placeholder_tiles = bank 1 이어 붙인 사전 목록의 index*2 (tile_start 0)."""
        with open(ORIGINAL, 'rb') as f:
            rom = f.read()
        flat = [c for lst in rom_dictionary(rom) for c in lst]
        start = self.cfg.get('cache_tile_start_observed', 0)
        for h in self.cfg.get('hosts', []):
            if isinstance(h, dict):
                self.assertEqual(h['host_tile'], start + 2 * flat.index(_int(h['host'])), h['jamo'])
        for p, t in zip(self.cfg.get('placeholders', []), self.cfg.get('placeholder_tiles', [])):
            self.assertEqual(t, start + 2 * flat.index(_int(p)), p)
        self.assertEqual(self.cfg.get('cache_count_observed', len(flat)), len(flat))

    def test_config_matches_t0(self):
        for k, v in g1.CONFIG.items():
            if k in self.cfg:
                want = self.cfg[k] if k in ('cache_code_order', 'pal_remap') else _int(self.cfg[k])
                self.assertEqual(v, want, k)



# --- T2b: p1.c host 테스트 -------------------------------------------------------------------------
P1_C = os.path.join(TOOLS, 'name_compose_p1', 'p1.c')
VRAM_HALFWORDS = 0x8000                       # 64 KiB (charblock 0..3)
FAKE_TILE_START = 0x10                        # 0 이 아닌 tile_start 로 식 검증


def fake_glyph(tile):
    return bytes(((tile * 37) + j * 11 + 1) & 0xFF for j in range(32))


class P1Lib:
    """p1.c(-DNC1_HOST) + host glue. 가짜 표·KOR·캐시·VRAM 을 ctypes 버퍼로 묶는다."""

    def __init__(self, workdir, table, codes):
        self.codes = codes
        d = os.path.join(workdir, 'p1helpers')
        os.makedirs(d)
        with open(os.path.join(d, 'p1_config.h'), 'wb') as f:
            f.write(g1.config_h())
        host_tab = g1.host_tab_bytes()
        ph = g1.placeholders_bytes()
        glue = os.path.join(d, 'glue.c')
        with open(glue, 'w') as f:
            f.write('#include <stdint.h>\n'
                    'const uint8_t *nc1_h_tbl_start, *nc1_h_tbl_end, *nc1_h_kor, *nc1_h_cache;\n'
                    'volatile uint16_t *nc1_h_vram;\n'
                    f'const uint8_t nc1_host_tab[{len(host_tab)}] = {{{", ".join(str(b) for b in host_tab)}}};\n'
                    f'const uint8_t nc1_placeholders[{len(ph)}] = {{{", ".join(str(b) for b in ph)}}};\n')
        lib = os.path.join(d, 'libp1.so')
        subprocess.run(['clang', '-std=c99', '-O2', '-fPIC', '-shared', '-Wall', '-Wextra', '-Werror',
                        '-DNC1_HOST', '-I', d, P1_C, glue, '-o', lib], check=True, capture_output=True)
        self.lib = ctypes.CDLL(lib)
        u, p = ctypes.c_uint, ctypes.c_char_p
        for fn, args, res in (('nc1_pad', [p], None), ('nc1_tail_init', [p], None),
                              ('nc1_korean_tiles', [u, ctypes.POINTER(u), ctypes.POINTER(u)], u),
                              ('nc1_cache_tile', [u], ctypes.c_int), ('nc1_upload', [u, u, u], None),
                              ('nc1_upload_hosts', [], None), ('nc1_display_init', [p], None),
                              ('nc1_preview_codes', [p, p], u)):
            getattr(self.lib, fn).argtypes = args
            getattr(self.lib, fn).restype = res
        # 가짜 확장 한자표: 비-bit15 한자 몇 개 + 2350 음절(top/bot = 2k/2k+1, bit15) + 자모 40(1275+2i, bit15)
        ents = [(0x8E52, 0x0123, 0x0124), (0x95BD, 0x0200, 0x0201), (0x88EA, 0x0300, 0x0301)]
        self.syl_tiles = {}
        syl_base = g1.CONFIG['jamo_first_tile'] + 2 * len(hc.PREVIEW_JAMO) + 8   # 자모 타일과 겹치지 않게
        for k, (ch, code) in enumerate(sorted(table.items(), key=lambda kv: kv[1])):
            t = syl_base + 2 * k
            ents.append((code, 0x8000 | t, 0x8000 | (t + 1)))
            self.syl_tiles[code] = (t, t + 1)
        jamo_order = hc.PREVIEW_JAMO
        for i, j in enumerate(jamo_order):
            t = g1.CONFIG['jamo_first_tile'] + 2 * i
            ents.append((codes[j], 0x8000 | t, 0x8000 | (t + 1)))
            self.syl_tiles[codes[j]] = (t, t + 1)
        tbl = b''.join(c.to_bytes(2, 'big') + t.to_bytes(2, 'little') + b.to_bytes(2, 'little') for c, t, b in ents)
        self.tbl = ctypes.create_string_buffer(tbl + b'\xEE' * 6, len(tbl) + 6)   # 끝 뒤 6B 는 표 밖(미탐색)
        self.tbl_len = len(tbl)
        ntiles = max(t for pair in self.syl_tiles.values() for t in pair) + 4
        self.kor = ctypes.create_string_buffer(b''.join(fake_glyph(t) for t in range(ntiles)), 32 * ntiles)
        self.cache = ctypes.create_string_buffer(0x620)
        self.vram = (ctypes.c_uint16 * VRAM_HALFWORDS)()
        self.set_dictionary(self.default_dictionary())
        for name, obj in (('nc1_h_tbl_start', self.tbl), ('nc1_h_kor', self.kor), ('nc1_h_cache', self.cache)):
            ctypes.c_void_p.in_dll(self.lib, name).value = ctypes.addressof(obj)
        ctypes.c_void_p.in_dll(self.lib, 'nc1_h_tbl_end').value = ctypes.addressof(self.tbl) + self.tbl_len
        ctypes.c_void_p.in_dll(self.lib, 'nc1_h_vram').value = ctypes.addressof(self.vram)

    @staticmethod
    def default_dictionary():
        return [0x824F, 0x8250, 0x8341, 0x8140] + list(g1.HOST_CODES) + list(g1.PLACEHOLDERS) + [0x97CE]

    def set_dictionary(self, codes, tile_start=FAKE_TILE_START):
        cfg = g1.CONFIG
        ctypes.memset(self.cache, 0x5A, 0x620)
        raw = bytearray(self.cache.raw)
        raw[cfg['cache_count_off']:cfg['cache_count_off'] + 2] = len(codes).to_bytes(2, 'little')
        lo = cfg['cache_list_off']
        for i, c in enumerate(codes):
            raw[lo + 2 * i:lo + 2 * i + 2] = c.to_bytes(2, 'big')
        raw[cfg['cache_tile_off']:cfg['cache_tile_off'] + 2] = tile_start.to_bytes(2, 'little')
        ctypes.memmove(self.cache, bytes(raw), len(raw))
        self.dictionary, self.tile_start = list(codes), tile_start

    def tile_of(self, code):
        return self.tile_start + 2 * self.dictionary.index(code)

    def clear_vram(self):
        ctypes.memset(self.vram, 0xA5, ctypes.sizeof(self.vram))

    def vram_bytes(self, tile, n=2):
        return bytes(ctypes.string_at(ctypes.addressof(self.vram) + tile * 32, 32 * n))

    def vram_all(self):
        return bytes(ctypes.string_at(ctypes.addressof(self.vram), ctypes.sizeof(self.vram)))

    def glyph(self, code):
        t, b = self.syl_tiles[code]
        return fake_glyph(t) + fake_glyph(b)

    def call(self, fn, buf, *args):
        cbuf = ctypes.create_string_buffer(bytes(buf), len(buf))
        rc = getattr(self.lib, fn)(cbuf, *args)
        buf[:] = cbuf.raw[:len(buf)]
        return rc

    def preview(self, buf):
        cbuf = ctypes.create_string_buffer(bytes(buf), len(buf))
        out = ctypes.create_string_buffer(b'\xCC' * 16, 16)
        n = self.lib.nc1_preview_codes(cbuf, out)
        self.assert_obj_unchanged = bytes(cbuf.raw[:len(buf)]) == bytes(buf)
        return n, out.raw[:16]


def obj_with(slots, length, max_slots):
    buf = sentinel_buffer()
    for i, c in enumerate(slots):
        buf[OFF_SLOT + 2 * i:OFF_SLOT + 2 * i + 2] = c.to_bytes(2, 'big')
    buf[OFF_LEN] = length
    buf[OFF_MAX] = max_slots
    return buf


@unittest.skipUnless(shutil.which('clang'), 'host clang unavailable')
class P1Helpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = hc.load_table()
        cls.codes = load_jamo_codes()
        os.makedirs(os.path.join(ROOT, 'temp'), exist_ok=True)
        cls.tmp = tempfile.mkdtemp(dir=os.path.join(ROOT, 'temp'), prefix='name_compose_p1_helpers_')
        cls.p1 = P1Lib(cls.tmp, cls.table, cls.codes)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.p1.set_dictionary(P1Lib.default_dictionary())
        self.p1.clear_vram()

    def syl(self, ch):
        return self.table[ch]

    # ⑥ pad 경계
    def test_6_pad_boundaries(self):
        for max_slots in (6, 8):
            for length in (0, 3, max_slots):
                codes = [self.syl(c) for c in '가나다라마바사아'[:length]]
                buf = obj_with(codes + [0] * (max_slots - length), length, max_slots)
                before = bytes(buf)
                self.p1.call('nc1_pad', buf)
                for i in range(max_slots):
                    got = int.from_bytes(buf[OFF_SLOT + 2 * i:OFF_SLOT + 2 * i + 2], 'big')
                    self.assertEqual(got, codes[i] if i < length else SPACE, (max_slots, length, i))
                end = OFF_SLOT + 2 * max_slots
                self.assertEqual(bytes(buf[:OFF_SLOT]), before[:OFF_SLOT])
                self.assertEqual(bytes(buf[end:]), before[end:], (max_slots, length))
        buf = obj_with([], 0, 12)                       # max>8 은 8 로 잘라 +0x3C 밖을 안 쓴다
        before = bytes(buf)
        self.p1.call('nc1_pad', buf)
        self.assertEqual(bytes(buf[OFF_SLOT:OFF_SLOT + 16]), bytes.fromhex('8140') * 8)
        self.assertEqual(bytes(buf[OFF_SLOT + 16:]), before[OFF_SLOT + 16:])

    def test_6_tail_init(self):
        buf = sentinel_buffer()
        before = bytes(buf)
        self.p1.call('nc1_tail_init', buf)
        self.assertEqual(bytes(buf[OFF_TAIL:OFF_TAIL + 16]), bytes([0, 0xFF, 0xFF, 0]) + bytes(12))
        self.assertEqual(bytes(buf[:OFF_TAIL]), before[:OFF_TAIL])

    def test_korean_tiles_lookup(self):
        top, bot = ctypes.c_uint(0xDEAD), ctypes.c_uint(0xBEEF)
        f = self.p1.lib.nc1_korean_tiles
        self.assertEqual(f(self.syl('가'), ctypes.byref(top), ctypes.byref(bot)), 1)
        self.assertEqual((top.value, bot.value), self.p1.syl_tiles[self.syl('가')])
        self.assertEqual(f(self.codes['ㅣ'], ctypes.byref(top), ctypes.byref(bot)), 1)
        self.assertEqual((top.value, bot.value), (1275 + 2 * 39, 1276 + 2 * 39))
        for code in (0x8E52, 0x95BD, SPACE, 0x824F, 0x834B, 0xEEEE):   # bit15 아님 / 표에 없음 / 표 끝 뒤
            top.value = bot.value = 0x1234
            self.assertEqual(f(code, ctypes.byref(top), ctypes.byref(bot)), 0, hex(code))
            self.assertEqual((top.value, bot.value), (0x1234, 0x1234), hex(code))

    def test_cache_tile(self):
        d = P1Lib.default_dictionary()
        for i, c in enumerate(d):
            self.assertEqual(self.p1.lib.nc1_cache_tile(c), FAKE_TILE_START + 2 * i, hex(c))
        self.assertEqual(self.p1.lib.nc1_cache_tile(self.syl('가')), -1)
        self.p1.set_dictionary(d[:3])                   # count 가 탐색 상한
        self.assertEqual(self.p1.lib.nc1_cache_tile(d[3]), -1)

    # ⑦ 한글/비한글 치환
    def test_7_substitution(self):
        slots = [self.syl('가'), SPACE, 0x824F, self.codes['ㄱ'], 0x834B, 0x8E52, self.syl('힝'), self.syl('한')]
        for max_slots, length in ((6, 6), (8, 8), (8, 5)):
            self.p1.clear_vram()
            buf = obj_with(slots[:max_slots], length, max_slots)
            n, out = self.p1.preview(buf)
            self.assertTrue(self.p1.assert_obj_unchanged)
            self.assertEqual(n, max_slots)
            got = [int.from_bytes(out[2 * i:2 * i + 2], 'big') for i in range(n)]
            want = []
            for i, c in enumerate(slots[:max_slots]):
                korean = c in self.p1.syl_tiles
                want.append(g1.PLACEHOLDERS[i] if korean and i < length else c)
            self.assertEqual(got, want, (max_slots, length))
            self.assertEqual(out[2 * n:], b'\xCC' * (16 - 2 * n))
            for i, c in enumerate(slots[:max_slots]):
                tile = self.p1.tile_of(g1.PLACEHOLDERS[i])
                if c in self.p1.syl_tiles and i < length:
                    self.assertEqual(self.p1.vram_bytes(tile), self.p1.glyph(c), (max_slots, i))
                else:
                    self.assertEqual(self.p1.vram_bytes(tile), b'\xA5' * 64, (max_slots, i))
            for h in g1.HOST_CODES:                     # host 타일은 미리보기가 건드리지 않음
                self.assertEqual(self.p1.vram_bytes(self.p1.tile_of(h)), b'\xA5' * 64)

    def test_7_only_placeholder_tiles_written(self):
        buf = obj_with([self.syl(c) for c in '반가워요'] + [SPACE] * 2, 4, 6)
        self.p1.preview(buf)
        vram = self.p1.vram_all()
        written = {i // 64 for i in range(0, len(vram), 2) if vram[i:i + 2] != b'\xA5\xA5'}
        tiles = {(self.p1.tile_of(g1.PLACEHOLDERS[i]) * 32) // 64 for i in range(4)}
        self.assertEqual(written, tiles)

    # ⑧ placeholder 재사용
    def test_8_placeholder_reuse(self):
        tile = self.p1.tile_of(g1.PLACEHOLDERS[0])
        buf = obj_with([self.codes['ㄱ']] + [SPACE] * 5, 1, 6)
        self.assertEqual(self.p1.preview(buf)[1][:2], g1.PLACEHOLDERS[0].to_bytes(2, 'big'))
        self.assertEqual(self.p1.vram_bytes(tile), self.p1.glyph(self.codes['ㄱ']))
        buf = obj_with([self.syl('가')] + [SPACE] * 5, 1, 6)       # 같은 칸, 다른 글자 → 같은 placeholder 를 덮음
        self.assertEqual(self.p1.preview(buf)[1][:2], g1.PLACEHOLDERS[0].to_bytes(2, 'big'))
        self.assertEqual(self.p1.vram_bytes(tile), self.p1.glyph(self.syl('가')))
        snap = self.p1.vram_all()
        self.p1.preview(buf)                                         # 같은 글자 다시 → 결과 동일
        self.assertEqual(self.p1.vram_all(), snap)
        buf = obj_with([SPACE] * 6, 0, 6)                           # 빈 이름 → 치환·업로드 없음
        self.assertEqual(self.p1.preview(buf)[1][:12], bytes.fromhex('8140') * 6)
        self.assertEqual(self.p1.vram_all(), snap)

    # ⑨ 캐시 부재
    def test_9_placeholder_missing_from_cache(self):
        d = [c for c in P1Lib.default_dictionary() if c != g1.PLACEHOLDERS[1]]
        self.p1.set_dictionary(d)
        buf = obj_with([self.syl('가'), self.syl('나')] + [SPACE] * 4, 2, 6)
        n, out = self.p1.preview(buf)
        self.assertEqual(out[:4], g1.PLACEHOLDERS[0].to_bytes(2, 'big') + self.syl('나').to_bytes(2, 'big'))
        vram = self.p1.vram_all()
        written = {i // 64 for i in range(0, len(vram), 2) if vram[i:i + 2] != b'\xA5\xA5'}
        self.assertEqual(written, {(self.p1.tile_of(g1.PLACEHOLDERS[0]) * 32) // 64})
        self.p1.set_dictionary([])                       # 사전 비었음 → 전부 원 코드, VRAM 무변경
        self.p1.clear_vram()
        n, out = self.p1.preview(buf)
        self.assertEqual(out[:12], b''.join(int.from_bytes(buf[OFF_SLOT + 2 * i:OFF_SLOT + 2 * i + 2], 'big')
                                            .to_bytes(2, 'big') for i in range(6)))
        self.assertEqual(self.p1.vram_all(), b'\xA5' * (2 * VRAM_HALFWORDS))
        self.p1.call('nc1_tail_init', bytearray(128))
        self.p1.lib.nc1_upload_hosts()
        self.assertEqual(self.p1.vram_all(), b'\xA5' * (2 * VRAM_HALFWORDS))

    # ⑩ 업로드 바이트 = KOR 원본
    def test_10_upload_raw_bytes(self):
        self.p1.lib.nc1_upload(0x41, 1275, 1276)
        self.assertEqual(self.p1.vram_bytes(0x41), fake_glyph(1275) + fake_glyph(1276))
        self.assertEqual(self.p1.vram_bytes(0x40, 1), b'\xA5' * 32)
        self.assertEqual(self.p1.vram_bytes(0x43, 1), b'\xA5' * 32)
        self.p1.lib.nc1_upload(0, 7, 3)                  # top/bot 가 연속이 아니어도 각각 복사
        self.assertEqual(self.p1.vram_bytes(0), fake_glyph(7) + fake_glyph(3))

    # ⑪ host 업로드·display_init
    def test_11_display_init_uploads_hosts_and_tail(self):
        buf = sentinel_buffer()
        before = bytes(buf)
        self.p1.call('nc1_display_init', buf)
        self.assertEqual(bytes(buf[OFF_TAIL:OFF_TAIL + 16]), bytes([0, 0xFF, 0xFF, 0]) + bytes(12))
        self.assertEqual(bytes(buf[:OFF_TAIL]), before[:OFF_TAIL])
        expect_tiles = set()
        for j, host in g1.HOST_OF.items():
            tile = self.p1.tile_of(host)
            k = hc.PREVIEW_JAMO.index(j)
            self.assertEqual(self.p1.vram_bytes(tile), fake_glyph(1275 + 2 * k) + fake_glyph(1276 + 2 * k), j)
            expect_tiles |= {tile, tile + 1}
        vram = self.p1.vram_all()
        written = {i // 32 for i in range(0, len(vram), 2) if vram[i:i + 2] != b'\xA5\xA5'}
        self.assertEqual(written, expect_tiles)
        for p in g1.PLACEHOLDERS:
            self.assertEqual(self.p1.vram_bytes(self.p1.tile_of(p)), b'\xA5' * 64)


if __name__ == '__main__':
    unittest.main(verbosity=2)
