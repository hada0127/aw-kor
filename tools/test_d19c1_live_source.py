"""Keep the two identical JP calls and their distinct B-team owners separate."""

import collections
import json
import unittest
from pathlib import Path

import build_korean_full as B


class D19C1LiveSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = Path(B.P.ROM).read_bytes()
        cls.codes = {s: int(c, 16) for s, c in json.loads(Path(B.SYLCODE).read_text()).items()}

    def test_duplicate_japanese_rows_have_distinct_protected_korean(self):
        source = b'\x69' + 'さん、リョウ！'.encode('shift_jis')
        baseline = json.loads(Path(B.BASE, 'data', 'bteam_baseline.json').read_text())['overrides']
        overrides = json.loads(Path(B.BASE, 'data', 'dialogue_overrides.json').read_text())
        for address, text in ((0xDC2937, '사령관님,료!'), (0xDC33AF, '님, 료！')):
            self.assertEqual(self.original[address - 1:address + 14], source)
            self.assertEqual(baseline[f'0x{address:08X}'], text)
            self.assertEqual(overrides[f'0x{address:08X}'], text)

    def test_b32r5_live_row_keeps_name_control_and_syllable_glyphs(self):
        path = Path(B.BASE, 'output', 'game_wars_korean_candidate_20261015_b32r5.gba')
        if not path.exists():
            self.skipTest('b32r5 candidate is not present in this checkout')
        rom = path.read_bytes()
        expected_name = B.encode_text('님、　료！', self.codes, collections.Counter()).ljust(14, b' ')
        expected_commander = B.encode_text('사령관님、료！', self.codes, collections.Counter())
        self.assertEqual(rom[0xDC33AE], 0x69)
        self.assertEqual(rom[0xDC33AF:0xDC33BD], expected_name)
        self.assertEqual(rom[0xDC2936], 0x69)
        self.assertEqual(rom[0xDC2937:0xDC2945], expected_commander)


if __name__ == '__main__':
    unittest.main()
