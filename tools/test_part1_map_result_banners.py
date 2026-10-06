import struct
import unittest

import part1_map_result_banners as m
from lz77_scan import lz77_decompress


class MapResultBannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (m.ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_native_tilemaps_match_module_geometry(self):
        # 0xBFD0B8: 32x6 map, WIN/DRAW tiles 0..95 as a 16-wide grid at columns 14..29.
        w, h = self.original[0xBFD0B8], self.original[0xBFD0B9]
        self.assertEqual((w, h), (32, 6))
        cells = struct.unpack_from('<192H', self.original, 0xBFD0BA)
        for row in range(6):
            self.assertEqual(list(cells[row * 32 + 14:row * 32 + 30]), list(range(row * 16, row * 16 + 16)))
        # 0xBFD23C: LOSE tiles 96.. (sheet tiles 0..10 of each 16-wide row) at columns 2..12.
        cells = struct.unpack_from('<96H', self.original, 0xBFD23E)
        for row in range(3):
            self.assertEqual(list(cells[row * 32 + 2:row * 32 + 13]), list(range(96 + row * 16, 107 + row * 16)))
        for banner in m.BANNERS:
            m.source(self.original, banner)

    def test_patch_reads_korean_and_keeps_shared_tiles(self):
        rom = bytearray(self.original)
        self.assertEqual(m.patch(rom, self.original), 3)
        for banner in m.BANNERS:
            new, used = lz77_decompress(rom, banner[1])
            self.assertLessEqual(used, banner[4])
            old = lz77_decompress(self.original, banner[1])[0]
            px_new, px_old = m._decode(new), m._decode(old)
            x0, y0, x1, y1 = banner[8]
            for y in range(len(px_old)):
                for x in range(128):
                    if not (x0 <= x < x1 and y0 <= y < y1):
                        self.assertEqual(px_new[y][x], px_old[y][x], (banner[0], x, y))
            ink = sum(row.count(m.INK) for row in px_new)
            self.assertGreater(ink, 150, banner[0])
            self.assertTrue({v for row in px_new for v in row[x0:x1]} <= {0, banner[7], m.INK} | (
                {v for row in px_old for v in row[x1:]} if x1 < 128 else set()))
        # LOSE: shared fill tiles 141/142/143 (sheet tiles 45..47) untouched.
        lose = lz77_decompress(rom, 0xBFCF48)[0]
        self.assertEqual(lose[45 * 32:48 * 32], lz77_decompress(self.original, 0xBFCF48)[0][45 * 32:48 * 32])
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
        rom[0xBFCBD8 + 30] ^= 1
        with self.assertRaises(AssertionError):
            m.verify(rom, regions)

    def test_conflicts_rejected(self):
        rom = bytearray(self.original)
        rom[0xBFC834 + 40] ^= 1
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        rom = bytearray(self.original)
        rom[0xB4C980] ^= 4
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        original = bytearray(self.original)
        original[0xBFCF48 + 50] ^= 1
        with self.assertRaises(AssertionError):
            m.expected_regions(original)


if __name__ == '__main__':
    unittest.main()
