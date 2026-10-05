import re
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

import part1_campaign_co_name_lz77 as m
from lz77_scan import lz77_decompress


class CampaignCoNameLz77Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent.parent
        cls.original = (root / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        cls.build_src = (root / 'tools/build_korean_full.py').read_text()

    def test_names_match_build_co_name_ko(self):
        block = re.search(r'CO_NAME_KO = \[(.*?)\]', self.build_src, re.S).group(1)
        co_name_ko = re.findall(r"'([^']+)'", block)
        for row in m.NAMES:
            self.assertIn(row[5], co_name_ko)
        self.assertEqual([row[5] for row in m.NAMES],
                         ['료', '맥스', '호이프', '도미노', '빌리', '키쿠치요', '아스카',
                          '이글', '모프', '헬보우즈', '하치'])

    def test_patch_only_owned_allocations_and_catherine_untouched(self):
        rom = bytearray(self.original)
        self.assertEqual(m.patch(rom, self.original), 11)
        outside = bytearray(rom)
        for source, pointers, following, capacity, *_ in m.NAMES:
            raw, used = lz77_decompress(rom, source)
            self.assertEqual(raw, m.render(source))
            self.assertLessEqual(used, capacity)
            self.assertEqual({n for b in raw for n in (b & 15, b >> 4)}, {0, m.INK})
            outside[source:source + capacity] = self.original[source:source + capacity]
        self.assertEqual(outside, self.original)
        self.assertEqual(lz77_decompress(rom, m.CATHERINE), lz77_decompress(self.original, m.CATHERINE))

    def test_plate_geometry_centres_glyphs(self):
        raw = m.render_name('료')
        ink = [(x, y) for y in range(16) for x in range(48)
               if (raw[m._offset(x, y)] >> (4 * (x % 2))) & 15]
        self.assertTrue(ink)
        self.assertTrue(all(20 <= x < 28 for x, _ in ink))
        raw = m.render_name('헬보우즈')
        ink = [x for y in range(16) for x in range(48)
               if (raw[m._offset(x, y)] >> (4 * (x % 2))) & 15]
        self.assertTrue(min(ink) >= 8 and max(ink) < 40)
        self.assertTrue(any(x >= 32 for x in ink))  # reaches the 16x16 cell
        with self.assertRaises(AssertionError):
            m.render_name('일곱글자이름요')

    def test_shared_hellbolt_sheet_patched_once(self):
        row = next(r for r in m.NAMES if r[0] == 0xC10984)
        self.assertEqual(row[1], (0xDF3C98, 0xDF3CB8))

    def test_drift_rejected(self):
        for address in (0xC10380 + 5, 0xDF3B78, 0xB42E48, 0xDF3B58, 0xC10984 + 9):
            original = bytearray(self.original)
            original[address] ^= 1
            with self.assertRaises(AssertionError):
                m.source_guard(original)
        for address in (0xDF3C98, 0xC10AA0 + 10, 0xC10AA0 + 145):
            rom = bytearray(self.original)
            rom[address] ^= 1
            with self.assertRaises(AssertionError):
                m.patch(rom, self.original)

    def test_overflow_is_atomic(self):
        rom = bytearray(self.original)
        with patch.object(m, 'lz77_compress_optimal', return_value=bytes(300)):
            with self.assertRaisesRegex(AssertionError, 'overflow'):
                m.patch(rom, self.original)
        self.assertEqual(rom, self.original)

    def test_snapshot(self):
        rom = bytearray(self.original)
        m.patch(rom, self.original)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        self.assertTrue(m.generated_matches(rom))
        for address in (0xC10594 + 4, 0xDF3CB8, 0xC10AA0 + 146):
            broken = bytearray(rom)
            broken[address] ^= 1
            with self.assertRaises(AssertionError):
                m.verify(broken, regions)
        rom[0xC10AA0 + 145] ^= 1
        with self.assertRaises(AssertionError):
            m.capture(rom, self.original)


if __name__ == '__main__':
    unittest.main()
