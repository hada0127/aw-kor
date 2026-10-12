"""Check the Part 2 decimal's private glyph-cache node and blank spaces."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_korean_full import patch_part2_decimal_point_a3, verify_part2_decimal_point_a3  # noqa: E402
from qa_part1_dialogue_punctuation import approved_decimal_consumer, decimal_positions, glyph_state  # noqa: E402


class DecimalGlyphTest(unittest.TestCase):
    def test_decimal_uses_private_a3_node_without_changing_spaces(self):
        source = (Path(__file__).resolve().parents[1] / 'original' /
                  'Game Boy Wars Advance 1+2 (Japan).gba')
        if not source.exists():
            self.skipTest('source ROM absent')
        original = source.read_bytes()
        rom = bytearray(original)
        space_table = original[0xB8027C:0xB8028C]
        blank = original[0xB974D0 + 95 * 32:0xB974D0 + 96 * 32]
        self.assertEqual(patch_part2_decimal_point_a3(rom, original), 0xFD0000)
        self.assertEqual(rom[0xB8027C:0xB8028C], space_table)
        self.assertEqual(rom[0xB974D0 + 95 * 32:0xB974D0 + 96 * 32], blank)
        state = glyph_state(rom, original, 0x8144)
        self.assertEqual(state['consumer'], 'part2_a3')
        self.assertEqual(state['slots'], [0xFD0008, 0xFD0028])
        self.assertTrue(state['visible'])
        self.assertTrue(state['restored'])
        glyph = rom[0xFD0008:0xFD0048]
        pixels = {(x, y): (glyph[y * 4 + x // 2] >> (4 * (x % 2))) & 15
                  for y in range(16) for x in range(8)}
        self.assertEqual({point: ink for point, ink in pixels.items() if ink},
                         {(x, y): 10 for y in (12, 13) for x in (3, 4)})
        verify_part2_decimal_point_a3(rom, original)
        rom[0xFD0028] ^= 1
        self.assertFalse(glyph_state(rom, original, 0x8144)['restored'])
        with self.assertRaises(AssertionError):
            verify_part2_decimal_point_a3(rom, original)
        rom[0xFD0028] ^= 1
        rom[0x52F960] ^= 1
        self.assertFalse(glyph_state(rom, original, 0x8144)['restored'])
        with self.assertRaises(AssertionError):
            verify_part2_decimal_point_a3(rom, original)

    def test_decimal_is_authorized_only_for_relocated_co_line(self):
        self.assertTrue(approved_decimal_consumer(0xA2BC3C, 0xA5823C))
        self.assertFalse(approved_decimal_consumer(0xD90000))
        self.assertFalse(approved_decimal_consumer(0xA2BC3C, 0xA58200))
        self.assertEqual(decimal_positions(b'\x81\x44\x00\x81\x44', 0x100),
                         {0x100, 0x103})
        self.assertEqual(decimal_positions(b'\x81\x40\x81\x44', 0x200), {0x202})

    def test_final_verification_rejects_space_mapping_and_glyph_mutations(self):
        source = (Path(__file__).resolve().parents[1] / 'original' /
                  'Game Boy Wars Advance 1+2 (Japan).gba')
        if not source.exists():
            self.skipTest('source ROM absent')
        original = source.read_bytes()
        rom = bytearray(original)
        patch_part2_decimal_point_a3(rom, original)
        verify_part2_decimal_point_a3(rom, original)
        for offset in (0xB8027C, 0xB8028C, 0xB974D0 + 95 * 32):
            with self.subTest(offset=hex(offset)):
                rom[offset] ^= 1
                with self.assertRaises(AssertionError):
                    verify_part2_decimal_point_a3(rom, original)
                rom[offset] ^= 1
        verify_part2_decimal_point_a3(rom, original)


if __name__ == '__main__':
    unittest.main()
