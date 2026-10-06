import struct
import unittest

import part2_campaign_rank_labels as m
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

    def test_balloon_kept_outside_interior(self):
        native = m.decode(lz77_decompress(self.original, m.SOURCE)[0])
        new = m.decode(m.sheet(self.original))
        for y in range(m.HEIGHT):
            for x in range(m.WIDTH):
                inside = m.INTERIOR_Y[0] <= y < m.INTERIOR_Y[1] and m.INTERIOR_X[0] <= x < m.INTERIOR_X[1]
                if not inside:
                    self.assertEqual(native[y][x], new[y][x], (x, y))
        self.assertEqual({v for r in new for v in r}, {0, 1, 10, 12, 14, 15})


if __name__ == '__main__':
    unittest.main()
