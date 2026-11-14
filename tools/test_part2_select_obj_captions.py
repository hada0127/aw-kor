import hashlib
import unittest
from pathlib import Path

import part2_select_obj_captions as m

# Current-generator golden of the four rendered regions (R20b, 2026-11-09).
REGIONS_SHA256 = '4e202923589a1f8b9121884e9132d670e3ac5c35b4f515411ca72b1ebe326857'


def regions_digest(regions):
    h = hashlib.sha256()
    for address, raw in regions:
        h.update(address.to_bytes(4, 'little') + raw)
    return h.hexdigest()


class Part2SelectCaptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent.parent
        cls.original = (root / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_patch_changes_only_owned_bytes_and_is_idempotent(self):
        rom = bytearray(self.original)
        self.assertEqual(m.patch(rom, self.original), 4)
        self.assertTrue(m.generated_matches(rom, self.original))
        restored = bytearray(rom)
        for offset, tiles, *_ in m.PROMPTS + (m.COUNTER,):
            restored[offset:offset + tiles * 32] = self.original[offset:offset + tiles * 32]
        self.assertEqual(restored, self.original)
        again = bytearray(rom)
        m.patch(again, self.original)
        self.assertEqual(again, rom)

    def test_foreign_writer_is_rejected(self):
        rom = bytearray(self.original)
        rom[0x457174] ^= 0xFF
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)

    def test_prompt_keeps_jp_key_and_colon(self):
        for (offset, new), (_, tiles, _, text, colour) in zip(m.expected_regions(self.original), m.PROMPTS):
            jp = m.decode(self.original[offset:offset + tiles * 32], 64)
            ko = m.decode(new, 64)
            for y in range(8):
                self.assertEqual(ko[y][:m.WORD_X], jp[y][:m.WORD_X], text)
                self.assertTrue(all(v == 0 for v in ko[y][55:]), text)   # past the screen edge
            word = {v for row in ko for v in row[m.WORD_X:]}
            self.assertEqual(word, {0, colour, m.OUTLINE}, text)
            self.assertEqual({y for y in range(8) if colour in ko[y][m.WORD_X:]}, set(range(1, 7)), text)

    def test_counter_is_six_row_white_myeong(self):
        offset, new = m.expected_regions(self.original)[-1]
        self.assertEqual(offset, 0x456BB4)
        pixels = m.decode(new, 8)
        self.assertEqual({v for row in pixels for v in row}, {0, 1, m.OUTLINE})
        self.assertNotIn(1, pixels[0] + pixels[7])
        self.assertEqual(m.glyph('명'), ('######', '#..#.#', '#..###', '####.#', '.#...#', '..###.'))

    def test_generator_golden(self):
        digest = regions_digest(m.expected_regions(self.original))
        self.assertEqual(digest, REGIONS_SHA256)


if __name__ == '__main__':
    unittest.main()
