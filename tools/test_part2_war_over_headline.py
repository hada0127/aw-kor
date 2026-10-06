import unittest

import part2_war_over_headline as m
from lz77_scan import lz77_decompress


class WarOverHeadlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (m.ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_native_headline_cells(self):
        native, entries = m.source_guard(self.original)
        cells = m.headline_cells(entries)
        self.assertEqual(len(cells), 82)
        self.assertEqual(entries[4 * 32 + 16] & 0x3FF, 651)        # W top-left
        self.assertEqual(entries[11 * 32 + 26] & 0x3FF, 635)       # '!' column
        self.assertEqual(len(m.paper_pattern(self.original)), 32)
        ink = {(b >> s) & 15 for t in cells.values() for b in native[t * 32:t * 32 + 32] for s in (0, 4)}
        self.assertIn(m.INK, ink)

    def test_patch_capture_verify_idempotent(self):
        rom = bytearray(self.original)
        self.assertEqual(m.patch(rom, self.original), 1)
        sheet, used = lz77_decompress(rom, m.SOURCE)
        self.assertLessEqual(used, m.CAPACITY)
        native, entries = m.source_guard(self.original)
        owned = set(m.headline_cells(entries).values())
        paper = m.paper_pattern(self.original)
        for tile in range(len(native) // 32):
            new, old = sheet[tile * 32:tile * 32 + 32], native[tile * 32:tile * 32 + 32]
            if tile in owned:
                self.assertTrue(all(((n >> s) & 15) in (m.INK, (p >> s) & 15)
                                    for n, p in zip(new, paper) for s in (0, 4)))
            else:
                self.assertEqual(new, old, tile)
        self.assertEqual(lz77_decompress(rom, m.TILEMAP), lz77_decompress(self.original, m.TILEMAP))
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
        rom[m.SOURCE + 30] ^= 1
        with self.assertRaises(AssertionError):
            m.verify(rom, regions)

    def test_conflicts_rejected(self):
        rom = bytearray(self.original)
        rom[m.SOURCE + 20] ^= 1
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        rom = bytearray(self.original)
        rom[m.TILEMAP_POINTER] ^= 4
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        original = bytearray(self.original)
        original[m.SOURCE + 100] ^= 1
        with self.assertRaises(AssertionError):
            m.source_guard(original)


if __name__ == '__main__':
    unittest.main()
