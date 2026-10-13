"""Exact final-ROM regressions for the C2 menu and terrain decisions."""
import os
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROM = Path(os.environ.get(
    "AW_TEST_ROM", ROOT / "output/game_wars_korean_candidate_20261013_b28.gba"
))


class C2BytesTest(unittest.TestCase):
    def test_part2_music_menu_rows_have_four_cells_and_zero_tail(self):
        rom = ROM.read_bytes()
        self.assertEqual(rom[0xA298C2:0xA298CC], bytes.fromhex("8f83 8ea0 8fb3 8f83 0000"))
        self.assertEqual(rom[0xA298D2:0xA298DC], bytes.fromhex("8f83 8ea0 8ecd 8f83 0000"))

    def test_part2_capital_header_has_both_glyphs_and_terminator(self):
        rom = ROM.read_bytes()
        self.assertEqual(rom[0xA29A04:0xA29A0A], bytes.fromhex("8def 8a5a 0000"))


if __name__ == "__main__":
    unittest.main()
