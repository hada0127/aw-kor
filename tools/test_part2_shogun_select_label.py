import struct
import unittest

import part2_shogun_select_label as m
from lz77_scan import lz77_decompress


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (m.ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_source_guard(self):
        m.source_guard(self.original)

    def test_patch_capture_verify_idempotent_and_local(self):
        rom = bytearray(self.original)
        count = m.patch(rom, self.original)
        self.assertEqual(count, len(m.expected_regions(self.original)))
        for address, raw in m.expected_regions(self.original):
            self.assertNotEqual(bytes(self.original[address:address + len(raw)]), raw)
            self.assertEqual(lz77_decompress(rom, address)[1] <= len(raw), True)
        outside = bytearray(rom)
        for address, raw in m.expected_regions(self.original):
            outside[address:address + len(raw)] = self.original[address:address + len(raw)]
        self.assertEqual(outside, self.original)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        self.assertTrue(m.generated_matches(rom, self.original))
        self.assertFalse(m.generated_matches(bytearray(self.original), self.original))
        again = bytearray(rom)
        m.patch(again, self.original)
        self.assertEqual(again, rom)
        first = regions[0][0]
        rom[first + 8] ^= 1
        with self.assertRaises(AssertionError):
            m.verify(rom, regions)

    def test_conflicts_rejected(self):
        first = m.expected_regions(self.original)[0][0]
        rom = bytearray(self.original)
        rom[first + 6] ^= 1
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        original = bytearray(self.original)
        original[first + 20] ^= 1
        with self.assertRaises(AssertionError):
            m.source_guard(original)

    def test_layout_and_inks(self):
        native = m.decode(lz77_decompress(self.original, m.SOURCE)[0])
        self.assertEqual(native[2][1:3], [14, 14])   # native band starts at x=1
        new = m.decode(m.sheet(self.original))
        self.assertEqual({v for r in new for v in r}, {0, m.INK, m.BAND})
        for text, top in m.LINES:
            _, width, height = m.text_mask(text)
            self.assertLessEqual(top + height + 1, m.HEIGHT)
            self.assertLessEqual(m.LEFT + width + 1, m.WIDTH)


if __name__ == '__main__':
    unittest.main()
