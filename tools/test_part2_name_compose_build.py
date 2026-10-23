"""PLAN-v5 T3: 2편 이름 입력 조합의 빌더 통합 단계를 전체 빌드 없이 검사한다.

fixture = 원본 ROM + 기존 baseline 빌드(이름 조합 이전 산출물). baseline 의 A3 hook 표 end 를
0 으로 되돌려 「hook 을 막 기록한 생성 단계」를 만들고, 빌더와 같은 순서로
_name_compose_a3_max → 표 tail → end 리터럴 → _part2_name_compose 를 적용한다.
연구용 ignored JSON 은 읽지 않는다. ROM 이 없거나 SHA 가 다르면 skip 한다.
"""
import contextlib
import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import build_korean_full as B  # noqa: E402
import build_korean_poc as P  # noqa: E402
import gen_jamo_assets as J  # noqa: E402
import part2_name_compose_blob as BLOB  # noqa: E402

ORIGINAL = ROOT / 'original' / 'Game Boy Wars Advance 1+2 (Japan).gba'
ORIGINAL_SHA = 'a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c'
BASELINE = ROOT / 'output' / 'game_wars_korean_namegrid_baseline_20261023.gba'
BASELINE_SHA = 'ebbca0babca25e4ed9d77c88af0b159fab567c9e8d708bd69a46f281e38a3a8a'

A3 = B.PART2_HOOK_A3_FILE
TABLE_END = 0x08F24494
ACTION = {0x31, 0x32, 0x62, 0x63, 0x65}
SEL_ORIG = 0x83FAF6          # 원본 선택표 6×15 u16 BE
ROW_ORIG = 0x83FE40          # 원본 표시행 6개(연속, 36/36/36/24/24/24B)
DISPLAY_PAIR = (0, 1, 2, 3, 4, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _read(path, sha):
    if not path.is_file():
        return None
    data = path.read_bytes()
    return data if _sha(data) == sha else None


_ORIG = _read(ORIGINAL, ORIGINAL_SHA)
_BASE = _read(BASELINE, BASELINE_SHA)


def _syl_to_code():
    return J.load_syllable_codes(B.SYLCODE)


def _sylmap():
    with open(B.SYLMAP_2350, encoding='utf-8') as f:
        sylmap = json.load(f)['map']
    sylmap['자']['top'] = 1274
    return sylmap


@unittest.skipUnless(_ORIG and _BASE, 'original/baseline ROM missing or SHA mismatch')
class NameComposeBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig, cls.base = _ORIG, _BASE
        cls.syl = _syl_to_code()
        cls.codes = J.load_jamo_codes()
        cls.regions = dict((n, (s, e)) for n, s, e in B.NAME_COMPOSE_WRITES)
        cls.candidate, cls.summary = cls.build_candidate()

    # ---- fixture: 빌더 단계 재현 -------------------------------------------------
    @classmethod
    def a3_stage(cls):
        """build_korean_full 의 PART2_HOOK_A3 기록 직후 상태(표 end 리터럴 0)."""
        rom = bytearray(cls.base)
        struct.pack_into('<I', rom, A3 + B.PART2_HOOK_A3_TABLE_END_OFF, 0)
        assert bytes(rom[A3:A3 + len(B.PART2_HOOK_A3)]) == B.PART2_HOOK_A3
        return rom

    @classmethod
    def table_stage(cls):
        """baseline 의 생성 표(원본 536 + 2350)와 그 원본 표."""
        orig_tbl = bytes(cls.orig[P.KTAB_FILE:P.KTAB_END_FILE])
        new_tbl = bytearray(cls.base[P.NEW_TBL_FILE:P.NEW_TBL_FILE + (536 + 2350) * 6])
        return new_tbl, orig_tbl

    @classmethod
    def write_table(cls, rom, new_tbl):
        """빌더의 표 기록 + end 리터럴 4곳(기존 경로) 재현."""
        rom[P.NEW_TBL_FILE:P.NEW_TBL_FILE + len(new_tbl)] = new_tbl
        P.patch_word(rom, P.LIT_TBL_END, P.NEW_TBL_RT + len(new_tbl))
        struct.pack_into('<I', rom, A3 + B.PART2_HOOK_A3_TABLE_END_OFF, P.NEW_TBL_RT + len(new_tbl))
        for _name, _start, end_lit, *_ in B.PART2_PATCHES:
            P.patch_word(rom, end_lit, P.NEW_TBL_RT + len(new_tbl))

    @classmethod
    def compose_stage(cls):
        """_part2_name_compose 직전 상태(A3 max·표 tail·end 리터럴 완료)."""
        rom = cls.a3_stage()
        B._name_compose_a3_max(rom, cls.syl, cls.orig)
        new_tbl, orig_tbl = cls.table_stage()
        new_tbl += B._name_compose_table_tail(rom, new_tbl, orig_tbl, _sylmap(), cls.syl, cls.orig)
        cls.write_table(rom, new_tbl)
        return rom

    @classmethod
    def build_candidate(cls):
        rom = cls.compose_stage()
        summary = B._part2_name_compose(rom, cls.orig)
        return bytes(rom), summary

    def assertRejectsUnchanged(self, func, rom, *args):
        before = bytes(rom)
        with self.assertRaises((ValueError, AssertionError)):
            func(rom, *args)
        self.assertEqual(bytes(rom), before, 'failed stage must leave rom unchanged')

    # ---- 정상 확장 ---------------------------------------------------------------
    def test_diff_is_subset_of_whitelist(self):
        allowed = set()
        for start, end in self.regions.values():
            allowed.update(range(start, end))
        for literal in B.NAME_COMPOSE_END_LITERALS:
            allowed.update(range(literal, literal + 4))
        diff = {i for i, (a, b) in enumerate(zip(self.base, self.candidate)) if a != b}
        self.assertEqual(len(self.base), len(self.candidate))
        self.assertTrue(diff, 'candidate must differ')
        self.assertFalse(sorted(diff - allowed)[:20])

    def test_every_payload_region_is_exact(self):
        rom = self.candidate
        entry = BLOB.entry
        expected = {
            'jamo_tiles': J.jamo_tiles(),
            'nc_dense': J.dense_table(self.syl),
            'nc_image': BLOB.CODE + bytes(0x2000 - len(BLOB.CODE)),
            'a3_table_tail': J.jamo_table_entries(_sylmap(), self.codes),
            'a3_max': struct.pack('<I', 0xE352),
            's1_press': bytes.fromhex('00480047') + struct.pack('<I', entry('nc_tramp_press')) + bytes.fromhex('c046'),
            's2_confirm': bytes.fromhex('00480047') + struct.pack('<I', entry('nc_tramp_confirm')),
            's3_backspace': bytes.fromhex('01480047c046') + struct.pack('<I', entry('nc_tramp_backspace')),
            'd1_display': bytes.fromhex('004b1847') + struct.pack('<I', entry('nc_tramp_display')),
            'p1_alloc': struct.pack('<I', entry('nc_alloc')),
        }
        self.assertEqual(set(expected), set(self.regions))
        for name, (start, end) in self.regions.items():
            with self.subTest(region=name):
                self.assertEqual(rom[start:end], expected[name])
        # 원본 사이트는 실제로 바뀌었다(빠진 영역 없음)
        for name, original in B.NAME_COMPOSE_SITES:
            start, end = self.regions[name]
            self.assertNotEqual(rom[start:end], original)
        self.assertEqual(self.summary['table_end'], '0x08F24494')
        self.assertEqual(self.summary['a3_max'], '0xE352')
        self.assertEqual(self.summary['code_sha256'], BLOB.CODE_SHA)

    def test_site_literals_are_word_aligned_thumb_entries(self):
        rom = self.candidate
        for name, literal in (('s1_press', 0x34B0C0), ('s2_confirm', 0x34B088),
                              ('s3_backspace', 0x34B214), ('d1_display', 0x34AB40), ('p1_alloc', 0x83FD58)):
            with self.subTest(site=name):
                self.assertEqual(literal % 4, 0)
                value = struct.unpack_from('<I', rom, literal)[0]
                self.assertEqual(value & 1, 1)
                offset = (value & ~1) - BLOB.IMAGE_RT
                self.assertIn(offset, {BLOB.SYMBOLS[s] for s in BLOB.FUNC_SYMBOLS})

    def test_a3_min_max_mask_and_end_literals(self):
        rom = self.candidate
        u32 = lambda a: struct.unpack_from('<I', rom, a)[0]
        self.assertEqual(u32(A3 + 0x80), 0x8840)
        self.assertEqual(u32(A3 + 0x84), max(*self.syl.values(), *self.codes.values()))
        self.assertGreaterEqual(u32(A3 + 0x84), max(*self.syl.values(), *self.codes.values()))
        self.assertEqual(u32(A3 + 0x88), P.NEW_TBL_RT)
        self.assertEqual(u32(A3 + 0x90), 0x7FFF)
        self.assertEqual(bytes(rom[0xF30310:0xF30314]), bytes.fromhex('ff7f0000'))
        for literal in (0xEFE974, 0xF3030C, 0x314000, 0xB11E28):
            with self.subTest(literal=hex(literal)):
                self.assertEqual(u32(literal), TABLE_END)
        self.assertEqual(B._verify_part2_name_compose(bytearray(rom), self.orig)['table_end'], '0x08F24494')

    def test_table_prefix_and_jamo_entries(self):
        rom = self.candidate
        self.assertEqual(rom[P.NEW_TBL_FILE:0xF243A4], self.base[P.NEW_TBL_FILE:0xF243A4])
        self.assertEqual(rom[P.NEW_TBL_FILE:P.NEW_TBL_FILE + 536 * 6], self.orig[P.KTAB_FILE:P.KTAB_END_FILE])
        tail = rom[0xF243A4:0xF24494]
        for i, (jamo, code) in enumerate(self.codes.items()):
            with self.subTest(jamo=jamo):
                self.assertEqual(tail[i * 6:i * 6 + 2], code.to_bytes(2, 'big'))
                self.assertEqual(struct.unpack_from('<HH', tail, i * 6 + 2),
                                 ((1275 + 2 * i) | 0x8000, (1276 + 2 * i) | 0x8000))

    def test_shared_tables_kana_and_reserved_tiles_unchanged(self):
        rom, base = self.candidate, self.base
        for start, end in ((SEL_ORIG, 0x83FBAA), (ROW_ORIG, 0x83FEF4), (0x34AC24, 0x34AC3C),
                           (0xB974D0, 0xBAF338), (0xF09F20, 0xF09F60), (0xF00000, 0xF09F20),
                           (0x83FD78, 0x83FD7C), (0x83FDE0, 0x83FDE4), (0x83FD28, 0x83FD2C),
                           (0x34AFAE, 0x34AFB8), (0xA3C7E8, 0xA3C7F0)):
            with self.subTest(range=hex(start)):
                self.assertEqual(rom[start:end], base[start:end])
        self.assertEqual(rom[0xF09F20:0xF09F40], bytes(32))      # tile 1273 blank
        self.assertTrue(any(rom[0xF09F40:0xF09F60]))            # tile 1274 private 자

    def test_private_selector_keeps_90_cell_classification(self):
        start = self.regions['nc_image'][0] + BLOB.SYMBOLS['nc_sel_priv']
        sel = self.candidate[start:start + 180]
        self.assertEqual(sel, BLOB.sel_priv())
        for cell in range(90):
            original = self.orig[SEL_ORIG + 2 * cell:SEL_ORIG + 2 * cell + 2]
            private = sel[2 * cell:2 * cell + 2]
            with self.subTest(cell=cell):
                if original[0] in ACTION:
                    self.assertEqual(private, original)
                else:
                    self.assertNotIn(private[0], ACTION)

    def test_private_rows_match_selector_and_native_format(self):
        image = self.candidate[0xF75800:0xF77800]
        offset, sel = BLOB.SYMBOLS['nc_row_priv'], BLOB.sel_priv()
        jamo = {c.to_bytes(2, 'big') for c in self.codes.values()}
        original_offset = ROW_ORIG
        for y, length in enumerate((36, 36, 36, 24, 24, 24)):
            row = image[offset:offset + length]
            native = self.orig[original_offset:original_offset + length]
            offset += length
            original_offset += length
            with self.subTest(row=y):
                self.assertEqual((row[0], row[-1]), (0x09, 0))
                self.assertEqual((native[0], native[-1]), (0x09, 0))
                pairs = [row[1 + 2 * i:3 + 2 * i] for i in range((length - 2) // 2)]
                natives = [native[1 + 2 * i:3 + 2 * i] for i in range((length - 2) // 2)]
                width = 15 if y < 3 else 10
                mapped = {DISPLAY_PAIR[x] for x in range(width)}
                for x in range(width):
                    cell = sel[2 * (y * 15 + x):2 * (y * 15 + x) + 2]
                    pair = pairs[DISPLAY_PAIR[x]]
                    if cell in jamo or cell == bytes.fromhex('8140'):
                        self.assertEqual(pair, cell, (y, x))
                    else:
                        self.assertEqual(pair, natives[DISPLAY_PAIR[x]], (y, x))
                for i, pair in enumerate(pairs):
                    if i not in mapped:
                        self.assertEqual(pair, natives[i], ('gap', y, i))
        self.assertEqual(sel[2 * (2 * 15 + 10):2 * (2 * 15 + 12)], bytes.fromhex('31313232'))

    def test_deny_region_and_constants(self):
        self.assertEqual(B.in_deny(0xF70000, 0xF70002), 'part2_name_compose')
        self.assertEqual(B.in_deny(0xF777FE, 0xF77800), 'part2_name_compose')
        self.assertNotEqual(B.in_deny(0xF77800, 0xF77802), 'part2_name_compose')
        spans = sorted((s, e) for s, e in self.regions.values())
        for (s1, e1), (s2, _e2) in zip(spans, spans[1:]):
            self.assertLessEqual(e1, s2)
        for literal in B.NAME_COMPOSE_END_LITERALS:
            self.assertFalse(any(s < literal + 4 and literal < e for s, e in spans))
        self.assertEqual(self.regions['nc_image'], (0xF75800, 0xF77800))
        self.assertEqual(self.regions['nc_dense'], (0xF70000, 0xF70000 + BLOB.DENSE_BYTES))

    # ---- 거부·원자성 ------------------------------------------------------------
    def test_compose_rejects_tampered_original_or_current_site(self):
        for name, original in B.NAME_COMPOSE_SITES:
            start, _end = self.regions[name]
            with self.subTest(orig_site=name):
                orig = bytearray(self.orig)
                orig[start] ^= 1
                self.assertRejectsUnchanged(B._part2_name_compose, self.compose_stage(), bytes(orig))
            with self.subTest(rom_site=name):
                rom = self.compose_stage()
                rom[start + len(original) - 1] ^= 1
                self.assertRejectsUnchanged(B._part2_name_compose, rom, self.orig)
        for start, _value in B.NAME_COMPOSE_KEEP:
            with self.subTest(keep=hex(start)):
                rom = self.compose_stage()
                rom[start] ^= 1
                self.assertRejectsUnchanged(B._part2_name_compose, rom, self.orig)

    def test_compose_rejects_occupied_regions(self):
        for offset in (0xF09F60, 0xF0A95F, 0xF70000, 0xF75747, 0xF75750, 0xF75800, 0xF777FF, 0xF09F20):
            with self.subTest(offset=hex(offset)):
                rom = self.compose_stage()
                rom[offset] ^= 0x10
                self.assertRejectsUnchanged(B._part2_name_compose, rom, self.orig)

    def test_compose_requires_earlier_stages(self):
        cases = {
            'a3_max_not_widened': (A3 + 0x84, struct.pack('<I', 0xE2A7)),
            'tail_missing': (0xF243A4, bytes(0xF0)),
            'end_literal_old': (0xB11E28, struct.pack('<I', 0x08F243A4)),
            'a3_mask': (A3 + 0x90, bytes.fromhex('ff7e0000')),
        }
        for label, (offset, data) in cases.items():
            with self.subTest(case=label):
                rom = self.compose_stage()
                rom[offset:offset + len(data)] = data
                self.assertRejectsUnchanged(B._part2_name_compose, rom, self.orig)
        with self.subTest(case='twice'):
            self.assertRejectsUnchanged(B._part2_name_compose, bytearray(self.candidate), self.orig)

    def test_final_verify_rejects_one_byte_change(self):
        for offset in (0xF09F60, 0xF70002, 0xF75800, 0xF77000, 0xF243A4, A3 + 0x84, A3 + 0x85,
                       0x34B0C0, 0x34B084, 0x34B214, 0x34AB3C, 0x83FD58, 0xEFE974, 0x314000):
            with self.subTest(offset=hex(offset)):
                rom = bytearray(self.candidate)
                rom[offset] ^= 1
                with self.assertRaises(AssertionError):
                    B._verify_part2_name_compose(rom, self.orig)

    def test_a3_max_stage(self):
        rom = self.a3_stage()
        self.assertEqual(B._name_compose_a3_max(rom, self.syl, self.orig), 0xE352)
        self.assertEqual(struct.unpack_from('<I', rom, 0xF30304)[0], 0xE352)
        for offset in (A3, A3 + 0x80, 0xF30304, 0xF30306, A3 + B.PART2_HOOK_A3_TABLE_END_OFF, 0xF30310):
            with self.subTest(offset=hex(offset)):
                rom = self.a3_stage()
                rom[offset] ^= 1
                self.assertRejectsUnchanged(B._name_compose_a3_max, rom, self.syl, self.orig)
        with self.subTest(case='already widened'):
            rom = self.a3_stage()
            B._name_compose_a3_max(rom, self.syl, self.orig)
            self.assertRejectsUnchanged(B._name_compose_a3_max, rom, self.syl, self.orig)

    def test_table_tail_stage(self):
        sylmap = _sylmap()
        rom = self.a3_stage()
        new_tbl, orig_tbl = self.table_stage()
        tail = B._name_compose_table_tail(rom, new_tbl, orig_tbl, sylmap, self.syl, self.orig)
        self.assertEqual(len(tail), 240)
        self.assertEqual(len(new_tbl), (536 + 2350) * 6)

        def reject(rom, new_tbl, orig_tbl, sylmap):
            before = bytes(new_tbl)
            self.assertRejectsUnchanged(B._name_compose_table_tail, rom, new_tbl, orig_tbl, sylmap,
                                        self.syl, self.orig)
            self.assertEqual(bytes(new_tbl), before)

        for offset in (0, 536 * 6, 536 * 6 + 3, len(new_tbl) - 1):
            with self.subTest(table_byte=offset):
                bad = bytearray(new_tbl)
                bad[offset] ^= 1
                reject(self.a3_stage(), bad, orig_tbl, sylmap)
        with self.subTest(case='short table'):
            reject(self.a3_stage(), bytearray(new_tbl[:-6]), orig_tbl, sylmap)
        with self.subTest(case='orig table changed'):
            reject(self.a3_stage(), new_tbl, orig_tbl[:-1] + bytes([orig_tbl[-1] ^ 1]), sylmap)
        with self.subTest(case='자 top not private'):
            changed = _sylmap()
            changed['자']['top'] = 119
            reject(self.a3_stage(), new_tbl, orig_tbl, changed)
        for offset in (0xF243A4, 0xF24493):
            with self.subTest(tail_region=hex(offset)):
                rom = self.a3_stage()
                rom[offset] = 1
                reject(rom, new_tbl, orig_tbl, sylmap)

    def assertAllStagesReject(self, patches, needle=None):
        """같은 변조 입력에서 세 단계가 모두 거부하고 rom·new_tbl 을 바꾸지 않는다."""
        compose, a3 = self.compose_stage(), self.a3_stage()
        new_tbl, orig_tbl = self.table_stage()
        table_before = bytes(new_tbl)
        calls = ((B._part2_name_compose, compose, (self.orig,)),
                 (B._name_compose_a3_max, a3, (self.syl, self.orig)),
                 (B._name_compose_table_tail, a3, (new_tbl, orig_tbl, _sylmap(), self.syl, self.orig)))
        with contextlib.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            for func, rom, args in calls:
                before = bytes(rom)
                with self.assertRaises(ValueError) as caught:
                    func(rom, *args)
                if needle:
                    self.assertIn(needle, str(caught.exception))
                self.assertEqual(bytes(rom), before)
        self.assertEqual(bytes(new_tbl), table_before)

    def test_inputs_reject_stale_oversize_or_tampered_assets(self):
        sha = dict(BLOB.SOURCE_SHA, **{'tools/name_compose/core.c': '0' * 64})
        big = BLOB.CODE + bytes(0x2001 - len(BLOB.CODE))
        for label, patches, needle in (
                ('source sha', [mock.patch.object(BLOB, 'SOURCE_SHA', sha)], 'stale'),
                ('code sha', [mock.patch.object(BLOB, 'CODE_SHA', '0' * 64)], 'sha'),
                ('image > 8192', [mock.patch.object(BLOB, 'CODE', big),
                                  mock.patch.object(BLOB, 'CODE_SHA', _sha(big))], 'IMAGE_MAX')):
            with self.subTest(case=label):
                self.assertAllStagesReject(patches, needle)
        codes = {j: f'0x{c:04X}' for j, c in self.codes.items()}
        from build_korean2350 import extend_pool
        pool = set(extend_pool(self.orig))
        outside = next(c for c in range(0x8840, 0xEAFD)
                       if (c & 0xFF) >= 0x40 and c not in pool and c not in set(self.syl.values()))
        swapped = dict(codes)
        swapped['ㄱ'], swapped['ㄲ'] = codes['ㄲ'], codes['ㄱ']
        not_pool = dict(codes, **{'ㄱ': f'0x{outside:04X}'})
        in_2350 = dict(codes, **{'ㄱ': f'0x{self.syl["가"]:04X}'})
        tmp_root = ROOT / 'temp'
        tmp_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=tmp_root) as tmp:
            for label, value, needle in (('swapped', swapped, 'compiled'), ('outside pool', not_pool, 'pool'),
                                         ('2350 overlap', in_2350, '2350')):
                with self.subTest(json=label):
                    path = Path(tmp) / f'{label}.json'
                    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
                    self.assertAllStagesReject([mock.patch.object(J, 'OUT_CODES', str(path))], needle)
            with self.subTest(glyphs='no ink'):
                path = Path(tmp) / 'glyphs.bin'
                data = bytearray(J.jamo_tiles())
                data[0:64] = bytes(64)
                path.write_bytes(data)
                rom = self.compose_stage()
                with mock.patch.object(J, 'OUT_GLYPHS', str(path)):
                    self.assertRejectsUnchanged(B._part2_name_compose, rom, self.orig)


if __name__ == '__main__':
    unittest.main()
