import unittest
from pathlib import Path
from unittest.mock import patch

import part1_continue_button as m
from lz77_scan import lz77_decompress


class ContinueButtonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (Path(__file__).resolve().parent.parent /
                        'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_only_text_rect_changes(self):
        rom = bytearray(self.original)
        m.patch(rom, self.original)
        self.assertEqual(rom[:m.SOURCE], self.original[:m.SOURCE])
        self.assertEqual(rom[m.SOURCE + m.CAPACITY:], self.original[m.SOURCE + m.CAPACITY:])
        before = lz77_decompress(self.original, m.SOURCE)[0]
        after, used = lz77_decompress(rom, m.SOURCE)
        self.assertLessEqual(used, m.CAPACITY)
        x0, y0, x1, y1 = m.RECT
        ink = []
        for y in range(16):
            for x in range(48):
                a, b = m.get_pixel(before, x, y), m.get_pixel(after, x, y)
                if not (x0 <= x <= x1 and y0 <= y <= y1):
                    self.assertEqual(a, b, (x, y))
                else:
                    self.assertIn(b, (m.FILL, m.INK))
                    if b == m.INK:
                        ink.append(x)
        self.assertTrue(ink)
        self.assertLessEqual(abs((min(ink) + max(ink)) / 2 - (x0 + x1) / 2), 1.5)

    def test_drift_and_overflow(self):
        for address in (m.SOURCE + 6, m.POINTER):
            original = bytearray(self.original)
            original[address] ^= 1
            with self.assertRaises(AssertionError):
                m.source_guard(original)
        rom = bytearray(self.original)
        rom[m.SOURCE + m.CAPACITY] ^= 1
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        rom = bytearray(self.original)
        with patch.object(m, 'lz77_compress_optimal', return_value=bytes(m.CAPACITY + 1)):
            with self.assertRaisesRegex(AssertionError, 'overflow'):
                m.patch(rom, self.original)
        self.assertEqual(rom, self.original)

    def test_snapshot(self):
        rom = bytearray(self.original)
        m.patch(rom, self.original)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        self.assertTrue(m.generated_matches(rom, self.original))
        for address in (m.SOURCE + 3, m.POINTER + 1):
            broken = bytearray(rom)
            broken[address] ^= 1
            with self.assertRaises(AssertionError):
                m.verify(broken, regions)


if __name__ == '__main__':
    unittest.main()
