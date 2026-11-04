"""PLAN B T4: 1편 이름 입력 조합(Phase C)의 빌더 통합 단계를 검사한다.

정적 검사는 원본 ROM 만 있으면 돈다(상수·payload·사설 선택표 90셀 분류·표시행·사전 목록·DENY).
fixture 검사는 빌더가 만든 최종 ROM(--rom)이 필요하다. 그 ROM 에서 P1_NAME_COMPOSE_WRITES 영역만
원래대로(사이트 = 원본 바이트, 코드 이미지 = 0) 되돌려 「_part1_name_compose 직전 단계」를 만들고,
같은 함수를 다시 적용하면 바이트 동일한지와 변조 입력 거부·원자성을 본다. --base(이 기능 이전
빌드)를 주면 후보−baseline 차이가 1편 이름 조합 영역과 trim 훅 영역 안에만 있는지도 본다.

  python3 -B tools/test_part1_name_compose_build.py [--rom CANDIDATE.gba] [--base BASELINE.gba] [-v]

--rom 이 없으면 output/game_wars_korean_p1compose_20261104.gba 가 있을 때 그것을 쓰고, 없으면
fixture 검사는 skip 한다(정적 검사만 돈다).
"""
import argparse
import hashlib
import struct
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tools' / 'name_compose'))

import build_korean_full as B  # noqa: E402
import build_korean_poc as P  # noqa: E402
import gen_jamo_assets as J  # noqa: E402
import gen_tables as GT  # noqa: E402
import hangul_compose as HC  # noqa: E402
import part1_name_compose_blob as BLOB  # noqa: E402

ORIGINAL = ROOT / 'original' / 'Game Boy Wars Advance 1+2 (Japan).gba'
ORIGINAL_SHA = 'a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c'
DEFAULT_CANDIDATE = ROOT / 'output' / 'game_wars_korean_p1compose_20261104.gba'

ACTION = set(GT.ACTION_LEADS)
SEL_NATIVE = 0xDF9F5C           # 1편 native 선택표 6×15 u16 BE
TRIM_SPAN = (B.PART1_NAME_TRIM_HOOK_FILE, B.PART1_NAME_TRIM_HOOK_FILE + B.PART1_NAME_TRIM_HOOK_SPAN)
EXPECTED_WRITES = (
    ('p1_image', 0xF77800, 0xF79800), ('h1_press', 0xB49018, 0xB49022),
    ('h2_confirm', 0xB48FE4, 0xB48FEC), ('h3_backspace', 0xB49162, 0xB4916C),
    ('h4_display', 0xB488FE, 0xB48908), ('h5_preview', 0xB48E50, 0xB48E58),
    ('h6_alloc', 0xB4985C, 0xB4985E), ('h7_lr', 0xB49180, 0xB49182),
)
# 사이트 → (리터럴 파일 오프셋, 진입 심볼). 리터럴은 4정렬, Thumb bit.
SITE_LITERALS = (
    ('h1_press', 0xB4901C, 'nc1_tramp_press'), ('h2_confirm', 0xB48FE8, 'nc1_tramp_confirm'),
    ('h3_backspace', 0xB49168, 'nc1_tramp_backspace'), ('h4_display', 0xB48904, 'nc1_tramp_display'),
    ('h5_preview', 0xB48E54, 'nc1_preview'),
)
# skipUnless 는 클래스 정의 때 평가되므로 인자를 import 시점에 읽는다(unittest 인자는 그대로 넘긴다).
_AP = argparse.ArgumentParser(add_help=False)
_AP.add_argument('--rom')
_AP.add_argument('--base')
_ARGS, _REST = _AP.parse_known_args(sys.argv[1:] if __name__ == '__main__' else [])
ROM_PATH, BASE_PATH = _ARGS.rom, _ARGS.base


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _read(path, sha=None):
    if not path or not Path(path).is_file():
        return None
    data = Path(path).read_bytes()
    return data if sha is None or _sha(data) == sha else None


_ORIG = _read(ORIGINAL, ORIGINAL_SHA)


def _candidate_path():
    if ROM_PATH:
        return Path(ROM_PATH)
    return DEFAULT_CANDIDATE if DEFAULT_CANDIDATE.is_file() else None


def _u16be(data, off):
    return int.from_bytes(data[off:off + 2], 'big')


@unittest.skipUnless(_ORIG, 'original ROM missing or SHA mismatch')
class StaticTests(unittest.TestCase):
    """원본 ROM·blob·빌더 상수만으로 도는 검사."""

    def test_regions_constants_and_deny(self):
        self.assertEqual(B.P1_NAME_COMPOSE_WRITES, EXPECTED_WRITES)
        spans = sorted((s, e) for _n, s, e in B.P1_NAME_COMPOSE_WRITES)
        for (_s1, e1), (s2, _e2) in zip(spans, spans[1:]):
            self.assertLessEqual(e1, s2)
        # 2편 영역·trim 훅 영역과 겹치지 않는다.
        others = [(s, e) for _n, s, e in B.NAME_COMPOSE_WRITES] + [TRIM_SPAN]
        for s, e in spans:
            self.assertFalse([o for o in others if s < o[1] and o[0] < e], hex(s))
        self.assertEqual(B.in_deny(0xF77800, 0xF77802), 'part1_name_compose')
        self.assertEqual(B.in_deny(0xF797FE, 0xF79800), 'part1_name_compose')
        self.assertEqual(B.in_deny(0xF777FE, 0xF77800), 'part2_name_compose')
        self.assertNotEqual(B.in_deny(0xF79800, 0xF79802), 'part1_name_compose')
        self.assertIn(('part1_name_compose', 0xF77800, 0xF79800), B.DENY_REGIONS)

    def test_sites_and_keep_match_original(self):
        regions = B.P1_NAME_COMPOSE_REGIONS
        self.assertEqual({n for n, _ in B.P1_NAME_COMPOSE_SITES}, set(regions) - {'p1_image'})
        for name, original in B.P1_NAME_COMPOSE_SITES:
            start, end = regions[name]
            with self.subTest(site=name):
                self.assertEqual(len(original), end - start)
                self.assertEqual(_ORIG[start:end], original)
        for start, value in B.P1_NAME_COMPOSE_KEEP:
            with self.subTest(keep=hex(start)):
                self.assertEqual(_ORIG[start:start + len(value)], value)
        self.assertFalse(any(_ORIG[0xF77800:0xF79800]))

    def test_payload_shapes_and_entries(self):
        payload = B._p1_name_compose_payload()
        self.assertEqual(set(payload), set(B.P1_NAME_COMPOSE_REGIONS))
        self.assertEqual(payload['p1_image'][:len(BLOB.CODE)], BLOB.CODE)
        self.assertFalse(any(payload['p1_image'][len(BLOB.CODE):]))
        self.assertEqual(payload['h6_alloc'], bytes.fromhex('8020'))   # movs r0,#0x80
        self.assertEqual(payload['h7_lr'], bytes.fromhex('2be0'))      # b 0x08B491DA
        self.assertEqual(payload['h1_press'][8:], bytes.fromhex('c046'))
        self.assertEqual(payload['h3_backspace'][:2], bytes.fromhex('c046'))
        self.assertEqual(payload['h4_display'][:2], bytes.fromhex('c046'))
        regions = B.P1_NAME_COMPOSE_REGIONS
        for name, literal, sym in SITE_LITERALS:
            start, _end = regions[name]
            data = payload[name]
            ldr = data.index(bytes.fromhex('004b1847'))
            with self.subTest(site=name):
                self.assertEqual(literal % 4, 0)
                self.assertEqual((start + ldr) % 4, 0)          # ldr r3,[pc,#0] 가 바로 뒤 워드를 읽는다
                self.assertEqual(start + ldr + 4, literal)
                value = struct.unpack_from('<I', data, literal - start)[0]
                self.assertEqual(value, BLOB.entry(sym))
                self.assertEqual(value & 1, 1)
                self.assertEqual((value & ~1) % 4, 0)
                self.assertTrue(BLOB.IMAGE_RT <= value & ~1 < BLOB.IMAGE_RT + len(BLOB.CODE))
        with self.assertRaises(ValueError):
            B._p1_far_tramp(0x08F77800, 0xB49018)       # Thumb bit 없음
        with self.assertRaises(ValueError):
            B._p1_far_tramp(0x08F77801, 0xB49019)       # 홀수 사이트

    def test_entries_documented_in_brief(self):
        want = {'nc1_tramp_press': 0x08F77801, 'nc1_tramp_confirm': 0x08F778A1,
                'nc1_tramp_backspace': 0x08F77915, 'nc1_tramp_display': 0x08F7795D,
                'nc1_preview': 0x08F77A41}
        for sym, value in want.items():
            with self.subTest(sym=sym):
                self.assertEqual(BLOB.entry(sym), value)

    def test_inputs_and_config(self):
        self.assertIs(B._p1_name_compose_inputs(_ORIG, _ORIG), BLOB)
        self.assertEqual(BLOB.CONFIG['tbl_start'], P.NEW_TBL_RT)
        self.assertEqual(BLOB.CONFIG['tbl_end'], P.NEW_TBL_RT + 2926 * 6)
        self.assertEqual(BLOB.CONFIG['jamo_first_tile'], J.FIRST_TILE)
        self.assertEqual(struct.unpack_from('<I', _ORIG, 0xBE7280)[0], 0x02012D44)
        self.assertEqual(BLOB.check_sources(), [])

    def test_trim_constant_premise(self):
        self.assertEqual(len(B.PART1_NAME_TRIM_HOOK), 58)
        self.assertEqual(B.PART1_NAME_TRIM_HOOK_SPAN, 70)
        halves = {B.PART1_NAME_TRIM_HOOK[i:i + 2] for i in range(0, 58, 2)}
        self.assertNotIn(bytes.fromhex('8f28'), halves)
        self.assertNotIn(bytes.fromhex('5a28'), halves)

    def test_private_selector_keeps_90_cell_classification(self):
        sel = BLOB.sel_priv()
        self.assertEqual(len(sel), 180)
        for cell in range(90):
            native = _ORIG[SEL_NATIVE + 2 * cell:SEL_NATIVE + 2 * cell + 2]
            private = sel[2 * cell:2 * cell + 2]
            with self.subTest(cell=(cell % 15, cell // 15)):
                if native[0] in ACTION:
                    self.assertEqual(private, native)
                else:
                    self.assertNotIn(private[0], ACTION)

    def test_display_rows_format_and_dictionary(self):
        lists = [B._p1_dict_list(_ORIG, s, n) for s, n in B.P1_NAME_DICT_LISTS]
        in_dict = {c for codes in lists for c in codes}
        codes = J.load_jamo_codes()
        host = {codes[HC.PREVIEW_JAMO[index]]: code for index, code in BLOB.host_tab()}
        self.assertEqual(len(host), 33)
        sel = BLOB.sel_priv()
        rows = BLOB.row_priv()
        self.assertEqual(tuple(len(r) for r in rows), (40, 40, 40, 28, 28, 28))
        for y, row in enumerate(rows):
            with self.subTest(row=y):
                self.assertEqual(row[:2], b'\x0a\x09')
                self.assertEqual(row[-4:], b'\x0a\x00\x00\x00')
                pairs = [_u16be(row, 2 + 2 * i) for i in range((len(row) - 6) // 2)]
                mapping = GT.WIDE_ROW_PAIRS if len(pairs) == 17 else GT.NARROW_ROW_PAIRS
                for x, p in enumerate(mapping):
                    c = _u16be(sel, 2 * (y * 15 + x))
                    if (x, y) in ((10, 2), (11, 2)):
                        self.assertEqual(pairs[p], {10: 0x8168, 11: 0x814B}[x])
                    elif c in host:
                        self.assertEqual(pairs[p], host[c], (x, y))
                    else:
                        self.assertEqual(pairs[p], c, (x, y))
                for i, p in enumerate(pairs):
                    if i not in mapping:
                        self.assertEqual(p, 0x8140, ('gap', i))
                    # 표시 코드는 사전에 있거나 공백이어야 그려진다(T0 NR-1).
                    self.assertTrue(p == 0x8140 or p in in_dict, hex(p))

    def test_host_and_placeholder_codes_in_dictionary(self):
        lists = [B._p1_dict_list(_ORIG, s, n) for s, n in B.P1_NAME_DICT_LISTS]
        self.assertEqual([len(x) for x in lists], [40, 31, 26, 16])
        hosts = [c for _i, c in BLOB.host_tab()]
        places = list(BLOB.placeholders())
        self.assertEqual(len(set(hosts + places)), 41)
        self.assertLessEqual(set(places), set(lists[3]))
        self.assertLessEqual(set(hosts), set(lists[2]) | set(lists[3]))
        self.assertFalse(set(hosts + places) & (set(lists[0]) | set(lists[1])))

    def test_inputs_reject_stale_or_tampered_blob(self):
        sha = dict(BLOB.SOURCE_SHA, **{'tools/name_compose_p1/p1.c': '0' * 64})
        big = BLOB.CODE + bytes(0x2001 - len(BLOB.CODE))
        cases = (
            ('source sha', [mock.patch.object(BLOB, 'SOURCE_SHA', sha)], 'stale'),
            ('code sha', [mock.patch.object(BLOB, 'CODE_SHA', '0' * 64)], 'sha'),
            ('image > 8192', [mock.patch.object(BLOB, 'CODE', big),
                              mock.patch.object(BLOB, 'CODE_SHA', _sha(big))], 'IMAGE_MAX'),
            ('image rt', [mock.patch.object(BLOB, 'IMAGE_RT', 0x08F77000)], 'layout'),
            ('config value', [mock.patch.object(BLOB, 'CONFIG', dict(BLOB.CONFIG, cache_bank=2))], 'cache_bank'),
            ('config key', [mock.patch.object(BLOB, 'CONFIG', dict(BLOB.CONFIG, extra=1))], 'keys'),
        )
        for label, patches, needle in cases:
            with self.subTest(case=label):
                for p in patches:
                    p.start()
                try:
                    with self.assertRaises(ValueError) as caught:
                        B._p1_name_compose_inputs(_ORIG, _ORIG)
                    self.assertIn(needle, str(caught.exception))
                finally:
                    for p in patches:
                        p.stop()


@unittest.skipUnless(_ORIG and _candidate_path(), 'no --rom candidate (or original ROM missing)')
class FixtureTests(unittest.TestCase):
    """빌더가 만든 최종 ROM 에서 직전 단계를 복원해 단계 함수를 다시 적용한다."""

    @classmethod
    def setUpClass(cls):
        cls.orig = _ORIG
        cls.candidate = Path(_candidate_path()).read_bytes()
        cls.regions = B.P1_NAME_COMPOSE_REGIONS

    @classmethod
    def pre_stage(cls):
        rom = bytearray(cls.candidate)
        for name, original in B.P1_NAME_COMPOSE_SITES:
            start, end = cls.regions[name]
            rom[start:end] = original
        start, end = cls.regions['p1_image']
        rom[start:end] = bytes(end - start)
        return rom

    def assertRejectsUnchanged(self, rom, orig=None, needle=None):
        before = bytes(rom)
        with self.assertRaises(ValueError) as caught:
            B._part1_name_compose(rom, self.orig if orig is None else orig)
        if needle:
            self.assertIn(needle, str(caught.exception))
        self.assertEqual(bytes(rom), before, 'failed stage must leave rom unchanged')

    def test_candidate_passes_final_verify(self):
        summary = B._verify_part1_name_compose(bytearray(self.candidate), self.orig)
        self.assertEqual(summary['code_sha256'], BLOB.CODE_SHA)
        self.assertEqual(summary['image_rt'], '0x08F77800')
        self.assertEqual(summary['code_bytes'], len(BLOB.CODE))
        # 2편 조합 최종 상태도 그대로다.
        self.assertEqual(B._verify_part2_name_compose(bytearray(self.candidate), self.orig)['table_end'],
                         '0x08F24494')

    def test_reapply_is_byte_identical_and_diff_is_exact(self):
        rom = self.pre_stage()
        before = bytes(rom)
        B._part1_name_compose(rom, self.orig)
        self.assertEqual(bytes(rom), self.candidate)
        diff = {i for i, (a, b) in enumerate(zip(before, rom)) if a != b}
        allowed = set()
        for start, end in self.regions.values():
            allowed.update(range(start, end))
        self.assertTrue(diff)
        self.assertFalse(sorted(diff - allowed)[:20])
        for name, original in B.P1_NAME_COMPOSE_SITES:
            start, end = self.regions[name]
            with self.subTest(site=name):
                self.assertNotEqual(rom[start:end], original)

    def test_site_literals_in_candidate(self):
        for name, literal, sym in SITE_LITERALS:
            with self.subTest(site=name):
                self.assertEqual(struct.unpack_from('<I', self.candidate, literal)[0], BLOB.entry(sym))
        self.assertEqual(self.candidate[0xB4985C:0xB4985E], bytes.fromhex('8020'))
        self.assertEqual(self.candidate[0xB49180:0xB49182], bytes.fromhex('2be0'))

    def test_keep_and_trim_in_candidate(self):
        for start, value in B.P1_NAME_COMPOSE_KEEP:
            with self.subTest(keep=hex(start)):
                self.assertEqual(self.candidate[start:start + len(value)], value)
        for start, end in B.P1_NAME_COMPOSE_KEEP_ORIGINAL:
            self.assertEqual(self.candidate[start:end], self.orig[start:end])
        hook = B.PART1_NAME_TRIM_HOOK_FILE
        self.assertEqual(self.candidate[hook:hook + 58], B.PART1_NAME_TRIM_HOOK)
        self.assertFalse(any(self.candidate[hook + 58:hook + 70]))
        self.assertFalse(any(self.candidate[0xF79800:0xF80000]))

    def test_rejects_tampered_original_or_current_site(self):
        for name, original in B.P1_NAME_COMPOSE_SITES:
            start, _end = self.regions[name]
            with self.subTest(orig_site=name):
                orig = bytearray(self.orig)
                orig[start] ^= 1
                self.assertRejectsUnchanged(self.pre_stage(), bytes(orig), 'original ROM differs')
            with self.subTest(rom_site=name):
                rom = self.pre_stage()
                rom[start + len(original) - 1] ^= 1
                self.assertRejectsUnchanged(rom, None, 'site already changed')

    def test_rejects_keep_changes(self):
        for start, _value in B.P1_NAME_COMPOSE_KEEP:
            with self.subTest(keep=hex(start)):
                rom = self.pre_stage()
                rom[start] ^= 1
                self.assertRejectsUnchanged(rom, None, 'keep')
        for offset in (0xDF9F5D, 0xDFA00F, 0xBE7245):   # 선택표 첫/끝 셀 · 숨은 한자 목록
            with self.subTest(keep_original=hex(offset)):
                rom = self.pre_stage()
                rom[offset] ^= 1
                self.assertRejectsUnchanged(rom)

    def test_rejects_occupied_image(self):
        for offset in (0xF77800, 0xF78000, 0xF797FF):
            with self.subTest(offset=hex(offset)):
                rom = self.pre_stage()
                rom[offset] ^= 0x10
                self.assertRejectsUnchanged(rom, None, 'not empty')

    def test_requires_earlier_stages(self):
        old_trim = bytes.fromhex(
            '031c00211878002806d0881c0006010e581800780028f8d1002910d0'
            '881e0006010e5a181078812802d08f2804d006e050784028f0d002e0'
            '50785a28ecd0c918002088707047')
        cases = {
            'part2 image missing': (0xF75800, bytes(16), 'part2'),
            'part2 hook missing': (0x34B0BC, bytes.fromhex('6520f0f7b9fcfff79dfe'), 'part2'),
            'table end old': (P.LIT_TBL_END, struct.pack('<I', 0x08F243A4), None),
            'trim hook retired': (B.PART1_NAME_TRIM_HOOK_FILE, old_trim, 'trim hook'),
            'trim site native': (B.PART1_NAME_TRIM_SITE, B.PART1_NAME_TRIM_EXPECT, 'trim site'),
            'tilemap literal': (0xBE7280, struct.pack('<I', 0x02012D40), 'tilemap'),
            'dictionary list': (0xBE720C, bytes.fromhex('8395'), 'dictionary'),
        }
        for label, (offset, data, needle) in cases.items():
            with self.subTest(case=label):
                rom = self.pre_stage()
                rom[offset:offset + len(data)] = data
                self.assertRejectsUnchanged(rom, None, needle)
        with self.subTest(case='twice'):
            self.assertRejectsUnchanged(bytearray(self.candidate))

    def test_rejects_stale_blob(self):
        sha = dict(BLOB.SOURCE_SHA, **{'generated/grid_p1.inc': '0' * 64})
        with mock.patch.object(BLOB, 'SOURCE_SHA', sha):
            self.assertRejectsUnchanged(self.pre_stage(), None, 'stale')

    def test_final_verify_rejects_one_byte_change(self):
        offsets = [0xF77800, 0xF77801 + BLOB.SYMBOLS['nc_sel_priv'], 0xF77800 + len(BLOB.CODE) - 1,
                   0xF77800 + len(BLOB.CODE), 0xF797FF, 0xB49018, 0xB49021, 0xB48FE4, 0xB48FEB,
                   0xB49162, 0xB4916B, 0xB488FE, 0xB48907, 0xB48E50, 0xB48E57, 0xB4985C, 0xB49180,
                   0xB48FEC, 0xB49336, 0xB4916E, 0xB48964, 0xB4985E, 0xDFA108, 0xDF9F5C, 0xBE7180,
                   B.PART1_NAME_TRIM_HOOK_FILE, B.PART1_NAME_TRIM_HOOK_FILE + 60]
        for offset in offsets:
            with self.subTest(offset=hex(offset)):
                rom = bytearray(self.candidate)
                rom[offset] ^= 1
                with self.assertRaises((AssertionError, ValueError)):
                    B._verify_part1_name_compose(rom, self.orig)


@unittest.skipUnless(_ORIG and _candidate_path() and BASE_PATH, 'no --base baseline given')
class BaselineDiffTests(unittest.TestCase):
    def test_candidate_minus_baseline_inside_whitelist(self):
        cand = Path(_candidate_path()).read_bytes()
        base = Path(BASE_PATH).read_bytes()
        self.assertEqual(len(cand), len(base))
        allowed = set(range(*TRIM_SPAN))
        for _n, start, end in B.P1_NAME_COMPOSE_WRITES:
            allowed.update(range(start, end))
        diff = {i for i, (a, b) in enumerate(zip(base, cand)) if a != b}
        self.assertFalse(sorted(diff - allowed)[:20])


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]] + _REST)
