import hashlib
import os
import unittest
from pathlib import Path

import part1_catherine_name as m
import part1_campaign_co_name_lz77 as names
from lz77_scan import lz77_decompress


class CatherineNameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parent.parent
        cls.original = (cls.root / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_patch_from_original_uses_48x16_plate(self):
        rom = bytearray(self.original)
        self.assertEqual(m.patch(rom, self.original), 1)
        raw, used = lz77_decompress(rom, m.SOURCE)
        self.assertEqual(raw, names.render_name('캐서린'))
        self.assertLessEqual(used, m.CAPACITY)
        outside = bytearray(rom)
        outside[m.SOURCE:m.SOURCE + m.CAPACITY] = self.original[m.SOURCE:m.SOURCE + m.CAPACITY]
        self.assertEqual(outside, self.original)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        self.assertTrue(m.generated_matches(rom))
        rom[m.SOURCE + 10] ^= 1
        with self.assertRaises(AssertionError):
            m.verify(rom, regions)

    def test_patch_after_legacy_96x8_writer(self):
        cwd = os.getcwd()
        os.chdir(self.root)  # build_title_hangul resolves its BDF path relative to the repo root
        try:
            import build_title_hangul as th
            rom = bytearray(self.original)
            th.patch_lz77_whole_block(rom, th.PART1_CATHERINE_NAME_LZ77_OFF,
                                      th.make_part1_catherine_block(), 'part1 Catherine name')
        finally:
            os.chdir(cwd)
        self.assertEqual(hashlib.sha256(lz77_decompress(rom, m.SOURCE)[0]).hexdigest(), m.LEGACY_SHA256)
        m.patch(rom, self.original)
        self.assertTrue(m.generated_matches(rom))
        m.patch(rom, self.original)  # idempotent
        self.assertTrue(m.generated_matches(rom))

    def test_foreign_writer_rejected(self):
        rom = bytearray(self.original)
        names.patch(rom, self.original)  # siblings do not conflict
        stream = bytearray(rom[m.SOURCE:m.SOURCE + m.CAPACITY])
        rom[m.SOURCE + 5] ^= 0x40
        if lz77_decompress(rom, m.SOURCE) is not None:
            with self.assertRaises(AssertionError):
                m.patch(rom, self.original)
        rom[m.SOURCE:m.SOURCE + m.CAPACITY] = stream
        rom[m.POINTER] ^= 4
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)

    def test_glyph_geometry(self):
        raw = m.render()
        ink = [(x, y) for y in range(16) for x in range(48)
               if (raw[names._offset(x, y)] >> (4 * (x % 2))) & 15]
        self.assertTrue(ink)
        self.assertGreaterEqual(min(x for x, _ in ink), 12)
        self.assertLess(max(x for x, _ in ink), 36)
        self.assertGreater(max(y for _, y in ink) - min(y for _, y in ink), 8)


if __name__ == '__main__':
    unittest.main()
