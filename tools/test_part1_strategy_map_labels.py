import hashlib
import unittest

import part1_strategy_map_labels as M
from lz77_scan import lz77_decompress

# Current-generator golden of the localized Mode 4 frame (R20, 2026-11-09).
FRAME_GOLDEN = '12782e44869079dc5e2b851c800c4cda7f85da2022327b82523c7291f554c902'


class StrategyMapLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (M.ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_only_script_pixels_and_korean_change(self):
        native = M.frame_from(self.original)
        frame = M.localized_frame(self.original)
        self.assertEqual(hashlib.sha256(frame).hexdigest(), FRAME_GOLDEN)
        changed = [i for i, (a, b) in enumerate(zip(native, frame)) if a != b]
        for i in changed:
            x, y = i % M.W, i // M.W
            label = [row for row in M.LABELS if row[1][0] <= x < row[1][2] and row[1][1] <= y < row[1][3]]
            self.assertEqual(len(label), 1, (x, y))
            _, _, fill, ink, aa, _ = label[0]
            self.assertIn(native[i], {fill, ink, aa}, (x, y))
            self.assertIn(frame[i], {fill, ink}, (x, y))
        for lines, (x0, y0, x1, y1), fill, ink, aa, _ in M.LABELS:
            for y in range(y0, y1):
                row = frame[y * M.W + x0:y * M.W + x1]
                span = [i for i, v in enumerate(row) if v == fill]
                if span:   # no cursive anti-alias left inside the label fill
                    self.assertNotIn(aa, row[span[0]:span[-1] + 1], (lines, y))
            drawn = sum(1 for i in changed if frame[i] == ink
                        and x0 <= i % M.W < x1 and y0 <= i // M.W < y1)
            self.assertGreater(drawn, 10 * len(''.join(lines)), lines)

    def test_patch_fits_both_halves(self):
        rom = bytearray(self.original)
        self.assertEqual(M.patch(rom, self.original), len(M.LABELS))
        self.assertEqual(bytes(M.frame_from(rom)), M.localized_frame(self.original))
        for offset, size in M.HALVES:
            self.assertLessEqual(lz77_decompress(rom, offset)[1], size)
        changed = [i for i, (a, b) in enumerate(zip(rom, self.original)) if a != b]
        self.assertTrue(all(any(o <= i < o + size for o, size in M.HALVES) for i in changed))

    def test_source_drift_fails_closed(self):
        original = bytearray(self.original)
        original[M.HALVES[1][0] + 100] ^= 1   # a literal byte
        with self.assertRaises(AssertionError):
            M.localized_frame(original)


if __name__ == '__main__':
    unittest.main()
