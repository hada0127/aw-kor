import unittest
import json
from pathlib import Path

import build_title_hangul as title
from lz77_compress import lz77_compress_optimal


class SpriteStyleTest(unittest.TestCase):
    def test_white_envelope_encloses_option_shadow(self):
        for name, _, text, size in title.PART1_MODE_OPTION_BLOCKS:
            image = title.make_part1_option_block(text, size)
            for y in range(image.height):
                for x in range(image.width):
                    if image.getpixel((x, y)) not in (9, 14):
                        continue
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        xx, yy = x + dx, y + dy
                        self.assertTrue(0 <= xx < image.width and 0 <= yy < image.height, name)
                        self.assertNotEqual(image.getpixel((xx, yy)), 0, (name, x, y))

    def test_footer_excludes_japanese_shadow(self):
        footer = title.original_part1_footer(0xC18CB4)
        for point in ((60, 24), (61, 24), (58, 25), (59, 25), (60, 25)):
            self.assertEqual(footer.getpixel(point), 0)
        self.assertEqual(footer.getpixel((8, 25)), 12)
        self.assertNotIn(9, footer.getdata())

    def test_english_border_under_japanese_shadow_is_restored(self):
        for offset, columns in ((0xC194D8, (28, 29)), (0xC19D14, (24, 34)),
                                (0xC19FF0, (34,)), (0xC1A2BC, (30,))):
            original = title.original_part1_header(offset)
            footer = title.original_part1_footer(offset)
            for x in columns:
                self.assertEqual(original.getpixel((x, 24)), 9)
                self.assertEqual(footer.getpixel((x, 24)), 14)
        for offset, point in ((0xC18F48, (38, 25)), (0xC1A564, (56, 25)),
                              (0xC1A9DC, (57, 25))):
            self.assertEqual(title.original_part1_footer(offset).getpixel(point), 0)

    def test_all_header_footers_and_original_capacities(self):
        source = (Path(__file__).resolve().parents[1] /
                  'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        specs = [(off, text, size) for _, off, text, size in title.PART1_SUBMENU_LOGO_BLOCKS]
        specs += [(0xC18CB4, '작전룸', 20), (0xC18F48, '맵 선택', 20),
                  (0xC191E0, '숍 선택', 20), (0xC194D8, '하드 숍', 18),
                  (0xC19794, '캠페인', 20), (0xC19A9C, '모드 선택', 18),
                  (0xC19D14, '룰 선택', 20), (0xC19FF0, '팀 설정', 20)]
        for offset, text, size in specs:
            image = title.make_part1_header_with_footer(offset, text, size)
            footer = title.original_part1_footer(offset)
            y = 19 if offset in (0xC1A81C, 0xC1AC60, 0xC1B3A8, 0xC1B610) else 24
            self.assertEqual(image.crop((0, y, 80, 32)).tobytes(),
                             footer.crop((0, y, 80, 32)).tobytes(), hex(offset))
            packed = lz77_compress_optimal(title.part1_logo_layer_to_tiles(image), vram_safe=True)
            self.assertLessEqual(len(packed), title.lz77_decompress(source, offset)[1], hex(offset))

    def test_duplicate_label_requires_source_offset(self):
        with self.assertRaises(ValueError):
            title.make_part1_submenu_label_block('캠페인')

    def test_oversized_header_is_rejected(self):
        with self.assertRaises(ValueError):
            title.make_part1_header_with_footer(0xC18CB4, '플레이어' * 20, 20)

    def test_override_storage_grid_round_trip(self):
        from build_korean_full import _grid_to_tiles
        from export_sprites import tiles_to_indices
        records = json.loads((Path(__file__).resolve().parents[1] /
                              'data/sprites_overrides.json').read_text())
        for offset in (0xC03880, 0xC03AF0):
            record = records[f'lz77_{offset:08X}']
            _, _, text, size = next(row for row in title.PART1_MODE_OPTION_BLOCKS if row[1] == offset)
            raw = title.option_layer_to_tiles(title.make_part1_option_block(text, size))
            self.assertEqual(_grid_to_tiles(record['indices']), raw)
            grid, width, height = tiles_to_indices(raw, record['width'] // 8)
            self.assertEqual((width, height), (256, 16))
            self.assertEqual(grid, record['indices'])

    def test_header_edge_check_excludes_neighboring_carousel(self):
        from PIL import Image, ImageDraw
        from qa_visual_regions import count_top_left_label_edge_pixels
        image = Image.new('RGB', (240, 160), 'white')
        draw = ImageDraw.Draw(image)
        draw.rectangle((80, 0, 239, 159), fill=(255, 0, 0))
        draw.rectangle((0, 32, 239, 159), fill=(255, 0, 0))
        self.assertEqual(count_top_left_label_edge_pixels(image), 0)
        image.putpixel((78, 15), (255, 0, 0))
        self.assertGreater(count_top_left_label_edge_pixels(image), 0)


if __name__ == '__main__':
    unittest.main()
