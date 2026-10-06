import unittest

import part1_versus_settle_banner as m
from lz77_scan import lz77_decompress


class VersusSettleBannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (m.ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_patch_capture_verify(self):
        rom = bytearray(self.original)
        self.assertEqual(m.patch(rom, self.original), 1)
        data, used = lz77_decompress(rom, m.SOURCE)
        self.assertLessEqual(used, m.CAPACITY)
        self.assertEqual(len(data), m.SIZE)
        for cell in range(2):
            values = {(data[cell * 512 + i] >> s) & 15 for i in range(512) for s in (0, 4)}
            self.assertTrue(values <= {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, m.OUTLINE})
            self.assertIn(m.OUTLINE, values)
        outside = bytearray(rom)
        for address, raw in m.expected_regions(self.original):
            outside[address:address + len(raw)] = self.original[address:address + len(raw)]
        self.assertEqual(outside, self.original)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        self.assertTrue(m.generated_matches(rom, self.original))
        again = bytearray(rom)
        m.patch(again, self.original)
        self.assertEqual(again, rom)
        rom[m.SOURCE + 9] ^= 1
        with self.assertRaises(AssertionError):
            m.verify(rom, regions)

    def test_conflicts_rejected(self):
        rom = bytearray(self.original)
        rom[m.SOURCE + 12] ^= 1
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        original = bytearray(self.original)
        original[m.LITERAL] ^= 4
        with self.assertRaises(AssertionError):
            m.source_guard(original)


if __name__ == '__main__':
    unittest.main()
