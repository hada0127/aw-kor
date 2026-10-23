#!/usr/bin/env python3
"""2편 이름 조합 코어·이미지 테스트 (PLAN-v5 T2).

① 고정 기대표: host 컴파일한 tools/name_compose/core.c(ctypes, 128B 객체 버퍼)를 hangul_compose 와
   mode-scope-re/model-results.json 실측값(아래 상수로 고정)에 대조.
② 시드 20261023 랜덤 20,000 조작: host core.c vs Composer + live adapter 매 스텝 일치.
③ 11,172 음절 표준 키열 전수: 도달 2,345 · 첫 거부 지점에서 버퍼 불변.
④ 이미지: blob CODE/SYMBOLS/SOURCE_SHA 가드(항상) + 툴체인이 있으면 소스 재생성 일치
   (relocation 0 · 미해결 0 · v4T/Thumb-1 · ≤ 8,192 · raw == ELF · 32bit 는 bl 뿐 — build_image.build 검사)
   + 사설 선택표 90셀/표시행이 §1.2·원본 ROM 행 형식과 일치(원본 ROM 이 있을 때).
ROM 삽입·실게임 동작은 이 테스트 범위가 아니다(T3~T5).
"""
import ctypes
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(TOOLS, 'name_compose'))
sys.path.insert(0, TOOLS)

import hangul_compose as hc  # noqa: E402
import gen_tables  # noqa: E402
import part2_name_compose_blob as blob  # noqa: E402
from gen_jamo_assets import dense_table, load_jamo_codes, load_syllable_codes  # noqa: E402

ORIGINAL = os.path.join(ROOT, 'original', 'Game Boy Wars Advance 1+2 (Japan).gba')
MODEL_RESULTS = os.path.join(ROOT, 'temp', 'name-grid-phaseB', 'mode-scope-re', 'model-results.json')
SEL_TABLE_FILE = 0x83FAF6                      # native 선택표(6x15 u16 BE)
NATIVE_ROW_FILES = (0x83FE40, 0x83FE64, 0x83FE88, 0x83FEAC, 0x83FEC4, 0x83FEDC)
SPACE = hc.SPACE_CODE
LITERALS = (0x824F, 0x8250, 0x8251, 0x8252, 0x8253, 0x8254, 0x8255, 0x8256, 0x8257, 0x8258,
            0x8145, 0x8149, 0x8148)
OFF_SLOT, OFF_LEN, OFF_TAIL = 0x2C, 0x61, 0x70
SEED, RANDOM_OPS = 20261023, 20000

# mode-scope-re/model-results.json(sha f93b8c013077…) 실측값. (키열, 스텝별 (수락, preview), confirm 후 16B)
MODEL_CASES = {
    'full8': ('ㄱㅏㄴㅏㄷㅏㄹㅏㅁㅏㅂㅏㅅㅏㅇㅏㄴㄱ',
              [(True, 'ㄱ'), (True, '가'), (True, '간'), (True, '가나'), (True, '가낟'),
               (True, '가나다'), (True, '가나달'), (True, '가나다라'), (True, '가나다람'),
               (True, '가나다라마'), (True, '가나다라맙'), (True, '가나다라마바'),
               (True, '가나다라마밧'), (True, '가나다라마바사'), (True, '가나다라마바상'),
               (True, '가나다라마바사아'), (True, '가나다라마바사안'), (False, '가나다라마바사안')],
              '884088e989e28adf8bc38ca68da98ea2'),
    '한글': ('ㅎㅏㄴㄱㅡㄹ', [(True, 'ㅎ'), (True, '하'), (True, '한'), (True, '한ㄱ'), (True, '한그'),
                        (True, '한글')], '92af888a000000000000000000000000'),
    '강철': ('ㄱㅏㅇㅊㅓㄹ', [(True, 'ㄱ'), (True, '가'), (True, '강'), (True, '강ㅊ'), (True, '강처'),
                        (True, '강철')], '884990d3000000000000000000000000'),
    '붉은달': ('ㅂㅜㄹㄱㅇㅡㄴㄷㅏㄹ',
             [(True, 'ㅂ'), (True, '부'), (True, '불'), (True, '붉'), (True, '붉ㅇ'), (True, '붉으'),
              (True, '붉은'), (True, '붉은ㄷ'), (True, '붉은다'), (True, '붉은달')],
             '8d5c8f7e89e700000000000000000000'),
    '가한-auto': ('ㄱㅏㅎㅏㄴ', [(True, 'ㄱ'), (True, '가'), (True, '갛'), (True, '가하'), (True, '가한')], None),
}
GAH_CODE = 34893                               # model-results 가한-auto.gah_in_2350 (0x884D)


def literal(comp, code):
    """space() 와 같은 규칙의 리터럴 셀(숫자·문장부호) — 참조 모델의 최소 확장."""
    codes = comp.committed.copy()
    if comp.active is not None:
        if not comp.active.complete:
            return hc.Result(False, 'incomplete')
        codes.append(comp.table[comp.active.char])
    return comp._apply(codes + [code], None)


def sentinel_buffer():
    return bytearray((i * 37 + 11) & 0xFF for i in range(128))


class HostCore:
    """같은 core.c 를 host 로 컴파일. nc_dense 는 JSON 에서 만든 실제 배열을 링크한다."""

    def __init__(self, workdir, table):
        gen = gen_tables.generate()
        for name, data in gen.items():
            with open(os.path.join(workdir, name), 'wb') as f:
                f.write(data)
        dense = dense_table(table)
        values = [int.from_bytes(dense[i:i + 2], 'little') for i in range(0, len(dense), 2)]
        with open(os.path.join(workdir, 'dense_host.c'), 'w') as f:
            f.write('#include <stdint.h>\nconst uint16_t nc_dense[11172] = {\n')
            f.write(',\n'.join(','.join(str(v) for v in values[i:i + 28]) for i in range(0, len(values), 28)))
            f.write('\n};\n')
        lib = os.path.join(workdir, 'libnc_host.so')
        subprocess.run(['clang', '-std=c99', '-O2', '-fPIC', '-shared', '-Wall', '-Wextra', '-Werror',
                        '-I', workdir, os.path.join(TOOLS, 'name_compose', 'core.c'),
                        os.path.join(workdir, 'dense_host.c'), '-o', lib],
                       check=True, capture_output=True)
        self.lib = ctypes.CDLL(lib)
        for fn, args in (('nc_press', [ctypes.c_char_p, ctypes.c_uint16]),
                         ('nc_confirm', [ctypes.c_char_p]), ('nc_backspace', [ctypes.c_char_p])):
            getattr(self.lib, fn).argtypes = args
            getattr(self.lib, fn).restype = ctypes.c_int

    def call(self, buf, fn, *args):
        cbuf = ctypes.create_string_buffer(bytes(buf), 128)
        rc = getattr(self.lib, fn)(cbuf, *args)
        buf[:] = cbuf.raw[:128]
        return rc


class CoreHarness:
    def __init__(self, host, table, codes):
        self.host, self.table, self.codes = host, table, codes
        self.decode = {v: k for k, v in table.items()}
        self.decode.update({v: k for k, v in codes.items()})

    def fresh(self, committed=()):
        """constructor 상태: 슬롯 16B 0 + 이름 복사, len, nc_alloc tail 초기값. 나머지는 감시 패턴."""
        buf = sentinel_buffer()
        buf[OFF_SLOT:OFF_SLOT + 16] = bytes(16)
        for i, c in enumerate(committed):
            buf[OFF_SLOT + 2 * i:OFF_SLOT + 2 * i + 2] = c.to_bytes(2, 'big')
        buf[OFF_LEN] = len(committed)
        buf[OFF_TAIL:OFF_TAIL + 16] = bytes([0, 0xFF, 0xFF, 0]) + bytes(12)
        comp = hc.Composer(self.table)
        if committed:
            comp.load(list(committed))
        return buf, comp

    def live_expected(self, comp):
        slots = list(comp.committed)
        a = comp.active
        if a is not None:
            if a.complete:
                slots.append(comp.table[a.char])
            else:
                slots.append(self.codes[hc.L_LIST[a.L]] if a.L is not None else self.codes[hc.V_LIST[a.V]])
        data = b''.join(c.to_bytes(2, 'big') for c in slots).ljust(16, b'\0')
        tail = bytes([1 if a else 0,
                      a.L if a is not None and a.L is not None else 0xFF,
                      a.V if a is not None and a.V is not None else 0xFF,
                      a.T if a is not None else 0]) + bytes(12)
        return data, len(slots), tail

    def check(self, tc, buf, comp, note=''):
        data, length, tail = self.live_expected(comp)
        tc.assertEqual(bytes(buf[OFF_SLOT:OFF_SLOT + 16]), data, note)
        tc.assertEqual(buf[OFF_LEN], length, note)
        tc.assertEqual(bytes(buf[OFF_TAIL:OFF_TAIL + 16]), tail, note)
        ref = sentinel_buffer()
        for i in list(range(0, OFF_SLOT)) + list(range(OFF_SLOT + 16, OFF_LEN)) + list(range(OFF_LEN + 1, OFF_TAIL)):
            if buf[i] != ref[i]:
                tc.fail(f'{note}: byte +0x{i:02X} changed')

    def preview(self, buf):
        n = buf[OFF_LEN]
        return ''.join(self.decode.get(int.from_bytes(buf[OFF_SLOT + 2 * i:OFF_SLOT + 2 * i + 2], 'big'), '?')
                       for i in range(n))

    def op(self, buf, comp, kind, arg=None):
        """(C 반환, 모델 Result). kind: jamo/space/literal/backspace/confirm."""
        if kind == 'jamo':
            return self.host.call(buf, 'nc_press', self.codes[arg]), comp.press(arg)
        if kind == 'space':
            return self.host.call(buf, 'nc_press', SPACE), comp.space()
        if kind == 'literal':
            return self.host.call(buf, 'nc_press', arg), literal(comp, arg)
        if kind == 'backspace':
            return self.host.call(buf, 'nc_backspace'), comp.backspace()
        if kind == 'confirm':
            return self.host.call(buf, 'nc_confirm'), comp.confirm()
        raise ValueError(kind)

    def step(self, tc, buf, comp, kind, arg=None, note=''):
        before = bytes(buf)
        rc, res = self.op(buf, comp, kind, arg)
        tc.assertEqual(rc == 0, res.accepted, f'{note}: {kind} {arg!r} C={rc} model={res}')
        if not res.accepted:
            tc.assertEqual(bytes(buf), before, f'{note}: rejected op changed buffer')
        self.check(tc, buf, comp, note)
        return rc


def _have_host_clang():
    return shutil.which('clang') is not None


@unittest.skipUnless(_have_host_clang(), 'host clang unavailable; blob guards still run')
class CoreBehaviour(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = hc.load_table()
        cls.codes = load_jamo_codes()
        os.makedirs(os.path.join(ROOT, 'temp'), exist_ok=True)
        cls.tmp = tempfile.mkdtemp(dir=os.path.join(ROOT, 'temp'), prefix='name_compose_host_')
        cls.h = CoreHarness(HostCore(cls.tmp, cls.table), cls.table, cls.codes)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def keys(self, buf, comp, keys, note):
        out = []
        for k in keys:
            if k == '!':
                out.append(self.h.step(self, buf, comp, 'confirm', note=note))
            elif k == '<':
                out.append(self.h.step(self, buf, comp, 'backspace', note=note))
            elif k == '_':
                out.append(self.h.step(self, buf, comp, 'space', note=note))
            else:
                out.append(self.h.step(self, buf, comp, 'jamo', k, note=note))
        return out

    def test_model_results_constants_match_research_file(self):
        if not os.path.exists(MODEL_RESULTS):
            self.skipTest('ignored research JSON absent; embedded constants still used')
        with open(MODEL_RESULTS, encoding='utf-8') as f:
            m = json.load(f)
        for name, (keys, steps, ser) in MODEL_CASES.items():
            self.assertEqual(''.join(st['key'] for st in m[name]['steps']), keys, name)
            self.assertEqual([(s['accepted'], s['preview']) for s in m[name]['steps']], steps, name)
            if ser:
                self.assertEqual(m[name]['serialize'], ser, name)
        self.assertEqual(m['가한-auto']['gah_in_2350'], GAH_CODE)

    def test_fixed_model_cases(self):
        for name, (keys, steps, ser) in MODEL_CASES.items():
            buf, comp = self.h.fresh()
            for k, (acc, prev) in zip(keys, steps):
                rc = self.h.step(self, buf, comp, 'jamo', k, note=name)
                self.assertEqual(rc == 0, acc, (name, k))
                self.assertEqual(self.h.preview(buf), prev, (name, k))
            if ser:
                self.assertEqual(self.h.step(self, buf, comp, 'confirm', note=name), 0)
                self.assertEqual(bytes(buf[OFF_SLOT:OFF_SLOT + 16]).hex(), ser, name)
                self.assertEqual(comp.serialize().hex(), ser, name)
        buf, comp = self.h.fresh()
        self.keys(buf, comp, 'ㄱㅏㅎ', '갛')
        self.assertEqual(int.from_bytes(buf[OFF_SLOT:OFF_SLOT + 2], 'big'), GAH_CODE)

    def test_full8_ninth_rejected_and_eighth_active_edit(self):
        buf, comp = self.h.fresh()
        rcs = self.keys(buf, comp, 'ㄱㅏㄴㅏㄷㅏㄹㅏㅁㅏㅂㅏㅅㅏㅇㅏ', 'full8')
        self.assertEqual(rcs, [0] * 16)
        self.assertEqual(buf[OFF_LEN], 8)
        self.assertEqual(self.keys(buf, comp, 'ㄴ', '8th T'), [0])        # 8번째 active 받침 편집
        self.assertEqual(self.h.preview(buf), '가나다라마바사안')
        self.assertEqual(self.keys(buf, comp, 'ㄱ', '9th'), [1])          # no_slot 원자
        self.assertEqual(self.keys(buf, comp, '<', 'edit back'), [0])     # 8번째 active 역삭제
        self.assertEqual(self.h.preview(buf), '가나다라마바사아')

    def test_atomic_rejections_and_migrations(self):
        cases = [('ㄱㅏㅋ', [0, 0, 1], '가'),           # 가+ㅋ 갘 표 밖 → 원자 거부
                 ('ㄱㅐㄷ', [0, 0, 1], '개'),           # 갣 표 밖
                 ('ㄱㅏㄴㅒ', [0, 0, 0, 1], '간'),       # 냬 표 밖 → 간 보존
                 ('ㅎㅏㄴㄱㅏ', [0] * 5, '한가'),
                 ('ㄷㅏㄹㄱㅏ', [0] * 5, '달가'),
                 ('ㄱㅏㅂㅅㅣ', [0] * 5, '갑시'),
                 ('ㅎㅏㄴㅏ', [0] * 4, '하나'),
                 ('ㄱㅏ!ㅋㅏ', [0] * 5, '가카')]          # 명시 확정 경계
        for keys, rcs, prev in cases:
            buf, comp = self.h.fresh()
            self.assertEqual(self.keys(buf, comp, keys, keys), rcs, keys)
            self.assertEqual(self.h.preview(buf), prev, keys)

    def test_compound_vowels_and_clusters_reverse(self):
        for (a, b), r in hc.COMPOUND_VOWELS.items():
            buf, comp = self.h.fresh()                      # V-only 복합
            self.assertEqual(self.keys(buf, comp, a + b, r), [0, 0])
            self.assertEqual(self.h.preview(buf), r)
            self.assertEqual(self.keys(buf, comp, '<', r), [0])
            self.assertEqual(self.h.preview(buf), a)
            li = next(i for i in range(19) if hc.code_for(self.table, i, hc.V_LIST.index(a))
                      and hc.code_for(self.table, i, hc.V_LIST.index(r)))
            buf, comp = self.h.fresh()                      # L+V 복합
            self.assertEqual(self.keys(buf, comp, hc.L_LIST[li] + a + b + '<', r), [0] * 4)
            self.assertEqual(comp.active, hc.Active(li, hc.V_LIST.index(a)))
        for (t1, t2), t in hc.FINAL_CLUSTERS.items():
            ti, tf = hc.T_LIST.index(t1), hc.T_LIST.index(t)
            lv = next((li, vi) for li in range(19) for vi in range(21)
                      if hc.V_LIST[vi] in hc.SELECTABLE_JAMO and hc.code_for(self.table, li, vi)
                      and hc.code_for(self.table, li, vi, ti) and hc.code_for(self.table, li, vi, tf))
            buf, comp = self.h.fresh()
            keys = hc.L_LIST[lv[0]] + hc.V_LIST[lv[1]] + t1 + t2
            self.assertEqual(self.keys(buf, comp, keys, t), [0] * 4, t)
            self.assertEqual(comp.active, hc.Active(lv[0], lv[1], tf))
            self.assertEqual(self.keys(buf, comp, '<', t), [0])
            self.assertEqual(comp.active, hc.Active(lv[0], lv[1], ti))

    def test_reverse_delete_incomplete_reject_literal_legacy(self):
        buf, comp = self.h.fresh()
        self.keys(buf, comp, 'ㄱㅏㅇ', '강')
        for prev in ('가', 'ㄱ', ''):
            self.assertEqual(self.keys(buf, comp, '<', prev), [0])
            self.assertEqual(self.h.preview(buf), prev)
        self.assertEqual(self.keys(buf, comp, '<', 'empty'), [1])
        buf, comp = self.h.fresh()
        self.keys(buf, comp, 'ㄱㅏ!', '가 committed')
        self.assertEqual(self.keys(buf, comp, '<', 'syllable delete'), [0])
        self.assertEqual(buf[OFF_LEN], 0)
        for start in ('ㄱ', 'ㅗ'):                         # 미완성 confirm/space/literal 거부
            buf, comp = self.h.fresh()
            self.keys(buf, comp, start, start)
            self.assertEqual(self.keys(buf, comp, '!_', start), [1, 1])
            self.assertEqual(self.h.step(self, buf, comp, 'literal', 0x8250, note=start), 1)
        buf, comp = self.h.fresh()
        self.keys(buf, comp, 'ㄱㅏ', '가')
        self.assertEqual(self.h.step(self, buf, comp, 'literal', 0x8250, note='lit'), 0)
        self.assertEqual(self.h.step(self, buf, comp, 'space', note='sp'), 0)
        self.assertEqual(bytes(buf[OFF_SLOT:OFF_SLOT + 6]).hex(), '884082508140')
        legacy = [0x8341] * 8                               # ア×8
        buf, comp = self.h.fresh(legacy)
        self.h.check(self, buf, comp, 'legacy load')
        self.assertEqual(self.keys(buf, comp, 'ㄱ', 'legacy full'), [1])
        self.assertEqual(self.keys(buf, comp, '<', 'legacy bs'), [0])
        self.assertEqual(buf[OFF_LEN], 7)
        self.assertEqual(self.keys(buf, comp, 'ㄱㅏ', 'after legacy'), [0, 0])
        buf, comp = self.h.fresh([0x1234, 0xFFFF])
        self.assertEqual(self.keys(buf, comp, '<<<', 'odd legacy'), [0, 0, 1])

    def test_random_20000_ops_match_model(self):
        rng = random.Random(SEED)
        buf, comp = self.h.fresh()
        stats = {'ops': 0, 'rejected': 0}
        for i in range(RANDOM_OPS):
            r = rng.random()
            if r < 0.70:
                kind, arg = 'jamo', rng.choice(hc.SELECTABLE_JAMO)
            elif r < 0.80:
                kind, arg = 'backspace', None
            elif r < 0.86:
                kind, arg = 'confirm', None
            elif r < 0.91:
                kind, arg = 'space', None
            elif r < 0.96:
                kind, arg = 'literal', rng.choice(LITERALS)
            elif r < 0.98:                              # 저장된 확정분으로 재진입
                buf, comp = self.h.fresh(tuple(comp.committed))
                self.h.check(self, buf, comp, f'reload {i}')
                continue
            else:
                buf, comp = self.h.fresh()
                continue
            rc = self.h.step(self, buf, comp, kind, arg, note=f'op {i}')
            stats['ops'] += 1
            stats['rejected'] += rc != 0
        print(f"random_operations={RANDOM_OPS} seed={SEED} applied={stats['ops']} "
              f"rejected={stats['rejected']}")
        self.assertGreater(stats['rejected'], 0)

    def test_exhaustive_11172_standard_keys(self):
        reached = rejected = 0
        supported_unreached = []
        for n in range(11172):
            ch = chr(0xAC00 + n)
            L, V, T = n // 588, (n // 28) % 21, n % 28
            vowel = hc.V_LIST[V]
            keys = [hc.L_LIST[L]] + list(next((a + b for (a, b), r in hc.COMPOUND_VOWELS.items()
                                               if r == vowel), vowel))
            if T:
                final = hc.T_LIST[T]
                keys += list(next((a + b for (a, b), r in hc.FINAL_CLUSTERS.items() if r == final), final))
            buf, comp = self.h.fresh()
            ok = True
            for k in keys:
                before = bytes(buf)
                rc, res = self.h.op(buf, comp, 'jamo', k)
                self.assertEqual(rc == 0, res.accepted, (ch, k))
                if rc:
                    self.assertEqual(bytes(buf), before, (ch, k))
                    ok = False
                    break
                self.h.check(self, buf, comp, ch)
            if ok and self.h.preview(buf) == ch and buf[OFF_LEN] == 1:
                reached += 1
            else:
                rejected += 1
                if ch in self.table:
                    supported_unreached.append(ch)
        print(f'exhaustive=11172 reached={reached} rejected={rejected} '
              f'supported_unreachable={len(supported_unreached)} {"".join(supported_unreached)}')
        self.assertEqual(reached, 2345)
        self.assertEqual(sorted(supported_unreached), sorted('뢨썅쏀쓩쭁'))


class ImageAndBlob(unittest.TestCase):
    """툴체인 없이도 도는 blob 가드 + 툴체인이 있으면 소스 재생성 일치."""

    def test_blob_code_and_sources_guard(self):
        self.assertTrue(blob.verify_code())
        self.assertEqual(blob.check_sources(), [])
        self.assertLessEqual(len(blob.CODE), blob.IMAGE_MAX)
        self.assertEqual((blob.IMAGE_RT, blob.IMAGE_MAX, blob.DENSE_RT), (0x08F75800, 0x2000, 0x08F70000))
        self.assertNotEqual(blob.DENSE_RT, blob.IMAGE_RT)
        for name in blob.FUNC_SYMBOLS:
            self.assertEqual(blob.entry(name) & 1, 1)
            self.assertEqual(blob.entry(name) - 1, blob.IMAGE_RT + blob.SYMBOLS[name])
        with self.assertRaises(KeyError):
            blob.entry('nc_sel_priv')

    def test_private_selection_and_rows_match_plan(self):
        codes = load_jamo_codes()
        grid = gen_tables.selection_grid(codes)
        sel = blob.sel_priv()
        self.assertEqual(len(sel), 180)
        cells = [int.from_bytes(sel[i:i + 2], 'big') for i in range(0, 180, 2)]
        self.assertEqual(cells, [c for row in grid for c in row])
        expect = {(9, 1): SPACE, (10, 2): 0x3131, (11, 2): 0x3232, (12, 2): 0x8145, (13, 2): 0x8149,
                  (14, 2): 0x8148}
        for x in range(10, 15):
            expect[(x, 0)] = 0x824F + x - 10
            expect[(x, 1)] = 0x8254 + x - 10
            expect[(x, 3)], expect[(x, 4)], expect[(x, 5)] = 0x6363, 0x6262, 0x6565
        for x in range(4, 10):
            expect[(x, 3)] = SPACE
        for y in (4, 5):
            for x in range(10):
                expect[(x, y)] = SPACE
        jamo_rows = ('ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅ', 'ㅆㅇㅈㅉㅊㅋㅌㅍㅎ', 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅛ', 'ㅜㅠㅡㅣ')
        for y, row in enumerate(jamo_rows):
            for x, j in enumerate(row):
                expect[(x, y)] = codes[j]
        self.assertEqual(len(expect), 90)
        for (x, y), code in expect.items():
            self.assertEqual(cells[y * 15 + x], code, (x, y))
        rows = blob.row_priv()
        self.assertEqual([len(r) for r in rows], [36, 36, 36, 24, 24, 24])
        mapping = (gen_tables.WIDE_ROW_PAIRS,) * 3 + (gen_tables.NARROW_ROW_PAIRS,) * 3
        for y, row in enumerate(rows):
            self.assertEqual((row[0], row[-1]), (0x09, 0x00))
            pairs = [int.from_bytes(row[1 + 2 * i:3 + 2 * i], 'big') for i in range((len(row) - 2) // 2)]
            for x, p in enumerate(mapping[y]):
                want = {(10, 2): 0x814A, (11, 2): 0x814B}.get((x, y), cells[y * 15 + x])
                self.assertEqual(pairs[p], want, (x, y))
            gaps = (5, 11) if len(pairs) == 17 else (5,)
            for g in gaps:
                self.assertEqual(pairs[g], SPACE, (y, g))
        print('selector_cells=90 display_rows=6 match')

    @unittest.skipUnless(os.path.exists(ORIGINAL), 'original ROM absent')
    def test_classification_identity_and_native_row_format(self):
        with open(ORIGINAL, 'rb') as f:
            rom = f.read()
        sel = blob.sel_priv()
        native = rom[SEL_TABLE_FILE:SEL_TABLE_FILE + 180]
        same = 0
        for i in range(90):
            n, p = native[2 * i:2 * i + 2], sel[2 * i:2 * i + 2]
            if n[0] in gen_tables.ACTION_LEADS:
                self.assertEqual(p, n, f'cell {i} action code must stay native')
                same += 1
            else:
                self.assertNotIn(p[0], gen_tables.ACTION_LEADS, f'cell {i}')
        self.assertEqual(same, 17)                          # 3131·3232 + wide 15
        rows = blob.row_priv()
        mapping = (gen_tables.WIDE_ROW_PAIRS,) * 3 + (gen_tables.NARROW_ROW_PAIRS,) * 3
        for y, (addr, row) in enumerate(zip(NATIVE_ROW_FILES, rows)):
            nat = rom[addr:addr + len(row)]
            self.assertEqual((nat[0], nat[-1], len(row)), (0x09, 0x00, len(row)), y)
            npairs = [nat[1 + 2 * i:3 + 2 * i] for i in range((len(nat) - 2) // 2)]
            ppairs = [row[1 + 2 * i:3 + 2 * i] for i in range((len(row) - 2) // 2)]
            self.assertNotIn(b'\x00', b''.join(npairs)[::2])   # native 행 안에 종료자 없음(길이 동일 근거)
            used = set(mapping[y])
            for p in range(len(npairs)):
                if p not in used:                           # 간격 쌍
                    self.assertEqual(ppairs[p], npairs[p], (y, p))
            for x, p in enumerate(mapping[y]):
                if x >= 10:                                 # 숫자·문장부호·legacy 표시 원본 유지
                    self.assertEqual(ppairs[p], npairs[p], (x, y))

    def test_toolchain_regenerates_identical_blob(self):
        import build_image
        tools = build_image.toolchain()
        if tools is None:
            self.skipTest('toolchain unavailable; SHA guards above still run')
        work = tempfile.mkdtemp(dir=os.path.join(ROOT, 'temp'), prefix='name_compose_img_')
        try:
            result = build_image.build(work, tools)
            self.assertEqual(result['code'], blob.CODE)
            self.assertEqual(result['symbols'], blob.SYMBOLS)
            self.assertEqual(result['source_sha'], blob.SOURCE_SHA)
            with open(build_image.BLOB_PATH, 'rb') as f:
                self.assertEqual(build_image.render_blob(result).encode('utf-8'), f.read())
            print(f"image_bytes={len(result['code'])} insns={result['insn_count']} "
                  f"code_sha={hashlib.sha256(result['code']).hexdigest()}")
        finally:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
