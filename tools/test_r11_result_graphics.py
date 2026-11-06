"""Current-generator goldens for the approved R9–R11 result art."""
import hashlib
import os
import unittest
from collections import Counter
from pathlib import Path

import build_korean_full as build
import part2_special_break_banner as special
from lz77_scan import lz77_decompress

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba'


def pixels(raw, width, height, *, sprite_width=None):
    result = []
    for y in range(height):
        row = []
        for x in range(width):
            if sprite_width:
                cell = x // sprite_width
                tile = cell * (sprite_width // 8) * (height // 8)
                tile += (y // 8) * (sprite_width // 8) + (x % sprite_width) // 8
            else:
                tile = (y // 8) * (width // 8) + x // 8
            value = raw[tile * 32 + (y % 8) * 4 + (x % 8) // 2]
            row.append((value >> (4 * (x % 2))) & 15)
        result.append(row)
    return result


class R11ApprovedArt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = ORIGINAL.read_bytes()

    def test_special_current_sheet_and_protected_cells(self):
        data = special.sheet(self.original)
        native, entries = special.source_guard(self.original)
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         'af50323856b92610fda3a49bd846ca0c2da2dad6bb54e5aab9d8d78a6348e2e7')
        owned = set()
        for text, row, col0, col1 in special.LINES:
            cells = special.line_cells(entries, row, col0, col1)
            owned.update(cells.values())
            line = special.render_line(text, (col1-col0)*8, set(cells))
            ink = [(x, y) for y, values in enumerate(line)
                   for x, v in enumerate(values) if v == 0]
            self.assertGreater(max(x for x, _ in ink) - min(x for x, _ in ink), 145)
            self.assertGreater(max(y for _, y in ink) - min(y for _, y in ink), 22)
            self.assertEqual({v for values in line for v in values}, {0, 4, 5, 6})
        for tile in range(256):
            if tile not in owned:
                self.assertEqual(data[tile*32:(tile+1)*32], native[tile*32:(tile+1)*32])

    def test_result_title_current_generator(self):
        rom = bytearray(self.original)
        build.patch_part2_result_congratulations_obj(rom)
        data = lz77_decompress(rom, 0xBFB45C)[0]
        native = lz77_decompress(self.original, 0xBFB45C)[0]
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         '53ef86256d577b2d7fe5c3d6a39e25511d371572ae49dc8f11bb309073f401be')
        art = pixels(data[:64*32], 128, 32, sprite_width=32)
        ink = [(x, y) for y, row in enumerate(art) for x, v in enumerate(row) if v]
        self.assertEqual((min(x for x, _ in ink), max(x for x, _ in ink)), (2, 126))
        self.assertGreaterEqual(max(y for _, y in ink)-min(y for _, y in ink)+1, 29)
        counts = Counter(v for row in art for v in row)
        for color in (1, 2, 3, 4, 5, 6, 7, 8, 14):
            self.assertGreater(counts[color], 0)
        self.assertNotEqual(data, native)

    def test_candidate_win_and_special_goldens(self):
        candidate = os.environ.get('AW_TEST_ROM')
        if not candidate:
            self.skipTest('AW_TEST_ROM required for fresh candidate checks')
        rom = Path(candidate).read_bytes()
        for off, expected in (
                (0xBFC834, 'efe4f952d9114d6213eb2e8af67aeba675c39454b77f9a9a8ceddf51b41887c7'),
                (0x5B00D8, 'af50323856b92610fda3a49bd846ca0c2da2dad6bb54e5aab9d8d78a6348e2e7')):
            self.assertEqual(hashlib.sha256(lz77_decompress(rom, off)[0]).hexdigest(), expected)
        for off, expected in (
                (0xBFCBD8, 'e96d31c9bc6fad033e1d83bf089bee72f6a954b93c984fb49f3f0fcc1eb05c96'),
                (0xBFCF48, 'ed1674c922aea727cac470b4a3d69ee886b1044d8924cae859318090e8199186')):
            self.assertEqual(hashlib.sha256(lz77_decompress(rom, off)[0]).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main()
