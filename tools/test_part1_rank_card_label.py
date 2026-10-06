import unittest

import part1_rank_card_label as m
from lz77_scan import lz77_decompress


class RankCardLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (m.ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_only_the_tag_box_changes(self):
        rom = bytearray(self.original)
        self.assertEqual(m.patch(rom, self.original), 1)
        new, used = lz77_decompress(rom, m.SOURCE)
        self.assertLessEqual(used, m.CAPACITY)
        old = lz77_decompress(self.original, m.SOURCE)[0]
        self.assertEqual(new[64 * 32:], old[64 * 32:])   # 32x64 half untouched
        for y in range(64):
            for x in range(64):
                inside = m.BOX_X0 <= x < m.BOX_X1 and m.BOX_Y0 <= y < m.BOX_Y1
                if not inside:
                    self.assertEqual(m._get(new, x, y), m._get(old, x, y), (x, y))
                else:
                    self.assertIn(m._get(new, x, y), (m.BOX, m.INK))
        ink = sum(m._get(new, x, y) == m.INK for y in range(m.BOX_Y0, m.BOX_Y1) for x in range(m.BOX_X0, m.BOX_X1))
        self.assertGreater(ink, 30)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        self.assertTrue(m.generated_matches(rom, self.original))
        again = bytearray(rom)
        m.patch(again, self.original)
        self.assertEqual(again, rom)
        rom[m.SOURCE + 100] ^= 1
        with self.assertRaises(AssertionError):
            m.verify(rom, regions)

    def test_conflicts_rejected(self):
        rom = bytearray(self.original)
        rom[m.SOURCE + 7] ^= 1
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        original = bytearray(self.original)
        original[m.SOURCE + 300] ^= 1
        with self.assertRaises(AssertionError):
            m.source_guard(original)


if __name__ == '__main__':
    unittest.main()
