"""Negative checks for the Part 1 name-grid Galmuri digit gate."""
import unittest

from pathlib import Path

from build_korean_full import NAME_GRID_SLOTS
from qa_transient_overlays import digit_tile_status, font_tile_bytes
from render_galmuri_8x16 import render_char


class NameGridDigitTileTest(unittest.TestCase):
    def test_galmuri_tile_accepted_and_original_rejected(self):
        original = (Path(__file__).resolve().parents[1] /
                    'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        for digit in "0123456789":
            for slot, expected in zip(NAME_GRID_SLOTS[digit], render_char(digit)):
                old = font_tile_bytes(original, slot)
                self.assertNotEqual(old, expected)
                self.assertEqual(digit_tile_status(expected, expected, old), (True, True))
                self.assertEqual(digit_tile_status(old, expected, old), (False, False))
                corrupted = bytes([expected[0] ^ 1]) + expected[1:]
                self.assertEqual(digit_tile_status(corrupted, expected, old), (False, True))


if __name__ == "__main__":
    unittest.main()
