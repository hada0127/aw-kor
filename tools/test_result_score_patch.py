"""Owned ROM bytes for the Part 1 result score atlas."""
from pathlib import Path
import unittest
from unittest.mock import patch

import build_korean_full as build


ROOT = Path(__file__).resolve().parents[1]


class ResultScorePatchTests(unittest.TestCase):
    def test_changes_only_owned_atlas_entries_and_rejects_changed_source(self):
        original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        rom = bytearray(original)
        with patch.object(build, 'rec_objlabel'), patch.object(build, 'rec_label_layout'):
            self.assertEqual(build.patch_part1_result_score_labels(rom), 3)
            self.assertEqual(rom[:0xBEAF5C], original[:0xBEAF5C])
            self.assertEqual(rom[0xBEB0FC:], original[0xBEB0FC:])
            for start, end in ((0xBEAF5C, 0xBEAFDC), (0xBEAFDC, 0xBEB05C),
                               (0xBEB05C, 0xBEB0FC)):
                self.assertNotEqual(rom[start:end], original[start:end])
            with self.assertRaisesRegex(AssertionError, 'atlas source changed'):
                build.patch_part1_result_score_labels(rom)


if __name__ == '__main__':
    unittest.main()
