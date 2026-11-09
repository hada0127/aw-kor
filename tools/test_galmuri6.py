import hashlib
import unittest

import galmuri6

# Current-generator golden over every reviewed cut (R18, 2026-11-09).
GLYPHS_SHA256 = '583feb7f401580982684883727bdf88ee3240965b820530e3c326c837ee28441'


def every_cut():
    chars = sorted(set(galmuri6.DROP_ROW) | set(galmuri6.DRAWN))
    return [(c, False) for c in chars] + [(c, True) for c in sorted(galmuri6.NARROW)]


class Galmuri6Tests(unittest.TestCase):
    def test_every_cut_is_six_even_rows(self):
        for char, narrow in every_cut():
            rows = galmuri6.glyph(char, narrow)
            self.assertEqual(len(rows), 6, char)
            self.assertEqual(len({len(r) for r in rows}), 1, char)
            self.assertTrue(all(set(r) <= {'#', '.'} for r in rows), char)
            self.assertTrue(any('#' in r for r in rows[:2]) and '#' in rows[-1] + rows[-2], char)

    def test_six_row_galmuri_glyphs_pass_through(self):
        font = galmuri6._font()
        for char in '료스호프도노요모보즈':
            grid = galmuri6.glyph_grid(font[ord(char)])[0]
            self.assertEqual(galmuri6.glyph(char), tuple(''.join('#' if b else '.' for b in r) for r in grid))

    def test_unreviewed_seven_row_syllable_fails(self):
        with self.assertRaises(KeyError):
            galmuri6.glyph('한')

    def test_ink_and_outline_layout(self):
        points, width = galmuri6.ink('맥스')
        self.assertEqual(width, 15)
        self.assertEqual({y for _, y in points}, set(range(6)))
        pixels = galmuri6.outlined(32, [(x + 2, y) for x, y in points])
        self.assertNotIn(1, pixels[0])
        self.assertNotIn(1, pixels[7])
        self.assertEqual({v for row in pixels for v in row}, {0, 1, 5})
        with self.assertRaises(AssertionError):
            galmuri6.outlined(15, points)

    def test_tiles_4bpp_layout(self):
        pixels = [[0] * 16 for _ in range(8)]
        pixels[0][0], pixels[0][9], pixels[7][15] = 1, 5, 3
        raw = galmuri6.tiles_4bpp(pixels)
        self.assertEqual(len(raw), 64)
        self.assertEqual((raw[0], raw[32], raw[63]), (0x01, 0x50, 0x30))

    def test_cuts_golden(self):
        blob = '\n'.join(f'{c}{int(n)}:' + '/'.join(galmuri6.glyph(c, n)) for c, n in every_cut())
        self.assertEqual(hashlib.sha256(blob.encode()).hexdigest(), GLYPHS_SHA256)


if __name__ == '__main__':
    unittest.main()
