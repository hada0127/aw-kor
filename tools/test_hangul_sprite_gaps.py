"""Final-index stroke-gap regression checks for every reworked menu label."""
import unittest
from pathlib import Path
from PIL import Image
import hangul_pixel_fit as fit
import build_title_hangul as title
from build_korean_full import patch_part2_mode_menu_obj_labels
from aw_fonts import obj_canvas
from lz77_scan import lz77_decompress
from bdf import load_bdf, glyph_grid

BIG = ((0x5B7930, '캠페인'), (0x5B7CB0, '자유전'), (0x5B7F38, '상점'),
       (0x5B82B4, '편집'), (0x5B8564, '통신'), (0x5B8850, '트라이얼'),
       (0x5B8B20, '사운드룸'))
SMALL = ((0x5B8E44, '캠페인'), (0x5B8F48, '자유전'), (0x5B9050, '상점'),
         (0x5B917C, '편집'), (0x5B9280, '통신'), (0x5B9378, '도전'))


def mask_from_indices(image, inks):
    return image.point(lambda v: 255 if v in inks else 0)


def check_large(image, records, inks):
    mask = mask_from_indices(image, inks)
    return [fit.verify_glyph(char, mask.crop(box)) for char, box in records
            if fit.dense_syllable(char)]


class HangulGapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = bytearray((Path(__file__).resolve().parents[1] /
                            'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes())
        patch_part2_mode_menu_obj_labels(cls.rom)

    def test_all_carousel_dense_syllables_in_final_palette(self):
        for _, off, text, size in title.PART1_MODE_OPTION_BLOCKS:
            image = title.make_part1_option_block(text, size)
            _, records = title.part1_option_body(text, size)
            for result in check_large(image, records, set(range(1, 7))):
                self.assertEqual(result['failures'], [], (hex(off), text, result))
                self.assertGreater(result['gap_columns'], 0, (hex(off), result))

    def test_all_large_mode_dense_syllables_in_final_palette(self):
        for off, text in BIG:
            grid = obj_canvas(lz77_decompress(self.rom, off)[0], 2, 8, 4)
            image = Image.new('L', (128, 32)); image.putdata([v for row in grid for v in row])
            _, records = fit.plate_line(text)
            records = [(c, (a + 6, b + 2, d + 6, e + 2)) for c, (a, b, d, e) in records]
            fit.verify_plate_ink(image, text)
            for char, box in records:
                actual = mask_from_indices(image.crop(box), {5})
                self.assertEqual(actual.tobytes(), fit.plate_glyph(char).tobytes())
                # The two compressed initials must retain BOTH counters.
                if char in ('통', '룸'):
                    self.assertEqual(actual.getpixel((5, 2)), 0)
                    self.assertEqual(actual.getpixel((5, 4)), 0)
                    self.assertEqual(actual.getpixel((5, 3)), 255)

    def test_small_glyphs_are_exact_native_grid_and_separated(self):
        font, _ = load_bdf(str(Path(__file__).resolve().parents[1] / 'reference/fonts/Galmuri9.bdf'))
        for off, text in SMALL:
            canvas = obj_canvas(lz77_decompress(self.rom, off)[0], 4, 4, 2)
            chars = [glyph_grid(font[ord(c)]) for c in text]
            width = sum(w for _, w, _, _, _ in chars) + len(chars) - 1
            height = max(h + yo for _, _, h, _, yo in chars)
            x = 4 + (120 - width) // 2; y = 3 + (9 - height) // 2
            for char, (grid, w, h, xo, yo) in zip(text, chars):
                for row in range(h):
                    for col in range(w):
                        self.assertEqual(canvas[y + height - h - yo + row][x + col + xo],
                                         1 if grid[row][col] else 5, (hex(off), char, col, row))
                self.assertTrue(all(canvas[yy][x + w] == 5 for yy in range(3, 12)))
                # Sensitive native glyph must actually contain separated bars.
                if fit.dense_syllable(char):
                    self.assertTrue(any(sum(v for v, _, _ in fit.runs([row[col] for row in grid])) >= 2
                                        for col in range(w)), (hex(off), char))
                x += w + 1
            self.assertTrue(all(canvas[2][x] == canvas[12][x] == 5 for x in range(4, 124)))

    def test_oracle_rejects_a_closed_gap(self):
        mask = fit.glyph('틀', 20, 22).copy()
        valid = fit.verify_glyph('틀', mask)
        self.assertFalse(valid['failures'])
        for x in range(mask.width):
            parts = fit.runs([mask.getpixel((x, y)) for y in range(mask.height)])
            gaps = [(a, b) for ink, a, b in parts[1:-1] if not ink]
            if gaps:
                a, b = gaps[0]
                for y in range(a, b): mask.putpixel((x, y), 255)
                break
        self.assertTrue(fit.verify_glyph('틀', mask)['failures'])

    def test_palette_image_uses_indices_without_grayscale_conversion(self):
        from PIL import ImageFont
        font = ImageFont.truetype(fit.aw_fonts.okdandan_path(), 24)
        for mode in ('L', 'P'):
            layer = Image.new(mode, (32, 32))
            records = fit.paint_native(layer, '실', font, (4, 0), fill=1, outline=14)
            crop = layer.crop(records[0][1])
            mask = Image.new('L', crop.size)
            mask.putdata([255 if v == 1 else 0 for v in crop.getdata()])
            self.assertFalse(fit.verify_glyph('실', mask)['failures'])

    def test_title_art_fits_the_actual_obj_rectangles(self):
        families = [(title.make_title_index_layer, title.TEXT_SPRITES + title.PROMPT_SPRITES),
                    (title.make_select_index_layer, title.SELECT_TOP_TEXT_SPRITES + title.SELECT_BOTTOM_TEXT_SPRITES + title.SELECT_PROMPT_SPRITES),
                    (title.make_part1_index_layer, title.PART1_TITLE_TEXT_SPRITES + title.PART1_PROMPT_SPRITES),
                    (title.make_part2_index_layer, title.PART2_TITLE_TEXT_SPRITES + title.PART2_PROMPT_SPRITES)]
        for render, sprites in families:
            layer = render()
            for y in range(layer.height):
                for x in range(layer.width):
                    if layer.getpixel((x, y)):
                        self.assertTrue(any(sx <= x < sx + w and sy <= y < sy + h
                                            for _, sx, sy, w, h, *_ in sprites),
                                        (render.__name__, x, y))

    def test_impossible_height_fails(self):
        with self.assertRaises(AssertionError):
            fit.fit_column([255, 0, 255, 0, 255], 4)


if __name__ == '__main__':
    unittest.main()
