import unittest

import part2_special_break_banner as m
from lz77_scan import lz77_decompress


class SpecialBreakBannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (m.ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_native_layout_is_what_the_module_assumes(self):
        native, entries = m.source_guard(self.original)
        self.assertEqual(entries[4 * 32 + 2] & 0x3FF, 0x00)        # S top-left
        self.assertEqual(entries[8 * 32 + 5] & 0x3FF, 0x17)        # B top-left
        self.assertEqual({entries[r * 32] & 0x3FF for r in (2, 13)}, {0x36})
        self.assertEqual(native[0x36 * 32:0x37 * 32], bytes([0x66]) * 32)
        cells1 = m.line_cells(entries, 4, 2, 25)
        cells2 = m.line_cells(entries, 8, 5, 28)
        self.assertEqual(len(cells1), 90)
        self.assertEqual(len(cells2), 92)
        self.assertFalse(set(cells1.values()) & set(cells2.values()))

    def test_patch_capture_verify_idempotent(self):
        rom = bytearray(self.original)
        self.assertEqual(m.patch(rom, self.original), 1)
        sheet, used = lz77_decompress(rom, m.SOURCE)
        self.assertLessEqual(used, m.CAPACITY)
        native = lz77_decompress(self.original, m.SOURCE)[0]
        _, entries = m.source_guard(self.original)
        line_tiles = set(m.line_cells(entries, 4, 2, 25).values()) | set(m.line_cells(entries, 8, 5, 28).values())
        for tile in range(256):
            same = sheet[tile * 32:tile * 32 + 32] == native[tile * 32:tile * 32 + 32]
            if tile not in line_tiles:
                self.assertTrue(same, tile)
        values = {(b >> s) & 15 for b in sheet for s in (0, 4)}
        self.assertTrue(values <= {0, 1, 3, 4, 5, 6})
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
        rom[m.SOURCE + 10] ^= 1
        with self.assertRaises(AssertionError):
            m.verify(rom, regions)

    def test_conflicts_rejected(self):
        rom = bytearray(self.original)
        rom[m.SOURCE + 20] ^= 1
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        rom = bytearray(self.original)
        rom[m.SOURCE_POINTER] ^= 4
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        original = bytearray(self.original)
        original[m.TILEMAP + 40] ^= 1
        with self.assertRaises(AssertionError):
            m.source_guard(original)


if __name__ == '__main__':
    unittest.main()
