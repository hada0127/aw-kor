"""The two live dialogue glyph paths share Galmuri digit artwork."""
import os
import struct
import unittest
from pathlib import Path

from build_korean_full import (
    NAME_GRID_SLOTS, _symbol_table_index, patch_fullwidth_digit_glyphs,
    patch_name_grid,
)
from render_galmuri_8x16 import render_char


ROOT = Path(__file__).resolve().parents[1]


def assert_digit_glyphs(test, rom):
    """Both live tables carry the Galmuri digits: Part 1 symbol table/font
    slots (0xB8027C / 0xB974D0) and the Part 2 A3 glyph cache (0x807680)."""
    for digit in range(10):
        char = str(digit)
        code = 0x824F + digit
        slots = NAME_GRID_SLOTS[char]
        idx = _symbol_table_index(code)
        test.assertEqual(struct.unpack_from('<H', rom, 0xB8027C + idx * 2)[0], slots[0], char)
        test.assertEqual(struct.unpack_from('<H', rom, 0xB8027C + (idx + 8) * 2)[0], slots[1], char)
        for slot, tile in zip(slots, render_char(char)):
            test.assertEqual(bytes(rom[0xB974D0 + slot * 32:0xB974D0 + (slot + 1) * 32]), tile, char)
        node = struct.unpack_from('<I', rom, 0x807680 + (code & 0xFF) * 4)[0] - 0x08000000
        seen = set()
        while rom[node + 4] != 0x82:
            test.assertNotIn(node, seen)
            seen.add(node)
            node = struct.unpack_from('<I', rom, node)[0] - 0x08000000
        test.assertEqual(bytes(rom[node + 8:node + 72]), b''.join(render_char(char, ink=10)), char)


class FullwidthDigitGlyphTest(unittest.TestCase):
    def test_part1_and_a3_digits_use_galmuri(self):
        rom = bytearray((ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes())
        patch_name_grid(rom)
        self.assertEqual(patch_fullwidth_digit_glyphs(rom), 10)
        assert_digit_glyphs(self, rom)

    def test_final_rom_digit_glyph_bytes(self):
        """Later writers must not overwrite the digit artwork in the candidate."""
        if not os.environ.get('AW_TEST_ROM'):
            self.skipTest('AW_TEST_ROM not set')
        assert_digit_glyphs(self, Path(os.environ['AW_TEST_ROM']).read_bytes())


if __name__ == '__main__':
    unittest.main()
