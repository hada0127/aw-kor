import hashlib
import unittest

import part1_obj_header_labels as m
from bdf import load_bdf
from build_korean_full import render_32x8_obj_label


def strip(raw, tiles):
    return [[(raw[(x // 8) * 32 + y * 4 + (x % 8) // 2] >> (4 * (x % 2))) & 15 for x in range(tiles * 8)]
            for y in range(8)]


# Current-generator goldens (R18, 2026-11-09).  SIX_ROW headers changed; the
# others are byte-identical to the previous generator.
GOLDEN = {
    0xBE93BC: '453153f6c2b1e3e807c32eaa75ddd01e19bfb295c87b9f0a7be22246c9980d0f',
    0xBE94DC: '59311754ed6623118ef25a1abf0cc58958f9caa035be1fd519aee8994fe82456',
    0xBE955C: 'cdbd829d0909011ece2b387da82db4944a6ced72c8911c9f23ca55cd074957b4',
    0xBE95DC: 'd52d4036e888de5597d44e25672cbb87c19930bfa48f4c214a685c2e2b57bf7a',
    0xBE965C: 'fbb175addd62db48617adec3bc4b4e41b290111f367a8b26cdc332e1ef8396ef',
    0xBE973C: '037c04f7bf404587380579d6da737c6568bca7fd278da012020c83d9c6076863',
    0xBE979C: '85c3cf9e2877321566adc8e6a60fcc4a25a8f24e79800ac2904c07b62ece6f13',
    0xBE981C: 'e2c7afc16b1b082111a8cde608246c11895eb99316c136e007a3e897e0f664f1',
    0xBE991C: '781cabaab319cdcbdd1ea80f88187bfc412aff99082fab438c89172aee04119b',
    0xBE9ADC: 'f1a4706d91b31e2d10e788e2a27edf2e698f8cf42dd0a4ec325408eafb6ac679',
}
COST_GOLDEN = '6d1003321a1deb3cd1c46c1a32898b543ea2585e83ad12a6f896116b635803f4'


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
            if address in m.SIX_ROW:
                # Black row above and below six-row text (JP margin; R18 clipped-top fix).
                self.assertNotIn(m.INK, pixels[0] + pixels[7], text)
                self.assertIn(m.BOX, pixels[0], text)
            else:
                self.assertEqual(pixels[0], [0] * tiles * 8)
            raw = bytes(rom[address:address + tiles * 32])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), GOLDEN[address], text)
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

    def test_cost_label_is_outlined_six_row_text(self):
        from build_korean_full import patch_part2_info_screen_obj_labels
        rom = bytearray(self.original)
        patch_part2_info_screen_obj_labels(rom)
        raw = bytes(rom[0xBE989C:0xBE991C])
        pixels = strip(raw, 4)
        self.assertEqual({v for row in pixels for v in row}, {0, 1, 5})
        self.assertNotIn(1, pixels[0] + pixels[7])
        self.assertEqual(min(x for row in pixels for x, v in enumerate(row) if v == 1), 1)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), COST_GOLDEN)
        font, _ = load_bdf(str(m.ROOT / 'reference/fonts/Galmuri7.bdf'))
        self.assertEqual(bytes(rom[0xBE9A5C:0xBE9ADC]), render_32x8_obj_label(font, '정보', compact=True))
        self.assertEqual(bytes(rom[0xBE945C:0xBE94DC]), render_32x8_obj_label(font, '정보'))
        self.assertEqual(bytes(rom[0xBE9BDC:0xBE9C5C]), render_32x8_obj_label(font, '설명'))

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
