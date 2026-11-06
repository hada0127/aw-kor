"""Current R12–R13 result generator and Part 1 cut-in contracts."""
import hashlib
import unittest
from collections import Counter
from pathlib import Path

import build_korean_full as build
from lz77_scan import lz77_decompress
from test_r11_result_graphics import pixels

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba'
SUMMARY_GOLDEN = '6082c9ef07cde601435e958a71537542adb5db721de8c3581c078ee9bd9752ce'
POWER_GOLDEN = '4cfd62fe94ba23180fbce05a38118e3ef8dcbbaf79d5cd83694400e502c7f193'
DAY_GOLDEN = 'f3de98eafd2770bfb6567c8a912290a2fbe312d5f504c7caf78d094d0ae60fdb'


class R12Graphics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = ORIGINAL.read_bytes()

    def test_day_generator_and_failure_rollback(self):
        rom = bytearray(self.original)
        build.patch_part2_battle_start_day_overlay_obj(rom)
        build.patch_part2_result_summary_obj(rom)
        day = lz77_decompress(rom, 0x45EC74)[0]
        self.assertEqual(hashlib.sha256(day).hexdigest(), DAY_GOLDEN)
        self.assertEqual(rom[0x34A3D0:0x34A3D4], self.original[0x34A3D0:0x34A3D4])
        self.assertEqual(rom[0xFDA000:0xFDB000], self.original[0xFDA000:0xFDB000])

    def test_summary_current_generator(self):
        rom = bytearray(self.original)
        build.patch_part2_result_summary_obj(rom)
        data = lz77_decompress(rom, 0x59DA5C)[0]
        self.assertEqual(hashlib.sha256(data).hexdigest(), SUMMARY_GOLDEN)
        art = pixels(data, 256, 256)
        for (x0, y0, x1, y1), expected in (
                ((0, 96, 48, 112), 0), ((64, 96, 104, 112), 64),
                ((128, 96, 192, 112), 128), ((0, 112, 64, 128), 0)):
            ink = [x for y in range(y0, y1) for x in range(x0, x1) if art[y][x]]
            self.assertEqual(min(ink), expected)
        congrat = [art[y][80:224] for y in range(80, 96)]
        self.assertEqual({v for row in congrat for v in row}, {0, 5, 6, 14})
        for gap in (22, 44, 66, 88, 110, 132):
            self.assertTrue(all(art[y][80+gap] == 0 for y in range(80, 96)), gap)
        face = Counter(v for row in congrat for v in row)
        self.assertGreater(face[6], 500)
        self.assertGreater(face[14], 300)

    def test_all_co_names_follow_native_gradient_bands(self):
        names = {int(addr, 16): text for addr, text in build.load_dialogue_overrides(
            str(ROOT / 'data/dialogue_overrides.json')).items()}
        dictionary = build.b84_full_power_dictionary(names)
        self.assertEqual(len(dictionary), 44)
        blocks = [build._b84_power_title_glyph_block(ch) for ch in dictionary]
        self.assertEqual(hashlib.sha256(b''.join(blocks)).hexdigest(), POWER_GOLDEN)
        native = lz77_decompress(self.original, 0xBC9D0C)[0]
        native_art = pixels(native[:256], 16, 32)
        native_bands = [13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2]
        first_rows = [next(y for y, row in enumerate(native_art) if color in row)
                      for color in native_bands]
        self.assertEqual(first_rows, [3, 6, 8, 10, 12, 14, 1, 17, 19, 21, 23, 25])
        for ch, block in zip(dictionary, blocks):
            art = pixels(block, 16, 32)
            ink = [(x, y) for y, row in enumerate(art) for x, v in enumerate(row) if v]
            self.assertTrue(all(0 < x < 15 and 0 < y < 31 for x, y in ink), ch)
            self.assertGreaterEqual(max(y for _, y in ink)-min(y for _, y in ink)+1, 28, ch)
            colors = Counter(v for row in art for v in row)
            self.assertLessEqual(set(colors), set(range(16)) - {1, 14})
            self.assertGreater(colors[15], 0, ch)
            self.assertGreater(colors[7], 0, ch)
            self.assertGreater(sum(colors[i] for i in (13, 12, 11, 10)), 0, ch)
            self.assertGreater(sum(colors[i] for i in (5, 4, 3, 2)), 0, ch)

    def test_b84_capacity_boundary(self):
        self.assertEqual(build.b84_glyph_stream_capacity(0x1000), 0x1000)
        with self.assertRaisesRegex(AssertionError, '4097 > 4096'):
            build.b84_glyph_stream_capacity(0x1001)


if __name__ == '__main__':
    unittest.main()
