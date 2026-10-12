import unittest

import part1_obj_header_labels as m
from bdf import load_bdf
from build_korean_full import render_32x8_obj_label


def strip(raw, tiles):
    return [[(raw[(x // 8) * 32 + y * 4 + (x % 8) // 2] >> (4 * (x % 2))) & 15 for x in range(tiles * 8)]
            for y in range(8)]


class HeaderLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (m.ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_patch_writes_only_label_spans(self):
        rom = bytearray(self.original)
        self.assertEqual(m.patch(rom, self.original), len(m.LABELS))
        outside = bytearray(rom)
        for address, tiles, text, _, _ in m.LABELS:
            pixels = strip(rom[address:address + tiles * 32], tiles)
            self.assertEqual({v for row in pixels for v in row} - {0}, {m.BOX, m.INK}, text)
            self.assertEqual(pixels[0], [0] * tiles * 8)
            outside[address:address + tiles * 32] = self.original[address:address + tiles * 32]
        self.assertEqual(outside, self.original)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        self.assertTrue(m.generated_matches(rom, self.original))
        again = bytearray(rom)
        m.patch(again, self.original)
        self.assertEqual(again, rom)
        rom[0xBE991C + 40] ^= 1
        with self.assertRaises(AssertionError):
            m.verify(rom, regions)

    def test_shared_info_joins_production_and_battle(self):
        rom = bytearray(self.original)
        m.patch(rom, self.original)
        production = strip(rom[0xBE965C:0xBE965C + 10 * 32], 10)   # observed 32x8+32x8+16x8
        battle = strip(rom[0xBE979C:0xBE979C + 4 * 32] + rom[0xBE973C:0xBE973C + 3 * 32], 7)
        for pixels, join in ((production, 56), (battle, 32)):
            self.assertEqual(pixels[4][join - 1], m.BOX)
            self.assertEqual(pixels[4][join], m.BOX)   # one continuous black box across the join
            self.assertIn(m.INK, pixels[4][:join])
            self.assertIn(m.INK, pixels[4][join:])

    def test_conflict_and_drift_rejected(self):
        rom = bytearray(self.original)
        rom[0xBE94DC + 3] ^= 1
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        original = bytearray(self.original)
        original[0xBE9ADC] ^= 1
        with self.assertRaises(AssertionError):
            m.expected_regions(original)

    def test_existing_sibling_writers_not_overlapped(self):
        siblings = ((0xBE945C, 128), (0xBE9A5C, 128), (0xBE989C, 128), (0xBE9BDC, 128), (0xBE9C5C, 64))
        for address, tiles, *_ in m.LABELS:
            for start, size in siblings:
                self.assertTrue(address + tiles * 32 <= start or start + size <= address, hex(address))

    def test_part2_noncompact_info_label_keeps_full_glyph_height(self):
        font, _ = load_bdf(str(m.ROOT / 'reference/fonts/Galmuri7.bdf'))
        full = strip(render_32x8_obj_label(font, '정보'), 4)
        compact = strip(render_32x8_obj_label(font, '정보', compact=True), 4)
        self.assertEqual(full, compact)
        self.assertEqual(full[0], [0] * 32)
        self.assertIn(1, full[1])
        self.assertIn(1, full[7])


if __name__ == '__main__':
    unittest.main()
