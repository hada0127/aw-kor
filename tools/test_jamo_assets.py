"""자모 40자 코드표·글리프·조회표(gen_jamo_assets)를 고정값과 독립 계산으로 검사한다."""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_jamo_assets as ga  # noqa: E402

JAMO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ' + 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
CODES_SHA256 = '628404ed7bbb567872108431f30c76fd8824acebbe3049ac4031923eeda2b7e9'
GLYPHS_SHA256 = '1417db5cb058782f3cd3f133cead8da711de47e3185bbfaf900ad8841f7c4980'
SYLMAP = Path(ga.ROOT) / 'data' / 'syllable_to_glyph_2350.json'
HAVE_ROM = os.path.exists(ga.ROM)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class JamoCodes(unittest.TestCase):
    def setUp(self):
        self.codes = ga.load_jamo_codes()
        self.syl = ga.load_syllable_codes()

    def test_order_count_unique(self):
        self.assertEqual(''.join(self.codes), JAMO)
        self.assertEqual(len(set(self.codes.values())), 40)
        self.assertEqual(list(self.codes.values()), sorted(self.codes.values()))

    def test_disjoint_and_range(self):
        self.assertFalse(set(self.codes.values()) & set(self.syl.values()))
        for c in self.codes.values():
            self.assertTrue(0x88 <= c >> 8 <= 0xEA and (c & 0xFF) >= 0x40, hex(c))

    def test_first_codes(self):
        self.assertEqual([self.codes[j] for j in 'ㄱㄲㄴㄷ'], [0xE2A8, 0xE2AB, 0xE2AD, 0xE2AE])

    def test_fixed_sha(self):
        self.assertEqual(sha(ga.OUT_CODES), CODES_SHA256)

    def test_rejects_overlap_and_order(self):
        bad = dict(self.codes)
        bad['ㄱ'] = self.syl['가']
        with self.assertRaises(ValueError):
            ga._validate_codes(bad, self.syl)
        swapped = dict(reversed(list(self.codes.items())))
        with self.assertRaises(ValueError):
            ga._validate_codes(swapped, self.syl)

    @unittest.skipUnless(HAVE_ROM, 'original ROM required')
    def test_pool_membership_and_selection(self):
        from build_korean2350 import extend_pool
        rom = Path(ga.ROM).read_bytes()
        self.assertEqual(hashlib.sha256(rom).hexdigest(), ga.ROM_SHA256)
        pool = extend_pool(rom)
        self.assertTrue(set(self.codes.values()) <= set(pool))
        # 독립 선정: 풀을 오름차순으로 훑어 2350에 없는 첫 40개
        used = set(self.syl.values())
        picked = [c for c in sorted(set(pool)) if c not in used][:40]
        self.assertEqual(list(self.codes.values()), picked)

    @unittest.skipUnless(HAVE_ROM, 'original ROM required')
    def test_regeneration_byte_identical(self):
        codes_bytes, glyphs = ga.generate()
        self.assertEqual(codes_bytes, Path(ga.OUT_CODES).read_bytes())
        self.assertEqual(glyphs, Path(ga.OUT_GLYPHS).read_bytes())


class JamoGlyphs(unittest.TestCase):
    def test_size_sha_ink(self):
        data = ga.jamo_tiles()
        self.assertEqual(len(data), 2560)
        self.assertEqual(sha(ga.OUT_GLYPHS), GLYPHS_SHA256)
        for i, j in enumerate(JAMO):
            self.assertTrue(any(data[i * 64:(i + 1) * 64]), j)

    def test_matches_render(self):
        self.assertEqual(ga.render_jamo_tiles(), ga.jamo_tiles())


class DenseTable(unittest.TestCase):
    def setUp(self):
        self.syl = ga.load_syllable_codes()
        self.table = ga.dense_table(self.syl)
        self.values = struct.unpack('<11172H', self.table)

    def test_size_and_exact_codes(self):
        self.assertEqual(len(self.table), 22344)
        self.assertEqual(sum(1 for v in self.values if v), 2350)
        self.assertEqual(len(self.syl), 2350)
        for s, code in self.syl.items():
            n = ord(s) - 0xAC00
            l, v, t = n // 588, n // 28 % 21, n % 28
            self.assertEqual(self.values[(l * 21 + v) * 28 + t], code, s)
        self.assertEqual(sorted(v for v in self.values if v), sorted(self.syl.values()))

    def test_missing_are_zero(self):
        for s in '갣뢔쌰쎼쓔쬬':
            self.assertNotIn(s, self.syl)
            self.assertEqual(self.values[ord(s) - 0xAC00], 0, s)

    def test_deterministic(self):
        self.assertEqual(ga.dense_table(dict(reversed(list(self.syl.items())))), self.table)


class TableEntries(unittest.TestCase):
    def setUp(self):
        self.codes = ga.load_jamo_codes()
        self.sylmap = json.loads(SYLMAP.read_text(encoding='utf-8'))['map']

    def test_entries(self):
        out = ga.jamo_table_entries(self.sylmap, self.codes)
        self.assertEqual(len(out), 240)
        for i, j in enumerate(JAMO):
            e = out[i * 6:(i + 1) * 6]
            self.assertEqual((e[0] << 8) | e[1], self.codes[j])
            self.assertEqual(struct.unpack('<HH', e[2:]),
                             (0x8000 | (1275 + 2 * i), 0x8000 | (1276 + 2 * i)))

    def test_accepts_builder_private_ja(self):
        # build_korean_full: sylmap['자']['top'] = _private_ja(1274) 뒤에 엔트리를 붙인다
        self.assertEqual(self.sylmap['자']['top'], 119)
        patched = dict(self.sylmap)
        patched['자'] = dict(self.sylmap['자'], top=1274)
        self.assertEqual(ga.jamo_table_entries(patched, self.codes),
                         ga.jamo_table_entries(self.sylmap, self.codes))

    def test_rejects_jamo_tile_collision(self):
        for tile in (1275, 1276 + 2 * 39):
            bad = dict(self.sylmap)
            bad['가'] = {'top': tile, 'bot': 0}
            with self.assertRaises(ValueError, msg=tile):
                ga.jamo_table_entries(bad, self.codes)


if __name__ == '__main__':
    unittest.main(verbosity=2)
